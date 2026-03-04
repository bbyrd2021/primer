// static/js/upload.js
import { api, APIError, apiKey } from "./api.js";

export function initAddPapers({ getState, onAddSuccess }) {
  const $wrap   = document.getElementById("add-papers-form-wrap");
  const $form   = document.getElementById("add-papers-form");
  const $input  = document.getElementById("add-papers-input");
  const $status = document.getElementById("add-papers-status");
  const $btn    = document.getElementById("btn-add-papers-submit");
  const $toggle = document.getElementById("btn-add-papers");
  if (!$form) return;

  let files = [];

  $toggle.addEventListener("click", () => {
    $wrap.hidden = !$wrap.hidden;
  });

  $input.addEventListener("change", () => {
    const pdfs = Array.from($input.files).filter(f => f.name.toLowerCase().endsWith(".pdf"));
    // dedupe by name+size
    files = [...files, ...pdfs.filter(f => !files.some(x => x.name === f.name && x.size === f.size))];
    $input.value = "";
    $status.hidden = false;
    $status.textContent = `${files.length} file(s) ready`;
  });

  $form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!files.length) return;
    const { sessionId, researchQuestion } = getState();
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("research_question", researchQuestion);
    files.forEach(f => formData.append("files", f));
    $btn.disabled = true;
    $status.hidden = false;
    $status.textContent = `Uploading ${files.length} paper(s)…`;
    try {
      const result = await api.uploadPapers(formData);
      $status.textContent = "Done — cards updated.";
      files = [];
      $wrap.hidden = true;
      onAddSuccess(result);
    } catch (err) {
      $status.textContent = err.message || "Upload failed.";
    } finally {
      $btn.disabled = false;
    }
  });
}

// Module-level file list — maintained separately from the FileList
// because FileList is immutable (can't remove individual files).
let selectedFiles = [];

export function resetUpload() {
  selectedFiles = [];
  const $fileList = document.getElementById("file-list");
  const $dropPrompt = document.getElementById("drop-prompt");
  const $status = document.getElementById("upload-status");
  const $question = document.getElementById("research-question");
  const $btnUpload = document.getElementById("btn-upload");
  if ($fileList) { $fileList.innerHTML = ""; $fileList.hidden = true; }
  if ($dropPrompt) $dropPrompt.hidden = false;
  if ($status) { $status.hidden = true; $status.textContent = ""; }
  if ($question) $question.value = "";
  if ($btnUpload) $btnUpload.disabled = false;
}

export function initUpload({ onSuccess }) {
  const $form = document.getElementById("upload-form");
  const $dropZone = document.getElementById("drop-zone");
  const $fileInput = document.getElementById("pdf-input");
  const $fileList = document.getElementById("file-list");
  const $dropPrompt = document.getElementById("drop-prompt");
  const $status = document.getElementById("upload-status");
  const $btnUpload = document.getElementById("btn-upload");

  // ── Drag-and-drop ──────────────────────────────────────────
  $dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    $dropZone.classList.add("drop-zone--over");
  });

  $dropZone.addEventListener("dragleave", (e) => {
    // Only remove class when leaving the drop zone itself
    if (!$dropZone.contains(e.relatedTarget)) {
      $dropZone.classList.remove("drop-zone--over");
    }
  });

  $dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    $dropZone.classList.remove("drop-zone--over");
    addFiles(Array.from(e.dataTransfer.files));
  });

  // ── File input ─────────────────────────────────────────────
  $fileInput.addEventListener("change", () => {
    addFiles(Array.from($fileInput.files));
    // Reset input so the same file can be re-selected if removed
    $fileInput.value = "";
  });

  // ── Form submit ────────────────────────────────────────────
  $form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleSubmit({ $status, $btnUpload, $fileList, $dropPrompt, onSuccess });
  });

  // ── Helpers (closed over DOM refs) ────────────────────────
  function addFiles(files) {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    for (const file of pdfs) {
      const isDuplicate = selectedFiles.some(
        (f) => f.name === file.name && f.size === file.size,
      );
      if (!isDuplicate) {
        selectedFiles.push(file);
      }
    }
    renderFileList($fileList, $dropPrompt);
  }
}

function renderFileList($fileList, $dropPrompt) {
  if (selectedFiles.length === 0) {
    $fileList.hidden = true;
    $dropPrompt.hidden = false;
    return;
  }

  $fileList.hidden = false;
  $dropPrompt.hidden = true;

  // Rebuild list — use DocumentFragment for batch DOM insert
  const fragment = document.createDocumentFragment();

  selectedFiles.forEach((file, index) => {
    const $item = document.createElement("li");
    $item.className = "drop-zone__file-item";

    const $name = document.createElement("span");
    $name.className = "drop-zone__file-name";
    $name.textContent = file.name;

    const $remove = document.createElement("button");
    $remove.type = "button";
    $remove.className = "drop-zone__file-remove";
    $remove.textContent = "×";
    $remove.setAttribute("aria-label", `Remove ${file.name}`);
    $remove.addEventListener("click", (e) => {
      e.stopPropagation(); // prevent click from reaching the file input overlay
      selectedFiles.splice(index, 1);
      renderFileList(
        document.getElementById("file-list"),
        document.getElementById("drop-prompt"),
      );
    });

    $item.appendChild($name);
    $item.appendChild($remove);
    fragment.appendChild($item);
  });

  $fileList.innerHTML = "";
  $fileList.appendChild(fragment);
}

