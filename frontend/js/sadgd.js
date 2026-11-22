/* SAD-GD (Fase 9): Perguntar (F1/F2), Acervo (upload e indexação), Linha do tempo e Memória de decisões.
   Todo conteúdo vindo do servidor passa por esc() antes de entrar no HTML. */
"use strict";

const SG = {
  CLASSE: { fato: ["ok", "Fato documental"], inferencia: ["info", "Inferência"], conflito: ["err", "Conflito"],
            ausencia: ["warn", "Informação ausente"], candidatos: ["info", "Documentos para conferir"] },
  ROTA: { F1_simples: "Pergunta simples", F1_complexa: "Pergunta complexa", F2: "Apoio à decisão" },
  AGENTE: {
    procurador_estado: "Procurador do Estado", advogado: "Advogado", controlador_geral: "Controlador-Geral",
    fiscal_contrato: "Fiscal de Contrato", gestor_publico: "Gestor Público", analista_administrativo: "Analista Administrativo",
    analista_orcamentario_financeiro: "Analista Orçamentário-Financeiro", especialista_licitacoes: "Especialista em Licitações",
  },
  RELACAO: { continuacao: "", aditivo: "info", alteracao: "info", revogacao: "err", substituicao: "warn",
             ruptura: "err", contradicao: "err", retomada: "ok", regulamenta: "", fundamenta: "" },
  AVALIACAO: { positivo: "ok", negativo: "err", neutro: "", pendente: "warn" },
  ORIGEM: { publico: ["info", "Público"], sintetico: ["", "Sintético"], real: ["warn", "Real"] },
  ELEMENTO: { alternativas: "Alternativas", riscos: "Riscos", base_legal: "Base legal", precedentes: "Precedentes",
              confianca: "Confiança", aviso: "Aviso" },
  NIVEL: { baixa: "warn", media: "warn", alta: "err", baixo: "", medio: "warn", alto: "err" },
  STATUS: { COM_TEXTO: "com texto", COM_OCR: "texto por OCR", ESCANEADO: "digitalizado sem OCR",
            SEM_TEXTO: "sem texto", CORROMPIDO: "corrompido", NAO_SUPORTADO: "não suportado" },
};

const sgPct = (v) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "—");
const sgBadge = (cls, txt) => `<span class="badge ${cls || ""}">${esc(txt)}</span>`;
const sgArquivo = (id, pagina) => `/api/sadgd/documentos/${id}/arquivo${pagina ? `#page=${pagina}` : ""}`;

/* [T123] e [P7] no texto viram atalhos para a fonte / o precedente (o texto já vem escapado) */
function sgCitacoes(texto) {
  return esc(texto)
    .replace(/\[T(\d+)\]/g, `<a href="#" class="cit" data-trecho="$1" title="Ver trecho citado">[T$1]</a>`)
    .replace(/\[P(\d+)\]/g, `<a href="#sg-prec-P$1" class="cit" title="Ver precedente">[P$1]</a>`);
}

async function sgVerTrecho(id) {
  const dlg = $("#doc-dialog");
  $("#doc-dialog-title").textContent = `Trecho T${id}`;
  $("#doc-dialog-body").innerHTML = `<p class="loading">Carregando…</p>`;
  if (!dlg.open) dlg.showModal();
  try {
    const t = await API.get(`/api/sadgd/trechos/${id}`);
    $("#doc-dialog-title").textContent = t.titulo || t.caminho_relativo;
    $("#doc-dialog-body").innerHTML = `
      <p class="muted small">${esc([t.dispositivo, t.pagina ? `pág. ${t.pagina}` : null, t.data_documento,
        t.caminho_relativo].filter(Boolean).join(" · "))}
        ${t.revogado || t.situacao_norma === "revogada" ? sgBadge("err", "revogado — não fundamenta decisão atual") : ""}</p>
      <div class="source-excerpt passage">${esc(t.texto)}</div>
      <p><a class="btn small" href="${sgArquivo(t.documento_id, t.pagina)}" target="_blank" rel="noopener">Abrir documento original</a></p>`;
  } catch (e) { $("#doc-dialog-body").innerHTML = `<p class="empty">${esc(e.message)}</p>`; }
}

