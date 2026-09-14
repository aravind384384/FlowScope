
const state = {
  folder: null,
  sessions: [],
  selectedStem: null,
  search: "",
  when: "all",
  tag: null,
  favoritesOnly: false,
  sort: "date-desc",
  saveTimers: {},
};

const el = (id) => document.getElementById(id);

window.addEventListener("DOMContentLoaded", () => {
  const savedFolder = localStorage.getItem("flowscope.folder");
  if (savedFolder) {
    openFolder(savedFolder);
  }

  el("choose-folder-btn").addEventListener("click", chooseFolder);
  el("choose-folder-btn-2").addEventListener("click", chooseFolder);
  el("rescan-btn").addEventListener("click", () => state.folder && openFolder(state.folder));

  el("search-input").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    renderCards();
  });

  el("sort-select").addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderCards();
  });

  el("date-filters").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-chip");
    if (!btn) return;
    state.when = btn.dataset.when;
    [...el("date-filters").children].forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    renderCards();
  });

  el("favorites-toggle").addEventListener("click", () => {
    state.favoritesOnly = !state.favoritesOnly;
    el("favorites-toggle").classList.toggle("active", state.favoritesOnly);
    renderCards();
  });

  el("tag-filters").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-chip");
    if (!btn) return;
    const tag = btn.dataset.tag;
    state.tag = state.tag === tag ? null : tag;
    renderSidebarTags();
    renderCards();
  });

  wireWorkspaceEvents();

  if (window.flowscope.onFolderChanged) {
    window.flowscope.onFolderChanged(() => {
      if (state.folder) openFolder(state.folder, { keepSelection: true });
    });
  }
});

async function chooseFolder() {
  const folder = await window.flowscope.pickFolder();
  if (folder) openFolder(folder);
}

async function openFolder(folder, opts = {}) {
  state.folder = folder;
  localStorage.setItem("flowscope.folder", folder);
  el("folder-path").textContent = folder;
  el("folder-path").title = folder;
  el("search-input").disabled = false;
  el("sort-select").disabled = false;

  try {
    state.sessions = await window.flowscope.scanFolder(folder);
  } catch (exc) {
    el("cards").innerHTML = `<div class="empty-hint">Error scanning folder: ${escapeHtml(exc.message)}</div>`;
    return;
  }

  window.flowscope.watchFolder(folder);

  renderSidebarStats();
  renderSidebarTags();
  renderCards();

  if (!opts.keepSelection) {
    state.selectedStem = null;
    showWorkspaceEmpty();
  } else if (state.selectedStem) {
    const still = state.sessions.find((s) => s.stem === state.selectedStem);
    if (still) selectSession(state.selectedStem, { skipCardHighlightScroll: true });
    else showWorkspaceEmpty();
  }
}





function renderSidebarStats() {
  const sessions = state.sessions;
  el("stat-sessions").textContent = sessions.length;
  el("stat-guides").textContent = sessions.filter((s) => s.files.guideMd || s.files.guidePdf).length;
  el("stat-commands").textContent = sessions.reduce((sum, s) => sum + (s.commandCount || 0), 0);
}

function renderSidebarTags() {
  const tagCounts = new Map();
  for (const s of state.sessions) {
    for (const t of s.tags || []) {
      tagCounts.set(t, (tagCounts.get(t) || 0) + 1);
    }
  }

  const container = el("tag-filters");
  container.innerHTML = "";

  if (tagCounts.size === 0) {
    container.innerHTML = '<div class="empty-hint">No tags yet</div>';
    return;
  }

  const sortedTags = [...tagCounts.entries()].sort((a, b) => b[1] - a[1]);
  for (const [tag, count] of sortedTags) {
    const btn = document.createElement("button");
    btn.className = "filter-chip" + (state.tag === tag ? " active" : "");
    btn.dataset.tag = tag;
    btn.textContent = `${tag} (${count})`;
    container.appendChild(btn);
  }
}





function withinWhen(session, when) {
  if (when === "all") return true;
  const ts = session.startedAt ? Date.parse(session.startedAt) : session.mtimeMs;
  if (!ts) return when === "older";

  const now = Date.now();
  const oneDay = 86400000;
  const age = now - ts;

  if (when === "today") return age < oneDay && new Date(ts).getDate() === new Date(now).getDate();
  if (when === "week") return age < 7 * oneDay;
  if (when === "older") return age >= 7 * oneDay;
  return true;
}

