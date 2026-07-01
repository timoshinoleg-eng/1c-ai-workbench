use cockpit_lib::{EmbeddedInstaller, config};
use std::sync::Mutex;

static DEST_ROOT_LOCK: Mutex<()> = Mutex::new(());

#[test]
fn test_dest_root_is_appdata_local() {
    let _guard = DEST_ROOT_LOCK.lock().unwrap();
    let installer = EmbeddedInstaller::new();
    let root = installer.dest_root();
    assert!(root.starts_with(dirs::data_local_dir().unwrap()));
    assert!(root.to_string_lossy().contains("1c-ai-workbench"));
    assert!(root.to_string_lossy().ends_with("embedded"));
}

#[test]
fn test_not_installed_when_no_sentinel() {
    let _guard = DEST_ROOT_LOCK.lock().unwrap();
    let installer = EmbeddedInstaller::new();
    assert!(!installer.is_installed());
}

#[test]
fn test_installed_when_sentinel_matches_version() {
    let _guard = DEST_ROOT_LOCK.lock().unwrap();
    let installer = EmbeddedInstaller::new();
    let root = installer.dest_root();
    std::fs::create_dir_all(&root).unwrap();
    let sentinel = root.join(".embedded-by-cockpit-v1");
    std::fs::write(&sentinel, serde_json::json!({
        "version": env!("CARGO_PKG_VERSION"),
        "extracted_at": "2026-06-25T00:00:00Z"
    }).to_string()).unwrap();
    assert!(installer.is_installed());
    std::fs::remove_dir_all(&root).unwrap();
}

#[test]
fn test_version_mismatch_returns_not_installed() {
    let _guard = DEST_ROOT_LOCK.lock().unwrap();
    let installer = EmbeddedInstaller::new();
    let root = installer.dest_root();
    std::fs::create_dir_all(&root).unwrap();
    let sentinel = root.join(".embedded-by-cockpit-v1");
    std::fs::write(&sentinel, serde_json::json!({
        "version": "0.0.0",
        "extracted_at": "2026-01-01T00:00:00Z"
    }).to_string()).unwrap();
    assert!(!installer.is_installed());
    std::fs::remove_dir_all(&root).unwrap();
}

#[test]
fn test_workbench_candidates_contains_embedded_path() {
    let _guard = DEST_ROOT_LOCK.lock().unwrap();
    let candidates: Vec<std::path::PathBuf> = config::internal_workbench_candidates();
    let has_embedded = candidates.iter().any(|c: &std::path::PathBuf| {
        c.to_string_lossy().contains("1c-ai-workbench") &&
        c.to_string_lossy().contains("embedded")
    });
    assert!(has_embedded, "embedded path not in workbench candidates");
}
