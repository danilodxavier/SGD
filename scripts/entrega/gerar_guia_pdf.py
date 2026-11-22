"""Gera o PDF do Demo Day: pitch + guia completo (construção, ferramentas e uso do SAD-GD, com telas reais).

As telas vêm de data/video/telas (instância de demonstração com o corpus ACADÊMICO; nenhum dado real).
HTML montado aqui e impresso em PDF pelo Microsoft Edge do sistema (Playwright, channel="msedge").

Uso:  .venv\\Scripts\\python.exe scripts\\entrega\\gerar_guia_pdf.py [--video URL]
Saída: data/entrega/SAD-GD_DemoDay_Pitch_e_Guia.pdf (fora do Git).
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
TELAS = RAIZ / "data" / "video" / "telas"
SAIDA = RAIZ / "data" / "entrega"
IMGS = SAIDA / "img"
GH = "https://github.com/danilodxavier/SGD"
GHB = GH + "/blob/main/"
GHT = GH + "/tree/main/"
KANBAN = "https://github.com/users/danilodxavier/projects/2"
LAN_HTTP = "http://sad.sema.mt.gov.br:8000"
LAN_HTTPS = "https://sad.sema.mt.gov.br"
LAN_IP = "http://172.16.110.45:8000"
VIDEO_PADRAO = GH + "/releases/tag/demoday-2026"


def jpg(nome: str, largura: int = 1600, recorte=None, origem: Path | None = None) -> str:
    """Converte a tela em JPEG (PDF menor) e devolve o caminho file:// para o HTML."""
    IMGS.mkdir(parents=True, exist_ok=True)
    src = origem or TELAS / f"{nome}.png"
    im = Image.open(src).convert("RGB")
    if recorte:
        im = im.crop(recorte)
    if im.width > largura:
        im = im.resize((largura, int(im.height * largura / im.width)), Image.LANCZOS)
    destino = IMGS / f"{nome}{'_r' if recorte else ''}.jpg"
    im.save(destino, quality=86, optimize=True)
    return destino.as_uri()


def link(url: str, texto: str | None = None) -> str:
    return f'<a href="{html.escape(url)}">{html.escape(texto or url)}</a>'


def figura(nome: str, legenda: str, recorte=None, classe: str = "", largura: int = 1600) -> str:
    return (f'<figure class="{classe}"><img src="{jpg(nome, largura, recorte)}" alt="{html.escape(legenda)}">'
            f"<figcaption>{legenda}</figcaption></figure>")


def tabela(cab: list[str], linhas: list[list[str]], classe: str = "") -> str:
    th = "".join(f"<th>{c}</th>" for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in li) + "</tr>" for li in linhas)
    return f'<table class="{classe}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def imagens_auxiliares() -> dict:
    """Diagrama da arquitetura e o apresentador 3D (gerados pelos scripts do vídeo)."""
    sys.path.insert(0, str(RAIZ / "scripts" / "video"))
    import gerar_video_demoday as gv

    v = gv.Video()
    k = next(j for j, c in enumerate(v.cenas) if c["id"] == "arquitetura")
    ini, fim = v.tempos[k]
    q = v.quadro(int((fim - 0.3) * gv.FPS))
    IMGS.mkdir(parents=True, exist_ok=True)
    Image.fromarray(q).crop((405, 66, 1895, 965)).save(IMGS / "arquitetura.png")
    est = v.estado_boneco(0, 0.0)
    est.update(fala=0.0, piscar=0.0, olhar=(0.0, 0.0), giro=0.0, inclina=0.0, sobe=0.0)
    av = v.grande.quadro(**est)
    Image.fromarray(av).save(IMGS / "apresentador.png")
    return {"arquitetura": (IMGS / "arquitetura.png").as_uri(), "apresentador": (IMGS / "apresentador.png").as_uri()}


CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #1c2433; font-size: 10.4pt; line-height: 1.5; margin: 0; }
h1, h2, h3 { color: #0d2c68; line-height: 1.2; }
h1 { font-size: 22pt; margin: 0 0 6mm; border-bottom: 3px solid #007a3d; padding-bottom: 3mm; }
h2 { font-size: 14.5pt; margin: 7mm 0 3mm; }
h3 { font-size: 11.5pt; margin: 5mm 0 2mm; color: #007a3d; }
p { margin: 0 0 2.6mm; text-align: justify; }
a { color: #0b4fb3; text-decoration: none; border-bottom: 1px dotted #0b4fb3; }
.secao { page-break-before: always; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #0d2c68; color: #fff; text-align: left; padding: 2mm 2.4mm; font-weight: 600; }
td { border-bottom: 1px solid #dfe4ee; padding: 1.8mm 2.4mm; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f5f7fb; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #eef2f8; padding: 0 1mm; border-radius: 2px; }
pre { font-family: Consolas, monospace; font-size: 8.6pt; background: #0f1f3d; color: #e8eefc; padding: 3mm 4mm;
      border-radius: 3mm; white-space: pre-wrap; page-break-inside: avoid; }
figure { margin: 3mm 0 5mm; page-break-inside: avoid; text-align: center; }
figure img { max-width: 100%; border: 1px solid #ccd4e2; border-radius: 2mm; box-shadow: 0 1mm 3mm rgba(0,0,0,.12); }
figure.media img { max-height: 115mm; width: auto; }
figure.alta img { max-height: 225mm; width: auto; }
figcaption { font-size: 8.6pt; color: #5a6478; margin-top: 1.5mm; }
.capa { height: 262mm; display: flex; flex-direction: column; justify-content: space-between;
        background: linear-gradient(160deg, #0d2c68 0%, #071d4a 70%); color: #fff; margin: 0; border-radius: 4mm;
        padding: 14mm 14mm 12mm; position: relative; }
.capa h1 { color: #fff; border: none; font-size: 40pt; margin: 0; letter-spacing: .5px; }
.capa .sub { font-size: 15pt; color: #cfe0ff; margin-top: 2mm; }
.capa .faixa { height: 2.2mm; width: 70mm; background: linear-gradient(90deg, #007a3d 62%, transparent 62%, transparent 66%, #f6be00 66%); margin: 6mm 0; border-radius: 2mm; }
.capa .autor { font-size: 11.5pt; line-height: 1.55; max-width: 104mm; }
.capa .autor b { font-size: 15pt; color: #f6be00; }
.capa img.av { position: absolute; right: 10mm; top: 112mm; width: 68mm; }
.capa .evento { display: inline-block; background: #f6be00; color: #0d2c68; font-weight: 700; padding: 1.6mm 4mm; border-radius: 10mm; font-size: 11pt; }
.links { background: #fff; color: #1c2433; border-radius: 4mm; padding: 4mm 5mm; font-size: 9.6pt; }
.links table { margin: 0; font-size: 9.3pt; }
.links td { border-bottom: 1px solid #e6eaf2; padding: 1.5mm 2mm; background: #fff !important; }
.links td:first-child { font-weight: 700; color: #0d2c68; width: 47mm; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin: 3mm 0 4mm; }
.card { border: 1px solid #d7deea; border-left: 2.2mm solid #007a3d; border-radius: 2.5mm; padding: 3mm 4mm; page-break-inside: avoid; background: #fbfcfe; }
.card h3 { margin-top: 0; }
.card.azul { border-left-color: #0d2c68; } .card.amarelo { border-left-color: #f6be00; } .card.roxo { border-left-color: #7846a0; }
.num { display: inline-block; background: #0d2c68; color: #fff; font-weight: 700; border-radius: 50%; width: 7mm; height: 7mm; text-align: center; line-height: 7mm; margin-right: 2mm; font-size: 10pt; }
.destaque { background: #eef7f1; border: 1px solid #b9dcc6; border-radius: 3mm; padding: 3mm 4mm; margin: 3mm 0; page-break-inside: avoid; }
.alerta { background: #fff7df; border: 1px solid #f1d27a; border-radius: 3mm; padding: 3mm 4mm; margin: 3mm 0; page-break-inside: avoid; }
.metricas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin: 3mm 0 5mm; }
.metricas div { background: #eef3fb; border-radius: 3mm; padding: 3mm; text-align: center; }
.metricas b { display: block; font-size: 19pt; color: #0d2c68; } .metricas span { font-size: 8.6pt; color: #4a556b; }
.passos li { margin-bottom: 1.4mm; }
.sumario { columns: 2; font-size: 10pt; } .sumario li { margin-bottom: 1mm; }
.pequeno { font-size: 8.6pt; color: #5a6478; }
"""


def montar(video_url: str, aux: dict) -> str:
    p = []
    # ---------------------------------------------------------------- capa + acesso rápido
    p.append(f"""
<section class="capa">
  <div>
    <span class="evento">Demo Day · 23/11/2026</span>
    <h1 style="margin-top:9mm">SAD-GD</h1>
    <div class="sub">Sistema de Apoio à Tomada de Decisão<br>e Gestão Documental — SEMA-MT</div>
    <div class="faixa"></div>
    <div class="autor"><b>Danilo Xavier</b><br>Analista de Meio Ambiente · Perfil Analista de Sistemas<br>
      Coordenadoria de Infraestrutura e Tecnologia — SEMA-MT<br>Curso de Engenharia de IA · Pitch e guia completo</div>
  </div>
  <img class="av" src="{aux['apresentador']}" alt="Apresentador 3D">
  <div class="links">
    <table>
      <tr><td>▶ Vídeo (4 min 57 s)</td><td>{link(video_url)}</td></tr>
      <tr><td>Repositório GitHub</td><td>{link(GH)}</td></tr>
      <tr><td>Sistema na rede interna (LAN)</td><td>{link(LAN_HTTP)} — hoje, por HTTP<br>{link(LAN_HTTPS)} — com o certificado da STI (voz em todos os computadores)<br>pelo IP: {link(LAN_IP)}</td></tr>
      <tr><td>Kanban (GitHub Projects)</td><td>{link(KANBAN)}</td></tr>
      <tr><td>Documentação</td><td>{link(GHT + 'docs', 'docs/')} · {link(GHB + 'README.md', 'README')} · {link(GHB + 'docs/RELATORIO_TECNICO.md', 'Relatório técnico')} · {link(GHT + 'docs/adr', 'ADRs')}</td></tr>
    </table>
  </div>
</section>""")
    p.append(f"""
<section class="secao">
<h1>Acesso rápido e sumário</h1>
<p>Este documento é o <b>ponto central do pitch</b>: reúne o vídeo, o código, a demonstração e os materiais
complementares, e serve também de <b>guia</b> para conhecer como o sistema foi construído e como usá-lo. Todos os
links são clicáveis.</p>
<h2>Links do pitch</h2>
{tabela(["Item do enunciado", "Onde acessar", "Observação"], [
    ["01 · Apresentação do projeto", "Seções 1 a 3 deste PDF", "Problema, solução, tecnologias, resultados e benefícios"],
    ["02 · Vídeo demonstrativo", link(video_url), "4 min 57 s, 1080p, legendas em português"],
    ["03 · Repositório GitHub", link(GH), "Público: código, testes, CI, 15 ADRs, documentação por fase"],
    ["04 · Demonstração da aplicação", f"{link(LAN_HTTP)}<br>{link(LAN_HTTPS)}<br>{link(LAN_IP)}",
     "Rede interna da SEMA-MT, com login (dados reais protegidos pela LGPD). Fora da rede: vídeo e telas deste guia"],
    ["05 · Recursos complementares", f"{link(GHT + 'docs', 'docs/')} · {link(KANBAN, 'Kanban')} · "
     f"{link(GHT + 'app/application/agentes/prompts', 'prompts dos agentes')}",
     "Documentação, diagramas, evidências, ADRs, prompts, MCP, skills, hooks e agentes (seção 5)"],
])}
<h2>Documentos de referência no repositório</h2>
{tabela(["Documento", "Conteúdo"], [
    [link(GHB + "README.md", "README.md"), "Visão geral, arquitetura, como rodar e avaliar"],
    [link(GHB + "docs/RELATORIO_TECNICO.md", "RELATORIO_TECNICO.md"), "Relatório técnico completo do projeto"],
    [link(GHB + "docs/RELATORIO_ATIVIDADES_E_FERRAMENTAS.md", "RELATORIO_ATIVIDADES_E_FERRAMENTAS.md"), "Cada atividade e ferramenta, com evidências"],
    [link(GHB + "docs/MANUAL_DO_USUARIO.md", "MANUAL_DO_USUARIO.md"), "Uso das telas, perfis e boas práticas"],
    [link(GHB + "docs/MANUAL_TECNICO.md", "MANUAL_TECNICO.md"), "Instalação, operação, backup, rede"],
    [link(GHB + "docs/AVALIACAO.md", "AVALIACAO.md"), "Métricas por versão e protocolo de avaliação"],
    [link(GHB + "docs/MODELOS_IA.md", "MODELOS_IA.md"), "Todos os modelos de IA usados (desenvolvimento e produção)"],
    [link(GHB + "docs/METODOLOGIAS.md", "METODOLOGIAS.md"), "Técnicas e metodologias aplicadas"],
    [link(GHT + "docs/fases", "docs/fases/"), "Planejamento, execução, evidências e aprovação de cada fase (0 a 12)"],
    [link(GHT + "docs/adr", "docs/adr/"), "15 registros de decisão de arquitetura"],
    [link(GHB + "docs/arquitetura/C4.md", "arquitetura/C4.md"), "Diagramas C4 (contexto, contêiner, componente)"],
    [link(GHT + "docs/projeto", "docs/projeto/"), "PMBOK: termo de abertura, EAP, riscos, cronograma, backlog, lições"],
])}
<h2>Sumário</h2>
<ol class="sumario">
<li>Pitch: problema, solução, tecnologias, resultados e benefícios</li>
<li>Percurso de desenvolvimento (fases 0 a 12)</li>
<li>Arquitetura e agentes de IA</li>
<li>Guia de uso com telas</li>
<li>Ferramentas utilizadas no desenvolvimento</li>
<li>Metodologias aplicadas</li>
<li>Avaliação e resultados</li>
<li>Segurança e LGPD</li>
<li>Instalação, publicação na rede e operação</li>
<li>Limitações e evolução</li>
<li>Como o vídeo e este guia foram produzidos</li>
</ol>
</section>""")
    # ---------------------------------------------------------------- 1. pitch
    p.append(f"""
<section class="secao">
<h1>1. Pitch</h1>
<div class="cards">
 <div class="card"><h3>O problema</h3><p>A SEMA-MT gerencia muitos contratos ao mesmo tempo — vigências, aditivos,
 apostilamentos, notificações, relatórios de fiscalização — sob normas que mudam, são revogadas e às vezes se
 contradizem. Achar a cláusula certa leva horas, e decidir com base em documento desatualizado expõe a gestão a
 riscos jurídicos e financeiros.</p></div>
 <div class="card azul"><h3>A necessidade</h3><p>Gerenciar e fiscalizar contratos de forma <b>inteligente, ágil e
 assertiva</b>, e apoiar os gestores a tomar as melhores decisões, garantindo que o investimento retorne em
 <b>vantajosidade e benefícios</b> para a SEMA e para todos os contribuintes.</p></div>
 <div class="card amarelo"><h3>A solução</h3><p>O <b>SAD-GD</b> lê o acervo e responde qualquer pergunta citando
 <b>documento, página e trecho literal</b> (F1), e apoia a decisão (F2) com uma equipe de <b>agentes de IA
 especialistas</b> — Procurador, Advogado, Controlador-Geral, Fiscal de Contrato, Gestor Público, Analista
 Administrativo — consolidada por um relator. <b>O sistema sugere; o gestor decide.</b></p></div>
 <div class="card roxo"><h3>As tecnologias</h3><p>Multiagentes com <b>LangGraph</b>; RAG híbrido (BM25 + bge-m3 +
 reranker); LLM local <b>Qwen 2.5 7B</b> no Ollama; voz com <b>Whisper</b> local; OCR com <b>Tesseract</b>; FastAPI +
 SQLite/sqlite-vec; desenvolvido com <b>Claude Code</b> (Claude Opus) em 13 fases, com GitHub, CI e Kanban. Tudo
 gratuito e executado na rede da SEMA.</p></div>
</div>
<h2>Resultados medidos</h2>
<div class="metricas">
 <div><b>0,965</b><span>Recall@5 da busca (meta ≥ 0,90)</span></div>
 <div><b>0,964</b><span>Fidelidade às fontes (meta ≥ 0,90)</span></div>
 <div><b>0%</b><span>Alucinação numérica (meta ≤ 5%)</span></div>
 <div><b>1,00</b><span>Classificação do tipo documental</span></div>
 <div><b>1,00</b><span>Precedentes encontrados (Recall@3)</span></div>
 <div><b>R$ 0</b><span>Custo por consulta (tudo local)</span></div>
</div>
<p>Na rede interna, com o acervo real, <b>11 de 12 perguntas reais foram respondidas em menos de 5 segundos</b>
graças às fichas de contrato pré-processadas (ADR-015), e a decisão (F2) de um caso real caiu de 334 s para 78 s após
a otimização do contexto (Fase 12).</p>
<h2>Benefícios para a SEMA</h2>
<div class="cards">
 <div class="card"><h3>Velocidade e inteligência documental</h3><p>Respostas em segundos, com a fonte na mão;
 linha do tempo de cada contrato; detecção de conflitos entre documentos e de normas revogadas.</p></div>
 <div class="card azul"><h3>Fiscalização mais efetiva</h3><p>Fichas de contrato com vigência, valores, aditivos,
 pendências e vencimentos — o fiscal sabe o que conferir e quando.</p></div>
 <div class="card amarelo"><h3>Decisões seguras e transparentes</h3><p>Recomendação com alternativas, prós e
 contras, riscos com mitigação, base legal, precedentes (inclusive os negativos), divergências, lacunas e nível de
 confiança — e todas as fontes citadas.</p></div>
 <div class="card roxo"><h3>Memória institucional e LGPD</h3><p>Decisões anteriores viram precedentes; tudo roda na
 rede da SEMA, sem enviar dados para fora; perfis de acesso e trilha de auditoria.</p></div>
</div>
<div class="alerta"><b>Escopo e potencial.</b> O escopo atual foi reduzido pela insuficiência de recursos de
hardware, principalmente a <b>GPU</b> (GTX 1660 SUPER, 6 GB, compartilhada entre o LLM e o reranker). A arquitetura,
porém, é geral: o sistema pode responder a <b>qualquer pergunta</b>, desde que o material de origem esteja indexado.
Com uma GPU mais robusta, o mesmo sistema cresce para todo o acervo da Secretaria (normas, processos e pareceres) e
reduz o tempo da decisão.</div>
</section>""")
    # ---------------------------------------------------------------- 2. percurso
    fases = [
        ["0", "Auditoria do app v1", "Relatório manter/refatorar/excluir; backup antes de excluir (tag e branch)", "16/11"],
        ["1", "Iniciação e planejamento", "Termo de abertura, requisitos, EAP, riscos, cronograma, backlog", "16/11"],
        ["2", "Arquitetura", "C4, ADR-003 a 013, modelo de dados e do grafo, especificação dos agentes", "16/11"],
        ["3", "Infraestrutura local", "Clean Architecture, CI no GitHub Actions, Ollama e Tesseract portáteis", "16/11"],
        ["4", "Ingestão e base de conhecimento", "Corpus acadêmico (69 públicos + 117 sintéticos), OCR, chunking por artigo/cláusula, bge-m3", "16/11"],
        ["5", "RAG + golden set + baseline", "Busca híbrida + reranker (R@5 0,965); 100+ perguntas; Qwen 2.5 7B escolhido", "16/11"],
        ["6", "Linha do tempo e relações", "Grafo documental: aditivo, revogação, suspensão, retomada, contradição; vigência", "16/11"],
        ["7", "Sistema multiagentes", "Roteador, verificador, especialistas, relator, LangGraph, LGPD, auditoria, API", "16/11"],
        ["8", "Apoio à decisão (F2)", "Memória de decisões e precedentes (R@3 1,00); recomendação com 6 elementos", "17/11"],
        ["9", "MVP completo", "Telas Perguntar, Acervo, Linha do tempo, Decisões, Painel; perfis; upload; E2E no Edge", "17/11"],
        ["10", "Otimização e avaliação final", "Cache semântico, juiz LLM calibrado, fidelidade 0,964 adjudicada", "17/11"],
        ["11", "Entrega acadêmica", "Relatório técnico, manuais, F2 opcional no Gemini (corpus acadêmico), vídeo", "17/11"],
        ["12", "Implantação na rede interna", "Acervo real, chat por texto e voz (Whisper local), fichas de contrato, publicação na LAN", "21–22/11"],
    ]
    p.append(f"""
<section class="secao">
<h1>2. Percurso de desenvolvimento</h1>
<p>O projeto foi conduzido como <b>engenharia de IA com governança</b>: cada fase funcionou como um sprint Scrum,
com planejamento, execução, evidências e um documento próprio em {link(GHT + 'docs/fases', 'docs/fases/')}. A
<b>revisão do sprint foi a aprovação explícita do responsável</b> ("Aprovado, siga para a Fase X"); nada foi excluído
sem aprovação e sem backup. O backlog virou 52 issues no {link(KANBAN, 'Kanban do GitHub Projects')}.</p>
{tabela(["Fase", "Nome", "Entregas principais", "Data (2026)"], fases)}
<h3>Regras invioláveis que guiaram o trabalho</h3>
<ul class="passos">
<li><b>Aprovação a cada fase</b> e <b>nada deletado sem aprovação</b> (backup <code>backup/pre-reestruturacao</code>, <code>backup/pre-limpeza-v1</code>).</li>
<li><b>Somente ferramentas gratuitas</b>, preferencialmente locais e open source (ADR-001).</li>
<li><b>Credenciais nunca no código ou no chat</b>: <code>.env</code> fora do Git, Git Credential Manager, varredura gitleaks no CI.</li>
<li><b>Continuidade total</b> em Markdown: <code>CLAUDE.md</code>, <code>docs/STATUS.md</code> (checkpoint), <code>docs/CONTINUIDADE.md</code>.</li>
<li><b>Rastreabilidade de IA</b>: todo modelo em <code>docs/MODELOS_IA.md</code>; toda técnica em <code>docs/METODOLOGIAS.md</code>.</li>
<li><b>LGPD</b>: dados reais só locais; o agente de desenvolvimento não lê conteúdo real (apenas contagens agregadas).</li>
<li><b>O sistema sugere, a gestão decide</b>: toda recomendação traz fundamentação, fontes, confiança e riscos.</li>
</ul>
<div class="figura-kanban">{figura('61_github_kanban', 'Kanban no GitHub Projects: 52 issues do backlog, todas concluídas (Done).', classe='media')}</div>
{figura('63_github_adr', 'Decisões de arquitetura versionadas em docs/adr (15 ADRs).', classe='media')}
</section>""")
    # ---------------------------------------------------------------- 3. arquitetura
    agentes = [
        ["Roteador", "Classifica a pergunta: F1 simples, F1 complexa ou F2 (decisão); regras + LLM só quando necessário", "roteador.v1.md"],
        ["Analista de Linha do Tempo", "Reconstrói a cronologia e as relações entre documentos (aditivo, revogação, ruptura…)", "analista_linha_do_tempo.v1.md"],
        ["Verificador de Fontes", "Anti-alucinação: remove frase sem trecho que a sustente e número que não está na fonte", "verificador_fontes.v1.md"],
        ["Relator", "Consolida pareceres: consensos, divergências, alternativas, riscos, confiança", "relator.v3.md"],
        ["Procurador do Estado", "Legalidade, constitucionalidade, riscos jurídicos para o ente público", "procurador_estado.v1.md"],
        ["Advogado", "Interpretação contratual, direitos e obrigações, litígio", "advogado.v1.md"],
        ["Controlador-Geral", "Conformidade, controle interno, recomendações de TCE/TCU/CGU", "controlador_geral.v1.md"],
        ["Fiscal de Contrato", "Execução, prazos, entregas, penalidades, aditivos (Lei 14.133/2021)", "fiscal_contrato.v1.md"],
        ["Gestor Público", "Viabilidade, impacto orçamentário, interesse público, oportunidade e conveniência", "gestor_publico.v1.md"],
        ["Analista Administrativo", "Fluxo processual, instrução documental, requisitos formais", "analista_administrativo.v1.md"],
        ["Analista Orçamentário-Financeiro", "Perfil proposto: dotação, empenho, impacto financeiro", "analista_orcamentario_financeiro.v1.md"],
        ["Especialista em Licitações", "Perfil proposto: modalidade, pesquisa de preços, vantajosidade", "especialista_licitacoes.v1.md"],
    ]
    adrs = [
        ["001", "Execução na máquina local, somente ferramentas gratuitas"], ["002", "Corpus acadêmico separado dos dados reais"],
        ["003", "Framework multiagentes: LangGraph (× CrewAI, matriz ponderada)"], ["004", "LLMs, abstração de provedor e roteamento por custo"],
        ["005", "Embeddings e reranker locais (bge-m3, bge-reranker-v2-m3)"], ["006", "Armazenamento único em SQLite: relacional + FTS5 + sqlite-vec + grafo"],
        ["007", "Leitura de documentos e OCR (Tesseract)"], ["008", "Frontend HTML/CSS/JS servido pelo FastAPI (Vercel adiada)"],
        ["009", "Observabilidade local: tabela de consultas + Arize Phoenix"], ["010", "Versão do Python e gestão de dependências"],
        ["011", "Estratégia de avaliação (métricas, juiz e golden set)"], ["012", "RAG avançado + prompts + few-shot, sem ajuste fino de LLM"],
        ["013", "Clean Architecture e migração incremental (strangler fig)"], ["014", "Perguntas por voz com transcrição local (faster-whisper)"],
        ["015", "Fichas de contrato pré-processadas para respostas em segundos"],
    ]
    p.append(f"""
<section class="secao">
<h1>3. Arquitetura e agentes de IA</h1>
<figure><img src="{aux['arquitetura']}" alt="Arquitetura"><figcaption>Fluxo de uma pergunta: roteador (LangGraph) →
busca híbrida/fichas ou especialistas → relator → verificador de fontes → resposta com documento, página e trecho.
</figcaption></figure>
<h3>Camadas (Clean Architecture)</h3>
<p><b>Domínio</b> (regras puras: hierarquia normativa Constituição &gt; Lei &gt; Decreto &gt; IN &gt; Orientação, vigência,
relações entre documentos) · <b>Aplicação</b> (ingestão, busca, fichas, linha do tempo, agentes, decisões) ·
<b>Infraestrutura</b> (SQLite + FTS5 + sqlite-vec, Ollama, Tesseract, Whisper, leitores de PDF/DOCX/XLSX) ·
<b>Interfaces</b> (API FastAPI e telas). A regra de dependência é verificada por teste automático de AST. Provedores
são <b>portas e adaptadores</b>: trocar Ollama por Gemini, ou Tesseract por Windows OCR, não exige reescrever código.</p>
<h3>Agentes (prompts versionados em {link(GHT + 'app/application/agentes/prompts', 'app/application/agentes/prompts')})</h3>
{tabela(["Agente", "Escopo", "Prompt"], agentes)}
<p>Cada agente tem prompt de sistema versionado, saída em <b>JSON estruturado</b> (parecer, fundamentação, citações,
confiança 0–1, riscos, lacunas) e critério de acionamento: só os especialistas relevantes são chamados (economia de
tokens e tempo). Regras comuns a todos ficam em <code>_regras_comuns.v2.md</code>.</p>
<h3>Decisões de arquitetura (ADRs)</h3>
{tabela(["ADR", "Decisão"], adrs)}
</section>""")
    # ---------------------------------------------------------------- 4. guia de uso
    p.append(f"""
<section class="secao">
<h1>4. Guia de uso com telas</h1>
<div class="destaque">As telas abaixo são do sistema real, numa instância de demonstração com o <b>corpus
acadêmico</b> (atos públicos e documentos sintéticos de um estado fictício). Nenhum dado real da SEMA aparece neste
guia nem no vídeo.</div>
<h2>4.1 Formas de acesso</h2>
{tabela(["Forma", "Como", "Observações"], [
    ["Aplicação na estação servidora", "<code>start.bat</code> (ou tarefa \"SAD-GD\" no logon, que inicia Ollama + servidor)", "Abre o sistema no navegador da própria estação"],
    ["Web na rede interna", f"{link(LAN_HTTP)} (atual) · {link(LAN_HTTPS)} (com certificado da STI) · {link(LAN_IP)}", "Qualquer computador da SEMA; firewall só para faixas internas; nome desconhecido recebe 403"],
    ["Texto", "Caixa \"Digite ou fale sua pergunta…\" + botão Perguntar", "Exemplos clicáveis abaixo da caixa"],
    ["Voz", "Botão <b>Falar</b> → falar → <b>Parar</b>; o texto aparece para conferência", "Transcrição local (Whisper). Em outros computadores o navegador só libera o microfone com HTTPS"],
    ["Celular e tablet", "Mesmo endereço, pelo navegador", "Layout responsivo; menu reorganizado"],
])}
{figura('00_login', 'Tela de login: cada usuário tem perfil (Administrador, Gestor ou Consulta).', classe='media')}
<h2>4.2 Painel</h2>
<p>Resumo do acervo: documentos, trechos indexados, vetores (bge-m3), processos reconstruídos, relações entre
documentos, contradições detectadas, normas revogadas e decisões na memória; consultas registradas com latência
média; e a última indexação. O administrador pode <b>Atualizar índice</b>.</p>
{figura('01_painel', 'Painel com os indicadores do acervo e das consultas.', classe='media')}
<h2>4.3 Perguntar por texto (F1)</h2>
<ol class="passos">
<li>Abra <b>Perguntar</b>, digite a pergunta (ou clique num exemplo) e clique em <b>Perguntar</b>.</li>
<li>A resposta mostra selos: tipo (Fato documental, Conflito, Informação ausente, Inferência), <b>confiança</b> e
tipo de pergunta; o tempo de resposta aparece no canto.</li>
<li>Cada afirmação traz a referência <b>[T…]</b> do trecho; em <b>Fontes citadas</b> há o documento, o dispositivo
(cláusula, artigo), a página e o trecho literal.</li>
<li><b>Ver trecho</b> abre o texto exato; <b>Abrir documento</b> abre o arquivo original (que nunca é alterado).</li>
</ol>
{figura('03_f1_resposta', 'Valor global do contrato: o sistema encontrou um relatório com valor divergente e mostrou o CONFLITO com as duas fontes, em vez de escolher uma.', classe='media')}
{figura('04_f1_trecho', '"Ver trecho": o texto literal da cláusula, com data e arquivo de origem.', classe='media')}
{figura('05b_f1_prazo', 'Vigência pela ficha do contrato: prorrogação, termo aditivo, rescisão e lacunas — em 0,2 s.', classe='media')}
{figura('05_f1_vigencia', 'Hierarquia e vigência: o decreto revogado é identificado com o ato que o revogou.', classe='media')}
{figura('05c_f1_sequencia', 'Sequência de eventos do contrato: suspensão, retomada e prorrogação, cada uma com sua fonte.', classe='media')}
{figura('06_f1_sem_evidencia', 'Sem evidência no acervo: "Não localizei essa informação nos documentos disponibilizados." Nada é inventado.', classe='media')}
<h2>4.4 Perguntar por voz</h2>
<ol class="passos">
<li>Clique em <b>Falar</b> (o botão vira <b>Parar</b>, em vermelho) e faça a pergunta.</li>
<li>Clique em <b>Parar</b>: o áudio é convertido em WAV 16 kHz no navegador e transcrito <b>no servidor da SEMA</b>
(faster-whisper). O áudio não é gravado em disco nem enviado para fora.</li>
<li>O texto aparece na caixa para <b>conferência</b>; números falados viram a forma escrita ("contrato doze barra dois
mil e vinte e três" → "contrato nº 12/2023"). Clique em <b>Perguntar</b>.</li>
</ol>
{figura('07_voz_gravando', 'Gravando a pergunta (botão Parar).', classe='media')}
{figura('08_voz_transcrita', 'Pergunta transcrita localmente, pronta para conferência.', classe='media')}
{figura('09_voz_resposta', 'Resposta à pergunta falada em 3,6 s, com as fontes.', classe='media')}
<h2>4.5 Apoio à decisão (F2)</h2>
<p>Perguntas de decisão ("devo…", "é recomendável…") acionam os agentes especialistas. A resposta traz a
<b>recomendação sugerida</b> e os seis elementos obrigatórios (alternativas, riscos, base legal, precedentes,
confiança e aviso), além de consensos, divergências, lacunas, pareceres por agente e as fontes. Precedentes com
resultado negativo geram alerta: "avaliar o que deu errado antes de repetir a solução".</p>
{figura('13_f2_inteira', 'Decisão completa: "Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?" — recomendação, alternativas com prós e contras, riscos com probabilidade, impacto e mitigação, precedentes, consensos, divergências, lacunas, pareceres e fontes. O sistema sugere; o gestor decide.', classe='alta', largura=1500)}
<h2>4.6 Linha do tempo</h2>
<p>Escolha um processo ou contrato: o sistema mostra as fases (execução, interrupção, retomada), cada documento em
ordem cronológica e a relação com o anterior (contrato, suspensão, retomada, aditivo, revogação, contradição), com o
botão <b>Ver evidência</b>.</p>
{figura('20_linha_do_tempo', 'Linha do tempo do Contrato 031/2023: contrato → ordem de suspensão → ordem de reinício → termo aditivo.', classe='media')}
<h2>4.7 Acervo e envio de documentos</h2>
<p>Lista todos os documentos com tipo, data, origem, situação e número de trechos, com filtros. Perfis Gestor e
Administrador podem <b>Escolher arquivo → Enviar e indexar</b> (PDF, DOCX, XLSX, ODT, imagens…): o servidor lê, faz
OCR se for digitalizado, divide por artigo/cláusula, gera vetores, atualiza o grafo e as fichas.</p>
{figura('10_acervo', 'Acervo com filtros por título/número, tipo e origem.', classe='media')}
<h2>4.8 Memória de decisões</h2>
<p>Registre as decisões da gestão e, depois, o resultado (positivo, negativo, neutro). Elas viram
<b>precedentes</b> nas próximas decisões — informam, não vinculam. A busca de precedentes encontra situações
parecidas.</p>
{figura('31_precedentes', 'Busca de precedentes para "prorrogação de contrato de vigilância com advertências".', classe='media')}
<h2>4.9 Administração, acessibilidade e celular</h2>
{figura('40_usuarios', 'Usuários: criar contas com senha temporária, definir perfil, redefinir senha e desativar.', classe='media')}
{figura('41_configuracoes', 'Configurações: diretório documental, indexação, verificação do sistema e OCR.', classe='media')}
{figura('42_acessibilidade', 'Página de acessibilidade (atalhos de teclado, alto contraste, tamanho da fonte, VLibras).', classe='media')}
<div class="cards">
 <figure><img src="{jpg('50_celular_painel', 700)}" style="max-height:120mm"><figcaption>Celular: painel.</figcaption></figure>
 <figure><img src="{jpg('51_celular_resposta', 700)}" style="max-height:120mm"><figcaption>Celular: resposta com fontes.</figcaption></figure>
</div>
</section>""")
    # ---------------------------------------------------------------- 5. ferramentas
    ferr_ia = [
        ["Claude Code (app desktop, aba Code)", "Agente de engenharia: auditoria, planejamento, arquitetura, código, testes, documentação, vídeo e este PDF", "Todas"],
        ["Claude Opus 5.5 (<code>claude-opus-5-5</code>)", "Modelo do Claude Code; atuou como engenheiro de IA, arquiteto e gerente de projeto sob regras explícitas", "Todas"],
        ["<code>CLAUDE.md</code> (prompt mestre)", "Regras invioláveis, decisões vigentes, convenções de pastas e particularidades do Windows; lido em toda sessão", "Todas"],
        ["Memória persistente", "Fatos entre sessões (ex.: responder em português; testar com banco isolado)", "Todas"],
        ["Skills", "Roteiros empacotados disponíveis na sessão: <code>engineering:architecture</code> (ADRs), <code>code-review</code>, <code>testing-strategy</code>, <code>documentation</code>, <code>debug</code>, <code>pdf</code>, <code>docx</code>, <code>pptx</code>, <code>xlsx</code>", "2–12"],
        ["Plugins", "<code>engineering</code> (skills e conectores de engenharia) e <code>cowork-plugin-management</code>", "2–12"],
        ["Subagentes", "Exploração e pesquisa em paralelo (Explore, general-purpose) sem poluir o contexto principal", "0–12"],
        ["Hooks e permissões", "Execução sob o modo de permissão escolhido pelo responsável; ações destrutivas e externas sempre confirmadas; nenhum hook personalizado foi necessário", "Todas"],
        ["Conectores MCP", "Navegador embutido (validação visual das telas), Claude in Chrome, terminal, registro de conectores MCP, tarefas agendadas, Claude Docs; Google Drive/Gmail/Agenda disponíveis, não usados com dados do projeto; GitHub/Slack/Notion do plugin exigem OAuth (GitHub operado por <code>git</code> + <code>gh</code>)", "3–12"],
        ["Tarefas, capítulos e artefatos", "Lista de tarefas visível ao responsável, capítulos da sessão e resumo de encerramento a cada entrega", "11–12"],
    ]
    ferr_gestao = [
        ["Git + GitHub", f"Repositório público {link(GH, 'danilodxavier/SGD')}; GitHub Flow; Conventional Commits; tags e branches de backup"],
        ["GitHub Actions (CI)", "A cada push: gitleaks (segredos), ruff (lint), pytest no Windows, portão de cobertura, regressão de qualidade da busca; falhas viram anotações públicas"],
        ["GitHub Projects (Kanban)", f"{link(KANBAN, 'Project #2')}: 52 issues com labels por fase/épico/prioridade, milestones e comentário de evidência"],
        ["GitHub CLI (<code>gh</code>) portátil", "Criação do backlog (<code>scripts/github/criar_backlog.ps1</code>) e consulta do CI; token no Gerenciador de Credenciais do Windows"],
        ["Git Credential Manager", "Push sem credenciais no código ou no chat"],
        ["Markdown", "Toda a documentação, fases, ADRs, manuais, prompts dos agentes, STATUS e CONTINUIDADE"],
    ]
    ferr_sis = [
        ["Python 3.15 + venv", "Backend, scripts de ingestão, avaliação e produção de mídia"],
        ["FastAPI + Uvicorn", "API e servidor web (HTTP na porta 8000; HTTPS na 443 com o certificado da STI)"],
        ["SQLite + FTS5 + sqlite-vec", "Banco único: relacional, busca textual BM25, vetores e grafo documental (ADR-006)"],
        ["LangGraph + langchain-core", "Orquestração multiagentes (fan-out dos especialistas com Send)"],
        ["Ollama (portátil)", "Execução local do Qwen 2.5 7B (Q4_K_M) na GPU de 6 GB; cache de prefixo; keep-alive"],
        ["sentence-transformers + transformers + PyTorch CUDA", "bge-m3 (embeddings 1024 dims) e bge-reranker-v2-m3 na GPU"],
        ["faster-whisper + CTranslate2", "Transcrição de voz local na CPU (Whisper small int8)"],
        ["Tesseract 5 (<code>por</code>)", "OCR de PDFs digitalizados e imagens (CER 0,09%)"],
        ["pypdf, pypdfium2, python-docx, openpyxl, xlrd, olefile, defusedxml", "Leitura segura de PDF, DOCX, XLSX/XLS, DOC e formatos legados"],
        ["scikit-learn, jsonschema, pydantic", "Métricas, validação dos JSON dos agentes e modelos de dados"],
        ["RAGAS, Arize Phoenix, OpenTelemetry", "Avaliação de RAG e observabilidade local (ADR-009, ADR-011)"],
        ["HTML/CSS/JS + padrão visual do Governo de MT", "Interface acessível (alto contraste, A+/A−, atalhos, VLibras), sem framework (ADR-008)"],
        ["pytest, pytest-cov, ruff", "451 testes automatizados, cobertura e lint"],
        ["Playwright + Microsoft Edge", "Testes ponta a ponta no navegador real e captura das telas deste guia"],
        ["Google Gemini (plano gratuito) — opcional", "F2 somente com corpus acadêmico anonimizado; desligado na rede da SEMA"],
    ]
    modelos = [
        ["Qwen 2.5 7B Instruct (Q4_K_M)", "Ollama, local", "Redação, especialistas, relator", "Escolhido no benchmark (exatidão 0,846 × 0,718 do Llama)"],
        ["BAAI/bge-m3", "Local", "Embeddings multilíngues", "5.691 vetores; R@5 0,965 com o reranker"],
        ["BAAI/bge-reranker-v2-m3", "Local", "Reranking", "R@5 0,748 → 0,965"],
        ["Whisper small (faster-whisper)", "Local, CPU", "Voz → texto", "Áudio não sai da máquina"],
        ["Tesseract 5 + por", "Local", "OCR", "CER 0,09%"],
        ["Llama 3.1 8B Instruct", "Ollama, local", "Juiz de fidelidade (avaliação)", "Outra família; calibrado (κ 0,71) e adjudicado"],
        ["Qwen 2.5 3B", "Ollama, local", "Avaliado e rejeitado", "Recusa correta 0,25; pareceres vazios"],
        ["Gemini 3.5 Flash-Lite", "Nuvem, gratuito", "F2 opcional (acadêmico)", "p95 100 s; desligado com dados reais"],
        ["Claude Opus 5.5", "Anthropic (Claude Code)", "Desenvolvimento", "Engenharia, documentação, vídeo e PDF"],
        ["Microsoft Daniel (voz neural pt-BR)", "Windows, local", "Narração dos vídeos", "Mesma voz nos dois vídeos"],
    ]
    p.append(f"""
<section class="secao">
<h1>5. Ferramentas utilizadas no desenvolvimento</h1>
<p>Todas as ferramentas são <b>gratuitas</b> (ou de uso já disponível ao responsável, no caso do Claude Code), e o
sistema roda <b>localmente</b> na rede da SEMA. Onde uma ferramenta sugerida não foi usada, o motivo está registrado
(ex.: Vercel e VPS Oracle adiadas pela ADR-001/008 — exigiriam expor o servidor; o frontend é servido pelo FastAPI).</p>
<h2>5.1 Desenvolvimento assistido por IA (prompts, MCP, skills, hooks, agentes)</h2>
{tabela(["Recurso", "Uso no projeto", "Fases"], ferr_ia)}
<div class="destaque"><b>Como o Claude Code trabalhou:</b> lia o <code>CLAUDE.md</code> e o <code>docs/STATUS.md</code>
no início de cada sessão, planejava a fase, implementava com testes, registrava evidências em <code>docs/fases/</code>
e parava para aprovação. Exemplos desta entrega: as telas foram capturadas com o Edge numa instância isolada com o
corpus acadêmico; um defeito real foi encontrado e corrigido durante a gravação (a fala "contrato doze barra dois mil e
vinte e três" não era reconhecida como número de contrato — agora é normalizada para "nº 12/2023", com testes); e a
falha do CI (dependência <code>onnxruntime</code> inexistente para o Python 3.15) foi diagnosticada pelos logs do GitHub
Actions e corrigida.</div>
<h2>5.2 Gestão, versionamento e documentação</h2>
{tabela(["Ferramenta", "Uso"], ferr_gestao)}
{figura('60_github_repo', 'Repositório público no GitHub (63 commits, código, testes, documentação).', classe='media')}
<h2>5.3 Sistema: backend, IA, interface e qualidade</h2>
{tabela(["Ferramenta / biblioteca", "Uso"], ferr_sis)}
<h2>5.4 Modelos de IA</h2>
{tabela(["Modelo", "Onde roda", "Função", "Evidência"], modelos)}
</section>""")
    # ---------------------------------------------------------------- 6. metodologias
    met = [
        ["PMBOK 7", "Termo de abertura, EAP, cronograma, riscos, partes interessadas, lições aprendidas", "docs/projeto/"],
        ["Scrum", "Cada fase = sprint; revisão = aprovação do responsável; retrospectiva no documento da fase", "docs/fases/"],
        ["Kanban", "52 issues no GitHub Projects com evidência em cada item", "Project #2"],
        ["CRISP-DM / MLOps / LLMOps", "Ciclo de dados (corpus com proveniência), modelagem, avaliação contínua no CI", "corpus/, avaliacao/"],
        ["Clean Architecture + SOLID", "Camadas domínio/aplicação/infraestrutura/interfaces; regra de dependência testada por AST", "app/"],
        ["TDD", "Regras críticas (hierarquia normativa, vigência, verificador, fichas, voz) escritas com testes", "tests/"],
        ["C4 + ADR", "Diagramas de contexto/contêiner/componente; 15 decisões registradas", "docs/arquitetura, docs/adr"],
        ["Conventional Commits + GitHub Flow", "feat/fix/perf/docs/ci; tags de backup antes de mudanças destrutivas", "histórico do Git"],
        ["Engenharia de requisitos", "Requisitos RF/RNF com critérios de aceite verificáveis e matriz de rastreabilidade", "docs/projeto/RASTREABILIDADE.md"],
        ["RAG avançado + engenharia de prompt + few-shot", "Sem ajuste fino de LLM (ADR-012); precedentes como few-shot", "ADR-012"],
        ["Avaliação científica", "Golden set 100+ perguntas (validação 30% / teste 70%), juiz calibrado, adjudicação humana", "docs/AVALIACAO.md"],
    ]
    p.append(f"""
<section class="secao">
<h1>6. Metodologias aplicadas</h1>
{tabela(["Metodologia", "Como foi aplicada", "Evidência"], met)}
<h1 style="margin-top:9mm">7. Avaliação e resultados</h1>
{tabela(["Métrica (conjunto de teste)", "Meta", "Resultado", "Situação"], [
    ["Recall@5 da busca", "≥ 0,90", "0,965", "✅"],
    ["Fidelidade às fontes (faithfulness)", "≥ 0,90", "0,964 (adjudicada)", "✅"],
    ["Alucinação numérica / por frase", "≤ 5%", "0% / 5,4%", "✅ / ⚠️ marginal"],
    ["Classificação do tipo documental", "≥ 0,85", "1,00", "✅"],
    ["Relações entre documentos (F1)", "≥ 0,85", "1,00 sintético; 10/10 oficiais públicas", "✅ com ressalva"],
    ["Roteamento das perguntas", "≥ 0,90", "0,935", "✅"],
    ["Precedentes (Recall@3)", "≥ 0,80", "1,00", "✅"],
    ["Recomendação com 6 elementos (RF-20)", "100%", "100%", "✅"],
    ["Perguntas reais em menos de 5 s (Fase 12)", "meta de 10 s", "11 de 12", "✅"],
    ["Decisão real (F2) na GPU local", "—", "334 s → 78 s", "melhorado"],
    ["Custo por consulta", "gratuito", "R$ 0", "✅"],
])}
<p>Evolução da qualidade: o app legado (v1) tinha Recall@5 de 0,431 e exatidão de 0,217; a v2 chegou a 0,965 e 0,795
sob o mesmo protocolo. Métricas sintéticas perfeitas foram sempre conferidas no corpus público antes de qualquer
conclusão; a métrica do juiz LLM só foi publicada após calibração (respostas corrompidas de propósito) e adjudicação
humana das discordâncias. Detalhes em {link(GHB + 'docs/AVALIACAO.md', 'docs/AVALIACAO.md')}.</p>
<h1 style="margin-top:9mm">8. Segurança e LGPD</h1>
<ul class="passos">
<li><b>Execução local</b>: documentos, perguntas, áudio e respostas ficam na rede da SEMA (<code>AI_ALLOW_REMOTE=false</code>).</li>
<li><b>Perfis de acesso</b> (Administrador, Gestor, Consulta), senha temporária e troca obrigatória.</li>
<li><b>Auditoria</b>: cada consulta registrada (com hash da pergunta) e numerada na resposta.</li>
<li><b>Pseudonimização</b> de nomes e CPF antes de qualquer envio remoto (usado apenas no corpus acadêmico).</li>
<li><b>Rede</b>: servidor só no IP da LAN, firewall de entrada para faixas internas, lista de nomes permitidos (host desconhecido → 403), HTTPS com certificado da STI.</li>
<li><b>Defesa em profundidade</b>: confinamento de arquivos, CSP, validação de upload, documentos originais nunca alterados, gitleaks no CI.</li>
<li><b>Desenvolvimento</b>: o agente de IA não lê conteúdo real — só contagens e métricas agregadas; a foto do apresentador e o vídeo não vão para o Git.</li>
</ul>
</section>""")
    # ---------------------------------------------------------------- 9-11
    p.append(f"""
<section class="secao">
<h1>9. Instalação, publicação na rede e operação</h1>
<pre>instalar.bat                      &lt;- cria o .venv, instala dependências, Ollama e Tesseract portáteis, modelos
start.bat                         &lt;- inicia o sistema na estação (abre o navegador)
scripts\\rede\\instalar_certificado.py --pfx &lt;arquivo da STI&gt;   &lt;- certificado para HTTPS
scripts\\rede\\publicar_rede.ps1 -Acao publicar                 &lt;- escuta no IP da LAN, firewall, tarefa no logon
.venv\\Scripts\\python.exe scripts\\sadgd\\indexar.py --max-minutos 7.5   &lt;- indexa (retoma de onde parou)
.venv\\Scripts\\python.exe scripts\\sadgd\\gerar_fichas.py      &lt;- fichas dos contratos após indexar
scripts\\sadgd\\ollama.ps1 -Acao iniciar|parar|status         &lt;- LLM local
.venv\\Scripts\\python.exe -m pytest -q                         &lt;- 451 testes</pre>
<p>Requisitos da estação atual: Windows 11, GPU NVIDIA GTX 1660 SUPER (6 GB), 16 GB de RAM. Tudo (modelos, caches,
índices, backups) fica em subpastas do projeto. Manual completo em {link(GHB + 'docs/MANUAL_TECNICO.md', 'MANUAL_TECNICO.md')}.</p>
<h1 style="margin-top:9mm">10. Limitações e evolução</h1>
{tabela(["Limitação atual", "Mitigação já aplicada", "Evolução proposta"], [
    ["GPU de 6 GB compartilhada (LLM + reranker)", "Fichas pré-processadas (respostas em segundos), cache semântico, contexto dentro do num_ctx, reranker cai para a CPU sem memória", "GPU com 16–24 GB: modelo maior, decisões em segundos, todo o acervo"],
    ["Decisão (F2) leva de 1 a 2 minutos localmente", "Só os especialistas relevantes; parecer direto quando há um só", "GPU dedicada ou servidor da STI"],
    ["Voz nos demais computadores exige HTTPS", "Publicação HTTPS pronta; aguarda DNS e certificado da STI", "Certificado institucional"],
    ["Alucinação por frase 5,4% (meta 5%)", "Verificador remove frases sem fonte; 0% numérica", "Mais regras determinísticas e julgamento humano das respostas reais"],
])}
<h1 style="margin-top:9mm">11. Como o vídeo e este guia foram produzidos</h1>
<p>Tudo com ferramentas gratuitas, conduzido pelo Claude Code:</p>
<ul class="passos">
<li><b>Telas</b>: <code>scripts/video/capturar_telas.py</code> sobe uma instância isolada com o corpus acadêmico e
navega com o Microsoft Edge (Playwright), inclusive a pergunta por voz (áudio sintético injetado como microfone).</li>
<li><b>Apresentador 3D no estilo de animação</b>: gerado no <b>Google Gemini</b> (app gratuito, operado pelo Claude Code
no Chrome do responsável, com a conta dele e a sua autorização) a partir da foto: retrato base e quatro variações
alinhadas ao pixel — boca em "A", boca em "O", olhos fechados e sorriso aberto com sobrancelhas erguidas. Os prompts
estão em <code>scripts/video/prompts_personagem.md</code>.</li>
<li><b>Animação</b>: <code>scripts/video/gerar_video_demoday.py</code> recorta o fundo e mistura, quadro a quadro, só a
região que muda — boca sincronizada com a energia da voz, piscadas, sorriso nas pausas, sobrancelhas erguidas nas
ênfases — com movimento de cabeça e respiração (OpenCV e NumPy).</li>
<li><b>Narração</b>: voz neural pt-BR Microsoft Daniel (a mesma do vídeo anterior), roteiro em
<code>scripts/video/cenas_demoday.json</code>; legendas geradas automaticamente.</li>
<li><b>Codificação</b>: ffmpeg (H.264 + AAC, 1080p, 25 fps); este PDF: HTML impresso pelo Edge.</li>
</ul>
<div class="destaque" style="margin-top:8mm"><b>Pergunte. Confira a fonte. Decida.</b><br>
O SAD-GD está em funcionamento na rede interna da SEMA-MT. Código: {link(GH)}</div>
</section>""")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>SAD-GD — Pitch e guia (Demo Day 2026)</title>
<style>{CSS}</style></head><body>{''.join(p)}</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=VIDEO_PADRAO)
    args = ap.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)
    aux = imagens_auxiliares()
    doc = montar(args.video, aux)
    arq_html = SAIDA / "guia.html"
    arq_html.write_text(doc, encoding="utf-8")
    from playwright.sync_api import sync_playwright

    destino = SAIDA / "SAD-GD_DemoDay_Pitch_e_Guia.pdf"
    rodape = ('<div style="font-size:7.5pt;color:#7a8396;width:100%;padding:0 15mm;display:flex;'
              'justify-content:space-between;font-family:Segoe UI"><span>SAD-GD · Demo Day 23/11/2026 · '
              'Danilo Xavier — SEMA-MT</span><span><span class="pageNumber"></span> / <span class="totalPages">'
              '</span></span></div>')
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="msedge", headless=True)
        pg = nav.new_page()
        pg.goto(arq_html.as_uri(), wait_until="load")
        pg.pdf(path=str(destino), format="A4", print_background=True, display_header_footer=True,
               header_template="<div></div>", footer_template=rodape,
               margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
        nav.close()
    print("OK:", destino, f"{destino.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
