# Roteiro de demonstração — SAD-GD

| Campo | Valor |
|---|---|
| Duração | ≈ 15 min de demonstração ao vivo + 5 min de perguntas (vídeo de apoio: 3 min 21 s, `docs/video/ROTEIRO.md`) |
| Ambiente | Computador local, `start.bat`, navegador em http://127.0.0.1:8000, perfil **Gestor** |
| Base | Corpus acadêmico (69 atos oficiais + 117 documentos sintéticos) — nenhum dado real |
| Validação do roteiro | Todas as perguntas abaixo foram executadas **ao vivo no banco real em 17/11/2026** pelo pipeline da API; resultados e tempos registrados nesta página |

> Mensagem central: **respostas com fonte, linha do tempo, apoio à decisão multiperspectiva — e o sistema sugere, a gestão decide.**

---

## 1. Preparação (30 min antes)

| # | Ação | Verificação |
|---|---|---|
| 1 | `scripts\sadgd\ollama.ps1 -Acao status` (iniciar se preciso) | "[OK] Ollama em execução" com `sadgd-qwen2.5-7b` |
| 2 | `start.bat` e login com um usuário **Gestor** | Painel com 186 documentos, 5.691 vetores |
| 3 | **Aquecer os modelos:** fazer a pergunta 1 uma vez | A primeira consulta carrega bge-m3/reranker/LLM (≈ 100 s); as seguintes levam 6–45 s |
| 4 | **Aquecer o cache da F2:** fazer a pergunta 6 uma vez | Repetida na apresentação, volta do cache semântico em milissegundos |
| 5 | Opcional: `SADGD_LLM_F2=gemini` no `.env` (corpus acadêmico) | F2 em ≈ 30 s–3 min em vez de 3–6 min |
| 6 | Deixar abertos: `docs/AVALIACAO.md` e o vídeo (`data/video/sadgd_apresentacao.mp4`) | Plano B |
| 7 | Navegador em tela cheia, zoom 110–125%, **Alto contraste** desligado | Legibilidade no projetor |

---

## 2. Roteiro

### Cena 1 — O problema (1 min) · tela **Painel**

**Fala:** "Um gestor precisa decidir sobre um contrato com aditivos, suspensões, relatórios de fiscalização e
dezenas de normas. O SAD-GD lê esse acervo e responde com a fonte de cada informação."
Mostrar os cartões: documentos por origem, trechos, processos, relações, normas revogadas, decisões.

### Cena 2 — Resposta com fonte (2 min) · tela **Perguntar**

| # | Pergunta | Resultado validado | Tempo |
|---|---|---|---|
| 1 | **Qual empresa é a contratada no Contrato nº 044/2023?** | *Fato documental*, confiança 100%: "Guardião Segurança Patrimonial Ltda. [T8555]" | 105 s a frio · ≈ 15 s aquecido |

**Ação:** clicar em **[T8555]** → o trecho abre; clicar **Abrir documento** → o original abre na página.
**Fala:** "Nenhuma afirmação sem fonte. Um verificador remove frases e números que não estão no trecho citado."

### Cena 3 — Conflito entre documentos (1 min)

| # | Pergunta | Resultado validado | Tempo |
|---|---|---|---|
| 2 | **Qual é o valor global do Contrato nº 044/2023?** | *Conflito*: R$ 2.340.000,00 no contrato [T8558] × R$ 2.430.000,00 no Relatório de Fiscalização nº 007/2024 [T8566] — "É necessária conferência documental." | 6 s |

**Fala:** "Um LLM comum escolheria um dos valores. O SAD-GD detecta a contradição pelo grafo documental e mostra os
dois lados para conferência."

### Cena 4 — Linha do tempo e vigência (3 min)

| # | Pergunta | Resultado validado | Tempo |
|---|---|---|---|
| 3 | **Após o termo aditivo de prorrogação, até quando vigora o Contrato nº 012/2023?** | *Fato*: até 28/02/2025, conforme o Primeiro Termo Aditivo [T8530] | 18 s |
| 4 | **Houve suspensão do Contrato nº 031/2023? Quando as atividades foram retomadas?** | Suspenso a partir de 11/10/2023 por 60 dias (migração do datacenter); retomado em 05/12/2023 — fontes: Ordem de Suspensão nº 004/2023 e Ordem de Reinício nº 005/2023 | 30 s |
| 5 | **A Lei nº 8.666/1993 ainda está em vigor?** | *Fato*: revogada em 30/12/2023, com fonte na Lei nº 14.133/2021 [T6543] | 46 s |

**Ação:** tela **Linha do tempo** → processo **CONTRATO Nº 031/2023** → mostrar as fases coloridas, a **ruptura**
(suspensão) e a **retomada**; clicar na evidência de uma relação. Depois, tela **Acervo** → digitar `8.666` (e depois `7.892`) no filtro → coluna
**Situação** mostra **revogada**.
**Fala:** "Norma revogada fica no histórico, mas não fundamenta decisão atual."

