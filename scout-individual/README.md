# Scout Individual — Etapa 1 (Performance + Notícias)

Escopo desta etapa: ler e validar performance da planilha local, e anexar
resultado de busca de notícias recentes (janela de 15 dias). **Sem HTML,
sem GitHub Pages, sem dados de mercado/empresário** — isso fica para
etapas futuras.

## Arquivos

```
scout-individual/
├── dados/
│   ├── scout_individual_dados.xlsx   ← planilha real (você precisa fornecer, ver abaixo)
│   ├── _fixture_teste.xlsx           ← planilha sintética p/ testar o script (gerada por gerar_fixture_teste.py)
│   └── noticias_manual.json          ← resultado da busca de notícias (ver "Como as notícias entram no pipeline")
├── scripts/
│   ├── etapa1_pipeline.py            ← script principal desta etapa
│   └── gerar_fixture_teste.py        ← gera a planilha sintética de teste
└── saida/
    ├── <jogador>.json                ← um arquivo consolidado por jogador
    ├── consolidado.json              ← todos os jogadores num único arquivo
    └── relatorio_validacao.txt       ← inconsistências encontradas na planilha
```

## Sobre a planilha real

Este script roda num container remoto isolado (sessão do Claude Code na
nuvem), **não na sua máquina local** — então `~/scout-individual/dados/scout_individual_dados.xlsx`
não existe aqui automaticamente. Pra rodar com dados reais, me envie o
arquivo (anexe na conversa) ou cole o conteúdo das abas, que eu coloco em
`dados/scout_individual_dados.xlsx` e re-rodo.

**Atualização**: você já enviou o export real do Sofascore, agora com os
3 jogadores que têm performance automatizável nessa fonte — André Clóvis,
Thiago Ocampo e Thauan Lara (`dados/sofascore_export.csv`, 218 linhas).
Esse arquivo confirmou o formato real — rótulos e valores pipe-delimitados
na mesma linha (`Colunas_Metricas` / `Valores`), não uma linha por métrica
como eu tinha assumido antes de ver o arquivo. O script foi reescrito
para esse formato real e já rodou contra ele (ver `saida/`). Ainda falta
a aba `Jogadores` (clube fica em branco por instrução sua — "desconsidere
o clube nesse momento" — a competição já vem linha a linha no próprio
arquivo) e Renê (fonte dele é FBref, fora do escopo desta etapa).

Ainda tenho também `_fixture_teste.xlsx`, a planilha **sintética** (números
inventados) que usei pra testar a lógica antes do arquivo real chegar —
mantida só como regressão, não reflete dados reais.

## Formato de saída (JSON por jogador)

```jsonc
{
  "jogador": "André Clóvis",
  "clube_atual": "Académico de Viseu",       // lido da aba Jogadores
  "competicao_principal": "Liga Portugal Betclic",
  "gerado_em": "2026-09-14T12:00:00",
  "performance": {
    "fonte_aba": "Performance_Sofascore",
    "encontrado_na_aba": true,
    "temporadas": [
      {
        "temporada": "2025/26",
        "competicao": "Liga Portugal 2",
        "tipo_linha": "competicao",          // ou "total_temporada" (quando Competicao == "Total do Ano")
        "categoria": "Geral",
        "metricas": {"MP": "34", "MIN": "2347", "GLS": "20", "AST": "5"},
        "metricas_faltantes": ["ASR"],         // tudo que faltou nessa linha (rótulo sem valor correspondente)
        "metricas_faltantes_aceitas": ["ASR"], // subconjunto de gap conhecido (não gera alerta nem afeta "completa")
        "completa": true,                      // considera só o que não é gap aceito
        "data_coleta": "2026-09-14T19:04:29.863Z"
      }
    ]
  },
  "noticias": {
    "janela_dias": 15,
    "data_referencia": "2026-09-14",
    "encontrada_na_janela": true,
    "itens": [
      {
        "titulo": "...",
        "fonte": "ESPN",
        "url": "https://...",
        "data_publicacao": "2026-09-07",
        "idade_dias": 7,
        "dentro_da_janela": true,
        "resumo": "..."
      }
    ]
  }
}
```

Quando não há notícia dentro da janela, `noticias.encontrada_na_janela = false`
e `itens` fica vazio (ou traz o item mais próximo fora da janela,
explicitamente com `dentro_da_janela: false` e a `idade_dias` real — nunca
disfarçado de notícia fresca).

