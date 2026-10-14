/* Aba Relatórios: catálogo de relatórios, parâmetros e arquivos já gerados. */
"use strict";

let reportChecklists = [];

function reportParams(kind) {
  const params = new URLSearchParams();
  const card = document.querySelector(`[data-report="${kind}"]`);
  const question = card.querySelector("[data-param=question]");
  const checklist = card.querySelector("[data-param=checklist_id]");
  if (question) params.set("question", question.value.trim());
  if (checklist && checklist.value) params.set("checklist_id", checklist.value);
  return params;
}

function paramInput(param) {
  const optional = param.endsWith("?");
  const name = param.replace("?", "");
  if (name === "question") {
    return `<input type="text" data-param="question" maxlength="1000" placeholder="Ex.: Qual o valor do contrato 034/2022?">`;
  }
  if (name === "checklist_id") {
    const options = reportChecklists.map((c) =>
      `<option value="${c.id}">${esc(c.name)}${c.contract_ref ? ` — ${esc(c.contract_ref)}` : ""}</option>`).join("");
    return `<select data-param="checklist_id">
      ${optional ? `<option value="">Todos os checklists</option>` : (options ? "" : `<option value="">Nenhum checklist cadastrado</option>`)}
      ${options}</select>`;
  }
  return "";
}

async function loadReports() {
  try {
    const [{ reports, formats }, checklists] = await Promise.all([API.get("/api/reports"), API.get("/api/checklists")]);
    reportChecklists = checklists;
    $("#rep-cards").innerHTML = reports.map((r) => `
      <div class="panel report-card" data-report="${r.kind}">
        <h2>${esc(r.title)}</h2>
        <p class="muted">${esc(r.description)}</p>
        ${r.params.map(paramInput).join("")}
        <div class="export-buttons">${formats.map((f) =>
          `<button class="btn small" type="button" data-report-format="${f}">${f.toUpperCase()}</button>`).join("")}</div>
      </div>`).join("");
    refreshReportFiles();
  } catch (e) { toast(e.message, true); }
}

async function refreshReportFiles() {
  try {
    const files = await API.get("/api/reports/files");
    $("#rep-files").innerHTML = files.length ? `
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Arquivo</th><th>Tamanho</th><th>Gerado em</th><th></th></tr></thead>
        <tbody>${files.slice(0, 100).map((f) => `
          <tr><td>${esc(f.name)}</td><td>${formatSize(f.size)}</td><td>${formatDate(f.created_at)}</td>
          <td class="actions"><a class="btn small" href="/api/reports/files/${encodeURIComponent(f.name)}">Baixar</a></td></tr>`).join("")}
        </tbody></table></div>`
      : `<p class="empty">Nenhum relatório gerado ainda.</p>`;
  } catch (e) { /* lista é complementar; erros já aparecem nas outras ações */ }
}

$("#rep-cards").addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-report-format]");
  if (!btn) return;
  const kind = btn.closest("[data-report]").dataset.report;
  const params = reportParams(kind);
  params.set("format", btn.dataset.reportFormat);
  downloadFile(`/api/reports/${kind}?${params}`, btn);
});

views.relatorios = loadReports;
