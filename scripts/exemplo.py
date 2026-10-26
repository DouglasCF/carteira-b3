"""Gera uma carteira fictícia no layout das planilhas da B3 e roda o pipeline completo nela.

Uso:
    .venv/bin/python scripts/exemplo.py [--destino exemplo] [--sem-mercado]
    open exemplo/relatorios/dashboard.html

Nada aqui toca em dados/ ou relatorios/data.js: tudo vai para a pasta de destino
(CARTEIRA_HOME). Os números são inventados; os tickers são só nomes conhecidos.
"""
import argparse
import os
import random
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import openpyxl

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
CORRETORA = "CORRETORA EXEMPLO S.A."
MESES_NOME = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

LISTADOS = {
    "Posição - Ações": [("PETR4", "PETROBRAS", 400, 32.0), ("VALE3", "VALE", 150, 60.0), ("ITUB4", "ITAU UNIBANCO", 300, 35.0), ("WEGE3", "WEG", 200, 45.0)],
    "Posição - BDR": [("AAPL34", "APPLE INC.", 300, 70.0), ("MSFT34", "MICROSOFT CORP", 120, 90.0)],
    "Posição - ETF": [("IVVB11", "ISHARES S&P 500", 30, 380.0, "Internacional"), ("BOVA11", "ISHARES IBOVESPA", 60, 130.0, "Ações")],
    "Posição - Fundos": [("HGLG11", "CSHG LOGISTICA FII", 250, 160.0), ("KNRI11", "KINEA RENDA IMOBILIARIA FII", 180, 140.0)],
}
# (código, tipo, emissor, indexador, emissão, vencimento, aplicado, taxa ao mês, mês em que é aplicado)
RENDA_FIXA = [
    ("CDBEXEMPLO1", "CDB", "BANCO EXEMPLO A S/A", "DI", "2024-03-15", "2026-03-16", 20000.0, 0.0105, None),
    ("LCAEXEMPLO2", "LCA", "BANCO EXEMPLO B S/A", "PREFIXADO", "2025-01-10", "2027-01-11", 15000.0, 0.0095, None),
    ("CDBEXEMPLO3", "CDB", "BANCO EXEMPLO A S/A", "DI", "2026-04-10", "2029-04-10", 25000.0, 0.011, "2026-04"),
]
TESOURO = [("Tesouro Selic 2029", "SELIC", "2029-03-01", 2.5, 16000.0, 0.0102), ("Tesouro IPCA+ 2035", "IPCA", "2035-05-15", 12.0, 3500.0, 0.009)]

# negociações: (mês do pregão, data, ticker, qtd compra, qtd venda, mês em que liquida)
NEGOCIACOES = [
    ("2026-02", "2026-02-12", "VALE3", 100, 0, "2026-02"),
    ("2026-03", "2026-03-31", "AAPL34", 50, 0, "2026-04"),  # fim de mês: liquida no mês seguinte
    ("2026-05", "2026-05-20", "PETR4", 0, 150, "2026-05"),
]