// Replaces the file list with per-file progress rows the moment upload starts.
function renderUploadProgress($fileList, $dropPrompt, files) {
  $dropPrompt.hidden = true;
  $fileList.hidden = false;
  $fileList.innerHTML = "";

  const fragment = document.createDocumentFragment();
  for (const file of files) {
    const $item = document.createElement("li");
    $item.className = "upload-progress-item";
    $item.dataset.filename = file.name;

    const $name = document.createElement("span");
    $name.className = "upload-progress-item__name";
    $name.textContent = file.name;

    const $bar = document.createElement("div");
    $bar.className = "upload-progress-bar";

    $item.appendChild($name);
    $item.appendChild($bar);
    fragment.appendChild($item);
  }

  $fileList.appendChild(fragment);
}

// After the response arrives, marks each row success or error.
function resolveUploadRows($fileList, files, papers) {
  for (const file of files) {
    const $item = $fileList.querySelector(
      `[data-filename="${CSS.escape(file.name)}"]`,
    );
    if (!$item) continue;

    const paper = papers.find((p) => p.filename === file.name);
    const isError = !paper || paper.error;

    $item.classList.add(
      isError ? "upload-progress-item--error" : "upload-progress-item--success",
    );

    const $bar = $item.querySelector(".upload-progress-bar");
    if ($bar) {
      const $result = document.createElement("span");
      $result.className = "upload-progress-item__result";
      $result.textContent = isError ? "✗ extraction failed" : "✓ indexed";
      $bar.replaceWith($result);
    }
  }
}

// Marks all pending rows as failed (network error / non-2xx response).
function failAllRows($fileList) {
  $fileList.querySelectorAll(".upload-progress-item").forEach(($item) => {
    if (
      $item.classList.contains("upload-progress-item--success") ||
      $item.classList.contains("upload-progress-item--error")
    )
      return;

    $item.classList.add("upload-progress-item--error");
    const $bar = $item.querySelector(".upload-progress-bar");
    if ($bar) {
      const $result = document.createElement("span");
      $result.className = "upload-progress-item__result";
      $result.textContent = "✗ upload failed";
      $bar.replaceWith($result);
    }
  });
}

// XHR wrapper that fires onProgress(pct 0–100) and resolves with parsed JSON.
function uploadWithProgress(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.setRequestHeader("X-LLM-Key", apiKey.get());

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new APIError("Invalid response", xhr.status));
        }
      } else {
        let message = "Request failed";
        try {
          const data = JSON.parse(xhr.responseText);
          message = data.detail || message;
        } catch {
          // ignore parse errors
        }
        reject(new APIError(message, xhr.status));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new APIError("Network error", 0));
    });

    xhr.send(formData);
  });
}

async function handleSubmit({ $status, $btnUpload, $fileList, $dropPrompt, onSuccess }) {
  const question = document
    .getElementById("research-question")
    .value.trim();

  if (!question) {
    showStatus($status, "Please enter a research question.", "error");
    return;
  }
  if (selectedFiles.length === 0) {
    showStatus($status, "Please select at least one PDF.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("research_question", question);
  for (const file of selectedFiles) {
    formData.append("files", file);
  }

  $btnUpload.disabled = true;
  const filesToUpload = [...selectedFiles];

  // Swap file list to progress rows before the request fires
  renderUploadProgress($fileList, $dropPrompt, filesToUpload);

  const count = filesToUpload.length;
  showStatus(
    $status,
    `Uploading ${count} paper${count !== 1 ? "s" : ""} — this may take a moment…`,
  );

  try {
    const result = await uploadWithProgress(formData, (pct) => {
      $fileList.querySelectorAll(".upload-progress-bar").forEach(($bar) => {
        if (pct >= 100) {
          // Bytes uploaded — switch to indeterminate shimmer while server extracts
          $bar.classList.add("upload-progress-bar--indeterminate");
          $bar.style.removeProperty("--pct");
        } else {
          $bar.style.setProperty("--pct", `${pct}%`);
        }
      });
    });

    resolveUploadRows($fileList, filesToUpload, result.papers);
    showStatus(
      $status,
      `Done — ${result.total_papers} papers indexed.`,
      "success",
    );
    selectedFiles = [];
    // Brief pause so users can see the resolved states before stage transition
    await new Promise((r) => setTimeout(r, 600));
    onSuccess(result.session_id, question, result.papers);
  } catch (err) {
    failAllRows($fileList);
    const msg =
      err instanceof APIError
        ? err.message
        : "Upload failed — please try again.";
    showStatus($status, msg, "error");
    console.error("Upload error:", err);
  } finally {
    $btnUpload.disabled = false;
  }
}

function showStatus($el, message, type = "") {
  $el.hidden = false;
  $el.textContent = message;
  $el.className =
    "upload-status" + (type ? ` upload-status--${type}` : "");
}
