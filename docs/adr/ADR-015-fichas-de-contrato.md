# ADR-015 — Fichas de contrato pré-processadas para respostas em segundos

| Campo | Valor |
|---|---|
| Status | **Aceito** (decisão do responsável em 2026-11-21: meta de resposta ≤ 10 s, opção "fichas pré-processadas") |
| Data | 2026-11-21 |
| Requisitos | Meta de tempo da alta gestão; RF-01 (citação), RNF de confiabilidade |

## Contexto

Nesta estação (GTX 1660 SUPER), o LLM de 7B lê o prompt a ≈ 140 tok/s: uma pergunta simples real leva 40–50 s
(≈ 5 s de busca, 17–25 s de leitura dos trechos, 8–10 s de geração). O modelo de 3B chegou a ≈ 12 s, mas com recusa
correta 0,25 (inventa resposta quando o acervo não tem a informação) — inaceitável para a alta gestão.

## Decisão

Separar o que pode ser **preparado antes** do que exige leitura no momento da pergunta:

1. **Agrupamento por contrato** (determinístico): a pasta de 1º nível identifica o contrato (19 pastas com nº/ano,
   5.944 de 6.011 documentos); sem pasta própria, o número citado no título/abertura liga o documento.
2. **Ficha** (LLM local, uma vez por contrato, fora do horário de uso): número, contratada, CNPJ, objeto, datas,
   vigência, valor, fiscal e gestor — **cada valor só entra se constar do trecho citado**.
3. **Inventário** (determinístico): documentos de cada tipo, com data e trecho (ordens de serviço reconhecidas pelo
   título, tipo que o classificador não tem).
4. **Na pergunta** (sem LLM): reconhece o contrato (número, apelido ou nome que só ele contém) e o assunto; responde
   em milissegundos com citação. Nome que casa com 2–5 contratos → lista os candidatos; contrato citado cujo número
   não aparece em **nenhum** trecho → ausência; pergunta transversal ("quais contratos tiveram notificação em 2025?")
   → junta os inventários. Sem contrato/assunto reconhecido ou sem o dado → caminho completo (busca + LLM).

## Consequências

- Acervo real (rodada 6): 6 das 11 perguntas não-decisórias da equipe respondidas em ≤ 1,2 s (antes 38–84 s);
  perguntas abertas continuam em 40–140 s e a decisão (F2) ≈ 4 min.
- Precisão dos campos garantida pela conferência literal; a das listas depende da classificação automática de tipos
  (amostra `avaliacao/real/amostra_tipos.csv` ainda sem conferência humana) — as respostas avisam.
- As fichas precisam ser atualizadas após cada indexação (`scripts/sadgd/gerar_fichas.py`; extração só para
  contratos novos, inventário sempre).
- Perguntas sobre vigência avisam que aditivos podem ter prorrogado o prazo (a ficha guarda o instrumento original).
