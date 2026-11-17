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

/* ---------- navegação ---------- */
const views = {};

function showView(name) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  try { localStorage.setItem("view", name); } catch (e) { /* armazenamento indisponível */ }
  if (typeof Layout !== "undefined") Layout.onView(name);   // breadcrumb e item de menu atual
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

/* ---------- indexação (SAD-GD: acervo inteiro, incremental; uploads são indexados pela tela Acervo) ---------- */
let indexPoll = null;

async function startIndex() {
  try {
    await API.post("/api/sadgd/indexar");
    toast("Atualização do índice iniciada (somente arquivos novos ou alterados).");
    watchIndexer();
  } catch (e) { toast(e.message, true); }
}

function renderIndexer(state) {
  const bar = $("#indexer-bar");
  if (!state || !state.executando) { bar.classList.add("hidden"); return; }
  bar.classList.remove("hidden");
  $("#indexer-text").textContent = `Indexando o acervo: ${state.etapa || "…"}`;
  $("#indexer-progress").style.width = "100%";
}

function watchIndexer(onDone) {
  if (indexPoll) return;
  const tick = async () => {
    try {
      const state = await API.get("/api/sadgd/indexacao");
      renderIndexer(state);
      if (!state.executando) {
        clearInterval(indexPoll);
        indexPoll = null;
        if (state.erro) toast(`Falha na indexação: ${state.erro}`, true);
        else if (state.resumo) toast(`Indexação concluída: ${state.resumo.novos} novo(s), ${state.resumo.alterados} alterado(s).`);
        if (onDone) onDone(state);
        loadDashboard();
        refreshHealth();
      }
    } catch (e) { /* tenta novamente no próximo ciclo */ }
  };
  indexPoll = setInterval(tick, 1500);
  tick();
}

/* ---------- painel (SAD-GD) ---------- */
const ORIGEM_LABEL = { publico: "Público", sintetico: "Sintético", real: "Real" };

async function loadDashboard() {
  try {
    const s = await API.get("/api/sadgd/painel");
    $("#dash-root").textContent = "Acervo documental do SAD-GD (corpus acadêmico público e sintético + documentos enviados).";
    const origens = Object.entries(s.por_origem || {}).map(([k, v]) => `${ORIGEM_LABEL[k] || k}: ${v}`).join(" · ");
    const cards = [
      ["Documentos", s.documentos],
      ["Trechos indexados", s.trechos],
      ["Vetores (bge-m3)", s.vetores ?? "—"],
      ["Processos reconstruídos", s.processos],
      ["Relações entre documentos", s.relacoes],
      ["Contradições detectadas", s.contradicoes, s.contradicoes ? "warn" : ""],
      ["Normas revogadas", s.normas_revogadas],
      ["Decisões na memória", s.decisoes],
      ["Origem", origens || "—", "", true],
    ];
    $("#dash-cards").innerHTML = cards.map(([label, value, cls, small]) => `
      <div class="card ${cls || ""}">
        <div class="label">${esc(label)}</div>
        <div class="value ${small ? "small-value" : ""}">${esc(value)}</div>
      </div>`).join("");
    const ROTA = { F1_simples: "F1 — pergunta simples", F1_complexa: "F1 — pergunta complexa", F2: "F2 — apoio à decisão" };
    $("#dash-consultas").innerHTML = (s.consultas || []).length ? `
      <div class="table-wrap"><table class="table"><thead><tr><th>Rota</th><th>Consultas</th><th>Latência média</th></tr></thead>
      <tbody>${s.consultas.map((c) => `<tr><td>${esc(ROTA[c.rota] || c.rota)}</td><td>${c.total}</td>
        <td>${(c.latencia_media_ms / 1000).toFixed(1)} s</td></tr>`).join("")}</tbody></table></div>
      <p class="muted small">A pergunta é registrada apenas como hash (LGPD); rota, agentes, fontes, tokens e latência ficam na auditoria.</p>`
      : `<p class="empty">Nenhuma consulta realizada ainda.</p>`;
    const u = s.ultima_indexacao || {};
    $("#dash-last-run").innerHTML = u.inicio
      ? `${formatDate(u.fim || u.inicio)} — novos: <b>${u.novos}</b> · alterados: <b>${u.alterados}</b> ·
         removidos: <b>${u.removidos}</b> · erros: <b>${u.erros}</b> · trechos gravados: <b>${u.trechos}</b>`
      : "Nenhuma indexação registrada.";
    renderIndexer(s.indexacao);
    if (s.indexacao && s.indexacao.executando) watchIndexer();
  } catch (e) { toast(e.message, true); }
}

$("#dash-index").addEventListener("click", () => startIndex());
views.dashboard = loadDashboard;

/* ---------- configurações ---------- */
async function loadConfig() {
  try {
    const c = await API.get("/api/config");
    $("#cfg-root").value = c.documents_root;
    const st = $("#cfg-root-status");
    st.textContent = c.documents_root_message;
    st.style.color = c.documents_root_ok ? "var(--color-success)" : "var(--color-danger)";
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

$("#cfg-index").addEventListener("click", () => { startIndex(); showView("dashboard"); });
$("#cfg-reindex").addEventListener("click", () => {
  if (confirm("Atualizar o índice do acervo? Apenas arquivos novos ou alterados são processados; os originais não são alterados.")) {
    startIndex();
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
    // SAD-GD: o indexador do acervo (não mais o da v1) aplica o OCR configurado aos arquivos novos ou alterados
    await startIndex();
    showView("dashboard");
  } catch (e) { toast(e.message, true); }
});

views.configuracoes = () => { loadConfig(); loadOcr(); };

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
    document.body.classList.toggle("is-gestor", !!(user && user.is_gestor));
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
