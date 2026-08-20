const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, { method = "GET", body, token, isFormData = false } = {}) {
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!isFormData) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export async function uploadDocument(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/upload", { method: "POST", body: formData, token, isFormData: true });
}

export async function getUploadHistory(token) {
  return request("/upload/history", { token });
}

export async function getCurrentDocuments(token) {
  return request("/upload/documents", { token });
}

export async function deleteDocument(filename, token) {
  return request(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE", token });
}

export async function queryDocuments(question, token, topK = 5) {
  return request("/query", {
    method: "POST",
    body: { question, top_k: topK },
    token,
  });
}

/**
 * Streams an answer via Server-Sent Events.
 * callbacks: { onMeta({confidence, sources}), onToken(text), onDone(), onError(message) }
 */
export async function queryDocumentsStream(question, token, callbacks, topK = 5) {
  const res = await fetch(`${API_BASE_URL}/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question, top_k: topK }),
  });

  if (!res.ok || !res.body) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop(); // last (possibly incomplete) chunk stays in buffer

    for (const raw of events) {
      const line = raw.trim();
      if (!line.startsWith("data:")) continue;
      const event = JSON.parse(line.slice(5).trim());

      if (event.type === "meta") callbacks.onMeta?.(event);
      else if (event.type === "token") callbacks.onToken?.(event.text);
      else if (event.type === "error") callbacks.onError?.(event.message);
      else if (event.type === "done") callbacks.onDone?.();
    }
  }
}
