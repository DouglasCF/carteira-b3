# Investimentos

Dashboard pessoal da carteira, gerado a partir dos relatórios consolidados mensais da B3. Fluxo de uso e estrutura: `README.md`. Atualização mensal: skill `/atualizar-carteira`.

## Regras

- **Dados pessoais nunca saem desta máquina.** `dados/`, `cache/` e `relatorios/data.js` ficam fora do git. Não adicione remote, não publique o dashboard nem cole valores ou posições em serviços externos sem o usuário pedir.
- **Planilhas da B3 são a fonte da verdade.** `dados/b3/*.xlsx` nunca são editados. Patrimônio, posições, preços e proventos vêm delas sem ajuste; o importador confere a soma de cada aba contra o "Total" da B3.
- **Não edite `dados/mensal/*.json` nem `relatorios/data.js` à mão.** Corrija o parser (`scripts/b3.py`) ou o cálculo (`scripts/gerar.py`) e regenere.
- **`relatorios/dashboard.html` é estático**: só lê `window.DATA` de `data.js`. Os cálculos de período (encadear meses, %CDI, filtros) ficam no JS; os cálculos de mês ficam no Python.

## Convenções de cálculo (não óbvias)

- Mês = posição no último dia útil. O anual da B3 vira `AAAA-12` (base, sem rentabilidade própria; os proventos dele são do ano inteiro).
- Rentabilidade mensal: Dietz modificado, `ganho / (inicial + aportes/2)`; período = meses encadeados.
- Ações, BDRs, ETFs e FIIs: aportes vêm da aba Negociações, reconhecidos quando a quantidade muda na posição (liquidação D+1/D+2; compras do fim do mês entram no mês seguinte).
- CDB, LCA e Tesouro: a B3 não informa aplicações e resgates. Eles são deduzidos comparando os meses; um título zerado com quantidade "-" significa pago (vencimento/FGC).
- Mudança de quantidade sem negociação gera aviso no `gerar.py`. Os casos conhecidos são direitos de subscrição de FII (tickers terminados em 12–15) e frações de bonificação.
- Benchmarks em `scripts/mercado.py`: CDI composto no mês, IPCA mensal, PTAX do último dia útil (BCB SGS); Ibovespa, S&P 500 em R$ e IFIX via XFIX11 (Yahoo). Os meses fechados ficam em `cache/`.

## Verificação

```sh
.venv/bin/python -W ignore scripts/importar.py --simular   # o que seria importado de ~/Downloads
.venv/bin/python -W ignore scripts/gerar.py                # tabela mês a mês + avisos
```

Depois de mexer no dashboard, abra-o servido localmente (`python3 -m http.server` em `relatorios/`) e confira o console e os dois temas.

## Git

Commits só de código. O usuário pediu histórico local, sem remote.
