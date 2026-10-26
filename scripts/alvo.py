"""Cria dados/alvo.json (carteira ideal) a partir da posição do último mês, como ponto de partida.

Uso:
    .venv/bin/python scripts/alvo.py                        # não sobrescreve um alvo existente
    .venv/bin/python scripts/alvo.py --importar [arquivo]   # alvo exportado pelo dashboard (padrão ~/Downloads/alvo.json)
    .venv/bin/python scripts/gerar.py                       # leva o alvo para o dashboard

Depois edite o arquivo: "alvo" é o % de cada classe na carteira (somando 100) e "ativos" é o %
de cada ativo dentro da classe (somando 100). Ativo da carteira que não está em "ativos" tem
alvo 0 (o dashboard sugere não comprar mais ou vender). Ativo em "ativos" que você ainda não
tem entra como compra. Classe sem "ativos" é rebalanceada só no total, o que serve para renda
fixa: o título você escolhe na hora de aplicar.
"""
import argparse
import json
import sys
from pathlib import Path

from config import ALVO
from gerar import BENCH_CLASSE, agrupar_rv, carregar, validar_alvo

SO_CLASSE = {"Renda fixa (CDB/LCA)", "Tesouro Direto", "Crédito privado"}


def arredondar(pesos, casas=1):
    """Percentuais com `casas` decimais que somam exatamente 100 (maiores restos)."""
    tot = sum(pesos.values())
    if tot <= 0:
        return {k: 0 for k in pesos}
    esc = 10 ** casas
    bruto = {k: v / tot * 100 * esc for k, v in pesos.items()}
    out = {k: int(v) for k, v in bruto.items()}
    for k in sorted(bruto, key=lambda k: bruto[k] - out[k], reverse=True)[: 100 * esc - sum(out.values())]:
        out[k] += 1
    return {k: v / esc for k, v in sorted(out.items(), key=lambda x: -x[1])}


def semente(doc, aporte_mensal=0):
    """Alvo igual à composição do mês: o ponto de partida para você ajustar."""
    classes = {}
    for p in agrupar_rv(doc["posicoes"]).values():
        if p["valor"] <= 0:
            continue
        c = classes.setdefault(p["classe"], {"valor": 0.0, "ativos": {}})
        c["valor"] += p["valor"]
        if p["id"].startswith("RV:"):
            c["ativos"][p["ticker"]] = c["ativos"].get(p["ticker"], 0) + p["valor"]
    pct = arredondar({c: v["valor"] for c, v in classes.items()})
    out = {}
    for c in sorted(classes, key=lambda c: list(BENCH_CLASSE).index(c) if c in BENCH_CLASSE else 99):
        out[c] = {"alvo": pct[c]}
        if c not in SO_CLASSE and classes[c]["ativos"]:
            out[c]["ativos"] = arredondar(classes[c]["ativos"])
    return {
        "_leia": "alvo = % da classe na carteira (soma 100); ativos = % dentro da classe (soma 100). "
                 "Ativo fora de 'ativos' tem alvo 0. Classe sem 'ativos' rebalanceia só o total. Rode scripts/gerar.py depois de editar.",
        "aporte_mensal": aporte_mensal,
        "classes": out,
    }


def importar(origem):
    """Valida o alvo exportado pelo dashboard e o move para dados/alvo.json (o anterior vira alvo.anterior.json)."""
    if not origem.exists():
        sys.exit(f"{origem} não existe; no dashboard, use “Exportar alvo.json” na seção Carteira ideal")
    try:
        alvo = json.loads(origem.read_text())
        avisos = validar_alvo(alvo)
    except ValueError as e:  # JSONDecodeError também é ValueError
        sys.exit(f"{origem}: {e}")
    ALVO.parent.mkdir(parents=True, exist_ok=True)
    if ALVO.exists():
        ALVO.replace(ALVO.with_name("alvo.anterior.json"))
    ALVO.write_text(json.dumps(alvo, ensure_ascii=False, indent=2) + "\n")
    origem.unlink()
    for a in avisos:
        print(" -", a)
    print(f"ok -> {ALVO}; rode scripts/gerar.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--importar", nargs="?", const=str(Path.home() / "Downloads" / "alvo.json"), metavar="ARQUIVO")
    args = ap.parse_args()
    if args.importar:
        return importar(Path(args.importar).expanduser())
    if ALVO.exists():
        sys.exit(f"{ALVO} já existe; edite-o (ou apague para recriar a partir da posição atual)")
    docs = carregar()
    if not docs:
        sys.exit("nenhum mês em dados/mensal; rode scripts/importar.py antes")
    ALVO.parent.mkdir(parents=True, exist_ok=True)
    ALVO.write_text(json.dumps(semente(docs[-1]), ensure_ascii=False, indent=2) + "\n")
    print(f"ok -> {ALVO} (composição de {docs[-1]['mes']}; ajuste os percentuais e o aporte_mensal)")


if __name__ == "__main__":
    main()
