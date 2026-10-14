/* Núcleo do painel: API, navegação, painel inicial e configurações. */
"use strict";

const API = {
  async request(method, url, body) {
    const options = { method, headers: {} };
    if (method !== "GET") {
      options.headers["X-Requested-With"] = "AgenteDocumental";
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body || {});
    }
    let response;
    try {
      response = await fetch(url, options);
    } catch (e) {
      throw new Error("Não foi possível comunicar com o servidor. Verifique se o sistema está em execução.");
    }
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && !url.startsWith("/api/auth/")) Auth.expired(data.detail);
    if (response.status === 403 && /Troque sua senha/.test(data.detail || "")) Auth.showPassword(true);
    if (!response.ok) throw new Error(data.detail || `Erro ${response.status}`);
    return data;
  },
  get(url) { return this.request("GET", url); },
  post(url, body) { return this.request("POST", url, body); },
  put(url, body) { return this.request("PUT", url, body); },
  del(url) { return this.request("DELETE", url); },
};

const $ = (sel) => document.querySelector(sel);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), isError ? 7000 : 3500);
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatSize(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

const STATUS_CLASS = {
  COM_TEXTO: "ok", COM_OCR: "ok", ESCANEADO: "warn", SEM_TEXTO: "warn",
  CORROMPIDO: "err", NAO_SUPORTADO: "", REMOVIDO: "",
};

function statusBadge(code, label) {
  return `<span class="badge ${STATUS_CLASS[code] ?? ""}">${esc(label || code)}</span>`;
}

/* ---------- abertura de documentos ---------- */
function fileUrl(id, page) {
  return `/api/documents/${id}/file${page ? `#page=${page}` : ""}`;
}

async function openInWindows(id) {
  try {
    await API.post(`/api/documents/${id}/open`);
    toast("Documento aberto no programa padrão do Windows.");
  } catch (e) { toast(e.message, true); }
}

/* ---------- downloads ---------- */
const EXPORT_FORMATS = ["pdf", "docx", "xlsx", "csv", "json"];

function exportButtons(baseUrl, formats = EXPORT_FORMATS) {
  const sep = baseUrl.includes("?") ? "&" : "?";
  return formats.map((f) =>
    `<button class="btn small" type="button" data-download="${esc(`${baseUrl}${sep}format=${f}`)}">${f.toUpperCase()}</button>`).join("");
}

async function downloadFile(url, button) {
  if (button) button.disabled = true;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Erro ${response.status}`);
    }
    const disposition = response.headers.get("Content-Disposition") || "";
    const name = (disposition.match(/filename="?([^";]+)"?/) || [])[1] || "relatorio";
    const blobUrl = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
    toast(`Relatório gerado: ${name}`);
    if (typeof refreshReportFiles === "function") refreshReportFiles();
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

document.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-download]");
  if (btn) {
    ev.preventDefault();
    downloadFile(btn.dataset.download, btn);
  }
});

/* ---------- navegação ---------- */
const views = {};

function showView(name) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  try { localStorage.setItem("view", name); } catch (e) { /* armazenamento indisponível */ }
  if (views[name]) views[name]();
}

document.querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));

/* ---------- saúde ---------- */
async function refreshHealth() {
  const dot = $("#health-dot");
  const text = $("#health-text");
  try {
    const h = await API.get("/health");
    dot.className = `dot ${h.status === "ok" ? "ok" : h.status === "atencao" ? "warn" : "err"}`;
    text.textContent = h.status === "ok" ? "Sistema operacional"
      : h.documents_root !== "ok" ? "Diretório documental indisponível" : "Verifique o sistema";
  } catch (e) {
    dot.className = "dot err";
    text.textContent = "Servidor indisponível";
  }
}

/* ---------- indexação ---------- */
let indexPoll = null;

async function startIndex(force) {
  try {
    await API.post("/api/index", { force });
    toast(force ? "Reindexação completa iniciada." : "Indexação iniciada.");
    watchIndexer();
  } catch (e) { toast(e.message, true); }
}

function renderIndexer(state) {
  const bar = $("#indexer-bar");
  if (!state.running) { bar.classList.add("hidden"); return; }
  bar.classList.remove("hidden");
  const pct = state.total ? Math.round((state.processed / state.total) * 100) : 0;
  $("#indexer-text").textContent =
    `Indexando (${state.phase}): ${state.processed} de ${state.total} arquivos${state.current ? ` — ${state.current}` : ""}`;
  $("#indexer-progress").style.width = `${pct}%`;
}

function watchIndexer() {
  if (indexPoll) return;
  const tick = async () => {
    try {
      const state = await API.get("/api/index/status");
      renderIndexer(state);
      if (!state.running) {
        clearInterval(indexPoll);
        indexPoll = null;
        if (state.error) toast(state.error, true);
        loadDashboard();
        refreshHealth();
      }
    } catch (e) { /* tenta novamente no próximo ciclo */ }
  };
  indexPoll = setInterval(tick, 1200);
  tick();
}

/* ---------- painel ---------- */
async function loadDashboard() {
  try {
    const s = await API.get("/api/status");
    $("#dash-root").textContent = `Diretório documental: ${s.documents_root}`;
    const last = s.last_run;
    const cards = [
      ["Documentos encontrados", s.found],
      ["Documentos indexados", s.indexed],
      ["Documentos com erro", s.errors, s.errors ? "err" : ""],
      ["Sem texto (requer OCR)", s.without_text, s.without_text ? "warn" : ""],
      ["Formato não suportado", s.unsupported],
      ["Contratos identificados", s.contracts],
      ["Checklists", s.checklists],
      ["Última atualização", last ? formatDate(last.finished_at) : "—", "", true],
      ["Indexador", s.indexer.running ? "Em execução" : "Parado", "", true],
    ];
    $("#dash-cards").innerHTML = cards.map(([label, value, cls, small]) => `
      <div class="card ${cls || ""}">
        <div class="label">${esc(label)}</div>
        <div class="value ${small ? "small-value" : ""}">${esc(value)}</div>
      </div>`).join("");
    $("#dash-last-run").innerHTML = last
      ? `Arquivos encontrados: <b>${last.found}</b> · novos: <b>${last.new}</b> · alterados: <b>${last.changed}</b> ·
         inalterados: <b>${last.unchanged}</b> · removidos: <b>${last.removed}</b> · erros: <b>${last.errors}</b>`
      : "Nenhuma indexação realizada. Configure o diretório documental e clique em “Atualizar índice”.";
    renderIndexer(s.indexer);
    if (s.indexer.running) watchIndexer();

    const contracts = await API.get("/api/contracts");
    $("#dash-contracts").innerHTML = contracts.length ? `
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Contrato</th><th>Contratada</th><th>Valor</th><th>Vigência</th><th>Fonte</th></tr></thead>
        <tbody>${contracts.map((c) => `
          <tr>
            <td><b>${esc(c.contract_number)}</b>${c.process_number ? `<div class="path">Processo ${esc(c.process_number)}</div>` : ""}</td>
            <td>${esc(c.contractor || "—")}${c.cnpj ? `<div class="path">CNPJ ${esc(c.cnpj)}</div>` : ""}</td>
            <td>${esc(c.value || "—")}</td>
            <td>${esc(c.start_date || "?")} a ${esc(c.end_date || "?")}</td>
            <td><a href="${fileUrl(c.source_document_id)}" target="_blank" rel="noopener">${esc(c.filename)}</a></td>
          </tr>`).join("")}
        </tbody></table></div>
      <p class="muted small" style="margin-top:8px">Dados extraídos do termo de contrato original. Aditivos posteriores
        podem alterá-los — consulte a aba Perguntas.</p>`
      : `<p class="empty">Nenhum contrato identificado até o momento.</p>`;
  } catch (e) { toast(e.message, true); }
}

$("#dash-index").addEventListener("click", () => startIndex(false));
views.dashboard = loadDashboard;

/* ---------- configurações ---------- */
async function loadConfig() {
  try {
    const c = await API.get("/api/config");
    $("#cfg-root").value = c.documents_root;
    const st = $("#cfg-root-status");
    st.textContent = c.documents_root_message;
    st.style.color = c.documents_root_ok ? "var(--ok)" : "var(--err)";
    const engines = [
      ["Endereço do painel", `http://${c.app_host}:${c.app_port}`],
      ["Indexação automática ao iniciar", c.auto_index ? "Sim" : "Não"],
    ];
    $("#cfg-engines").innerHTML = engines.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
  } catch (e) { toast(e.message, true); }
}

