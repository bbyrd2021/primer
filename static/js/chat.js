// static/js/chat.js
import { api, APIError } from "./api.js";

const HISTORY_STORAGE_PREFIX = "primer_chat_";

// Module state
let chatHistory = [];
let isLoading = false;

export function initChat({ getState }) {
  const $form = document.getElementById("chat-form");
  const $input = document.getElementById("chat-input");
  const $btnBrief = document.getElementById("btn-brief-shortcut");

  // Auto-resize textarea on input
  $input.addEventListener("input", () => {
    $input.style.height = "auto";
    $input.style.height = `${Math.min($input.scrollHeight, 160)}px`;
  });

  // Submit on Enter, newline on Shift+Enter
  $input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $form.requestSubmit();
    }
  });

  $form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = $input.value.trim();
    if (!message || isLoading) return;
    $input.value = "";
    $input.style.height = "auto";
    await handleSend({ message, generateBrief: false, getState });
  });

  $btnBrief.addEventListener("click", () => {
    if (isLoading) return;
    handleSend({ message: "", generateBrief: true, getState });
  });
}

export function resetChat(_sessionId) {
  chatHistory = [];

  const $messages = document.getElementById("chat-messages");
  $messages.innerHTML = "";

  const $empty = document.createElement("div");
  $empty.id = "chat-empty";
  $empty.className = "chat-empty";
  const $p = document.createElement("p");
  $p.className = "chat-empty__text";
  $p.textContent =
    "Ask a question about your papers, or generate a full research brief.";
  $empty.appendChild($p);
  $messages.appendChild($empty);
}

export function loadChatHistory(sessionId) {
  const saved = localStorage.getItem(`${HISTORY_STORAGE_PREFIX}${sessionId}`);
  if (!saved) return;

  try {
    const history = JSON.parse(saved);
    const $messages = document.getElementById("chat-messages");

    for (const msg of history) {
      if (msg.role === "user") {
        appendUserMessage($messages, msg.content);
      } else if (msg.role === "assistant") {
        appendAssistantMessage($messages, msg.content, msg.sources ?? []);
      }
    }

    chatHistory = history;
  } catch {
    localStorage.removeItem(`${HISTORY_STORAGE_PREFIX}${sessionId}`);
  }
}

export function triggerBrief(getState) {
  if (isLoading) return;
  handleSend({ message: "", generateBrief: true, getState });
}

// ── Private ────────────────────────────────────────────────────

async function handleSend({ message, generateBrief, getState }) {
  const { sessionId, researchQuestion, paperCount } = getState();
  if (!sessionId) return;

  const $messages = document.getElementById("chat-messages");
  const $btnSend = document.getElementById("btn-send");
  const $btnBrief = document.getElementById("btn-brief-shortcut");

  isLoading = true;
  $btnSend.disabled = true;
  $btnBrief.disabled = true;

  const displayMessage = generateBrief ? "Generate my research brief" : message;
  appendUserMessage($messages, displayMessage);

  // Append a loading bubble that will transition into the streamed response
  const { $msg: $streamMsg, $body: $streamBody } = appendLoadingMessage($messages);

  // Build history for API — only user/assistant turns
  const apiHistory = chatHistory
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({ role: m.role, content: m.content }));

  let accumulated = "";
  let streamingStarted = false;

  try {
    const result = await api.streamChat(
      {
        session_id: sessionId,
        message: generateBrief ? researchQuestion : message,
        research_question: researchQuestion,
        paper_count: paperCount,
        history: apiHistory,
        generate_brief: generateBrief,
      },
      (chunk) => {
        if (!streamingStarted) {
          // First chunk: drop the "Thinking" state and start showing text
          streamingStarted = true;
          $streamMsg.classList.remove("chat-message--loading");
          $streamBody.textContent = "";
        }
        accumulated += chunk;
        $streamBody.textContent = accumulated;
        scrollToBottom($messages);
      },
    );

    // Stream finished: do the full markdown + citation render
    $streamBody.innerHTML = renderContent(accumulated);
    if (result.sources.length > 0) {
      const $src = document.createElement("div");
      $src.className = "chat-message__sources";
      $src.textContent = `Sources: ${result.sources.join(", ")}`;
      $streamMsg.appendChild($src);
    }
    scrollToBottom($messages);

    // Persist to history
    chatHistory.push(
      { role: "user", content: displayMessage },
      { role: "assistant", content: accumulated, sources: result.sources },
    );
    saveHistory(sessionId);
  } catch (err) {
    $streamMsg.classList.remove("chat-message--loading");
    const msg =
      err instanceof APIError ? err.message : "Something went wrong — please try again.";
    $streamBody.innerHTML = renderContent(msg);
    console.error("Chat error:", err);
  } finally {
    isLoading = false;
    $btnSend.disabled = false;
    $btnBrief.disabled = false;
  }
}

