/* Aba Checklist: inserir, salvar, executar, filtrar, organizar e exportar. */
"use strict";

const CK_CLASS = {
  ATENDIDO: "ok", PARCIALMENTE_ATENDIDO: "warn", AUSENTE: "err", DUVIDA: "info",
  DUPLICADO: "", VENCIDO: "err", INCOMPATIVEL: "err", NAO_IDENTIFICADO: "warn",
};
const ck = { id: null, data: null, filter: "" };

async function loadChecklistList(selectId) {
  try {
    const list = await API.get("/api/checklists");
    const select = $("#ck-select");
    select.innerHTML = `<option value="">Novo checklist</option>` + list.map((c) =>
      `<option value="${c.id}">${esc(c.name)}${c.contract_ref ? ` — ${esc(c.contract_ref)}` : ""} (${c.items} itens)${c.created_by_name ? ` · ${esc(c.created_by_name)}` : ""}</option>`).join("");
    select.value = selectId ?? ck.id ?? "";
  } catch (e) { toast(e.message, true); }
}

function resetChecklistForm() {
  ck.id = null;
  ck.data = null;
  $("#ck-name").value = "";
  $("#ck-contract").value = "";
  $("#ck-text").value = "";
  applyChecklistPermission(null);
  $("#ck-results").classList.add("hidden");
}

async function openChecklist(id) {
  if (!id) { resetChecklistForm(); return; }
  try {
    const data = await API.get(`/api/checklists/${id}`);
    ck.id = data.checklist.id;
    $("#ck-name").value = data.checklist.name;
    $("#ck-contract").value = data.checklist.contract_ref || "";
    $("#ck-text").value = data.checklist.source_text || "";
    $("#ck-delete").disabled = false;
    renderChecklist(data);
  } catch (e) { toast(e.message, true); }
}

async function saveChecklist() {
  if (ck.id && ck.data && !ck.data.checklist.can_edit) {
    return ck.data;  // checklist de outra pessoa: executa sem alterar o conteúdo
  }
  const body = {
    name: $("#ck-name").value.trim(),
    contract_ref: $("#ck-contract").value.trim() || null,
    text: $("#ck-text").value,
  };
  const data = ck.id ? await API.put(`/api/checklists/${ck.id}`, body) : await API.post("/api/checklists", body);
  ck.id = data.checklist.id;
  applyChecklistPermission(data.checklist);
  await loadChecklistList(ck.id);
  return data;
}

function evidenceHtml(ev) {
  const where = [ev.page ? `pág. ${ev.page}` : null, ev.section, ev.note].filter(Boolean).map(esc).join(" · ");
  return `<div class="ck-evidence">
    <div><b>${esc(ev.filename)}</b>${where ? ` <span class="source-meta">— ${where}</span>` : ""}</div>
    <div>
      <a class="btn small" href="${fileUrl(ev.document_id, ev.page)}" target="_blank" rel="noopener">Visualizar</a>
      <button class="btn small local-only" data-ck-open="${ev.document_id}">Abrir</button>
    </div>
    ${ev.excerpt ? `<div class="source-excerpt">${esc(ev.excerpt)}</div>` : ""}
  </div>`;
}

function renderItems() {
  const data = ck.data;
  const items = data.items.filter((i) => !ck.filter || i.status === ck.filter);
  let group = undefined;
  $("#ck-items").innerHTML = items.length ? items.map((i) => {
    const header = i.category !== group ? `<div class="ck-group">${esc(i.category || "Sem grupo")}</div>` : "";
    group = i.category;
    return `${header}<div class="ck-item ${CK_CLASS[i.status] ?? ""}">
      <div class="ck-item-head">
        <span class="ck-num">ITEM ${String(i.position).padStart(2, "0")}</span>
        <span class="ck-desc">${esc(i.description)}</span>
        ${i.priority !== "normal" ? `<span class="badge">prioridade ${esc(i.priority)}</span>` : ""}
        <span class="badge ${CK_CLASS[i.status] ?? ""}">${esc(i.status_label)}</span>
        ${i.confidence ? `<span class="badge">confiança ${esc(i.confidence === "media" ? "média" : i.confidence)}</span>` : ""}
      </div>
      ${i.justification ? `<p class="ck-just">${esc(i.justification)}</p>` : ""}
      ${i.evidences.map(evidenceHtml).join("")}
    </div>`;
  }).join("") : `<p class="empty">Nenhum item com este status.</p>`;
}

function renderSummary() {
  const { summary, status_labels: labels, items } = ck.data;
  const chips = [[" ", `Todos (${items.length})`]].concat(
    Object.entries(summary).map(([k, v]) => [k, `${labels[k]} (${v})`]));
  $("#ck-summary").innerHTML = chips.map(([k, label]) =>
    `<button class="chip ${(ck.filter || " ") === k ? "active" : ""}" data-ck-filter="${k.trim()}">${esc(label)}</button>`).join("");
  $("#ck-filter").innerHTML = `<option value="">Todos os status</option>` +
    Object.entries(labels).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join("");
  $("#ck-filter").value = ck.filter;
}

