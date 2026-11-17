# FASE 10 — Otimização e avaliação final (Sprint S10)

| Campo | Valor |
|---|---|
| Período | 2026-11-17 |
| Executor | Claude Code (`claude-opus-5-5`) |
| Situação | **Aguardando aprovação** |

## 1. Entregas

| Item | Entregável | Arquivos |
|---|---|---|
| Limpeza v1 (aprovada) | Tag `backup/pre-limpeza-v1` (GitHub) + cópia do banco em `BACKUP\pre-limpeza-v1\`; removidos os pacotes `checklist`, `contracts`, `retrieval`, `indexing`, 7 serviços e 5 rotas v1, telas v1, `indexar.py`, `aceitacao.py`/`.bat`; indexação automática, painel e OCR usam o indexador do SAD-GD; 165 testes exclusivos da v1 removidos, testes de segurança/OCR/extração/banco/backup/servidor **adaptados** (não perdidos) | commit `38d761d` |
| Proteção portada | Pastas da aplicação (`data`, `BACKUP`, `modelos`, `ferramentas`, `.venv`, `.git`) e pastas de sistema nunca são indexadas, mesmo dentro da raiz documental (a v1 tinha; o SAD-GD não tinha) | `app/infrastructure/fonte_arquivos.py`, `tests/test_auth.py` |
| Cache semântico (§5 do prompt mestre) | Reaproveita resposta somente com **mesmos identificadores** (nº de contrato, lei, ano, valor), **mesma versão do acervo/memória** e texto igual ou cosseno ≥ **0,93** (bge-m3, calibrado); consultas do cache também são auditadas (`cache_hit`) | `app/application/cache_semantico.py`, `app/infrastructure/sqlite/cache_semantico.py`, `scripts/sadgd/calibrar_cache.py` |
| Faithfulness com LLM-juiz | Juiz de **outra família** (Llama 3.1 8B) julga cada frase contra os trechos citados; calibrado na **validação** com respostas corrompidas de propósito; medido no **teste** com correção de Rogan–Gladen e adjudicação | `app/application/avaliacao/fidelidade.py`, `scripts/sadgd/avaliar_fidelidade.py` |
| Experimentos de latência da F2 | Especialistas no Qwen 2.5 3B; orçamento de tokens maior — ambos medidos na validação e **rejeitados** (ver §3) | `scripts/sadgd/avaliar_f2.py --modelo-especialistas`, `avaliacao/execucoes/fase10/` |
| Correção | Relator descarta chaves inventadas em alternativas/riscos/divergências (causa de 1 relator inválido) | `especialistas.py` |

Testes: **311 passando**, cobertura domínio+aplicação **96%**, ruff limpo; suíte validada também sem o diretório documental local (como no CI).

## 2. Métricas finais × metas do prompt mestre (conjunto de TESTE)

| Métrica | Meta | Resultado | Situação |
|---|---|---|---|
| Recall@5 (recuperação) | ≥ 0,90 | **0,965** (híbrido + rerank) | ✅ |
| MRR / nDCG@10 / P@5 | — | 0,909 / 0,964 / 0,240¹ | — |
| Faithfulness | ≥ 0,90 | **0,964** adjudicada (juiz bruto: 0,795) | ✅ (ver §4) |
| Alucinação | ≤ 5% | **0,0%** numérica (determinística); **5,4%** por frase, adjudicada (5/92; +≈1 falso negativo estimado) | ⚠️ não atendida por margem pequena |
| F1 de classificação — relações entre documentos | ≥ 0,85 | **1,00** sintético (sobreajuste declarado); público: 10/10 relações oficiais, 38/39 coerentes | ✅ com ressalva |
| Classificação — tipo documental | ≥ 0,85 | acurácia **1,00** (186 documentos); número 1,00; data 0,984 | ✅ |
| Roteamento | ≥ 0,90 | **0,935** (3 rotas); 1,00 F1×F2 | ✅ |
| Precedentes (RF-19) | Recall@3 ≥ 0,80 | **1,00** | ✅ |
| Recomendação F2 com 6 elementos (RF-20) | 100% | **100%** presentes ou declarados (71% com conteúdo nos 6) | ✅ |
| Anonimização (RF-25) | recall nomes ≥ 0,90; CPF 100% | 1,00 / 1,00 | ✅ |
| Latência F1 p50 / p95 | — | 14,6 s / 29,0 s (Qwen 2.5 7B local) | — |
| Latência F2 p50 / p95 | — | 329 s / 387 s | ⚠️ limitação de hardware (R15) |
| Latência com cache (acerto) | — | **5 ms** p50 | ✅ |
| Tokens por consulta (entrada/saída) | medir | F1 ≈ 2.457 / 107; F2 ≈ 18.872 / 2.538; cache: 0 | ✅ |
| Custo por consulta | gratuito | **R$ 0** (tudo local) | ✅ |

¹ P@5 é limitado pelo número de trechos relevantes por pergunta (em geral 1–2), não por erro de ranking.

## 3. Latência da F2 — experimentos (mesmos 6 itens de validação)

| Configuração | p50 | Pareceres com conteúdo | Recall docs | Novas tentativas | Decisão |
|---|---|---|---|---|---|
| Fase 8: tudo no Qwen 7B | 322 s | **100%** | 0,722 | 9 | **mantida** |
| Especialistas Qwen 3B + relator 7B | **127 s** | **7%** | 0,806 | 1 | rejeitada |
| Tudo 7B, orçamento 1.300 tokens | 296 s | 100% | 0,472 | 0 | rejeitada (revertida) |

O 3B é 2,5× mais rápido, mas em 13 de 14 pareceres **não produziu o campo `parecer`** (devolveu outras estruturas); o reparo de forma os tornava "válidos" e vazios, e a recomendação só parecia completa porque as regras determinísticas de RF-20 preenchiam alternativas e riscos. Lição registrada: métricas agregadas de validade escondem perda de conteúdo. Conclusão: neste hardware (GTX 1660 SUPER, 6 GB) a F2 é limitada pela velocidade de geração do 7B; caminhos reais são hardware maior ou um provedor gratuito em nuvem **somente para o corpus acadêmico** (já previsto no ADR-004 e protegido pela política LGPD da Fase 7), o que exige chave de API do responsável. O cache semântico elimina o custo das perguntas repetidas.

## 4. Faithfulness — instrumento e resultado

**Calibração (validação, 63 itens: 33 originais + 30 corrompidas por número trocado, sentido invertido ou frase inventada):**

| | Sensibilidade (detecta infiel) | Especificidade (aceita fiel) | κ de Cohen |
|---|---|---|---|
| Rótulos por construção | 0,80 | 0,82 | 0,62 |
| **Rótulos adjudicados** (3 "originais boas" eram infiéis de fato; 3 erros do juiz) | **0,82** | **0,90** | **0,71** |

Primeira calibração (κ 0,56) revelou um defeito **meu**: a divisão em frases quebrava em "art." e "nº". Corrigido antes de qualquer medição no teste; o prompt do juiz não foi alterado.

**Teste (v2.2, 92 respostas julgadas; 3 falhas de JSON do juiz):** faithfulness bruta 0,795 e 25% das respostas sinalizadas (20,9% após Rogan–Gladen). **Todas** as 23 respostas sinalizadas foram revistas contra o texto integral dos trechos: 18 eram falsos alarmes do juiz (datas de suspensão/retomada, reajustes do IPCA, conflito determinístico, art. 74 V…), 5 eram infiéis de fato (atribuição: "art. 1º" para conteúdo do art. 11; princípio do Decreto 9.203 atribuído à Constituição; "60 dias" × "até 60 dias"; detalhes "a partir do termo aditivo" e "por inexecução parcial" ausentes dos trechos citados). Resultado adjudicado: **faithfulness 0,964; alucinação 5,4%**. Revisão feita pelo agente de desenvolvimento — **pendente de confirmação humana** (arquivos `fidelidade_adjudicacao*.json`).

## 5. Cache semântico — calibração do limiar

No golden set, o par de perguntas **diferentes** mais parecido com os mesmos identificadores ("prorrogação de contratos contínuos" × "prazo inicial de contratos contínuos", ambos da Lei 14.133) tem cosseno 0,883; paráfrases verdadeiras vão de 0,876 a 0,997. Limiar 0,93 (margem 0,05): nenhuma resposta errada reaproveitada no golden set, 7/10 paráfrases reaproveitadas. Para apoio à decisão, reaproveitar errado custa mais que recalcular.

## 6. Para sua decisão

1. **Tabelas v1 no banco**: ao preparar a limpeza encontrei as tabelas v1 **com dados** (189 documentos, 645 trechos, 40 contratos e 1 checklist com 4 itens) — o indexador v1 voltou a rodar sobre `corpus\` depois da Fase 1 (eu havia dito que estavam esvaziadas). São índices derivados do corpus (regeneráveis), mas por isso **não as apaguei**: o código que as usava saiu; os dados ficam até você decidir (há cópia em `BACKUP\pre-limpeza-v1\`).
2. **Provedor gratuito em nuvem para a F2 do corpus acadêmico** (ex.: Groq/Gemini free tier), para medir a F2 com latência de segundos — exige que você crie uma chave e a coloque no `.env` (nunca no chat).

## 7. Pendências

1. Confirmação humana das adjudicações (faithfulness) e revisão do golden set.
2. Precedentes fracos em perguntas F2 longas (R17) — não recalibrei usando perguntas de teste; fica como trabalho futuro documentado.
3. Manuais (`MANUAL_DO_USUARIO.md`, `MANUAL_TECNICO.md`) ainda descrevem a v1 — reescrita na Fase 11.
4. Kanban depende do `gh`.

## 8. Retrospectiva

- **Bem:** olhar dentro das métricas agregadas evitou duas conclusões erradas (o 3B "igual e 2,5× mais rápido"; o juiz "dizendo" 25% de alucinação); a calibração do juiz pegou um defeito do próprio instrumento.
- **A melhorar:** afirmei que as tabelas v1 estavam vazias sem verificar — a verificação antes de apagar evitou o erro.
- **Ação:** Fase 11 — relatório técnico, documentação final, roteiro de demonstração e lições aprendidas.

## 9. Aprovação

- [ ] Aprovado por: ______ em ____/____/______
