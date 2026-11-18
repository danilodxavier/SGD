# Product Backlog — SAD-GD

**Fonte única:** [`backlog.csv`](backlog.csv) (52 itens, 228 pontos). O GitHub renderiza o CSV como tabela.

## Publicação no GitHub Projects (Kanban)

**Publicado em 2026-11-17:** [https://github.com/users/danilodxavier/projects/2](https://github.com/users/danilodxavier/projects/2) — 52 issues (`#1`–`#52`), todas em **Done** e fechadas com comentário apontando a evidência (`docs/fases/FASE_XX.md`); labels `fase-X`, `epico:*`, `prioridade:*` e milestones "Fase 1"–"Fase 11".

Para reproduzir ou atualizar (o `gh` portátil fica em `ferramentas\gh`, fora do Git; credencial no Gerenciador de Credenciais do Windows):

```powershell
$env:GH_CONFIG_DIR = "$PWD\ferramentas\gh\config"; $env:PATH = "$PWD\ferramentas\gh\bin;$env:PATH"
gh auth login --web --scopes project          # autorização no navegador (código de uso único)
powershell -ExecutionPolicy Bypass -File scripts\github\criar_backlog.ps1 -ProjectNumber 2 -Owner danilodxavier
```

O script é idempotente: cria labels `fase-X`, `epico:*`, `prioridade:*`, milestones "Fase X" e uma issue por item (ignora as já existentes pelo prefixo `[SAD-XXX]`). Use `-DryRun` para simular.

Colunas do quadro: **Backlog → Pronto → Em andamento → Em revisão → Concluído**.

## Resumo por épico

| Épico | Fase | Itens | Prioridade predominante |
|---|---|---|---|
| Gerenciamento | 1 | 3 | M |
| Arquitetura | 2 | 12 | M |
| Infraestrutura | 3 | 4 | M |
| Base de conhecimento | 4 | 6 | M |
| RAG F1 | 5 | 6 | M |
| Linha do tempo | 6 | 4 | M |
| Multiagentes | 7 | 6 | M |
| Apoio à decisão | 8 | 2 | M |
| MVP | 9 | 4 | M |
| Otimização | 10 | 2 | S/M |
| Entrega | 11 | 3 | M |

## Definition of Ready (DoR)

Item tem critério de aceite verificável, requisito rastreado, estimativa e dependências conhecidas.

## Definition of Done (DoD)

1. Código revisado (PR) e com testes; testes v1 continuam verdes.
2. Critério de aceite demonstrado com evidência em `docs/fases/FASE_XX.md`.
3. Métricas afetadas reexecutadas e registradas em `docs/AVALIACAO.md`.
4. Modelos/metodologias novos registrados em `MODELOS_IA.md` / `METODOLOGIAS.md`.
5. `docs/STATUS.md` e `CHANGELOG.md` atualizados; commit em Conventional Commits.