function matchesSearch(session, q) {
  if (!q) return true;
  const haystack = [
    session.title,
    session.stem,
    session.sessionId,
    session.shell,
    ...(session.tags || []),
    ...(session.commands || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

function sortSessions(sessions, mode) {
  const copy = [...sessions];
  const tOf = (s) => (s.startedAt ? Date.parse(s.startedAt) : s.mtimeMs || 0);
  switch (mode) {
    case "date-asc":
      return copy.sort((a, b) => tOf(a) - tOf(b));
    case "duration-desc":
      return copy.sort((a, b) => (b.duration || 0) - (a.duration || 0));
    case "duration-asc":
      return copy.sort((a, b) => (a.duration || 0) - (b.duration || 0));
    case "commands-desc":
      return copy.sort((a, b) => (b.commandCount || 0) - (a.commandCount || 0));
    case "title-asc":
      return copy.sort((a, b) => (displayTitle(a) || "").localeCompare(displayTitle(b) || ""));
    case "date-desc":
    default:
      return copy.sort((a, b) => tOf(b) - tOf(a));
  }
}




function baseStem(stem) {
  const idx = stem.lastIndexOf("/");
  return idx === -1 ? stem : stem.slice(idx + 1);
}

function displayTitle(session) {
  return session.title || baseStem(session.stem);
}

function getFilteredSessions() {
  return sortSessions(
    state.sessions.filter(
      (s) =>
        withinWhen(s, state.when) &&
        matchesSearch(s, state.search) &&
        (!state.favoritesOnly || s.favorite) &&
        (!state.tag || (s.tags || []).includes(state.tag))
    ),
    state.sort
  );
}

function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return null;
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}m ${rem}s` : `${rem}s`;
}

function fmtDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderCards() {
  const list = getFilteredSessions();
  const cardsEl = el("cards");
  const emptyEl = el("empty-state");

  if (state.sessions.length === 0) {
    emptyEl.classList.remove("hidden");
    cardsEl.classList.add("hidden");
    cardsEl.innerHTML = "";
    return;
  }

  emptyEl.classList.add("hidden");
  cardsEl.classList.remove("hidden");

  if (list.length === 0) {
    cardsEl.innerHTML = '<div class="empty-hint">No sessions match the current filters.</div>';
    return;
  }

  cardsEl.innerHTML = "";
  for (const s of list) {
    const card = document.createElement("div");
    card.className = "session-card" + (s.stem === state.selectedStem ? " selected" : "");
    card.dataset.stem = s.stem;

    const dur = fmtDuration(s.duration);
    const date = fmtDate(s.startedAt);

    const badges = [];
    if (s.files.guideMd || s.files.guidePdf) badges.push('<span class="badge artifact-guide">Guide</span>');
    else badges.push('<span class="badge artifact-missing">No guide</span>');
    if (s.commandCount) badges.push(`<span class="badge">${s.commandCount} cmds</span>`);
    for (const t of (s.tags || []).slice(0, 3)) badges.push(`<span class="badge tag">${escapeHtml(t)}</span>`);

    card.innerHTML = `
      <div class="card-title-row">
        <div class="card-title">${escapeHtml(displayTitle(s))}</div>
        ${s.favorite ? '<div class="card-fav">★</div>' : ""}
      </div>
      <div class="card-meta">
        ${date ? `<span>${date}</span>` : ""}
        ${dur ? `<span>${dur}</span>` : ""}
        ${s.shell ? `<span>${escapeHtml(s.shell)}</span>` : ""}
      </div>
      <div class="card-badges">${badges.join("")}</div>
    `;
    card.addEventListener("click", () => selectSession(s.stem));
    cardsEl.appendChild(card);
  }
}





function showWorkspaceEmpty() {
  el("workspace-empty").classList.remove("hidden");
  el("workspace-content").classList.add("hidden");
}

async function selectSession(stem, opts = {}) {
  state.selectedStem = stem;
  [...el("cards").children].forEach((c) => c.classList.toggle("selected", c.dataset.stem === stem));

  const session = state.sessions.find((s) => s.stem === stem);
  if (!session) return showWorkspaceEmpty();

  el("workspace-empty").classList.add("hidden");
  el("workspace-content").classList.remove("hidden");

  el("ws-title-input").value = session.title || "";
  el("ws-title-input").placeholder = baseStem(session.stem);
  el("ws-favorite-btn").textContent = session.favorite ? "♥" : "♡";
  el("ws-favorite-btn").classList.toggle("active", session.favorite);
  el("ws-notes").value = session.notes || "";

  const metaParts = [];
  if (fmtDate(session.startedAt)) metaParts.push(`<span>${fmtDate(session.startedAt)}</span>`);
  if (fmtDuration(session.duration)) metaParts.push(`<span>${fmtDuration(session.duration)}</span>`);
  if (session.shell) metaParts.push(`<span>${escapeHtml(session.shell)}</span>`);
  metaParts.push(`<span>${session.commandCount} commands</span>`);
  el("ws-meta").innerHTML = metaParts.join("");

  renderTagPills(session);

  el("open-pdf-btn").disabled = !session.files.guidePdf;

  
  const overviewBody = el("overview-body");
  overviewBody.innerHTML = `
    <div class="overview-stat-row">
      <div class="overview-stat"><div class="num">${session.commandCount}</div><div class="label">Commands</div></div>
      <div class="overview-stat"><div class="num">${fmtDuration(session.duration) || "—"}</div><div class="label">Duration</div></div>
      <div class="overview-stat"><div class="num">${session.files.guideMd ? "Yes" : "No"}</div><div class="label">Guide generated</div></div>
    </div>
    ${
      session.commands.length
        ? `<div class="overview-commands">${session.commands.map((c) => `<div>${escapeHtml(c)}</div>`).join("")}</div>`
        : '<div class="artifact-empty">No blocks.json for this session — run the AI/heuristics pipeline to see commands here.</div>'
    }
  `;

  
  await Promise.all([
    loadMarkdownPanel(session, "transcript", session.files.transcript, "No transcript.md for this session."),
    loadMarkdownPanel(session, "guide", session.files.guideMd, "No guide.md for this session."),
    loadJsonPanel("session", session.files.session, "No session.json for this session."),
    loadJsonPanel("blocks", session.files.blocks, "No blocks.json for this session."),
  ]);

  if (!opts.skipCardHighlightScroll) {
    
  }
}

async function loadMarkdownPanel(session, key, filename, emptyMsg) {
  const panel = el(`panel-${key}`);
  if (!filename) {
    panel.innerHTML = `<pre class="artifact-empty">${emptyMsg}</pre>`;
    return;
  }
  try {
    const raw = await window.flowscope.readTextFile(state.folder, filename);
    panel.innerHTML = `<div class="md-body">${renderMarkdown(raw)}</div>`;
  } catch (exc) {
    panel.innerHTML = `<pre class="artifact-empty">Could not read ${escapeHtml(filename)}: ${escapeHtml(exc.message)}</pre>`;
  }
}

async function loadJsonPanel(key, filename, emptyMsg) {
  const panel = el(`panel-${key}`);
  if (!filename) {
    panel.innerHTML = `<pre class="artifact-empty">${emptyMsg}</pre>`;
    return;
  }
  try {
    const pretty = await window.flowscope.readJsonPretty(state.folder, filename);
    panel.innerHTML = `<pre class="raw-json">${escapeHtml(pretty)}</pre>`;
  } catch (exc) {
    panel.innerHTML = `<pre class="artifact-empty">Could not read ${escapeHtml(filename)}: ${escapeHtml(exc.message)}</pre>`;
  }
}

function renderTagPills(session) {
  const container = el("ws-tags");
  container.innerHTML = "";
  for (const tag of session.tags || []) {
    const pill = document.createElement("div");
    pill.className = "tag-pill";
    pill.innerHTML = `<span>${escapeHtml(tag)}</span><span class="remove" data-tag="${escapeHtml(tag)}">×</span>`;
    pill.querySelector(".remove").addEventListener("click", () => removeTag(session.stem, tag));
    container.appendChild(pill);
  }
}

function wireWorkspaceEvents() {
  el("ws-tabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".ws-tab");
    if (!tab) return;
    [...el("ws-tabs").children].forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".ws-panel").forEach((p) => p.classList.remove("active"));
    el(`panel-${tab.dataset.tab}`).classList.add("active");
  });

  el("ws-title-input").addEventListener("input", (e) => {
    debouncedSave("title", { title: e.target.value.trim() || null });
  });

  el("ws-notes").addEventListener("input", (e) => {
    debouncedSave("notes", { notes: e.target.value });
  });

  el("ws-favorite-btn").addEventListener("click", async () => {
    const session = currentSession();
    if (!session) return;
    session.favorite = !session.favorite;
    el("ws-favorite-btn").textContent = session.favorite ? "♥" : "♡";
    el("ws-favorite-btn").classList.toggle("active", session.favorite);
    await window.flowscope.updateSessionMeta(state.folder, session.stem, { favorite: session.favorite });
    renderCards();
  });

  el("ws-tag-input").addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    const value = e.target.value.trim();
    if (!value) return;
    const session = currentSession();
    if (!session) return;
    if (!(session.tags || []).includes(value)) {
      session.tags = [...(session.tags || []), value];
      await window.flowscope.updateSessionMeta(state.folder, session.stem, { tags: session.tags });
      renderTagPills(session);
      renderSidebarTags();
      renderCards();
    }
    e.target.value = "";
  });

  el("open-pdf-btn").addEventListener("click", () => {
    const session = currentSession();
    if (session && session.files.guidePdf) {
      window.flowscope.openFileExternal(state.folder, session.files.guidePdf);
    }
  });

  el("reveal-btn").addEventListener("click", () => {
    const session = currentSession();
    if (!session) return;
    const anyFile = Object.values(session.files).find(Boolean);
    if (anyFile) window.flowscope.revealInFolder(state.folder, anyFile);
  });

  el("delete-btn").addEventListener("click", async () => {
    const session = currentSession();
    if (!session) return;
    const ok = confirm(
      `Delete all FlowScope files for "${displayTitle(session)}"?\n\nThis removes the raw session, blocks, transcript, guide, and PDF from disk. This cannot be undone.`
    );
    if (!ok) return;
    await window.flowscope.deleteSession(state.folder, session.stem, session.files);
    state.sessions = state.sessions.filter((s) => s.stem !== session.stem);
    state.selectedStem = null;
    renderSidebarStats();
    renderSidebarTags();
    renderCards();
    showWorkspaceEmpty();
  });
}

function currentSession() {
  return state.sessions.find((s) => s.stem === state.selectedStem) || null;
}

async function removeTag(stem, tag) {
  const session = state.sessions.find((s) => s.stem === stem);
  if (!session) return;
  session.tags = (session.tags || []).filter((t) => t !== tag);
  await window.flowscope.updateSessionMeta(state.folder, stem, { tags: session.tags });
  renderTagPills(session);
  renderSidebarTags();
  renderCards();
}

function debouncedSave(key, patch) {
  const session = currentSession();
  if (!session) return;
  Object.assign(session, patch);
  clearTimeout(state.saveTimers[key]);
  state.saveTimers[key] = setTimeout(async () => {
    await window.flowscope.updateSessionMeta(state.folder, session.stem, patch);
    renderCards();
  }, 400);
}










function renderMarkdown(md) {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let inCode = false;
  let codeBuf = [];
  let listOpen = false;

  const closeList = () => {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine;
    const fenceMatch = line.trim().match(/^`{3,}/);

    if (fenceMatch) {
      if (!inCode) {
        inCode = true;
        codeBuf = [];
      } else {
        inCode = false;
        out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
      }
      continue;
    }

    if (inCode) {
      codeBuf.push(line);
      continue;
    }

    const trimmed = line.trim();

    if (!trimmed) {
      closeList();
      continue;
    }

    if (/^(---|\*\*\*|___)$/.test(trimmed)) {
      closeList();
      out.push("<hr/>");
      continue;
    }

    let m;
    if ((m = trimmed.match(/^###\s+(.*)$/))) {
      closeList();
      out.push(`<h3>${inline(m[1])}</h3>`);
    } else if ((m = trimmed.match(/^##\s+(.*)$/))) {
      closeList();
      out.push(`<h2>${inline(m[1])}</h2>`);
    } else if ((m = trimmed.match(/^#\s+(.*)$/))) {
      closeList();
      out.push(`<h1>${inline(m[1])}</h1>`);
    } else if ((m = trimmed.match(/^[-*]\s+(.*)$/))) {
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${inline(m[1])}</li>`);
    } else if ((m = trimmed.match(/^>\s?(.*)$/))) {
      closeList();
      out.push(`<blockquote>${inline(m[1])}</blockquote>`);
    } else {
      closeList();
      out.push(`<p>${inline(trimmed)}</p>`);
    }
  }
  closeList();
  if (inCode && codeBuf.length) {
    out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
  }

  return out.join("\n");
}

function inline(text) {
  let t = escapeHtml(text);
  t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g, "<em>$1</em>");
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  return t;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}