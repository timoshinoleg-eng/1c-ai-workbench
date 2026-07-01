//! Persisted Cockpit configuration.
//!
//! The file lives under the OS user config dir (e.g. `%APPDATA%\1c-ai-cockpit\config.json`)
//! and is the source of truth for the UI settings store. The in-memory copy is
//! mirrored in [`crate::AppState`].

use std::collections::HashMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

const DEFAULT_DUMP_PATH: &str = r"C:\1c-ai-client\dump";
const CODE_INDEX_HOME_RELATIVE: &str = r"generated\code-index-home";
const HELP_DB_RELATIVE: &str = r"generated\help-index\help-index.db";
const WORKBENCH_MARKER_RELATIVE: &str = r"tools\code-index-mcp\target\release\bsl-indexer.exe";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServerConfig {
    pub enabled: bool,
    pub command: String,
    pub args: Vec<String>,
    #[serde(default)]
    pub env: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct LlmConfig {
    #[serde(default)]
    pub api_key: String,
    #[serde(default = "default_llm_base_url")]
    pub base_url: String,
    #[serde(default = "default_llm_model")]
    pub model: String,
}

fn default_llm_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}

fn default_llm_model() -> String {
    "gpt-4o-mini".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CockpitConfig {
    #[serde(alias = "dump_path")]
    pub dump_path: String,
    #[serde(alias = "workbench_path")]
    pub workbench_path: String,
    #[serde(alias = "code_index_home")]
    pub code_index_home: String,
    #[serde(alias = "help_db_path")]
    pub help_db_path: String,
    #[serde(default)]
    pub servers: HashMap<String, ServerConfig>,
    #[serde(default)]
    pub llm: LlmConfig,
}

impl Default for CockpitConfig {
    fn default() -> Self {
        let workbench_root = detect_workbench_root();
        let (workbench_path, code_index_home, help_db_path) = match workbench_root {
            Some(root) => {
                let workbench_path = root.to_string_lossy().into_owned();
                let code_index_home = root
                    .join(CODE_INDEX_HOME_RELATIVE)
                    .to_string_lossy()
                    .into_owned();
                let help_db_path = root.join(HELP_DB_RELATIVE).to_string_lossy().into_owned();
                (workbench_path, code_index_home, help_db_path)
            }
            None => (String::new(), String::new(), String::new()),
        };

        Self {
            dump_path: String::from(DEFAULT_DUMP_PATH),
            workbench_path,
            code_index_home,
            help_db_path,
            servers: HashMap::new(),
            llm: LlmConfig::default(),
        }
    }
}

pub fn detect_workbench_root() -> Option<PathBuf> {
    workbench_candidates()
        .into_iter()
        .find(|candidate| is_valid_workbench_root(candidate))
}

pub fn is_valid_workbench_root(path: &Path) -> bool {
    path.is_dir() && path.join(WORKBENCH_MARKER_RELATIVE).is_file()
}

fn workbench_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(value) = std::env::var("WORKBENCH_ROOT") {
        push_candidate(&mut candidates, PathBuf::from(value));
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            push_candidate(&mut candidates, exe_dir.to_path_buf());
            push_candidate(&mut candidates, exe_dir.join("workbench"));
            push_candidate(&mut candidates, exe_dir.join("1c-ai-workbench"));
            if let Some(parent) = exe_dir.parent() {
                push_candidate(&mut candidates, parent.join("workbench"));
                push_candidate(&mut candidates, parent.join("1c-ai-workbench"));
            }
        }
    }

    push_candidate(&mut candidates, PathBuf::from(r"C:\1c-ai-workbench"));
    push_candidate(
        &mut candidates,
        PathBuf::from(r"C:\Program Files\1c-ai-workbench"),
    );

    if let Some(local) = dirs::data_local_dir() {
        push_candidate(&mut candidates, local.join("1c-ai-workbench"));
        push_candidate(&mut candidates, local.join("1c-ai-workbench").join("embedded"));
    }
    if let Some(home) = dirs::home_dir() {
        push_candidate(&mut candidates, home.join("1c-ai-workbench"));
    }

    candidates
}

#[allow(dead_code)]
pub fn internal_workbench_candidates() -> Vec<PathBuf> {
    workbench_candidates()
}

fn push_candidate(candidates: &mut Vec<PathBuf>, candidate: PathBuf) {
    if candidate.as_os_str().is_empty() {
        return;
    }
    if !candidates.iter().any(|existing| existing == &candidate) {
        candidates.push(candidate);
    }
}

pub fn config_dir() -> io::Result<PathBuf> {
    let base = dirs::config_dir()
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "no config dir"))?;
    let dir = base.join("1c-ai-cockpit");
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

pub fn config_file_path() -> io::Result<PathBuf> {
    Ok(config_dir()?.join("config.json"))
}

impl CockpitConfig {
    pub fn load(path: &Path) -> Result<Self, String> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let raw = fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?;
        serde_json::from_str(&raw).map_err(|e| format!("parse {}: {e}", path.display()))
    }

    pub fn save(&self, path: &Path) -> io::Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let pretty = serde_json::to_string_pretty(self)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        fs::write(path, pretty)
    }

    pub fn with_derived_paths(mut self) -> Self {
        if !self.workbench_path.is_empty() {
            let root = PathBuf::from(&self.workbench_path);
            if self.code_index_home.is_empty() {
                self.code_index_home = root
                    .join(CODE_INDEX_HOME_RELATIVE)
                    .to_string_lossy()
                    .into_owned();
            }
            if self.help_db_path.is_empty() {
                self.help_db_path = root.join(HELP_DB_RELATIVE).to_string_lossy().into_owned();
            }
        }
        self
    }
}
