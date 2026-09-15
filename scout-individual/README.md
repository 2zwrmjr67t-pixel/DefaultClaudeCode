# Scout Individual — v1 completa (passos 1 e 2 concluídos)

Projeto pessoal de acompanhamento de 4 jogadores nomeados — André Clóvis,
Thiago Ocampo, Thauan Lara, Renê. Escopo definido em
`dados/prompt-claude-code-v1-final.md` (substitui os prompts anteriores):
dado completo (performance, performance por jogo + radar, mercado,
lesão, rumor, notícia) → JSON por jogador → página HTML (resumo +
completo, mobile-first) → GitHub Pages.

**Status**: passo 1 (ler + validar) e passo 2 (montar o JSON combinado)
concluídos e aprovados. Passo 3 (HTML) e passo 4 (publicar) ainda não
foram feitos.

## Arquivos

```
scout-individual/
├── dados/
│   ├── scout_individual_dados.xlsx          ← planilha final combinada com aba Jogadores/IDs (ainda não existe)
│   ├── sofascore_export.csv                 ← Performance_Sofascore real (296 linhas, histórico multi-temporada)
│   ├── sofascore_season.csv                 ← Performance_Season real (dado "por jogo" da temporada atual + radar)
│   ├── transfermarkt_export_raw.csv         ← Transfermarkt real (mercado/empresário, CSV sem cabeçalho)
│   ├── lesoes_transfermarkt.csv             ← Lesões reais (todos "sem lesão" nesta rodada)
│   ├── rumores_transfermarkt.csv            ← Rumores reais (só André Clóvis e Renê têm registro)
│   ├── noticias_manual.json                 ← notícia recente pesquisada na web (ver seção própria)
│   ├── prompt-claude-code-v1-final.md       ← prompt vigente (referência)
│   ├── prompt-claude-code-etapa1-v2.md      ← prompt anterior, mantido só de histórico
│   └── _fixture_teste.xlsx                  ← planilha sintética p/ regressão (gerada por gerar_fixture_teste.py)
├── scripts/
│   ├── etapa1_pipeline.py            ← lê todas as fontes, valida, junta, gera o JSON por jogador
│   ├── gerar_dossie_html.py          ← preview HTML anterior (schema v2 — desatualizado, será refeito no passo 3)
│   └── gerar_fixture_teste.py        ← gera a planilha sintética de teste
└── saida/
    ├── <jogador>.json                ← JSON combinado por jogador (schema completo, ver abaixo)
    ├── consolidado.json              ← todos os jogadores num único arquivo
    └── relatorio_validacao.txt       ← inconsistências encontradas nos exports
```

## Sobre a planilha real

Este script roda num container remoto isolado (sessão do Claude Code na
nuvem), não na sua máquina local — `scout_individual_dados.xlsx` ainda
não existe aqui. Enquanto isso, uso os CSVs avulsos reais que você
anexou (não é dado de exemplo). Quando a planilha combinada com aba
`Jogadores` (IDs reais) chegar, o pipeline já lê por `--planilha` — é só
trocar os `--*-csv` pela aba correspondente.

## Junção entre fontes: por ID onde já dá, por nome onde ainda não dá

O prompt pede junção sempre por ID, nunca por texto de nome. Hoje isso é
parcialmente verdade:

- **Transfermarkt ↔ Lesões ↔ Rumores**: as três compartilham
  `ID_Transfermarkt` — junção real por ID (`id_to_nome` em
  `etapa1_pipeline.py`), confirmada com os 4/4 jogadores casando sem
  ambiguidade.
- **Sofascore (Performance e Performance_Season) ↔ resto**: os exports
  do Sofascore não trazem nenhum ID nas colunas — só `Jogador` como
  texto. Junção aqui é por nome canônico + `NOME_ALIAS`, que já resolve
  o caso confirmado `"Renê Sousa"` (Sofascore) → `"Renê"`
  (Transfermarkt/shortlist). Isso é um paliativo documentado — quando a
  aba `Jogadores` com `ID_Sofascore` existir, troco por junção real.

`Clube_Atual` exibido vem cru do Transfermarkt, sem normalizar — por
isso André Clóvis aparece como `"Académico FC"`, não `"Académico de
Viseu"`. É a mesma divergência de nome entre fontes que o prompt avisou,
ainda não reconciliada (só reconcilio de verdade com a aba `Jogadores`).

## Validações aplicadas (as 4 do prompt + as específicas de cada fonte)

1. **`Performance_Season`: categoria `"Partidas"` é sempre descartada.**
   Confirmado com dado real — é despejo bruto corrompido da página
   (concatena seções inteiras num só `Colunas_Metricas`/`Valores`
   gigante), não uma categoria válida. 4/4 jogadores tinham exatamente 1
   linha assim (31 linhas no arquivo, 27 válidas) — descarte sinalizado
   como `[INFO]`, nunca como erro.
2. **Contagem de métricas** (`Performance_Sofascore` e `Performance_Season`):
   quando `Valores` tem menos itens que `Colunas_Metricas`, os rótulos
   sobrando entram em `metricas_faltantes` — não descartados
   silenciosamente. Nesta rodada: zero mismatch nos dois arquivos.
3. **Junção por ID** (ver seção acima) — onde ainda é por nome, isso
   fica documentado, não escondido atrás de um "funciona sempre".
4. **Categoria ausente por jogador é normal, não erro.** Ex.: Thiago
   Ocampo não tem `"Desempenho de corrida"` no `Performance_Season`
   (confirmado — provável limitação de rastreamento físico na Primera
   Nacional); Thauan Lara tem só 1 métrica nessa categoria (velocidade
   máxima) em vez de 3. Nenhum dos dois vira alerta.

