# ADR-008 — Frontend: HTML/CSS/JS servido pelo FastAPI (sem Next.js nesta versão)

| Campo | Valor |
|---|---|
| Status | **Aceito** (aprovação da Fase 2 em 2026-11-16) |
| Data | 2026-11-16 |
| Requisitos | RF-13, RF-21, RF-22, RNF-02, RNF-13 |

## Contexto

O prompt mestre sugere Next.js na Vercel. Com ADR-001 a API roda em `127.0.0.1`: um frontend na Vercel não alcança o backend local sem túnel público, o que expõe dados. A v1 já tem SPA em JS puro com tokens de design do Governo de MT, página de acessibilidade e verificação de contraste (commits "Fase 2/3" de UI). Node.js está instalado na máquina, então Next.js local seria possível.

## Opções

| Critério | JS puro (atual, evoluído) | Next.js local | Next.js na Vercel |
|---|---|---|---|
| Funciona 100% offline/local | ✅ | ✅ | ❌ (precisa de túnel) |
| Reaproveita padrão Gov-MT e acessibilidade já feitos | ✅ | parcial (reescrever componentes) | parcial |
| Etapa de build / toolchain extra | nenhuma | npm + build | npm + build + deploy |
| Risco LGPD | baixo | baixo | alto se houver túnel |
| Esforço para chat, painel de fontes, pareceres, linha do tempo | médio | médio | médio + infraestrutura |

## Decisão

Manter **HTML/CSS/JS puro (ES modules)** servido pelo FastAPI, evoluindo a interface v1 com novas telas (chat F1/F2, painel de fontes, pareceres por agente, linha do tempo, decisões, upload). A linha do tempo é renderizada em **SVG próprio acessível** (sem dependência de CDN). Bibliotecas de terceiros, se necessárias, ficam **vendorizadas** em `frontend\vendor\` com versão e licença registradas.

Next.js/Vercel ficam como evolução futura junto com o perfil de implantação em nuvem (ADR-001).

## Consequências

- (+) Zero build, funciona offline, mantém a identidade visual e a acessibilidade (WCAG 2.1 AA).
- (−) Menos componentes prontos; mitigado por módulos JS pequenos e testes E2E na Fase 9.
- Desvio consciente da stack sugerida, justificado por ADR-001 e pelo reaproveitamento.
