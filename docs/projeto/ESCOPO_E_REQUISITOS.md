# Escopo e Requisitos — SAD-GD

Versão 1.0 — 2026-11-16. Prioridade MoSCoW: **M** (must), **S** (should), **C** (could), **W** (won't, nesta versão).
Cada requisito tem critério de aceite verificável (formato Dado/Quando/Então ou métrica) e fase prevista.

## 1. Requisitos funcionais

### RF-01 a RF-05 — Ingestão e base de conhecimento

| ID | Requisito | Pri. | Critério de aceite | Fase |
|---|---|---|---|---|
| RF-01 | Ingerir PDF, DOCX, DOC, XLSX, XLS, ODT, ODS, RTF, PPT(X), TXT, MD, HTML e imagens | M | Dado o corpus de fixtures, quando indexado, então 100% dos arquivos suportados têm status registrado e texto extraído quando houver | 4 (reuso v1) |
| RF-02 | OCR de documentos digitalizados com motor portátil (Tesseract) e alternativa Windows OCR | M | PDF escaneado de teste retorna texto com CER ≤ 10% em relação ao gabarito | 4 |
| RF-03 | Chunking estrutural: artigo, parágrafo, inciso, alínea; cláusula e subcláusula | M | Em 20 normas/contratos anotados, ≥ 95% dos limites de dispositivo coincidem com o gabarito; cada trecho guarda documento, página, dispositivo e offsets | 4 |
| RF-04 | Metadados ricos: tipo, número, órgão, data, vigência, processo, contrato, partes | M | Extração de tipo e número com acurácia ≥ 0,90 no corpus anotado | 4 |
| RF-05 | Indexação híbrida incremental (BM25 + embeddings) | M | Reindexar sem alterações processa 0 arquivos; novo arquivo aparece na busca em uma execução | 4 |

### RF-06 a RF-10 — F1: Perguntas e respostas

| ID | Requisito | Pri. | Critério de aceite | Fase |
|---|---|---|---|---|
| RF-06 | Responder perguntas em linguagem natural sobre a base | M | Recall@5 ≥ 0,90 e faithfulness ≥ 0,90 no golden set de teste | 5 |
| RF-07 | Citar a fonte literal: documento, página, dispositivo e trecho | M | 100% das respostas factuais têm ≥ 1 citação; taxa de citações corretas ≥ 0,95 | 5 |
| RF-08 | Declarar ausência de informação sem inventar | M | Nas perguntas "sem resposta" do golden set, ≥ 95% retornam a mensagem de ausência | 5 |
| RF-09 | Detectar e exibir conflitos entre documentos | M | Nos casos de contradição plantados, ≥ 90% sinalizados com as duas fontes | 5–6 |
| RF-10 | Exibir nível de confiança (0–1) e classificação fato/inferência/conflito/ausência | M | Toda resposta da API contém `confianca` e `classificacao` | 5 |

### RF-11 a RF-14 — Linha do tempo e hierarquia normativa

| ID | Requisito | Pri. | Critério de aceite | Fase |
|---|---|---|---|---|
| RF-11 | Agrupar documentos do mesmo processo/contrato/tema | M | Pureza de agrupamento ≥ 0,90 no corpus sintético | 6 |
| RF-12 | Classificar relação entre documentos: continuação, aditivo, alteração, revogação, substituição, ruptura/interrupção, contradição, retomada | M | F1-macro ≥ 0,85; matriz de confusão publicada | 6 |
| RF-13 | Exibir linha do tempo com fases e relações | M | Para um processo do corpus, a tela mostra datas, documentos e rótulos de relação com link à fonte | 6/9 |
| RF-14 | Aplicar hierarquia (CF > Lei > Decreto > IN > Orientação) e vigência | M | Norma revogada nunca é usada como fundamento atual; aparece como "histórico" em 100% dos casos de teste | 6 |

### RF-15 a RF-20 — Multiagentes e F2

| ID | Requisito | Pri. | Critério de aceite | Fase |
|---|---|---|---|---|
| RF-15 | Roteador classifica a pergunta (F1 simples, F1 complexa, F2) e escolhe agentes | M | Acurácia de roteamento ≥ 0,90 no golden set; nenhum caso aciona todos os agentes por padrão | 7 |
| RF-16 | Especialistas (Procurador, Advogado, Controlador, Fiscal, Gestor, Analista Administrativo + propostos) emitem parecer JSON padronizado | M | 100% das saídas validam contra o schema (parecer, fundamentação, citações, confiança, riscos) | 7 |
| RF-17 | Verificador de fontes rejeita afirmações sem trecho de suporte | M | Taxa de alucinação final ≤ 5%; afirmações rejeitadas registradas no trace | 7 |
| RF-18 | Relator consolida consensos e divergências | M | Resposta F2 lista explicitamente consensos e divergências quando houver ≥ 2 pareceres | 7 |
| RF-19 | Memória de decisões: registrar decisão, contexto, fundamentos e resultado; recuperar precedentes | M | Decisão cadastrada é recuperada como precedente em pergunta semelhante (Recall@3 ≥ 0,80 em casos de teste) | 8 |
| RF-20 | Recomendação F2 com alternativas, riscos, base legal, precedentes e confiança, marcada como **sugestão** | M | 100% das respostas F2 contêm os 6 elementos e o aviso "O sistema sugere, a gestão decide" | 8 |

### RF-21 a RF-26 — Interface, acesso e operação

| ID | Requisito | Pri. | Critério de aceite | Fase |
|---|---|---|---|---|
| RF-21 | Chat com respostas, fontes clicáveis e pareceres por agente | M | Teste E2E: pergunta → resposta com fonte que abre o documento na página | 9 |
| RF-22 | Upload de documentos com indexação | M | Arquivo enviado aparece na busca após indexação | 9 |
| RF-23 | Autenticação e perfis (Administrador, Gestor, Consulta) | M | Rotas protegidas retornam 401/403 sem sessão/perfil adequado (reuso v1) | 9 |
| RF-24 | Log de auditoria: quem perguntou o quê, quais documentos acessou | M | Toda consulta gera registro com usuário, data/hora, documentos citados (sem o texto completo) | 7–9 |
| RF-25 | Anonimização de dados pessoais (CPF, e-mail, telefone, nomes de pessoas físicas) antes de envio a LLM externo e em exportações opcionais | M | Nos casos de teste, 100% dos CPFs/e-mails mascarados; recall de nomes de PF ≥ 0,90 | 7 |
| RF-26 | Checklist e relatórios do v1 preservados | S | Testes v1 continuam verdes | todas |

## 2. Requisitos não funcionais

| ID | Categoria | Requisito | Critério de aceite |
|---|---|---|---|
| RNF-01 | Custo | Somente ferramentas gratuitas | Custo monetário = R$ 0,00 registrado em MODELOS_IA.md |
| RNF-02 | Implantação | Executar localmente no Windows 11 (ADR-001) | Instalação do zero por script em ≤ 30 min (excluindo download de modelos) |
| RNF-03 | Armazenamento | Tudo em subpastas do projeto | Varredura de diagnóstico não encontra caches do projeto fora da pasta |
| RNF-04 | Desempenho | Latência | F1 p50 ≤ 6 s, p95 ≤ 15 s; F2 p95 ≤ 120 s (hardware local de referência) |
| RNF-05 | Eficiência | Tokens | Tokens médios por consulta F1 ≤ 3.000; F2 reportado por fase com tendência de queda |
| RNF-06 | Confiabilidade | Anti-alucinação | Alucinação ≤ 5%; faithfulness ≥ 0,90 |
| RNF-07 | Segurança | Escuta em 127.0.0.1 por padrão; sem credenciais no repositório | Varredura de segredos no CI sem achados |
| RNF-08 | Privacidade | LGPD: dados reais não saem da máquina | Provedor externo bloqueado quando a base ativa não for o corpus acadêmico (teste automatizado) |
| RNF-09 | Manutenibilidade | Clean Architecture, SOLID, cobertura | Cobertura ≥ 80% em `domain/` e `application/`; lint sem erros |
| RNF-10 | Portabilidade de provedor | Trocar LLM/embeddings por configuração | Trocar provedor sem alterar código de domínio (teste com 2 provedores) |
| RNF-11 | Observabilidade | Rastrear chamadas, tokens, latência | 100% das consultas com trace (Langfuse local ou equivalente) |
| RNF-12 | Avaliação contínua | Suíte de avaliação no CI | CI executa avaliação reduzida a cada PR e publica resumo |
| RNF-13 | Usabilidade/Acessibilidade | Português-BR, padrão Gov-MT, WCAG 2.1 AA | Verificação de contraste e navegação por teclado (reuso v1) |
| RNF-14 | Continuidade | Retomada por nova sessão | Nova sessão retoma pelo STATUS.md sem informação adicional |

## 3. Fora de escopo (Won't)

- Decisão automática ou execução de atos administrativos.
- Integração com SEI ou sistemas oficiais.
- Ajuste fino de LLM generativo (avaliar apenas reranker/embeddings — ADR na Fase 2/5).
- Hospedagem pública permanente (opcional futuro — ADR-001).

## 4. Rastreabilidade

A matriz requisito → componente → teste → métrica será mantida em `docs/projeto/RASTREABILIDADE.md` a partir da Fase 2.
