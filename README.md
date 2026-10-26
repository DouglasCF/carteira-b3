# Investimentos

Dashboard local da carteira a partir dos relatórios consolidados mensais da B3 (Área do Investidor). Os dados ficam só nesta máquina.

## Uso mensal

1. Na B3 Área do Investidor, baixe o **relatório consolidado mensal em .xlsx** (fica em `~/Downloads`).
2. No Claude Code, dentro desta pasta: `/atualizar-carteira`.

Manual:
```sh
.venv/bin/python scripts/importar.py      # Downloads -> dados/b3 + dados/mensal
.venv/bin/python scripts/gerar.py         # dados/mensal -> relatorios/data.js
open relatorios/dashboard.html
```

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `scripts/b3.py` | leitura e validação das planilhas da B3 |
| `scripts/importar.py` | move e normaliza os meses |
| `scripts/mercado.py` | CDI, IPCA, PTAX (Banco Central); Ibovespa, IFIX, S&P 500 (Yahoo) |
| `scripts/gerar.py` | fluxos, rentabilidade (Dietz modificado), por classe, por ativo |
| `relatorios/dashboard.html` | dashboard estático; lê `data.js` |
| `dados/`, `cache/`, `relatorios/data.js` | dados pessoais, fora do git |

Setup: `python3 -m venv .venv && .venv/bin/pip install openpyxl`
