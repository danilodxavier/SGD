# Conformidade com a especificação

Situação da aplicação em relação ao [`AGENTS.md`](../AGENTS.md) ao final da fase 14.

Verificação: `.venv\Scripts\python.exe -m pytest` (**238 testes**) e `aceitacao.bat` (**23 de 23** verificações:
os 21 critérios, o encerramento e o controle de acesso), ambos com documentos fictícios e sem usar dados do usuário.

## Critérios de conclusão (seção 48)

Todos conferidos automaticamente por `scripts\aceitacao.py`.

| Critério | Situação | Evidência |
|---|---|---|
| Instalar no Windows 11 | ✅ | `instalar.bat` (9 etapas); executado nesta máquina sem erros |
| Iniciar pelo `start.bat` | ✅ | `aceitacao.py`, `tests/test_app.py::test_iniciar_e_parar_servidor` |
| Abrir `http://127.0.0.1:8000` | ✅ | `aceitacao.py`, `tests/test_api.py::test_painel_servido` |
| Detectar o diretório documental | ✅ | `/health`, `tests/test_api.py::test_health` |
| Ler PDFs | ✅ | `tests/test_extraction.py` (texto, página, senha), OCR para digitalizados |
| Ler DOCX | ✅ | `tests/test_extraction.py::test_docx_identifica_secoes` |
| Ler XLSX | ✅ | `tests/test_extraction.py::test_xlsx_le_planilha` |
| Indexar documentos | ✅ | `tests/test_search.py` (inicial, incremental, alteração, remoção), `tests/test_scripts.py` (300 documentos) |
| Pesquisar documentos | ✅ | `tests/test_search.py` (CNPJ, nº de contrato, acentos) |
| Responder perguntas | ✅ | `tests/test_search.py`, `tests/test_questions.py`, `tests/test_ai.py` |
| Apresentar fontes | ✅ | Documento, página, seção e trecho em cada resposta; testes de fontes |
| Detectar informação ausente | ✅ | `test_informacao_ausente`, `test_contrato_inexistente`, `test_clausula_inexistente_continua_ausente` |
| Detectar conflitos | ✅ | `test_valor_conflitante`, `tests/test_reports.py::test_relatorio_conflitos_mostra_os_dois_valores` |
| Identificar contratos | ✅ | `tests/test_contracts.py`, `/api/contracts` |
| Identificar itens | ✅ | `tests/test_items.py` (XLSX com células vazias, DOCX, CSV) |
| Processar checklist | ✅ | `tests/test_checklist.py` (os 8 status) |
| Organizar documentos virtualmente | ✅ | `test_organizacao_virtual` |
| Gerar relatório | ✅ | `tests/test_reports.py` (6 relatórios × 5 formatos) |
| Executar diagnóstico | ✅ | `tests/test_app.py::test_diagnostico_em_processo`, `tests/test_scripts.py::test_diagnostico` |
| Registrar logs | ✅ | `aceitacao.py` confere indexação e consultas em `data\logs\app.log` |
| Preservar documentos originais | ✅ | Hash de todos os arquivos antes/depois (indexação, OCR, checklist, aceitação) |

## Testes exigidos (seção 39)

| Item | Arquivo de teste |
|---|---|
| 1. PDF | `test_extraction.py` — texto por página, seção, corrompido, protegido por senha |
| 2. DOCX | `test_extraction.py`, `test_items.py` (tabelas) |
| 3. XLSX | `test_extraction.py`, `test_items.py` (colunas preservadas) |
| 4. TXT | `test_extraction.py` — UTF-8, cp1252, Markdown, CSV |
| 5. OCR | `test_ocr.py` — PDF digitalizado, imagens, TIFF multipágina, limpeza do cache, OCR real do Windows |
| 6. Indexação | `test_search.py`, `test_scripts.py`, `test_database.py` |
| 7. Busca | `test_search.py` |
| 8. Contrato | `test_contracts.py`, `test_questions.py` |
| 9. Aditivo | `test_search.py::test_encerramento_considera_aditivo`, `test_aditivos`, `test_questions.py` |
| 10. Conflito | `test_search.py::test_valor_conflitante`, `test_ai.py::test_conflito_exige_todos_os_valores` |
| 11. Informação ausente | `test_search.py`, `test_questions.py` |
| 12. Checklist | `test_checklist.py` |
| 13. Duplicidade | `test_search.py::test_duplicidade`, citações sem cópias repetidas |
| 14. API | `test_api.py`, `test_app.py`, rotas cobertas em cada módulo |
| 15. Banco de dados | `test_database.py` — esquema, migração sem perda, cascatas, reindexação sem duplicar |

Também: formatos legados com arquivos reais salvos pelo Microsoft Office (`test_legacy.py` — DOC, XLS, PPT, PPTX,
RTF, ODT, ODS, arquivos com senha, `.doc`/`.xls` disfarçados, proteção contra zip bomb), relatórios
(`test_reports.py`), IA com alucinações simuladas (`test_ai.py`), scripts e desempenho (`test_scripts.py`), ciclo de
vida do servidor (`test_app.py`).

