# AGENTE DE INTELIGÊNCIA DOCUMENTAL — CONTRATOS E CHECKLISTS

## 1. IDENTIDADE E OBJETIVO

Você é um agente de desenvolvimento de software responsável por construir, testar, documentar e manter uma aplicação local de **Inteligência Documental para Gestão de Contratos, Processos Administrativos e Checklists**.

A aplicação será executada **diretamente em uma máquina Windows 11**, em ambiente local, com os documentos armazenados em diretórios do computador, especialmente em unidades como `D:`.

O sistema deverá:

1. Ler documentos de um diretório configurado pelo usuário;
2. Indexar e organizar o conteúdo documental;
3. Permitir consultas em linguagem natural;
4. Responder perguntas sobre contratos e documentos;
5. Apresentar as fontes utilizadas para cada resposta;
6. Nunca inventar informações ausentes dos documentos;
7. Detectar conflitos entre documentos;
8. Permitir inserção de checklists pelo painel;
9. Relacionar os documentos existentes aos requisitos do checklist;
10. Apresentar os documentos organizados para atendimento do checklist;
11. Permitir exportação de resultados;
12. Funcionar localmente, preferencialmente sem depender de serviços externos;
13. Ser simples de instalar, executar, atualizar e manter no Windows 11.

---

# 2. REGRA FUNDAMENTAL

## DOCUMENTOS LOCAIS SÃO A FONTE DE VERDADE

Toda informação factual apresentada ao usuário sobre contratos, processos, valores, datas, objetos, obrigações, itens, vigências, aditivos, fornecedores ou qualquer outro assunto documental deverá ser baseada exclusivamente nos documentos existentes no diretório configurado para análise.

O agente NÃO deve:

- inventar informações;
- completar informações por conhecimento externo;
- presumir datas;
- presumir valores;
- presumir cláusulas;
- tratar conhecimento jurídico genérico como se estivesse nos documentos;
- escolher arbitrariamente entre documentos conflitantes;
- apresentar inferência como fato documental.

Quando a informação não for localizada, responder claramente:

> "Não localizei essa informação nos documentos disponibilizados."

Quando houver documentos conflitantes:

> "Foram identificadas informações divergentes entre os documentos. A aplicação apresenta as fontes e os respectivos conteúdos para conferência."

---

# 3. AMBIENTE DE EXECUÇÃO

A aplicação será desenvolvida e executada em:

- Windows 11 Pro 64 bits;
- PowerShell;
- Python 3.x;
- navegador local;
- armazenamento local;
- unidade `D:` para o projeto e/ou documentos.

O Codex será executado diretamente na máquina Windows.

NÃO presumir:

- Linux;
- WSL;
- Docker;
- Kubernetes;
- Node.js;
- npm;
- Vite;
- React;
- servidores Linux;
- infraestrutura em nuvem.

A arquitetura deve funcionar nativamente no Windows.

---

# 4. PRINCÍPIO DE SIMPLICIDADE

Não adicionar dependências desnecessárias.

A primeira versão deverá funcionar sem Node.js.

A arquitetura preferencial será:

```text
Windows 11
    │
    ├── Python
    │
    ├── FastAPI
    │
    ├── Uvicorn
    │
    ├── SQLite
    │
    ├── HTML
    ├── CSS
    └── JavaScript puro
```

O frontend deverá ser servido pelo próprio FastAPI.

Não utilizar React, Vite, Next.js ou outro framework frontend na primeira versão, salvo justificativa técnica concreta.

---

# 5. ESTRUTURA DO PROJETO

Criar estrutura semelhante a:

```text
D:\AgenteDocumental\
│
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── start.bat
├── stop.bat
├── instalar.bat
├── diagnostico.bat
│
├── app\
│   ├── main.py
│   │
│   ├── api\
│   │   ├── routes_documents.py
│   │   ├── routes_search.py
│   │   ├── routes_questions.py
│   │   ├── routes_checklist.py
│   │   └── routes_system.py
│   │
│   ├── core\
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── ingestion\
│   │   ├── scanner.py
│   │   ├── extractor.py
│   │   ├── pdf.py
│   │   ├── docx.py
│   │   ├── xlsx.py
│   │   ├── pptx.py
│   │   ├── images.py
│   │   └── ocr.py
│   │
│   ├── indexing\
│   │   ├── indexer.py
│   │   ├── metadata.py
│   │   ├── chunks.py
│   │   └── duplicates.py
│   │
│   ├── retrieval\
│   │   ├── search.py
│   │   ├── ranking.py
│   │   └── citations.py
│   │
│   ├── contracts\
│   │   ├── extractor.py
│   │   ├── entities.py
│   │   └── validation.py
│   │
│   ├── checklist\
│   │   ├── parser.py
│   │   ├── matcher.py
│   │   ├── organizer.py
│   │   └── report.py
│   │
│   └── services\
│       ├── documents.py
│       ├── questions.py
│       ├── checklist.py
│       └── reports.py
│
├── frontend\
│   ├── index.html
│   ├── css\
│   │   └── app.css
│   └── js\
│       ├── app.js
│       ├── search.js
│       ├── checklist.js
│       └── documents.js
│
├── data\
│   ├── database\
│   ├── index\
│   ├── cache\
│   ├── logs\
│   └── reports\
│
├── tests\
│   ├── test_extraction.py
│   ├── test_search.py
│   ├── test_contracts.py
│   ├── test_checklist.py
│   └── test_api.py
│
└── scripts\
    ├── indexar.py
    ├── diagnostico.py
    └── backup.py
```

---

# 6. DIRETÓRIO DOS DOCUMENTOS

O diretório contendo os documentos analisados deverá ser configurável.

Não gravar documentos originais dentro de `data`.

Por padrão, utilizar uma configuração semelhante a:

```text
DOCUMENTS_ROOT=D:\Documentos
```

O usuário deverá poder alterar esse caminho pelo painel.

O sistema deverá verificar:

- existência do diretório;
- permissões de leitura;
- quantidade de arquivos;
- subdiretórios;
- arquivos não suportados;
- arquivos corrompidos;
- arquivos duplicados;
- arquivos alterados desde a última indexação.

---

# 7. DOCUMENTOS SUPORTADOS

Implementar suporte prioritário para:

```text
PDF
DOCX
DOC
XLSX
XLS
CSV
TXT
MD
RTF
PPTX
PPT
ODS
ODT
JPG
JPEG
PNG
TIFF
```

Quando tecnicamente possível, implementar OCR para documentos digitalizados.

O sistema deverá diferenciar:

```text
DOCUMENTO COM TEXTO
DOCUMENTO ESCANEADO
DOCUMENTO COM OCR
DOCUMENTO SEM TEXTO EXTRAÍVEL
DOCUMENTO CORROMPIDO
FORMATO NÃO SUPORTADO
```

---

# 8. LEITURA DOS DOCUMENTOS

A indexação deverá:

1. localizar arquivos recursivamente;
2. calcular hash do arquivo;
3. identificar extensão;
4. registrar tamanho;
5. registrar data de modificação;
6. extrair texto;
7. identificar páginas, quando possível;
8. identificar tabelas, quando possível;
9. identificar títulos e seções;
10. registrar metadados;
11. dividir o conteúdo em trechos pesquisáveis;
12. armazenar referência precisa ao documento original.

Não reprocessar arquivos que não foram modificados, salvo solicitação expressa.

---

# 9. BANCO DE DADOS

Utilizar SQLite inicialmente.

Registrar pelo menos:

### documents

- id
- filename
- full_path
- extension
- size
- hash
- modified_at
- indexed_at
- status
- mime_type

### document_chunks

- id
- document_id
- chunk_number
- text
- page
- section
- start_offset
- end_offset

### contracts

- id
- contract_number
- process_number
- contractor
- cnpj
- object
- value
- signature_date
- start_date
- end_date
- term
- source_document_id

### contract_items

- id
- contract_id
- item_number
- description
- quantity
- unit
- unit_value
- total_value
- source_document_id

### checklist

- id
- name
- created_at

### checklist_items

- id
- checklist_id
- description
- requirement
- priority

### checklist_matches

- id
- checklist_item_id
- document_id
- status
- confidence
- justification

---

# 10. PESQUISA DOCUMENTAL

Implementar busca híbrida.

Primeira camada:

- busca textual;
- palavras-chave;
- frases;
- números de contrato;
- números de processo;
- CNPJ;
- nomes;
- datas;
- valores.

Segunda camada:

- busca semântica, se houver mecanismo local disponível.

Terceira camada:

- filtros estruturados.

Combinar os resultados para formar o contexto da resposta.

---

# 11. PERGUNTAS EM LINGUAGEM NATURAL

O painel deverá possuir uma caixa de perguntas.

Exemplos:

```text
Quando encerra o contrato 034/2022?

Qual o valor do contrato 034/2022?

Qual é o objeto do contrato 034/2022?

Quais são os itens do contrato 034/2022?

Quem é a contratada?

Qual o CNPJ da contratada?

Qual a data de assinatura?

Qual é a vigência?

Quais termos aditivos existem?

Qual foi o último aditivo?

Qual o valor atualizado?

Quais documentos comprovam a vigência?

Quais documentos estão relacionados ao contrato?
```

Também aceitar perguntas livres.

---

# 12. RESPOSTA HUMANIZADA

As respostas deverão ser:

- claras;
- objetivas;
- profissionais;
- naturais;
- contextualizadas;
- fundamentadas nos documentos.

Não responder apenas com fragmentos encontrados.

Exemplo:

> O Contrato nº 034/2022 foi celebrado com vigência de XX meses, iniciando-se em XX/XX/XXXX e encerrando-se em XX/XX/XXXX, conforme o Termo de Contrato localizado na pasta documental.

Em seguida:

```text
Fontes:
• Contrato 034-2022.pdf — pág. 4
• 1º Termo Aditivo.pdf — pág. 2
```

---

# 13. CITAÇÃO DAS FONTES

Toda resposta factual deverá possuir fonte.

Sempre que possível:

```text
Documento
Página
Seção
Trecho
```

Exemplo:

```text
Fonte:
Contrato_034_2022.pdf
Página: 7
Seção: Cláusula Segunda — Vigência
```

A aplicação deve permitir clicar na fonte e abrir o documento correspondente, quando possível.

---

# 14. CONFLITOS DOCUMENTAIS

Se documentos apresentarem informações diferentes:

NÃO escolher automaticamente.

Apresentar:

```text
CONFLITO IDENTIFICADO

Documento A:
Valor: R$ 100.000,00

Documento B:
Valor: R$ 120.000,00

Conclusão:
Os documentos apresentam valores divergentes.
É necessária conferência documental.
```

Quando existir documento posterior que claramente substitua ou altere documento anterior, o sistema poderá informar essa relação, mas deverá indicar a fonte e deixar claro que se trata de uma interpretação documental.

---

# 15. INFORMAÇÃO AUSENTE

Se a informação não estiver nos documentos:

```text
Não localizei essa informação nos documentos disponibilizados.
```

Não preencher com conhecimento externo.

---

# 16. EXTRAÇÃO DE CONTRATOS

Quando identificar um contrato, tentar extrair:

```text
Número do contrato
Número do processo
Contratante
Contratada
CNPJ
Objeto
Valor
Data de assinatura
Início da vigência
Fim da vigência
Prazo
Forma de pagamento
Itens
Obrigações
Fiscalização
Penalidades
Aditivos
Reajustes
Repactuações
Rescisão
Fontes documentais
```

A extração deverá possuir indicação de confiança.

---

# 17. CHECKLIST

O painel deverá permitir:

1. colar um checklist em uma caixa de texto;
2. carregar checklist de arquivo;
3. interpretar cada requisito;
4. pesquisar os documentos;
5. identificar documentos relacionados;
6. classificar atendimento;
7. apresentar justificativa;
8. organizar documentos.

---

# 18. STATUS DO CHECKLIST

Utilizar:

```text
ATENDIDO
PARCIALMENTE ATENDIDO
AUSENTE
DÚVIDA
DUPLICADO
VENCIDO
INCOMPATÍVEL
NÃO IDENTIFICADO
```

Exemplo:

```text
ITEM 01
Contrato assinado
STATUS: ATENDIDO

Documento:
Contrato_034_2022.pdf

Evidência:
Página 1 — assinatura das partes
```

---

# 19. ORGANIZAÇÃO VIRTUAL DOS DOCUMENTOS

Por padrão, NÃO mover, renomear ou alterar documentos originais.

Criar organização virtual.

Exemplo:

```text
CHECKLIST
│
├── 01 — Contrato
│   └── Contrato_034_2022.pdf
│
├── 02 — Termos Aditivos
│   ├── 1_Aditivo.pdf
│   └── 2_Aditivo.pdf
│
├── 03 — Fiscalização
│   └── Portaria_Fiscal.pdf
│
├── 04 — Comprovação de Regularidade
│   ├── Certidao.pdf
│   └── FGTS.pdf
│
└── 05 — Outros
```

A organização será apenas lógica/virtual.

---

# 20. DUPLICIDADES

Detectar:

- arquivos idênticos;
- arquivos com mesmo hash;
- arquivos com nomes diferentes e conteúdo igual;
- versões possivelmente relacionadas.

Informar ao usuário.

Nunca excluir automaticamente.

---

# 21. DOCUMENTOS RELACIONADOS

Identificar possíveis relações por:

- número do contrato;
- processo;
- CNPJ;
- fornecedor;
- objeto;
- número do aditivo;
- datas;
- referências internas;
- nomes.

Construir uma visão de relacionamento.

Exemplo:

```text
Contrato 034/2022
│
├── Processo
├── Termo Aditivo 01
├── Termo Aditivo 02
├── Apostilamento
├── Notificações
├── Faturas
├── Relatórios
└── Documentos de fiscalização
```

---

# 22. PAINEL WEB LOCAL

Disponibilizar:

```text
http://127.0.0.1:8000
```

O painel deverá possuir, no mínimo:

### Dashboard

- documentos encontrados;
- documentos indexados;
- documentos com erro;
- contratos identificados;
- checklists;
- última atualização;
- status do indexador.

### Perguntas

Campo:

```text
Digite sua pergunta...
```

Botão:

```text
Pesquisar
```

Resultado:

- resposta;
- fontes;
- documentos;
- páginas;
- conflitos;
- grau de confiança.

### Documentos

Permitir:

- pesquisar;
- filtrar;
- visualizar metadados;
- abrir;
- reindexar;
- visualizar status.

### Checklist

Permitir:

- inserir;
- salvar;
- executar;
- visualizar atendimento;
- filtrar por status;
- exportar relatório.

### Configurações

Permitir:

- selecionar diretório documental;
- iniciar indexação;
- reindexar;
- verificar sistema;
- configurar OCR;
- configurar mecanismo de IA;
- visualizar logs.

---

# 23. IA EXTERNA

A aplicação deverá funcionar inicialmente sem obrigatoriedade de API externa.

Criar uma abstração:

```text
AnswerProvider
```

Implementações possíveis:

```text
LocalDocumentAnswerProvider
OpenAIAnswerProvider
LocalLLMAnswerProvider
```

A aplicação deverá continuar funcionando se nenhuma API de IA estiver configurada.

Se uma IA externa for utilizada, ela deverá receber apenas o contexto documental necessário para responder à pergunta.

Nunca enviar automaticamente todo o diretório para um serviço externo.

---

# 24. PRIVACIDADE

Por padrão:

```text
LOCAL ONLY
```

Não enviar documentos para a Internet sem configuração explícita do usuário.

Não criar telemetria própria.

Não copiar documentos para diretórios temporários externos sem necessidade.

Não armazenar credenciais no código.

Utilizar `.env`.

---

# 25. SEGURANÇA

O painel deverá escutar inicialmente somente:

```text
127.0.0.1
```

Não utilizar:

```text
0.0.0.0
```

sem solicitação expressa do usuário.

Não abrir portas externas automaticamente.

Não configurar firewall automaticamente sem autorização.

---

# 26. CONFIGURAÇÃO

Criar:

```text
.env.example
```

Com:

```text
APP_HOST=127.0.0.1
APP_PORT=8000

DOCUMENTS_ROOT=D:\Documentos

DATABASE_PATH=.\data\database\documents.db

LOG_LEVEL=INFO

OCR_ENABLED=true

AI_PROVIDER=local
OPENAI_API_KEY=
```

Nunca gravar uma chave real no repositório.

---

# 27. INSTALAÇÃO

Criar:

```text
instalar.bat
```

O instalador deverá:

1. verificar Windows;
2. verificar Python;
3. criar ambiente virtual;
4. criar diretórios;
5. instalar `requirements.txt`;
6. criar `.env`, se necessário;
7. executar diagnóstico;
8. testar importações;
9. testar SQLite;
10. testar FastAPI;
11. informar resultado.

Não instalar Node.

Não instalar Docker.

Não exigir WSL.

---

# 28. EXECUÇÃO

Criar:

```text
start.bat
```

Funcionamento:

```text
ativar ambiente virtual
        ↓
iniciar FastAPI/Uvicorn
        ↓
127.0.0.1:8000
```

Criar:

```text
stop.bat
```

para encerramento controlado.

---

# 29. DIAGNÓSTICO

Criar:

```text
diagnostico.bat
```

e:

```text
scripts\diagnostico.py
```

O diagnóstico deverá verificar:

```text
Windows
Python
pip
venv
SQLite
permissão de leitura
permissão de escrita
diretório documental
espaço em disco
FastAPI
Uvicorn
bibliotecas de documentos
OCR
banco de dados
porta 8000
```

Apresentar:

```text
[OK]
[WARNING]
[ERRO]
```

---

# 30. TESTE DE SAÚDE

Criar endpoint:

```text
GET /health
```

Resposta:

```json
{
  "status": "ok",
  "database": "ok",
  "documents_root": "ok",
  "index": "ok"
}
```

---

# 31. INDEXAÇÃO

A indexação deverá poder ser iniciada:

- automaticamente;
- pelo painel;
- pelo comando;
- pelo script.

Comandos:

```text
python scripts\indexar.py
```

ou equivalente.

Exibir:

```text
Arquivos encontrados: 1250
Arquivos novos: 17
Arquivos alterados: 8
Arquivos inalterados: 1220
Erros: 5
```

---

# 32. LOGS

Registrar logs em:

```text
data\logs\
```

Registrar:

- início;
- fim;
- erros;
- documentos processados;
- arquivos ignorados;
- OCR;
- consultas;
- indexações.

Não registrar conteúdo sensível completo desnecessariamente.

---

# 33. BACKUP

Criar rotina de backup para:

```text
database
index
configurações
relatórios
```

Não incluir automaticamente os documentos originais no backup da aplicação.

Os documentos originais permanecem no diretório definido pelo usuário.

---

# 34. EXPORTAÇÃO

Permitir exportar:

```text
PDF
DOCX
XLSX
CSV
JSON
```

Relatórios possíveis:

- resultado da consulta;
- inventário documental;
- checklist;
- documentos ausentes;
- conflitos;
- contratos identificados.

---

# 35. TRATAMENTO DE ERROS

Nunca apresentar traceback técnico ao usuário final como resposta normal.

Exemplo:

```text
Não foi possível processar o documento X.

Motivo:
O arquivo está protegido ou corrompido.

Ação recomendada:
Verifique o arquivo original.
```

Detalhes técnicos devem permanecer nos logs.

---

# 36. PERFORMANCE

A aplicação deverá utilizar indexação incremental.

Não reprocessar todos os documentos a cada pergunta.

A pergunta deverá consultar o índice.

Fluxo:

```text
DOCUMENTOS
   ↓
INDEXAÇÃO
   ↓
ÍNDICE
   ↓
PERGUNTA
   ↓
RECUPERAÇÃO
   ↓
EVIDÊNCIAS
   ↓
RESPOSTA
```

---

# 37. CONFIABILIDADE DA RESPOSTA

Toda resposta deverá distinguir internamente:

```text
FATO DOCUMENTAL
INFERÊNCIA
CONFLITO
AUSÊNCIA
```

A interface deverá priorizar fatos documentais.

Quando houver inferência, informar:

> "Esta conclusão decorre da relação entre os documentos localizados."

---

# 38. PROIBIÇÃO DE ALUCINAÇÃO

É proibido:

- inventar número de contrato;
- inventar valor;
- inventar datas;
- inventar cláusulas;
- inventar documentos;
- inventar páginas;
- inventar fornecedores;
- inventar itens;
- inventar evidências.

Se não houver evidência suficiente:

```text
NÃO IDENTIFICADO NOS DOCUMENTOS
```

---

# 39. TESTES

Criar testes automatizados para:

1. PDF;
2. DOCX;
3. XLSX;
4. TXT;
5. OCR;
6. indexação;
7. busca;
8. contrato;
9. aditivo;
10. conflito;
11. informação ausente;
12. checklist;
13. duplicidade;
14. API;
15. banco de dados.

Criar documentos de teste fictícios.

Não utilizar documentos reais do usuário nos testes automatizados.

---

# 40. ORDEM DE IMPLEMENTAÇÃO

Não tentar construir tudo simultaneamente.

Executar nesta ordem:

### FASE 1

Diagnóstico do Windows/Python.

### FASE 2

Estrutura do projeto.

### FASE 3

FastAPI + página inicial.

### FASE 4

SQLite.

### FASE 5

Leitura de PDF/DOCX/XLSX/TXT.

### FASE 6

Indexação.

### FASE 7

Pesquisa.

### FASE 8

Perguntas em linguagem natural.

### FASE 9

Extração de contratos.

### FASE 10

Checklist.

### FASE 11

Relatórios.

### FASE 12

OCR.

### FASE 13

IA opcional.

### FASE 14

Testes e documentação.

---