document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-trecho]");
  if (a) { ev.preventDefault(); sgVerTrecho(a.dataset.trecho); }
});
$("#doc-dialog-close").addEventListener("click", () => $("#doc-dialog").close());

/* ============================== PERGUNTAR ============================== */
const SG_EXEMPLOS = [
  "Qual o valor global do Contrato nº 044/2023?",
  "Quando termina a vigência do Contrato nº 012/2023?",
  "O Decreto nº 7.892/2013 ainda está em vigor?",
  "Qual a sequência de eventos do Contrato nº 031/2023?",
  "Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?",
];

function sgFontes(fontes) {
  if (!fontes || !fontes.length) return "";
  return `<div class="section-title">Fontes citadas</div><ul class="sources">${fontes.map((f) => `
    <li class="source" id="sg-fonte-T${f.trecho_id}">
      <div class="source-head">
        <div><b>[T${f.trecho_id}]</b> <span class="source-name">${esc(f.titulo || f.arquivo)}</span>
          <span class="source-meta"> — ${esc([f.dispositivo, f.pagina ? `pág. ${f.pagina}` : null, f.arquivo].filter(Boolean).join(" · "))}</span>
          ${f.revogado || f.situacao_norma === "revogada" ? sgBadge("err", "revogado") : ""}</div>
        <div>
          <button class="btn small" type="button" data-trecho="${f.trecho_id}">Ver trecho</button>
          <a class="btn small" href="${sgArquivo(f.documento_id, f.pagina)}" target="_blank" rel="noopener">Abrir documento</a>
        </div>
      </div>
      <div class="source-excerpt">${esc((f.texto || "").slice(0, 320))}${(f.texto || "").length > 320 ? "…" : ""}</div>
    </li>`).join("")}</ul>`;
}

function sgLista(titulo, itens, render) {
  return itens && itens.length ? `<div class="section-title">${esc(titulo)}</div><ul class="sg-list">${itens.map((i) => `<li>${render(i)}</li>`).join("")}</ul>` : "";
}

function sgRiscos(riscos) {
  if (!riscos || !riscos.length) return "";
  return `<div class="section-title">Riscos</div><div class="table-wrap"><table class="table">
    <thead><tr><th>Risco</th><th>Probabilidade</th><th>Impacto</th><th>Mitigação</th></tr></thead><tbody>
    ${riscos.map((r) => `<tr><td>${esc(r.descricao)}${r.agente ? `<div class="path">${esc(SG.AGENTE[r.agente] || r.agente)}</div>` : ""}</td>
      <td>${sgBadge(SG.NIVEL[r.probabilidade], r.probabilidade || "—")}</td><td>${sgBadge(SG.NIVEL[r.impacto], r.impacto || "—")}</td>
      <td>${esc(r.mitigacao || "—")}</td></tr>`).join("")}</tbody></table></div>`;
}

function sgAlternativas(alts) {
  return sgLista("Alternativas", alts, (a) => `<b>${esc(a.descricao)}</b>
    ${(a.pros || []).length ? `<div class="small"><span class="badge ok">prós</span> ${(a.pros || []).map(esc).join("; ")}</div>` : ""}
    ${(a.contras || []).length ? `<div class="small"><span class="badge err">contras</span> ${(a.contras || []).map(esc).join("; ")}</div>` : ""}`);
}