## Como as notícias entram no pipeline

Não existe uma API de busca configurada nesta sessão (não tenho uma
chave de NewsAPI/SerpAPI/etc.), então a busca de notícia não é uma etapa
100% automatizada dentro do `.py` — é feita por mim (Claude, via
ferramenta de busca web) a cada rodada, e o resultado entra no pipeline
como `dados/noticias_manual.json`, num formato documentado (lista de
itens com título, fonte, url, data de publicação — sempre obrigatória —
e resumo). O script apenas lê esse JSON, calcula a idade de cada item em
dias a partir da data de referência e decide o que cai dentro/fora da
janela de 15 dias. Se no futuro você quiser 100% automação sem mim no
loop, dá pra plugar uma API de notícias real nesse ponto — mas isso é
decisão para depois, não implementei nada disso agora.

`dados/noticias_manual.json` desta rodada já contém o resultado real da
busca que fiz agora (14/09/2026) para os 4 jogadores da shortlist —
não é dado de exemplo.

## Validações aplicadas em Performance_Sofascore

O formato real é `Colunas_Metricas` (`"MP | MIN | GLS | AST | ASR"`) +
`Valores` (`"25 | 1788 | 4 | 3"`) na mesma linha — cada linha já é um
bloco completo de métricas para um Jogador+Ano_Temporada+Competicao+Categoria.

1. **Métrica sem valor correspondente**: quando `Valores` tem menos itens
   que `Colunas_Metricas`, os rótulos sobrando (mapeados na ordem, um a
   um) não são descartados — entram em `metricas_faltantes` no JSON e
   viram `[ALERTA]` no relatório.
2. **`Valores` com item a mais**: o inverso (mais valores que rótulos) —
   caso não esperado, mas sinalizado em vez de ignorado.
3. **Um `"-"` como valor não é bug**: quando a contagem bate mas o valor é
   `"-"` (ex.: `CA%` quando `ACR` é 0), isso é uma proporção indefinida do
   próprio Sofascore, mantido como está — só falta *rótulo sem qualquer
   valor* (contagem menor) é que conta como métrica ausente.
4. **Renê ausente da aba**: tratado como esperado (fonte dele é
   FBref/comp ID 24, fora do escopo desta etapa), não como erro. Se ele
   aparecer na aba, também não é erro — só um aviso informativo.
5. **`Competicao == "Total do Ano"`**: marcado como `tipo_linha:
   "total_temporada"` (agregado), nunca listado como se fosse uma
   competição real.

**Achado real no export**: a métrica `ASR` falta sistematicamente na
categoria `Geral` — confirmado nos 3 jogadores (André Clóvis, Thiago
Ocampo, Thauan Lara), em todas as temporadas/competições, e em 0 linhas
de qualquer outra categoria. Você confirmou que é um gap conhecido do
processo de cópia do Sofascore, então **não gera mais alerta** — mas o
dado continua honesto no JSON: `metricas_faltantes` mostra tudo que
faltou, e `metricas_faltantes_aceitas` isola o que é gap conhecido (hoje,
só ASR) e não conta para `completa`. Se `ASR` aparecer como `"-"` (em vez
de simplesmente faltar), isso significa que a contagem bateu e o próprio
Sofascore não tinha o dado (ex.: Thauan Lara / 25-26 / U23 Liga Next Gen)
— tratado como valor válido, não como métrica ausente.

Qualquer outra métrica que vier a faltar (fora ASR) continua gerando
`[ALERTA]` normalmente — o gap aceito é só para ASR na categoria Geral,
não uma licença geral para ignorar contagem de valores.

Tudo isso vai pro `relatorio_validacao.txt` (e pro console), pra você
revisar antes de confiarmos no pipeline.

## Rodar

```bash
# CSV avulso do Sofascore (o que você enviou e o que roda hoje em saida/):
python3 scripts/etapa1_pipeline.py --performance-csv dados/sofascore_export.csv

# quando a planilha final combinada (Jogadores + todas as abas) existir:
python3 scripts/etapa1_pipeline.py --planilha dados/scout_individual_dados.xlsx

# fixture sintética, só para regressão da lógica de validação:
python3 scripts/gerar_fixture_teste.py
python3 scripts/etapa1_pipeline.py --planilha dados/_fixture_teste.xlsx
```
