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