function sgPrecedentes(precs) {
  if (!precs || !precs.length) return "";
  return `<div class="section-title">Precedentes da gestão (informam, não vinculam)</div>${precs.map((p) => `
    <div class="source sg-prec" id="sg-prec-${esc(p.id)}">
      <div class="source-head"><div><b>[${esc(p.id)}]</b> <span class="source-name">${esc(p.titulo)}</span>
        <span class="source-meta"> — ${esc(p.data)}</span></div>
        ${sgBadge(SG.AVALIACAO[p.avaliacao_resultado], `resultado ${p.avaliacao_resultado}`)}</div>
      <div class="small"><b>Decisão:</b> ${esc(p.decisao)}</div>
      ${p.resultado ? `<div class="small"><b>Resultado:</b> ${esc(p.resultado)}</div>` : ""}
      <div class="note">${esc(p.licao)}</div>
    </div>`).join("")}`;
}

function sgParecer(p) {
  const d = p.parecer || {};
  return `<details class="ai-details sg-parecer"><summary><b>${esc(SG.AGENTE[p.agente] || p.agente)}</b>
      ${p.valido ? sgBadge("ok", "estrutura válida") : sgBadge("err", "parecer inválido — ignorado pelo relator")}
      ${typeof d.confianca === "number" ? sgBadge("", `confiança ${sgPct(d.confianca)}`) : ""}</summary>
    ${d.parecer ? `<p>${sgCitacoes(d.parecer)}</p>` : ""}
    ${d.recomendacao ? `<p><b>Recomendação do agente:</b> ${sgCitacoes(d.recomendacao)}</p>` : ""}
    ${sgLista("Afirmações verificadas", d.afirmacoes, (a) => `${sgBadge(a.tipo === "fato" ? "ok" : "info", a.tipo)} ${sgCitacoes(a.texto)}
      ${(a.citacoes || []).map((c) => sgCitacoes(`[${c}]`)).join(" ")}`)}
    ${sgLista("Fundamentação legal", d.fundamentacao_legal, (f) => `${esc(f.norma)} ${esc(f.dispositivo || "")} ${sgCitacoes(`[${f.trecho}]`)}`)}
    ${sgLista("Lacunas", d.lacunas, (l) => esc(l))}
  </details>`;
}

function sgRenderF2(r) {
  const d = r.recomendacao || {};
  const el = r.elementos_rf20 || {};
  return `
    <div class="sg-recomendacao"><div class="section-title">Recomendação sugerida</div>
      <p class="answer-text"><b>${sgCitacoes(d.recomendacao || "")}</b></p></div>
    <div class="sg-elementos" aria-label="Elementos obrigatórios da recomendação (RF-20)">
      ${Object.entries(SG.ELEMENTO).map(([k, rotulo]) => sgBadge(el[k] === "presente" ? "ok" : el[k] === "declarado" ? "warn" : "err",
        `${rotulo}: ${el[k] === "presente" ? "presente" : el[k] === "declarado" ? "ausência declarada" : "ausente"}`)).join(" ")}
    </div>
    ${(d.alertas || []).map((a) => `<div class="note warning-note">${esc(a)}</div>`).join("")}
    ${sgAlternativas(d.alternativas)}
    ${sgRiscos(d.riscos)}
    ${sgLista("Base legal vigente (pela hierarquia normativa)", d.base_legal, (b) => `${esc(b.norma)} ${esc(b.dispositivo || "")} ${sgCitacoes(`[${b.trecho}]`)}`)}
    ${sgLista("Normas revogadas consideradas apenas como histórico", d.normas_no_historico, (b) => `${esc(b.norma)} ${sgCitacoes(`[${b.trecho}]`)}`)}
    ${sgPrecedentes(d.precedentes)}
    ${sgLista("Consensos entre os pareceres", d.consensos, (c) => sgCitacoes(typeof c === "string" ? c : JSON.stringify(c)))}
    ${sgLista("Divergências", d.divergencias, (v) => `<b>${esc(v.tema)}</b>: ${(v.posicoes || []).map((p) =>
      `${esc(SG.AGENTE[p.agente] || p.agente)} — ${sgCitacoes(p.posicao)}`).join(" | ")}`)}
    ${sgLista("Lacunas", d.lacunas, (l) => esc(l))}
    <div class="section-title">Pareceres dos agentes especialistas</div>
    ${(r.pareceres || []).map(sgParecer).join("") || `<p class="empty">Nenhum parecer.</p>`}`;
}

