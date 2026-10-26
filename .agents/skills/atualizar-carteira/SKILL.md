---
name: atualizar-carteira
description: Importa os relatórios consolidados da B3 (.xlsx) baixados em ~/Downloads, valida, move para dados/b3/, recalcula a evolução mensal e atualiza o dashboard. Use quando o usuário disser que baixou relatórios da B3, pedir para atualizar a carteira/dashboard ou rodar /atualizar-carteira.
---

# Atualizar carteira

Pipeline determinístico em Python; o seu papel é rodar, conferir e resumir. Não edite os JSONs nem o `data.js` à mão.

## Passos

1. **Ambiente.** Se `.venv/` não existir: `python3 -m venv .venv && .venv/bin/pip install openpyxl`.
2. **Prévia.** `.venv/bin/python -W ignore scripts/importar.py --simular` mostra o que seria importado de `~/Downloads/relatorio-consolidado-*.xlsx`.
   - `invalidos`: mostre os erros ao usuário e não continue com esses arquivos (layout da B3 mudou ou arquivo errado).
   - `conflitos`: mês já importado com conteúdo diferente (a B3 às vezes reemite). Pergunte antes de rodar com `--substituir`.
   - Nada em `importados` nem em `duplicados`: avise que não há planilhas novas em Downloads e pare.
3. **Importar.** `.venv/bin/python -W ignore scripts/importar.py`. Move cada planilha para `dados/b3/AAAA-MM.xlsx`, apaga de Downloads as cópias idênticas e regrava `dados/mensal/*.json`.
   - Confira `avisos`: soma das posições diferente do total da B3, buraco na sequência de meses e mês fechado que ainda não foi baixado.
4. **Calcular.** `.venv/bin/python -W ignore scripts/gerar.py` grava `relatorios/data.js` e imprime a tabela mês a mês, os destaques do último mês e os avisos.
5. **Revisar os avisos de cálculo.** Cada um é um ativo cuja quantidade mudou sem negociação na B3. Os já conhecidos são direitos de subscrição de FII (tickers terminados em 12–15) e frações de bonificação. Se aparecer algo diferente (desdobramento grande, transferência entre corretoras, incorporação), explique ao usuário como foi tratado e se distorce a rentabilidade do mês.
6. **Abrir.** `open relatorios/dashboard.html`.
7. **Responder** em poucas linhas:
   - o último mês importado: patrimônio, ganho em R$, rentabilidade e %CDI;
   - o acumulado do ano;
   - os maiores ganhos e perdas;
   - os proventos;
   - os pontos de atenção relevantes.

   Se existir `dados/alvo.json`, diga também quais classes estão mais longe do alvo e para onde vai o próximo aporte. Isso está na seção "Carteira ideal e rebalanceamento" do dashboard. Se não existir, mencione que `scripts/alvo.py` cria o alvo.

## Onde ficam os dados

- `dados/b3/AAAA-MM.xlsx`: planilhas originais, nunca editadas. O anual de AAAA vira `AAAA-12.xlsx`, a posição de 31/12.
- `dados/mensal/AAAA-MM.json`: o mês normalizado (posições, proventos, negociações), regenerado a cada importação.
- `relatorios/data.js`: `window.DATA` com a série calculada, lido pelo `relatorios/dashboard.html` (estático).
- `cache/`: respostas do Banco Central e do Yahoo dos meses fechados.

`dados/`, `cache/` e `relatorios/data.js` estão no `.gitignore`: são dados financeiros pessoais e não podem ir para nenhum remote.
