// static/js/cards.js
import { api } from "./api.js";

// Column order matches the manual spreadsheet layout from BUILD.md
const CSV_HEADERS = [
  "Title",
  "Authors",
  "Venue",
  "Year",
  "Task",
  "Modality",
  "Methodology",
  "Results",
  "Datasets",
  "Pretraining",
  "Code Available",
  "Code URL",
  "Key Limitations",
  "Synthesis Note",
  "Relevance Score",
  "Tier",
  "Filename",
];

let currentCards = [];
let sortKey = "relevance_score";

export function initCards({ onGoToChat, onGenerateBrief }) {
  const $sortSelect = document.getElementById("sort-select");
  const $btnExport = document.getElementById("btn-export-csv");
  const $btnBrief = document.getElementById("btn-generate-brief");
  const $btnChat = document.getElementById("btn-go-chat");

  $sortSelect.addEventListener("change", () => {
    sortKey = $sortSelect.value;
    renderCards(currentCards);
  });

  $btnExport.addEventListener("click", handleExportCsv);
  $btnBrief.addEventListener("click", onGenerateBrief);
  $btnChat.addEventListener("click", onGoToChat);
}

export async function loadCards(sessionId) {
  const $status = document.getElementById("cards-status");
  $status.hidden = false;
  $status.textContent = "Loading papers…";

  try {
    const cards = await api.getCards(sessionId);
    renderCards(cards);
    $status.hidden = true;
    return cards;
  } catch (err) {
    $status.textContent = "Failed to load cards — try uploading again.";
    console.error("Load cards error:", err);
    return [];
  }
}

export function renderCards(papers) {
  currentCards = papers;

  const $count = document.getElementById("cards-count");
  const $tbody = document.getElementById("cards-tbody");

  $count.textContent = `${papers.length} paper${papers.length !== 1 ? "s" : ""}`;

  const sorted = sortedCards(papers);
  const fragment = document.createDocumentFragment();

  for (const card of sorted) {
    fragment.appendChild(buildRow(card));
  }

  $tbody.innerHTML = "";
  $tbody.appendChild(fragment);
}

function sortedCards(cards) {
  return [...cards].sort((a, b) => {
    switch (sortKey) {
      case "relevance_score":
        return (b.relevance_score ?? 0) - (a.relevance_score ?? 0);
      case "tier":
        return (a.tier ?? 9) - (b.tier ?? 9);
      case "year":
        return (b.year ?? 0) - (a.year ?? 0);
      case "venue":
        return (a.venue ?? "").localeCompare(b.venue ?? "");
      default:
        return 0;
    }
  });
}

function buildRow(card) {
  const tier = card.tier ?? 3;
  const $tr = document.createElement("tr");
  $tr.className = `paper-card paper-card--tier-${tier}${card.error ? " paper-card--error" : ""}`;

  $tr.appendChild(buildTitleTd(card));
  $tr.appendChild(buildTextTd(card.venue));
  $tr.appendChild(buildTextTd(card.year));
  $tr.appendChild(buildTextTd(card.task));
  $tr.appendChild(buildTextTd(card.methodology));
  $tr.appendChild(buildTextTd(card.results));
  $tr.appendChild(buildTextTd((card.datasets ?? []).join(", ") || null));
  $tr.appendChild(buildScoreTd(card));
  $tr.appendChild(buildTextTd(card.synthesis_note));

  return $tr;
}

function buildTextTd(text) {
  const $td = document.createElement("td");
  $td.textContent = text ?? "—";
  return $td;
}

function buildTitleTd(card) {
  const $td = document.createElement("td");
  $td.className = "paper-card__title";

  const $title = document.createElement("span");
  $title.textContent = card.title ?? card.filename;
  $td.appendChild($title);

  if (card.code_available && card.code_url) {
    const $br = document.createElement("br");
    const $link = document.createElement("a");
    $link.href = card.code_url;
    $link.textContent = "Code ↗";
    $link.className = "paper-card__code-link";
    $link.target = "_blank";
    $link.rel = "noopener noreferrer";
    $link.setAttribute("aria-label", `Code for ${card.title ?? card.filename}`);
    $td.appendChild($br);
    $td.appendChild($link);
  }

  return $td;
}


function buildScoreTd(card) {
  const tier = card.tier ?? 3;
  const $td = document.createElement("td");
  $td.className = "paper-card__score";

  const $score = document.createElement("div");
  $score.textContent =
    card.relevance_score != null ? `${card.relevance_score}/5` : "—";
  $td.appendChild($score);

  const $badge = document.createElement("span");
  $badge.className = `tier-badge tier-badge--${tier}`;
  $badge.textContent = `T${tier}`;
  $td.appendChild($badge);

  return $td;
}

function handleExportCsv() {
  if (currentCards.length === 0) return;

  const rows = [CSV_HEADERS];

  for (const card of currentCards) {
    rows.push([
      card.title ?? "",
      (card.authors ?? []).join("; "),
      card.venue ?? "",
      card.year ?? "",
      card.task ?? "",
      card.modality ?? "",
      card.methodology ?? "",
      card.results ?? "",
      (card.datasets ?? []).join("; "),
      card.pretraining ?? "",
      card.code_available ? "Yes" : "No",
      card.code_url ?? "",
      card.key_limitations ?? "",
      card.synthesis_note ?? "",
      card.relevance_score ?? "",
      card.tier ?? "",
      card.filename,
    ]);
  }

  const csv = rows
    .map((row) =>
      row
        .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
        .join(","),
    )
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  // Temporary anchor for programmatic download — not an interactive element
  const $a = document.createElement("a");
  $a.href = url;
  $a.download = "primer-papers.csv";
  document.body.appendChild($a);
  $a.click();
  document.body.removeChild($a);
  URL.revokeObjectURL(url);
}