function sgRender(pergunta, r) {
  const classe = r.rota === "F2" ? (r.recomendacao || {}).classificacao : r.classificacao;
  const [cls, rotulo] = SG.CLASSE[classe] || ["", classe || "—"];
  const obs = (r.observacoes || []).filter((o) => /verificador|conflito/.test(o));
  return `
    <div class="panel answer sg-${esc(classe || "")}">
      <div class="answer-head">
        ${sgBadge(cls, rotulo)} ${sgBadge("", `Confiança: ${sgPct(r.confianca)}`)}
        ${sgBadge("info", SG.ROTA[r.rota] || r.rota)}
        ${r.agentes && r.agentes.length && r.rota === "F2" ? sgBadge("", `${r.agentes.length} agente(s)`) : ""}
        <span class="question">${esc(pergunta)} · ${(r.latencia_ms / 1000).toFixed(1)} s</span>
      </div>
      <p class="answer-text">${sgCitacoes((r.resposta || "").replace(r.aviso, "").trim())}</p>
      ${obs.length ? `<div class="note">Verificador de fontes: ${obs.map((o) => esc(o.replace(/_/g, " "))).join("; ")}.</div>` : ""}
      ${r.rota === "F2" ? sgRenderF2(r) : sgLista("Lacunas", r.lacunas, (l) => esc(l))}
      ${sgFontes(r.fontes)}
      <div class="note">${esc(r.aviso)} Consulta nº ${r.consulta_id} registrada na auditoria.</div>
    </div>`;
}

/* Conversa: cada pergunta entra numa fila no servidor (um LLM local por vez); a tela acompanha posição, etapa e
   tempo decorrido e mostra a resposta quando fica pronta. Várias perguntas podem ser enviadas em sequência. */
const sgEspera = (s) => (s.posicao > 1 ? `Na fila — ${s.posicao - 1} pergunta(s) à frente`
  : s.etapa_descricao || (s.estado === "fila" ? "Na fila" : "Analisando os documentos"));

async function sgPerguntar(pergunta) {
  pergunta = pergunta.trim();
  if (pergunta.length < 3) return;
  $("#sg-pergunta").value = "";
  const conversa = $("#sg-resultado");
  const turno = document.createElement("div");
  turno.className = "turn";
  turno.innerHTML = `<div class="turn-question"><span class="muted">Você</span><p>${esc(pergunta)}</p></div>
    <div class="panel loading" role="status"><span class="spinner" aria-hidden="true"></span>
      <span class="sg-etapa">Enviando…</span> <span class="muted sg-tempo"></span></div>`;
  conversa.appendChild(turno);
  turno.scrollIntoView({ behavior: "smooth", block: "start" });
  const status = turno.querySelector(".panel.loading");
  try {
    let s = await API.post("/api/sadgd/consultas", { pergunta });
    while (s.estado === "fila" || s.estado === "processando") {
      status.querySelector(".sg-etapa").textContent = sgEspera(s);
      status.querySelector(".sg-tempo").textContent = `${Math.round(s.decorrido_s)} s`;
      await new Promise((ok) => setTimeout(ok, 1000));
      s = await API.get(`/api/sadgd/consultas/${s.id}`);
    }
    if (s.estado === "erro") throw new Error(s.erro || "Falha ao processar a pergunta.");
    status.outerHTML = sgRender(pergunta, s.resultado);
  } catch (e) {
    status.outerHTML = `<div class="panel note err">${esc(e.message)}</div>`;
  }
}

$("#sg-form").addEventListener("submit", (ev) => { ev.preventDefault(); sgPerguntar($("#sg-pergunta").value); });

/* Pergunta por voz: grava no navegador, converte para WAV 16 kHz mono e transcreve NO SERVIDOR (Whisper local) —
   o áudio não vai para serviços externos. O texto volta para a caixa para conferência antes do envio. */
