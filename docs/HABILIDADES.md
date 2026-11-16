# Habilidades e conhecimentos adquiridos — SAD-GD

## Técnicos

| Data | Habilidade / conhecimento | Contexto |
|---|---|---|
| 2026-11-16 | Diagnóstico de inchaço em SQLite: registros lógicos removidos + freelist (1,16 M páginas livres) explicam 6,6 GB; `VACUUM INTO` gera cópia compacta verificável sem tocar no original | Fase 0 — banco reduzido de 6,6 GB para 1,7 GB |
| 2026-11-16 | Tabelas FTS5 sem *external content* não são limpas por `ON DELETE CASCADE`; a remoção precisa ser explícita | Fase 0 — análise do indexador v1 |
| 2026-11-16 | Limites de hardware local para IA: 6 GB de VRAM comportam LLM 7–8B Q4; 16 GB de RAM exigem carregar modelos sob demanda | Fase 1 — riscos R01/R02 |

## Domínio (setor público)

| Data | Conhecimento | Contexto |
|---|---|---|
| 2026-11-16 | Hierarquia normativa (CF > Lei > Decreto > IN > Orientação) e vigência temporal como requisito de recuperação, não só de geração | Requisito RF-14 |
| 2026-11-16 | Lei 14.133/2021 como referência para aditivos, prorrogações e fiscalização contratual | Agente Fiscal de Contrato |
| 2026-11-16 | LGPD: documentos públicos podem conter dados pessoais; separar corpus de avaliação de dados reais | ADR-002 |
