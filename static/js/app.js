// static/js/app.js
// Orchestrator — manages stage transitions and shared session state.
// Imports from all other modules; nothing imports from here.

import { initUpload, initAddPapers } from "./upload.js";
import { initCards, renderCards, loadCards } from "./cards.js";
import { initChat, resetChat, loadChatHistory, triggerBrief } from "./chat.js";
import { initSessions } from "./sessions.js";
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

const $navMeta = document.getElementById("nav-meta");
const $navQuestion = document.getElementById("nav-question");
const $navActions = document.getElementById("nav-actions");
const $btnBackToCards = document.getElementById("btn-back-to-cards");
const $btnNewSession = document.getElementById("btn-new-session");
const $btnEditQuestion   = document.getElementById("btn-edit-question");
const $editQuestionInput = document.getElementById("edit-question-input");
const $btnSaveQuestion   = document.getElementById("btn-save-question");
const $staleBanner       = document.getElementById("question-stale-banner");

// ── Stage transitions ────────────────────────────────────────
function goToStage(n) {
  $stageUpload.classList.toggle("stage--hidden", n !== 1);
  $stageCards.classList.toggle("stage--hidden", n !== 2);
  $stageChat.classList.toggle("stage--hidden", n !== 3);

  $navMeta.hidden = n === 1;
  $navActions.hidden = n === 1;
  $btnEditQuestion.hidden = n === 1;

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

// ── Session resume ────────────────────────────────────────────
function handleSessionResume(sessionId, researchQuestion, paperCount) {
  setSession(sessionId, researchQuestion, paperCount);
  goToStage(2);
  loadCards(sessionId);
}

// ── Upload success ────────────────────────────────────────────
function handleUploadSuccess(sessionId, researchQuestion, papers) {
  setSession(sessionId, researchQuestion, papers.length);
  renderCards(papers);
  goToStage(2);
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

// ── Nav actions ───────────────────────────────────────────────
$btnBackToCards.addEventListener("click", () => goToStage(2));

$btnNewSession.addEventListener("click", () => {
  localStorage.removeItem(SESSION_STORAGE_KEY);
  state.sessionId = null;
  state.researchQuestion = "";
  state.paperCount = 0;
  $navQuestion.textContent = "";
  chatLoadedForSession = null;
  $staleBanner.hidden = true;
  goToStage(1);
  initSessions({ onResume: handleSessionResume });
});

// ── Research question edit ────────────────────────────────────
$btnEditQuestion.addEventListener("click", () => {
  $navQuestion.hidden = true;
  $btnEditQuestion.hidden = true;
  $editQuestionInput.value = state.researchQuestion;
  $editQuestionInput.hidden = false;
  $btnSaveQuestion.hidden = false;
  $editQuestionInput.focus();
});

async function saveQuestion() {
  const newQ = $editQuestionInput.value.trim();
  if (!newQ || newQ === state.researchQuestion) { cancelEdit(); return; }
  try {
    await api.updateSession(state.sessionId, newQ);
    state.researchQuestion = newQ;
    $navQuestion.textContent = newQ;
    saveSession();
    $staleBanner.hidden = false;
    cancelEdit();
  } catch (err) {
    // stay in edit mode on error; user can retry
    console.error("Failed to update question:", err);
  }
}

function cancelEdit() {
  $editQuestionInput.hidden = true;
  $btnSaveQuestion.hidden = true;
  $navQuestion.hidden = false;
  $btnEditQuestion.hidden = false;
}

$btnSaveQuestion.addEventListener("click", saveQuestion);
$editQuestionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); saveQuestion(); }
  if (e.key === "Escape") cancelEdit();
});

// ── Module initialization ─────────────────────────────────────
initUpload({ onSuccess: handleUploadSuccess });

initCards({
  onGoToChat: goToChat,
  onGenerateBrief: handleGenerateBrief,
});

initChat({ getState });

initSessions({ onResume: handleSessionResume });
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
