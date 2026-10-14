/* Aba Perguntas: envio da pergunta e apresentação de resposta, conflitos e fontes. */
"use strict";

const EXAMPLES = [
  "Quando encerra o contrato 034/2022?",
  "Qual o valor do contrato 034/2022?",
  "Qual é o objeto do contrato 034/2022?",
  "Quais são os itens do contrato 034/2022?",
  "Quem é a contratada?",
  "Qual o CNPJ da contratada?",
  "Qual a data de assinatura?",
  "Qual é a vigência?",
  "Quais termos aditivos existem?",
  "Qual foi o último aditivo?",
  "Qual o valor atualizado?",
  "Quais documentos comprovam a vigência?",
  "Quais documentos estão relacionados ao contrato 034/2022?",
];

const KIND_BADGE = {
  FATO_DOCUMENTAL: "ok", INFERENCIA: "info", CONFLITO: "err", AUSENCIA: "warn", TRECHOS: "", RESPOSTA_IA: "info",
};

function renderAiInfo(ai) {
  if (!ai) return "";
  if (ai.validated && ai.local_answer) {
    return `<details class="ai-details"><summary>Resposta redigida por IA local (${esc(ai.model)}, ${ai.seconds}s) —
      validada nos trechos. Ver resposta do mecanismo local</summary><p>${esc(ai.local_answer)}</p></details>`;
  }
  if (ai.used && !ai.validated && ai.rejected_answer) {
    return `<details class="ai-details"><summary>Ver resposta descartada da IA (${esc(ai.model)})</summary>
      <p>${esc(ai.rejected_answer)}</p></details>`;
  }
  return "";
}

function sourceMeta(s) {
  return [s.page ? `pág. ${s.page}` : null, s.section].filter(Boolean).map(esc).join(" · ");
}

function renderSources(sources) {
  if (!sources.length) return "";
  return `<div class="section-title">Fontes</div><ul class="sources">${sources.map((s) => `
    <li class="source">
      <div class="source-head">
        <div>${s.ref ? `<b>[${s.ref}]</b> ` : ""}<span class="source-name">${esc(s.filename)}</span>
          ${s.ocr ? `<span class="badge warn" title="Texto reconhecido por OCR">OCR</span>` : ""}
          ${sourceMeta(s) ? `<span class="source-meta"> — ${sourceMeta(s)}</span>` : ""}</div>
        <div>
          <a class="btn small" href="${fileUrl(s.document_id, s.page)}" target="_blank" rel="noopener">Visualizar</a>
          <button class="btn small local-only" data-open="${s.document_id}">Abrir no Windows</button>
        </div>
      </div>
      ${s.excerpt ? `<div class="source-excerpt">${esc(s.excerpt)}</div>` : ""}
    </li>`).join("")}</ul>`;
}

function renderConflicts(conflicts) {
  if (!conflicts.length) return "";
  return `<div class="section-title">Conflito identificado</div><div class="conflict-box">${conflicts.map((c) => `
    <div class="conflict-item"><b>${esc(c.filename)}</b>${c.page ? ` (pág. ${c.page})` : ""}:
      <strong>${esc(c.value)}</strong></div>`).join("")}
    <div class="conflict-item">Conclusão: os documentos apresentam valores divergentes. É necessária conferência documental.</div>
  </div>`;
}

function renderPassages(passages) {
  if (!passages.length) return "";
  return `<div class="section-title">Trechos dos documentos</div>${passages.map((p) => `
    <div class="source">
      <div class="source-head"><span class="source-name">${esc(p.filename)}</span>
        <span class="source-meta">${sourceMeta(p)}</span></div>
      <div class="source-excerpt passage">${esc(p.text)}</div>
    </div>`).join("")}`;
}

async function ask(question) {
  const out = $("#ask-result");
  if (!question.trim()) return;
  out.innerHTML = `<div class="panel loading">Consultando os documentos…</div>`;
  try {
    const r = await API.post("/api/ask", { question });
    out.innerHTML = `
      <div class="panel answer ${esc(r.kind)}">
        <div class="answer-head">
          <span class="badge ${KIND_BADGE[r.kind] ?? ""}">${esc(r.kind_label)}</span>
          <span class="badge">Confiança: ${esc(r.confidence)}</span>
          ${r.ai && r.ai.validated ? `<span class="badge info">IA local</span>` : ""}
          <span class="question">${esc(question)}</span>
        </div>
        <p class="answer-text">${esc(r.answer)}</p>
        ${r.note ? `<div class="note">${esc(r.note)}</div>` : ""}
        ${(r.warnings || []).map((w) => `<div class="note warning-note">${esc(w)}</div>`).join("")}
        ${renderAiInfo(r.ai)}
        ${renderConflicts(r.conflicts)}
        ${renderPassages(r.passages)}
        ${renderSources(r.sources)}
        <div class="answer-export"><span class="muted small">Exportar resultado:</span>
          ${exportButtons(`/api/reports/consulta?question=${encodeURIComponent(question)}`, ["pdf", "docx", "xlsx", "json"])}
        </div>
      </div>`;
  } catch (e) {
    out.innerHTML = "";
    toast(e.message, true);
  }
}

$("#ask-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  ask($("#ask-input").value);
});

$("#ask-examples").innerHTML = EXAMPLES.map((q) => `<button class="chip" type="button">${esc(q)}</button>`).join("");
$("#ask-examples").addEventListener("click", (ev) => {
  if (!ev.target.classList.contains("chip")) return;
  $("#ask-input").value = ev.target.textContent;
  ask(ev.target.textContent);
});

$("#ask-result").addEventListener("click", (ev) => {
  const id = ev.target.dataset.open;
  if (id) openInWindows(id);
});

views.perguntas = () => $("#ask-input").focus();