const SgVoz = {
  gravando: false, contexto: null, fonte: null, processador: null, fluxo: null, blocos: [], limite: null,
  async alternar() { return this.gravando ? this.parar() : this.iniciar(); },
  async iniciar() {
    if (!navigator.mediaDevices || !window.isSecureContext) {
      toast("O microfone só funciona em conexão segura (https) ou no próprio computador do servidor.", true);
      return;
    }
    try {
      this.fluxo = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, noiseSuppression: true, echoCancellation: true } });
    } catch (e) {
      toast("Permita o uso do microfone no navegador para perguntar por voz.", true);
      return;
    }
    this.contexto = new (window.AudioContext || window.webkitAudioContext)();
    this.fonte = this.contexto.createMediaStreamSource(this.fluxo);
    this.processador = this.contexto.createScriptProcessor(4096, 1, 1);
    this.blocos = [];
    this.processador.onaudioprocess = (ev) => this.blocos.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
    this.fonte.connect(this.processador);
    this.processador.connect(this.contexto.destination);
    this.gravando = true;
    this.limite = setTimeout(() => this.parar(), 60000);
    this.botao(true);
  },
  async parar() {
    clearTimeout(this.limite);
    this.gravando = false;
    this.botao(false, "Transcrevendo…");
    this.processador.disconnect(); this.fonte.disconnect();
    this.fluxo.getTracks().forEach((t) => t.stop());
    const taxa = this.contexto.sampleRate;
    await this.contexto.close();
    const wav = this.wav(this.reamostrar(this.blocos, taxa, 16000), 16000);
    try {
      const resp = await fetch("/api/sadgd/transcrever", { method: "POST", body: wav,
        headers: { "X-Requested-With": "AgenteDocumental", "Content-Type": "audio/wav" } });
      const dados = await resp.json().catch(() => ({}));
      if (resp.status === 401) Auth.expired(dados.detail);
      if (!resp.ok) throw new Error(dados.detail || `Erro ${resp.status}`);
      if (!dados.texto) throw new Error("Não foi possível entender o áudio. Tente novamente, mais perto do microfone.");
      const campo = $("#sg-pergunta");
      campo.value = dados.texto;
      campo.focus();
      toast("Confira a pergunta transcrita e clique em Perguntar.");
    } catch (e) {
      toast(e.message, true);
    } finally {
      this.botao(false);
    }
  },
  reamostrar(blocos, de, para) {
    const total = blocos.reduce((n, b) => n + b.length, 0);
    const todos = new Float32Array(total);
    let pos = 0;
    blocos.forEach((b) => { todos.set(b, pos); pos += b.length; });
    if (de === para) return todos;
    const razao = de / para, n = Math.floor(total / razao), saida = new Float32Array(n);
    for (let i = 0; i < n; i++) {  // média da janela: reamostragem com filtro passa-baixa simples
      const ini = Math.floor(i * razao), fim = Math.min(total, Math.floor((i + 1) * razao));
      let soma = 0;
      for (let j = ini; j < fim; j++) soma += todos[j];
      saida[i] = soma / Math.max(1, fim - ini);
    }
    return saida;
  },
  wav(amostras, taxa) {
    const buf = new ArrayBuffer(44 + amostras.length * 2), v = new DataView(buf);
    const txt = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    txt(0, "RIFF"); v.setUint32(4, 36 + amostras.length * 2, true); txt(8, "WAVE"); txt(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, taxa, true);
    v.setUint32(28, taxa * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); txt(36, "data");
    v.setUint32(40, amostras.length * 2, true);
    amostras.forEach((a, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, a)) * 0x7fff, true));
    return new Blob([buf], { type: "audio/wav" });
  },
  botao(gravando, texto) {
    const b = $("#sg-voz");
    b.classList.toggle("recording", gravando);
    b.disabled = Boolean(texto);
    b.setAttribute("aria-pressed", String(gravando));
    b.querySelector(".sg-voz-rotulo").textContent = texto || (gravando ? "Parar" : "Falar");
    b.title = gravando ? "Clique para encerrar a gravação" : "Perguntar por voz";
  },
};
$("#sg-voz").addEventListener("click", () => SgVoz.alternar());
$("#sg-exemplos").innerHTML = SG_EXEMPLOS.map((q) => `<button class="chip" type="button">${esc(q)}</button>`).join("");
$("#sg-exemplos").addEventListener("click", (ev) => {
  if (!ev.target.classList.contains("chip")) return;
  $("#sg-pergunta").value = ev.target.textContent;
  sgPerguntar(ev.target.textContent);
});
views.perguntar = () => $("#sg-pergunta").focus();

