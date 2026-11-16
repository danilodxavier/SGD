# ADR-007 — Leitura de documentos e OCR

| Campo | Valor |
|---|---|
| Status | **Proposto** |
| Data | 2026-11-16 |
| Requisitos | RF-01, RF-02, RF-03, RNF-01, RNF-03 |

## Contexto

A v1 já extrai 15+ formatos com `pypdf`/`pypdfium2`, `python-docx`, `openpyxl`, `xlrd`, `olefile` e parsers próprios (ODF, RTF, DOC, PPT), com 238 testes. O OCR da v1 usa o **Windows OCR**, que não é portátil e cuja qualidade em documentos digitalizados antigos é variável. O prompt mestre sugere PyMuPDF, Docling ou Unstructured, e Tesseract.

## Decisão

1. **Manter os extratores da v1** como adaptadores de `ExtratorPort` (já testados).
2. **PDF:** manter `pypdfium2` (licença Apache/BSD) como padrão. **Não adotar PyMuPDF por padrão** porque é **AGPL-3.0** (gratuito, mas copyleft e incompatível com eventual distribuição fechada); fica como adaptador opcional se a extração de layout/tabelas exigir.
3. **OCR:** adicionar **Tesseract 5** (`por`) via `pytesseract` como motor padrão portátil; o Windows OCR continua como alternativa (`OCR_ENGINE=auto|tesseract|windows`). Instalar o Tesseract em `<projeto>\ferramentas\tesseract` (o instalador permite escolher a pasta), apontando `TESSERACT_CMD`, conforme ADR-001.
4. **Docling:** avaliar na Fase 4 apenas para tabelas de contratos (itens, valores). Custo: dependências pesadas e modelos próprios; só entra se houver ganho medido.
5. **Unstructured:** descartado (sobreposição com o que já existe; dependências pesadas).

## Critério de aceite associado

CER ≤ 10% no PDF escaneado de teste (RF-02), comparando Tesseract × Windows OCR; o melhor vira o padrão de `auto`.

## Consequências

- (+) Reaproveitamento máximo; licenças permissivas por padrão.
- (−) Tesseract exige instalação de binário (fora do pip); documentado em `instalar.bat`/manual.
