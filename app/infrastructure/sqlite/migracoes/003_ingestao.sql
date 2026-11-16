-- SAD-GD — campos produzidos pela ingestão da Fase 4 (chunking estrutural, metadados, OCR, revogação)

ALTER TABLE trechos ADD COLUMN revogado INTEGER NOT NULL DEFAULT 0;
ALTER TABLE trechos ADD COLUMN subdispositivos TEXT;
ALTER TABLE documentos ADD COLUMN processo TEXT;
ALTER TABLE documentos ADD COLUMN motor_ocr TEXT;
ALTER TABLE documentos ADD COLUMN modelo_embedding TEXT;
-- 'vigente' = sem nota de revogação no próprio documento; 'revogada' somente com evidência textual
ALTER TABLE normas ADD COLUMN evidencia_situacao TEXT;

CREATE INDEX ix_documentos_processo ON documentos(processo);

CREATE TABLE indexacoes (
    id INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL,
    fim TEXT,
    raiz TEXT NOT NULL,
    encontrados INTEGER NOT NULL DEFAULT 0,
    novos INTEGER NOT NULL DEFAULT 0,
    alterados INTEGER NOT NULL DEFAULT 0,
    inalterados INTEGER NOT NULL DEFAULT 0,
    removidos INTEGER NOT NULL DEFAULT 0,
    erros INTEGER NOT NULL DEFAULT 0,
    trechos INTEGER NOT NULL DEFAULT 0,
    vetores INTEGER NOT NULL DEFAULT 0,
    segundos REAL,
    modelo_embedding TEXT
);
