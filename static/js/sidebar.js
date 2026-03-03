// static/js/sidebar.js
// Manages the persistent session sidebar: toggle, session list, rename.

import { api } from "./api.js";

const STORAGE_KEY = "primer_sidebar_open";

let currentSessionId = null;

export function initSidebar({ onNewSession, onResumeSession, onRenameSession, onDeleteSession }) {
  const $toggle = document.getElementById("btn-sidebar-toggle");
  const $newBtn = document.getElementById("btn-new-session");
  const $backdrop = document.querySelector(".sidebar-backdrop");

  // Restore persisted open/closed state (default: open)
  if (localStorage.getItem(STORAGE_KEY) !== "false") {
    document.body.classList.add("sidebar-open");
    $toggle.setAttribute("aria-expanded", "true");
  }

  $toggle.addEventListener("click", () => toggleSidebar($toggle));
  $backdrop?.addEventListener("click", () => toggleSidebar($toggle));

  $newBtn.addEventListener("click", onNewSession);

  loadSessions({ onResumeSession, onRenameSession, onDeleteSession });
}

function toggleSidebar($toggle) {
  const isOpen = document.body.classList.toggle("sidebar-open");
  $toggle.setAttribute("aria-expanded", String(isOpen));
  localStorage.setItem(STORAGE_KEY, String(isOpen));
}

export async function refreshSidebar({ onResumeSession, onRenameSession, onDeleteSession }) {
  await loadSessions({ onResumeSession, onRenameSession, onDeleteSession });
}

export function setActiveSidebarSession(sessionId) {
  currentSessionId = sessionId;
  document.querySelectorAll(".sidebar-item").forEach(($item) => {
    $item.classList.toggle(
      "sidebar-item--active",
      $item.dataset.sessionId === sessionId
    );
  });
}

async function loadSessions({ onResumeSession, onRenameSession, onDeleteSession }) {
  const $list = document.getElementById("sidebar-sessions-list");
  if (!$list) return;

  try {
    const sessions = await api.getSessions();
    $list.innerHTML = "";
    const fragment = document.createDocumentFragment();
    for (const s of sessions) {
      fragment.appendChild(buildItem(s, { onResumeSession, onRenameSession, onDeleteSession }));
    }
    $list.appendChild(fragment);
  } catch {
    // Silently degrade — never block the app
  }
}

function buildItem(session, { onResumeSession, onRenameSession, onDeleteSession }) {
  const $li = document.createElement("li");
  $li.className = "sidebar-item";
  $li.dataset.sessionId = session.session_id;
  if (session.session_id === currentSessionId) {
    $li.classList.add("sidebar-item--active");
  }

  const $body = document.createElement("button");
  $body.type = "button";
  $body.className = "sidebar-item__body";
  $body.addEventListener("click", () =>
    onResumeSession(session.session_id, session.research_question, session.paper_count)
  );

  const $q = document.createElement("span");
  $q.className = "sidebar-item__question";
  $q.textContent = truncate(session.research_question, 60);

  const $meta = document.createElement("span");
  $meta.className = "sidebar-item__meta";
  $meta.textContent = `${session.paper_count} paper${session.paper_count !== 1 ? "s" : ""} · ${relativeDate(session.created_at)}`;

  $body.appendChild($q);
  $body.appendChild($meta);

  const $rename = document.createElement("button");
  $rename.type = "button";
  $rename.className = "sidebar-item__rename";
  $rename.setAttribute("aria-label", "Rename session");
  $rename.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  $rename.addEventListener("click", (e) => {
    e.stopPropagation();
    startRename($li, $q, session, onRenameSession);
  });

  const $delete = document.createElement("button");
  $delete.type = "button";
  $delete.className = "sidebar-item__delete";
  $delete.setAttribute("aria-label", "Delete session");
  $delete.textContent = "×";
  $delete.addEventListener("click", (e) => {
    e.stopPropagation();
    if (onDeleteSession) onDeleteSession(session.session_id, $li);
  });

  const $actions = document.createElement("div");
  $actions.className = "sidebar-item__actions";
  $actions.appendChild($delete);
  $actions.appendChild($rename);

  $li.appendChild($body);
  $li.appendChild($actions);
  return $li;
}

function startRename($li, $q, session, onRenameSession) {
  // Prevent double rename inputs
  if ($li.querySelector(".sidebar-item__rename-input")) return;

  const $input = document.createElement("input");
  $input.type = "text";
  $input.className = "sidebar-item__rename-input";
  $input.value = session.research_question;
  $input.setAttribute("aria-label", "Edit research question");

  $li.appendChild($input);
  $input.focus();
  $input.select();

  async function commit() {
    const newQ = $input.value.trim();
    $input.remove();
    if (!newQ || newQ === session.research_question) return;
    try {
      await api.updateSession(session.session_id, newQ);
      session.research_question = newQ;
      $q.textContent = truncate(newQ, 60);
      onRenameSession(session.session_id, newQ);
    } catch {
      // Silently revert — no partial state left
    }
  }

  $input.addEventListener("blur", commit);
  $input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); $input.blur(); }
    if (e.key === "Escape") { $input.value = session.research_question; $input.blur(); }
  });
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + "…" : str;
}

function relativeDate(iso) {
  const days = Math.floor((Date.now() - new Date(iso)) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}
