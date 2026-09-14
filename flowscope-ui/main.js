







const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const path = require("path");
const fs = require("fs/promises");
const fssync = require("fs");

const LIBRARY_FILE = ".flowscope-library.json";

let mainWindow;
let watcher = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "FlowScope",
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});





async function readLibrary(folder) {
  const libPath = path.join(folder, LIBRARY_FILE);
  try {
    const raw = await fs.readFile(libPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && parsed.sessions) return parsed;
  } catch (_) {
    
  }
  return { sessions: {} };
}

async function writeLibrary(folder, library) {
  const libPath = path.join(folder, LIBRARY_FILE);
  await fs.writeFile(libPath, JSON.stringify(library, null, 2), "utf-8");
}
















const SUFFIXES = [
  { key: "blocks", suffix: ".blocks.json" },
  { key: "transcript", suffix: ".transcript.md" },
  { key: "guideMd", suffix: ".guide.md" },
  { key: "guidePdf", suffix: ".guide.pdf" },
];

function stemFor(filename) {
  for (const { suffix } of SUFFIXES) {
    if (filename.endsWith(suffix)) {
      return filename.slice(0, -suffix.length);
    }
  }
  if (filename.endsWith(".json")) {
    return filename.slice(0, -".json".length);
  }
  return null;
}





function isBareGuideFile(filename) {
  const base = filename.split("/").pop();
  return base === "guide.md" || base === "guide.pdf";
}

function dirOf(relPath) {
  const idx = relPath.lastIndexOf("/");
  return idx === -1 ? "" : relPath.slice(0, idx);
}

async function safeReadJson(filePath) {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}







async function walkFiles(dir, baseDir) {
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch (exc) {
    throw new Error(`Could not read folder: ${dir} (${exc.message})`);
  }

  const results = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue; 
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const nested = await walkFiles(fullPath, baseDir);
      results.push(...nested);
    } else if (entry.isFile()) {
      results.push(path.relative(baseDir, fullPath).split(path.sep).join("/"));
    }
  }
  return results;
}

async function scanFolder(folder) {
  let files;
  try {
    files = await walkFiles(folder, folder);
  } catch (exc) {
    throw new Error(`Could not read folder: ${folder} (${exc.message})`);
  }

  
  const groups = new Map();

  const bareGuideFiles = []; 

  for (const filename of files) {
    
    
    if (filename === LIBRARY_FILE || filename.endsWith("/" + LIBRARY_FILE)) continue;

    if (isBareGuideFile(filename)) {
      bareGuideFiles.push(filename);
      continue;
    }

    const stem = stemFor(filename);
    if (!stem) continue;

    if (!groups.has(stem)) {
      groups.set(stem, { stem, files: {} });
    }
    const group = groups.get(stem);

    const match = SUFFIXES.find((s) => filename.endsWith(s.suffix));
    if (match) {
      group.files[match.key] = filename;
    } else if (filename.endsWith(".json")) {
      
      
      if (!group.files.session) group.files.session = filename;
    }
  }

  
  
  
  
  for (const filename of bareGuideFiles) {
    const key = filename.endsWith(".pdf") ? "guidePdf" : "guideMd";
    const dir = dirOf(filename);
    const matches = [...groups.values()].filter((g) => dirOf(g.stem) === dir);

    if (matches.length > 0) {
      for (const g of matches) {
        if (!g.files[key]) g.files[key] = filename;
      }
    } else {
      const standaloneStem = dir ? `${dir}/guide` : "guide";
      if (!groups.has(standaloneStem)) {
        groups.set(standaloneStem, { stem: standaloneStem, files: {} });
      }
      groups.get(standaloneStem).files[key] = filename;
    }
  }

  const library = await readLibrary(folder);

  const sessions = [];

  for (const [stem, group] of groups) {
    const sessionFile = group.files.session;
    const blocksFile = group.files.blocks;

    let sessionMeta = null;
    let blocksMeta = null;

    if (sessionFile) {
      sessionMeta = await safeReadJson(path.join(folder, sessionFile));
    }
    if (blocksFile) {
      blocksMeta = await safeReadJson(path.join(folder, blocksFile));
    }

    const commands = [];
    if (blocksMeta && Array.isArray(blocksMeta.blocks)) {
      for (const b of blocksMeta.blocks) {
        if (b && typeof b.command === "string" && b.command.trim()) {
          commands.push(b.command.trim());
        }
      }
    }

    const startedAt =
      (sessionMeta && sessionMeta.started_at) ||
      (blocksMeta && blocksMeta.started_at) ||
      null;
    const endedAt =
      (sessionMeta && sessionMeta.ended_at) ||
      (blocksMeta && blocksMeta.ended_at) ||
      null;
    const duration =
      (sessionMeta && sessionMeta.duration) ||
      (blocksMeta && blocksMeta.duration) ||
      null;
    const shell =
      (sessionMeta && sessionMeta.shell) ||
      (blocksMeta && blocksMeta.shell) ||
      null;
    const sessionId =
      (sessionMeta && sessionMeta.session_id) ||
      (blocksMeta && blocksMeta.session_id) ||
      stem;

    const libEntry = library.sessions[stem] || {};

    let statOnDisk = null;
    const anyFile = sessionFile || blocksFile || group.files.transcript || group.files.guideMd || group.files.guidePdf;
    if (anyFile) {
      try {
        statOnDisk = await fs.stat(path.join(folder, anyFile));
      } catch (_) {
        statOnDisk = null;
      }
    }

    sessions.push({
      stem,
      sessionId,
      startedAt,
      endedAt,
      duration,
      shell,
      commandCount: commands.length,
      commands,
      files: group.files,
      title: libEntry.title || null,
      tags: libEntry.tags || [],
      notes: libEntry.notes || "",
      favorite: !!libEntry.favorite,
      mtimeMs: statOnDisk ? statOnDisk.mtimeMs : null,
    });
  }

  
  sessions.sort((a, b) => {
    const ta = a.startedAt ? Date.parse(a.startedAt) : a.mtimeMs || 0;
    const tb = b.startedAt ? Date.parse(b.startedAt) : b.mtimeMs || 0;
    return tb - ta;
  });

  return sessions;
}





