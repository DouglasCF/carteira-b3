# Carteira B3

Dashboard pessoal de carteira gerado a partir dos relatórios consolidados mensais da B3. Uso e estrutura: `README.md`. Atualização mensal: skill `atualizar-carteira`. A fonte da skill fica em `.agents/skills/`; `.claude`, `.cursor`, `.codex` e `.agent` apontam para ela via symlink, assim como `CLAUDE.md` aponta para este arquivo.

## Regras

- **Dados financeiros do usuário nunca saem da máquina.** `dados/`, `cache/`, `exemplo/` e `relatorios/` (exceto `dashboard.html`) ficam fora do git. Nunca versione, publique ou cole valores, posições, nomes de ativos da carteira, números de conta ou CPF em issues, commits, serviços externos ou exemplos. Exemplos e testes usam apenas a carteira fictícia de `scripts/exemplo.py`.
- **As planilhas da B3 são a fonte da verdade.** `dados/b3/*.xlsx` nunca são editados. Patrimônio, posições, preços e proventos vêm delas sem ajuste; o importador confere a soma de cada aba contra o "Total" da B3.
- **Não edite `dados/mensal/*.json` nem `relatorios/data.js` à mão.** Corrija o parser (`scripts/b3.py`) ou o cálculo (`scripts/gerar.py`) e regenere.
- **Para testar, use `CARTEIRA_HOME`** apontando para uma pasta temporária (como fazem `scripts/exemplo.py` e `tests/`). Rodar `importar.py` sem isso move arquivos reais de `~/Downloads`.
- **`relatorios/dashboard.html` é estático** e só lê `window.DATA` de `data.js`. Cálculos de período (encadear meses, %CDI, filtros) ficam no JS; cálculos de mês ficam no Python.

## Convenções de cálculo (não óbvias)

- Mês = posição no último dia útil. O anual da B3 vira `AAAA-12`: é a base, sem rentabilidade própria, e os proventos dele são do ano inteiro.
- Rentabilidade mensal: Dietz modificado, `ganho / (inicial + aportes/2)`; sem saldo inicial (classe que nasce no mês), `ganho / aportes`. O período é o encadeamento dos meses.
- Classes econômicas: o `gerar.py` reclassifica pelo que o ativo carrega (`classe_economica`), enquanto o JSON mensal mantém a classe da B3 (`classe_b3`). BDRs e ETFs de S&P/global formam a classe "Exterior (BDRs e ETFs)". ETFs de Ibovespa/dividendos vão para Ações Brasil, ETFs de títulos públicos para Tesouro Direto, e ETFs de cripto para Cripto, que não tem índice próprio, então o resultado dela conta todo como alocação.
- Ações, BDRs, ETFs e FIIs: os aportes vêm da aba Negociações e são reconhecidos quando a quantidade muda na posição (liquidação D+1/D+2: compras do fim do mês entram no mês seguinte).
- CDB, LCA e Tesouro: a B3 não informa aplicações e resgates, que são deduzidos comparando os meses. Um título zerado com quantidade "-" significa que foi pago (vencimento ou FGC).
- Mudança de quantidade sem negociação gera aviso no `gerar.py`. Os casos conhecidos são direitos de subscrição de FII (tickers terminados em 12–15) e frações de bonificação.
- Benchmarks em `scripts/mercado.py`: CDI composto no mês, IPCA mensal e PTAX do último dia útil vêm do BCB SGS; Ibovespa, S&P 500 em R$ e IFIX via XFIX11 vêm do Yahoo (não oficial). Os meses fechados ficam em `cache/`. Se um índice faltar, o dashboard mostra "—".

## Diagnóstico e carteira ideal

- O diagnóstico e o rebalanceamento são calculados no JS (dependem do período, do aporte e do modo). O `gerar.py` só valida e repassa `dados/alvo.json`.
- Atribuição contra o CDI, com peso médio da classe = média mensal de `(inicial + fluxo/2)` da classe sobre o da carteira. Alocação = `peso × (índice − CDI)` e seleção = `peso × (classe − índice)`. O resíduo vem do encadeamento dos meses.
- `dados/alvo.json`: `classes.<classe>.alvo` em % da carteira, e `ativos` em % dentro da classe (o ticker para RV). O dashboard normaliza somas diferentes de 100 e o `gerar.py` avisa. Ativo fora de `ativos` tem alvo 0. Classe sem `ativos` é rebalanceada só no total.
- O `dados/alvo.json` reflete a decisão do usuário. Só altere os percentuais quando o usuário pedir.
- `alvo.regras` traz os limites do usuário, com as chaves em `REGRAS` no `gerar.py`, validados ali. O `checarRegras` do dashboard calcula a venda ou o aporte que traz cada item de volta ao limite, e o modo "só com aportes" não compra o que está acima de um limite. O painel não recomenda ativos nem setores, só aplica a política do usuário.
- O dashboard não grava arquivos. O editor guarda um rascunho no `localStorage`, exporta `alvo.json` para Downloads, e o `scripts/alvo.py --importar` valida e move para `dados/`.
- `scripts/setores.py` é uma lista genérica de tickers da B3. Não acrescente lá só os ativos do usuário, porque isso revelaria a carteira; use `dados/setores.json`. O `gerar.py` avisa sobre ativos sem setor.
- Simulador: `mercado.historico()` gera séries mensais longas (desde 2000) só com índices públicos e vai para `data.js` como `historico`. As fontes são o CDI e o IPCA do SGS, consultados ano a ano; o Ibovespa, o ^SP500TR × PTAX e o BTC-USD × PTAX do Yahoo; e o IFIX oficial da B3, desde 2011. Mapeamento classe → série em `SERIE_SIM` no JS. As métricas e o mix (rebalanceamento mensal) são calculados no JS. Offline, `historico` fica vazio e o simulador mostra um aviso.

## Verificação

```sh
.venv/bin/python -m unittest discover tests                   # pipeline completo, offline, carteira fictícia
.venv/bin/python -W ignore scripts/importar.py --simular       # o que seria importado de ~/Downloads
.venv/bin/python -W ignore scripts/gerar.py                    # tabela mês a mês + avisos
```

Depois de mexer no dashboard, rode `scripts/exemplo.py`, sirva `exemplo/relatorios/` com `python3 -m http.server` e confira o console e os dois temas.

## Git

O e-mail de autor deste repositório está configurado localmente (`git config user.email`). Não altere a configuração global.
