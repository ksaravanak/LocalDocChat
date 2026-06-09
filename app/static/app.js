const TOKEN_KEY = "ldc_token";
const HISTORY_KEY = "ldc_history";

const loginScreen = document.getElementById("login-screen");
const appEl = document.getElementById("app");
const passwordInput = document.getElementById("password-input");
const loginBtn = document.getElementById("login-btn");
const loginError = document.getElementById("login-error");
const statusBadge = document.getElementById("status-badge");
const uploadZone = document.getElementById("upload-zone");
const fileInput = document.getElementById("file-input");
const uploadProgress = document.getElementById("upload-progress");
const docList = document.getElementById("doc-list");
const emptyDocs = document.getElementById("empty-docs");
const refreshDocs = document.getElementById("refresh-docs");
const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");

let chatHistory = loadHistory();

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory() {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(chatHistory.slice(-20)));
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || d).join(", ")
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderDocuments(docs) {
  docList.innerHTML = "";
  emptyDocs.classList.toggle("hidden", docs.length > 0);

  for (const doc of docs) {
    const li = document.createElement("li");
    li.className = "doc-item";
    li.innerHTML = `
      <div class="doc-meta">
        <span class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</span>
        <span class="doc-info">${doc.chunk_count} chunks · ${formatBytes(doc.size_bytes)}</span>
      </div>
      <button type="button" class="icon-btn" data-id="${doc.id}" title="Delete">×</button>
    `;
    li.querySelector("button").addEventListener("click", () => deleteDoc(doc.id));
    docList.appendChild(li);
  }
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function appendMessage(role, content, sources = []) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  let sourcesHtml = "";
  if (sources.length) {
    const names = [...new Set(sources.map((s) => s.filename))];
    sourcesHtml = `<div class="sources">Sources: ${names.map(escapeHtml).join(", ")}</div>`;
  }

  wrap.innerHTML = `<div class="bubble">${escapeHtml(content)}${sourcesHtml}</div>`;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadDocuments() {
  const data = await api("/api/documents");
  renderDocuments(data.documents);
}

async function uploadFiles(files) {
  if (!files.length) return;

  uploadProgress.classList.remove("hidden");
  uploadProgress.textContent = `Uploading ${files.length} file(s)...`;

  for (const file of files) {
    const form = new FormData();
    form.append("file", file);

    try {
      uploadProgress.textContent = `Processing ${file.name} (local AI indexing)...`;
      await api("/api/documents/upload", { method: "POST", body: form });
    } catch (err) {
      uploadProgress.textContent = `Failed: ${file.name} — ${err.message}`;
      setTimeout(() => uploadProgress.classList.add("hidden"), 5000);
      return;
    }
  }

  uploadProgress.textContent = "Upload complete.";
  setTimeout(() => uploadProgress.classList.add("hidden"), 1500);
  await loadDocuments();
}

async function deleteDoc(id) {
  if (!confirm("Delete this document?")) return;
  await api(`/api/documents/${id}`, { method: "DELETE" });
  await loadDocuments();
}

async function sendMessage(text) {
  appendMessage("user", text);
  chatHistory.push({ role: "user", content: text });
  saveHistory();

  sendBtn.disabled = true;
  chatInput.disabled = true;
  sendBtn.textContent = "Thinking...";

  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: chatHistory.slice(0, -1) }),
    });

    appendMessage("assistant", data.answer, data.sources || []);
    chatHistory.push({ role: "assistant", content: data.answer });
    saveHistory();
  } catch (err) {
    appendMessage("assistant", `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    chatInput.disabled = false;
    sendBtn.textContent = "Send";
    chatInput.focus();
  }
}

async function checkHealth() {
  const data = await fetch("/api/health").then((r) => r.json());
  const ollama = data.ollama || {};

  if (!ollama.reachable) {
    statusBadge.textContent = "Ollama offline";
    statusBadge.classList.remove("ok");
    statusBadge.classList.add("warn");
  } else if (!ollama.chat_ready || !ollama.embed_ready) {
    statusBadge.textContent = "Model missing";
    statusBadge.classList.remove("ok");
    statusBadge.classList.add("warn");
  } else {
    statusBadge.textContent = data.chat_model || "Local · Ollama";
    statusBadge.classList.add("ok");
    statusBadge.classList.remove("warn");
  }

  return data;
}

async function tryLogin(password) {
  const data = await api("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  setToken(data.token);
  return data;
}

async function bootstrap() {
  const health = await checkHealth();

  if (health.auth_required) {
    loginScreen.classList.remove("hidden");
    appEl.classList.add("hidden");

    loginBtn.addEventListener("click", async () => {
      loginError.classList.add("hidden");
      try {
        await tryLogin(passwordInput.value);
        loginScreen.classList.add("hidden");
        appEl.classList.remove("hidden");
        await loadDocuments();
      } catch (err) {
        loginError.textContent = err.message;
        loginError.classList.remove("hidden");
      }
    });

    passwordInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") loginBtn.click();
    });

    const existing = getToken();
    if (existing) {
      try {
        await loadDocuments();
        loginScreen.classList.add("hidden");
        appEl.classList.remove("hidden");
      } catch {
        localStorage.removeItem(TOKEN_KEY);
      }
    }
  } else {
    setToken("public");
    loginScreen.classList.add("hidden");
    appEl.classList.remove("hidden");
    await loadDocuments();
  }
}

uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.classList.add("dragover");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("dragover");
  uploadFiles([...e.dataTransfer.files]);
});

fileInput.addEventListener("change", () => {
  uploadFiles([...fileInput.files]);
  fileInput.value = "";
});

refreshDocs.addEventListener("click", loadDocuments);

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  sendMessage(text);
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

bootstrap();