function appendUserMessage($messages, content) {
  hideEmpty($messages);

  const $msg = document.createElement("div");
  $msg.className = "chat-message chat-message--user";

  const $role = document.createElement("div");
  $role.className = "chat-message__role";
  $role.textContent = "You";

  const $body = document.createElement("div");
  $body.className = "chat-message__body";
  $body.textContent = content;

  $msg.appendChild($role);
  $msg.appendChild($body);
  $messages.appendChild($msg);
  scrollToBottom($messages);
}

function appendAssistantMessage($messages, content, sources) {
  hideEmpty($messages);

  const $msg = document.createElement("div");
  $msg.className = "chat-message chat-message--assistant";

  const $role = document.createElement("div");
  $role.className = "chat-message__role";
  $role.textContent = "Primer";

  const $body = document.createElement("div");
  $body.className = "chat-message__body";
  // renderContent escapes user data before setting innerHTML
  $body.innerHTML = renderContent(content);

  $msg.appendChild($role);
  $msg.appendChild($body);

  if (sources.length > 0) {
    const $src = document.createElement("div");
    $src.className = "chat-message__sources";
    $src.textContent = `Sources: ${sources.join(", ")}`;
    $msg.appendChild($src);
  }

  $messages.appendChild($msg);
  scrollToBottom($messages);
}

function appendLoadingMessage($messages) {
  const $msg = document.createElement("div");
  $msg.className = "chat-message chat-message--assistant chat-message--loading";

  const $role = document.createElement("div");
  $role.className = "chat-message__role";
  $role.textContent = "Primer";

  const $body = document.createElement("div");
  $body.className = "chat-message__body";
  $body.textContent = "Thinking";

  $msg.appendChild($role);
  $msg.appendChild($body);
  $messages.appendChild($msg);
  scrollToBottom($messages);
  return { $msg, $body };
}

function hideEmpty($messages) {
  const $empty = $messages.querySelector("#chat-empty");
  if ($empty) $empty.hidden = true;
}

function scrollToBottom($el) {
  $el.scrollTop = $el.scrollHeight;
}

function saveHistory(sessionId) {
  // Keep last 40 entries (20 turns) to avoid localStorage bloat
  const trimmed = chatHistory.slice(-40);
  localStorage.setItem(
    `${HISTORY_STORAGE_PREFIX}${sessionId}`,
    JSON.stringify(trimmed),
  );
}

// ── Content rendering ──────────────────────────────────────────
// Escapes HTML first, then applies safe inline transforms.
// Citation pattern: [filename.pdf, p.X] → chip span

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function applyInline(escapedText) {
  return escapedText
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Citation chips — square brackets survived escapeHtml intact
    .replace(
      /\[([^\]]+?),\s*p\.(\d+)\]/g,
      '<span class="citation-chip">[$1, p.$2]</span>',
    );
}

function renderContent(text) {
  const lines = text.split("\n");
  const parts = [];
  let inList = false;

  for (const line of lines) {
    const escaped = escapeHtml(line);

    if (line.startsWith("## ")) {
      if (inList) { parts.push("</ul>"); inList = false; }
      parts.push(`<h3>${applyInline(escapeHtml(line.slice(3)))}</h3>`);
    } else if (line.startsWith("### ")) {
      if (inList) { parts.push("</ul>"); inList = false; }
      parts.push(`<h4>${applyInline(escapeHtml(line.slice(4)))}</h4>`);
    } else if (/^[-*] /.test(line)) {
      if (!inList) { parts.push("<ul>"); inList = true; }
      parts.push(`<li>${applyInline(escapeHtml(line.slice(2)))}</li>`);
    } else if (/^\d+\. /.test(line)) {
      if (!inList) { parts.push("<ul>"); inList = true; }
      parts.push(`<li>${applyInline(escapeHtml(line.replace(/^\d+\. /, "")))}</li>`);
    } else if (line.trim() === "") {
      if (inList) { parts.push("</ul>"); inList = false; }
      parts.push("<br>");
    } else {
      if (inList) { parts.push("</ul>"); inList = false; }
      parts.push(`<p>${applyInline(escaped)}</p>`);
    }
  }

  if (inList) parts.push("</ul>");
  return parts.join("");
}
