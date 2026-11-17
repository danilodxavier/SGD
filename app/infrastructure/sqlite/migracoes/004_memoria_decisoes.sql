-- SAD-GD Fase 8 — memória de decisões (RF-19): código, origem (política LGPD de envio), consulta de origem e busca lexical

ALTER TABLE decisoes ADD COLUMN codigo TEXT;
ALTER TABLE decisoes ADD COLUMN corpus_origem TEXT NOT NULL DEFAULT 'real';
ALTER TABLE decisoes ADD COLUMN consulta_id INTEGER REFERENCES consultas(id) ON DELETE SET NULL;
ALTER TABLE decisoes ADD COLUMN modelo_embedding TEXT;

CREATE UNIQUE INDEX ux_decisoes_codigo ON decisoes(codigo) WHERE codigo IS NOT NULL;
CREATE INDEX ix_decisoes_processo ON decisoes(processo_id);

CREATE VIRTUAL TABLE decisoes_fts USING fts5(
    titulo, contexto, decisao, fundamentos, resultado, content = 'decisoes', content_rowid = 'id',
    tokenize = "unicode61 remove_diacritics 2"
);
CREATE TRIGGER decisoes_ai AFTER INSERT ON decisoes BEGIN
    INSERT INTO decisoes_fts(rowid, titulo, contexto, decisao, fundamentos, resultado)
    VALUES (new.id, new.titulo, new.contexto, new.decisao, new.fundamentos, new.resultado);
END;
CREATE TRIGGER decisoes_ad AFTER DELETE ON decisoes BEGIN
    INSERT INTO decisoes_fts(decisoes_fts, rowid, titulo, contexto, decisao, fundamentos, resultado)
    VALUES ('delete', old.id, old.titulo, old.contexto, old.decisao, old.fundamentos, old.resultado);
END;
CREATE TRIGGER decisoes_au AFTER UPDATE ON decisoes BEGIN
    INSERT INTO decisoes_fts(decisoes_fts, rowid, titulo, contexto, decisao, fundamentos, resultado)
    VALUES ('delete', old.id, old.titulo, old.contexto, old.decisao, old.fundamentos, old.resultado);
    INSERT INTO decisoes_fts(rowid, titulo, contexto, decisao, fundamentos, resultado)
    VALUES (new.id, new.titulo, new.contexto, new.decisao, new.fundamentos, new.resultado);
END;
