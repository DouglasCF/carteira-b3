"""Move os relatórios da B3 de ~/Downloads para dados/b3/ e normaliza cada mês em dados/mensal/.

Uso:
    .venv/bin/python scripts/importar.py [--origem ~/Downloads] [--substituir] [--simular]

Imprime um JSON com o que foi feito, para a skill /atualizar-carteira resumir.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import b3
from config import DIR_B3, DIR_MENSAL
PADRAO = "relatorio-consolidado-*.xlsx"


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def proximo_mes(m):
    a, n = map(int, m.split("-"))
    return f"{a + n // 12}-{n % 12 + 1:02d}"


def importar_downloads(origem, substituir, simular):
    feitos = {"importados": [], "duplicados": [], "conflitos": [], "invalidos": []}
    for src in sorted(origem.glob(PADRAO)):
        mes = b3.mes_do_arquivo(src.name)
        if not mes:
            feitos["invalidos"].append({"arquivo": src.name, "erros": ["nome fora do padrão mensal/anual"]})
            continue
        erros = b3.validar(src)
        if erros:
            feitos["invalidos"].append({"arquivo": src.name, "erros": erros})
            continue
        dst = DIR_B3 / f"{mes}.xlsx"
        item = {"arquivo": src.name, "mes": mes}
        if dst.exists():
            if sha256(dst) == sha256(src):
                feitos["duplicados"].append(item)
                if not simular:
                    src.unlink()  # cópia idêntica do que já está no projeto
                continue
            if not substituir:
                feitos["conflitos"].append(item)
                continue
            item["substituiu"] = True
        if not simular:
            shutil.move(str(src), dst)
        feitos["importados"].append(item)
    return feitos


def normalizar_todos():
    DIR_MENSAL.mkdir(parents=True, exist_ok=True)
    resumo, avisos = [], []
    meses = sorted(p.stem for p in DIR_B3.glob("*.xlsx"))
    for mes in meses:
        src = DIR_B3 / f"{mes}.xlsx"
        dados = b3.ler(src)
        # o anual traz proventos do ano inteiro; não dá para atribuí-los a dezembro
        anual = mes.endswith("-12") and not dados["negociacoes"] and any(p["data"] is None for p in dados["proventos"])
        doc = {"mes": mes, "fonte": src.name, "sha256": sha256(src), "proventos_do_ano": anual, **dados}
        (DIR_MENSAL / f"{mes}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))

        # confere a soma das posições com o "Total" que a própria B3 escreve em cada aba
        por_aba = {
            "Posição - Ações": "Ações Brasil", "Posição - BDR": "BDRs (ações globais)", "Posição - ETF": "ETFs",
            "Posição - Fundos": "FIIs", "Posição - Tesouro Direto": "Tesouro Direto",
        }
        for aba, total in dados["totais_b3"].items():
            if total is None:
                continue
            if aba == "Posição - Renda Fixa":
                soma = sum(p["valor"] for p in dados["posicoes"] if p["id"].startswith("RF:"))
            else:
                soma = sum(p["valor"] for p in dados["posicoes"] if p["classe"] == por_aba[aba])
            if abs(soma - total) > 1:
                avisos.append(f"{mes} {aba}: soma lida {soma:.2f} ≠ total da B3 {total:.2f}")
        resumo.append({
            "mes": mes,
            "posicoes": len(dados["posicoes"]),
            "patrimonio": round(sum(p["valor"] for p in dados["posicoes"]), 2),
            "proventos": round(sum(p["valor"] for p in dados["proventos"]), 2),
            "negociacoes": len(dados["negociacoes"]),
        })

    for a, b in zip(meses, meses[1:]):
        if proximo_mes(a) != b:
            avisos.append(f"buraco na sequência: falta mês entre {a} e {b}")
    if meses:
        hoje = date.today()
        ultimo_fechado = f"{hoje.year}-{hoje.month - 1:02d}" if hoje.month > 1 else f"{hoje.year - 1}-12"
        if meses[-1] < ultimo_fechado:
            avisos.append(f"último mês importado é {meses[-1]}; {ultimo_fechado} já fechou e pode ser baixado na B3")
    return resumo, avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=str(Path.home() / "Downloads"))
    ap.add_argument("--substituir", action="store_true", help="sobrescreve um mês já importado com conteúdo diferente")
    ap.add_argument("--simular", action="store_true", help="só mostra o que faria")
    args = ap.parse_args()

    DIR_B3.mkdir(parents=True, exist_ok=True)
    feitos = importar_downloads(Path(args.origem).expanduser(), args.substituir, args.simular)
    resumo, avisos = ([], []) if args.simular else normalizar_todos()
    json.dump({**feitos, "meses": resumo, "avisos": avisos}, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
