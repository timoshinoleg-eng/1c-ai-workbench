//! Tauri commands exposed to the webview.
//!
//! Every command is a thin wrapper over state held in [`crate::AppState`].
//! The shape of these commands is mirrored in TypeScript by
//! `src/lib/api.ts` and `src/types/mcp.ts`.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;

use crate::config::CockpitConfig;
use crate::llm::{self, ChatMessage, ChatResponse};
use crate::mcp::{McpServerInfo, ServerTestResult};
use crate::AppState;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct McpToolResult {
    pub ok: bool,
    pub tool: String,
    pub server: String,
    pub elapsed_ms: u128,
    pub data: Value,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkbenchStatus {
    pub dump_path: String,
    pub index_exists: bool,
    pub index_file_count: u64,
    pub last_indexed_at: Option<String>,
    pub servers_running: u32,
    pub servers_total: u32,
    pub workbench_version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HealthCheckItem {
    pub name: String,
    pub area: String,
    pub status: String,
    pub message: String,
    pub why_it_matters: String,
    pub next_step: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HealthReport {
    pub status: String,
    pub generated_at: String,
    pub passed: u32,
    pub failed: u32,
    pub next_step: String,
    pub checks: Vec<HealthCheckItem>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ValidationCheck {
    pub name: String,
    pub status: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ValidationReport {
    pub ok: bool,
    pub path: String,
    pub xml_file_count: u64,
    pub metadata_dir_count: u64,
    pub checks: Vec<ValidationCheck>,
}

fn err<T: std::fmt::Display>(e: T) -> String {
    e.to_string()
}

#[tauri::command]
pub fn list_servers(state: State<'_, AppState>) -> Vec<McpServerInfo> {
    crate::list_servers(&state)
}

#[tauri::command]
pub async fn start_server(state: State<'_, AppState>, name: String) -> Result<(), String> {
    state.mcp.start_server(&name).await
}

#[tauri::command]
pub fn stop_server(state: State<'_, AppState>, name: String) -> Result<(), String> {
    state.mcp.stop(&name)
}

#[tauri::command]
pub async fn restart_server(state: State<'_, AppState>, name: String) -> Result<(), String> {
    state.mcp.restart(&name).await
}

#[tauri::command]
pub async fn test_server(state: State<'_, AppState>, name: String) -> Result<ServerTestResult, String> {
    state.mcp.test_server(&name).await
}

#[tauri::command]
pub async fn call_tool(
    state: State<'_, AppState>,
    server: String,
    tool: String,
    args: Value,
) -> Result<McpToolResult, String> {
    let started = Instant::now();
    match state.mcp.call_tool(&server, &tool, args).await {
        Ok(data) => Ok(McpToolResult {
            ok: true,
            tool,
            server,
            elapsed_ms: started.elapsed().as_millis(),
            data,
            error: None,
        }),
        Err(e) => Ok(McpToolResult {
            ok: false,
            tool,
            server,
            elapsed_ms: started.elapsed().as_millis(),
            data: Value::Null,
            error: Some(e),
        }),
    }
}

#[tauri::command]
pub fn get_status(state: State<'_, AppState>) -> WorkbenchStatus {
    let cfg = state.config.read();
    let servers = state.mcp.list();
    let running = servers
        .iter()
        .filter(|s| matches!(s.status, crate::mcp::ServerStatus::Running))
        .count() as u32;
    let dump_path = PathBuf::from(&cfg.dump_path);
    let index_dir = dump_path.join(".code-index");
    let index_exists = index_dir.exists();
    let index_file_count = if index_exists {
        walkdir_count(&index_dir)
    } else {
        0
    };
    let workbench_root = PathBuf::from(&cfg.workbench_path);
    let version = read_workbench_version(&workbench_root);
    WorkbenchStatus {
        dump_path: cfg.dump_path.clone(),
        index_exists,
        index_file_count,
        last_indexed_at: None,
        servers_running: running,
        servers_total: servers.len() as u32,
        workbench_version: version,
    }
}

#[tauri::command]
pub fn load_config(state: State<'_, AppState>) -> CockpitConfig {
    state.config.read().clone()
}

#[tauri::command]
pub fn validate_dump_dir(path: String) -> ValidationReport {
    validate_dump_path(PathBuf::from(path))
}

#[tauri::command]
pub fn validate_config(config: CockpitConfig) -> ValidationReport {
    validate_config_paths(config.with_derived_paths())
}

#[tauri::command]
pub fn save_config(state: State<'_, AppState>, config: CockpitConfig) -> Result<(), String> {
    let config = config.with_derived_paths();
    let path = crate::config::config_file_path().map_err(err)?;
    config.save(&path).map_err(err)?;
    {
        let mut current = state.config.write();
        *current = config.clone();
    }
    {
        let mut workbench_root = state.workbench_root.write();
        *workbench_root = PathBuf::from(&config.workbench_path);
    }
    state.mcp.refresh_from_config(&config);
    Ok(())
}

#[tauri::command]
pub async fn pick_dump_dir(app: AppHandle) -> Option<String> {
    let (tx, rx) = tokio::sync::oneshot::channel::<Option<PathBuf>>();
    app.dialog()
        .file()
        .set_title("Pick dump directory")
        .pick_folder(move |folder| {
            let _ = tx.send(folder.and_then(|fp| fp.into_path().ok()));
        });
    rx.await
        .ok()
        .flatten()
        .map(|p| p.to_string_lossy().into_owned())
}

#[tauri::command]
pub async fn pick_workbench_dir(app: AppHandle) -> Option<String> {
    let (tx, rx) = tokio::sync::oneshot::channel::<Option<PathBuf>>();
    app.dialog()
        .file()
        .set_title("Pick 1c-ai-workbench directory")
        .pick_folder(move |folder| {
            let _ = tx.send(folder.and_then(|fp| fp.into_path().ok()));
        });
    rx.await
        .ok()
        .flatten()
        .map(|p| p.to_string_lossy().into_owned())
}

#[tauri::command]
pub fn run_healthcheck(state: State<'_, AppState>) -> HealthReport {
    let started = chrono::Utc::now();
    let cfg = state.config.read().clone();
    let workbench_root = PathBuf::from(&cfg.workbench_path);
    let mut checks = Vec::new();
    let mut failed = 0u32;

    // 1. workbench root exists
    let wb_ok = workbench_root.exists();
    checks.push(HealthCheckItem {
        name: "workbench root".into(),
        area: "Workbench".into(),
        status: if wb_ok {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: workbench_root.to_string_lossy().into_owned(),
        why_it_matters: "Cockpit needs the workbench checkout to spawn MCP servers.".into(),
        next_step: "Set WORKBENCH_ROOT or update Settings.".into(),
    });
    if !wb_ok {
        failed += 1;
    }

    // 2. dump dir
    let dump = PathBuf::from(&cfg.dump_path);
    let dump_ok = dump.exists();
    checks.push(HealthCheckItem {
        name: "dump dir".into(),
        area: "Local Search".into(),
        status: if dump_ok {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: cfg.dump_path.clone(),
        why_it_matters: "The indexer reads the dump directory.".into(),
        next_step: "Pick a valid dump directory in Settings.".into(),
    });
    if !dump_ok {
        failed += 1;
    }

    // 3. bsl-indexer binary
    let bsl = workbench_root.join("tools/code-index-mcp/target/release/bsl-indexer.exe");
    let bsl_ok = bsl.exists();
    checks.push(HealthCheckItem {
        name: "bsl-indexer".into(),
        area: "Local Search".into(),
        status: if bsl_ok {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: bsl.to_string_lossy().into_owned(),
        why_it_matters: "bsl-indexer powers the 1c-code-index MCP server.".into(),
        next_step: "Run scripts\\03_build_bsl_indexer.ps1.".into(),
    });
    if !bsl_ok {
        failed += 1;
    }

    // 4. python
    let py_ok = which_exists("python") || which_exists("py");
    checks.push(HealthCheckItem {
        name: "python".into(),
        area: "Python bridges".into(),
        status: if py_ok {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: if py_ok {
            "python on PATH".into()
        } else {
            "python not found".into()
        },
        why_it_matters: "skills, prompt-gallery, help-index, ibcmd bridges are Python.".into(),
        next_step: "Install Python 3.10+ and ensure it is on PATH.".into(),
    });
    if !py_ok {
        failed += 1;
    }

    let passed = checks.len() as u32 - failed;
    let status = if failed == 0 { "Ready" } else { "Blocked" }.to_string();
    let next_step = checks
        .iter()
        .find(|c| c.status == "Blocked")
        .map(|c| c.next_step.clone())
        .unwrap_or_else(|| "Open the Cockpit and start the MCP servers.".to_string());

    HealthReport {
        status,
        generated_at: started.to_rfc3339(),
        passed,
        failed,
        next_step,
        checks,
    }
}

#[tauri::command]
pub async fn ping_server(
    state: State<'_, AppState>,
    name: String,
) -> Result<serde_json::Value, String> {
    let started = Instant::now();
    let result = state.mcp.ping(&name).await;
    let latency_ms = started.elapsed().as_millis();
    match result {
        Ok(_) => Ok(serde_json::json!({ "ok": true, "latencyMs": latency_ms })),
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub fn open_config_file() -> Result<(), String> {
    let path = crate::config::config_file_path().map_err(err)?;
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", &path.to_string_lossy()])
            .spawn()
            .map_err(err)?;
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = path; // unused on non-Windows
        return Err("open_config_file is only implemented on Windows".into());
    }
    Ok(())
}

fn walkdir_count(dir: &Path) -> u64 {
    let mut count = 0u64;
    for entry in walkdir::WalkDir::new(dir).into_iter().flatten() {
        if entry.file_type().is_file() {
            count += 1;
        }
    }
    count
}

fn read_workbench_version(root: &Path) -> String {
    let cargo = root.join("Cargo.toml");
    if !cargo.exists() {
        return "unknown".into();
    }
    if let Ok(content) = std::fs::read_to_string(&cargo) {
        for line in content.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("version") {
                if let Some(value) = trimmed.split('=').nth(1) {
                    return value.trim().trim_matches('"').to_string();
                }
            }
        }
    }
    "unknown".into()
}

fn validate_dump_path(path: PathBuf) -> ValidationReport {
    let mut checks = Vec::new();
    let exists = path.exists();
    checks.push(ValidationCheck {
        name: "path exists".into(),
        status: if exists {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: path.to_string_lossy().into_owned(),
    });

    let is_dir = exists && path.is_dir();
    checks.push(ValidationCheck {
        name: "is directory".into(),
        status: if is_dir {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: if is_dir {
            "directory is readable".into()
        } else {
            "not a directory".into()
        },
    });

    let metadata_dirs = [
        "Catalogs",
        "Documents",
        "CommonModules",
        "Reports",
        "DataProcessors",
        "Roles",
        "Subsystems",
    ];
    let metadata_dir_count = if is_dir {
        metadata_dirs
            .iter()
            .filter(|name| path.join(name).is_dir())
            .count() as u64
    } else {
        0
    };
    checks.push(ValidationCheck {
        name: "1C metadata directories".into(),
        status: if metadata_dir_count > 0 {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: format!("{metadata_dir_count} known metadata directories found"),
    });

    let xml_file_count = if is_dir {
        walkdir::WalkDir::new(&path)
            .max_depth(4)
            .into_iter()
            .flatten()
            .filter(|entry| {
                entry.file_type().is_file()
                    && entry
                        .path()
                        .extension()
                        .map(|ext| ext.to_string_lossy().eq_ignore_ascii_case("xml"))
                        .unwrap_or(false)
            })
            .count() as u64
    } else {
        0
    };
    checks.push(ValidationCheck {
        name: "XML files".into(),
        status: if xml_file_count > 0 {
            "Ready".into()
        } else {
            "Blocked".into()
        },
        message: format!("{xml_file_count} XML files found"),
    });

    ValidationReport {
        ok: checks.iter().all(|check| check.status == "Ready"),
        path: path.to_string_lossy().into_owned(),
        xml_file_count,
        metadata_dir_count,
        checks,
    }
}

fn validate_config_paths(cfg: CockpitConfig) -> ValidationReport {
    let mut checks = Vec::new();

    let dump = PathBuf::from(&cfg.dump_path);
    let dump_exists = dump.is_dir();
    push_check(
        &mut checks,
        "dump directory",
        dump_exists,
        if cfg.dump_path.is_empty() {
            "Pick a dump directory.".to_string()
        } else {
            cfg.dump_path.clone()
        },
    );

    let dump_markers = ["Configuration.xml", "Catalogs", "Documents"];
    let dump_marker_count = if dump_exists {
        dump_markers
            .iter()
            .filter(|marker| dump.join(marker).exists())
            .count() as u64
    } else {
        0
    };
    push_check(
        &mut checks,
        "dump layout",
        dump_marker_count > 0,
        if dump_marker_count > 0 {
            format!("{dump_marker_count} known 1C dump markers found")
        } else {
            "Expected Configuration.xml, Catalogs, or Documents.".to_string()
        },
    );

    let metadata_dirs = [
        "Catalogs",
        "Documents",
        "CommonModules",
        "Reports",
        "DataProcessors",
        "Roles",
        "Subsystems",
    ];
    let metadata_dir_count = if dump_exists {
        metadata_dirs
            .iter()
            .filter(|name| dump.join(name).is_dir())
            .count() as u64
    } else {
        0
    };
    let xml_file_count = if dump_exists {
        walkdir::WalkDir::new(&dump)
            .max_depth(4)
            .into_iter()
            .flatten()
            .filter(|entry| {
                entry.file_type().is_file()
                    && entry
                        .path()
                        .extension()
                        .map(|ext| ext.to_string_lossy().eq_ignore_ascii_case("xml"))
                        .unwrap_or(false)
            })
            .count() as u64
    } else {
        0
    };

    let workbench = PathBuf::from(&cfg.workbench_path);
    let workbench_exists = workbench.is_dir();
    push_check(
        &mut checks,
        "workbench directory",
        workbench_exists,
        if cfg.workbench_path.is_empty() {
            "Workbench not found. Browse to the installed 1c-ai-workbench root.".to_string()
        } else {
            cfg.workbench_path.clone()
        },
    );
    push_check(
        &mut checks,
        "bsl-indexer binary",
        crate::config::is_valid_workbench_root(&workbench),
        workbench
            .join("tools/code-index-mcp/target/release/bsl-indexer.exe")
            .to_string_lossy()
            .into_owned(),
    );

    for (name, relative_path) in [
        ("skills bridge", "tools/skills-bridge/server.py"),
        ("prompt gallery bridge", "tools/prompt-gallery/server.py"),
        ("help index bridge", "tools/help-index-mcp/server.py"),
        ("ibcmd bridge", "tools/ibcmd-bridge/server.py"),
    ] {
        let path = workbench.join(relative_path);
        push_check(
            &mut checks,
            name,
            path.is_file(),
            path.to_string_lossy().into_owned(),
        );
    }

    push_check(
        &mut checks,
        "code-index parent",
        parent_exists_or_can_create(&cfg.code_index_home),
        parent_message(&cfg.code_index_home),
    );
    push_check(
        &mut checks,
        "help-index parent",
        parent_exists_or_can_create(&cfg.help_db_path),
        parent_message(&cfg.help_db_path),
    );

    ValidationReport {
        ok: checks.iter().all(|check| check.status == "Ready"),
        path: cfg.workbench_path,
        xml_file_count,
        metadata_dir_count,
        checks,
    }
}

fn push_check(checks: &mut Vec<ValidationCheck>, name: &str, ok: bool, message: String) {
    checks.push(ValidationCheck {
        name: name.into(),
        status: if ok { "Ready".into() } else { "Blocked".into() },
        message,
    });
}

fn parent_exists_or_can_create(path: &str) -> bool {
    if path.is_empty() {
        return false;
    }
    let Some(parent) = Path::new(path).parent() else {
        return false;
    };
    if parent.is_dir() {
        return true;
    }
    fs::create_dir_all(parent).is_ok()
}

fn parent_message(path: &str) -> String {
    if path.is_empty() {
        return "Path is empty.".into();
    }
    Path::new(path)
        .parent()
        .map(|parent| parent.to_string_lossy().into_owned())
        .unwrap_or_else(|| "No parent directory.".into())
}

fn which_exists(cmd: &str) -> bool {
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("where")
            .arg(cmd)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
    #[cfg(not(target_os = "windows"))]
    {
        std::process::Command::new("which")
            .arg(cmd)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_root(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "cockpit-config-validation-{name}-{}",
            uuid::Uuid::new_v4()
        ))
    }

    fn touch(path: &Path) {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(path, b"").unwrap();
    }

    fn config_for(dump: &Path, workbench: &Path) -> CockpitConfig {
        CockpitConfig {
            dump_path: dump.to_string_lossy().into_owned(),
            workbench_path: workbench.to_string_lossy().into_owned(),
            code_index_home: workbench
                .join("generated/code-index-home")
                .to_string_lossy()
                .into_owned(),
            help_db_path: workbench
                .join("generated/help-index/help-index.db")
                .to_string_lossy()
                .into_owned(),
            servers: Default::default(),
            llm: Default::default(),
        }
    }

    #[test]
    fn validate_config_blocks_missing_workbench_layout() {
        let dump = temp_root("missing-dump");
        let workbench = temp_root("missing-workbench");
        touch(&dump.join("Configuration.xml"));

        let report = validate_config_paths(config_for(&dump, &workbench));

        assert!(!report.ok);
        assert!(report
            .checks
            .iter()
            .any(|check| check.name == "bsl-indexer binary" && check.status == "Blocked"));

        let _ = fs::remove_dir_all(dump);
        let _ = fs::remove_dir_all(workbench);
    }

    #[test]
    fn validate_config_accepts_complete_workbench_layout() {
        let dump = temp_root("ready-dump");
        let workbench = temp_root("ready-workbench");
        touch(&dump.join("Configuration.xml"));
        touch(&workbench.join("tools/code-index-mcp/target/release/bsl-indexer.exe"));
        touch(&workbench.join("tools/skills-bridge/server.py"));
        touch(&workbench.join("tools/prompt-gallery/server.py"));
        touch(&workbench.join("tools/help-index-mcp/server.py"));
        touch(&workbench.join("tools/ibcmd-bridge/server.py"));

        let report = validate_config_paths(config_for(&dump, &workbench));

        assert!(report.ok, "{:?}", report.checks);

        let _ = fs::remove_dir_all(dump);
        let _ = fs::remove_dir_all(workbench);
    }
}

#[tauri::command]
pub async fn chat_send(
    state: State<'_, AppState>,
    messages: Vec<ChatMessage>,
) -> Result<ChatResponse, String> {
    let (llm_cfg, dump_path) = {
        let cfg = state.config.read();
        (cfg.llm.clone(), cfg.dump_path.clone())
    };
    state
        .mcp
        .ensure_started()
        .await
        .map_err(|e| format!("start MCP servers: {e}"))?;
    llm::chat(&llm_cfg, &dump_path, messages, &state.mcp).await
}
