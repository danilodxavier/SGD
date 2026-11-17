-- SAD-GD Fase 9 — a reconstrução do grafo recria a tabela `processos` (ids novos; FK com ON DELETE SET NULL).
-- A decisão guarda a CHAVE estável do processo (ex.: "012/2023", "convenio:007/2023") para ser religada depois.

ALTER TABLE decisoes ADD COLUMN processo_chave TEXT;
UPDATE decisoes SET processo_chave = (SELECT chave FROM processos WHERE processos.id = decisoes.processo_id)
WHERE processo_id IS NOT NULL;
