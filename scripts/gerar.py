"""Calcula a evolução mês a mês a partir de dados/mensal/*.json e grava relatorios/data.js.

Uso:
    .venv/bin/python scripts/gerar.py

Rentabilidade mensal (Dietz modificado):
    ganho   = patrimônio final - patrimônio inicial - aportes líquidos + proventos
    retorno = ganho / (patrimônio inicial + aportes líquidos / 2)

Aportes líquidos (fluxos) por tipo de ativo:
    - bolsa: aba Negociações (compras - vendas a preço médio)
    - CDB/LCA/Tesouro: a B3 não informa aplicações e resgates; são deduzidos comparando
      os dois meses (título novo = aplicação, título que sumiu = resgate/vencimento,
      mudança de quantidade = aplicação/resgate parcial ao preço do mês)
"""
import json
import sys
from collections import defaultdict
from datetime import date

import mercado
import setores
from config import ALVO, DIR_MENSAL, SAIDA

EXTERIOR = "Exterior (BDRs e ETFs)"
BENCH_CLASSE = {
    "Ações Brasil": "Ibovespa",
    EXTERIOR: "S&P 500 (R$)",
    "FIIs": "IFIX",
    "Cripto": None,  # sem índice: o resultado da classe conta todo como alocação
    "Renda fixa (CDB/LCA)": "CDI",
    "Tesouro Direto": "CDI",
    "Crédito privado": "CDI",
}
EPS = 1e-6
# limites que o usuário define em dados/alvo.json ("regras"), todos em %; o dashboard aponta o que os quebra
REGRAS = {
    "max_ativo": "de um ativo de renda variável na carteira",
    "max_setor_classe": "de um setor dentro de Ações Brasil, Exterior ou FIIs",
    "max_setor_carteira": "de um setor na carteira toda, somando as classes",
    "min_posicao": "mínimo de uma posição de renda variável (abaixo disso: levar ao mínimo ou zerar)",
    "tolerancia_classe": "desvio aceito entre o % atual e o alvo de cada classe, em p.p.",
}


def classe_economica(p, mapa):
    """A B3 separa por produto (aba BDR, aba ETF); aqui vale o que o ativo carrega.

    ETF de Ibovespa/dividendos vira Ações Brasil, de S&P/global vira Exterior junto com os BDRs,
    de títulos públicos vira Tesouro Direto e de cripto vira Cripto. O setor vem de setores.py;
    sem setor, vale o "Tipo" da aba ETF da B3.
    """
    if p["classe"] == "BDRs (ações globais)":
        return EXTERIOR
    if p["classe"] != "ETFs":
        return p["classe"]
    s = setores.setor(p["ticker"], mapa) or ""
    if s == "Renda fixa":
        return "Tesouro Direto"
    if s == "Cripto" or p.get("estrategia") == "Cripto":
        return "Cripto"
    if s == "Índice amplo (Brasil)":
        return "Ações Brasil"
    if s.startswith("Índice amplo") or p.get("estrategia") == "Renda Variável Global":
        return EXTERIOR
    return "Ações Brasil"


def reclassificar(doc, mapa):
    for p in doc["posicoes"]:
        p["classe_b3"], p["classe"] = p["classe"], classe_economica(p, mapa)
    return doc


def carregar():
    mapa = setores.mapa()
    return [reclassificar(json.loads(p.read_text()), mapa) for p in sorted(DIR_MENSAL.glob("*.json"))]


def agrupar_rv(posicoes):
    """Ações/BDRs/ETFs/FIIs somados por ticker (o mesmo ativo em duas corretoras é uma posição)."""
    out = {}
    for p in posicoes:
        if not p["id"].startswith("RV:"):
            out[p["id"]] = dict(p)
            continue
        k = f"RV:{p['ticker']}"
        if k in out:
            out[k]["quantidade"] += p["quantidade"]
            out[k]["valor"] += p["valor"]
            out[k]["instituicao"] = " + ".join(sorted({*out[k]["instituicao"].split(" + "), p["instituicao"]}))
        else:
            out[k] = {**p, "id": k}
    return out


