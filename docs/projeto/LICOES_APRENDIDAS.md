# Lições aprendidas — SAD-GD (PMBOK 7)

Registro consolidado das retrospectivas das 12 fases (`docs/fases/FASE_XX.md`, seção "Retrospectiva") e da
Fase 11. Cada lição traz o fato que a originou, a evidência e a prática adotada. Conhecimentos técnicos e de
domínio adquiridos estão em `docs/HABILIDADES.md`.

---

## 1. Avaliação e métricas

| # | Lição | O que aconteceu | Evidência | Prática adotada |
|---|---|---|---|---|
| L01 | **Métrica agregada esconde perda de conteúdo** | Especialistas no Qwen 2.5 3B: schema 1,00 após reparo e 2,5× mais rápido, mas 13/14 pareceres sem o campo `parecer`; as regras do RF-20 preenchiam a recomendação e mascaravam o vazio | `FASE_10.md` §3 | Inspecionar amostras brutas antes de aceitar qualquer ganho; medir "com conteúdo", não só "válido" |
| L02 | **Métrica perfeita exige verificação externa** | F1 de relações = 1,00 no corpus sintético porque as regras foram ajustadas no próprio gabarito | `FASE_06.md` | Toda métrica sintética 1,00 vem com verificação no corpus público (10/10 relações oficiais) e ressalva publicada |
| L03 | **Instrumento de medida também precisa de teste** | O LLM-juiz "dizia" 25% de respostas infiéis; 18 de 23 eram falsos alarmes. A primeira calibração ainda revelou um defeito do próprio separador de frases ("art.", "nº") | `FASE_10.md` §4 | Calibrar o juiz com corrupções controladas na validação, κ de Cohen, Rogan–Gladen e adjudicação antes de publicar |
| L04 | **Calibre antes de olhar o teste** | O limiar inicial de precedentes, sem regra de calibração, gerava falsos precedentes | `FASE_08.md` | Toda regra de calibração é escrita antes e aplicada só na validação; o teste nunca é usado para ajuste |
| L05 | **Mau resultado pode ser defeito de integração** | Na Fase 5, dois "maus resultados" do LLM eram defeitos de integração (ids de citação, formato); na Fase 7, a falha da F2 era corte por limite de tokens | `FASE_05.md`, `FASE_07.md` | Ler a saída bruta na primeira execução de cada experimento |
| L06 | **Defeito de formato ≠ defeito do modelo** | No Gemini, o relator foi válido em só 0,333 porque o prompt não dava o formato de `consensos`; com instrução + reparo, 1,00 | `FASE_11.md` §3 | Todo campo do JSON pedido no prompt tem formato explícito; reparo de forma determinístico, preservando o conteúdo |
| L07 | **Registrar experimentos negativos** | Schema estrito no Ollama, RRF puro, modelo 3B, orçamento maior de tokens: todos pioraram algo | `AVALIACAO.md` | Experimentos rejeitados ficam na tabela de execuções com o motivo |

## 2. Arquitetura e IA

| # | Lição | O que aconteceu | Evidência | Prática adotada |
|---|---|---|---|---|
| L08 | **O LLM argumenta, as regras verificam** | O verificador determinístico zerou a alucinação numérica sem custo de LLM; precedentes, base legal, hierarquia e vigência por regras garantiram os 6 elementos do RF-20 sem inventar | `FASE_07.md`, `FASE_08.md` | Tudo que é verificável deterministicamente sai do LLM |
| L09 | **Roteamento por regras pode bastar** | Roteador por regras atingiu 0,935 sem LLM; o 3B como roteador foi dispensado | `FASE_07.md` | Testar a solução simples antes do modelo |
| L10 | **Schema estrito pode piorar o LLM local** | No Ollama, o schema estrito ordena as chaves alfabeticamente e induz recusas | `FASE_05.md` §4 | JSON livre com a ordem dos campos no prompt + validação no Python |
| L11 | **Medir antes de assumir o "óbvio"** | fp16 era 5× mais lento que fp32 na GTX 1660 SUPER | `FASE_04.md` | Benchmark curto antes de fixar configuração de desempenho |
| L12 | **Hardware limita a F2; a nuvem resolve só onde a política permite** | Local: p95 387 s. Gemini (corpus acadêmico): p95 100 s. Dados reais continuam locais | `FASE_10.md`, `FASE_11.md` | Política por origem do trecho + reserva local automática |
| L23 | **Recorte sem identificação vira recusa** | No acervo real, o LLM recusava "Qual o contrato do <fornecedor de software>?" (R05) com 8 trechos certos: cláusulas do meio não dizem número, partes nem objeto; o número estava no nome da pasta | `AVALIACAO_REAL.md` §8 | Ficha do documento em todo trecho; abertura do documento quando a ficha não identifica; diagnosticar com códigos fechados pedidos ao próprio LLM local quando não se pode ler o conteúdo |

