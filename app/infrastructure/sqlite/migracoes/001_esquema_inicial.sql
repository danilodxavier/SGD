-- SAD-GD — esquema inicial (docs/arquitetura/MODELO_DE_DADOS.md, ADR-006)

CREATE TABLE documentos (
    id INTEGER PRIMARY KEY,
    caminho TEXT NOT NULL UNIQUE,
    caminho_relativo TEXT,
    hash TEXT,
    extensao TEXT,
    tamanho INTEGER,
    mtime REAL,
    status TEXT NOT NULL,
    corpus_origem TEXT NOT NULL CHECK (corpus_origem IN ('publico', 'sintetico', 'real')),
    tipo_documental TEXT,
    numero TEXT,
    orgao TEXT,
    titulo TEXT,
    data_documento TEXT,
    vigencia_inicio TEXT,
    vigencia_fim TEXT,
    paginas INTEGER,
    erro TEXT,
    indexado_em TEXT
);
CREATE INDEX ix_documentos_hash ON documentos(hash);
CREATE INDEX ix_documentos_tipo ON documentos(tipo_documental);

CREATE TABLE trechos (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    texto TEXT NOT NULL,
    pagina INTEGER,
    dispositivo TEXT,
    tipo_dispositivo TEXT NOT NULL DEFAULT 'livre',
    caminho TEXT,
    inicio INTEGER,
    fim INTEGER,
    tokens INTEGER
);
CREATE INDEX ix_trechos_documento ON trechos(documento_id);

-- FTS5 com conteúdo externo + gatilhos: a remoção em cascata limpa o índice (lição da v1)
CREATE VIRTUAL TABLE trechos_fts USING fts5(
    texto, dispositivo, content = 'trechos', content_rowid = 'id',
    tokenize = "unicode61 remove_diacritics 2"
);
CREATE TRIGGER trechos_ai AFTER INSERT ON trechos BEGIN
    INSERT INTO trechos_fts(rowid, texto, dispositivo) VALUES (new.id, new.texto, new.dispositivo);
END;
CREATE TRIGGER trechos_ad AFTER DELETE ON trechos BEGIN
    INSERT INTO trechos_fts(trechos_fts, rowid, texto, dispositivo) VALUES ('delete', old.id, old.texto, old.dispositivo);
END;
CREATE TRIGGER trechos_au AFTER UPDATE ON trechos BEGIN
    INSERT INTO trechos_fts(trechos_fts, rowid, texto, dispositivo) VALUES ('delete', old.id, old.texto, old.dispositivo);
    INSERT INTO trechos_fts(rowid, texto, dispositivo) VALUES (new.id, new.texto, new.dispositivo);
END;

CREATE TABLE normas (
    documento_id INTEGER PRIMARY KEY REFERENCES documentos(id) ON DELETE CASCADE,
    especie TEXT NOT NULL,
    nivel INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
    esfera TEXT CHECK (esfera IN ('federal', 'estadual', 'municipal')),
    numero TEXT,
    ano INTEGER,
    situacao TEXT NOT NULL DEFAULT 'vigente' CHECK (situacao IN ('vigente', 'parcialmente_revogada', 'revogada')),
    revogada_por INTEGER REFERENCES documentos(id) ON DELETE SET NULL
);

CREATE TABLE processos (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('processo', 'contrato', 'tema')),
    chave TEXT NOT NULL,
    titulo TEXT,
    UNIQUE (tipo, chave)
);

CREATE TABLE documento_processo (
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    processo_id INTEGER NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
    papel TEXT,
    confianca REAL CHECK (confianca BETWEEN 0 AND 1),
    PRIMARY KEY (documento_id, processo_id)
);

CREATE TABLE relacoes (
    id INTEGER PRIMARY KEY,
    origem_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    destino_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('continuacao', 'aditivo', 'alteracao', 'revogacao', 'substituicao',
                                       'ruptura', 'contradicao', 'retomada', 'regulamenta', 'fundamenta')),
    confianca REAL NOT NULL CHECK (confianca BETWEEN 0 AND 1),
    metodo TEXT NOT NULL CHECK (metodo IN ('regra', 'llm', 'manual')),
    evidencia_trecho_id INTEGER NOT NULL REFERENCES trechos(id) ON DELETE CASCADE,
    justificativa TEXT,
    validada INTEGER NOT NULL DEFAULT 0,
    CHECK (origem_id <> destino_id),
    UNIQUE (origem_id, destino_id, tipo)
);
CREATE INDEX ix_relacoes_destino ON relacoes(destino_id);

CREATE TABLE contratos (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    numero TEXT, processo TEXT, contratada TEXT, cnpj TEXT, objeto TEXT, valor TEXT,
    assinatura TEXT, inicio TEXT, fim TEXT
);

CREATE TABLE contrato_itens (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id) ON DELETE CASCADE,
    descricao TEXT, quantidade TEXT, unidade TEXT, valor_unitario TEXT, valor_total TEXT
);

CREATE TABLE decisoes (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER REFERENCES processos(id) ON DELETE SET NULL,
    titulo TEXT NOT NULL,
    contexto TEXT,
    decisao TEXT NOT NULL,
    fundamentos TEXT,
    decisor_perfil TEXT,
    data TEXT NOT NULL,
    resultado TEXT,
    avaliacao_resultado TEXT NOT NULL DEFAULT 'pendente'
        CHECK (avaliacao_resultado IN ('positivo', 'negativo', 'neutro', 'pendente')),
    registrado_por INTEGER,
    criado_em TEXT NOT NULL
);

CREATE TABLE decisao_fontes (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id) ON DELETE CASCADE,
    documento_id INTEGER REFERENCES documentos(id) ON DELETE SET NULL,
    trecho_id INTEGER REFERENCES trechos(id) ON DELETE SET NULL
);

-- auditoria e métricas (ADR-009); a pergunta é guardada apenas como hash (LGPD)
CREATE TABLE consultas (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER,
    pergunta_hash TEXT NOT NULL,
    rota TEXT,
    agentes TEXT,
    classificacao TEXT,
    confianca REAL,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_saida INTEGER NOT NULL DEFAULT 0,
    latencia_ms INTEGER,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    versao_indice TEXT,
    versao_sistema TEXT,
    criado_em TEXT NOT NULL
);

CREATE TABLE consulta_fontes (
    consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    trecho_id INTEGER,
    aprovada_verificador INTEGER
);

CREATE TABLE pareceres (
    id INTEGER PRIMARY KEY,
    consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    agente TEXT NOT NULL,
    versao_prompt TEXT NOT NULL,
    saida_json TEXT,
    valido INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE spans (
    id INTEGER PRIMARY KEY,
    consulta_id INTEGER REFERENCES consultas(id) ON DELETE CASCADE,
    no TEXT NOT NULL,
    modelo TEXT,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_saida INTEGER NOT NULL DEFAULT 0,
    latencia_ms INTEGER NOT NULL,
    erro TEXT,
    atributos TEXT,
    inicio TEXT NOT NULL
);
CREATE INDEX ix_spans_consulta ON spans(consulta_id);

CREATE TABLE auditoria (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER,
    acao TEXT NOT NULL,
    alvo TEXT,
    ip TEXT,
    criado_em TEXT NOT NULL
);

CREATE TABLE cache_semantico (
    id INTEGER PRIMARY KEY,
    pergunta_normalizada TEXT NOT NULL,
    resposta_json TEXT NOT NULL,
    versao_indice TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
