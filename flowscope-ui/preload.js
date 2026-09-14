const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("flowscope", {
  pickFolder: () => ipcRenderer.invoke("pick-folder"),
  scanFolder: (folder) => ipcRenderer.invoke("scan-folder", folder),
  readTextFile: (folder, filename) => ipcRenderer.invoke("read-text-file", folder, filename),
  readJsonPretty: (folder, filename) => ipcRenderer.invoke("read-json-pretty", folder, filename),
  openFileExternal: (folder, filename) => ipcRenderer.invoke("open-file-external", folder, filename),
  revealInFolder: (folder, filename) => ipcRenderer.invoke("reveal-in-folder", folder, filename),
  updateSessionMeta: (folder, stem, patch) => ipcRenderer.invoke("update-session-meta", folder, stem, patch),
  deleteSession: (folder, stem, files) => ipcRenderer.invoke("delete-session", folder, stem, files),
  watchFolder: (folder) => ipcRenderer.invoke("watch-folder", folder),
  onFolderChanged: (cb) => ipcRenderer.on("folder-changed", cb),
});
