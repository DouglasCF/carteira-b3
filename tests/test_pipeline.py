"""Pipeline completo sobre a carteira fictícia de scripts/exemplo.py, offline.

    .venv/bin/python -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import b3  # noqa: E402


class PipelineExemplo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.tmp.name)
        subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "scripts" / "exemplo.py"), "--destino", str(cls.home), "--sem-mercado"],
                       check=True, capture_output=True)
        js = (cls.home / "relatorios" / "data.js").read_text()
        cls.data = json.loads(js[js.index("{"):js.rindex("}") + 1])
        cls.meses = {m["mes"]: m for m in cls.data["meses"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_planilhas_saem_de_downloads(self):
        self.assertEqual(list((self.home / "downloads").glob("*.xlsx")), [])
        self.assertEqual(len(list((self.home / "dados" / "b3").glob("*.xlsx"))), 7)

    def test_patrimonio_bate_com_o_total_da_b3(self):
        for mes, m in self.meses.items():
            totais = b3.ler(self.home / "dados" / "b3" / f"{mes}.xlsx")["totais_b3"]
            self.assertAlmostEqual(m["patrimonio"], sum(v for v in totais.values() if v), places=1, msg=mes)

    def test_ganho_fecha_com_patrimonio_e_aportes(self):
        for m in self.data["meses"][1:]:
            r = m["resumo"]
            self.assertAlmostEqual(r["ganho"], r["final"] - r["inicial"] - r["fluxo"] + r["proventos"], places=1, msg=m["mes"])

    def test_compra_no_ultimo_dia_entra_quando_liquida(self):
        # AAPL34 comprada em 31/03 só aparece na posição de abril: sem avisos e aporte reconhecido em abril
        self.assertEqual([a for m in self.data["meses"] for a in m.get("avisos", [])], [])
        self.assertAlmostEqual(self.meses["2026-03"]["classes"]["BDRs (ações globais)"]["fluxo"], 0, places=2)
        self.assertGreater(self.meses["2026-04"]["classes"]["BDRs (ações globais)"]["fluxo"], 0)

    def test_vencimento_e_aplicacao_de_renda_fixa(self):
        tipos = lambda mes: {(x["tipo"], x["ativo"]) for x in self.meses[mes]["movimentos"]}
        self.assertIn(("Vencimento", "CDB Banco Exemplo A S/A"), tipos("2026-03"))
        self.assertIn(("Aplicação", "CDB Banco Exemplo A S/A"), tipos("2026-04"))
        self.assertIn(("Venda", "PETR4"), tipos("2026-05"))

    def test_reimportar_e_idempotente(self):
        env = {**os.environ, "CARTEIRA_HOME": str(self.home), "CARTEIRA_SEM_MERCADO": "1"}
        out = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "scripts" / "importar.py"), "--origem", str(self.home / "downloads")],
                             env=env, check=True, capture_output=True, text=True).stdout
        self.assertEqual(json.loads(out)["importados"], [])


class LeituraNomes(unittest.TestCase):
    def test_mes_do_arquivo(self):
        self.assertEqual(b3.mes_do_arquivo("relatorio-consolidado-mensal-2026-marco.xlsx"), "2026-03")
        self.assertEqual(b3.mes_do_arquivo("relatorio-consolidado-anual-2025.xlsx"), "2025-12")
        self.assertIsNone(b3.mes_do_arquivo("extrato.xlsx"))

    def test_fracionario_vira_lote_padrao(self):
        self.assertEqual(b3.ticker_base("EGIE3F"), "EGIE3")
        self.assertEqual(b3.ticker_base("TAEE11"), "TAEE11")


if __name__ == "__main__":
    unittest.main()
