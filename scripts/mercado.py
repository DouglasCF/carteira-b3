"""Benchmarks mensais de fontes públicas (sem autenticação), com cache em cache/.

- Banco Central SGS: CDI (12), IPCA (433), Dólar PTAX venda (1)
- Yahoo Finance: Ibovespa, IFIX (via ETF XFIX11), S&P 500

historico() monta as séries longas (desde 2000) usadas pelo simulador de alocação: CDI, IPCA,
Ibovespa, S&P 500 com dividendos em R$, IFIX oficial da B3 (desde 2011) e Bitcoin em R$ (desde 2014).
"""
import base64
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timezone

from config import CACHE, SEM_MERCADO
UA = {"User-Agent": "Mozilla/5.0"}


def _mes_fechado(fim):
    hoje = date.today()
    return fim < f"{hoje.year}-{hoje.month:02d}"


def _get_json(url, nome, cachear):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / nome
    if cachear and f.exists():
        return json.loads(f.read_text())
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as resp:
                data = json.loads(resp.read())
            if cachear:
                f.write_text(json.dumps(data))
            return data
        except Exception as e:  # rede instável / rate limit
            print(f"  ! {nome}: {e}", file=sys.stderr)
            time.sleep(1 + tentativa)
    return None


def _ym(d):
    return f"{d.year}-{d.month:02d}"


def _mes_anterior(m):
    a, n = map(int, m.split("-"))
    return f"{a - 1}-12" if n == 1 else f"{a}-{n - 1:02d}"


