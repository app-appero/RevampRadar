export async function openExternal(url: string): Promise<void> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_external", { url });
    return;
  } catch {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