$("#cfg-save").addEventListener("click", async () => {
  try {
    await API.post("/api/config", { documents_root: $("#cfg-root").value });
    toast("Diretório documental salvo. Inicie a indexação para atualizar o índice.");
    loadConfig();
    refreshHealth();
  } catch (e) { toast(e.message, true); }
});

$("#cfg-browse").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  try {
    const r = await API.post("/api/config/browse");
    if (r.path) $("#cfg-root").value = r.path;
  } catch (e) { toast(e.message, true); }
  ev.target.disabled = false;
});

$("#cfg-index").addEventListener("click", () => { startIndex(false); showView("dashboard"); });
$("#cfg-reindex").addEventListener("click", () => {
  if (confirm("Reprocessar todos os documentos? Isso pode levar alguns minutos. Os arquivos originais não são alterados.")) {
    startIndex(true);
    showView("dashboard");
  }
});

$("#cfg-diagnostics").addEventListener("click", async () => {
  const list = $("#cfg-checks");
  list.innerHTML = `<li class="loading">Verificando…</li>`;
  try {
    const { checks } = await API.get("/api/diagnostics");
    const cls = { OK: "ok", WARNING: "warn", ERRO: "err" };
    list.innerHTML = checks.map((c) => `
      <li><span class="badge ${cls[c.level]}">${c.level}</span>
      <span class="check-name">${esc(c.name)}</span><span class="muted">${esc(c.message)}</span></li>`).join("");
  } catch (e) { list.innerHTML = ""; toast(e.message, true); }
});

