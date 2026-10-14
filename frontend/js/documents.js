/* Aba Documentos: listagem, filtros, metadados, abertura, reindexação e duplicidades. */
"use strict";

let docsTimer = null;

async function loadDocuments() {
  const params = new URLSearchParams();
  const q = $("#docs-q").value.trim();
  if (q) params.set("q", q);
  if ($("#docs-status").value) params.set("status", $("#docs-status").value);
  if ($("#docs-type").value) params.set("doc_type", $("#docs-type").value);
  const tbody = $("#docs-table tbody");
  try {
    const data = await API.get(`/api/documents?${params}`);
    $("#docs-count").textContent = `${data.total} documento(s)` + (data.total > data.items.length ? ` — exibindo ${data.items.length}` : "");
    tbody.innerHTML = data.items.length ? data.items.map((d) => `
      <tr>
        <td><b>${esc(d.filename)}</b><div class="path">${esc(d.relative_path)}</div></td>
        <td>${esc(d.doc_type_label)}${d.ordinal ? ` (${d.ordinal}º)` : ""}</td>
        <td>${statusBadge(d.status, d.status_label)}</td>
        <td>${esc(d.contract_ref || "—")}</td>
        <td>${formatSize(d.size)}</td>
        <td>${formatDate(d.modified_at)}</td>
        <td class="actions">
          <button class="btn small" data-detail="${d.id}">Detalhes</button>
          ${d.status !== "REMOVIDO" ? `<a class="btn small" href="${fileUrl(d.id)}" target="_blank" rel="noopener">Visualizar</a>
          <button class="btn small local-only" data-open="${d.id}">Abrir</button>` : ""}
        </td>
      </tr>`).join("") : `<tr><td colspan="7" class="empty">Nenhum documento encontrado.</td></tr>`;
  } catch (e) { toast(e.message, true); }
}

async function showDocument(id) {
  try {
    const d = await API.get(`/api/documents/${id}`);
    $("#doc-dialog-title").textContent = d.filename;
    const rows = [
      ["Caminho", d.full_path],
      ["Tipo", d.doc_type_label + (d.ordinal ? ` (${d.ordinal}º)` : "")],
      ["Status", d.status_label],
      ["Contrato relacionado", d.contract_ref || "—"],
      ["Páginas", d.pages ?? "—"],
      ["Trechos indexados", d.chunks],
      ["Tamanho", formatSize(d.size)],
      ["Modificado em", formatDate(d.modified_at)],
      ["Indexado em", formatDate(d.indexed_at)],
      ["Tipo MIME", d.mime_type],
      ["OCR", d.ocr ? `${d.ocr === "windows" ? "OCR do Windows" : d.ocr} — ${d.ocr_pages || 0} página(s) reconhecida(s)` : "não aplicado"],
      ["Hash SHA-256", d.hash],
    ];
    if (d.error) rows.push(["Observação", d.error]);
    $("#doc-dialog-body").innerHTML = `
      <dl class="meta">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${d.sections.length ? `<div class="section-title">Seções identificadas</div>
        <ul>${d.sections.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
      ${d.status !== "REMOVIDO" ? `<div class="row" style="margin-top: var(--space-4)">
        <button class="btn primary admin-only" data-reindex="${d.id}">Reindexar este documento</button>
        <a class="btn" href="${fileUrl(d.id)}" target="_blank" rel="noopener">Visualizar</a>
        <button class="btn local-only" data-open="${d.id}">Abrir no Windows</button></div>` : ""}`;
    $("#doc-dialog").showModal();
  } catch (e) { toast(e.message, true); }
}

async function reindexDocument(id) {
  try {
    const d = await API.post(`/api/documents/${id}/reindex`);
    toast(`Documento reindexado: ${d.status_label}.`);
    $("#doc-dialog").close();
    loadDocuments();
  } catch (e) { toast(e.message, true); }
}

async function showDuplicates() {
  const box = $("#docs-duplicates-result");
  try {
    const { identical, possible_versions: versions } = await API.get("/api/documents/duplicates");
    const group = (g) => `<ul>${g.map((d) => `<li>${esc(d.relative_path)} <span class="muted">(${formatSize(d.size)})</span></li>`).join("")}</ul>`;
    box.innerHTML = `<div class="panel">
      <h2>Duplicidades</h2>
      <p class="muted">Apenas informativo: nenhum arquivo é excluído automaticamente.</p>
      <div class="section-title">Conteúdo idêntico (${identical.length} grupo(s))</div>
      ${identical.length ? identical.map(group).join("") : `<p class="muted">Nenhum arquivo idêntico encontrado.</p>`}
      <div class="section-title">Versões possivelmente relacionadas (${versions.length} grupo(s))</div>
      ${versions.length ? versions.map(group).join("") : `<p class="muted">Nenhuma versão relacionada encontrada.</p>`}
    </div>`;
  } catch (e) { toast(e.message, true); }
}

$("#docs-q").addEventListener("input", () => {
  clearTimeout(docsTimer);
  docsTimer = setTimeout(loadDocuments, 300);
});
$("#docs-status").addEventListener("change", loadDocuments);
$("#docs-type").addEventListener("change", loadDocuments);
$("#docs-duplicates").addEventListener("click", showDuplicates);
$("#doc-dialog-close").addEventListener("click", () => $("#doc-dialog").close());

document.addEventListener("click", (ev) => {
  const t = ev.target;
  if (t.dataset.detail) showDocument(t.dataset.detail);
  else if (t.dataset.reindex) reindexDocument(t.dataset.reindex);
  else if (t.dataset.open && t.closest("#view-documentos, #doc-dialog")) openInWindows(t.dataset.open);
});

views.documentos = loadDocuments;
