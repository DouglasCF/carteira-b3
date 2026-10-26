# Investimentos

Dashboard local da sua carteira a partir dos **relatórios consolidados mensais da B3** (Área do Investidor). Mostra patrimônio, aportes, rentabilidade mês a mês contra CDI/Ibovespa/IPCA/IFIX/S&P 500, composição, proventos e movimentações, com seleção de período.

Tudo roda na sua máquina: as planilhas, os dados normalizados e o dashboard gerado ficam fora do git.

## Requisitos

- Python 3.9+
- Navegador (o dashboard é um HTML estático; Chart.js vem de CDN)

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Experimente sem dados reais

```sh
.venv/bin/python scripts/exemplo.py
open exemplo/relatorios/dashboard.html
```

Gera uma carteira fictícia no layout da B3 em `exemplo/` e roda o pipeline completo nela.

## Uso mensal

1. Na [Área do Investidor da B3](https://www.investidor.b3.com.br), baixe o **relatório consolidado mensal em .xlsx** de cada mês. Opcional: o anual do ano anterior, que serve como posição inicial.
2. Rode a skill `atualizar-carteira` (`/atualizar-carteira` no Claude Code; também funciona no Cursor e no Codex). Para rodar manualmente:

```sh
.venv/bin/python scripts/importar.py      # ~/Downloads -> dados/b3 (move) + dados/mensal (normaliza)
.venv/bin/python scripts/gerar.py         # dados/mensal -> relatorios/data.js
open relatorios/dashboard.html
```

`importar.py --simular` mostra o que seria feito sem mover nada; `--origem <pasta>` lê de outra pasta que não Downloads.

## Como os números são calculados

- **Patrimônio, posições, preços e proventos:** exatamente os da planilha da B3. O importador confere a soma de cada aba contra o "Total" da B3.
- **Rentabilidade mensal:** Dietz modificado, `ganho / (patrimônio inicial + aportes/2)`, com `ganho = final − inicial − aportes + proventos`. Os períodos encadeiam os meses.
- **Aportes em bolsa:** vêm da aba Negociações e são reconhecidos quando a posição liquida (D+1/D+2).
- **Aportes em CDB/LCA/Tesouro:** a B3 não os informa, então são deduzidos comparando os meses (título novo, título que sumiu, mudança de quantidade). A rentabilidade fica próxima da real, mas não é idêntica ao extrato da corretora.
- A menor granularidade é **um mês**, porque a B3 entrega a posição de fim de mês.

## Fontes de mercado

| Dado | Fonte |
|---|---|
| CDI, IPCA, Dólar PTAX | [Banco Central, SGS](https://dadosabertos.bcb.gov.br) (oficial, sem autenticação) |
| Ibovespa, S&P 500, IFIX (via ETF XFIX11) | Yahoo Finance |

> **Aviso:** o endpoint do Yahoo Finance é **não oficial e não documentado**. Pode mudar ou bloquear sem aviso, e o uso está sujeito aos termos do Yahoo. Se falhar, o dashboard continua funcionando, só sem aquele índice. Para uma fonte estável de cotações da B3, considere a [brapi.dev](https://brapi.dev), que exige token gratuito; a troca fica em `scripts/mercado.py`.

Os meses fechados ficam em `cache/`. Apague a pasta para rebaixar.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `scripts/b3.py` | leitura e validação das planilhas da B3 |
| `scripts/importar.py` | move de Downloads e normaliza cada mês |
| `scripts/gerar.py` | aportes, rentabilidade, por classe e por ativo → `data.js` |
| `scripts/mercado.py` | benchmarks |
| `scripts/exemplo.py` | carteira fictícia para demo e testes |
| `scripts/config.py` | caminhos; `CARTEIRA_HOME` troca a pasta de dados |
| `relatorios/dashboard.html` | dashboard estático, lê `relatorios/data.js` |
| `tests/` | testes do pipeline (offline) |
| `.agents/skills/atualizar-carteira/` | skill para agentes (Claude Code, Cursor, Codex via symlinks) |

## Testes

```sh
.venv/bin/python -m unittest discover tests
```

## Privacidade

`dados/`, `cache/`, `exemplo/`, tudo em `relatorios/` exceto o `dashboard.html`, e qualquer `.xlsx`, `.pdf`, `.csv` ou `.json` estão no `.gitignore`. Não versione nem publique esses arquivos: contêm suas posições e valores.

## Licença

[MIT](LICENSE). Não é recomendação de investimento.
