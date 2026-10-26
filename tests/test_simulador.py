"""Histórico longo do simulador (scripts/mercado.py), offline: as fontes são trocadas por respostas fixas.

    .venv/bin/python -m unittest discover tests
"""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mercado  # noqa: E402


def b3_ano(ano):
    """Resposta da B3 para um ano: linhas por dia, colunas por mês (rateValueN), texto em formato brasileiro."""
    if ano != 2011:
        return {"results": []}
    return {"results": [
        {"day": 3, "rateValue1": "1.001,00", "rateValue2": "1.020,00"},
        {"day": 31, "rateValue1": "1.010,00", "rateValue2": None},
        {"day": 28, "rateValue1": None, "rateValue2": "1.030,10"},
    ]}


class HistoricoOffline(unittest.TestCase):
    def test_sem_mercado_devolve_vazio(self):
        with mock.patch.object(mercado, "SEM_MERCADO", True):
            self.assertEqual(mercado.historico(), {})

    def test_ifix_usa_o_ultimo_dia_de_cada_mes(self):
        def falso(url, nome, cachear):
            return b3_ano(int(nome.split("-")[2].split(".")[0]))
        with mock.patch.object(mercado, "_get_json", side_effect=falso):
            niveis = mercado._ifix_b3("2011-02")
        self.assertEqual(niveis, {"2010-12": 1000.0, "2011-01": 1010.0, "2011-02": 1030.1})

    def test_sp500_convertido_em_reais(self):
        ptax = [(date(2020, 1, 31), 4.0), (date(2020, 2, 28), 5.0)]
        yahoo = {"%5ESP500TR": {"2020-01": 100.0, "2020-02": 100.0}, "%5EBVSP": {}, "BTC-USD": {}}
        with mock.patch.object(mercado, "SEM_MERCADO", False), \
             mock.patch.object(mercado, "_ultimo_mes_fechado", return_value="2020-02"), \
             mock.patch.object(mercado, "_sgs_anos", side_effect=lambda s, fim: ptax if s == 1 else [(date(2020, 2, 3), 0.1)]), \
             mock.patch.object(mercado, "sgs", return_value=[(date(2020, 2, 1), 0.5)]), \
             mock.patch.object(mercado, "_yahoo_mensal", side_effect=lambda s, fim: yahoo[s]), \
             mock.patch.object(mercado, "_ifix_b3", return_value={}):
            h = mercado.historico()
        self.assertAlmostEqual(h["S&P 500 (R$)"]["2020-02"], 25.0)  # índice parado, dólar +25%
        self.assertEqual(h["IPCA"], {"2020-02": 0.5})
        self.assertNotIn("IFIX", h)  # série que falhou fica de fora; o dashboard trata


if __name__ == "__main__":
    unittest.main()
