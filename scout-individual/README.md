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

Enquanto isso, validei a lógica do script contra `_fixture_teste.xlsx`,
uma planilha **sintética** com números inventados (claramente marcados
como teste) mas com os mesmos 4 jogadores e os mesmos tipos de bug que
você já viu no Sofascore (métrica sumindo, "Total do Ano", Renê ausente).

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
        "metricas_faltantes": ["ASR"],        // rótulos esperados (vistos em outras linhas da mesma categoria) que não apareceram aqui
        "completa": false,
        "data_coleta": "2026-08-01"
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

1. **Métrica com valor ausente**: linha com `Metrica` preenchida e `Valor`
   vazio → sinalizada.
2. **Métrica ausente por completo (linha sumiu)**: como o Sofascore às
   vezes perde uma métrica inteira na cópia (ex.: ASR sumiu numa
   exportação), o script constrói, para cada `Categoria`, o conjunto de
   rótulos que aparecem em qualquer linha daquela categoria na planilha
   inteira (o "esperado"). Se um grupo (Jogador+Temporada+Competicao+Categoria)
   não tem um rótulo que aparece em outros grupos da mesma categoria,
   isso é reportado como métrica faltante para aquele jogador/temporada.
3. **Renê ausente da aba**: tratado como esperado (fonte dele é
   FBref/comp ID 24, fora do escopo desta etapa), não como erro. Se ele
   aparecer na aba, também não é erro — só um aviso informativo.
4. **`Competicao == "Total do Ano"`**: marcado como `tipo_linha:
   "total_temporada"` (agregado), nunca listado como se fosse uma
   competição real.

Tudo isso vai pro `relatorio_validacao.txt` (e pro console), pra você
revisar antes de confiarmos no pipeline.

## Rodar

```bash
# com a planilha real, quando você me enviar:
python3 scripts/etapa1_pipeline.py --planilha dados/scout_individual_dados.xlsx

# com a fixture sintética (o que rodei agora, ver saida/):
python3 scripts/gerar_fixture_teste.py
python3 scripts/etapa1_pipeline.py --planilha dados/_fixture_teste.xlsx
```
