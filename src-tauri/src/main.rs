// Prevents an additional console window on Windows release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Tauri shell for Lore Forge.
//!
//! Boot sequence:
//!   1. Spawn the PyInstaller sidecar via `tauri-plugin-shell`'s
//!      `Sidecar` API. The binary is registered as
//!      `binaries/sidecar` in `tauri.conf.json::externalBin` and must
//!      exist at build time with the host target-triple suffix
//!      (e.g. `sidecar-aarch64-apple-darwin`).
//!   2. Parse the sidecar's first stdout line `SIDECAR_READY http://.../`
//!      to discover the loopback port the backend bound to.
//!   3. Inject `window.__LORE_FORGE_API__ = "<url>"` into the webview
//!      so `frontend/lib/api.ts` routes every request at the sidecar.
//!      The frontend guards against the missing value during the brief
//!      pre-ready window.
//!   4. On window close → SIGTERM the sidecar so orphaned Python
//!      processes don't linger after the app quits.

use std::sync::Mutex;

use tauri::{Emitter, Manager};
use tauri_plugin_shell::process::{CommandEvent, CommandChild};
use tauri_plugin_shell::ShellExt;

/// Holds the sidecar child so `on_window_event` can SIGTERM it at quit.
struct SidecarHandle(Mutex<Option<CommandChild>>);

/// Holds the sidecar URL once discovered. Exposed to the frontend via
/// the `sidecar_url` command — belt-and-suspenders alongside the
/// window.eval injection, so a refreshed webview can still recover it.
struct SidecarUrl(Mutex<Option<String>>);

#[tauri::command]
fn sidecar_url(state: tauri::State<SidecarUrl>) -> Option<String> {
    state.0.lock().ok().and_then(|g| g.clone())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarHandle(Mutex::new(None)))
        .manage(SidecarUrl(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![sidecar_url])
        .setup(|app| {
            let handle = app.handle().clone();

            // Spawn the sidecar. `sidecar("sidecar")` resolves to the
            // platform-specific binary baked into the bundle by the
            // Tauri packager.
            let (mut rx, child) = app
                .shell()
                .sidecar("sidecar")
                .expect("sidecar binary not found — did you run build_sidecar.sh?")
                .spawn()
                .expect("failed to spawn sidecar");

            // Stash the child so the quit handler can terminate it.
            handle
                .state::<SidecarHandle>()
                .0
                .lock()
                .unwrap()
                .replace(child);

            // Drain stdout/stderr on a Tokio task and watch for
            // SIDECAR_READY. Uvicorn's own logs flow through the same
            // channel afterwards; we just forward them to the Rust log.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                            let text = String::from_utf8_lossy(&line);
                            log::info!("sidecar: {}", text.trim_end());
                            if let Some(url) = text.strip_prefix("SIDECAR_READY ") {
                                let url = url.trim().to_string();
                                handle
                                    .state::<SidecarUrl>()
                                    .0
                                    .lock()
                                    .unwrap()
                                    .replace(url.clone());
                                // Inject the URL into the frontend as
                                // soon as possible. The main window may
                                // not have finished navigating yet; the
                                // frontend falls back to polling the
                                // `sidecar_url` command if so.
                                if let Some(window) = handle.get_webview_window("main") {
                                    let js = format!(
                                        "window.__LORE_FORGE_API__ = {};",
                                        serde_json::to_string(&url).unwrap()
                                    );
                                    let _ = window.eval(&js);
                                    let _ = window.emit("sidecar-ready", url);
                                }
                            }
                        }
                        CommandEvent::Terminated(payload) => {
                            log::warn!("sidecar exited: {:?}", payload);
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Best-effort SIGTERM. The sidecar also exits when its
                // stdin hits EOF, so this is usually redundant — but
                // redundancy is fine here.
                if let Some(child) = window
                    .state::<SidecarHandle>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
