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
