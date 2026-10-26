"""Caminhos do projeto.

CARTEIRA_HOME troca a pasta de dados/relatórios (usado pelo exemplo e pelos testes,
para nunca tocar nos dados reais). O cache de mercado é público e fica sempre na raiz.
CARTEIRA_SEM_MERCADO=1 pula Banco Central/Yahoo (testes offline).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("CARTEIRA_HOME", ROOT)).expanduser().resolve()
DIR_B3 = BASE / "dados" / "b3"
DIR_MENSAL = BASE / "dados" / "mensal"
SAIDA = BASE / "relatorios" / "data.js"
CACHE = ROOT / "cache"
SEM_MERCADO = os.environ.get("CARTEIRA_SEM_MERCADO") == "1"
