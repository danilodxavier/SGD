# Fase 12 — Implantação na rede interna (chat por texto e voz)

> Aberta em 2026-11-21 a pedido do responsável: acesso pelo navegador em `https://sad.sema.mt.gov.br`, servido
> por esta máquina, com perguntas por texto ou voz, para uso da alta gestão (alta assertividade, baixo tempo de
> resposta).

## 1. Decisões (2026-11-21)

| Tema | Decisão | Motivo |
|---|---|---|
| DNS e certificado | **A STI fornece** o registro DNS e o certificado prontos; o sistema só instala e valida | Certificado válido evita alerta no navegador e é exigido para o microfone (contexto seguro) |
| Quem acessa | **Rede interna + login** (perfis do sistema; consultas auditadas) | Faixas privadas 10/8, 172.16/12, 192.168/16; nome de acesso conferido (`ALLOWED_HOSTS`) |
| Tempo × precisão | **Precisão + tempo percebido** | Mantém a qualidade medida; fila com posição/etapa e parecer de hardware para reduzir o tempo real |
| Voz | **Transcrição local** (faster-whisper, CPU) — ver [ADR-014](../adr/ADR-014-voz-local.md) | O reconhecimento do navegador envia o áudio a servidores externos; perguntas citam contratos reais |

## 1.1 Ajuste de 2026-11-21 — endereço `sad.sema.mt.gov.br`, só na LAN

O responsável pediu trocar `http://127.0.0.1:8000` por `http://sad.sema.mt.gov.br`, respondendo apenas na LAN. A porta 80 está numa faixa excluída do Windows desta estação (`netsh int ipv4 show excludedportrange`: 80–80, origem desconhecida) e o http.sys reserva `*:80`; decisão: **já em `http://sad.sema.mt.gov.br:8000`** (sem alterar o Windows) e, com o certificado, **`https://sad.sema.mt.gov.br`** (porta 443 livre no IP da LAN, com voz).

Estado: servidor escutando só no IP da LAN, porta 8000; `ALLOWED_HOSTS` = nome + IP; firewall de entrada TCP 8000 só para faixas privadas (perfil Domínio); tarefa "SAD-GD" no logon. Testes: pelo IP 200, pelo nome 200, nome desconhecido 403, `127.0.0.1:8000` sem resposta. **Voz**: em http o navegador bloqueia o microfone nos outros computadores (e numa sessão remota depende do redirecionamento de áudio) — só com HTTPS. DNS do nome: pendente (STI).

## 2. Entregue