async function renderOrganization() {
  const box = $("#ck-organization");
  try {
    const org = await API.get(`/api/checklists/${ck.id}/organization`);
    const pending = (title, list) => list.length ? `<div class="ck-group">${title}</div><ul>${list.map((i) =>
      `<li>ITEM ${String(i.position).padStart(2, "0")} — ${esc(i.description)}
       <span class="badge ${CK_CLASS[i.status] ?? ""}">${esc(ck.data.status_labels[i.status])}</span></li>`).join("")}</ul>` : "";
    box.innerHTML = (org.folders.length ? `<div class="tree"><div class="folder">CHECKLIST</div>${org.folders.map((f) => `
        <div class="folder">├── ${esc(f.name)}</div>
        ${f.documents.map((d) => `<div class="file">└── <a href="${fileUrl(d.document_id)}" target="_blank" rel="noopener">${esc(d.filename)}</a>
          <span class="muted small">(itens ${d.items.join(", ")})</span></div>`).join("")}`).join("")}</div>`
      : `<p class="empty">Nenhum documento comprova itens deste checklist.</p>`)
      + pending("Itens sem documento", org.without_documents)
      + pending("Itens a conferir", org.to_review);
  } catch (e) { box.innerHTML = ""; toast(e.message, true); }
}

function applyChecklistPermission(c) {
  const editable = !c || c.can_edit !== false;  // null = checklist novo
  $("#ck-delete").disabled = !c || !editable;
  $("#ck-save").disabled = !editable;
  for (const id of ["#ck-name", "#ck-contract", "#ck-text"]) $(id).readOnly = !editable;
  $("#ck-run").textContent = editable ? "Salvar e executar" : "Executar";
  const note = $("#ck-owner-note");
  note.textContent = editable ? "" : `Checklist criado por ${c.created_by_name || "outro usuário"}: você pode executar e exportar, mas somente o autor ou um administrador pode alterá-lo ou excluí-lo.`;
  note.classList.toggle("hidden", editable);
}

function renderChecklist(data) {
  ck.data = data;
  const c = data.checklist;
  applyChecklistPermission(c);
  $("#ck-results").classList.remove("hidden");
  $("#ck-title").textContent = c.name;
  $("#ck-run-info").textContent = (c.contract_ref ? `Contrato ${c.contract_ref} · ` : "Todos os documentos · ") +
    (c.last_run_at ? `Avaliado em ${formatDate(c.last_run_at)}` : "Ainda não executado — clique em “Salvar e executar”.");
  $("#ck-export").innerHTML = exportButtons(`/api/checklists/${c.id}/export`, ["pdf", "docx", "xlsx", "csv", "txt", "json"]);
  renderSummary();
  renderItems();
  renderOrganization();
}

$("#ck-select").addEventListener("change", (ev) => { ck.filter = ""; openChecklist(ev.target.value); });

$("#ck-save").addEventListener("click", async () => {
  try {
    const data = await saveChecklist();
    toast(`Checklist salvo com ${data.items.length} item(ns).`);
    renderChecklist(data);
  } catch (e) { toast(e.message, true); }
});

$("#ck-run").addEventListener("click", async (ev) => {
  const btn = ev.target;
  btn.disabled = true;
  btn.textContent = "Executando…";
  try {
    await saveChecklist();
    const data = await API.post(`/api/checklists/${ck.id}/run`);
    ck.filter = "";
    renderChecklist(data);
    toast("Checklist avaliado.");
  } catch (e) { toast(e.message, true); }
  btn.disabled = false;
  btn.textContent = ck.data && ck.data.checklist.can_edit === false ? "Executar" : "Salvar e executar";
});

$("#ck-delete").addEventListener("click", async () => {
  if (!ck.id || !confirm("Excluir este checklist e seus resultados? Os documentos não são afetados.")) return;
  try {
    await API.del(`/api/checklists/${ck.id}`);
    resetChecklistForm();
    await loadChecklistList("");
    toast("Checklist excluído.");
  } catch (e) { toast(e.message, true); }
});

$("#ck-file").addEventListener("change", async (ev) => {
  const file = ev.target.files[0];
  ev.target.value = "";
  if (!file) return;
  try {
    const buffer = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let i = 0; i < buffer.length; i += 0x8000) binary += String.fromCharCode(...buffer.subarray(i, i + 0x8000));
    const { text } = await API.post("/api/checklists/parse-file", { filename: file.name, content_base64: btoa(binary) });
    $("#ck-text").value = text;
    if (!$("#ck-name").value) $("#ck-name").value = file.name.replace(/\.[^.]+$/, "");
    toast("Arquivo carregado. Revise os itens e clique em Salvar.");
  } catch (e) { toast(e.message, true); }
});

$("#ck-filter").addEventListener("change", (ev) => { ck.filter = ev.target.value; renderSummary(); renderItems(); });
$("#ck-summary").addEventListener("click", (ev) => {
  if (ev.target.dataset.ckFilter === undefined) return;
  ck.filter = ev.target.dataset.ckFilter;
  renderSummary();
  renderItems();
});
$("#view-checklist").addEventListener("click", (ev) => {
  if (ev.target.dataset.ckOpen) openInWindows(ev.target.dataset.ckOpen);
});

views.checklist = () => loadChecklistList();
