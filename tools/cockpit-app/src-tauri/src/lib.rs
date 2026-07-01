//! 1C AI Cockpit — Tauri 2.x entry point.
//!
//! Responsibilities:
//!  * Build the Tauri application.
//!  * Register plugins (fs, dialog, shell).
//!  * Register the IPC commands defined in `commands.rs`.
//!  * Own the shared state (config, MCP manager).
//!
//! Note: tauri-plugin-updater is intentionally not wired in v0.1.0. Auto-update
//! requires a code-signing certificate on Windows. We will add it in v0.5.0
//! once we have a cert. Until then, users update by re-running the installer.

pub mod commands;
pub mod config;
mod embedded;
mod llm;
mod mcp;

pub use embedded::*;
pub use llm::{chat as llm_chat, ChatMessage, ChatResponse, ChatTurn};

use std::path::Path;
use std::sync::Arc;

use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

use crate::config::CockpitConfig;
use crate::mcp::{McpManager, McpServerInfo};

pub struct AppState {
    pub config: parking_lot::RwLock<CockpitConfig>,
    pub mcp: Arc<McpManager>,
    pub workbench_root: parking_lot::RwLock<std::path::PathBuf>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            // Resolve a config file under the OS user config dir. On first run
            // we write a default config so the UI can render.
            let cfg_path = config::config_file_path()
                .unwrap_or_else(|_| std::path::PathBuf::from("cockpit-config.json"));
            let mut cfg = CockpitConfig::load(&cfg_path)
                .unwrap_or_default()
                .with_derived_paths();
            if cfg.workbench_path.is_empty() {
                if let Some(detected) = config::detect_workbench_root() {
                    cfg.workbench_path = detected.to_string_lossy().into_owned();
                    cfg = cfg.with_derived_paths();
                }
            }
            if let Err(e) = cfg.save(&cfg_path) {
                log::warn!(
                    "could not persist initial config to {}: {e}",
                    cfg_path.display()
                );
            }

            let embedded_root = embedded::embedded_workbench_path(app.handle());
            if let Some(ref embedded_root) = embedded_root {
                log::info!("using embedded workbench at {}", embedded_root.display());
                if cfg.workbench_path.is_empty() || !config::is_valid_workbench_root(Path::new(&cfg.workbench_path)) {
                    cfg.workbench_path = embedded_root.to_string_lossy().into_owned();
                    cfg = cfg.with_derived_paths();
                    if let Err(e) = cfg.save(&cfg_path) {
                        log::warn!("could not persist config with embedded path: {e}");
                    }
                }
            }

            let workbench_root = std::path::PathBuf::from(&cfg.workbench_path);
            let mcp = Arc::new(McpManager::new(workbench_root.clone()));
            mcp.refresh_from_config(&cfg);

            app.manage(AppState {
                config: parking_lot::RwLock::new(cfg),
                mcp,
                workbench_root: parking_lot::RwLock::new(workbench_root.clone()),
            });

            // Sanity-check that the dialog plugin is wired up at runtime.
            // This forces a non-noop DialogExt import so the dependency
            // is not pruned.
            let _ = app.dialog();

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Tear down all running MCP child processes before exit.
                if let Some(state) = window.app_handle().try_state::<AppState>() {
                    state.mcp.stop_all();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::list_servers,
            commands::start_server,
            commands::stop_server,
            commands::restart_server,
            commands::test_server,
            commands::call_tool,
            commands::get_status,
            commands::load_config,
            commands::save_config,
            commands::validate_dump_dir,
            commands::validate_config,
            commands::pick_dump_dir,
            commands::pick_workbench_dir,
            commands::run_healthcheck,
            commands::ping_server,
            commands::open_config_file,
            commands::chat_send,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Convenience: list servers in the format the UI expects.
pub(crate) fn list_servers(state: &AppState) -> Vec<McpServerInfo> {
    state.mcp.list()
}