def calcular_mes(ant, cur, cdi_mes, classe_de, pendentes):
    """pendentes: {id: [qtd, custo]} de negociações que ainda não apareceram na posição.

    A aba Negociações é por data do pregão, mas a posição só muda na liquidação (D+1/D+2),
    então compras dos últimos dias do mês só entram na quantidade do mês seguinte.
    O aporte é reconhecido quando a quantidade muda, ao preço médio da negociação.
    """
    p0, p1 = agrupar_rv(ant["posicoes"]), agrupar_rv(cur["posicoes"])
    trades = defaultdict(lambda: {"compra": 0.0, "venda": 0.0})
    for n in cur["negociacoes"]:
        k = f"RV:{n['ticker']}"
        trades[k]["compra"] += n["qtd_compra"] * n["pm_compra"]
        trades[k]["venda"] += n["qtd_venda"] * n["pm_venda"]
        pend = pendentes.setdefault(k, [0.0, 0.0])
        pend[0] += n["qtd_compra"] - n["qtd_venda"]
        pend[1] += n["qtd_compra"] * n["pm_compra"] - n["qtd_venda"] * n["pm_venda"]

    prov = defaultdict(float)
    for p in cur["proventos"]:
        prov[f"RV:{p['ticker']}"] += p["valor"]

    itens, movimentos, avisos = [], [], []
    for k in sorted(set(p0) | set(p1) | set(trades) | set(prov)):
        a, b = p0.get(k), p1.get(k)
        ref = b or a or {}
        v0, v1 = (a or {}).get("valor", 0.0), (b or {}).get("valor", 0.0)
        q0, q1 = (a or {}).get("quantidade", 0.0), (b or {}).get("quantidade", 0.0)
        classe = ref.get("classe") or classe_de.get(k, "Outros")
        nome = ref.get("ticker") if k.startswith("RV:") else ref.get("nome")
        nome = nome or k.split(":", 1)[1]
        fluxo = 0.0

        if k.startswith("RV:"):
            t = trades.get(k)
            if t:
                if t["compra"]:
                    movimentos.append({"tipo": "Compra", "ativo": nome, "classe": classe, "valor": round(t["compra"], 2)})
                if t["venda"]:
                    movimentos.append({"tipo": "Venda", "ativo": nome, "classe": classe, "valor": round(-t["venda"], 2)})
            dq = q1 - q0
            pend = pendentes.get(k, [0.0, 0.0])
            liquidado = 0.0
            if abs(pend[0]) > EPS and dq * pend[0] > 0:
                liquidado = pend[0] if abs(dq) >= abs(pend[0]) else dq
                pm = pend[1] / pend[0]
                fluxo += liquidado * pm
                pend[0] -= liquidado
                pend[1] -= liquidado * pm
            # compra e venda dentro do mês sem passar pela posição: o caixa é o resultado
            if abs(pend[0]) <= EPS and abs(pend[1]) > 0.005:
                fluxo += pend[1]
                pend[1] = 0.0
            sobra = dq - liquidado
            if abs(sobra) > EPS:
                pu1 = v1 / q1 if q1 > EPS else 0.0
                pu0 = v0 / q0 if q0 > EPS else 0.0
                desdobro = q0 > EPS and q1 > EPS and not (0.83 < q1 / q0 < 1.2) and abs((q1 / q0) * (pu1 / pu0) - 1) < 0.05
                if desdobro:
                    avisos.append(f"{nome}: quantidade {q0:g} → {q1:g} com preço ajustado na mesma proporção; tratado como desdobramento/grupamento (sem aporte)")
                elif q0 < EPS:
                    fluxo += v1
                    avisos.append(f"{nome}: apareceu sem negociação (subscrição, direito ou transferência); tratado como aporte de R$ {v1:,.2f}")
                    movimentos.append({"tipo": "Entrada sem negociação", "ativo": nome, "classe": classe, "valor": round(v1, 2)})
                elif q1 < EPS:
                    fluxo -= v0
                    avisos.append(f"{nome}: saiu sem venda registrada (exercício de direito, incorporação ou transferência); tratado como resgate de R$ {v0:,.2f}")
                    movimentos.append({"tipo": "Saída sem negociação", "ativo": nome, "classe": classe, "valor": round(-v0, 2)})
                else:
                    fluxo += sobra * pu1
                    if abs(sobra) >= 1:
                        avisos.append(f"{nome}: {sobra:+g} unidades sem negociação (subscrição/bonificação/transferência); tratado como aporte de R$ {sobra * pu1:,.2f}")
                    movimentos.append({"tipo": "Ajuste de quantidade", "ativo": nome, "classe": classe, "valor": round(sobra * pu1, 2)})
        else:
            # a B3 mantém o título zerado ("-") no mês em que ele é pago (ex.: ressarcimento do FGC)
            if (a is None or q0 <= EPS) and v1 > EPS:
                fluxo = v1
                movimentos.append({"tipo": "Aplicação", "ativo": nome, "classe": classe, "valor": round(v1, 2), "vencimento": ref.get("vencimento")})
            elif (b is None or q1 <= EPS) and v0 > EPS:
                fluxo = -v0 * (1 + cdi_mes / 100)  # rendeu até sair; aproximação pelo CDI do mês
                venc = ref.get("vencimento") or ""
                tipo = "Vencimento" if venc[:7] <= cur["mes"] else "Resgate"
                movimentos.append({"tipo": tipo, "ativo": nome, "classe": classe, "valor": round(fluxo, 2)})
            elif a and b and abs(q1 - q0) > EPS and q1 > EPS:
                fluxo = (q1 - q0) * v1 / q1
                movimentos.append({"tipo": "Aplicação" if fluxo > 0 else "Resgate parcial", "ativo": nome, "classe": classe, "valor": round(fluxo, 2)})

        ganho = v1 - v0 - fluxo + prov.get(k, 0.0)
        itens.append({"id": k, "classe": classe, "v0": v0, "v1": v1, "fluxo": fluxo, "prov": prov.get(k, 0.0), "ganho": ganho})

    def resumo(lista):
        v0 = sum(i["v0"] for i in lista)
        v1 = sum(i["v1"] for i in lista)
        f = sum(i["fluxo"] for i in lista)
        g = sum(i["ganho"] for i in lista)
        base = v0 + f / 2
        return {"inicial": round(v0, 2), "final": round(v1, 2), "fluxo": round(f, 2), "proventos": round(sum(i["prov"] for i in lista), 2),
                "ganho": round(g, 2), "rent": round(g / base * 100, 4) if base > 1 else None}

    por_classe = defaultdict(list)
    for i in itens:
        por_classe[i["classe"]].append(i)
    ganho_ativo = {i["id"]: round(i["ganho"], 2) for i in itens if abs(i["ganho"]) > 0.005}
    return resumo(itens), {c: resumo(l) for c, l in por_classe.items()}, movimentos, avisos, ganho_ativo