## Seções da especificação

| Seção | Situação |
|---|---|
| 2, 15, 38 — fonte de verdade, ausência, proibição de alucinação | ✅ Respostas por regras; IA validada contra os trechos; frase padrão de ausência |
| 3, 4, 42 — Windows, simplicidade, sem Node/Docker/WSL | ✅ Python + FastAPI + SQLite + HTML/JS; scripts `.bat` e PowerShell |
| 5 — estrutura do projeto | ✅ Semelhante à sugerida (ver [ARQUITETURA.md](ARQUITETURA.md)) |
| 6, 44 — diretório configurável | ✅ Painel, `.env` e linha de comando |
| 7 — formatos suportados | ✅ Todos os listados: PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, MD, RTF, PPTX, PPT, ODS, ODT, JPG, JPEG, PNG, TIFF (imagens por OCR) |
| 8, 31, 36 — leitura e indexação incremental | ✅ Hash, páginas, seções, trechos, sem reprocessar inalterados |
| 9 — banco de dados | ✅ Todas as tabelas e campos mínimos (e alguns adicionais) |
| 10 — busca híbrida | ⚠️ Textual e filtros estruturados; sem busca semântica (opcional na especificação) |
| 11, 12, 13 — perguntas, resposta humanizada, fontes | ✅ |
| 14, 37 — conflitos, fato/inferência/conflito/ausência | ✅ |
| 16 — extração de contratos | ✅ Campos estruturados + cláusulas (pagamento, penalidades, rescisão…) transcritas literalmente |
| 17, 18, 19 — checklist, status, organização virtual | ✅ |
| 20, 21 — duplicidades e documentos relacionados | ✅ |
| 22, 46 — painel e experiência | ✅ Seis abas, português, mensagens compreensíveis |
| 23, 24, 25 — IA opcional, privacidade, segurança | ✅ Somente LLM local; LOCAL ONLY; 127.0.0.1 por padrão; acesso pela rede somente por solicitação expressa (decisão do usuário), com login, perfis e lista de computadores autorizados; sem telemetria |
| 26–30 — configuração, instalação, execução, diagnóstico, `/health` | ✅ |
| 32, 33 — logs e backup | ✅ |
| 34 — exportação | ✅ PDF, DOCX, XLSX, CSV, JSON |
| 35 — tratamento de erros | ✅ Sem traceback ao usuário; detalhes no log |
| 43, 45 — sandbox e não destruição | ✅ Nenhuma configuração de sistema alterada; originais apenas lidos |
| 47 — README | ✅ Os 14 tópicos |

## Limitações conhecidas

1. **Formatos legados:** arquivos do Word anteriores à versão 97 (Word 6/95) não são lidos; em DOC são lidos o corpo e
   as tabelas (cabeçalhos, rodapés e notas não); em PPT/PPTX, os slides (anotações e mestres não). Arquivos com senha
   são registrados como protegidos, sem tentativa de abertura.
2. **Extração por padrões textuais:** contratos com redação muito diferente do usual podem resultar em *Trechos
   localizados* ou *informação não localizada* — nunca em dado inventado.
3. **Itens contratados** são lidos de planilhas (XLSX, XLS, ODS, CSV) e de tabelas de DOCX, DOC, RTF e ODT; tabelas
   dentro de PDF não são estruturadas (aparecem como trechos).
4. **Cláusulas** são reconhecidas pelo título da seção (ex.: "DO PAGAMENTO"); cláusulas sem título não são
   identificadas como tema.
5. **OCR:** a qualidade depende da digitalização; o OCR do Windows não informa confiança por palavra (ex.: "nº" pode
   ser lido como "no"). Por isso todo uso de texto de OCR é sinalizado e limitado a confiança média.
6. **IA opcional:** validada com um servidor simulado; nenhum modelo real foi instalado nesta máquina. A validação
   confere datas, valores, CNPJ, números e citações; nomes e frases são orientados pelas regras e citações, mas não
   conferidos palavra a palavra.
7. **Busca semântica** (seção 10, segunda camada, opcional) não foi implementada.
8. **Interface web** não tem testes automatizados de navegador; o JavaScript é verificado por sintaxe e a API por
   testes. Recomenda-se uma conferência visual após atualizações.

## Decisões que divergem de uma leitura literal

| Tema | Decisão | Motivo |
|---|---|---|
| Status DUPLICADO | Requisito repetido no próprio checklist | Marcar o item como duplicado por haver cópias de arquivo esconderia que ele está atendido; as cópias são informadas na justificativa. |
| Pasta do projeto | Pasta atual em vez de `D:\AgenteDocumental` | Escolha do usuário (caminhos são exemplos na seção 44). |
| IA externa | Somente LLM local | Escolha do usuário na fase 13; endereços externos bloqueados por padrão. |
| Contrato “assinado” | ATENDIDO com confiança média quando só há local e data no fecho | O texto não comprova as assinaturas; o original deve ser conferido. |
