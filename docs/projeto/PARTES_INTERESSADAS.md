# Registro de Partes Interessadas — SAD-GD

| Parte interessada | Papel | Interesse / expectativa | Poder | Interesse | Estratégia |
|---|---|---|---|---|---|
| Responsável pelo projeto (aluno) | Patrocinador, Product Owner, aprovador de fases | Nota máxima, sistema funcional e bem documentado | Alto | Alto | Gerenciar de perto: aprovação ao fim de cada fase |
| Professor / banca avaliadora | Avaliador | Rigor técnico, métricas, metodologia, rastreabilidade de IA | Alto | Alto | Manter satisfeito: AVALIACAO.md, ADRs, relatório final |
| Alta gestão pública (usuário-alvo) | Usuário final de F2 | Recomendações confiáveis, fundamentadas, com riscos | Médio | Alto | Manter informado: personas e requisitos de F2 |
| Servidores (fiscais, analistas) | Usuários de F1 | Respostas rápidas com fonte, linha do tempo | Médio | Alto | Manter informado: personas e testes de usabilidade |
| Órgãos de controle (TCE/TCU/CGU) | Referência normativa | Conformidade, trilha de auditoria | Baixo | Médio | Monitorar: logs de auditoria, princípio "sugere, não decide" |
| Titulares de dados pessoais (LGPD) | Afetados | Proteção de dados pessoais nos documentos | Baixo | Alto | Proteger: anonimização, acesso controlado, dados reais só locais |
| TI do órgão (SEMA-MT) | Operação do v1 | Continuidade do app v1 em uso | Médio | Médio | Monitorar: modo local Windows preservado |
| Claude Code (agente de desenvolvimento) | Executor técnico | Instruções claras, aprovação por fase | — | — | Regido por `CLAUDE.md` |

## Personas

- **Gestora (Secretária Adjunta):** precisa decidir sobre prorrogação de contrato; quer alternativas, riscos e base legal em uma página.
- **Fiscal de contrato:** quer saber vigência, aditivos e prazos com o documento e página de origem.
- **Procurador/assessor jurídico:** quer a cadeia normativa vigente e precedentes de decisões anteriores.