def carregar_alvo():
    """Carteira ideal (dados/alvo.json, opcional): % de cada classe e, dentro dela, % de cada ativo."""
    if not ALVO.exists():
        return None, []
    alvo = json.loads(ALVO.read_text())
    return alvo, validar_alvo(alvo)


def validar_alvo(alvo):
    """Avisos sobre o alvo; levanta ValueError se a estrutura não for usável."""
    classes = alvo.get("classes") if isinstance(alvo, dict) else None
    if not isinstance(classes, dict) or not classes:
        raise ValueError('o alvo precisa de "classes": {"<classe>": {"alvo": %, "ativos": {"TICKER": %}}}')
    for c, v in classes.items():
        nums = [v.get("alvo")] + list((v.get("ativos") or {}).values()) if isinstance(v, dict) else [None]
        if not all(isinstance(n, (int, float)) and n >= 0 for n in nums):
            raise ValueError(f"{c}: percentuais precisam ser números >= 0")
    regras = alvo.get("regras") or {}
    if not isinstance(regras, dict):
        raise ValueError('"regras" precisa ser um objeto: {"max_ativo": %, "max_setor_classe": %, ...}')
    for k, v in regras.items():
        if k not in REGRAS:
            raise ValueError(f"regra desconhecida \"{k}\" (use: {', '.join(REGRAS)})")
        if not isinstance(v, (int, float)) or not 0 < v <= 100:
            raise ValueError(f"regra {k}: precisa ser um % entre 0 e 100")
    avisos = [f"alvo: classe desconhecida \"{c}\" (use: {', '.join(BENCH_CLASSE)})" for c in classes if c not in BENCH_CLASSE]
    tot = sum(v.get("alvo", 0) for v in classes.values())
    if abs(tot - 100) > 0.05:
        avisos.append(f"alvo: as classes somam {tot:g}%, não 100% (o dashboard normaliza)")
    for c, v in classes.items():
        if v.get("ativos") and abs(sum(v["ativos"].values()) - 100) > 0.05:
            avisos.append(f"alvo: os ativos de {c} somam {sum(v['ativos'].values()):g}%, não 100% (o dashboard normaliza)")
    return avisos


