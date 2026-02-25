// static/js/app.js
// Orchestrator — manages stage transitions and shared session state.
// Imports from all other modules; nothing imports from here.

import { initUpload } from "./upload.js";
import { initCards, renderCards, loadCards } from "./cards.js";
import { initChat, resetChat, loadChatHistory, triggerBrief } from "./chat.js";

const SESSION_STORAGE_KEY = "primer_session";

// ── Shared state ─────────────────────────────────────────────
const state = {
  sessionId: null,
  researchQuestion: "",
  paperCount: 0,
};

function getState() {
  return { ...state };
}

// ── DOM refs ─────────────────────────────────────────────────
const $stageUpload = document.getElementById("stage-upload");
const $stageCards = document.getElementById("stage-cards");
const $stageChat = document.getElementById("stage-chat");

const $navMeta = document.getElementById("nav-meta");
const $navQuestion = document.getElementById("nav-question");
const $navActions = document.getElementById("nav-actions");
const $btnBackToCards = document.getElementById("btn-back-to-cards");
const $btnNewSession = document.getElementById("btn-new-session");

// ── Stage transitions ────────────────────────────────────────
function goToStage(n) {
  $stageUpload.classList.toggle("stage--hidden", n !== 1);
  $stageCards.classList.toggle("stage--hidden", n !== 2);
  $stageChat.classList.toggle("stage--hidden", n !== 3);

  $navMeta.hidden = n === 1;
  $navActions.hidden = n === 1;

  // Scroll to top of new stage
  window.scrollTo(0, 0);
}

// ── Chat session tracking ─────────────────────────────────────
// Avoid re-loading history on every nav to stage 3.
let chatLoadedForSession = null;

function goToChat() {
  goToStage(3);
  if (chatLoadedForSession !== state.sessionId) {
    resetChat(state.sessionId);
    loadChatHistory(state.sessionId);
    chatLoadedForSession = state.sessionId;
  }
}

// ── Session state helpers ─────────────────────────────────────
function saveSession() {
  localStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      sessionId: state.sessionId,
      researchQuestion: state.researchQuestion,
      paperCount: state.paperCount,
    }),
  );
}

function setSession(sessionId, researchQuestion, paperCount) {
  state.sessionId = sessionId;
  state.researchQuestion = researchQuestion;
  state.paperCount = paperCount;
  $navQuestion.textContent = researchQuestion;
  chatLoadedForSession = null; // reset so history is re-loaded
  saveSession();
}

// ── Upload success ────────────────────────────────────────────
function handleUploadSuccess(sessionId, researchQuestion, papers) {
  setSession(sessionId, researchQuestion, papers.length);
  renderCards(papers);
  goToStage(2);
}

// ── Generate Brief (from cards toolbar) ──────────────────────
function handleGenerateBrief() {
  goToChat();
  // Small delay lets the DOM paint before the API call starts
  setTimeout(() => triggerBrief(getState), 50);
}

// ── Nav actions ───────────────────────────────────────────────
$btnBackToCards.addEventListener("click", () => goToStage(2));

$btnNewSession.addEventListener("click", () => {
  localStorage.removeItem(SESSION_STORAGE_KEY);
  state.sessionId = null;
  state.researchQuestion = "";
  state.paperCount = 0;
  $navQuestion.textContent = "";
  chatLoadedForSession = null;
  goToStage(1);
});

// ── Module initialization ─────────────────────────────────────
initUpload({ onSuccess: handleUploadSuccess });

initCards({
  onGoToChat: goToChat,
  onGenerateBrief: handleGenerateBrief,
});

initChat({ getState });

// ── Session restore ───────────────────────────────────────────
const savedSession = localStorage.getItem(SESSION_STORAGE_KEY);
if (savedSession) {
  try {
    const { sessionId, researchQuestion, paperCount } = JSON.parse(savedSession);
    if (sessionId && researchQuestion) {
      setSession(sessionId, researchQuestion, paperCount ?? 0);
      goToStage(2);
      loadCards(sessionId);
    }
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }
}