def ultimo_dia_util(ano, mes):
    d = date(ano + mes // 12, mes % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def br(d):
    return f"{d[8:10]}/{d[5:7]}/{d[0:4]}"


def escrever_aba(wb, nome, header, linhas, col_total):
    ws = wb.create_sheet(nome)
    ws.append(header)
    for l in linhas:
        ws.append(l)
    if col_total is not None:
        ws.append([""] + [None] * (len(header) - 1))
        ws.append([""] * col_total + ["Total"])
        ws.append([""] * col_total + [round(sum(l[col_total] for l in linhas if isinstance(l[col_total], (int, float))), 2)])


def gerar_planilhas(destino, meses):
    rnd = random.Random(42)
    precos = {t[0]: t[3] for aba in LISTADOS.values() for t in aba}
    qtd = {t[0]: t[2] for aba in LISTADOS.values() for t in aba}
    rf_valor = {c[0]: c[6] for c in RENDA_FIXA}
    td_valor = {t[0]: t[4] * t[3] for t in TESOURO}
    destino.mkdir(parents=True, exist_ok=True)

    for i, mes in enumerate(meses):
        ano, m = map(int, mes.split("-"))
        if i:  # variação de preço do mês e rendimento da renda fixa
            for t in precos:
                precos[t] = round(precos[t] * (1 + rnd.gauss(0.008, 0.05)), 2)
            for c in RENDA_FIXA:
                rf_valor[c[0]] *= 1 + c[7]
            for t in TESOURO:
                td_valor[t[0]] *= 1 + t[5] + rnd.gauss(0, 0.004)
        for neg in NEGOCIACOES:
            if neg[5] == mes:
                qtd[neg[2]] += neg[3] - neg[4]

        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for aba, ativos in LISTADOS.items():
            etf = aba == "Posição - ETF"
            header = ["Produto", "Instituição", "Conta", "Código de Negociação", "Código ISIN / Distribuição"] + (["Tipo"] if etf else []) + ["Quantidade", "Preço de Fechamento", "Valor Atualizado"]
            linhas = []
            for a in ativos:
                t = a[0]
                linhas.append([f"{t} - {a[1]}", CORRETORA, "000000", t, "-"] + ([a[4]] if etf else []) + [qtd[t], precos[t], round(qtd[t] * precos[t], 2)])
            escrever_aba(wb, aba, header, linhas, len(header) - 1)

        header = ["Produto", "Instituição", "Emissor", "Código", "Indexador", "Tipo de regime", "Data de Emissão", "Vencimento", "Quantidade",
                  "Quantidade Disponível", "Quantidade Indisponível", "Motivo", "Contraparte", "Preço Atualizado MTM", "Valor Atualizado MTM",
                  "Preço Atualizado CURVA", "Valor Atualizado CURVA"]
        linhas = []
        for c in RENDA_FIXA:
            if c[8] and mes < c[8]:
                continue
            if c[5][:7] < mes:  # já pago: some da posição
                continue
            pago = c[5][:7] == mes  # mês do vencimento: B3 mantém a linha zerada
            v = 0 if pago else round(rf_valor[c[0]], 2)
            linhas.append([f"{c[1]} - {c[2]}", CORRETORA, c[2], c[0], c[3], "DEPOSITADO", br(c[4]), br(c[5]), "-" if pago else 1,
                           "-", "-", "-", "-", "-", "-", v, v])
        escrever_aba(wb, "Posição - Renda Fixa", header, linhas, 16)

        header = ["Produto", "Instituição", "Código ISIN", "Indexador", "Vencimento", "Quantidade", "Quantidade Disponível",
                  "Quantidade Indisponível", "Motivo", "Valor Aplicado", "Valor bruto", "Valor líquido", "Valor Atualizado"]
        linhas = [[t[0], CORRETORA, "BRSTN0000000", t[1], br(t[2]), t[3], t[3], 0, "-", t[4] * t[3],
                   round(td_valor[t[0]], 2), round(td_valor[t[0]] * 0.98, 2), round(td_valor[t[0]], 2)] for t in TESOURO]
        escrever_aba(wb, "Posição - Tesouro Direto", header, linhas, 12)

        anual = mes.endswith("-12")
        header = ["Produto", "Tipo de Evento", "Valor líquido"] if anual else ["Produto", "Pagamento", "Tipo de Evento", "Instituição", "Quantidade", "Preço unitário", "Valor líquido"]
        linhas = []
        for t, tipo, por_cota in (("HGLG11", "Rendimento", 1.10), ("KNRI11", "Rendimento", 1.00), ("ITUB4", "Dividendo", 0.25)):
            v = round(qtd[t] * por_cota * (12 if anual else 1), 2)
            linhas.append([f"{t} - EXEMPLO", tipo, v] if anual else
                          [f"{t} - EXEMPLO", br(f"{mes}-15"), tipo, CORRETORA, qtd[t], por_cota, v])
        escrever_aba(wb, "Proventos Recebidos", header, linhas, len(header) - 1)

        negs = [n for n in NEGOCIACOES if n[0] == mes]
        if negs:
            header = ["Código de Negociação", "Período (Inicial)", "Período (Final)", "Instituição", "Quantidade (Compra)",
                      "Quantidade (Venda)", "Quantidade (Líquida)", "Preço Médio (Compra)", "Preço Médio (Venda)"]
            linhas = [[n[2], br(n[1]), "-", CORRETORA, n[3], n[4], n[3] - n[4], precos[n[2]] if n[3] else 0, precos[n[2]] if n[4] else 0] for n in negs]
            escrever_aba(wb, "Negociações", header, linhas, None)

        nome = f"relatorio-consolidado-anual-{ano}.xlsx" if anual else f"relatorio-consolidado-mensal-{ano}-{MESES_NOME[m - 1]}.xlsx"
        wb.save(destino / nome)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=str(ROOT / "exemplo"))
    ap.add_argument("--sem-mercado", action="store_true", help="não busca CDI/Ibovespa (offline)")
    args = ap.parse_args()

    home = Path(args.destino).resolve()
    if home == ROOT:
        sys.exit("o destino do exemplo não pode ser a raiz do projeto (dados reais)")
    meses = ["2025-12"] + [f"2026-{m:02d}" for m in range(1, 7)]
    gerar_planilhas(home / "downloads", meses)

    env = {**os.environ, "CARTEIRA_HOME": str(home)}
    if args.sem_mercado:
        env["CARTEIRA_SEM_MERCADO"] = "1"
    py = [sys.executable, "-W", "ignore"]
    subprocess.run(py + [str(SCRIPTS / "importar.py"), "--origem", str(home / "downloads")], env=env, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(py + [str(SCRIPTS / "gerar.py")], env=env, check=True)

    painel = home / "relatorios" / "dashboard.html"
    if painel.is_symlink() or painel.exists():
        painel.unlink()
    painel.symlink_to(ROOT / "relatorios" / "dashboard.html")
    print(f"\nabra: {painel}")


if __name__ == "__main__":
    main()