### Cena 5 — Informação ausente (30 s)

| # | Pergunta | Resultado validado | Tempo |
|---|---|---|---|
| 6a | **Qual é o valor global do Contrato nº 999/2024?** | *Informação ausente*: "Não localizei essa informação nos documentos disponibilizados." | 11 s |

**Fala:** "Quando não há evidência, o sistema diz que não sabe. No teste, a recusa correta foi 100%."

### Cena 6 — Apoio à decisão (4 min)

| # | Pergunta | Resultado validado | Tempo |
|---|---|---|---|
| 6 | **Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?** | *Apoio à decisão*: Gestor Público + Fiscal de Contrato; relator válido; 6 elementos (base legal com "ausência declarada"); precedentes P2, P13, P23; recomendação: aguardar a instrução processual com dados atualizados e a manifestação favorável do fiscal antes de nova prorrogação | 175 s (Gemini com 2 quedas para o LLM local) · cache: instantâneo |

**Ação (com a resposta em cache):** percorrer de cima para baixo:
1. **Recomendação sugerida** e os selos dos **6 elementos** (explicar verde × amarelo "ausência declarada").
2. **Alternativas** com prós e contras; **Riscos** com probabilidade × impacto e o agente que apontou.
3. **Precedentes da gestão** — "informam, não vinculam"; resultado e lição de cada um.
4. Abrir o parecer do **Fiscal de Contrato** → afirmações verificadas com citação.
5. Rodapé: **aviso** "o sistema sugere, a gestão decide" e o **número da consulta** na auditoria.

**Fala:** "Só os especialistas relevantes foram chamados — aqui, 2 de 8. Cada parecer é validado e cada afirmação
precisa de citação. A recomendação traz alternativas, riscos e precedentes, mas a decisão é da gestão."

### Cena 7 — Memória de decisões (1 min) · tela **Decisões**

Buscar precedentes para "prorrogação de contrato de vigilância com fiscalização desfavorável" e abrir uma decisão
com **Resultado** e **Lição**. Mostrar (sem salvar) o formulário **Registrar decisão**.

### Cena 8 — Evidências de qualidade (2 min) · `docs/AVALIACAO.md`

| Métrica (teste) | Meta | Resultado |
|---|---|---|
| Recall@5 | ≥ 0,90 | 0,965 (legado 0,431) |
| Faithfulness | ≥ 0,90 | 0,964 |
| Alucinação numérica | ≤ 5% | 0% |
| Roteamento | ≥ 0,90 | 0,935 |
| F2 p95 (nuvem, corpus acadêmico) | ≤ 120 s | 100 s |
| Custo | gratuito | R$ 0 |

**Fala:** "Teste nunca usado para ajuste, juiz de fidelidade calibrado e adjudicado, experimentos negativos
registrados — como o modelo 3B que parecia 2,5× mais rápido, mas devolvia pareceres vazios."

### Encerramento (30 s)

"Execução local, gratuita e auditável; LGPD por padrão; fonte em cada resposta. O sistema sugere — a gestão decide."

---

## 3. Plano B

| Problema | Ação |
|---|---|
| F2 demorando mais que o tempo da cena | Explicar a latência local (GPU de 6 GB) e usar a resposta aquecida no cache, ou mostrar a captura `docs/img/fase09/05_perguntar_f2.png` |
| Gemini com 503/429 | Automático: cai no LLM local (mais lento). Seguir com o cache |
| Ollama parado | `scripts\sadgd\ollama.ps1 -Acao iniciar` (não encadear com `| Out-Null`) |
| Servidor não abre | `diagnostico.bat`; em último caso, apresentar o vídeo (3 min 21 s) e as capturas de `docs/img/fase09/` |
| Pergunta da plateia sem resposta | Mostrar como recurso: "Não localizei…" é o comportamento correto sem evidência |

## 4. Perguntas prováveis da banca

| Pergunta | Resposta curta | Onde aprofundar |
|---|---|---|
| Por que não ajuste fino? | Recall@5 0,965 sem ajuste; custo e risco de sobreajuste | ADR-012 |
| Como sabem que não alucina? | Verificador determinístico + juiz de outra família calibrado (κ 0,71) + adjudicação | `FASE_10.md` §4 |
| E os dados pessoais? | Tudo local; nuvem só para corpus acadêmico, com pseudonimização e política por origem | `RELATORIO_TECNICO.md` §7 |
| Por que LangGraph e não CrewAI? | Controle explícito do fluxo e fan-out seletivo; matriz ponderada | ADR-003 |
| F1 1,00 nas relações não é bom demais? | Sim — sobreajuste declarado no sintético; verificado no público (10/10) | `FASE_06.md` |
| Qual a maior limitação? | Latência da F2 no hardware local | `RELATORIO_TECNICO.md` §10 |