def tickers_do_alvo(alvo):
    """Tickers citados no alvo (inclusive os que ainda não estão na carteira)."""
    return [t for c in (alvo or {}).get("classes", {}).values() for t in (c.get("ativos") or {})]


def compactar(p):
    campos = ("id", "ticker", "nome", "classe", "classe_b3", "estrategia", "instituicao", "quantidade", "preco", "valor",
              "emissor", "tipo_rf", "indexador", "vencimento", "aplicado", "liquido")
    return {k: p[k] for k in campos if p.get(k) is not None}


def main():
    docs = carregar()
    if len(docs) < 1:
        sys.exit("nenhum mês em dados/mensal; rode scripts/importar.py antes")
    meses_ret = [d["mes"] for d in docs[1:]]
    bench = mercado.benchmarks(meses_ret)

    classe_de = {}
    for d in docs:
        for p in agrupar_rv(d["posicoes"]).values():
            classe_de[p["id"]] = p["classe"]

    saida, todos_avisos, pendentes = [], [], {}
    for i, d in enumerate(docs):
        mes = {
            "mes": d["mes"],
            "patrimonio": round(sum(p["valor"] for p in d["posicoes"]), 2),
            "posicoes": [compactar(p) for p in d["posicoes"]],
            "proventos": [] if d.get("proventos_do_ano") else d["proventos"],
            "negociacoes": d["negociacoes"],
        }
        if d.get("proventos_do_ano"):
            mes["proventos_ano"] = d["proventos"]  # anual: proventos do ano anterior inteiro
        if i > 0:
            total, classes, movs, avisos, ganho_ativo = calcular_mes(docs[i - 1], d, bench.get("CDI", {}).get(d["mes"], 0.0), classe_de, pendentes)
            mes.update({"resumo": total, "classes": classes, "movimentos": movs, "avisos": avisos, "ganho_ativo": ganho_ativo})
            todos_avisos += [f"{d['mes']} {a}" for a in avisos]
        saida.append(mes)

    for k, (q, c) in pendentes.items():
        if abs(q) > EPS:
            todos_avisos.append(f"{k[3:]}: {q:+g} unidades negociadas ainda não aparecem na posição (liquidação no próximo mês?)")
    alvo, avisos_alvo = carregar_alvo()
    todos_avisos += avisos_alvo
    tickers = sorted({p["ticker"] for d in docs for p in d["posicoes"] if p["id"].startswith("RV:")} | set(tickers_do_alvo(alvo)))
    m = setores.mapa()
    setor = {t: s for t in tickers if (s := setores.setor(t, m))}
    sem_setor = [t for t in tickers if t not in setor and any(p.get("ticker") == t and p["valor"] > 0 for p in docs[-1]["posicoes"])]
    if sem_setor:
        todos_avisos.append(f"sem setor (classifique em dados/setores.json): {', '.join(sem_setor)}")
    data = {"gerado_em": date.today().isoformat(), "meses": saida, "benchmarks": bench, "bench_classe": BENCH_CLASSE,
            "alvo": alvo, "alvo_avisos": avisos_alvo, "setores": setor, "historico": mercado.historico()}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")

    for m in saida[1:]:
        r = m["resumo"]
        cdi = bench.get("CDI", {}).get(m["mes"])
        print(f"{m['mes']}  patrimônio {r['final']:>13,.2f}  aportes {r['fluxo']:>11,.2f}  ganho {r['ganho']:>10,.2f}  "
              f"rent {r['rent']:6.2f}%  CDI {cdi if cdi is not None else float('nan'):5.2f}%")
    ult = saida[-1]
    nomes = {}
    for m in saida:
        for p in m["posicoes"]:
            nomes[f"RV:{p['ticker']}" if p["id"].startswith("RV:") else p["id"]] = p["ticker"] if p["id"].startswith("RV:") else p["nome"]
    ranking = sorted(ult.get("ganho_ativo", {}).items(), key=lambda x: x[1])
    if ranking:
        print(f"\n{ult['mes']} maiores ganhos: " + ", ".join(f"{nomes.get(k, k)} {v:+,.0f}" for k, v in ranking[::-1][:3]))
        print(f"{ult['mes']} maiores perdas: " + ", ".join(f"{nomes.get(k, k)} {v:+,.0f}" for k, v in ranking[:3]))
    print(f"\n{len(todos_avisos)} avisos")
    for a in todos_avisos:
        print(" -", a)
    print(f"ok -> {SAIDA}")


if __name__ == "__main__":
    main()
