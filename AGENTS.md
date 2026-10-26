# Investimentos

Dashboard pessoal de carteira gerado a partir dos relatórios consolidados mensais da B3. Uso e estrutura: `README.md`. Atualização mensal: skill `atualizar-carteira`. A fonte da skill fica em `.agents/skills/`; `.claude`, `.cursor`, `.codex` e `.agent` apontam para ela via symlink, assim como `CLAUDE.md` aponta para este arquivo.

## Regras

- **Dados financeiros do usuário nunca saem da máquina.** `dados/`, `cache/`, `exemplo/` e `relatorios/` (exceto `dashboard.html`) ficam fora do git. Nunca versione, publique ou cole valores, posições, nomes de ativos da carteira, números de conta ou CPF em issues, commits, serviços externos ou exemplos. Exemplos e testes usam apenas a carteira fictícia de `scripts/exemplo.py`.
- **As planilhas da B3 são a fonte da verdade.** `dados/b3/*.xlsx` nunca são editados. Patrimônio, posições, preços e proventos vêm delas sem ajuste; o importador confere a soma de cada aba contra o "Total" da B3.
- **Não edite `dados/mensal/*.json` nem `relatorios/data.js` à mão.** Corrija o parser (`scripts/b3.py`) ou o cálculo (`scripts/gerar.py`) e regenere.
- **Para testar, use `CARTEIRA_HOME`** apontando para uma pasta temporária (como fazem `scripts/exemplo.py` e `tests/`). Rodar `importar.py` sem isso move arquivos reais de `~/Downloads`.
- **`relatorios/dashboard.html` é estático** e só lê `window.DATA` de `data.js`. Cálculos de período (encadear meses, %CDI, filtros) ficam no JS; cálculos de mês ficam no Python.

## Convenções de cálculo (não óbvias)

- Mês = posição no último dia útil. O anual da B3 vira `AAAA-12`: é a base, sem rentabilidade própria, e os proventos dele são do ano inteiro.
- Rentabilidade mensal: Dietz modificado, `ganho / (inicial + aportes/2)`. O período é o encadeamento dos meses.
- Ações, BDRs, ETFs e FIIs: os aportes vêm da aba Negociações e são reconhecidos quando a quantidade muda na posição (liquidação D+1/D+2: compras do fim do mês entram no mês seguinte).
- CDB, LCA e Tesouro: a B3 não informa aplicações e resgates, que são deduzidos comparando os meses. Um título zerado com quantidade "-" significa que foi pago (vencimento ou FGC).
- Mudança de quantidade sem negociação gera aviso no `gerar.py`. Os casos conhecidos são direitos de subscrição de FII (tickers terminados em 12–15) e frações de bonificação.
- Benchmarks em `scripts/mercado.py`: CDI composto no mês, IPCA mensal e PTAX do último dia útil vêm do BCB SGS; Ibovespa, S&P 500 em R$ e IFIX via XFIX11 vêm do Yahoo (não oficial). Os meses fechados ficam em `cache/`. Se um índice faltar, o dashboard mostra "—".

## Verificação

```sh
.venv/bin/python -m unittest discover tests                   # pipeline completo, offline, carteira fictícia
.venv/bin/python -W ignore scripts/importar.py --simular       # o que seria importado de ~/Downloads
.venv/bin/python -W ignore scripts/gerar.py                    # tabela mês a mês + avisos
```

Depois de mexer no dashboard, rode `scripts/exemplo.py`, sirva `exemplo/relatorios/` com `python3 -m http.server` e confira o console e os dois temas.

## Git

O e-mail de autor deste repositório está configurado localmente (`git config user.email`). Não altere a configuração global.