ipcMain.handle("pick-folder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    title: "Choose your FlowScope sessions folder",
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.handle("scan-folder", async (_evt, folder) => {
  return scanFolder(folder);
});

ipcMain.handle("read-text-file", async (_evt, folder, filename) => {
  if (!filename) return null;
  return fs.readFile(path.join(folder, filename), "utf-8");
});

ipcMain.handle("read-json-pretty", async (_evt, folder, filename) => {
  if (!filename) return null;
  const raw = await fs.readFile(path.join(folder, filename), "utf-8");
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch (_) {
    return raw;
  }
});

ipcMain.handle("open-file-external", async (_evt, folder, filename) => {
  if (!filename) return;
  const err = await shell.openPath(path.join(folder, filename));
  if (err) throw new Error(err);
});

ipcMain.handle("reveal-in-folder", async (_evt, folder, filename) => {
  if (!filename) return;
  shell.showItemInFolder(path.join(folder, filename));
});

ipcMain.handle("update-session-meta", async (_evt, folder, stem, patch) => {
  const library = await readLibrary(folder);
  const existing = library.sessions[stem] || {};
  library.sessions[stem] = { ...existing, ...patch };
  await writeLibrary(folder, library);
  return library.sessions[stem];
});

ipcMain.handle("delete-session", async (_evt, folder, stem, files) => {
  for (const filename of Object.values(files || {})) {
    if (!filename) continue;
    try {
      await fs.unlink(path.join(folder, filename));
    } catch (_) {
      
    }
  }
  const library = await readLibrary(folder);
  delete library.sessions[stem];
  await writeLibrary(folder, library);
});



ipcMain.handle("watch-folder", async (_evt, folder) => {
  if (watcher) {
    watcher.close();
    watcher = null;
  }
  if (!folder || !fssync.existsSync(folder)) return;

  try {
    
    
    
    watcher = fssync.watch(folder, { persistent: false, recursive: true }, () => {
      if (mainWindow) mainWindow.webContents.send("folder-changed");
    });
  } catch (_) {
    
    watcher = fssync.watch(folder, { persistent: false }, () => {
      if (mainWindow) mainWindow.webContents.send("folder-changed");
    });
  }
});