$("#cfg-logs").addEventListener("click", async () => {
  const pre = $("#cfg-logs-content");
  try {
    const { lines } = await API.get("/api/logs?lines=300");
    pre.textContent = lines.length ? lines.join("\n") : "Nenhum registro.";
    pre.classList.remove("hidden");
    pre.scrollTop = pre.scrollHeight;
  } catch (e) { toast(e.message, true); }
});

/* ---------- OCR ---------- */
async function loadOcr() {
  try {
    renderOcr(await API.get("/api/ocr"));
  } catch (e) { toast(e.message, true); }
}

function renderOcr(st) {
  $("#ocr-enabled").checked = st.enabled;
  $("#ocr-engine").value = st.engine;
  const active = st.enabled
    ? (st.active_label ? `<li><span class="badge ok">EM USO</span><span class="check-name">${esc(st.active_label)}</span>
        <span class="muted">idioma ${esc(st.language)}, ${st.dpi} dpi, até ${st.max_pages} páginas por documento</span></li>`
      : `<li><span class="badge warn">ATENÇÃO</span><span class="check-name">Nenhum mecanismo disponível</span>
        <span class="muted">documentos digitalizados continuarão sem texto</span></li>`)
    : `<li><span class="badge">DESATIVADO</span><span class="check-name">OCR desativado</span>
        <span class="muted">documentos digitalizados ficam sem texto pesquisável</span></li>`;
  $("#ocr-engines").innerHTML = active + st.engines.map((e) => `
    <li><span class="badge ${e.available ? "ok" : ""}">${e.available ? "DISPONÍVEL" : "INDISPONÍVEL"}</span>
    <span class="check-name">${esc(e.label)}</span><span class="muted">${esc(e.message)}</span></li>`).join("");
}