/* ============================== ACERVO ============================== */
let sgDocs = [];
let sgFiltroTimer = null;

async function sgCarregarAcervo() {
  try {
    const params = new URLSearchParams({ q: $("#ac-q").value, tipo: $("#ac-tipo").value, origem: $("#ac-origem").value });
    sgDocs = await API.get(`/api/sadgd/documentos?${params}`);
    const tipos = $("#ac-tipo");
    if (tipos.options.length <= 1) {
      const todos = await API.get("/api/sadgd/documentos?limite=2000");
      [...new Set(todos.map((d) => d.tipo_documental).filter(Boolean))].sort().forEach((t) =>
        tipos.insertAdjacentHTML("beforeend", `<option value="${esc(t)}">${esc(t.replace(/_/g, " "))}</option>`));
    }
    $("#ac-contagem").textContent = `${sgDocs.length} documento(s) exibido(s).`;
    $("#ac-tabela tbody").innerHTML = sgDocs.map((d) => {
      const [ocls, olbl] = SG.ORIGEM[d.corpus_origem] || ["", d.corpus_origem];
      return `<tr>
        <td><b>${esc(d.titulo || d.caminho_relativo)}</b><div class="path">${esc(d.caminho_relativo)}</div></td>
        <td>${esc((d.tipo_documental || "—").replace(/_/g, " "))}</td>
        <td>${esc(d.data_documento || "—")}</td>
        <td>${sgBadge(ocls, olbl)}</td>
        <td>${d.situacao_norma === "revogada" ? sgBadge("err", "revogada") : d.situacao_norma ? sgBadge("ok", d.situacao_norma) : statusBadge(d.status, SG.STATUS[d.status])}</td>
        <td>${d.trechos}</td>
        <td class="actions"><a class="btn small" href="${sgArquivo(d.id)}" target="_blank" rel="noopener">Abrir</a>
          <button class="btn small" type="button" data-tl-doc="${d.id}">Linha do tempo</button></td>
      </tr>`;
    }).join("") || `<tr><td colspan="7" class="empty">Nenhum documento encontrado.</td></tr>`;
  } catch (e) { toast(e.message, true); }
}

["#ac-tipo", "#ac-origem"].forEach((s) => $(s).addEventListener("change", sgCarregarAcervo));
$("#ac-q").addEventListener("input", () => { clearTimeout(sgFiltroTimer); sgFiltroTimer = setTimeout(sgCarregarAcervo, 300); });
$("#ac-arquivo").addEventListener("change", () => {
  const f = $("#ac-arquivo").files[0];
  $("#ac-arquivo-nome").textContent = f ? `${f.name} (${formatSize(f.size)})` : "nenhum arquivo";
});

async function sgAcompanharIndexacao() {
  const barra = $("#ac-indexacao");
  barra.classList.remove("hidden");
  for (;;) {
    const st = await API.get("/api/sadgd/indexacao");
    $("#ac-indexacao-texto").textContent = st.executando ? `Indexando: ${st.etapa}…`
      : st.erro ? `Falha: ${st.erro}` : `Concluído: ${st.resumo ? st.resumo.novos : 0} novo(s), ${st.resumo ? st.resumo.trechos : 0} trecho(s); grafo reconstruído.`;
    if (!st.executando) {
      toast(st.erro ? `Falha na indexação: ${st.erro}` : "Documento indexado e disponível na busca.", !!st.erro);
      sgCarregarAcervo();
      setTimeout(() => barra.classList.add("hidden"), 6000);
      return;
    }
    await new Promise((ok) => setTimeout(ok, 1500));
  }
}

