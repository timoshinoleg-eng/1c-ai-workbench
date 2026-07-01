//! Embedded workbench installer.
//!
//! On first run Cockpit extracts the resources baked into the Tauri bundle to
//! `%LOCALAPPDATA%\1c-ai-workbench\embedded\`.  A sentinel file records the
//! package version so we only re-extract when the application version changes.

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use uuid::Uuid;
use walkdir::WalkDir;

const SENTINEL_NAME: &str = ".embedded-by-cockpit-v1";
const EMBEDDED_DIR_NAME: &str = "embedded";
const WORKBENCH_DIR_NAME: &str = "1c-ai-workbench";

/// Description of the resources that ship inside the application bundle.
#[derive(Debug, Clone)]
pub struct ResourceManifest {
    pub version: String,
    pub items: Vec<ResourceItem>,
}

/// A single bundled resource.
///
/// `relative_path` is the path inside `app_handle.path().resource_dir()`.
/// If it ends with `/**` it is expanded at runtime as a directory glob.
/// `dest_name` is the relative path under the extraction root.
#[derive(Debug, Clone)]
pub struct ResourceItem {
    pub relative_path: String,
    pub dest_name: PathBuf,
}

impl ResourceManifest {
    fn bundled() -> Self {
        Self {
            version: env!("CARGO_PKG_VERSION").to_owned(),
            items: vec![
                ResourceItem {
                    relative_path: String::from(
                        "tools/code-index-mcp/target/release/bsl-indexer.exe",
                    ),
                    dest_name: PathBuf::from(
                        "tools/code-index-mcp/target/release/bsl-indexer.exe",
                    ),
                },
                ResourceItem {
                    relative_path: String::from("tools/skills-bridge/**"),
                    dest_name: PathBuf::from("tools/skills-bridge"),
                },
                ResourceItem {
                    relative_path: String::from("tools/prompt-gallery/**"),
                    dest_name: PathBuf::from("tools/prompt-gallery"),
                },
                ResourceItem {
                    relative_path: String::from("tools/help-index-mcp/**"),
                    dest_name: PathBuf::from("tools/help-index-mcp"),
                },
                ResourceItem {
                    relative_path: String::from("configs/opencode-mcp.jsonc"),
                    dest_name: PathBuf::from("configs/opencode-mcp.jsonc"),
                },
            ],
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct Sentinel {
    version: String,
    extracted_at: String,
}

/// Installer state.  Cheap to construct and can be used to check whether the
/// embedded workbench is already on disk.
pub struct EmbeddedInstaller {
    manifest: ResourceManifest,
    dest_root: PathBuf,
    sentinel_path: PathBuf,
}

impl Default for EmbeddedInstaller {
    fn default() -> Self {
        Self::new()
    }
}

impl EmbeddedInstaller {
    pub fn new() -> Self {
        let dest_root = dirs::data_local_dir()
            .map(|local| local.join(WORKBENCH_DIR_NAME).join(EMBEDDED_DIR_NAME))
            .unwrap_or_else(|| PathBuf::from(WORKBENCH_DIR_NAME).join(EMBEDDED_DIR_NAME));

        Self {
            manifest: ResourceManifest::bundled(),
            sentinel_path: dest_root.join(SENTINEL_NAME),
            dest_root,
        }
    }

    /// Returns the directory the embedded workbench would be extracted into.
    pub fn dest_root(&self) -> &PathBuf {
        &self.dest_root
    }

    /// Checks whether the sentinel exists and was written by the same package
    /// version that is currently running.
    pub fn is_installed(&self) -> bool {
        if !self.dest_root.is_dir() || !self.sentinel_path.is_file() {
            return false;
        }

        let raw = match fs::read_to_string(&self.sentinel_path) {
            Ok(raw) => raw,
            Err(e) => {
                log::debug!(
                    "could not read embedded sentinel {}: {e}",
                    self.sentinel_path.display()
                );
                return false;
            }
        };

        let sentinel: Sentinel = match serde_json::from_str(&raw) {
            Ok(s) => s,
            Err(e) => {
                log::debug!(
                    "corrupted embedded sentinel {}: {e}",
                    self.sentinel_path.display()
                );
                return false;
            }
        };

        sentinel.version == self.manifest.version
    }

    /// Extracts all bundled resources to disk.
    ///
    /// The extraction is performed into a temporary directory next to the
    /// destination and then renamed atomically so the destination is never in
    /// a partially-written state.
    pub fn extract(&self, app_handle: &AppHandle) -> Result<PathBuf> {
        let resource_dir = app_handle
            .path()
            .resource_dir()
            .map_err(|e| anyhow!("failed to resolve resource directory: {e}"))?;

        let sources = self.collect_sources(&resource_dir)?;

        // The bsl-indexer.exe marker is the canonical indicator that the
        // workbench resources were actually bundled.
        let bsl_item = PathBuf::from(bsl_item_str());
        if !sources.iter().any(|(_, dest)| dest == &bsl_item) {
            return Err(anyhow!(
                "bsl-indexer.exe not found in bundled resources at {}",
                resource_dir.join(&bsl_item).display()
            ));
        }

        let required_bytes = Self::required_space(&sources)?;
        let dest_parent = self
            .dest_root
            .parent()
            .ok_or_else(|| anyhow!("embedded destination has no parent directory"))?;

        fs::create_dir_all(dest_parent)
            .with_context(|| format!("creating {}", dest_parent.display()))?;

        let available = available_space(dest_parent)?;
        if available < required_bytes {
            return Err(anyhow!(
                "insufficient disk space at {}: {} bytes required (2x embedded size), {} available",
                dest_parent.display(),
                required_bytes,
                available
            ));
        }

        let temp_dir = dest_parent.join(format!("extract-{}", Uuid::new_v4()));
        fs::create_dir(&temp_dir)
            .with_context(|| format!("creating temporary extraction directory {}", temp_dir.display()))?;

        for (src, dest_rel) in &sources {
            let dest = temp_dir.join(dest_rel);
            if let Some(parent) = dest.parent() {
                fs::create_dir_all(parent)
                    .with_context(|| format!("creating {}", parent.display()))?;
            }
            fs::copy(src, &dest).with_context(|| {
                format!("copying {} -> {}", src.display(), dest.display())
            })?;
        }

        // Remove a previous extraction if present; `fs::rename` on Windows does
        // not overwrite existing directories.
        if self.dest_root.exists() {
            fs::remove_dir_all(&self.dest_root)
                .with_context(|| format!("removing old {}", self.dest_root.display()))?;
        }

        fs::rename(&temp_dir, &self.dest_root)
            .with_context(|| format!("renaming {} -> {}", temp_dir.display(), self.dest_root.display()))?;

        let sentinel = Sentinel {
            version: self.manifest.version.clone(),
            extracted_at: chrono::Utc::now().to_rfc3339(),
        };
        let sentinel_json = serde_json::to_string_pretty(&sentinel)
            .map_err(|e| anyhow!("serializing sentinel: {e}"))?;
        fs::write(&self.sentinel_path, sentinel_json)
            .with_context(|| format!("writing sentinel {}", self.sentinel_path.display()))?;

        Ok(self.dest_root.clone())
    }

    fn collect_sources(&self, resource_dir: &Path) -> Result<Vec<(PathBuf, PathBuf)>> {
        let mut sources = Vec::new();

        for item in &self.manifest.items {
            if let Some(prefix) = item.relative_path.strip_suffix("/**") {
                let src_base = resource_dir.join(prefix);
                if !src_base.exists() {
                    return Err(anyhow!(
                        "embedded resource directory not found: {}",
                        src_base.display()
                    ));
                }

                for entry in WalkDir::new(&src_base)
                    .into_iter()
                    .filter_map(|e| e.ok())
                    .filter(|e| e.file_type().is_file())
                {
                    let rel = entry
                        .path()
                        .strip_prefix(&src_base)
                        .map_err(|e| anyhow!("computing relative path: {e}"))?;
                    let dest = item.dest_name.join(rel);
                    sources.push((entry.path().to_path_buf(), dest));
                }
            } else {
                let src = resource_dir.join(&item.relative_path);
                if !src.exists() {
                    if item.relative_path == bsl_item_str() {
                        return Err(anyhow!(
                            "bsl-indexer.exe not found in bundled resources at {}",
                            src.display()
                        ));
                    }
                    return Err(anyhow!("embedded resource not found: {}", src.display()));
                }
                sources.push((src, item.dest_name.clone()));
            }
        }

        Ok(sources)
    }

    fn required_space(sources: &[(PathBuf, PathBuf)]) -> Result<u64> {
        let mut total: u64 = 0;
        for (src, _) in sources {
            let meta = fs::metadata(src)
                .with_context(|| format!("reading metadata for {}", src.display()))?;
            total = total.saturating_add(meta.len());
        }
        Ok(total.saturating_mul(2))
    }
}

fn bsl_item_str() -> &'static str {
    "tools/code-index-mcp/target/release/bsl-indexer.exe"
}

/// Returns the path to the embedded workbench, installing it if necessary.
///
/// On failure the error is logged and `None` is returned so the app can fall
/// back to normal workbench detection.
pub fn embedded_workbench_path(app_handle: &AppHandle) -> Option<PathBuf> {
    let installer = EmbeddedInstaller::new();

    if installer.is_installed() {
        return Some(installer.dest_root().to_path_buf());
    }

    match installer.extract(app_handle) {
        Ok(path) => Some(path),
        Err(e) => {
            log::error!("failed to extract embedded workbench: {e:#}");
            None
        }
    }
}

#[cfg(windows)]
fn available_space(path: &Path) -> Result<u64> {
    use std::os::windows::ffi::OsStrExt;

    #[link(name = "kernel32")]
    extern "system" {
        fn GetDiskFreeSpaceExW(
            lpDirectoryName: *const u16,
            lpFreeBytesAvailableToCaller: *mut u64,
            lpTotalNumberOfBytes: *mut u64,
            lpTotalNumberOfFreeBytes: *mut u64,
        ) -> i32;
    }

    let wide: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();

    let mut available: u64 = 0;
    let rc = unsafe {
        GetDiskFreeSpaceExW(
            wide.as_ptr(),
            &mut available,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
        )
    };

    if rc == 0 {
        return Err(anyhow!(
            "failed to query available disk space for {}",
            path.display()
        ));
    }

    Ok(available)
}

#[cfg(not(windows))]
fn available_space(_path: &Path) -> Result<u64> {
    Ok(u64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_manifest_has_expected_items() {
        let manifest = ResourceManifest::bundled();
        assert_eq!(manifest.version, env!("CARGO_PKG_VERSION"));
        assert_eq!(manifest.items.len(), 5);
    }

    #[test]
    fn installer_paths_are_nonempty() {
        let installer = EmbeddedInstaller::new();
        assert!(!installer.dest_root().as_os_str().is_empty());
        assert!(!installer.sentinel_path.as_os_str().is_empty());
    }
}