$("#ocr-save").addEventListener("click", async () => {
  try {
    const st = await API.post("/api/ocr", { enabled: $("#ocr-enabled").checked, engine: $("#ocr-engine").value });
    renderOcr(st);
    toast(st.enabled ? "OCR ativado. Use “Reprocessar digitalizados” para ler os documentos já indexados."
      : "OCR desativado.");
  } catch (e) { toast(e.message, true); }
});

$("#ocr-test").addEventListener("click", async (ev) => {
  const pre = $("#ocr-test-result");
  ev.target.disabled = true;
  pre.classList.remove("hidden");
  pre.textContent = "Reconhecendo imagem de teste…";
  try {
    const r = await API.post("/api/ocr/test");
    pre.textContent = [
      `${r.ok ? "[OK]" : "[ATENÇÃO]"} ${r.engine || ""} ${r.seconds != null ? `(${r.seconds}s)` : ""}`,
      r.message, "", "Texto reconhecido:", r.text || "(nenhum)",
    ].join("\n");
  } catch (e) { pre.textContent = e.message; }
  ev.target.disabled = false;
});

$("#ocr-retry").addEventListener("click", async () => {
  try {
    await API.post("/api/index", { retry_ocr: true });
    toast("Reprocessando documentos digitalizados e imagens.");
    watchIndexer();
    showView("dashboard");
  } catch (e) { toast(e.message, true); }
});

/* ---------- IA (LLM local) ---------- */
function fillModels(models, selected) {
  const list = [...new Set([...(selected ? [selected] : []), ...models])];
  $("#ai-model").innerHTML = `<option value="">—</option>` + list.map((m) =>
    `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  $("#ai-model").value = selected || "";
}

function renderAi(st) {
  $("#ai-provider").value = st.provider;
  $("#ai-url").value = st.base_url;
  fillModels(st.models || [], st.model);
  const level = st.provider === "local" ? "ok" : (st.reachable && st.models.includes(st.model) ? "ok" : "warn");
  const label = st.provider === "local" ? "LOCAL" : (level === "ok" ? "PRONTO" : "ATENÇÃO");
  $("#ai-status").innerHTML = `<li><span class="badge ${level}">${label}</span>
    <span class="check-name">${esc(st.providers[st.provider])}</span><span class="muted">${esc(st.message)}</span></li>`;
}

async function loadAi() {
  try { renderAi(await API.get("/api/ai")); } catch (e) { toast(e.message, true); }
}

$("#ai-list").addEventListener("click", async () => {
  try {
    const { models } = await API.get(`/api/ai/models?base_url=${encodeURIComponent($("#ai-url").value.trim())}`);
    fillModels(models, $("#ai-model").value);
    toast(models.length ? `${models.length} modelo(s) encontrado(s).` : "Nenhum modelo instalado no servidor.");
  } catch (e) { toast(e.message, true); }
});

$("#ai-save").addEventListener("click", async () => {
  try {
    const st = await API.post("/api/ai", {
      provider: $("#ai-provider").value, base_url: $("#ai-url").value.trim(), model: $("#ai-model").value,
    });
    renderAi(st);
    toast("Mecanismo de respostas salvo.");
  } catch (e) { toast(e.message, true); }
});

$("#ai-test").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  try {
    const r = await API.post("/api/ai/test");
    toast(`IA respondeu em ${r.seconds}s (${r.model}): “${r.reply}”`);
  } catch (e) { toast(e.message, true); }
  ev.target.disabled = false;
});

views.configuracoes = () => { loadConfig(); loadOcr(); loadAi(); };

/* ---------- inicialização ---------- */
/* ---------- acesso: configuração inicial, login, troca de senha ---------- */
const Auth = {
  user: null,
  started: false,

  message(text, ok = false) {
    const el = $("#auth-message");
    el.textContent = text || "";
    el.classList.toggle("hidden", !text);
    el.classList.toggle("ok", ok);
  },

  show(formId) {
    for (const id of ["login-form", "setup-form", "setup-remote", "password-form"]) {
      $(`#${id}`).classList.toggle("hidden", id !== formId);
    }
    $("#auth-screen").classList.remove("hidden");
    const first = $(`#${formId} input`);
    if (first) setTimeout(() => first.focus(), 50);
  },

  showLogin(text) {
    this.message(text);
    $("#login-password").value = "";
    this.show("login-form");
  },

  showPassword(mandatory) {
    this.message("");
    $("#password-form").reset();
    $("#password-reason").textContent = mandatory
      ? "Por segurança, troque a senha temporária recebida antes de continuar."
      : "Informe a senha atual e a nova senha.";
    $("#pw-cancel").classList.toggle("hidden", mandatory);
    this.show("password-form");
  },

  expired(text) {
    if (this.user) {
      this.user = null;
      this.showLogin(text || "Sua sessão expirou. Entre novamente.");
    }
  },

  apply(status) {
    const user = status.user;
    this.user = user;
    document.body.classList.toggle("is-admin", !!(user && user.is_admin));
    document.body.classList.toggle("is-local", !!status.is_local);
    if (user) {
      $("#user-name").textContent = user.name;
      $("#user-profile").textContent = `${user.username} · ${user.profile_label}`;
    }
  },

  enter() {
    $("#auth-screen").classList.add("hidden");
    document.body.classList.remove("auth-pending");
    this.message("");
    if (!this.started) {
      this.started = true;
      refreshHealth();
      setInterval(refreshHealth, 30000);
    }
    let initial = "dashboard";
    try { initial = localStorage.getItem("view") || initial; } catch (e) { /* ignora */ }
    const nav = document.querySelector(`.nav-item[data-view="${initial}"]`);
    const allowed = nav && getComputedStyle(nav).display !== "none";
    showView(allowed ? initial : "dashboard");
  },

  async boot() {
    let status;
    try {
      status = await API.get("/api/auth/status");
    } catch (e) {
      this.show("login-form");
      this.message(e.message);
      return;
    }
    $("#app-version").textContent = status.version;
    this.apply(status);
    if (status.setup_required) {
      this.show(status.is_local ? "setup-form" : "setup-remote");
    } else if (!status.user) {
      this.showLogin("");
    } else if (status.user.must_change_password) {
      this.showPassword(true);
    } else {
      this.enter();
    }
  },
};

