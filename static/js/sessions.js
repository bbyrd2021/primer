// static/js/sessions.js
import { api } from "./api.js";

export async function initSessions({ onResume }) {
  const $panel   = document.getElementById("sessions-panel");
  const $list    = document.getElementById("sessions-list");
  const $divider = document.getElementById("sessions-divider");
  if (!$panel) return;

  try {
    const sessions = await api.getSessions();
    if (sessions.length === 0) { $panel.hidden = true; return; }

    $list.innerHTML = "";
    for (const s of sessions) {
      const li = document.createElement("li");
      li.innerHTML = `
        <button class="session-item__btn" type="button">
          <span class="session-item__question">${truncate(s.research_question, 80)}</span>
          <span class="session-item__meta">
            ${s.paper_count} paper${s.paper_count !== 1 ? "s" : ""}
            · ${relativeDate(s.created_at)}
            ${s.updated_at ? '<span class="session-item__stale-badge">scores from old question</span>' : ""}
          </span>
        </button>`;
      li.querySelector("button").addEventListener("click", () =>
        onResume(s.session_id, s.research_question, s.paper_count)
      );
      $list.appendChild(li);
    }
    $panel.hidden = false;
    $divider.hidden = false;
  } catch {
    $panel.hidden = true; // silently degrade — never block new session flow
  }
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + "…" : str;
}

function relativeDate(iso) {
  const days = Math.floor((Date.now() - new Date(iso)) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}
