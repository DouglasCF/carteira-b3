"""Leitura dos relatórios consolidados (.xlsx) da B3 Área do Investidor."""
import re
from datetime import datetime

import openpyxl

INSTITUICOES = {
    "NU INVEST CORRETORA DE VALORES S.A.": "Nu Invest",
    "NU INVESTIMENTOS S.A. - CTVM": "Nu Invest",
    "XP INVESTIMENTOS CCTVM S/A": "XP",
}

# abas de posição obrigatórias; as demais (Negociações, Proventos...) são opcionais
ABAS_POSICAO = ["Posição - Ações", "Posição - BDR", "Posição - ETF", "Posição - Fundos", "Posição - Renda Fixa", "Posição - Tesouro Direto"]

COLUNAS = {
    "Posição - Ações": ["Código de Negociação", "Instituição", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
    "Posição - BDR": ["Código de Negociação", "Instituição", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
    "Posição - ETF": ["Código de Negociação", "Instituição", "Tipo", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
    "Posição - Fundos": ["Código de Negociação", "Instituição", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
    "Posição - Renda Fixa": ["Código", "Emissor", "Indexador", "Vencimento", "Quantidade", "Valor Atualizado CURVA", "Valor Atualizado MTM"],
    "Posição - Tesouro Direto": ["Produto", "Indexador", "Vencimento", "Quantidade", "Valor Aplicado", "Valor Atualizado"],
    "Proventos Recebidos": ["Produto", "Tipo de Evento", "Valor líquido"],
    "Negociações": ["Código de Negociação", "Instituição", "Quantidade (Compra)", "Quantidade (Venda)", "Preço Médio (Compra)", "Preço Médio (Venda)"],
}

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def mes_do_arquivo(nome):
    """'relatorio-consolidado-mensal-2026-janeiro.xlsx' -> '2026-01'; anual-2025 -> '2025-12' (posição em 31/12)."""
    m = re.search(r"mensal-(\d{4})-([a-zç]+)", nome)
    if m and m.group(2) in MESES:
        return f"{m.group(1)}-{MESES[m.group(2)]:02d}"
    m = re.search(r"anual-(\d{4})", nome)
    if m:
        return f"{m.group(1)}-12"
    return None


def ticker_base(t):
    """Mercado fracionário (EGIE3F) e lote padrão são o mesmo ativo."""
    m = re.fullmatch(r"([A-Z0-9]{4}\d{1,2})F", t or "")
    return m.group(1) if m else t


def _header(ws):
    return [h.strip() if isinstance(h, str) else h for h in next(ws.iter_rows(max_row=1, values_only=True))]


def _rows(ws):
    """Linhas como dicts, parando no primeiro produto vazio (antes do 'Total')."""
    it = ws.iter_rows(values_only=True)
    header = [h.strip() if isinstance(h, str) else h for h in next(it)]
    for row in it:
        if not row[0] or not str(row[0]).strip():
            break
        yield dict(zip(header, row))


def _total_declarado(ws):
    """Último número da aba (linha 'Total' que a B3 coloca no fim)."""
    nums = [v for r in ws.iter_rows(values_only=True) for v in r if isinstance(v, (int, float))]
    return nums[-1] if nums else None


def _num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def _inst(nome):
    return INSTITUICOES.get(nome, (nome or "").title())


def _date(s):
    return datetime.strptime(s, "%d/%m/%Y").date().isoformat() if s and s != "-" else None


def validar(path):
    """Lista de problemas estruturais (vazia = ok)."""
    erros = []
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as e:
        return [f"não abriu como xlsx: {e}"]
    abas = {ws.title: ws for ws in wb}
    if not any(a in abas for a in ABAS_POSICAO):
        erros.append("nenhuma aba de posição encontrada")
    for aba, cols in COLUNAS.items():
        if aba in abas:
            faltando = [c for c in cols if c not in _header(abas[aba])]
            if faltando:
                erros.append(f"{aba}: colunas ausentes {faltando}")
    return erros


def ler(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    abas = {ws.title: ws for ws in wb}
    posicoes, proventos, negociacoes, totais = [], [], [], {}

    listados = {
        "Posição - Ações": ("Ações Brasil", "Renda Variável Brasil"),
        "Posição - BDR": ("BDRs (ações globais)", "Renda Variável Global"),
        "Posição - ETF": ("ETFs", None),
        "Posição - Fundos": ("FIIs", "Fundos Imobiliários"),
    }
    for aba, (classe, estrategia) in listados.items():
        if aba not in abas:
            continue
        totais[aba] = _total_declarado(abas[aba])
        for r in _rows(abas[aba]):
            est = estrategia
            if classe == "ETFs":
                est = {"Internacional": "Renda Variável Global", "Criptoativo": "Cripto"}.get(r.get("Tipo"), "Renda Variável Brasil")
            t = ticker_base(r["Código de Negociação"])
            posicoes.append({
                "id": f"RV:{t}:{_inst(r['Instituição'])}",
                "ticker": t,
                "nome": r["Produto"].split(" - ", 1)[-1].strip(),
                "classe": classe,
                "estrategia": est,
                "instituicao": _inst(r["Instituição"]),
                "quantidade": _num(r["Quantidade"]),
                "preco": _num(r["Preço de Fechamento"]),
                "valor": _num(r["Valor Atualizado"]),
            })

    # ações doadas em empréstimo saem da aba de posição, mas continuam sendo do investidor
    if "Posição - Empréstimos" in abas:
        por_id = {p["id"]: p for p in posicoes}
        for r in _rows(abas["Posição - Empréstimos"]):
            if r.get("Natureza") != "Doador":
                continue
            t = ticker_base(r["Produto"].split(" - ", 1)[0].strip())
            inst = _inst(r["Instituição"])
            p = por_id.get(f"RV:{t}:{inst}")
            if p is None:
                igual = next((x for x in posicoes if x.get("ticker") == t), {})  # mesmo ativo em outra corretora
                p = por_id[f"RV:{t}:{inst}"] = {
                    "id": f"RV:{t}:{inst}", "ticker": t, "nome": r["Produto"].split(" - ", 1)[-1].strip(),
                    "classe": igual.get("classe", "Ações Brasil"), "estrategia": igual.get("estrategia", "Renda Variável Brasil"),
                    "instituicao": inst, "quantidade": 0.0, "preco": _num(r["Preço de Fechamento"]), "valor": 0.0,
                }
                posicoes.append(p)
            p["quantidade"] += _num(r["Quantidade"])
            p["valor"] += _num(r["Valor Atualizado"])
            p["emprestado"] = p.get("emprestado", 0.0) + _num(r["Valor Atualizado"])

    if "Posição - Renda Fixa" in abas:
        totais["Posição - Renda Fixa"] = _total_declarado(abas["Posição - Renda Fixa"])
        for r in _rows(abas["Posição - Renda Fixa"]):
            idx = r["Indexador"]
            tipo = r["Produto"].split(" - ", 1)[0]
            credito = tipo in ("DEB", "CRI", "CRA")
            valor = _num(r["Valor Atualizado CURVA"]) or _num(r["Valor Atualizado MTM"])
            posicoes.append({
                "id": f"RF:{r['Código']}:{_inst(r['Instituição'])}",
                "ticker": r["Código"],
                "nome": f'{tipo} {r["Emissor"].title()}',
                "emissor": r["Emissor"],
                "tipo_rf": tipo,
                "classe": "Crédito privado" if credito else "Renda fixa (CDB/LCA)",
                "estrategia": "Outros / Crédito" if credito else {"DI": "Pós-fixado", "PREFIXADO": "Pré-fixado", "IPCA": "Inflação"}.get(idx, "Outros / Crédito"),
                "indexador": idx,
                "instituicao": _inst(r["Instituição"]),
                "quantidade": _num(r["Quantidade"]),
                "valor": valor,
                "emissao": _date(r.get("Data de Emissão")),
                "vencimento": _date(r["Vencimento"]),
            })

    if "Posição - Tesouro Direto" in abas:
        totais["Posição - Tesouro Direto"] = _total_declarado(abas["Posição - Tesouro Direto"])
        for r in _rows(abas["Posição - Tesouro Direto"]):
            idx = r["Indexador"].upper()
            posicoes.append({
                "id": f"TD:{r['Produto']}:{_inst(r['Instituição'])}",
                "ticker": r.get("Código ISIN"),
                "nome": r["Produto"],
                "classe": "Tesouro Direto",
                "estrategia": {"SELIC": "Pós-fixado", "IPCA": "Inflação", "PREFIXADO": "Pré-fixado"}.get(idx, "Pós-fixado"),
                "indexador": idx,
                "instituicao": _inst(r["Instituição"]),
                "quantidade": _num(r["Quantidade"]),
                "valor": _num(r["Valor Atualizado"]),
                "aplicado": _num(r["Valor Aplicado"]),
                "liquido": _num(r.get("Valor líquido")),
                "vencimento": _date(r["Vencimento"]),
            })

    for aba in ("Proventos Recebidos", "Reembolsos de Empréstimo"):
        if aba in abas:
            for r in _rows(abas[aba]):
                if "Movimentação" in r:  # reembolso no mensal vem como extrato: Entrada/Saída, Data, Movimentação...
                    r = {**r, "Tipo de Evento": r["Movimentação"], "Valor líquido": r["Valor da Operação"], "Pagamento": r["Data"]}
                proventos.append({
                    "ticker": ticker_base(r["Produto"].split(" - ", 1)[0].strip()),
                    "tipo": r["Tipo de Evento"],
                    "valor": _num(r["Valor líquido"]),
                    "data": _date(r.get("Pagamento")),
                    "instituicao": _inst(r.get("Instituição")) if r.get("Instituição") else None,
                })

    if "Negociações" in abas:
        for r in _rows(abas["Negociações"]):
            negociacoes.append({
                "ticker": ticker_base(r["Código de Negociação"]),
                "instituicao": _inst(r["Instituição"]),
                "inicio": _date(r.get("Período (Inicial)")),
                "fim": _date(r.get("Período (Final)")),
                "qtd_compra": _num(r["Quantidade (Compra)"]),
                "qtd_venda": _num(r["Quantidade (Venda)"]),
                "pm_compra": _num(r["Preço Médio (Compra)"]),
                "pm_venda": _num(r["Preço Médio (Venda)"]),
            })

    return {"posicoes": posicoes, "proventos": proventos, "negociacoes": negociacoes, "totais_b3": totais}
