# Agente de Inteligência Documental — Contratos e Checklists

Aplicação local para Windows 11 que lê os documentos de um diretório, monta um índice pesquisável e responde
perguntas sobre contratos **exclusivamente com base nos documentos**, sempre citando as fontes. Também avalia
checklists, organiza virtualmente os documentos que os atendem e gera relatórios.

- **Manual do Usuário:** [`docs/MANUAL_DO_USUARIO.md`](docs/MANUAL_DO_USUARIO.md)
- **Manual Técnico de Manutenção e Migração:** [`docs/MANUAL_TECNICO.md`](docs/MANUAL_TECNICO.md)
- Especificação do agente: [`AGENTS.md`](AGENTS.md)
- Arquitetura e decisões técnicas: [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md)
- Conformidade com a especificação (critérios, testes, limitações): [`docs/CONFORMIDADE.md`](docs/CONFORMIDADE.md)

**Sumário:** 1. Objetivo · 2. Requisitos · 3. Instalação · 4. Configuração · 5. Diretório documental ·
6. Inicialização · 7. Acesso ao painel · 8. Indexação e OCR · 9. Perguntas e IA opcional · 10. Checklist e relatórios ·
11. Backup · 12. Solução de problemas · 13. Atualização · 14. Desinstalação · Testes e verificação · Segurança

---

## 1. Objetivo

- Indexar os documentos de um diretório local (ex.: `D:\Documentos`), inclusive digitalizados (OCR).
- Responder perguntas como *"Quando encerra o contrato 034/2022?"* com documento, página, seção e trecho.
- Classificar cada resposta em **Fato documental**, **Inferência documental**, **Conflito** ou
  **Informação ausente** — sem evidência, a resposta é *"Não localizei essa informação nos documentos
  disponibilizados."*
- Detectar conflitos entre documentos, aditivos que alteram vigência e valor, duplicidades e documentos vencidos.
- Avaliar checklists, organizar virtualmente os documentos e exportar relatórios (PDF, DOCX, XLSX, CSV, JSON).
- **Nunca** mover, renomear, alterar ou excluir os documentos originais. Por padrão, **nada sai da máquina**.