def sgs(serie, inicio, fim):
    """[(date, valor)] de inicio-01 até o fim do mês fim (meses 'AAAA-MM')."""
    a, m = map(int, inicio.split("-"))
    b, n = map(int, fim.split("-"))
    ult = (date(b + n // 12, n % 12 + 1, 1) - date.resolution)
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json"
           f"&dataInicial=01/{m:02d}/{a}&dataFinal={ult:%d/%m/%Y}")
    rows = _get_json(url, f"sgs-{serie}-{inicio}-{fim}.json", _mes_fechado(fim)) or []
    return [(datetime.strptime(r["data"], "%d/%m/%Y").date(), float(r["valor"])) for r in rows]


def fechamentos(symbol, inicio, fim):
    """{'AAAA-MM': último fechamento do mês} de inicio a fim."""
    a, m = map(int, inicio.split("-"))
    b, n = map(int, fim.split("-"))
    p1 = int(datetime(a, m, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(b + n // 12, n % 12 + 1, 2, tzinfo=timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
    data = _get_json(url, f"yahoo-{symbol}-{inicio}-{fim}.json", _mes_fechado(fim))
    try:
        res = data["chart"]["result"][0]
        pares = zip(res["timestamp"], res["indicators"]["quote"][0]["close"])
    except (TypeError, KeyError, IndexError):
        return {}
    out = {}
    for t, c in pares:
        if c is not None:
            k = _ym(datetime.fromtimestamp(t, tz=timezone.utc).date())
            if inicio <= k <= fim:
                out[k] = c  # timestamps em ordem: fica o último do mês
    return out


def benchmarks(meses):
    """{'CDI': {'AAAA-MM': retorno_mensal_%}, ...} para cada mês da lista."""
    if not meses or SEM_MERCADO:
        return {}
    ini, fim = meses[0], meses[-1]
    base = _mes_anterior(ini)  # nível do mês anterior para calcular a variação do primeiro

    cdi = {}
    for d, v in sgs(12, ini, fim):
        cdi[_ym(d)] = cdi.get(_ym(d), 1.0) * (1 + v / 100)
    ipca = {_ym(d): 1 + v / 100 for d, v in sgs(433, ini, fim)}

    ptax = {}
    for d, v in sgs(1, base, fim):
        ptax[_ym(d)] = v

    def var(niveis):
        return {m: niveis[m] / niveis[_mes_anterior(m)] for m in meses if m in niveis and _mes_anterior(m) in niveis}

    spx = fechamentos("%5EGSPC", base, fim)
    spx_brl = {m: spx[m] * ptax[m] for m in spx if m in ptax}

    fatores = {
        "CDI": cdi,
        "IPCA": ipca,
        "Ibovespa": var(fechamentos("%5EBVSP", base, fim)),
        "IFIX": var(fechamentos("XFIX11.SA", base, fim)),  # o índice não tem histórico diário no Yahoo; XFIX11 é o ETF do IFIX
        "S&P 500 (R$)": var(spx_brl),
        "Dólar": var(ptax),
    }
    return {k: {m: round((f[m] - 1) * 100, 4) for m in meses if m in f} for k, f in fatores.items()}


# ---------------------------------------------------------------- histórico longo (simulador)
INICIO_HIST = 2000


def _ultimo_mes_fechado():
    hoje = date.today()
    return _mes_anterior(f"{hoje.year}-{hoje.month:02d}")


def _sgs_anos(serie, fim):
    """SGS ano a ano: séries diárias só aceitam até 10 anos por consulta."""
    out = []
    for ano in range(INICIO_HIST, int(fim[:4]) + 1):
        out += sgs(serie, f"{ano}-01", min(f"{ano}-12", fim))
    return out


def _yahoo_mensal(symbol, fim):
    """{'AAAA-MM': fechamento do mês} com barras mensais, de 2000 até fim."""
    p1 = int(datetime(INICIO_HIST, 1, 1, tzinfo=timezone.utc).timestamp())
    a, n = map(int, fim.split("-"))
    p2 = int(datetime(a + n // 12, n % 12 + 1, 1, tzinfo=timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1mo"
    data = _get_json(url, f"yahoo-mensal-{symbol}-{fim}.json", True)
    try:
        res = data["chart"]["result"][0]
        pares = zip(res["timestamp"], res["indicators"]["quote"][0]["close"])
    except (TypeError, KeyError, IndexError):
        return {}
    return {k: c for t, c in pares if c is not None and (k := _ym(datetime.fromtimestamp(t, tz=timezone.utc).date())) <= fim}


def _ifix_b3(fim):
    """IFIX oficial (B3, estatísticas históricas): fechamento do último dia de cada mês, desde a base de 2010."""
    niveis = {"2010-12": 1000.0}  # base do índice: 1.000 pontos em 30/12/2010
    for ano in range(2011, int(fim[:4]) + 1):
        q = base64.b64encode(json.dumps({"language": "pt-br", "index": "IFIX", "year": str(ano)}).encode()).decode()
        url = f"https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{q}"
        dias = (_get_json(url, f"b3-ifix-{ano}.json", f"{ano}-12" <= fim) or {}).get("results") or []
        for m in range(1, 13):
            vals = [d.get(f"rateValue{m}") for d in sorted(dias, key=lambda d: d["day"])]
            vals = [v for v in vals if v]
            if vals and f"{ano}-{m:02d}" <= fim:
                niveis[f"{ano}-{m:02d}"] = float(vals[-1].replace(".", "").replace(",", "."))
    return niveis if len(niveis) > 1 else {}


def historico():
    """{'Índice': {'AAAA-MM': retorno_mensal_%}} desde 2000 (ou o início de cada série), meses fechados."""
    if SEM_MERCADO:
        return {}
    try:
        fim = _ultimo_mes_fechado()
        cdi, ptax = {}, {}
        for d, v in _sgs_anos(12, fim):
            cdi[_ym(d)] = cdi.get(_ym(d), 1.0) * (1 + v / 100)
        for d, v in _sgs_anos(1, fim):
            ptax[_ym(d)] = v  # em ordem: fica a PTAX do último dia útil
        ipca = {_ym(d): 1 + v / 100 for d, v in sgs(433, f"{INICIO_HIST}-01", fim)}

        def var(niveis):
            return {m: niveis[m] / niveis[_mes_anterior(m)] for m in niveis if _mes_anterior(m) in niveis}

        def em_reais(niveis):
            return {m: v * ptax[m] for m, v in niveis.items() if m in ptax}

        fatores = {
            "CDI": cdi,
            "IPCA": ipca,
            "Ibovespa": var(_yahoo_mensal("%5EBVSP", fim)),
            "S&P 500 (R$)": var(em_reais(_yahoo_mensal("%5ESP500TR", fim))),  # com dividendos reinvestidos
            "IFIX": var(_ifix_b3(fim)),
            "Bitcoin (R$)": var(em_reais(_yahoo_mensal("BTC-USD", fim))),
        }
        return {k: {m: round((f[m] - 1) * 100, 4) for m in sorted(f)} for k, f in fatores.items() if f}
    except Exception as e:  # o dashboard funciona sem o simulador
        print(f"  ! histórico: {e}", file=sys.stderr)
        return {}
