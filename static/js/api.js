// static/js/api.js
// All fetch calls go here. Never write raw fetch() anywhere else.

const API_BASE = "/api";

// API Key management — lives in sessionStorage for the browser tab only
export const apiKey = {
  get: () => sessionStorage.getItem("primer_llm_key") || "",
  set: (key) => sessionStorage.setItem("primer_llm_key", key),
  clear: () => sessionStorage.removeItem("primer_llm_key"),
  isSet: () => {
    const k = sessionStorage.getItem("primer_llm_key");
    return !!k && (k.startsWith("sk-ant-") || k.startsWith("sk-"));
  },
};

export class APIError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "APIError";
    this.status = status;
  }
}

async function handleResponse(response) {
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new APIError(error.detail || "Request failed", response.status);
  }
  return response.json();
}

export const api = {
  uploadPapers: (formData) =>
    fetch(`${API_BASE}/upload`, {
      method: "POST",
      headers: {
        "X-LLM-Key": apiKey.get(),
      },
      body: formData,
    }).then(handleResponse),

  getCards: (sessionId) =>
    fetch(`${API_BASE}/cards/${encodeURIComponent(sessionId)}`).then(
      handleResponse,
    ),

  sendChat: (request) =>
    fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-LLM-Key": apiKey.get(),
      },
      body: JSON.stringify(request),
    }).then(handleResponse),

  /**
   * Stream a chat response via SSE.
   * @param {object} request  - Same shape as sendChat request body.
   * @param {function} onChunk - Called with each text string as it arrives.
   * @returns {Promise<{sources: string[], chunks_retrieved: number}>}
   */
  async streamChat(request, onChunk) {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-LLM-Key": apiKey.get(),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: response.statusText }));
      throw new APIError(error.detail || "Request failed", response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let sources = [];
    let chunksRetrieved = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process all complete SSE lines in the buffer
      const lines = buffer.split("\n");
      buffer = lines.pop(); // hold the last (possibly incomplete) line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6);

        let event;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }

        if (event.type === "chunk") {
          onChunk(event.text);
        } else if (event.type === "done") {
          sources = event.sources ?? [];
          chunksRetrieved = event.chunks_retrieved ?? 0;
        } else if (event.type === "error") {
          throw new APIError(event.message || "Stream error", 500);
        }
      }
    }

    return { sources, chunksRetrieved };
  },

  getSessions: () =>
    fetch(`${API_BASE}/sessions`).then(handleResponse),

  getSession: (sessionId) =>
    fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`).then(handleResponse),

  updateSession: (sessionId, researchQuestion) =>
    fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ research_question: researchQuestion }),
    }).then(handleResponse),
};
