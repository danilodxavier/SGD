-- Fichas de contrato pré-processadas (Fase 12, 2026-11-21): respostas em ~1 s, sem LLM no momento da pergunta,
-- para as perguntas mais comuns da gestão sobre um contrato (objeto, partes, vigência, valor, fiscal, documentos).
CREATE TABLE IF NOT EXISTS fichas_contrato (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,            -- número normalizado do contrato, ex.: 012/2023
    pasta TEXT,                            -- pasta de 1º nível do acervo (quando o contrato tem pasta própria)
    campos TEXT NOT NULL DEFAULT '{}',     -- {campo: {"valor": ..., "trecho_id": ...}} — só valores conferidos
    documentos TEXT NOT NULL DEFAULT '[]', -- inventário [{documento_id, tipo, data, trecho_id}]
    texto_busca TEXT NOT NULL DEFAULT '',  -- pasta + contratada + objeto, normalizado (casar "contrato do <nome>")
    extracao TEXT NOT NULL DEFAULT 'pendente',  -- pendente | ok | sem_documento | falha
    gerada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fichas_extracao ON fichas_contrato (extracao);
