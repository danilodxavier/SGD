"""SAD-091 — Indexação no servidor (RF-22): upload ou atualização incremental do acervo em segundo plano.

Uma execução por vez (thread única). Etapas: extrair → trechos/metadados/FTS → vetores (bge-m3) → reconstruir o
grafo documental (relações, processos, vigência; decisões religadas pela chave do processo). Arquivos enviados são
indexados em modo PARCIAL (nada fora deles é considerado removido). O estado fica em memória para a interface e
cada execução é registrada na tabela `indexacoes`."""
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from app.core.config import settings

log = logging.getLogger(__name__)


class ServicoIndexacao:
    def __init__(self, raiz=None, *, com_embeddings=True, fabrica=None, atualizar_fichas=None):
        self._raiz = raiz
        self.com_embeddings = com_embeddings
        # padrão: SADGD_FICHAS_APOS_INDEXAR (true); testes desligam para não chamar o LLM
        self.atualizar_fichas = (os.environ.get("SADGD_FICHAS_APOS_INDEXAR", "true").lower() in ("1", "true", "sim")
                                 if atualizar_fichas is None else atualizar_fichas)
        self._fabrica = fabrica
        self._trava = threading.Lock()
        self._thread = None
        self.estado = {"executando": False, "etapa": None, "arquivos": [], "resumo": None, "grafo": None,
                       "fichas": None, "erro": None, "inicio": None, "fim": None}

    @property
    def raiz(self) -> Path:
        from app.core.database import get_documents_root  # a mesma raiz da tela Configurações (banco > .env)

        r = Path(self._raiz or get_documents_root())
        return r if r.is_absolute() else (Path(__file__).resolve().parents[2] / r).resolve()

    def _conexao(self):
        from app.infrastructure.sqlite.conexao import conectar

        return (self._fabrica or (lambda: conectar(settings.database_path)))()

    def iniciar(self, relativos=None) -> bool:
        """relativos: caminhos (relativos à raiz) dos arquivos enviados; None = acervo inteiro (incremental)."""
        with self._trava:
            if self.estado["executando"]:
                return False
            self.estado.update(executando=True, etapa="preparando", arquivos=list(relativos or []), resumo=None,
                               grafo=None, fichas=None, erro=None,
                               inicio=datetime.now().isoformat(timespec="seconds"), fim=None)
            self._thread = threading.Thread(target=self._executar, args=(relativos,), daemon=True,
                                            name="sadgd-indexacao")
            self._thread.start()
            return True

    def aguardar(self, timeout=None):
        if self._thread:
            self._thread.join(timeout)
        return self.estado

    def _executar(self, relativos):
        t0 = time.perf_counter()
        try:
            from app.application.ingestao.indexador import IndexarCorpus
            from app.application.linha_do_tempo.construcao import construir_grafo
            from app.domain.documentos import CorpusOrigem
            from app.infrastructure.extratores.adaptador import extensoes_suportadas, extrair
            from app.infrastructure.fonte_arquivos import listar, sha256
            from app.infrastructure.sqlite.repositorio_grafo import RepositorioGrafoSqlite
            from app.infrastructure.sqlite.repositorio_indexacao import RepositorioIndexacaoSqlite
            from app.infrastructure.sqlite.vetores import SqliteVecStore

            emb = None
            if self.com_embeddings:
                self.estado["etapa"] = "carregando modelo de embeddings"
                from app.infrastructure.modelos import compartilhados

                emb = compartilhados.embedder()
            self.estado["etapa"] = "lendo e indexando arquivos"
            arquivos = listar(self.raiz, extensoes_suportadas())
            if relativos is not None:
                alvo = set(relativos)
                arquivos = [a for a in arquivos if a.relativo in alvo]
            caso = IndexarCorpus(RepositorioIndexacaoSqlite(self._conexao), extrair, sha256, emb,
                                 SqliteVecStore(self._conexao) if emb else None,
                                 origem_padrao=CorpusOrigem(settings.corpus_origem),
                                 modelo=emb.nome_modelo if emb else "")
            r = caso.executar(str(self.raiz), arquivos, parcial=relativos is not None)
            self.estado["resumo"] = {k: v for k, v in r.__dict__.items() if k != "falhas"} | {
                "falhas": [f"{a}: {e}" for a, e in r.falhas]}
            self.estado["etapa"] = "reconstruindo o grafo documental"
            from app.infrastructure.sqlite.conexao import conectar

            self.estado["grafo"] = construir_grafo(RepositorioGrafoSqlite(
                self._fabrica or (lambda: conectar(settings.database_path, vetores=False))))
            self.estado["etapa"] = "atualizando as fichas dos contratos"
            self.estado["fichas"] = self._atualizar_fichas()
            self.estado["etapa"] = "concluída"
        except Exception as exc:  # noqa: BLE001 - registrado e exibido na interface
            log.exception("Falha na indexação do SAD-GD")
            self.estado.update(erro=f"{type(exc).__name__}: {exc}"[:300], etapa="falhou")
        finally:
            self.estado.update(executando=False, fim=datetime.now().isoformat(timespec="seconds"),
                               segundos=round(time.perf_counter() - t0, 1))


    def _atualizar_fichas(self) -> dict:
        """Fichas de contrato (ADR-015) refletem o acervo recém-indexado; falha não invalida a indexação."""
        if not self.atualizar_fichas:
            return {"pulada": "desativada"}
        try:
            from app.infrastructure.fichas_servico import atualizar_fichas

            return atualizar_fichas(self._fabrica)
        except Exception as exc:  # noqa: BLE001 - indexação continua válida; fichas na próxima execução
            log.exception("Falha ao atualizar as fichas dos contratos")
            return {"erro": f"{type(exc).__name__}: {exc}"[:300]}


servico = ServicoIndexacao()
