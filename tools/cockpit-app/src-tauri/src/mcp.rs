//! MCP server manager.
//!
//! The Cockpit owns the lifecycle of local MCP child processes and speaks
//! newline-delimited JSON-RPC over stdio. Each running server has one stdout
//! reader task that routes responses back to the request waiting on the same ID.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Arc;
use std::time::{Duration, Instant};

use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command};
use tokio::sync::{oneshot, Mutex as AsyncMutex};
use tokio::task::JoinHandle;

const STDERR_TAIL_LIMIT: usize = 2000;

/// Catalog of the 5 MCP servers documented for the Cockpit UI.
/// `opencode.jsonc` also contains `live-1c-bridge`, but that server is outside
/// the v0.2.0 cockpit catalog and remains a separate live COM bridge surface.
fn default_servers(workbench_root: &Path) -> HashMap<String, McpServer> {
    let mut m = HashMap::new();

    m.insert(
        "1c-code-index".into(),
        McpServer {
            name: "1c-code-index".into(),
            description: "BSL code navigation, object metadata, call graph".into(),
            command: workbench_root
                .join("tools/code-index-mcp/target/release/bsl-indexer.exe")
                .to_string_lossy()
                .into_owned(),
            args: vec![
                "serve".into(),
                "--path".into(),
                format!(
                    "onec={}",
                    workbench_root
                        .join("generated/index/source-mirror")
                        .to_string_lossy()
                ),
                "--transport".into(),
                "stdio".into(),
            ],
            env: vec![(
                "CODE_INDEX_HOME".into(),
                workbench_root
                    .join("generated/code-index-home")
                    .to_string_lossy()
                    .into_owned(),
            )],
            enabled: true,
            last_error_details: None,
        },
    );

    m.insert(
        "1c-skills".into(),
        McpServer {
            name: "1c-skills".into(),
            description: "Read-only 1C-specific skills (16 tools)".into(),
            command: "python".into(),
            args: vec![workbench_root
                .join("tools/skills-bridge/server.py")
                .to_string_lossy()
                .into_owned()],
            env: vec![(
                "SOURCE_MIRROR".into(),
                workbench_root
                    .join("generated/index/source-mirror")
                    .to_string_lossy()
                    .into_owned(),
            )],
            enabled: true,
            last_error_details: None,
        },
    );

    m.insert(
        "1c-prompt-gallery".into(),
        McpServer {
            name: "1c-prompt-gallery".into(),
            description: "Prompt catalog exposed as callable tools".into(),
            command: "python".into(),
            args: vec![workbench_root
                .join("tools/prompt-gallery/server.py")
                .to_string_lossy()
                .into_owned()],
            env: vec![],
            enabled: true,
            last_error_details: None,
        },
    );

    m.insert(
        "1c-help-index".into(),
        McpServer {
            name: "1c-help-index".into(),
            description: "Local 1C .hbk help search".into(),
            command: "python".into(),
            args: vec![workbench_root
                .join("tools/help-index-mcp/server.py")
                .to_string_lossy()
                .into_owned()],
            env: vec![(
                "WORKBENCH_ROOT".into(),
                workbench_root.to_string_lossy().into_owned(),
            )],
            enabled: true,
            last_error_details: None,
        },
    );

    m.insert(
        "1c-ibcmd".into(),
        McpServer {
            name: "1c-ibcmd".into(),
            description: "Phase B export/import (experimental, disabled by default)".into(),
            command: "python".into(),
            args: vec![workbench_root
                .join("tools/ibcmd-bridge/server.py")
                .to_string_lossy()
                .into_owned()],
            env: vec![
                ("IBCMD_EXE".into(), "ibcmd".into()),
                ("IBCMD_ALLOW_WRITE".into(), "0".into()),
            ],
            enabled: false,
            last_error_details: None,
        },
    );

    m
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServer {
    pub name: String,
    pub description: String,
    pub command: String,
    pub args: Vec<String>,
    #[serde(default)]
    pub env: Vec<(String, String)>,
    pub enabled: bool,
    #[serde(skip, default)]
    pub last_error_details: Option<ServerErrorDetails>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ServerErrorDetails {
    pub error_class: String,
    pub stderr_tail: String,
    pub command: String,
    pub env: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ServerStatus {
    Stopped,
    Starting,
    Running,
    Errored,
    Disabled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct McpServerInfo {
    pub name: String,
    pub description: String,
    pub status: ServerStatus,
    pub version: Option<String>,
    pub command: String,
    pub args: Vec<String>,
    pub env: HashMap<String, String>,
    pub enabled: bool,
    pub last_activity: Option<String>,
    pub last_error: Option<String>,
    #[serde(default)]
    pub last_error_details: Option<ServerErrorDetails>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: String,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

impl JsonRpcRequest {
    pub fn new(method: impl Into<String>, params: Value) -> Self {
        Self {
            jsonrpc: "2.0".into(),
            id: uuid::Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: Option<i64>,
    pub message: String,
    #[serde(default)]
    pub data: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: Option<String>,
    pub id: Option<Value>,
    #[serde(default)]
    pub result: Option<Value>,
    #[serde(default)]
    pub error: Option<JsonRpcError>,
}

impl JsonRpcResponse {
    fn id_key(&self) -> Option<String> {
        match self.id.as_ref()? {
            Value::String(value) => Some(value.clone()),
            Value::Number(value) => Some(value.to_string()),
            other => Some(other.to_string()),
        }
    }
}

type PendingMap = Arc<AsyncMutex<HashMap<String, oneshot::Sender<JsonRpcResponse>>>>;

#[derive(Clone)]
struct RequestHandles {
    stdin: Arc<AsyncMutex<ChildStdin>>,
    pending: PendingMap,
    last_activity: Arc<Mutex<Instant>>,
    last_error: Arc<Mutex<Option<String>>>,
}

struct RunningChild {
    child: Child,
    stdin: Arc<AsyncMutex<ChildStdin>>,
    pending: PendingMap,
    reader_task: JoinHandle<()>,
    stderr_task: JoinHandle<()>,
    last_activity: Arc<Mutex<Instant>>,
    last_error: Arc<Mutex<Option<String>>>,
    stderr_tail: Arc<Mutex<String>>,
}

pub struct McpManager {
    servers: Mutex<HashMap<String, McpServer>>,
    children: Mutex<HashMap<String, RunningChild>>,
    request_timeout: Duration,
}

impl McpManager {
    pub fn new(workbench_root: PathBuf) -> Self {
        Self {
            servers: Mutex::new(default_servers(&workbench_root)),
            children: Mutex::new(HashMap::new()),
            request_timeout: Duration::from_secs(30),
        }
    }

    #[cfg(test)]
    fn new_with_timeout(workbench_root: PathBuf, request_timeout: Duration) -> Self {
        Self {
            servers: Mutex::new(default_servers(&workbench_root)),
            children: Mutex::new(HashMap::new()),
            request_timeout,
        }
    }

    /// Replace the server definitions in place. Used after `load_config` so
    /// per-server enable/disable changes from the UI take effect.
    pub fn refresh_from_config(&self, cfg: &crate::config::CockpitConfig) {
        let mut guard = default_servers(&PathBuf::from(&cfg.workbench_path));
        for (name, entry) in &cfg.servers {
            if let Some(server) = guard.get_mut(name) {
                server.enabled = entry.enabled;
                if !entry.command.is_empty() {
                    server.command = entry.command.clone();
                    server.args = entry.args.clone();
                    server.env = entry
                        .env
                        .iter()
                        .map(|(k, v)| (k.clone(), v.clone()))
                        .collect();
                }
            } else {
                guard.insert(
                    name.clone(),
                    McpServer {
                        name: name.clone(),
                        description: String::new(),
                        command: entry.command.clone(),
                        args: entry.args.clone(),
                        env: entry
                            .env
                            .iter()
                            .map(|(k, v)| (k.clone(), v.clone()))
                            .collect(),
                        enabled: entry.enabled,
                        last_error_details: None,
                    },
                );
            }
        }
        *self.servers.lock() = guard;
    }

    pub fn list(&self) -> Vec<McpServerInfo> {
        let servers = self.servers.lock();
        let mut children = self.children.lock();
        servers
            .values()
            .map(|s| {
                let mut status = if !s.enabled {
                    ServerStatus::Disabled
                } else if children.contains_key(&s.name) {
                    ServerStatus::Running
                } else {
                    ServerStatus::Stopped
                };
                let mut last_error = children
                    .get(&s.name)
                    .and_then(|c| c.last_error.lock().clone());
                let mut last_error_details: Option<ServerErrorDetails> = None;
                if let Some(child) = children.get_mut(&s.name) {
                    match child.child.try_wait() {
                        Ok(Some(exit_status)) => {
                            status = ServerStatus::Errored;
                            let message = format!("process exited: {exit_status}");
                            let stderr_tail = child.stderr_tail.lock().clone();
                            *child.last_error.lock() = Some(message.clone());
                            last_error = Some(message);
                            last_error_details = Some(error_details_with_tail(
                                "server_crash",
                                &stderr_tail,
                                s,
                            ));
                        }
                        Ok(None) => {}
                        Err(e) => {
                            status = ServerStatus::Errored;
                            let message = format!("process status failed: {e}");
                            *child.last_error.lock() = Some(message.clone());
                            last_error = Some(message);
                            last_error_details = Some(error_details_with_tail(
                                "server_crash",
                                &e.to_string(),
                                s,
                            ));
                        }
                    }
                }
                if last_error_details.is_none() {
                    last_error_details = s.last_error_details.clone();
                }
                if last_error.is_none() && last_error_details.is_some() {
                    last_error = last_error_details.as_ref().map(|d| d.error_class.clone());
                }
                let env: HashMap<String, String> = s.env.iter().cloned().collect();
                McpServerInfo {
                    name: s.name.clone(),
                    description: s.description.clone(),
                    status,
                    version: None,
                    command: s.command.clone(),
                    args: s.args.clone(),
                    env,
                    enabled: s.enabled,
                    last_activity: children
                        .get(&s.name)
                        .and_then(|c| instant_to_rfc3339(*c.last_activity.lock())),
                    last_error,
                    last_error_details,
                }
            })
            .collect()
    }

    /// Start every enabled server that is not already running. Used by the
    /// chat tab to make sure tool calls actually have a server to dispatch
    /// against. Idempotent: already-running servers are skipped, and
    /// failures on one server do not abort the rest.
    pub async fn ensure_started(&self) -> Result<(), String> {
        let names: Vec<String> = {
            let servers = self.servers.lock();
            servers
                .iter()
                .filter(|(_, s)| s.enabled)
                .map(|(name, _)| name.clone())
                .collect()
        };
        let mut errors: Vec<String> = Vec::new();
        for name in names {
            if let Err(e) = self.start_server(&name).await {
                errors.push(format!("{name}: {e}"));
            }
        }
        if errors.is_empty() {
            Ok(())
        } else {
            Err(format!("some servers failed to start: {}", errors.join("; ")))
        }
    }

    pub async fn start_server(&self, name: &str) -> Result<(), String> {
        let server = {
            let servers = self.servers.lock();
            servers
                .get(name)
                .cloned()
                .ok_or_else(|| format!("unknown server '{name}'"))?
        };
        if !server.enabled {
            return Err(format!("server '{name}' is disabled"));
        }

        // Hold the children lock for the entire critical section
        // (check-running → spawn → insert). Otherwise two concurrent
        // start_server calls can both see "no entry" and both spawn a
        // child, leaking the first one's stdin handle and reader task.
        // (sec-fix-2026-06-23, race-fix)
        let mut children = self.children.lock();
        if let Some(running) = children.get_mut(name) {
            match running.child.try_wait() {
                Ok(None) => {
                    self.clear_server_error(name);
                    return Ok(());
                }
                Ok(Some(_)) | Err(_) => {
                    if let Some(old) = children.remove(name) {
                        old.reader_task.abort();
                        old.stderr_task.abort();
                    }
                }
            }
        }

        if let Err(e) = preflight_server(&server) {
            let details = error_details_from_message(&e, &server);
            self.set_server_error(name, details.clone());
            return Err(format!("{}; {e}", details.error_class));
        }

        let mut cmd = Command::new(&server.command);
        cmd.args(&server.args);
        for (k, v) in &server.env {
            cmd.env(k, v);
        }
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let mut child = match cmd.spawn() {
            Ok(child) => child,
            Err(e) => {
                let details = error_details_with_tail("spawn_failed", &e.to_string(), &server);
                self.set_server_error(name, details.clone());
                return Err(format!("{}; spawn failed for '{}': {e}", details.error_class, server.command));
            }
        };
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "child has no stdin".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "child has no stdout".to_string())?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| "child has no stderr".to_string())?;
        let pending: PendingMap = Arc::new(AsyncMutex::new(HashMap::new()));
        let last_activity = Arc::new(Mutex::new(Instant::now()));
        let last_error = Arc::new(Mutex::new(None));
        let stderr_tail = Arc::new(Mutex::new(String::new()));
        let reader_task = spawn_stdout_reader(
            stdout,
            Arc::clone(&pending),
            Arc::clone(&last_activity),
            Arc::clone(&last_error),
        );
        let stderr_task = spawn_stderr_reader(stderr, Arc::clone(&stderr_tail));

        children.insert(
            name.to_string(),
            RunningChild {
                child,
                stdin: Arc::new(AsyncMutex::new(stdin)),
                pending,
                reader_task,
                stderr_task,
                last_activity,
                last_error,
                stderr_tail,
            },
        );
        self.clear_server_error(name);
        Ok(())
    }

    pub fn stop(&self, name: &str) -> Result<(), String> {
        let mut children = self.children.lock();
        if let Some(mut running) = children.remove(name) {
            running.reader_task.abort();
            running.stderr_task.abort();
            let _ = running.child.start_kill();
        }
        Ok(())
    }

    pub fn stop_all(&self) {
        let mut children = self.children.lock();
        for (_, mut running) in children.drain() {
            running.reader_task.abort();
            running.stderr_task.abort();
            let _ = running.child.start_kill();
        }
    }

    fn set_server_error(&self, name: &str, details: ServerErrorDetails) {
        let mut servers = self.servers.lock();
        if let Some(server) = servers.get_mut(name) {
            server.last_error_details = Some(details);
        }
    }

    fn clear_server_error(&self, name: &str) {
        let mut servers = self.servers.lock();
        if let Some(server) = servers.get_mut(name) {
            server.last_error_details = None;
        }
    }

    pub async fn restart(&self, name: &str) -> Result<(), String> {
        self.stop(name)?;
        self.start_server(name).await
    }

    pub async fn call_tool(&self, server: &str, tool: &str, args: Value) -> Result<Value, String> {
        let request = JsonRpcRequest::new(
            "tools/call",
            serde_json::json!({
                "name": tool,
                "arguments": args,
            }),
        );
        self.send_json_rpc(server, request).await
    }

    pub async fn ping(&self, server: &str) -> Result<Value, String> {
        self.send_json_rpc(
            server,
            JsonRpcRequest::new("ping", Value::Object(Default::default())),
        )
        .await
    }

    async fn send_json_rpc(&self, server: &str, request: JsonRpcRequest) -> Result<Value, String> {
        let handles = self.handles_for(server).await?;
        let request_id = request.id.clone();
        let payload =
            serde_json::to_string(&request).map_err(|e| format!("serialize request: {e}"))? + "\n";
        let (tx, rx) = oneshot::channel();
        handles.pending.lock().await.insert(request_id.clone(), tx);

        let write_result: Result<(), String> = {
            let mut stdin = handles.stdin.lock().await;
            if let Err(e) = stdin
                .write_all(payload.as_bytes())
                .await
                .map_err(|e| format!("write stdin: {e}"))
            {
                Err(e)
            } else {
                stdin.flush().await.map_err(|e| format!("flush stdin: {e}"))
            }
        };

        if let Err(e) = write_result {
            handles.pending.lock().await.remove(&request_id);
            *handles.last_error.lock() = Some(e.clone());
            return Err(e);
        }

        let response = match tokio::time::timeout(self.request_timeout, rx).await {
            Ok(Ok(response)) => response,
            Ok(Err(_)) => {
                let message = format!("response channel closed for request {request_id}");
                *handles.last_error.lock() = Some(message.clone());
                return Err(message);
            }
            Err(_) => {
                handles.pending.lock().await.remove(&request_id);
                let message = format!("request {request_id} on server '{server}' timed out");
                *handles.last_error.lock() = Some(message.clone());
                return Err(message);
            }
        };

        *handles.last_activity.lock() = Instant::now();
        if let Some(error) = response.error {
            let message = if let Some(code) = error.code {
                format!("JSON-RPC error {code}: {}", error.message)
            } else {
                format!("JSON-RPC error: {}", error.message)
            };
            *handles.last_error.lock() = Some(message.clone());
            return Err(message);
        }
        *handles.last_error.lock() = None;
        Ok(response.result.unwrap_or(Value::Null))
    }

    async fn handles_for(&self, server: &str) -> Result<RequestHandles, String> {
        let mut should_restart = false;
        let handles = {
            let mut children = self.children.lock();
            match children.get_mut(server) {
                Some(running) => match running.child.try_wait() {
                    Ok(None) => Some(RequestHandles {
                        stdin: Arc::clone(&running.stdin),
                        pending: Arc::clone(&running.pending),
                        last_activity: Arc::clone(&running.last_activity),
                        last_error: Arc::clone(&running.last_error),
                    }),
                    Ok(Some(_)) | Err(_) => {
                        if let Some(old) = children.remove(server) {
                            old.reader_task.abort();
                            old.stderr_task.abort();
                        }
                        should_restart = true;
                        None
                    }
                },
                None => None,
            }
        };

        if let Some(handles) = handles {
            return Ok(handles);
        }
        if should_restart {
            self.start_server(server).await?;
            let children = self.children.lock();
            if let Some(running) = children.get(server) {
                return Ok(RequestHandles {
                    stdin: Arc::clone(&running.stdin),
                    pending: Arc::clone(&running.pending),
                    last_activity: Arc::clone(&running.last_activity),
                    last_error: Arc::clone(&running.last_error),
                });
            }
        }
        let preflight = {
            let servers = self.servers.lock();
            servers.get(server).cloned()
        };
        if let Some(server_cfg) = preflight {
            if let Err(e) = preflight_server(&server_cfg) {
                let details = error_details_from_message(&e, &server_cfg);
                self.set_server_error(server, details);
                return Err(format!("server '{server}' is not running; {e}"));
            }
        }
        Err(format!("server '{server}' is not running; start it from the server list or check Settings -> Workbench path"))
    }

    pub async fn test_server(&self, name: &str) -> Result<ServerTestResult, String> {
        let server = {
            let servers = self.servers.lock();
            servers
                .get(name)
                .cloned()
                .ok_or_else(|| format!("unknown server '{name}'"))?
        };
        if let Err(e) = preflight_server(&server) {
            return Ok(ServerTestResult {
                ok: false,
                exit_code: None,
                stdout: String::new(),
                stderr: String::new(),
                error: Some(e),
            });
        }

        let mut cmd = Command::new(&server.command);
        cmd.args(&server.args);
        for (k, v) in &server.env {
            cmd.env(k, v);
        }
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let mut child = match cmd.spawn() {
            Ok(child) => child,
            Err(e) => {
                return Ok(ServerTestResult {
                    ok: false,
                    exit_code: None,
                    stdout: String::new(),
                    stderr: String::new(),
                    error: Some(format!("spawn failed: {e}")),
                })
            }
        };

        // Give the server a moment to print startup diagnostics, then terminate it.
        tokio::time::sleep(Duration::from_millis(800)).await;
        let _ = child.start_kill();

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "child has no stdout".to_string())?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| "child has no stderr".to_string())?;
        let mut stdout_lines = BufReader::new(stdout).lines();
        let mut stderr_lines = BufReader::new(stderr).lines();
        let mut stdout_buf = String::new();
        let mut stderr_buf = String::new();

        while let Ok(Some(line)) = stdout_lines.next_line().await {
            stdout_buf.push_str(&line);
            stdout_buf.push('\n');
            if stdout_buf.len() >= 256 {
                break;
            }
        }
        while let Ok(Some(line)) = stderr_lines.next_line().await {
            stderr_buf.push_str(&line);
            stderr_buf.push('\n');
            if stderr_buf.len() >= 256 {
                break;
            }
        }

        let exit_code = child.wait().await.ok().and_then(|s| s.code());
        Ok(ServerTestResult {
            ok: exit_code == Some(0),
            exit_code,
            stdout: stdout_buf.chars().take(200).collect(),
            stderr: stderr_buf.chars().take(200).collect(),
            error: None,
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServerTestResult {
    pub ok: bool,
    pub exit_code: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub error: Option<String>,
}

fn preflight_server(server: &McpServer) -> Result<(), String> {
    if command_is_path(&server.command) {
        let command_path = PathBuf::from(&server.command);
        if !command_path.is_file() {
            return Err(format!("binary not found: {}", command_path.display()));
        }
    } else if !command_exists(&server.command) {
        return Err(format!("{} not in PATH", server.command));
    }

    if let Some(script) = server.args.iter().find(|arg| arg.ends_with(".py")) {
        let script_path = PathBuf::from(script);
        if !script_path.is_file() {
            return Err(format!(
                "server script not found: {}",
                script_path.display()
            ));
        }
    }

    Ok(())
}

fn error_details_from_message(message: &str, server: &McpServer) -> ServerErrorDetails {
    let error_class = classify_error_message(message);
    ServerErrorDetails {
        error_class: error_class.into(),
        stderr_tail: String::new(),
        command: server.command.clone(),
        env: server.env.iter().cloned().collect(),
    }
}

fn error_details_with_tail(
    error_class: &str,
    stderr_tail: &str,
    server: &McpServer,
) -> ServerErrorDetails {
    ServerErrorDetails {
        error_class: error_class.into(),
        stderr_tail: stderr_tail.into(),
        command: server.command.clone(),
        env: server.env.iter().cloned().collect(),
    }
}

fn classify_error_message(message: &str) -> &'static str {
    let lower = message.to_lowercase();
    if lower.contains("binary not found") {
        "binary_not_found"
    } else if lower.contains("not in path") && lower.contains("python") {
        "python_not_found"
    } else if lower.contains("server script not found") {
        "server_script_not_found"
    } else if lower.contains("permission denied") {
        "permission_denied"
    } else if lower.contains("timed out") {
        "timeout"
    } else if lower.contains("process exited") || lower.contains("stdout closed") {
        "server_crash"
    } else if lower.contains("spawn failed") {
        "spawn_failed"
    } else if lower.contains("not running") {
        "not_running"
    } else {
        "generic"
    }
}

fn command_is_path(command: &str) -> bool {
    let path = Path::new(command);
    path.is_absolute() || command.contains('\\') || command.contains('/')
}

fn command_exists(command: &str) -> bool {
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("where")
            .arg(command)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
    #[cfg(not(target_os = "windows"))]
    {
        std::process::Command::new("which")
            .arg(command)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

fn spawn_stdout_reader(
    stdout: ChildStdout,
    pending: PendingMap,
    last_activity: Arc<Mutex<Instant>>,
    last_error: Arc<Mutex<Option<String>>>,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut lines = BufReader::new(stdout).lines();
        loop {
            match lines.next_line().await {
                Ok(Some(line)) => {
                    if line.trim().is_empty() {
                        continue;
                    }
                    match serde_json::from_str::<JsonRpcResponse>(&line) {
                        Ok(response) => {
                            *last_activity.lock() = Instant::now();
                            if let Some(id) = response.id_key() {
                                if let Some(tx) = pending.lock().await.remove(&id) {
                                    let _ = tx.send(response);
                                }
                            }
                        }
                        Err(e) => {
                            *last_error.lock() =
                                Some(format!("invalid JSON from child: {e}; raw: {line}"));
                        }
                    }
                }
                Ok(None) => {
                    *last_error.lock() = Some("stdout closed".into());
                    break;
                }
                Err(e) => {
                    *last_error.lock() = Some(format!("read stdout: {e}"));
                    break;
                }
            }
        }
    })
}

fn spawn_stderr_reader(stderr: ChildStderr, tail: Arc<Mutex<String>>) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut lines = BufReader::new(stderr).lines();
        loop {
            match lines.next_line().await {
                Ok(Some(line)) => {
                    let mut tail = tail.lock();
                    tail.push_str(&line);
                    tail.push('\n');
                    if tail.len() > STDERR_TAIL_LIMIT {
                        let start = tail.len() - STDERR_TAIL_LIMIT;
                        let split_at = tail[start..].find('\n').map(|i| start + i + 1).unwrap_or(start);
                        tail.replace_range(..split_at, "");
                    }
                }
                Ok(None) => break,
                Err(_) => break,
            }
        }
    })
}

fn instant_to_rfc3339(instant: Instant) -> Option<String> {
    chrono::Utc::now()
        .checked_sub_signed(chrono::Duration::from_std(instant.elapsed()).unwrap_or_default())
        .map(|t| t.to_rfc3339())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn python_command() -> String {
        std::env::var("PYTHON").unwrap_or_else(|_| "python".to_string())
    }

    fn manager_with_server(name: &str, code: &str, timeout: Duration) -> McpManager {
        let manager = McpManager::new_with_timeout(std::env::temp_dir(), timeout);
        manager.servers.lock().insert(
            name.to_string(),
            McpServer {
                name: name.to_string(),
                description: "mock".into(),
                command: python_command(),
                args: vec!["-u".into(), "-c".into(), code.into()],
                env: vec![],
                enabled: true,
                last_error_details: None,
            },
        );
        manager
    }

    #[test]
    fn json_rpc_request_has_tools_call_shape() {
        let request = JsonRpcRequest::new(
            "tools/call",
            json!({"name": "search_text", "arguments": {"query": "x"}}),
        );
        assert_eq!(request.jsonrpc, "2.0");
        assert_eq!(request.method, "tools/call");
        assert!(request.id.len() > 10);
        assert_eq!(request.params["name"], "search_text");
    }

    #[test]
    fn default_catalog_contains_five_cockpit_servers() {
        let root = PathBuf::from(r"C:\1c-ai-workbench");
        let servers = default_servers(&root);
        let mut names = servers.keys().cloned().collect::<Vec<_>>();
        names.sort();
        assert_eq!(
            names,
            vec![
                "1c-code-index".to_string(),
                "1c-help-index".to_string(),
                "1c-ibcmd".to_string(),
                "1c-prompt-gallery".to_string(),
                "1c-skills".to_string()
            ]
        );
        assert!(!servers["1c-ibcmd"].enabled);
    }

    #[tokio::test]
    async fn start_server_tracks_running_child() {
        let code = "import time\nwhile True:\n    time.sleep(0.1)\n";
        let manager = manager_with_server("mock", code, Duration::from_secs(1));
        manager.start_server("mock").await.unwrap();
        let server = manager
            .list()
            .into_iter()
            .find(|item| item.name == "mock")
            .unwrap();
        assert!(matches!(server.status, ServerStatus::Running));
        manager.stop("mock").unwrap();
    }

    #[tokio::test]
    async fn call_tool_correlates_response_by_id() {
        let code = r#"
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {"tool": req["params"]["name"], "args": req["params"]["arguments"]}}), flush=True)
"#;
        let manager = manager_with_server("mock", code, Duration::from_secs(2));
        manager.start_server("mock").await.unwrap();
        let result = manager
            .call_tool("mock", "search_text", json!({"query": "Products"}))
            .await
            .unwrap();
        assert_eq!(result["tool"], "search_text");
        assert_eq!(result["args"]["query"], "Products");
        manager.stop("mock").unwrap();
    }

    #[tokio::test]
    async fn call_tool_times_out() {
        let code = "import time, sys\nfor line in sys.stdin:\n    time.sleep(1)\n";
        let manager = manager_with_server("mock", code, Duration::from_millis(50));
        manager.start_server("mock").await.unwrap();
        let err = manager
            .call_tool("mock", "slow", json!({}))
            .await
            .unwrap_err();
        assert!(err.contains("timed out"));
        manager.stop("mock").unwrap();
    }

    #[tokio::test]
    async fn call_tool_requires_running_server() {
        let manager = McpManager::new_with_timeout(std::env::temp_dir(), Duration::from_millis(50));
        let err = manager
            .call_tool("missing", "search_text", json!({}))
            .await
            .unwrap_err();
        assert!(err.contains("not running"));
    }
}