$("#login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await API.post("/api/auth/login", { username: $("#login-username").value.trim(), password: $("#login-password").value });
    await Auth.boot();
  } catch (e) { Auth.message(e.message); $("#login-password").value = ""; }
});

$("#setup-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if ($("#setup-password").value !== $("#setup-password2").value) { Auth.message("As senhas digitadas não conferem."); return; }
  try {
    await API.post("/api/auth/setup", {
      username: $("#setup-username").value.trim(), name: $("#setup-name").value.trim(), password: $("#setup-password").value,
    });
    await Auth.boot();
    toast("Administrador criado. Bem-vindo(a)!");
  } catch (e) { Auth.message(e.message); }
});

$("#password-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if ($("#pw-new").value !== $("#pw-new2").value) { Auth.message("As novas senhas digitadas não conferem."); return; }
  try {
    await API.post("/api/auth/password", { current_password: $("#pw-current").value, new_password: $("#pw-new").value });
    await Auth.boot();
    toast("Senha alterada com sucesso.");
  } catch (e) { Auth.message(e.message); }
});

$("#pw-cancel").addEventListener("click", () => Auth.enter());
$("#btn-password").addEventListener("click", () => Auth.showPassword(false));
$("#btn-logout").addEventListener("click", async () => {
  try { await API.post("/api/auth/logout"); } catch (e) { /* encerra mesmo assim */ }
  Auth.user = null;
  document.body.classList.add("auth-pending");
  Auth.showLogin("Você saiu do sistema.");
  $("#auth-message").classList.add("ok");
});

document.addEventListener("DOMContentLoaded", () => Auth.boot());