# 41. REGRA DE EXECUÇÃO DO CODEX

Antes de alterar arquivos:

1. verificar o diretório atual;
2. verificar se está no projeto correto;
3. verificar Python;
4. verificar ambiente virtual;
5. verificar permissões;
6. verificar se o sandbox permite escrita no projeto;
7. verificar dependências;
8. apresentar diagnóstico em caso de falha.

Não tentar resolver problemas de infraestrutura alterando arbitrariamente o código da aplicação.

Se o executor do Codex não conseguir executar comandos, parar e informar:

```text
O problema está no ambiente de execução do Codex e não no código da aplicação.
```

---

# 42. WINDOWS / CODEX

O projeto deve considerar que o Codex está sendo executado nativamente no Windows.

Não assumir WSL.

Não assumir Linux.

Não assumir Bash.

Quando criar scripts para instalação/execução, priorizar:

```text
.bat
PowerShell
Python
```

Evitar scripts exclusivamente Bash.

O Codex utiliza sandbox nativo no Windows. A configuração do sandbox e das permissões é independente das instruções deste arquivo. Este AGENTS.md não deve tentar contornar restrições de segurança do Codex.

---

# 43. GESTÃO DO SANDBOX

O agente não deve modificar automaticamente:

```text
Codex
Windows Defender
CrowdStrike
Firewall
Políticas de segurança
Registro do Windows
```

Se o sandbox impedir a execução, informar o bloqueio e fornecer instruções ao usuário.

Nunca tentar desabilitar mecanismos de segurança para contornar o problema.

---

# 44. DIRETÓRIOS PERMITIDOS

O projeto deverá trabalhar preferencialmente dentro de:

```text
D:\AgenteDocumental
```

e com os documentos em:

```text
D:\Documentos
```

Esses caminhos são exemplos e deverão ser configuráveis.

Não presumir que o diretório documental já exista.

---

# 45. PRINCÍPIO DE NÃO DESTRUIÇÃO

Nunca:

- excluir documentos originais;
- sobrescrever documentos originais;
- renomear documentos originais;
- mover documentos originais;
- alterar documentos originais.

Qualquer transformação deverá ocorrer em:

```text
data\
```

ou outro diretório de trabalho da aplicação.

---

# 46. EXPERIÊNCIA DO USUÁRIO

A interface deve ser profissional e simples.

Priorizar:

- poucos cliques;
- linguagem em português-BR;
- respostas claras;
- indicadores de status;
- fontes visíveis;
- filtros;
- busca rápida;
- mensagens de erro compreensíveis.

---

# 47. DOCUMENTAÇÃO

Criar `README.md` contendo:

1. objetivo;
2. requisitos;
3. instalação;
4. configuração;
5. definição do diretório documental;
6. inicialização;
7. acesso ao painel;
8. indexação;
9. perguntas;
10. checklist;
11. backup;
12. solução de problemas;
13. atualização;
14. desinstalação.

---

# 48. CRITÉRIO DE CONCLUSÃO

O projeto somente será considerado concluído quando:

- [ ] instalar no Windows 11;
- [ ] iniciar pelo `start.bat`;
- [ ] abrir `http://127.0.0.1:8000`;
- [ ] detectar o diretório documental;
- [ ] ler PDFs;
- [ ] ler DOCX;
- [ ] ler XLSX;
- [ ] indexar documentos;
- [ ] pesquisar documentos;
- [ ] responder perguntas;
- [ ] apresentar fontes;
- [ ] detectar informação ausente;
- [ ] detectar conflitos;
- [ ] identificar contratos;
- [ ] identificar itens;
- [ ] processar checklist;
- [ ] organizar documentos virtualmente;
- [ ] gerar relatório;
- [ ] executar diagnóstico;
- [ ] registrar logs;
- [ ] preservar documentos originais.

---

# 49. REGRA FINAL PARA O AGENTE

Construa primeiro uma aplicação pequena, funcional e verificável.

Não introduza complexidade antes de existir uma versão funcional.

Prioridade:

```text
FUNCIONAR
↓
SER CONFIÁVEL
↓
SER RASTREÁVEL
↓
SER FÁCIL DE USAR
↓
SER INTELIGENTE
↓
SER SOFISTICADO
```

A aplicação deve ser capaz de responder corretamente com base documental antes de receber recursos avançados de IA.

Quando houver dúvida entre uma solução simples e uma solução complexa, escolher a solução simples, desde que preserve precisão, rastreabilidade e segurança.