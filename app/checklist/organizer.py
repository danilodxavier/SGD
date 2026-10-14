"""Organização VIRTUAL dos documentos que atendem ao checklist.

Apenas agrupa referências no painel e nos relatórios: nenhum arquivo é copiado, movido ou renomeado.
"""
from app.checklist.matcher import ATENDIDO, AUSENTE, DUVIDA, INCOMPATIVEL, NAO_IDENTIFICADO, PARCIAL, VENCIDO

# Só entram nas pastas os documentos que de fato comprovam (ainda que parcialmente ou com validade vencida).
SUPPORTING = {ATENDIDO, PARCIAL, VENCIDO}

FOLDERS = [
    ("CONTRATO", "Contrato"),
    ("ADITIVO", "Termos Aditivos"),
    ("APOSTILAMENTO", "Apostilamentos"),
    ("PORTARIA", "Fiscalização"),
    ("CERTIDAO", "Comprovação de Regularidade"),
    ("FATURA", "Faturas e Notas Fiscais"),
    ("RELATORIO", "Relatórios"),
    ("NOTIFICACAO", "Notificações"),
    ("PLANILHA", "Planilhas"),
    ("EDITAL", "Edital"),
    ("TERMO_REFERENCIA", "Termo de Referência"),
]


def organize(items):
    """Recebe os itens avaliados (com evidências) e devolve as pastas virtuais."""
    docs = {}
    for item in items:
        if item["status"] not in SUPPORTING:
            continue
        for ev in item["evidences"]:
            entry = docs.setdefault(ev["document_id"], {
                "document_id": ev["document_id"],
                "filename": ev["filename"],
                "doc_type": ev["doc_type"],
                "items": [],
            })
            label = f"{item['position']:02d}"
            if label not in entry["items"]:
                entry["items"].append(label)

    folders = []
    known = {code for code, _ in FOLDERS}
    for code, name in FOLDERS + [(None, "Outros")]:
        files = [d for d in docs.values() if (d["doc_type"] == code if code else d["doc_type"] not in known)]
        if files:
            files.sort(key=lambda d: d["filename"].lower())
            folders.append({"name": f"{len(folders) + 1:02d} — {name}", "documents": files})

    def summary(statuses):
        return [{"position": i["position"], "description": i["description"], "status": i["status"]}
                for i in items if i["status"] in statuses]

    return {"folders": folders,
            "without_documents": summary({AUSENTE, NAO_IDENTIFICADO}),
            "to_review": summary({DUVIDA, INCOMPATIVEL})}