Validações específicas:
- **Lesões**: junção por ID; jogador sem linha vira `[ALERTA]` (não é o
  caso hoje — 4/4 casaram). `"Nenhuma lesão registrada"` é estado válido,
  não vazio.
- **Rumores**: jogador sem nenhum registro vira `[INFO]` explícito (não
  erro) — é o caso real de Thauan Lara e Thiago Ocampo.
- **Arquétipo**: vem de `ARQUETIPOS` no script (tabela do prompt, ainda
  não de uma coluna `Jogadores.Arquetipo` real). Jogador sem arquétipo
  definido vira `[ALERTA]`. Renê entra com `fonte: "[Inferência]..."`
  explícito no próprio dado — a etiqueta oficial do Transfermarkt é
  "Ponta/Extremo", mas o volume de gols dele sugere centroavante; a
  página (passo 3) precisa mostrar essa incerteza, não escondê-la atrás
  de uma escolha silenciosa.

Tudo isso vai pro `relatorio_validacao.txt` (e pro console). Rodada
atual: **zero `[ERRO]`, zero `[ALERTA]` real** — só `[INFO]`.

## Formato de saída (JSON por jogador)

```jsonc
{
  "jogador": "André Clóvis",
  "clube_atual": null,                    // aba Jogadores ainda nao existe; null ate ela chegar
  "competicao_principal": null,
  "arquetipo": {"valor": "Centroavante", "fonte": "[Verificado] tabela do prompt"},
  "referencias": {},
  "gerado_em": "2026-09-15T...",
  "performance": {                        // Performance_Sofascore -- historico multi-temporada
    "fonte_aba": "Performance_Sofascore",
    "encontrado_na_aba": true,
    "temporadas": [ /* ver formato de saída detalhado no historico deste README */ ]
  },
  "performance_season": {                 // Performance_Season -- so a temporada atual, "por jogo"
    "fonte_aba": "Performance_Season",
    "encontrado_na_aba": true,
    "categorias": [
      {
        "temporada": "26/27", "competicao": "Liga Portugal Betclic",
        "categoria": "Resumo da Temporada",
        "metricas": {"JOGOS": "6", "MINUTOS POR JOGO": "76", "GOLS": "2", "GOLS ESPERADOS (XG)": "1.78", "ASSISTÊNCIAS": "0"},
        "metricas_faltantes": [], "completa": true, "data_coleta": "2026-09-15T14:05:26.884Z"
      }
      // ... Atacando, Passe, Defendendo, Outros (por partida), Cartões, [Desempenho de corrida se existir]
    ]
  },
  "radar": {                               // null se o jogador nao tiver linha na Performance_Season
    "fonte": "[Verificado] índice proprietário Sofascore (ATT/TEC/TAC/DEF/CRE) -- NAO é contagem direta de evento, não misturar com métrica de contagem.",
    "temporadas": [{"temporada": "26/27", "ATT": "66", "TEC": "50", "TAC": "51", "DEF": "38", "CRE": "38"}]
  },
  "mercado": { /* ... como antes: valor de mercado, contrato, empresário ... */ },
  "lesoes": [
    {"temporada": null, "lesao": "Nenhuma lesão registrada", "de": null, "ate": null, "dias": 0, "jogos_perdidos": 0, "data_extracao": "2026-09-15"}
  ],
  "rumores": {
    "itens": [
      {"clube_interessado": "Raja Club Athletic", "data_mencao": "2026-07-30", "data_atualizacao": "2026-07-30", "data_coleta": "2026-09-15"}
    ],
    "tem_rumor": true,                     // false + itens:[] é estado real, não erro (ex.: Thauan Lara, Thiago Ocampo)
    "fonte": "[Especulação] Transfermarkt -- clube interessado noticiado, não negociação confirmada."
  },
  "noticias": {
    "janela_dias": 15, "data_referencia": "2026-09-15", "encontrada_na_janela": true,
    "itens": [{"titulo": "...", "fonte": "...", "url": "...", "data_publicacao": "2026-09-07", "idade_dias": 8, "dentro_da_janela": true, "resumo": "..."}]
  }
}
```

## Como as notícias entram no pipeline

Sem API de busca configurada nesta sessão — a pesquisa é feita por mim
(Claude, via ferramenta de busca web) a cada rodada, resultado entra como
`dados/noticias_manual.json`. Query monta clube + termo de evento (ex.:
`"Renê" "Vitória" gols`), candidatos ordenados por data de publicação
real (não por relevância do buscador). Sem nada na janela de 15 dias =
estado explícito de "sem notícia recente", nunca um item antigo
disfarçado de atual.

## Rodar

```bash
python3 scripts/etapa1_pipeline.py \
  --performance-csv dados/sofascore_export.csv \
  --transfermarkt-csv dados/transfermarkt_export_raw.csv \
  --performance-season-csv dados/sofascore_season.csv \
  --lesoes-csv dados/lesoes_transfermarkt.csv \
  --rumores-csv dados/rumores_transfermarkt.csv \
  --data-referencia 2026-09-15

# quando a planilha final combinada (aba Jogadores com IDs) existir:
python3 scripts/etapa1_pipeline.py --planilha dados/scout_individual_dados.xlsx

# fixture sintética, só para regressão da lógica de validação:
python3 scripts/gerar_fixture_teste.py
python3 scripts/etapa1_pipeline.py --planilha dados/_fixture_teste.xlsx
```

`scripts/gerar_dossie_html.py` ainda lê o schema da v2 (sem arquétipo,
radar, lesão, rumor) — vai ser refeito no passo 3 com o layout de
resumo + completo do mockup aprovado.
