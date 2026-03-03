// static/js/app.js
// Orchestrator — manages stage transitions and shared session state.
// Imports from all other modules; nothing imports from here.

import { initUpload, initAddPapers } from "./upload.js";
import { initCards, renderCards, loadCards } from "./cards.js";
import { initChat, resetChat, loadChatHistory, triggerBrief } from "./chat.js";
import { initSidebar, refreshSidebar, setActiveSidebarSession } from "./sidebar.js";
import { api } from "./api.js";

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

const $navActions = document.getElementById("nav-actions");
const $btnBackToCards = document.getElementById("btn-back-to-cards");
const $staleBanner = document.getElementById("question-stale-banner");

// ── Stage transitions ────────────────────────────────────────
function goToStage(n) {
  $stageUpload.classList.toggle("stage--hidden", n !== 1);
  $stageCards.classList.toggle("stage--hidden", n !== 2);
  $stageChat.classList.toggle("stage--hidden", n !== 3);

  $navActions.hidden = n !== 3;

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
  chatLoadedForSession = null; // reset so history is re-loaded
  saveSession();
  setActiveSidebarSession(sessionId);
}

// ── Session resume ────────────────────────────────────────────
function handleSessionResume(sessionId, researchQuestion, paperCount) {
  setSession(sessionId, researchQuestion, paperCount);
  goToStage(2);
  loadCards(sessionId);
}

// ── Upload success ────────────────────────────────────────────
async function handleUploadSuccess(sessionId, researchQuestion, papers) {
  setSession(sessionId, researchQuestion, papers.length);
  renderCards(papers);
  goToStage(2);
  await refreshSidebar({ onResumeSession: handleSessionResume, onRenameSession: handleRename });
}

// ── Add papers success ────────────────────────────────────────
function handleAddPapersSuccess(result) {
  setSession(state.sessionId, state.researchQuestion, result.total_papers);
  loadCards(state.sessionId);
}

// ── Generate Brief (from cards toolbar) ──────────────────────
function handleGenerateBrief() {
  goToChat();
  // Small delay lets the DOM paint before the API call starts
  setTimeout(() => triggerBrief(getState), 50);
}

// ── Rename callback (from sidebar) ───────────────────────────
function handleRename(sessionId, newQuestion) {
  if (sessionId === state.sessionId) {
    state.researchQuestion = newQuestion;
    saveSession();
    $staleBanner.hidden = false;
  }
}

// ── New session ───────────────────────────────────────────────
function handleNewSession() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
  state.sessionId = null;
  state.researchQuestion = "";
  state.paperCount = 0;
  chatLoadedForSession = null;
  $staleBanner.hidden = true;
  setActiveSidebarSession(null);
  goToStage(1);
}

// ── Nav actions ───────────────────────────────────────────────
$btnBackToCards.addEventListener("click", () => goToStage(2));

// ── Module initialization ─────────────────────────────────────
initSidebar({
  onNewSession: handleNewSession,
  onResumeSession: handleSessionResume,
  onRenameSession: handleRename,
});

initUpload({ onSuccess: handleUploadSuccess });

initCards({
  onGoToChat: goToChat,
  onGenerateBrief: handleGenerateBrief,
});

initChat({ getState });

initAddPapers({ getState, onAddSuccess: handleAddPapersSuccess });

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