## 3. Testes e qualidade

| # | Lição | O que aconteceu | Evidência | Prática adotada |
|---|---|---|---|---|
| L13 | **Teste com dublê não testa a montagem real** | Desde a Fase 7, a API passava ao orquestrador o objeto da recuperação em vez da lista de trechos; os testes da API e o E2E usavam orquestrador falso, e as avaliações montavam a recuperação por conta própria. A tela Perguntar falhava com o pipeline real até a validação ao vivo do roteiro de demonstração | `FASE_11.md` §4, commit `bead9a7` | Pelo menos um teste por ponto de composição (fábrica real com dublês só nas bordas) e uma fumaça ao vivo antes de cada entrega |
| L14 | **Navegador real pega o que a API não pega** | E2E no Edge revelou aviso repetido e rótulos errados; o serviço de upload revelou dois defeitos latentes graves (remoção do acervo, desvinculação das decisões) | `FASE_09.md` §3 | E2E com Playwright no Edge do sistema para cada fluxo de aceite |
| L15 | **Ambiente local mascara dependência não declarada** | `python-multipart` instalado no venv local, ausente do `requirements.txt`; só o CI acusou | `FASE_09.md` §3 | CI em ambiente limpo + falhas publicadas como anotações |
| L16 | **Teste não pode depender da máquina do desenvolvedor** | Testes passaram a ler a pasta documental do `.env` local; o servidor tentava baixar o bge-m3 no runner do CI | `FASE_10.md` §7.1 | Raiz de amostra nos testes; servidor nunca baixa modelos ao iniciar |

## 4. Gestão, governança e processo

| # | Lição | O que aconteceu | Evidência | Prática adotada |
|---|---|---|---|---|
| L17 | **Verificar antes de afirmar — e antes de apagar** | Afirmei que as tabelas v1 estavam vazias; a contagem antes da exclusão mostrou dados (o indexador v1 voltara a rodar) | `FASE_10.md` §6 | Contar linhas e fazer backup antes de qualquer exclusão; aprovação explícita |
| L18 | **Aprovação por fase evita retrabalho grande** | Mudanças de rumo (execução local, corpus acadêmico, Gemini só para corpus acadêmico) foram decididas na revisão de cada sprint, com ADR | `CLAUDE.md`, `docs/adr/` | Fase = sprint; revisão = aprovação do responsável; decisão = ADR |
| L19 | **Continuidade exige estado escrito** | Cada nova sessão de trabalho retomou pelo checkpoint (`STATUS.md`, `CONTINUIDADE.md`), sem depender da memória da sessão anterior | `docs/STATUS.md` | Atualizar o checkpoint ao fim de cada tarefa, com a próxima tarefa exata |
| L20 | **Restrições de ambiente viram regras escritas** | Pouca RAM encerrava processos em segundo plano; `sed` corrompia caminhos Windows; `| Out-Null` travava o Ollama | `CLAUDE.md` (particularidades) | Comandos retomáveis com `--max-minutos` em primeiro plano; edição de caminhos só via Python/PowerShell |
| L21 | **Dizer não com justificativa** | Vercel e VPS sugeridos no início conflitavam com LGPD e custo; ficaram como perfil futuro | ADR-001, ADR-008 | Toda ferramenta sugerida passa por avaliação registrada |
| L22 | **Cotas gratuitas são variáveis** | Gemini: 503 de alta demanda em até 15/21 itens e 429 de cota por minuto | `FASE_11.md` §3 | Reserva local, sem dependência crítica de serviço externo |

---

## 5. Recomendações para projetos semelhantes

1. Construa o **golden set e o protocolo de avaliação antes** de comparar modelos.
2. Tire do LLM tudo que for **verificável por regra** (citações, números, vigência, hierarquia).
3. Desconfie de **qualquer métrica perfeita ou ganho grande**: abra amostras brutas.
4. Tenha ao menos **um teste da montagem real** de cada pipeline, além dos testes com dublês.
5. Faça uma **demonstração ao vivo antes da entrega**: ela é também um teste de integração.
6. Escreva o **estado do projeto em arquivos**; trate a sessão de trabalho como descartável.