$("#ac-upload").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = $("#ac-arquivo").files[0];
  if (!f) { toast("Escolha um arquivo.", true); return; }
  const dados = new FormData();
  dados.append("arquivo", f);
  try {
    const resp = await fetch("/api/sadgd/documentos", { method: "POST", body: dados,
      headers: { "X-Requested-With": "AgenteDocumental" } });
    const corpo = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(corpo.detail || `Erro ${resp.status}`);
    toast(`Arquivo recebido: ${corpo.arquivo}. Indexando…`);
    $("#ac-arquivo").value = "";
    $("#ac-arquivo-nome").textContent = "nenhum arquivo";
    sgAcompanharIndexacao();
  } catch (e) { toast(e.message, true); }
});

document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-tl-doc]");
  if (!b) return;
  showView("linha");
  sgLinhaDoTempo({ documento_id: b.dataset.tlDoc });
});
views.acervo = sgCarregarAcervo;

/* ============================== LINHA DO TEMPO ============================== */
async function sgCarregarProcessos() {
  const sel = $("#tl-processo");
  if (sel.options.length > 1) return;
  try {
    const ps = await API.get("/api/sadgd/processos");
    sel.insertAdjacentHTML("beforeend", ps.map((p) =>
      `<option value="${p.id}">${esc(p.tipo === "contrato" ? `Contrato ${p.chave}` : p.chave)} — ${esc(p.titulo || "")} (${p.documentos} doc.)</option>`).join(""));
  } catch (e) { toast(e.message, true); }
}

async function sgLinhaDoTempo(params) {
  const out = $("#tl-conteudo");
  out.innerHTML = `<div class="panel loading">Montando a linha do tempo…</div>`;
  try {
    const tl = await API.get(`/api/sadgd/linha-do-tempo?${new URLSearchParams(params)}`);
    $("#tl-processo").value = String(tl.processo.id);
    const titulo = Object.fromEntries(tl.eventos.map((e) => [e.documento_id, e.titulo || e.arquivo]));
    const chegam = {};
    tl.relacoes.forEach((r) => { (chegam[r.destino] = chegam[r.destino] || []).push(r); });
    const faseDe = {};
    tl.fases.forEach((f) => f.documentos.forEach((d) => { faseDe[d] = f.nome; }));
    out.innerHTML = `
      <div class="panel">
        <h2>${esc(tl.processo.tipo === "contrato" ? `Contrato ${tl.processo.chave}` : tl.processo.chave)}</h2>
        <div class="sg-fases" aria-label="Fases do processo">${tl.fases.map((f, i) =>
          `<span class="sg-fase sg-fase-${i % 4}">${esc(f.nome)}${f.inicio ? ` · desde ${esc(f.inicio)}` : ""}</span>`).join("")}</div>
        ${tl.inconsistencias.map((i) => `<div class="note warning-note">${esc(i)}</div>`).join("")}
        <ol class="sg-timeline">${tl.eventos.map((e) => `
          <li class="sg-evento">
            <div class="sg-data">${esc(e.data || "s/d")}</div>
            <div class="sg-corpo">
              <div><b>${esc(e.titulo || e.arquivo)}</b> ${sgBadge("", (e.tipo_documental || "").replace(/_/g, " "))}
                ${faseDe[e.documento_id] ? sgBadge("info", faseDe[e.documento_id]) : ""}
                <a class="btn small" href="${sgArquivo(e.documento_id)}" target="_blank" rel="noopener">Abrir</a></div>
              ${(chegam[e.documento_id] || []).map((r) => `<div class="sg-relacao">
                ${sgBadge(SG.RELACAO[r.tipo], r.tipo)} em relação a <i>${esc(titulo[r.origem] || `documento ${r.origem}`)}</i>
                — ${esc(r.justificativa || "")}
                <button class="btn small" type="button" data-trecho="${r.evidencia.trecho_id}">Ver evidência</button></div>`).join("")}
            </div>
          </li>`).join("")}</ol>
      </div>`;
  } catch (e) {
    out.innerHTML = `<p class="empty">${esc(e.message)}</p>`;
  }
}

