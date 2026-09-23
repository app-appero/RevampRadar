#[tauri::command]
fn open_external(url: String) -> Result<(), String> {
    if !(url.starts_with("https://") || url.starts_with("http://") || url.starts_with("mailto:")) {
        return Err("URL non consentito".into());
    }

    // Non "cmd /c start": cmd.exe reinterpreta "&" (comune nelle query string, es. "?a=1&b=2")
    // come separatore di comandi anche dentro le virgolette, spezzando l'URL. explorer.exe
    // apre l'URL con il browser di default senza fare parsing di shell.
    #[cfg(target_os = "windows")]
    let result = std::process::Command::new("explorer").arg(&url).spawn();

    #[cfg(target_os = "macos")]
    let result = std::process::Command::new("open").arg(&url).spawn();

    #[cfg(all(unix, not(target_os = "macos")))]
    let result = std::process::Command::new("xdg-open").arg(&url).spawn();

    result.map_err(|err| err.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_external])
        .run(tauri::generate_context!())
        .expect("error while running RevampRadar");
}