| Item | Onde | Evidência |
|---|---|---|
| Fila de consultas FIFO com acompanhamento: `POST /api/sadgd/consultas` (202, número na hora) e `GET /api/sadgd/consultas/{id}` (posição, etapa, tempo, resultado); só o dono vê a consulta | `app/application/consultas/fila.py`, `app/interfaces/api/perguntar.py` | `tests/sadgd/test_fila.py`, `test_api_perguntar.py` |
| Chat na tela Perguntar: conversa com várias perguntas, etapa atual ("Buscando nos documentos", "Ouvindo os agentes especialistas"…), posição na fila e tempo | `frontend/js/sadgd.js`, `frontend/index.html`, `frontend/css/app.css` | E2E no Edge (403 testes) |
| Pergunta por voz: botão Falar/Parar; navegador grava e converte para WAV 16 kHz; `POST /api/sadgd/transcrever` (login) transcreve localmente; o texto volta à caixa para conferência antes do envio; áudio não é gravado | `app/infrastructure/voz/transcritor.py`, `app/interfaces/api/voz.py` | `tests/sadgd/test_voz.py`; voz sintética pt-BR: 3/3 frases exatas, 1,3 s cada (small, CPU) |
| Instalação do certificado da STI (.pfx ou .crt+.key): valida nome (inclusive curinga), validade e par de chaves; grava PEM em `ferramentas\certificados\` | `scripts/rede/instalar_certificado.py` | `tests/test_instalar_certificado.py` |
| Publicação: `status` / `publicar` / `remover` — backup do `.env`, escuta em `IP:443`, firewall de entrada só para faixas internas, tarefa de início no logon (Ollama + servidor) | `scripts/rede/publicar_rede.ps1`, `scripts/rede/iniciar_rede.bat` | `status` executado; fumaça HTTPS local: health 200, voz/consultas sem login 401, host desconhecido 403 |

## 3. Pendências (dependem da STI)

Ver [PEDIDO_STI.md](../implantacao/PEDIDO_STI.md): registro DNS `sad.sema.mt.gov.br` → **IP da estação**
com IP fixo (reserva DHCP) e certificado do nome. Com eles:

```powershell
.venv\Scripts\python.exe scripts\rede\instalar_certificado.py --pfx <arquivo da STI>
# PowerShell como Administrador:
scripts\rede\publicar_rede.ps1 -Acao publicar
stop.bat ; scripts\rede\iniciar_rede.bat
scripts\rede\publicar_rede.ps1 -Acao status
```

## 4. Tempo de resposta — situação e parecer de hardware

Medido no acervo real (rodada 4): pergunta simples mediana ≈ 89 s; decisão ≈ 4 min; uma pergunta por vez (fila).
O gargalo é o LLM de 7B: com 6 GB de VRAM, 21% do modelo roda na CPU, e só restam ≈ 1,4 GB de RAM livre.

| Opção | Efeito esperado | Custo |
|---|---|---|
| Fila + etapas na tela (feito) | Tempo **percebido**: o gestor vê o andamento e pode enviar outras perguntas | — |
| Cache semântico (já existe) | Pergunta repetida volta em segundos | — |
| Ajuste fino de trechos/saída após o julgamento da equipe | Menos tokens por pergunta, sem perder o que a equipe aprovar | — |
| GPU com 12–16 GB (ex.: RTX 3060 12 GB) + 32 GB de RAM | Modelo inteiro na GPU; ganho estimado de 3–4× na geração | **Pago** — fora da regra de ferramentas gratuitas; decisão da gestão |

O LLM em nuvem (Gemini) continua **proibido para dados reais** (ADR-002) e não é alternativa aqui.

## 5. Riscos

| Risco | Mitigação |
|---|---|
| Máquina desligada ou em suspensão = sistema fora do ar | Tarefa de início no logon; configurar energia para não suspender; documentar no manual |
| RAM baixa (≈ 1,4 GB livres) com vários usuários | Fila única (um LLM por vez); Whisper small (≈ 0,5 GB); reiniciar o Ollama se o `llama-server` acumular memória |
| IP da máquina mudar (DHCP) | Reserva de IP pela STI; `publicar_rede.ps1 -Acao status` aponta divergência entre DNS e IP |
| Voz real (sotaque, ruído) pior que a sintética | Texto sempre conferido antes do envio; trocar para `SADGD_WHISPER_MODELO=medium` se necessário |

## 6. Desempenho do LLM nesta estação (medição de 2026-11-21)

Benchmark fixo (texto sintético; modelo descarregado antes de cada rodada):

| Configuração | Leitura do prompt | Geração | Camadas na GPU |
|---|---|---|---|
| Atual (Ollama padrão) | 124 tok/s | 21,5 tok/s | 25/29 (21% na CPU) |
| + flash attention + cache de atenção q8_0 | 124 tok/s | 24,7 tok/s | 81% GPU |
| `num_gpu 29` + flash attention + q8_0 | 125 tok/s | 34,9 tok/s | 100% GPU |
| **`num_gpu 29`, sem flash attention** | 126 tok/s | **38,0 tok/s** | **100% GPU** |

- A leitura do prompt sem cache fica em ≈ 140 tok/s em qualquer tamanho (505 → 6.129 tokens): é o limite de cálculo
  da GTX 1660 SUPER (sem tensor cores) para um 7B; **cada 1.000 tokens de trechos custam ≈ 7 s**.
- O prompt de sistema (≈ 1.235 tokens) é reaproveitado entre perguntas pelo cache de prefixo do Ollama (0,4 s).
- O Ollama deixava 4 camadas (844 MB) na CPU por margem de segurança; com `num_gpu 29` (variante
  `sadgd-qwen2.5-7b-gpu`, `LLM_MODELO_PADRAO` no `.env`) o modelo cabe inteiro — a placa é compartilhada com Chrome,
  Edge, Teams, Docker, Acrobat etc. (≈ 1 GB de VRAM); fechar esses programas na estação servidora dá margem.

Mudanças adotadas (versão rápida): modelo 100% na GPU; `SADGD_CONTEXTO_MAX_CHARS` 1.200 → 800; relator v3 só com as
instruções da F1; detalhe reprovado pelo verificador sai sem nova chamada ao LLM (a nova tentativa fica para a resposta
direta errada).

| Validação acadêmica (47 F1, com verificador) | Antes | **Versão rápida** |
|---|---|---|
| Exatidão | 0,923 | 0,923 |
| Classificação | 0,915 | **0,979** |
| Recusa correta / conflito | 1,00 / 1,00 | 1,00 / 1,00 |
| Citação correta | 0,907 | **0,954** |
| Alucinação numérica | 0 | 0 |
| Tempo do LLM p50 / p95 | 23,1 s / 48,5 s | **16,9 s / 31,1 s** |

Acervo real (mesmas perguntas, ponta a ponta): R01 48 → 47 s; R05 44 → 42 s; R09 (histórico) 95 → 77 s; R08 (lista)
129 → 68 s. Nas perguntas simples o ganho real é pequeno porque o tempo é dominado pela leitura de ≈ 2.500 tokens
novos de trechos (≈ 17–25 s) — piso desta placa. Próximas alavancas: menos texto por pergunta (exige o julgamento
da equipe para não perder qualidade) ou GPU com tensor cores (ex.: RTX 3060 12 GB: leitura do prompt estimada em
5–10×, decisão de compra da gestão).

## 7. Meta de 10 s — fichas de contrato (ADR-015)

Pedido do responsável: respostas em até 10 s. Medido: nenhuma configuração gratuita do LLM chega lá mantendo o acerto
(3B: ≈ 12 s, exatidão 0,872 e **recusa correta 0,25**). Decisão: **fichas pré-processadas** — ver
[ADR-015](../adr/ADR-015-fichas-de-contrato.md).

- Agrupamento: 19 contratos (pastas de 1º nível com nº/ano), 5.944 de 6.011 documentos; acadêmico: 20 contratos.
- Extração (LLM local, ≈ 25 s por contrato, uma vez): real 104 campos conferidos (objeto 19/19, contratada e valor
  12/19, gestor 10/19, fiscal 7/19, vigência 7/19); acadêmico 166 campos (8,3 por contrato).
- Consulta sem LLM: 0–20 ms; checagem de número inexistente ≈ 0,4–0,8 s.

| Pergunta real (rodada 5 → 6) | Antes | Agora | Como |
|---|---|---|---|
| R01 objeto do contrato | 66 s | **0,0 s** | ficha |
| R04 empenho do contrato | 28–41 s | **1,2 s** | inventário |
| R05 contrato de um fornecedor | 38–45 s | **0,0 s** | 2 contratos casam com o nome → lista |
| R08 contratos com notificação em 2025 | 49–84 s | **0,0 s** | inventário transversal |
| R11 termo de recebimento do contrato | 38–65 s | **0,0 s** | inventário |
| R12 ordem de serviço em 2026 | 72–98 s | **0,0 s** | inventário (tipo pelo título) |
| R03, R10 (número citado aparece no acervo, mas sem pasta) | 40–83 s | 40–83 s | caminho completo |
| R06, R07, R09 (abertas) | 90–145 s | 90–145 s | caminho completo |
| R02 decisão (especialistas) | ≈ 4 min | ≈ 4 min | F2 |

Atualização: `python scripts/sadgd/gerar_fichas.py` após cada indexação (extrai só contratos novos; o inventário é
sempre refeito).

## 8. Rodada 7 — 2ª passada das fichas e regras de precisão (2026-11-21)

**2ª passada** (`gerar_fichas.py`, automática após a 1ª): campos que faltaram, buscados no extrato de publicação, nas
portarias de designação e no resto do instrumento; **vigência atual e valor atualizado** pelo termo aditivo mais
recente. Real: 104 → **170 campos** (vigência 7 → 16, fiscal 7 → 11, gestor 10 → 15, contratada 12 → 15, vigência
atual 5, valor atual 7). Acadêmico: +66 campos, vigência atual em 14/20.

**Conferência contra o golden acadêmico** (156 perguntas não-F2) revelou erros das respostas rápidas, corrigidos:

| Erro | Correção |
|---|---|
| "Até quando vigora após o aditivo?" caía na lista de aditivos | vigência tem prioridade sobre "aditivo" |
| Valor após aditivo/reajuste; "valor da garantia" | só valor DO contrato; com aditivo/apostilamento, só se o valor atualizado veio do mais recente |
| "Qual reajuste foi apostilado?" (conteúdo) | ficha responde só existência/listas; conteúdo → caminho completo |
| "Houve paralisação?" → "não localizei" (documento classificado como ordem de suspensão) | assunto abrange suspensão/reinício/rescisão; **antes de afirmar ausência, confere o texto da pasta** |
| Valor com **contradição registrada no grafo** (RF-09) respondido pela ficha | contradição sobre o campo → caminho completo, que mostra as duas fontes |
| "Preposto da contratada" respondido como contratada | preposto, representante, endereço, CPF… → caminho completo |
| Ausência no acervo inteiro (pergunta transversal) | não se afirma pela classificação → caminho completo |

Resultado no acadêmico: a ficha responde **71** perguntas, **69 corretas pelo critério automático (as 2 restantes
diferem só na pontuação de "Ltda.")** — antes 101 respondidas com 67 corretas. Menos cobertura, nenhuma resposta
rápida errada.

**Acervo real (rodada 7 × rodada 4):** mediana F1 89 s → **47 s**; até 10 s: 4/11 (R01, R04, R05, R11, em 0–1,6 s);
recusas 2 → 1 (R12, provável ausência real); R03 e R10 passaram a ser respondidas. Pergunta transversal sem
ocorrência no ano (R08) e ausência com o assunto citado no texto da pasta (R12) agora vão ao caminho completo
(46–89 s) — troca deliberada de tempo por segurança.

## 9. Fichas sempre atualizadas e decisão sobre a GPU (2026-11-21)

- **Atualização automática**: ao fim de cada indexação — upload/atualização pela tela Acervo (serviço do servidor,
  etapa "atualizando as fichas dos contratos", resultado em `estado.fichas`) e `scripts/sadgd/indexar.py` (exceto
  `--sem-fichas` ou execução interrompida por `--max-minutos`, que atualiza no ciclo final). Inventário sempre
  refeito; LLM local só para contratos novos ou fichas sem a 2ª passada. Sem contrato novo: ≈ 3,6 s. Falha nas
  fichas não invalida a indexação (registrada; nova tentativa na próxima). Chave: `SADGD_FICHAS_APOS_INDEXAR`.
- **GPU**: o responsável informou que a troca da placa **não é possível agora**. Perguntas abertas e de decisão
  seguem limitadas pelo hardware (abertas ≈ 45–90 s; decisão ≈ 3–4 min); a estratégia passa a ser ampliar o que é
  preparado antes (fichas) e reduzir texto por pergunta sem perder acerto.

## 10. Rodada 8 — a ficha responde mais (2026-11-21)

| Ampliação | Exemplo | Salvaguarda |
|---|---|---|
| **Panorama de vigência** de todos os contratos: vencem em até 120 dias (fase de renovação), encerrados, vigentes | "Quais processos estão em fase de renovação?" | término pela vigência atual (aditivo), pelo instrumento ou **calculado** (início/assinatura + prazo), sempre identificado e citado; aditivo posterior sinalizado; classificação "inferência" |
| **Tipos pelo título**: relatório de apuração; notificação extrajudicial classificada como outro tipo | "Quais contratos tiveram notificação extrajudicial em 2025?" | lista com o documento mais recente citado |
| **Existência sem contrato citado** ("houve…?", "foi realizado…?") percorre todas as fichas | "Foi realizado relatório de apuração em 2025?" | — |
| **Ausência com ano conferida no texto** (contrato ou acervo inteiro) | "Foi aberta OS em 2026?" | só afirma se nenhum trecho cita o assunto **junto com o ano**; senão, caminho completo |

Golden acadêmico: 72 respostas rápidas, todas corretas (2 diferem só na pontuação de "Ltda."). Acervo real: 16 dos
19 contratos com data de término na ficha.

**Rodada 8 × rodada 4:** mediana das perguntas não-decisórias **89 s → 0,8 s**; **6 de 11 em ≤ 0,8 s** (R01, R04,
R05, R06, R08, R11); demais 33–75 s pelo caminho completo (R09 e R12: o texto cita o assunto com o ano — a ficha não
afirma ausência); decisão (R02) 243 → 154 s. Recusas: R12 (provável ausência real) e R07 ("há pendência em algum
contrato?", pergunta vaga pelo caminho completo, que oscila entre rodadas).

## 11. Rodada 9 — números que não são de contrato e ausência pelo início dos documentos (2026-11-21)

- **Número citado que não é de contrato** (R03 e R10): o número aparece no acervo (203 e 11
  trechos), mas **nunca como "contrato nº"** — sobretudo em apostilamentos, ofícios e extratos. A ficha responde que
  não há contrato com esse número e mostra até 5 documentos onde ele aparece, citados (caso a pergunta se refira a um
  deles). Se o número aparecer como contrato em algum trecho, o caminho completo lê.
- **Ausência com ano pelo início do documento**: em vez de "termo + ano em qualquer trecho" (uma cláusula do contrato
  que cita "ordem de serviço" num trecho com "2026" bloqueava a resposta), procura documento cujo 1º trecho
  (título/abertura) cita o assunto e cuja data é do ano pedido — ou sem data (dúvida → caminho completo).

**Rodada 9:** **8 de 11 perguntas não-decisórias em ≤ 4,6 s** (R01, R03, R04, R05, R06, R08, R10, R11); R07, R09 e
R12 pelo caminho completo (56–85 s; em R09/R12 há documento que começa citando o assunto no ano pedido ou sem data);
decisão (R02) 149 s. Golden acadêmico inalterado (72 respostas rápidas corretas).

## 12. Rodada 10 — busca no contrato citado quando a ficha não basta (2026-11-21)

Quando a pergunta identifica um contrato com ficha, mas a ficha não responde (inclusive na **decisão**), a busca do
caminho completo fica no contrato: candidatos lexicais e vetoriais ampliados para 400, filtrados pelos documentos da
pasta (sem pasta: inventário), **misturados com 3 vagas do acervo inteiro** e reranqueados juntos; com menos de 3
trechos no contrato, busca no acervo inteiro.

| Golden acadêmico (37 perguntas com contrato identificado que a ficha não responde) | Sem escopo | Filtro só no contrato | **Contrato + 3 do acervo** |
|---|---|---|---|
| Documento esperado entre os 8 trechos | 37/37 | 33/37 (perdeu lei/portaria fora do grupo) | **37/37** |
| Trechos dos documentos esperados | 18% | — | **27%** |
| Tempo da busca | 1,8 s | 0,7 s | **1,0 s** |

Acervo real (rodada 10 × 9): R12 76 → 55 s (recusa mantida, agora com a busca no contrato certo); decisão R02
149 → 139 s; demais inalteradas (8 de 11 em ≤ 5 s).

## 13. Decisão (F2): ficha para os especialistas e contexto compartilhado (2026-11-22)

**Diagnóstico** (decisão real, só números): o relator relia ≈ 5.600 tokens de trechos que o especialista já tinha
lido (≈ 40 s) — o cache de prefixo do Ollama não ajudava porque cada papel começava com um prompt de sistema
diferente.

**Mudanças:**
1. **Contexto compartilhado**: sistema = regras comuns (igual para todos); 1ª mensagem = pergunta + ficha + linha do
   tempo + trechos (igual para todos); 2ª mensagem = instruções do papel (+ pareceres, no relator). O Ollama lê o
   bloco comum uma vez; o relator só lê o que é novo (medido: 58 s → 25 s com o modelo carregado).
2. **Ficha no contexto da decisão** sobre contrato com ficha: objeto, valor, vigência e situação, fiscal, contratada,
   gestor e contagem de documentos por tipo, com citação; os trechos de origem (até 4) entram no contexto (citáveis e
   conferidos pelo verificador) e a busca traz 4 trechos em vez de 8.
3. **Correção de uma conclusão anterior (§6)**: com o reranker carregado na GPU (situação de produção), a variante
   `sadgd-qwen2.5-7b-gpu` (`num_gpu 29`) é **mais lenta** que o padrão — a VRAM não comporta os dois e o excesso vai
   para a RAM. Medido com o modelo descarregado antes: pergunta aberta 89 → 80 s, decisão 149 → 124 s com o padrão.
   `.env` voltou a `sadgd-qwen2.5-7b`; a variante fica disponível para uma placa maior.
4. **LLM carregado por 12 h** (`OLLAMA_KEEP_ALIVE`, `ollama.ps1`): o padrão do Ollama descarregava após 5 min e a 1ª
   pergunta depois de uma pausa pagava 10–15 s de recarga.

**Regressão acadêmica da decisão** (validação, 6 F2, LLM local, `avaliacao/execucoes/fase12_f2/` ×
`fase11_f2ctx/`; os 3 últimos itens rodados em primeiro plano após a 1ª execução ser encerrada por falta de memória):

| | Antes | Contexto compartilhado |
|---|---|---|
| Relator válido | 1,00 | 1,00 |
| RF-20 completo (6 elementos presentes) | 0,83 | 0,83 |
| Recall de documentos | 0,639 | 0,639 |
| Precisão de documentos | 0,456 | 0,442 |
| p50 | 319 s | **236 s (−26%)** |

Item a item, mesmo número de pareceres (2–3) e o mesmo resultado estrutural; ganho de tempo em todos (283 → 265 s a
372 → 235 s).

## 14. Rodada 11 — datas dos documentos, pendências e documentos para conferir (2026-11-22)

**Diagnóstico** (só contagens): **4.891 dos 6.011 documentos reais (81%) estavam sem data** — a regra de data só
aceitava o fecho ("Cuiabá, 10 de março de 2025.") no fim da última linha. Toda pergunta com ano ("em 2025",
"no ano de 2026") esbarrava nisso: a ficha não podia afirmar ausência e a pergunta ia para o caminho completo
(≈ 55 s), que terminava em recusa (R09, R12).

**Mudanças:**
1. **Datas complementares** (`data_complementar` em `metadados.py`; só onde a regra antiga não achou data):
   último fecho por extenso em qualquer ponto → último "assinado … dd/mm/aaaa" → "data de emissão" → "em
   dd/mm/aaaa, às hh:mm" → "Cuiabá, dd/mm/aaaa"; datas antes de 1988 ou no futuro são descartadas. Medido contra
   os 1.120 documentos reais que já tinham data: último fecho com **ano igual em 98,5%** (dia igual em 90%);
   assinatura com ano igual em 93%. `scripts/sadgd/datar_documentos.py` completou o acervo já indexado
   (backup antes): **1.492 documentos datados**; seguem sem data 3.399 (sobretudo planilhas e rascunhos .docx).
   Grafo reconstruído e inventário das fichas atualizado (sem LLM).
2. **Documentos para conferir** (classificação `candidatos`, confiança 0,5): quando nada foi classificado no
   tipo e no ano, mas há documentos que começam citando o assunto no ano (ou sem data), a ficha lista esses
   documentos com a fonte, em vez de mandar a pergunta para um caminho longo que recusava. Na pergunta geral
   (sem contrato), agrupa por contrato só os documentos datados do ano.
3. **Pendências** ("Há pendência em algum contrato?" / "…no contrato X?"): pontos de atenção deduzidos das
   fichas, cada um com fonte — vencimento em até 120 dias, documentos de execução datados depois do término,
   término passado com aditivo posterior (conferir prorrogação), notificação/apuração nos últimos 12 meses e
   contrato vigente sem empenho no exercício. Sem nada avaliável, não afirma "sem pendências" (caminho completo);
   "pendência de pagamento/empenho…" segue o assunto próprio.
4. **Aditivos relidos quando surge um mais recente** (nova indexação ou data corrigida; só os aditivos, uma vez)
   e **cláusula de prorrogação priorizada** na seleção de trechos do aditivo (antes, trechos que só citavam
   "valor"/"prazo" ocupavam as vagas). Acervo real: vigência atual pelo aditivo em 7 das 16 fichas com término
   (5 aditivos com vigência lida nesta rodada); acadêmico: vigência 32/32 mantida.

**Resultado nas perguntas reais** (só tempos e códigos):

| Pergunta | Antes | Agora |
|---|---|---|
| R07 (pendências) | 87 s (caminho completo) | **0,0 s** — 11 contratos com pontos de atenção, 13 fontes |
| R09 (apuração em 2025) | 57 s, recusa | **0,0 s** — fato, com fonte (documento passou a ter data) |
| R12 (OS em 2026) | 55 s, recusa | **0,1 s** — documentos para conferir (8 fontes) |
| Demais 8 não-decisão | ≤ 5 s | ≤ 4,3 s (sem mudança) |

Agora **11 das 12 perguntas reais respondem em menos de 5 s**; só a decisão (R02, F2) segue no caminho dos
especialistas. Regressão acadêmica das fichas: 70/72 (as 2 diferenças são pontuação de "Ltda."), igual à anterior.

## 15. Rodada 12 — tempo da decisão: contexto dentro do limite do modelo (2026-11-22)

**Diagnóstico** (decisão real R02, só números; modelo recém-reiniciado): **334 s** — especialista 225 s com **2
tentativas** e relator 105 s. O contexto comum tinha ≈ 17 mil caracteres (**≈ 7.500 tokens**; o texto real rende
≈ 2,3 caracteres/token) e o modelo local roda com `num_ctx 8192`: prompt + resposta passavam do limite, o JSON do
especialista era cortado (nova tentativa = outra geração inteira) e o deslocamento do contexto anulava o cache de
prefixo, então o relator relia tudo. A linha do tempo ocupava ≈ 4.900 caracteres e trazia os eventos **mais
antigos** (os sem data, ordenados no início, ocupavam as vagas).

**Mudanças:**
1. **Orçamento do contexto da decisão** (`ajustar_contexto`, 8.500 caracteres para ficha + linha do tempo +
   precedentes + trechos): trechos na ordem (origem da ficha, depois os mais relevantes) até o limite, mínimo 4;
   a linha do tempo é a parte que cede (ficha e precedentes ficam inteiros). Especialistas, relator e verificador
   veem os mesmos trechos.
2. **Linha do tempo com os eventos mais recentes** (datados primeiro, exibidos em ordem cronológica); com ficha do
   contrato, só 1 processo e 8 eventos — a ficha já resume o contrato.
3. **Parecer mais enxuto** (até 3 afirmações, 2 fundamentos, 2 riscos, 2 alternativas, 2 lacunas; raciocínio curto)
   e teto de 1.200 tokens: com 900, o JSON completo (≈ 850 tokens) era cortado.
4. **Pareceres para o relator em níveis de compactação** até caberem em 3.500 caracteres (vários especialistas
   somados ao contexto passariam do limite).

**Resultado na decisão real (R02):**

| | Antes | Agora |
|---|---|---|
| Tokens de entrada do especialista | 7.563 | 4.743 |
| Tentativas do especialista | 2 | **1** |
| Especialista | 225 s | 35 s (cache) / 63 s (modelo descarregado antes) |
| Relator | 105 s | 33–36 s (cache de prefixo voltou a valer) |
| **Total** | **334 s** (124 s na medição anterior) | **78 s** com o modelo carregado; **103 s** com o modelo descarregado antes |

**Regressão acadêmica da decisão** (validação, 6 F2, LLM local, `avaliacao/execucoes/fase12_f2_orcamento/` ×
`fase12_f2/`; uma falha transitória do Ollama no V030 foi repetida automaticamente):

| | Antes | Orçamento |
|---|---|---|
| JSON do especialista válido sem reparo | 0,714 | **1,00** |
| Afirmações removidas pelo verificador (por consulta) | 1,0 | **0,0** |
| Relator válido / RF-20 com os 6 elementos preenchidos | 1,00 / 0,83 | 1,00 / 0,83 |
| Recall / precisão de documentos | 0,639 / 0,442 | 0,639 / **0,511** |
| Base legal (média de itens) | 4,5 | 3,5 (presente em 100%) |
| p50 / p95 | 235 / 265 s | **150 / 185 s (−36% / −30%)** |

## 16. Rodada 13 — decisão com um só especialista sem 2ª chamada ao modelo (2026-11-22)

Quando o roteador aciona **um único especialista** (caso da decisão real R02: só o gestor público), não há consensos
nem divergências a consolidar e o relator custava ≈ 35 s só para reorganizar o parecer. Agora a síntese é montada
**sem LLM** a partir do parecer (`sintese_de_parecer_unico`): texto do parecer + afirmações com citação (já
verificadas), recomendação, alternativas, riscos e lacunas do especialista. Passa pelas mesmas salvaguardas do
relator (verificador de frases, RF-20 completado pelo sistema, aviso obrigatório) e registra a observação
`relator_dispensado_parecer_unico`. Parecer inválido ou sem afirmação citada, ou dois ou mais pareceres → relator
com o LLM, como antes.

**Decisão real R02** (modelo descarregado antes): **103 → 71 s** (especialista 64 s; síntese 3 ms; sem frases
removidas pelo verificador). Na rodada 11 eram 124 s e, com o estouro de contexto, 334 s.

**Regressão acadêmica:** as 6 decisões da validação acionam 2–3 especialistas (`fase12_f2_orcamento`), portanto
seguem pelo relator e o resultado da §15 vale sem alteração.

## 17. Rodada 14 — perguntas abertas: diagnóstico, correções e experimentos rejeitados (2026-11-22)

**Diagnóstico** (6 perguntas abertas genéricas no acervo real, só números): as que vão ao LLM levam **37–58 s**;
≈ 65% é a **leitura do prompt** (3.700–5.800 tokens a ≈ 135 tokens/s) e o resto é geração (≈ 25 tokens/s).

**Correções aplicadas:**
1. **Pergunta sobre regra ou procedimento não vira inventário** (`RE_NORMATIVA`): "Quais documentos são exigidos
   para o pagamento da nota fiscal?" era respondida na hora pela ficha **listando as notas fiscais das pastas**
   (resposta errada, embora rápida). "Exigido", "necessário", "requisito", "como deve…", "o que diz…" seguem
   para o caminho completo. Golden das fichas 70/72 (igual); nenhuma das 12 perguntas reais afetada.
2. **Reranker sem memória na GPU passa para a CPU** em vez de derrubar a pergunta. Após ≈ 1 h de avaliações o
   `llama-server` voltou a passar de 12 GB comprometidos e um processo novo não conseguia carregar o reranker
   (CUDA OOM); o servidor só carrega o reranker na 1ª pergunta, então um reinício nesse estado faria toda busca
   falhar.

**Experimentos rejeitados (medidos):**

| Experimento | Resultado | Decisão |
|---|---|---|
| Ficha do documento uma vez por documento (bloco DOCUMENTO), em vez de repetida em cada trecho — cabeçalhos eram 23–45% do contexto real | Acadêmico: tokens −3%; exatidão 0,923 =, mas **recusa correta 1,00 → 0,75**. Teste isolado com o mesmo modelo: V036 recusa no formato antigo e responde no agrupado (`avaliacao/execucoes/fase12_contexto_doc/`) | Revertido — recusa correta é salvaguarda contra invenção |
| Descartar trechos com nota baixa do reranker | Acadêmico: nota ≥ 0,05 manteria 88% dos trechos sem perder evidência; **real: todas as notas entre 0,12 e 0,98** (A3) e quase todas ≥ 0,7 — nada a cortar | Sem ganho no acervo real |
| Modelo inteiro na GPU (`-gpu`, 29 camadas) | Texto sintético: leitura 135 → 138 tokens/s (igual: a leitura é limitada pela GPU); **geração 24,7 → 39,7 tokens/s**. Mas não cabe junto do reranker (5,2 + 2,3 GB > 6 GB): reranker na CPU custa 16,6 s × 4 s | Mantido o padrão: −9 s na geração × +12,6 s na busca |

**Conclusão:** nesta GPU, o tempo das perguntas abertas é dominado pela leitura do prompt (fixa em ≈ 135
tokens/s) e o número de tokens já está no mínimo seguro medido; os ganhos restantes passam por responder mais
perguntas sem o LLM (fichas) ou por hardware.

## 18. Rodada 15 — configuração do Ollama: flash attention + cache de contexto em 8 bits (2026-11-22)

Medição com o reranker carregado na GPU e o modelo descarregado antes (texto sintético, 4.835 tokens, 3 repetições):

| Configuração | Leitura (tok/s) | Geração (tok/s) | VRAM do modelo | Decisão |
|---|---|---|---|---|
| Padrão (KV f16, 25/29 camadas) | 127 | 23,8 | 4.073 MB | — |
| `OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0` + `OLLAMA_NUM_PARALLEL=1` | 128 | **26,7 (+12%)** | 4.013 MB | **Adotado** (`ollama.ps1`) |
| Idem + 27 camadas na GPU (`num_gpu 27`) | 92 | 7,5 | 4.297 MB | Rejeitado: a VRAM transborda para a memória compartilhada |

O cache de contexto em 8 bits cai de 448 MB para 238 MB, mas o Ollama continua escolhendo 25 camadas (o reranker
ocupa o resto da placa); o ganho vem do flash attention com o cache menor.

**Regressões acadêmicas (qualidade):**
- F1 (`fase12_kv_q8`, 47 itens, com verificador): exatidão 0,923 → **0,949**; recusa correta 1,00 =; conflito 1,00 =;
  citação correta 0,954 =; alucinação numérica 0 =; precisão das citações 0,716 → 0,684.
- F2 (`fase12_f2_kv_q8`, 6 decisões): **p50 150 → 121 s (−19%)**, p95 185 → 187 s (1º item frio); RF-20 1,00 =;
  recall de documentos 0,639 =; precisão 0,511 → 0,517; schema bruto 1,00 → 0,857 (1 parecer reparado, reparado 1,00).

**Configuração do computador conferida:** plano de energia já em Alto desempenho; arquivo de paginação 47 GB
(gerenciado); driver NVIDIA 595.95 com limite de potência no máximo (125 W). A RAM livre baixa (1–2 GB de 15,7 GB) vem
de aplicativos do usuário (navegadores, Docker/WSL), não do SAD-GD — fechá-los é decisão do usuário.

**Ajuste fino dos modelos (treino):** não é viável nesta máquina com ganho mensurável — QLoRA de um 7B com contexto de
8 mil tokens não cabe em 6 GB na GTX 1660 (sem bf16), o golden set acadêmico tem 100 perguntas (superajuste e
vazamento entre validação e teste) e o acervo real não pode ser rotulado pelo agente. A "calibração" segue pelo ciclo
medir → ajustar → regressão (ADR do aprendizado: RAG + prompts + precedentes).

**Experimentos seguintes (mesma rodada):**

| Experimento | Resultado | Decisão |
|---|---|---|
| Repetição da F1 com a mesma configuração (`fase12_kv_q8b`) | Exatidão 0,923, recusa 1,00, citação 0,954, precisão das citações 0,700; **p50 9,7 s**. As 3 execuções idênticas deram p50 9,7 / 14,2 / 20,7 s com os mesmos tokens: a 1ª rodou com o modelo de teste de 28 camadas ainda residente | Latência da F1 depende da carga da máquina; qualidade estável (exatidão 0,92–0,95) |
| 2 aberturas por pergunta em vez de 3 (`fase12_ab2`) | Tokens de entrada 3.009 → 3.008 (sem efeito: o limite de 12 trechos já corta), exatidão 0,923 | Sem ganho |
| `OLLAMA_NUM_PARALLEL=2` (especialistas atendidos ao mesmo tempo) (`fase12_f2_par2`) | 24 camadas na GPU (KV dobrado); geração isolada 26,7 → 24,9 tok/s; **F2 p50 121 → 154 s**, recall de documentos 0,639 → 0,583 | Rejeitado (1 fila mantida) |

**Onde está o tempo da decisão** (`fase12_f2_kv_q8`, tempos por nó): o tempo de cada especialista inclui a espera na
fila do Ollama (os nós rodam em paralelo, o Ollama atende um por vez); na prática ≈ 32 s por especialista e ≈ 36 s no
relator, quase tudo leitura e geração do LLM. O nó `contexto_f2` de 30–65 s em 2 itens é artefato da avaliação
(`avaliar_f2.py` carrega bge-m3 e reranker dos precedentes na CPU; o servidor usa os modelos compartilhados, com o
reranker na GPU).

## 19. Rodada 16 — caminho real, aquecimento dos modelos e memória (2026-11-23)

**Avaliação pelo caminho do servidor** (fichas + escopo do contrato + busca ao vivo + verificador; banco acadêmico,
47 perguntas F1 da validação): exatidão **0,949** (as 2 "falhas" são de grafia na chave — "LTDA" sem ponto e "5 anos"
× "5 (cinco) anos"; adjudicadas, 47/47), classificação 0,979, recusa correta 1,00, **20/47 respondidas pela ficha
(≤ 50 ms)**, p50 1,8 s, p95 62 s. A regressão com recuperação em cache (`avaliar_respostas.py`) não passa pelas fichas
e subestima o sistema: V046/V048 ("até quando vigora após o aditivo?") erravam porque a cláusula com a nova data não
vinha entre os 10 trechos (cláusulas de prorrogação de outros contratos ocupavam o lugar); pelo caminho real a ficha
responde certo em 15 ms.

**Aquecimento dos modelos ao iniciar o servidor** (`app/infrastructure/modelos/aquecimento.py`): a 1ª busca após
cada reinício levava 24 s (bge-m3 na CPU + reranker na GPU); as seguintes, 1–2 s. O servidor agora carrega em segundo
plano o reranker (primeiro, para o Ollama dimensionar as camadas com ele já na GPU), o embedder e o LLM.
`SADGD_PRECARREGAR=0` desliga; testes (`create_app(auto_index=False)`) não disparam.

**Memória — causa do inchaço do `llama-server`:** o servidor interno do Ollama mantém um cache de prompts na RAM de
até **8 GB** (`prompt cache is enabled, size limit: 8192 MiB`), por isso passava de 12 GB após horas de uso.
`ollama.ps1` passa `LLAMA_ARG_CACHE_RAM=1024` (o Ollama não repassa a opção; o llama-server lê a variável). Teste
sintético com contexto comum de 4.470 tokens e 4 papéis alternados: 1ª leitura 34 s, as 7 seguintes **0,2 s** (o
reaproveitamento entre especialistas continua), processo estável em 5,6 GB.

**Arquivo de paginação:** o disco C: tem 5,1 GB livres e a paginação gerenciada pelo Windows (47 GB, no C:) não
consegue crescer — origem dos erros "arquivo de paginação muito pequeno" (1455) e CUDA OOM com a máquina carregada
(navegadores 8 GB + servidor 7,7 GB + llama-server 5,5 GB). Com a autorização do responsável: paginação adicional
**D:\pagefile.sys 16–32 GB** (C: continua gerenciado pelo sistema); vale após reiniciar o Windows. Reverter:
`AutomaticManagedPagefile=True` e remover a entrada do D:.