$("#tl-processo").addEventListener("change", (ev) => { if (ev.target.value) sgLinhaDoTempo({ processo_id: ev.target.value }); });
views.linha = sgCarregarProcessos;

/* ============================== DECISÕES ============================== */
async function sgCarregarDecisoes() {
  try {
    const ds = await API.get("/api/sadgd/decisoes");
    $("#dc-tabela tbody").innerHTML = ds.map((d) => `<tr>
      <td><b>${esc(d.titulo)}</b><div class="small">${esc(d.decisao)}</div></td>
      <td>${esc(d.data)}</td>
      <td>${sgBadge(SG.AVALIACAO[d.avaliacao_resultado], d.avaliacao_resultado)}<div class="small">${esc(d.resultado || "")}</div></td>
      <td class="actions"><button class="btn small gestor-only" type="button" data-dc-resultado="${d.id}">Registrar resultado</button></td>
    </tr>`).join("") || `<tr><td colspan="4" class="empty">Nenhuma decisão registrada.</td></tr>`;
  } catch (e) { toast(e.message, true); }
}

function sgDialogoDecisao(decisao) {
  $("#dc-id").value = decisao ? decisao : "";
  $("#dc-campos-nova").classList.toggle("hidden", !!decisao);
  ["#dc-titulo", "#dc-decisao", "#dc-data"].forEach((s) => { $(s).required = !decisao; });
  $("#dc-dialogo-titulo").textContent = decisao ? "Registrar resultado da decisão" : "Registrar decisão";
  if (!decisao) $("#dc-data").value = new Date().toISOString().slice(0, 10);
  $("#dc-dialogo").showModal();
}

$("#dc-nova").addEventListener("click", () => sgDialogoDecisao(null));
$("#dc-fechar").addEventListener("click", () => $("#dc-dialogo").close());
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-dc-resultado]");
  if (b) sgDialogoDecisao(b.dataset.dcResultado);
});

$("#dc-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const id = $("#dc-id").value;
  try {
    if (id) {
      await API.request("PATCH", `/api/sadgd/decisoes/${id}/resultado`,
        { resultado: $("#dc-resultado").value, avaliacao_resultado: $("#dc-avaliacao").value });
    } else {
      await API.post("/api/sadgd/decisoes", {
        titulo: $("#dc-titulo").value, codigo: $("#dc-codigo").value || null, data: $("#dc-data").value,
        contexto: $("#dc-contexto").value, decisao: $("#dc-decisao").value, fundamentos: $("#dc-fundamentos").value,
        resultado: $("#dc-resultado").value, avaliacao_resultado: $("#dc-avaliacao").value });
    }
    $("#dc-dialogo").close();
    $("#dc-form").reset();
    toast("Decisão salva na memória de decisões.");
    sgCarregarDecisoes();
  } catch (e) { toast(e.message, true); }
});

$("#dc-busca").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#dc-pergunta").value.trim();
  if (q.length < 3) return;
  $("#dc-precedentes").innerHTML = `<div class="panel loading">Buscando precedentes…</div>`;
  try {
    const ps = await API.get(`/api/sadgd/precedentes?${new URLSearchParams({ pergunta: q, k: 3 })}`);
    $("#dc-precedentes").innerHTML = ps.length ? `<div class="panel">${sgPrecedentes(ps)}</div>`
      : `<p class="empty">Não há decisões anteriores semelhantes registradas.</p>`;
  } catch (e) { $("#dc-precedentes").innerHTML = ""; toast(e.message, true); }
});
views.decisoes = sgCarregarDecisoes;
