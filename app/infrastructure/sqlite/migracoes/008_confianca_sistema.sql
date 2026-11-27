-- Confiança calculada pelo sistema (2026-11-25, app/domain/confianca.py): `confianca` passa a ser a do sistema
-- (NULL em ausência/conflito); a autoavaliação declarada pelo LLM fica registrada à parte, só para auditoria,
-- junto com o critério do cálculo (lista JSON de fatores exibida ao usuário).
ALTER TABLE consultas ADD COLUMN confianca_modelo REAL;
ALTER TABLE consultas ADD COLUMN criterio_confianca TEXT;
