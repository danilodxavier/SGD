"""Gera/atualiza as fichas de contrato: agrupamento + inventário (determinísticos) + extração com o LLM local."""
import re
import time
from typing import Protocol

from app.application.fichas.agrupamento import (
    agrupar,
    chaves_no_texto,
    documento_principal,
    normalizar,
)
from app.application.fichas.extracao import mensagens, selecionar_trechos, validar

TIPOS_INVENTARIO = {"contrato", "aditivo", "apostilamento", "nota_empenho", "nota_fiscal", "pagamento",
                    "termo_recebimento", "portaria", "portaria_designacao", "extrato_publicacao", "notificacao",
                    "termo_rescisao", "ordem_reinicio", "ordem_suspensao", "termo_paralisacao", "termo_retomada",
                    "relatorio_fiscalizacao", "garantia", "certidao", "proposta", "termo_referencia", "oficio",
                    "relatorio", "boletim_medicao", "parecer_juridico", "despacho"}


class RepositorioFichasPort(Protocol):
    def documentos_acervo(self) -> list: ...
    def trechos_do_documento(self, documento_id: int) -> list: ...
    def ficha(self, chave: str) -> dict | None: ...
    def salvar(self, ficha: dict) -> None: ...


TIPOS_PELO_TITULO = [("ordem_servico", re.compile(r"orde(?:m|ns) de servic"))]  # tipos que o classificador não tem


def _tipo(d) -> str | None:
    titulo = normalizar(f"{d.titulo or ''} {d.abertura[:200]}")
    return next((t for t, padrao in TIPOS_PELO_TITULO if padrao.search(titulo)), d.tipo)


def inventario(grupo) -> list[dict]:
    itens = [(d, _tipo(d)) for d in sorted(grupo.documentos, key=lambda d: (d.data or "", d.id))]
    return [{"documento_id": d.id, "tipo": t, "data": d.data, "trecho_id": d.primeiro_trecho}
            for d, t in itens if t in TIPOS_INVENTARIO or t == "ordem_servico"]


def apelidos(grupos) -> dict[str, str]:
    """Outros números de contrato citados nos instrumentos de uma pasta (ex.: renovação) → chave da pasta; números
    citados em mais de uma pasta são ambíguos e ficam de fora."""
    candidatos: dict[str, set] = {}
    for k, g in grupos.items():
        for d in g.documentos:
            if d.tipo in ("contrato", "aditivo", "extrato_publicacao"):
                for outra in chaves_no_texto(f"{d.titulo or ''} {d.abertura}"):
                    if outra != k and outra not in grupos:
                        candidatos.setdefault(outra, set()).add(k)
    return {num: next(iter(ks)) for num, ks in candidatos.items() if len(ks) == 1}


class GerarFichas:
    def __init__(self, repositorio: RepositorioFichasPort, llm, *, max_tokens: int = 600):
        self.repo, self.llm, self.max_tokens = repositorio, llm, max_tokens

    def executar(self, limite_s: float | None = None, refazer: bool = False, ao_progredir=None) -> dict:
        inicio = time.perf_counter()
        grupos = agrupar(self.repo.documentos_acervo())
        mapa_apelidos = apelidos(grupos)
        resumo = {"contratos": len(grupos), "extraidas": 0, "puladas": 0, "sem_documento": 0, "falhas": 0,
                  "pendentes": 0, "campos_aceitos": 0}
        for k, g in sorted(grupos.items()):
            existente = self.repo.ficha(k)
            if existente and existente.get("extracao") == "ok" and not refazer:
                # inventário e apelidos são baratos: sempre atualizados com o acervo
                existente.update(documentos=inventario(g),
                                 apelidos=sorted(a for a, d in mapa_apelidos.items() if d == k))
                self.repo.salvar(existente)
                resumo["puladas"] += 1
                continue
            if limite_s and time.perf_counter() - inicio > limite_s:
                resumo["pendentes"] += 1
                continue
            ficha = {"chave": k, "pasta": g.pasta, "documentos": inventario(g), "campos": {},
                     "apelidos": sorted(a for a, d in mapa_apelidos.items() if d == k), "extracao": "sem_documento"}
            principal = documento_principal(g)
            if principal is not None:
                portarias = sorted((d for d in g.documentos if d.tipo in ("portaria_designacao", "portaria")),
                                   key=lambda d: (d.data or "", d.id), reverse=True)[:2]
                trechos = selecionar_trechos(self.repo.trechos_do_documento(principal.id),
                                             [t for p in portarias for t in self.repo.trechos_do_documento(p.id)[:1]])
                try:
                    r = self.llm.chat(mensagens(trechos), max_tokens=self.max_tokens, temperatura=0.0, json_livre=True)
                    ficha["campos"] = validar(r.json if isinstance(r.json, dict) else {}, trechos)
                    ficha["extracao"] = "ok"
                    resumo["extraidas"] += 1
                    resumo["campos_aceitos"] += len(ficha["campos"])
                except Exception:  # noqa: BLE001 - registra e segue; nova tentativa na próxima execução
                    ficha["extracao"] = "falha"
                    resumo["falhas"] += 1
            else:
                resumo["sem_documento"] += 1
            campos = ficha["campos"]
            ficha["texto_busca"] = normalizar(" ".join(filter(None, [
                g.pasta or "", (campos.get("contratada") or {}).get("valor", ""),
                (campos.get("objeto") or {}).get("valor", "")])))
            self.repo.salvar(ficha)
            if ao_progredir:
                ao_progredir(k, ficha)
        return resumo
