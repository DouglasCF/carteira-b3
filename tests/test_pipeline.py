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

import alvo  # noqa: E402
import b3  # noqa: E402
import gerar  # noqa: E402
import setores  # noqa: E402


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
        self.assertAlmostEqual(self.meses["2026-03"]["classes"]["Exterior (BDRs e ETFs)"]["fluxo"], 0, places=2)
        self.assertGreater(self.meses["2026-04"]["classes"]["Exterior (BDRs e ETFs)"]["fluxo"], 0)

    def test_vencimento_e_aplicacao_de_renda_fixa(self):
        tipos = lambda mes: {(x["tipo"], x["ativo"]) for x in self.meses[mes]["movimentos"]}
        self.assertIn(("Vencimento", "CDB Banco Exemplo A S/A"), tipos("2026-03"))
        self.assertIn(("Aplicação", "CDB Banco Exemplo A S/A"), tipos("2026-04"))
        self.assertIn(("Venda", "PETR4"), tipos("2026-05"))

    def test_alvo_vai_para_o_dashboard(self):
        self.assertEqual(self.data["alvo"]["classes"]["FIIs"]["ativos"]["XPML11"], 20)
        self.assertEqual(self.data["alvo_avisos"], [])

    def test_semente_do_alvo_soma_100(self):
        doc = gerar.reclassificar(json.loads((self.home / "dados" / "mensal" / "2026-06.json").read_text()), setores.SETORES)
        classes = alvo.semente(doc)["classes"]
        self.assertNotIn("ETFs", classes)
        self.assertAlmostEqual(sum(c["alvo"] for c in classes.values()), 100, places=6)
        for nome, c in classes.items():
            if "ativos" in c:
                self.assertAlmostEqual(sum(c["ativos"].values()), 100, places=6, msg=nome)
        self.assertNotIn("ativos", classes["Tesouro Direto"])

    def test_setores_dos_ativos_do_exemplo(self):
        self.assertEqual(self.data["setores"]["PETR4"], "Petróleo e gás")
        self.assertEqual(self.data["setores"]["HGLG11"], "FII Logística")
        self.assertEqual(self.data["setores"]["XPML11"], "FII Shoppings")  # só está no alvo

    def test_importar_alvo_exportado_pelo_dashboard(self):
        env = {**os.environ, "CARTEIRA_HOME": str(self.home), "CARTEIRA_SEM_MERCADO": "1"}
        alvo_py = [sys.executable, "-W", "ignore", str(ROOT / "scripts" / "alvo.py"), "--importar"]
        ruim = self.home / "ruim.json"
        ruim.write_text('{"classes": {"FIIs": {"alvo": "dez"}}}')
        self.assertNotEqual(subprocess.run(alvo_py + [str(ruim)], env=env, capture_output=True).returncode, 0)
        original = (self.home / "dados" / "alvo.json").read_text()
        novo = self.home / "alvo.json"
        novo.write_text(json.dumps({"aporte_mensal": 1000, "classes": {"FIIs": {"alvo": 60, "ativos": {"HGLG11": 100}}, "Tesouro Direto": {"alvo": 40}}}))
        try:
            subprocess.run(alvo_py + [str(novo)], env=env, check=True, capture_output=True)
            self.assertFalse(novo.exists())
            self.assertEqual(json.loads((self.home / "dados" / "alvo.json").read_text())["classes"]["FIIs"]["alvo"], 60)
            self.assertEqual((self.home / "dados" / "alvo.anterior.json").read_text(), original)
        finally:
            (self.home / "dados" / "alvo.json").write_text(original)

    def test_etf_vai_para_a_classe_do_que_carrega(self):
        classe = {p["ticker"]: (p["classe"], p["classe_b3"]) for p in self.meses["2026-06"]["posicoes"] if p.get("ticker")}
        self.assertEqual(classe["IVVB11"], ("Exterior (BDRs e ETFs)", "ETFs"))
        self.assertEqual(classe["BOVA11"], ("Ações Brasil", "ETFs"))
        self.assertEqual(classe["AAPL34"][0], "Exterior (BDRs e ETFs)")
        self.assertEqual(gerar.classe_economica({"classe": "ETFs", "ticker": "IMAB11"}, setores.SETORES), "Tesouro Direto")
        self.assertEqual(gerar.classe_economica({"classe": "ETFs", "ticker": "NOVO11", "estrategia": "Cripto"}, {}), "Cripto")

    def test_regras_do_alvo(self):
        self.assertEqual(self.data["alvo"]["regras"]["max_ativo"], 10)
        base = {"classes": {"FIIs": {"alvo": 100}}}
        self.assertEqual(gerar.validar_alvo({**base, "regras": {"max_ativo": 8}}), [])
        for ruim in ({"max_ativo": 0}, {"max_ativo": "8"}, {"maximo": 8}, [8]):
            with self.assertRaises(ValueError, msg=ruim):
                gerar.validar_alvo({**base, "regras": ruim})

    def test_direito_de_subscricao_herda_setor(self):
        self.assertEqual(setores.setor("HGLG12", setores.SETORES), "FII Logística")
        self.assertIsNone(setores.setor("ZZZZ3", setores.SETORES))

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


