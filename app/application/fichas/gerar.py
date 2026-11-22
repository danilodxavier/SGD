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
from app.application.fichas.extracao import (
    CAMPOS,
    CAMPOS_ADITIVO,
    COMPLEMENTAVEIS,
    mensagens,
    selecionar_trechos,
    trechos_aditivo,
    trechos_complemento,
    validar,
)

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


VERSAO_COMPLEMENTO = 2  # 2: valor atualizado pelo aditivo (fichas com versão menor são complementadas de novo)
VERSAO_ADITIVOS = 2  # 2: cláusula de prorrogação priorizada na seleção de trechos (só os aditivos são relidos)
TIPOS_PELO_TITULO = [("ordem_servico", re.compile(r"orde(?:m|ns) de servic")),
                     ("relatorio_apuracao", re.compile(r"\bapuracao\b|\bapurar\b|apuracao de responsabilidade")),
                     ("notificacao", re.compile(r"notificacao extrajudicial|\bnotificacao\b"))]


def _tipo(d) -> str | None:
    titulo = normalizar(f"{d.titulo or ''} {d.abertura[:200]}")
    return next((t for t, padrao in TIPOS_PELO_TITULO if padrao.search(titulo)), d.tipo)


def inventario(grupo) -> list[dict]:
    itens = [(d, _tipo(d)) for d in sorted(grupo.documentos, key=lambda d: (d.data or "", d.id))]
    return [{"documento_id": d.id, "tipo": t, "data": d.data, "trecho_id": d.primeiro_trecho}
            for d, t in itens if t in TIPOS_INVENTARIO or t in ("ordem_servico", "relatorio_apuracao")]


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

    def complementar(self, limite_s: float | None = None, refazer: bool = False, ao_progredir=None) -> dict:
        """2ª passada: campos que faltaram (extratos de publicação, portarias de designação, resto do instrumento) e
        vigência atual pelo termo aditivo mais recente que prorroga o prazo. Uma vez por ficha (marca `complemento`)."""
        inicio = time.perf_counter()
        grupos = agrupar(self.repo.documentos_acervo())
        resumo = {"fichas": 0, "complementadas": 0, "campos_novos": 0, "vigencia_atual": 0, "pendentes": 0}
        for k, g in sorted(grupos.items()):
            ficha = self.repo.ficha(k)
            if not ficha or ficha.get("extracao") != "ok":
                continue
            resumo["fichas"] += 1
            por_data = sorted(g.documentos, key=lambda d: (d.data or "", d.id))
            recentes = [d.id for d in reversed(por_data) if d.tipo == "aditivo"][:2]
            lidos = set(ficha.get("aditivos_lidos") or [(ficha["campos"].get(c) or {}).get("documento_id")
                                                       for c in ("aditivo_vigencia", "aditivo_valor")])
            if ficha.get("aditivos_versao", 1) < VERSAO_ADITIVOS:
                lidos = set()  # seleção de trechos do aditivo mudou: reler os aditivos (só eles)
            completa = ficha.get("complemento", 0) >= VERSAO_COMPLEMENTO and not refazer
            if completa and set(recentes) <= lidos:
                continue  # já complementada e nenhum aditivo mais recente desde a última leitura
            if limite_s and time.perf_counter() - inicio > limite_s:
                resumo["pendentes"] += 1
                continue
            antes = len(ficha["campos"])
            # ficha já complementada que só ganhou aditivo novo (indexação ou datas corrigidas): só os aditivos
            faltantes = [] if completa else [c for c in COMPLEMENTAVEIS if c not in ficha["campos"]]
            if faltantes:
                extratos = [d for d in por_data if d.tipo == "extrato_publicacao"][:2]
                portarias = [d for d in reversed(por_data) if d.tipo in ("portaria_designacao", "portaria")][:3]
                principal = documento_principal(g)
                fontes = [t for d in extratos for t in self.repo.trechos_do_documento(d.id)[:2]]
                fontes_port = [t for d in portarias for t in self.repo.trechos_do_documento(d.id)[:1]]
                resto = self.repo.trechos_do_documento(principal.id) if principal else []
                enviados = {c["trecho_id"] for c in ficha["campos"].values()}
                trechos = trechos_complemento([fontes, fontes_port, resto], faltantes, enviados)
                if trechos:
                    pedido = {c: CAMPOS[c] for c in faltantes}
                    try:
                        r = self.llm.chat(mensagens(trechos, pedido), max_tokens=self.max_tokens, temperatura=0.0,
                                          json_livre=True)
                        novos = validar(r.json if isinstance(r.json, dict) else {}, trechos, pedido)
                        ficha["campos"].update({c: v for c, v in novos.items() if c not in ficha["campos"]})
                    except Exception:  # noqa: BLE001, S110 - segue sem o complemento; nova tentativa com --refazer
                        pass
            vigencia_ok = valor_ok = False
            for aditivo in [d for d in reversed(por_data) if d.tipo == "aditivo"][:2]:  # do mais recente
                if vigencia_ok and valor_ok:
                    break
                if completa and aditivo.id in lidos:
                    continue  # já lido: os valores dele seguem na ficha
                trechos = trechos_aditivo(self.repo.trechos_do_documento(aditivo.id))
                try:
                    r = self.llm.chat(mensagens(trechos, CAMPOS_ADITIVO), max_tokens=250, temperatura=0.0,
                                      json_livre=True)
                    achados = validar(r.json if isinstance(r.json, dict) else {}, trechos, CAMPOS_ADITIVO)
                except Exception:  # noqa: BLE001
                    achados = {}
                origem = {"valor": aditivo.data or "", "trecho_id": aditivo.primeiro_trecho,
                          "documento_id": aditivo.id}
                if "vigencia_atual_fim" in achados and not vigencia_ok:
                    ficha["campos"].update({c: achados[c] for c in ("vigencia_atual_fim", "prazo_prorrogacao")
                                            if c in achados})
                    ficha["campos"]["aditivo_vigencia"] = origem
                    vigencia_ok = True
                    resumo["vigencia_atual"] += 1
                if "valor_atual" in achados and not valor_ok:
                    ficha["campos"]["valor_atual"] = achados["valor_atual"]
                    ficha["campos"]["aditivo_valor"] = origem
                    valor_ok = True
            ficha["complemento"] = VERSAO_COMPLEMENTO
            ficha["aditivos_lidos"] = sorted(i for i in lidos | set(recentes) if i is not None)
            ficha["aditivos_versao"] = VERSAO_ADITIVOS
            resumo["complementadas"] += 1
            resumo["campos_novos"] += len(ficha["campos"]) - antes
            self.repo.salvar(ficha)
            if ao_progredir:
                ao_progredir(k, ficha)
        return resumo
