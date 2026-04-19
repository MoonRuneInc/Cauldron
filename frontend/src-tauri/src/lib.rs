#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let mut builder = tauri::Builder::default()
    .plugin(tauri_plugin_http::init())
    .plugin(tauri_plugin_websocket::init())
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    });

  #[cfg(feature = "updater")]
  {
    builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
  }

  builder
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
