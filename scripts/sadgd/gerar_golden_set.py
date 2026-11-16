"""SAD-052 — Golden set (ADR-011): ≥ 100 perguntas com respostas-chave e fontes esperadas, divididas em
validação (30%) e teste (70%), estratificadas por tipo. Toda fonte é VALIDADA contra o índice: a pergunta só
entra se o dispositivo/evidência existir num trecho indexado do documento esperado.

Uso: python scripts/sadgd/gerar_golden_set.py
Saída: avaliacao/golden_set/{validacao,teste}.jsonl e avaliacao/golden_set/RELATORIO.json
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.application.avaliacao.metricas import Fonte, TrechoAvaliado, julgar, normalizar  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.infrastructure.sqlite.conexao import conectar  # noqa: E402

SAIDA = RAIZ / "avaliacao" / "golden_set"
LEI14133 = "publico/federal/lei/lei14133_2021.htm"

# Corpus público: (pergunta, arquivo, dispositivo, evidência literal, respostas-chave, tipo)
PUBLICOS = [
    ("Quais são as hipóteses em que a licitação é dispensável segundo a Lei nº 14.133/2021?", LEI14133, "art. 75",
     "É dispensável a licitação", [], "F1_complexa"),
    ("Em que situação a licitação é inexigível pela Lei nº 14.133/2021?", LEI14133, "art. 74",
     "inexigível a licitação quando inviável a competição", ["inviável a competição"], "F1_simples"),
    ("Por quanto tempo podem ser prorrogados os contratos de serviços contínuos na Lei nº 14.133/2021?", LEI14133,
     "art. 107", "vigência máxima decenal", ["decenal"], "F1_simples"),
    ("Qual o prazo máximo inicial dos contratos de serviços e fornecimentos contínuos na Lei nº 14.133/2021?",
     LEI14133, "art. 106", "prazo de até 5 (cinco) anos", ["5 (cinco) anos"], "F1_simples"),
    ("Quem deve acompanhar e fiscalizar a execução do contrato segundo a Lei nº 14.133/2021?", LEI14133,
     "art. 117", "fiscais do contrato", ["fiscais do contrato"], "F1_simples"),
    ("Quais sanções podem ser aplicadas ao licitante ou contratado pela Lei nº 14.133/2021?", LEI14133, "art. 156",
     "declaração de inidoneidade para licitar ou contratar", ["advertência", "multa"], "F1_complexa"),
    ("Qual o limite de acréscimos e supressões contratuais previsto na Lei nº 14.133/2021?", LEI14133, "art. 125",
     "25% (vinte e cinco por cento)", ["25%"], "F1_simples"),
    ("Qual o objetivo da Lei nº 14.133/2021 segundo seu art. 1º?", LEI14133, "art. 1º",
     "normas gerais de licitação e contratação", ["normas gerais de licitação"], "F1_simples"),
    ("Quais leis foram revogadas pela Lei nº 14.133/2021?", LEI14133, "art. 193", "Revogam-se", ["8.666"],
     "linha_do_tempo"),
    ("Qual o prazo para interposição de recurso administrativo na Lei nº 9.784/1999?",
     "publico/federal/lei/lei9784_1999.htm", "art. 59", "prazo de dez dias", ["dez dias"], "F1_simples"),
    ("Das decisões administrativas cabe recurso por quais razões, segundo a Lei nº 9.784/1999?",
     "publico/federal/lei/lei9784_1999.htm", "art. 56", "razões de legalidade e de mérito",
     ["legalidade", "mérito"], "F1_simples"),
    ("O que é dado pessoal segundo a LGPD?", "publico/federal/lei/lei13709_2018.htm", "art. 5º",
     "informação relacionada a pessoa natural identificada ou identificável", ["pessoa natural"], "F1_simples"),
    ("Qual o objeto da Lei Anticorrupção (Lei nº 12.846/2013)?", "publico/federal/lei/lei12846_2013.htm", "art. 1º",
     "responsabilização objetiva administrativa e civil de pessoas jurídicas", ["pessoas jurídicas"], "F1_simples"),
    ("O que dispõe a Lei de Acesso à Informação no seu art. 1º?", "publico/federal/lei/lei12527_2011.htm", "art. 1º",
     "procedimentos a serem observados pela União, Estados, Distrito Federal e Municípios", ["acesso a informações"],
     "F1_simples"),
    ("A Lei nº 8.666/1993 ainda está em vigor?", "publico/federal/lei/lei8666_1993.htm", None,
     "Revogado pela Lei nº 14.133", ["14.133"], "linha_do_tempo"),
    ("A Lei nº 10.520/2002 (pregão) ainda está em vigor?", "publico/federal/lei/lei10520_2002.htm", None,
     "Revogado pela Lei nº 14.133", ["14.133"], "linha_do_tempo"),
    ("O Decreto nº 7.892/2013 (registro de preços) continua vigente?", "publico/federal/decreto/d7892_2013.htm", None,
     "Revogado pelo Decreto nº 11.462", ["11.462"], "linha_do_tempo"),
    ("Qual decreto regulamenta atualmente o sistema de registro de preços previsto na Lei nº 14.133/2021?",
     "publico/federal/decreto/d11462_2023.htm", "art. 1º", "sistema de registro de preços", ["11.462"],
     "F1_simples"),
    ("O que a Constituição Federal estabelece sobre a obrigatoriedade de licitação no art. 37, XXI?",
     "publico/federal/constituicao/cf1988.htm", None, "processo de licitação pública que assegure igualdade de "
     "condições a todos os concorrentes", ["igualdade de condições"], "F1_simples"),
    ("Quais princípios regem a administração pública segundo o art. 37 da Constituição?",
     "publico/federal/constituicao/cf1988.htm", None, "legalidade, impessoalidade, moralidade, publicidade e "
     "eficiência", ["impessoalidade", "eficiência"], "F1_simples"),
    ("Qual o objetivo da Lei de Responsabilidade Fiscal segundo seu art. 1º?",
     "publico/federal/lei_complementar/lcp101_2000.htm",
     "art. 1º", "normas de finanças públicas voltadas para a responsabilidade na gestão fiscal",
     ["responsabilidade na gestão fiscal"], "F1_simples"),
    ("Quem pode ser sujeito passivo de ato de improbidade segundo a Lei nº 8.429/1992?",
     "publico/federal/lei/lei8429_1992.htm", None, "improbidade administrativa", [], "F1_complexa"),
]

AUSENTES = [
    "Qual é o valor global do Contrato nº 999/2024?",
    "Qual o número da nota de empenho do Contrato nº 012/2023?",
    "Em que data o Contrato nº 058/2023 foi publicado no Diário Oficial?",
    "Qual o nome do preposto da contratada no Contrato nº 031/2023?",
    "Qual o valor da garantia contratual prestada no Contrato nº 072/2024?",
    "Quantos funcionários a empresa Brilho Serviços Gerais Ltda. alocou no contrato?",
    "Qual o endereço da sede da empresa Nuvem Clara Tecnologia S.A.?",
    "Qual o resultado do pregão eletrônico de 2026 para aquisição de veículos?",
    "Qual a pontuação mínima da matriz de sustentabilidade definida no Decreto nº 2.087/2025?",
    "Quem é o ordenador de despesas que aprovou a Instrução Normativa nº 03/2025?",
    "Qual foi o índice de satisfação dos usuários com o serviço de copeiragem?",
    "Qual o valor do contrato de manutenção de elevadores da SEGEP?",
]


def carregar_trechos():
    conn = conectar(settings.database_path)
    por_doc = defaultdict(list)
    for r in conn.execute("SELECT d.caminho_relativo, t.dispositivo, t.texto, t.subdispositivos FROM trechos t "
                          "JOIN documentos d ON d.id = t.documento_id"):
        subs = json.loads(r["subdispositivos"]) if r["subdispositivos"] else []
        por_doc[r["caminho_relativo"]].append(TrechoAvaliado(r["caminho_relativo"], r["dispositivo"], r["texto"],
                                                             subs))
    conn.close()
    return por_doc


def fonte(arquivo, dispositivo=None, evidencia=None):
    return {"documento": arquivo, "dispositivo": dispositivo, "evidencia": evidencia}


def item(tipo, pergunta, fontes, chaves=(), classificacao="fato", origem="sintetico", resposta="", **extra):
    return {"tipo": tipo, "pergunta": pergunta, "resposta_referencia": resposta, "respostas_chave": list(chaves),
            "classificacao_esperada": classificacao, "fontes_esperadas": fontes, "origem": origem,
            "revisado_por": "pendente", **extra}


def perguntas_sinteticas(gab):
    docs = {d["id"]: d for d in gab["documentos"]}
    contraditos = defaultdict(set)
    for c in gab["contradicoes"]:
        for d in c["documentos"]:
            contraditos[d].add(c["campo"])
    itens = []
    for d in gab["documentos"]:
        if d["tipo_documental"] != "contrato":
            continue
        f, n, arq = d["fatos"], d["numero"], d["arquivo"]
        if "valor_global" in contraditos[d["id"]]:
            outro = next(c for c in gab["contradicoes"] if d["id"] in c["documentos"] and c["campo"] == "valor_global")
            oid = next(x for x in outro["documentos"] if x != d["id"])
            itens.append(item("F1_complexa", f"Qual é o valor global do Contrato nº {n}?",
                              [fonte(arq, "cláusula terceira", f["valor_global"]),
                               fonte(docs[oid]["arquivo"], None, outro["valores"][oid])],
                              [f["valor_global"], outro["valores"][oid]], "conflito",
                              resposta=f"Divergência: {f['valor_global']} no contrato e {outro['valores'][oid]} "
                                       f"no documento {docs[oid]['titulo']}."))
        else:
            itens.append(item("F1_simples", f"Qual é o valor global do Contrato nº {n}?",
                              [fonte(arq, "cláusula terceira", f["valor_global"])], [f["valor_global"]],
                              resposta=f"{f['valor_global']}."))
        itens.append(item("F1_simples", f"Qual o período de vigência original do Contrato nº {n}?",
                          [fonte(arq, "cláusula segunda", f["vigencia_fim"])],
                          [f["vigencia_inicio"], f["vigencia_fim"]],
                          resposta=f"De {f['vigencia_inicio']} a {f['vigencia_fim']}."))
        alterna = int(n.split("/")[0]) % 2
        if alterna:
            itens.append(item("F1_simples", f"Qual o CNPJ da empresa contratada no Contrato nº {n}?",
                              [fonte(arq, None, f["cnpj"])], [f["cnpj"]], resposta=f["cnpj"]))
        else:
            itens.append(item("F1_simples", f"Qual empresa é a contratada no Contrato nº {n}?",
                              [fonte(arq, None, f["contratada"])], [f["contratada"]], resposta=f["contratada"]))

    # linha do tempo a partir das relações do gabarito
    vistos = set()
    for r in gab["relacoes"]:
        if r["origem"].startswith("PUB:"):
            continue
        o, dst = docs[r["origem"]], docs[r["destino"]]
        rotulo_o = o["titulo"].split(",")[0].split(" — ")[0].title()
        chave = (r["tipo"], r["origem"])
        if chave in vistos:
            continue
        vistos.add(chave)
        fontes_lt = [fonte(dst["arquivo"], None, r["evidencia"])]
        if r["tipo"] == "aditivo" and dst["fatos"].get("vigencia_fim"):
            numero = o["numero"]
            itens.append(item("linha_do_tempo", f"Após o termo aditivo de prorrogação, até quando vigora o Contrato "
                                                f"nº {numero}?", fontes_lt + [fonte(o["arquivo"], "cláusula segunda")],
                              [dst["fatos"]["vigencia_fim"]], "fato", relacoes_esperadas=[r],
                              resposta=f"Até {dst['fatos']['vigencia_fim']}, conforme {dst['titulo']}."))
        elif r["tipo"] == "revogacao":
            itens.append(item("linha_do_tempo", f"A {rotulo_o} ainda está vigente?", fontes_lt,
                              [dst["numero"]], "fato", relacoes_esperadas=[r],
                              resposta=f"Não. Foi revogada pela {dst['titulo'].split(',')[0].title()}."))
        elif r["tipo"] == "substituicao":
            itens.append(item("linha_do_tempo", f"O que substituiu a {rotulo_o}?" if o["tipo_documental"] != "contrato"
                              else f"Qual contrato substituiu o Contrato nº {o['numero']}?", fontes_lt,
                              [dst["numero"]], "fato", relacoes_esperadas=[r],
                              resposta=f"{dst['titulo'].split(',')[0].title()}."))
        elif r["tipo"] == "ruptura":
            itens.append(item("linha_do_tempo", f"Houve suspensão, paralisação ou extinção relacionada ao "
                                                f"{rotulo_o}? Qual documento registra isso?", fontes_lt,
                              [], "fato",  # número interno do termo nem sempre aparece no texto
                              relacoes_esperadas=[r], resposta=f"Sim: {dst['titulo']}."))
        elif r["tipo"] == "retomada":
            itens.append(item("linha_do_tempo", f"Após a interrupção registrada no {dst['titulo'].split(' — ')[-1]}, "
                                                f"quando as atividades foram retomadas?", fontes_lt,
                              [], "fato", relacoes_esperadas=[r], resposta=f"Conforme {dst['titulo']}."))
        elif r["tipo"] == "alteracao" and dst["tipo_documental"] == "apostilamento":
            itens.append(item("F1_complexa", f"Qual reajuste foi apostilado ao {rotulo_o}?", fontes_lt,
                              [dst["fatos"]["reajuste"]] if dst["fatos"].get("reajuste") else [],
                              "fato", relacoes_esperadas=[r], resposta=dst["fatos"].get("reajuste") or ""))
    # contradição de vigência (P07)
    for c in gab["contradicoes"]:
        if c["campo"] == "vigencia_fim":
            a, b = (docs[x] for x in c["documentos"])
            itens.append(item("F1_complexa", "Qual é a data de término da vigência do Contrato nº 058/2023 após o "
                                             "1º termo aditivo?",
                              [fonte(a["arquivo"], None, c["valores"][a["id"]]),
                               fonte(b["arquivo"], None, c["valores"][b["id"]])],
                              list(c["valores"].values()), "conflito",
                              resposta="Divergência entre o termo aditivo e o apostilamento."))
    itens.append(item("linha_do_tempo", "Qual é atualmente o prazo para o fiscal técnico atestar as notas fiscais?",
                      [fonte(docs["S032"]["arquivo"], "art. 2º", "2 (dois) dias úteis")], ["2 (dois) dias"], "fato",
                      resposta="2 (dois) dias úteis, conforme a Portaria nº 040/2025 (as portarias anteriores foram "
                               "revogadas)."))
    itens.append(item("linha_do_tempo", "Qual o número mínimo de cotações exigido atualmente na pesquisa de preços?",
                      [fonte(docs["S041"]["arquivo"], "art. 2º", "4 (quatro) cotações")], ["4 (quatro)"], "fato",
                      resposta="4 (quatro) cotações, conforme a IN nº 03/2025, que substituiu a IN nº 01/2022."))
    return itens


def perguntas_f2(gab):
    docs = {d["id"]: d for d in gab["documentos"]}
    arq = {k: v["arquivo"] for k, v in docs.items()}
    base = [
        ("Devo prorrogar novamente o Contrato nº 044/2023 de vigilância?", ["S020", "S022", "S102"],
         ["gestor_publico", "fiscal_contrato", "analista_orcamentario_financeiro"]),
        ("Posso contratar novamente a empresa Brilho Serviços Gerais Ltda.?", ["S006", "S005", "S101"],
         ["gestor_publico", "procurador_estado", "controlador_geral"]),
        ("É recomendável pagar a próxima fatura do Contrato nº 044/2023 considerando o relatório de fiscalização?",
         ["S020", "S021"], ["gestor_publico", "fiscal_contrato", "controlador_geral"]),
        ("Devo aplicar sanção à contratada do Contrato nº 012/2023 antes da rescisão?", ["S005", "S006", "S001"],
         ["gestor_publico", "advogado", "fiscal_contrato"]),
        ("Vale a pena aditar o valor da obra da Escola Estadual Pedra Azul novamente?", ["S070", "S073", "S074"],
         ["gestor_publico", "fiscal_contrato", "analista_orcamentario_financeiro"]),
        ("Devo retomar as turmas do Convênio nº 007/2023 já em 2025?", ["S090", "S091", "S092"],
         ["gestor_publico", "analista_administrativo", "controlador_geral"]),
        ("A compra de mobiliário pode prosseguir sem a declaração orçamentária?", ["S081", "S082"],
         ["gestor_publico", "procurador_estado", "analista_orcamentario_financeiro"]),
        ("Qual decreto devo seguir para exigir critérios de sustentabilidade nos termos de referência?",
         ["S052", "S050"], ["gestor_publico", "procurador_estado", "especialista_licitacoes"]),
        ("Devo usar a IN nº 01/2022 ou a IN nº 03/2025 na pesquisa de preços do novo pregão?", ["S041", "S040"],
         ["gestor_publico", "especialista_licitacoes", "analista_administrativo"]),
        ("Posso designar o servidor Joaquim Pereira Lins como fiscal de outro contrato?", ["S111", "S110"],
         ["gestor_publico", "analista_administrativo"]),
        ("Devo prorrogar o Contrato nº 058/2023 de manutenção predial considerando a data divergente?",
         ["S061", "S062"],
         ["gestor_publico", "fiscal_contrato", "advogado"]),
        ("Devo prorrogar o contrato de suporte do sistema de protocolo (Contrato nº 031/2023)?", ["S010", "S013"],
         ["gestor_publico", "fiscal_contrato", "analista_orcamentario_financeiro"]),
    ]
    itens = []
    for pergunta, ids, agentes in base:
        itens.append(item("F2", pergunta, [fonte(arq[i]) for i in ids], [], "inferencia", agentes_esperados=agentes))
    # F2 a partir das famílias: substituição após rescisão e contradição de valor
    familias = [r for r in gab["relacoes"] if r["tipo"] == "substituicao" and docs[r["origem"]]["tipo_documental"]
                == "contrato"]
    for r in familias[:5]:
        o = docs[r["origem"]]
        itens.append(item("F2", f"A contratação substituta do Contrato nº {o['numero']} foi a melhor alternativa ou "
                                f"devo licitar novamente?", [fonte(o["arquivo"]), fonte(docs[r["destino"]]["arquivo"])],
                          [], "inferencia", agentes_esperados=["gestor_publico", "especialista_licitacoes",
                                                               "procurador_estado"]))
    contradicoes = [c for c in gab["contradicoes"] if c["campo"] == "valor_global"][1:6]
    for c in contradicoes:
        a, b = (docs[x] for x in c["documentos"])
        itens.append(item("F2", f"Como devo tratar a divergência de valor do Contrato nº {a['numero']} antes de "
                                f"autorizar pagamentos?", [fonte(a["arquivo"]), fonte(b["arquivo"])], [], "inferencia",
                          agentes_esperados=["gestor_publico", "controlador_geral",
                                             "analista_orcamentario_financeiro"]))
    return itens


def validar(itens, por_doc):
    aceitos, rejeitados = [], []
    for it in itens:
        ok = True
        for f in it["fontes_esperadas"]:
            trechos = por_doc.get(f["documento"], [])
            if not trechos:
                ok = False
                break
            if f["dispositivo"] or f["evidencia"]:
                alvo = Fonte(f["documento"], f["dispositivo"], f["evidencia"])
                if not any(julgar(t, [alvo])[0] == 2 for t in trechos):
                    ok = False
                    break
        # respostas-chave de itens factuais precisam existir em algum trecho das fontes (sem gabarito inventado)
        if ok and it["respostas_chave"] and it["classificacao_esperada"] != "ausencia":
            textos = " ".join(normalizar(t.texto) for f in it["fontes_esperadas"] for t in por_doc[f["documento"]])
            ok = all(normalizar(c) in textos for c in it["respostas_chave"])
        (aceitos if ok else rejeitados).append(it)
    return aceitos, rejeitados


def main():
    gab = json.loads((RAIZ / "corpus/sintetico/GABARITO.json").read_text(encoding="utf-8"))
    itens = perguntas_sinteticas(gab) + perguntas_f2(gab)
    for p, arq, disp, ev, chaves, tipo in PUBLICOS:
        itens.append(item(tipo, p, [fonte(arq, disp, ev)], chaves, origem="publico"))
    for p in AUSENTES:
        itens.append(item("ausente", p, [], [], "ausencia", resposta="Não localizei essa informação nos documentos "
                                                                     "disponibilizados."))
    aceitos, rejeitados = validar(itens, carregar_trechos())
    rng = random.Random(20261116)  # noqa: S311 - divisão reprodutível, sem uso criptográfico
    por_tipo = defaultdict(list)
    for it in aceitos:
        por_tipo[it["tipo"]].append(it)
    validacao, teste = [], []
    for tipo in sorted(por_tipo):
        grupo = por_tipo[tipo]
        rng.shuffle(grupo)
        corte = round(len(grupo) * 0.3)
        validacao += grupo[:corte]
        teste += grupo[corte:]
    for conjunto, lista in (("validacao", validacao), ("teste", teste)):
        for i, it in enumerate(lista, start=1):
            it["id"] = f"{'V' if conjunto == 'validacao' else 'T'}{i:03d}-{it['tipo']}"
    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome, lista in (("validacao", validacao), ("teste", teste)):
        with (SAIDA / f"{nome}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for it in lista:
                f.write(json.dumps({"id": it.pop("id"), **it}, ensure_ascii=False) + "\n")
    relatorio = {"total": len(aceitos), "rejeitados_na_validacao": len(rejeitados),
                 "por_tipo": dict(Counter(i["tipo"] for i in aceitos)),
                 "por_origem": dict(Counter(i["origem"] for i in aceitos)),
                 "por_classificacao": dict(Counter(i["classificacao_esperada"] for i in aceitos)),
                 "validacao": len(validacao), "teste": len(teste),
                 "rejeitados": [{"pergunta": r["pergunta"], "fontes": r["fontes_esperadas"]} for r in rejeitados]}
    (SAIDA / "RELATORIO.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in relatorio.items() if k != "rejeitados"}, ensure_ascii=False, indent=2))
    for r in rejeitados:
        print("[REJEITADO]", r["pergunta"])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