Todas as 14 fases da especificação foram implementadas. Limitações conhecidas estão em
[`docs/CONFORMIDADE.md`](docs/CONFORMIDADE.md#limitações-conhecidas).

## 2. Requisitos

- Windows 11 (64 bits) com PowerShell (nativo)
- Python 3.10 ou superior no PATH (testado com 3.15) — <https://www.python.org/downloads/>
- Navegador (Edge, Chrome ou Firefox)
- Para OCR: idioma Português (Brasil) no Windows (normalmente já instalado)
- Não requer Node.js, Docker, WSL nem serviços em nuvem.

## 3. Instalação

1. Copie a pasta do projeto para o computador (ex.: `D:\AgenteDocumental`).
2. Dê um duplo clique em **`instalar.bat`**, que: verifica Windows e Python → cria o ambiente virtual `.venv` →
   cria `data\` → instala `requirements.txt` → cria `.env` (se não existir) → testa importações, SQLite e FastAPI →
   executa o diagnóstico.
3. (Opcional) Dê um duplo clique em **`aceitacao.bat`** para conferir os critérios de conclusão com documentos
   fictícios (seus dados não são usados).

## 4. Configuração

As configurações ficam no arquivo `.env` (criado a partir de `.env.example`). Diretório documental, OCR e mecanismo de
respostas também podem ser alterados no painel, que prevalece sobre o `.env`.

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | Endereço do painel. Não use `0.0.0.0`: exporia o painel na rede. |
| `APP_PORT` | `8000` | Porta do painel. |
| `DOCUMENTS_ROOT` | `D:\Documentos` | Diretório documental inicial. |
| `DATABASE_PATH` | `.\data\database\documents.db` | Banco SQLite. |
| `DATA_DIR` | `.\data` | (Opcional) Pasta de trabalho: banco, logs, cache, relatórios e backups. |
| `LOG_LEVEL` | `INFO` | Nível de log. |
| `AUTO_INDEX` | `true` | Indexação incremental automática ao iniciar. |
| `OCR_ENABLED` | `true` | Ativa o OCR. |
| `OCR_ENGINE` | `auto` | `auto` (Windows, depois Tesseract), `windows` ou `tesseract`. |
| `OCR_LANGUAGE` | `pt-BR` | Idioma do OCR do Windows. |
| `OCR_DPI` / `OCR_MAX_PAGES` | `200` / `50` | Resolução das páginas de PDF digitalizado e limite de páginas por documento. |
| `TESSERACT_CMD` / `TESSERACT_LANG` | vazio / `por` | Tesseract opcional (se instalado pela TI). |
| `AI_PROVIDER` | `local` | `local` (somente documentos) ou `llm_local` (LLM local). |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | Servidor do LLM local (Ollama; LM Studio usa a porta 1234). |
| `LLM_MODEL` | vazio | Modelo (ex.: `qwen2.5:7b`). |
| `LLM_TIMEOUT` / `LLM_MAX_PASSAGES` | `120` / `8` | Tempo limite (s) e máximo de trechos enviados ao modelo. |
| `AI_ALLOW_REMOTE` | `false` | Mantém o modo LOCAL ONLY. Só altere com autorização institucional. |
| `OPENAI_API_KEY` | vazio | Reservado (não utilizado). Nunca grave chaves reais no repositório. |

## 5. Diretório documental

Em **Configurações → Diretório documental**, digite o caminho ou clique em **Selecionar pasta…** e em **Salvar**.
O sistema verifica existência, permissão de leitura, subdiretórios, arquivos não suportados, corrompidos,
duplicados e alterados desde a última indexação.

| Formato | Situação |
|---|---|
| PDF com texto, DOCX, XLSX/XLSM, TXT, MD, CSV | Lidos |
| DOC, XLS e PPT (Office 97-2003), PPTX, RTF, ODT, ODS | Lidos sem precisar do Microsoft Office (PPT/PPTX: um trecho por slide) |
| `.doc`/`.xls` que na verdade são RTF ou HTML (exportações de sistemas) | Lidos pelo conteúdo real |
| PDF digitalizado, JPG, JPEG, PNG, TIFF | Lidos por OCR (quando ativado) |
| Arquivos protegidos por senha | Registrados como *corrompido/protegido*, com o motivo |

Itens contratados são identificados em planilhas (XLSX, XLS, ODS, CSV) e em tabelas de documentos (DOCX, DOC, RTF, ODT).

Cada documento recebe um status: *com texto*, *escaneado*, *com OCR*, *sem texto extraível*, *corrompido/protegido*,
*formato não suportado* ou *removido do diretório*.

**Para experimentar sem documentos reais:** `.venv\Scripts\python.exe scripts\gerar_exemplos.py` cria documentos
**fictícios** em `exemplos\documentos` (contrato, aditivo, planilha de itens, certidões, portaria digitalizada, um
resumo com valor divergente, uma cópia duplicada, um PDF corrompido, uma imagem inválida e, em `Legados`, um contrato
em DOC/RTF/ODT, planilhas XLS/ODS, apresentações PPT/PPTX e dois arquivos protegidos por senha).

## 6. Inicialização

| Arquivo | Função |
|---|---|
| `start.bat` | Inicia o servidor e abre o navegador. Mantenha a janela aberta. |
| `servidor.bat` | Inicia sem janela nem navegador, para o início automático pelo Agendador de Tarefas (Manual Técnico, 5.8). |
| `stop.bat` | Encerra o servidor de forma controlada. |
| `diagnostico.bat` | Verifica Windows, Python, pip, venv, SQLite, permissões, diretório documental, espaço em disco, FastAPI, Uvicorn, bibliotecas, OCR, mecanismo de respostas, banco de dados e porta 8000 (`[OK]`, `[WARNING]`, `[ERRO]`). |
| `aceitacao.bat` | Confere os critérios de conclusão da especificação com documentos fictícios. |
| `backup.bat` | Cria um backup na pasta `BACKUP` do projeto, mantendo os 30 mais recentes (pode ser agendado). |
| `usuarios.bat` | Gestão de usuários pela linha de comando (recuperar o acesso de administrador). |

## 7. Acesso ao painel

<http://127.0.0.1:8000> — saúde: <http://127.0.0.1:8000/health> — API (administradores): <http://127.0.0.1:8000/api/docs>

**Login e perfis.** Todo acesso exige usuário e senha. No primeiro uso, abra o painel **no computador onde o sistema
está instalado**: aparecerá a tela *Configuração inicial* para criar o primeiro administrador. Depois, os
administradores cadastram os demais usuários na aba **Usuários** (com senha temporária, trocada no primeiro acesso).

| Perfil | Pode | Não pode |
|---|---|---|
| **Administrador** | Tudo: usuários, configurações, indexação, OCR, IA, logs, diagnóstico | — |
| **Consulta** | Painel, perguntas, documentos (ver e baixar), checklists (criar, executar, exportar; alterar/excluir os próprios), relatórios | Usuários, configurações, indexação, reindexar documentos |

Após 5 senhas erradas seguidas a conta fica bloqueada por 15 minutos (ou até um administrador desbloquear). A sessão
expira em 8 horas (`SESSION_HOURS`). "Abrir no Windows" e "Selecionar pasta…" só aparecem no próprio computador do
sistema.

**Acesso pela rede.** Por padrão o sistema só aceita o próprio computador (`APP_HOST=127.0.0.1`). Para liberar outros
computadores da rede interna, a TI define `APP_HOST=0.0.0.0`, ajusta `ALLOWED_CLIENTS`/`ALLOWED_HOSTS`, libera a porta
no Firewall do Windows e, de preferência, configura HTTPS (`SSL_CERTFILE`/`SSL_KEYFILE`). O passo a passo está no
[`docs/MANUAL_TECNICO.md`](docs/MANUAL_TECNICO.md).

| Aba | Recursos |
|---|---|
| **Painel** | Documentos encontrados, indexados, com erro, sem texto; contratos identificados; checklists; última atualização; status do indexador. |
| **Perguntas** | Caixa de perguntas; resposta, tipo, confiança, conflitos, fontes (*Visualizar* abre o PDF na página citada; *Abrir no Windows*); exportação. |
| **Documentos** | Busca e filtros (status, tipo), metadados, abrir, reindexar, duplicidades, exportar inventário. |
| **Checklist** | Inserir ou carregar de arquivo, salvar, executar, filtrar por status, organização virtual, exportar. |
| **Relatórios** | Todos os relatórios e a lista dos já gerados. |
| **Configurações** | Diretório documental, indexação, verificação do sistema, OCR, mecanismo de respostas (IA), logs. |

## 8. Indexação e OCR

A indexação pode ser automática (ao iniciar), pelo painel (**Atualizar índice** / **Reindexar tudo**) ou por comando:

```bat
.venv\Scripts\python.exe scripts\indexar.py
.venv\Scripts\python.exe scripts\indexar.py --forcar
.venv\Scripts\python.exe scripts\indexar.py --raiz "D:\Outro diretorio"
```

```text
Arquivos encontrados: 1250
Arquivos novos: 17
Arquivos alterados: 8
Arquivos inalterados: 1220
Arquivos removidos: 0
Documentos com OCR: 3
Erros: 5
```

É **incremental**: arquivos com mesmo tamanho e data de modificação não são reprocessados; arquivos apagados do
diretório são marcados como removidos. Durante a indexação também são identificados os contratos (número, processo,
contratada, CNPJ, objeto, valor, vigência, assinatura) e os **itens** das planilhas e tabelas.

**OCR (documentos digitalizados).** Reconhece o texto de PDFs digitalizados e de imagens JPG, PNG e TIFF, na própria
máquina, com o **OCR nativo do Windows** (sem instalação) ou, opcionalmente, o Tesseract. Em **Configurações → OCR**:
ativar, escolher o mecanismo, **Testar OCR** e **Reprocessar digitalizados**. Textos obtidos por OCR são sinalizados:
as respostas e itens de checklist que os usam exibem *"confira no documento original"* e têm confiança limitada a
**média**. As imagens intermediárias ficam em `data\cache` e são apagadas em seguida.

## 9. Perguntas e IA opcional

Perguntas reconhecidas: encerramento, início e vigência; valor e valor atualizado; objeto; contratada e CNPJ;
data de assinatura; processo; termos aditivos e último aditivo; itens; documentos que comprovam a vigência;
documentos relacionados. Perguntas livres retornam os trechos mais pertinentes.

| Tipo de resposta | Quando |
|---|---|
| **Fato documental** | O valor aparece explicitamente e os documentos concordam. |
| **Inferência documental** | Um documento posterior (ex.: termo aditivo) altera outro; ambos são mostrados com o aviso *"Esta conclusão decorre da relação entre os documentos localizados."* |
| **Conflito** | Documentos equivalentes divergem; nada é escolhido automaticamente e todos os valores são exibidos. |
| **Informação ausente** | *"Não localizei essa informação nos documentos disponibilizados."* |
| **Trechos localizados** | Pergunta livre sem resposta estruturada: os trechos são apresentados para conferência. |

Sem número de contrato na pergunta, o único contrato existente é considerado (com aviso); havendo vários, a resposta
lista os valores por contrato e pede o número.

**IA opcional (LLM local).** Um modelo rodando na própria máquina pode redigir as respostas a partir dos trechos.
Exemplo com Ollama:

```bat
winget install Ollama.Ollama
ollama pull qwen2.5:7b
```

Em **Configurações → Mecanismo de respostas**: *LLM local*, endereço `http://127.0.0.1:11434/v1`, **Listar modelos**,
escolha o modelo, **Salvar** e **Testar conexão**. Salvaguardas: o mecanismo local responde primeiro; o modelo recebe
apenas os trechos da pergunta, numerados, com regras rígidas; a resposta só é aceita se citar apenas trechos
existentes, se **toda data, valor, CNPJ, nº de contrato e número** constar dos trechos e se, havendo conflito,
apresentar todos os valores — caso contrário vale a resposta local, com aviso. Endereços fora de `127.0.0.1` são
recusados (LOCAL ONLY); se um dia autorizados, CPF, e-mail e telefone são mascarados antes do envio.

## 10. Checklist e relatórios

Na aba **Checklist**: informe um nome e, se quiser, o contrato (ex.: `034/2022` — a busca se restringe aos documentos
dele e aos que citam o CNPJ da contratada). Cole os requisitos, um por linha, ou **Carregar de arquivo…** (TXT, MD,
CSV, DOCX, XLSX, PDF). Aceita numeração (`1.`, `1)`, `a)`, `ITEM 01`), marcadores (`-`, `•`, `[ ]`) e linhas de
planilha; linhas em maiúsculas ou terminadas em `:` viram grupos; *(obrigatório)* e *(se houver)* definem a prioridade.
Clique em **Salvar e executar**.

| Status | Quando |
|---|---|
| **ATENDIDO** | Há documento do tipo exigido e as verificações do item passam (assunto, assinatura, validade). |
| **PARCIALMENTE ATENDIDO** | Parte do requisito foi comprovada (ex.: FGTS sim, INSS não). |
| **AUSENTE** | O tipo de documento exigido é conhecido e não foi localizado. |
| **DÚVIDA** | Evidência fraca: documento não trata do assunto, sem texto (digitalizado sem OCR), datas divergentes. |
| **DUPLICADO** | Requisito repetido no checklist (avaliado uma vez). Arquivos idênticos são informados na justificativa. |
| **VENCIDO** | Validade da certidão ou vigência do contrato terminou antes da data da avaliação. |
| **INCOMPATÍVEL** | Há documento do tipo, mas de outro contrato ou CNPJ. |
| **NÃO IDENTIFICADO** | Requisito livre sem evidência (não se afirma a ausência) ou texto não interpretável. |

A **organização virtual** agrupa os documentos que comprovam os itens (Contrato, Termos Aditivos, Fiscalização,
Comprovação de Regularidade…) e lista itens sem documento e a conferir. **Nenhum arquivo é copiado ou movido.**

**Relatórios** (aba Relatórios ou botões de exportação nas abas):

| Relatório | Conteúdo |
|---|---|
| Resultado da consulta | Pergunta, tipo, confiança, mecanismo, resposta, conflitos, trechos e fontes. |
| Inventário documental | Todos os documentos com pasta, tipo, status, contrato, páginas, tamanho e observações. |
| Checklist | Resumo por status, itens com justificativa e evidências, organização virtual, pendências. |
| Documentos ausentes | Itens ausentes, vencidos ou incompletos e arquivos que saíram do diretório. |
| Conflitos documentais | Valores divergentes por contrato (com fontes) e alterações por termo aditivo. |
| Contratos identificados | Dados de cada contrato, situação após aditivos e itens contratados. |

Formatos: **PDF**, **DOCX**, **XLSX**, **CSV** (separador `;`) e **JSON**; o checklist também em TXT. Cada relatório
fica salvo em `data\reports\`. Textos dos documentos nunca são interpretados como fórmulas nas planilhas.

## 11. Backup

Dê um duplo clique em **`backup.bat`** (ou agende-o no Agendador de Tarefas do Windows). Ele gera
`BACKUP\backup_AAAAMMDD_HHMMSS.zip` com banco (inclusive usuários), índice, configurações e relatórios, mantendo os 30
mais recentes. **Os documentos originais não são incluídos** — permanecem no diretório documental.

Para restaurar (com o sistema parado):

```bat
.venv\Scripts\python.exe scripts\restaurar.py --arquivo "BACKUP\backup_AAAAMMDD_HHMMSS.zip"
```

O banco atual é guardado antes (`documents.db.antes_restauracao_...`), permitindo desfazer.

## 12. Solução de problemas

| Sintoma | Ação |
|---|---|
| "Python não encontrado" | Instale o Python marcando *Add python.exe to PATH*; reabra o terminal. |
| Esqueci a senha / conta bloqueada | Um administrador usa **Redefinir senha** ou **Desbloquear** na aba Usuários. Sem administrador disponível: `usuarios.bat redefinir-senha --usuario NOME` no computador do sistema. |
| "Este computador não está autorizado" | O IP do computador está fora de `ALLOWED_CLIENTS`; ajuste no `.env` (Manual Técnico). |
| Painel não abre | Execute `diagnostico.bat`. Porta 8000 em uso: rode `stop.bat` ou altere `APP_PORT`. |
| "Diretório documental indisponível" | Verifique o caminho em Configurações e a permissão de leitura. |
| Documento "escaneado / sem texto" | Ative o OCR e clique em **Reprocessar digitalizados**. Sem mecanismo disponível, instale o idioma Português (Brasil) em Configurações do Windows > Hora e idioma. |
| Documento "corrompido / protegido" | Verifique se o original tem senha ou está danificado. |
| Resposta incompleta ou "Trechos localizados" | Confira as fontes; reformule citando o nº do contrato; reindexe o documento em Documentos → Detalhes. |
| "IA indisponível" | Verifique se o Ollama/LM Studio está em execução e se o modelo está instalado (Configurações → Testar conexão). |
| Detalhes técnicos | `data\logs\app.log` (também em Configurações → Logs). |

Se o antivírus ou o sandbox bloquear a execução, informe a equipe de TI; não desative mecanismos de segurança.

## 13. Atualização

1. Rode `stop.bat`.
2. Substitua os arquivos do projeto, **preservando** `.env` e a pasta `data\`.
3. Rode `instalar.bat` (atualiza dependências; o `.env` existente é mantido; o banco é migrado automaticamente).
4. Rode `start.bat` e, se necessário, **Reindexar tudo**.

## 14. Desinstalação

1. Rode `stop.bat`.
2. (Opcional) Faça backup com `scripts\backup.py`.
3. Apague a pasta do projeto — remove apenas a aplicação, o índice e os logs. **Os documentos originais não são
   afetados.** Se usou IA local, desinstale o Ollama/LM Studio pelo Windows, se desejar.

---

## Testes e verificação

```bat
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\aceitacao.py
```

- **238 testes automatizados**, apenas com documentos fictícios em pastas temporárias (`tests\sample_docs.py`).
  Os testes de OCR real rodam somente se o OCR do Windows estiver disponível.
- **Verificação de aceitação**: confere os 21 critérios de conclusão da especificação, o encerramento pelo
  `stop.bat` e o controle de acesso (23 verificações), sem usar os dados do usuário.

O mapa completo critério → implementação → teste está em [`docs/CONFORMIDADE.md`](docs/CONFORMIDADE.md).

## Segurança e privacidade

- Todo acesso exige login; senhas guardadas apenas como hash PBKDF2; sessão em cookie HttpOnly/SameSite=Strict;
  bloqueio após tentativas erradas; perfis Administrador e Consulta.
- Por padrão o painel escuta somente em `127.0.0.1`. No acesso pela rede, só computadores das faixas de
  `ALLOWED_CLIENTS` e nomes conhecidos (`ALLOWED_HOSTS`) são aceitos (proteção contra DNS rebinding).
- Operações que alteram estado exigem um cabeçalho próprio do painel, impedindo que outros sites acionem a API.
- Sem HTTPS, a senha trafega sem criptografia na rede interna: configure `SSL_CERTFILE`/`SSL_KEYFILE` no acesso pela rede.
- Nenhum documento é enviado para a Internet; não há telemetria. A IA opcional só aceita servidores locais.
- Os logs registram eventos e metadados, não o conteúdo dos documentos.
- O OCR do Windows é chamado com um script da própria aplicação, sem alterar políticas de execução do sistema.
