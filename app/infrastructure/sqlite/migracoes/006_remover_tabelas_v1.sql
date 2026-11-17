-- SAD-GD Fase 10/11 — remoção das tabelas da v1 (aprovada pelo responsável em 2026-11-17).
-- Dados derivados do corpus pelo indexador v1 (código já removido). Backup: BACKUP\pre-limpeza-v1\sadgd.db
-- e tag git backup/pre-limpeza-v1. Ficam settings, users e sessions (acesso), usados pelo SAD-GD.

DROP TABLE IF EXISTS checklist_matches;
DROP TABLE IF EXISTS checklist_items;
DROP TABLE IF EXISTS checklist;
DROP TABLE IF EXISTS contract_items;
DROP TABLE IF EXISTS contracts;
DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS index_runs;