class Grupamento(unittest.TestCase):
    def mes(self, q, preco, negociacoes=()):
        return {"posicoes": [{"id": "RV:VALE3:XP", "ticker": "VALE3", "nome": "Vale", "classe": "Ações Brasil",
                              "estrategia": "Renda Variável Brasil", "instituicao": "XP", "quantidade": q, "preco": preco, "valor": q * preco}],
                "proventos": [], "negociacoes": list(negociacoes)}

    def test_grupamento_com_preco_oscilando_nao_e_resgate(self):
        # 10:1 com queda de 9% no mês
        total, _, _, avisos, _ = gerar.calcular_mes(self.mes(3000, 2.0), self.mes(300, 18.2), 0.8, {"RV:VALE3": "Ações Brasil"}, {})
        self.assertAlmostEqual(total["fluxo"], 0)
        self.assertIn("grupamento", avisos[0])

    def test_compra_antes_do_desdobramento_entra_no_fator(self):
        # 50 + 20 comprados, desdobramento 20:1 → 1400; só a compra é aporte
        neg = [{"ticker": "VALE3", "instituicao": "XP", "inicio": None, "fim": None, "qtd_compra": 20, "qtd_venda": 0, "pm_compra": 80.0, "pm_venda": 0}]
        total, _, _, avisos, _ = gerar.calcular_mes(self.mes(50, 76.0), self.mes(1400, 3.6, neg), 0.8, {"RV:VALE3": "Ações Brasil"}, {})
        self.assertAlmostEqual(total["fluxo"], 1600)
        self.assertIn("desdobramento", avisos[0])

    def test_transferencia_que_dobra_a_posicao_e_aporte(self):
        total, _, _, _, _ = gerar.calcular_mes(self.mes(100, 10.0), self.mes(300, 10.5), 0.8, {"RV:VALE3": "Ações Brasil"}, {})
        self.assertAlmostEqual(total["fluxo"], 2100)


class LeituraEmprestimo(unittest.TestCase):
    """Ações doadas em empréstimo somem da aba de posição e voltam na de empréstimos."""

    def ler(self, abas):
        import openpyxl
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for nome, linhas in abas.items():
            ws = wb.create_sheet(nome)
            for l in linhas:
                ws.append(l)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.xlsx"
            wb.save(p)
            return b3.ler(p)

    def test_doado_soma_na_posicao(self):
        acoes = [["Produto", "Instituição", "Código de Negociação", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
                 ["WEGE3 - WEG S.A.", "XP INVESTIMENTOS CCTVM S/A", "WEGE3", 10, 40.0, 400.0]]
        emp = [["Produto", "Instituição", "Natureza", "Quantidade", "Preço de Fechamento", "Valor Atualizado"],
               ["WEGE3 - WEG S.A.", "XP INVESTIMENTOS CCTVM S/A", "Doador", 5, 40.0, 200.0],
               ["ITUB4 - ITAU UNIBANCO", "XP INVESTIMENTOS CCTVM S/A", "Doador", 3, 30.0, 90.0],
               ["PETR4 - PETROBRAS", "XP INVESTIMENTOS CCTVM S/A", "Tomador", 7, 25.0, 175.0]]
        pos = {p["ticker"]: p for p in self.ler({"Posição - Ações": acoes, "Posição - Empréstimos": emp})["posicoes"]}
        self.assertEqual((pos["WEGE3"]["quantidade"], pos["WEGE3"]["valor"], pos["WEGE3"]["emprestado"]), (15, 600, 200))
        self.assertEqual((pos["ITUB4"]["quantidade"], pos["ITUB4"]["classe"]), (3, "Ações Brasil"))
        self.assertNotIn("PETR4", pos)

    def test_reembolso_no_formato_de_extrato(self):
        reemb = [["Entrada/Saída", "Data", "Movimentação", "Produto", "Instituição", "Quantidade", "Preço unitário", "Valor da Operação"],
                 ["Credito", "10/03/2026", "Reembolso", "WEGE3 - WEG S.A.", "XP INVESTIMENTOS CCTVM S/A", 0, "-", 12.5]]
        prov = self.ler({"Reembolsos de Empréstimo": reemb})["proventos"]
        self.assertEqual(prov, [{"ticker": "WEGE3", "tipo": "Reembolso", "valor": 12.5, "data": "2026-03-10", "instituicao": "XP"}])


if __name__ == "__main__":
    unittest.main()
