# Scout Individual — Etapa 1 v2 (Performance + Mercado/Empresário + Notícias)

Escopo desta etapa (v2, substitui o escopo original): ler e validar
performance (Sofascore) **e** mercado/empresário (Transfermarkt), e
anexar resultado de busca de notícias recentes (janela de 15 dias). Um
preview em HTML já existe (ver `saida/dossie_preview.html` e o Artifact
publicado) mas **não é a publicação final** — GitHub Pages fica para
depois.

## Arquivos

```
scout-individual/
├── dados/
│   ├── scout_individual_dados.xlsx        ← planilha final combinada (ainda não existe — ver abaixo)
│   ├── sofascore_export.csv               ← export real do Sofascore (4 jogadores)
│   ├── transfermarkt_export_raw.csv       ← export real do Transfermarkt (4 jogadores, CSV sem cabeçalho)
│   ├── noticias_manual.json               ← resultado da busca de notícias
│   ├── prompt-claude-code-etapa1-v2.md    ← prompt que definiu este escopo (referência)
│   └── _fixture_teste.xlsx                ← planilha sintética p/ regressão (gerada por gerar_fixture_teste.py)
├── scripts/
│   ├── etapa1_pipeline.py            ← le performance + mercado, valida, junta por nome, gera JSON
│   ├── gerar_dossie_html.py          ← le saida/*.json e gera o preview em HTML (dossie_preview.html)
│   └── gerar_fixture_teste.py        ← gera a planilha sintética de teste
└── saida/
    ├── <jogador>.json                ← um arquivo consolidado por jogador (performance + mercado + notícias)
    ├── consolidado.json              ← todos os jogadores num único arquivo
    ├── relatorio_validacao.txt       ← inconsistências encontradas nos exports
    └── dossie_preview.html           ← preview visual (mesmo conteúdo do Artifact publicado)
```

## Sobre a planilha real

Este script roda num container remoto isolado (sessão do Claude Code na
nuvem), **não na sua máquina local** — então `~/scout-individual/dados/scout_individual_dados.xlsx`
não existe aqui automaticamente. Pra rodar com dados reais, me envie o
arquivo (anexe na conversa) ou cole o conteúdo das abas, que eu coloco em
`dados/scout_individual_dados.xlsx` e re-rodo.

**Atualização (v2)**: agora tenho export real do Sofascore **e** do
Transfermarkt pros 4 jogadores, incluindo o Renê (que ganhou cobertura
Sofascore própria — o plano original de usar FBref pra ele ficou
obsoleto). `dados/sofascore_export.csv` (296 linhas, zero inconsistência
de contagem de métrica nesta exportação) e
`dados/transfermarkt_export_raw.csv` (4 linhas, uma por jogador).

Ainda falta a aba `Jogadores` com `ID_Sofascore`/`ID_Transfermarkt` reais
— então a junção entre as duas fontes hoje é por **nome**, com um mapa de
apelido manual (`NOME_ALIAS` em `etapa1_pipeline.py`) pro caso já
confirmado de `"Renê Sousa"` (Sofascore) vs. `"Renê"` (Transfermarkt).
Isso é um paliativo documentado, não a junção por ID que o pipeline final
deve usar — quando a aba `Jogadores` chegar, troco por junção real.
Clube atual exibido no dossiê vem do próprio Transfermarkt (`Clube_Atual`
da linha), não normalizado — por isso André Clóvis aparece como
"Académico FC" (nome abreviado do Transfermarkt) e não "Académico de
Viseu"; é a mesma inconsistência entre fontes que o prompt já tinha
avisado, só ainda não reconciliada.

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
  "mercado": {                                 // null se o jogador nao tiver linha no Transfermarkt
    "id_transfermarkt": "564890",
    "clube_atual": "Académico FC",              // string crua do Transfermarkt, pode divergir do Sofascore
    "valor_mercado": {"texto_original": "€2.50 mi. Última alteração: 24/06/2026", "valor_eur": 2500000, "ultima_alteracao": "2026-06-24"},
    "valor_mercado_maximo": {"texto_original": null, "valor_eur": null, "ultima_alteracao": null},
    "data_nascimento": "1997-11-21", "idade": 28,
    "naturalidade": "São Paulo (SP)", "nacionalidade": "Brasil", "altura_m": 1.86,
    "posicao": "Atacante - Centroavante", "pe_preferido": "direito",
    "contrato_inicio": "2023-07-01", "contrato_fim": "2028-06-30",
    "empresario": "Jose Renato Martinez", "data_coleta": "2026-09-15"
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
4. **Jogador da shortlist ausente do export**: gera `[ALERTA]` — antes
   Renê era exceção esperada (fonte FBref), mas ele agora tem export
   Sofascore próprio (como `Renê Sousa`, resolvido por `NOME_ALIAS`), então
   deixou de ser caso especial: se qualquer um dos 4 sumir de um export
   futuro, é alerta como qualquer outro.
5. **`Competicao == "Total do Ano"`**: marcado como `tipo_linha:
   "total_temporada"` (agregado), nunca listado como se fosse uma
   competição real.

**Atualização sobre o ASR**: no export de 14/09, `ASR` faltava em 100%
das linhas `Geral` dos 3 jogadores. No export de 15/09 (o atual), `ASR`
veio presente em **100%** das linhas `Geral` dos 4 jogadores — zero
inconsistência de contagem no arquivo inteiro. Ou seja, **não é um gap
permanente do Sofascore**, foi algo pontual naquela cópia específica.
Mantive `ASR` na lista de gap aceito (`METRICAS_GAP_ACEITO`) por
segurança — se sumir de novo isoladamente, não trava a validação — mas
isso já não é a explicação real, é só uma rede de proteção. O relatório
mostra a contagem de mismatch por arquivo então dá pra conferir a cada
rodada se o padrão voltou.

Qualquer métrica que faltar continua gerando `[ALERTA]` (exceto ASR, que
fica em `metricas_faltantes_aceitas` e não afeta `completa`).

Tudo isso vai pro `relatorio_validacao.txt` (e pro console), pra você
revisar antes de confiarmos no pipeline.

## Validações aplicadas em Transfermarkt

O export real vem como CSV **sem cabeçalho**, com cada linha inteira
entre aspas extras (uma única "célula" contendo vírgulas internas) — o
script desfaz isso antes de parsear (`_corrige_linha_bruta`). 15 campos
posicionais confirmados com dado real: `DataHora, Jogador,
ID_Transfermarkt, Clube_Atual, Valor_Mercado_Maximo_Texto,
Valor_Mercado_Texto, Data_Nascimento_Idade, Naturalidade, Nacionalidade,
Altura, Posicao, Pe, Contrato_Inicio, Contrato_Fim, Empresario`.

- `Valor_Mercado_Texto` vem como `"€2.50 mi. Última alteração:
  24/06/2026"` — o script separa o valor numérico (`valor_eur`), o texto
  original (pra conferência) e a data da última alteração.
- `Valor_Mercado_Maximo_Texto` veio vazio nos 4 jogadores — esperado, sem
  fonte confirmada ainda (dito no prompt), gera só `[INFO]`, não trava.
- `Empresario` ausente gera `[ALERTA]` (não deveria faltar).
- Jogador sem nenhuma linha na aba/CSV gera `[ALERTA]`.
- Duas linhas pro mesmo jogador (após resolver alias) gera `[ALERTA]` —
  fica com a última lida, mas sinaliza a duplicidade.

## Preview em HTML (`gerar_dossie_html.py`)

```bash
python3 scripts/gerar_dossie_html.py
```

Lê só `saida/consolidado.json` (não recalcula nada de validação) e monta
o dossiê visual: snapshot da temporada atual por categoria, Precisão de
finalização e Gols−xG calculados (não vêm prontos do Sofascore), gráfico
de minutos por temporada colorido pela divisão disputada naquele ano
(classificada pelo nome real da competição — nunca por "Total do Ano" —
ver `LEAGUE_TIERS` no script), hachura + opacidade reduzida pra temporada
com menos de 10 jogos (não dá pra tirar conclusão de eficiência sobre
essas), bloco de mercado/empresário, e a notícia. Qualquer métrica sem
valor real vira `N/D` de forma consistente (nunca em branco/implícito).
Isso é só visualização — a fonte da verdade continua sendo o JSON em
`saida/`.

## Rodar

```bash
# CSVs avulsos (o que roda hoje em saida/), + preview HTML:
python3 scripts/etapa1_pipeline.py \
  --performance-csv dados/sofascore_export.csv \
  --transfermarkt-csv dados/transfermarkt_export_raw.csv
python3 scripts/gerar_dossie_html.py --data-geracao "15 set 2026"

# quando a planilha final combinada (Jogadores + todas as abas) existir:
python3 scripts/etapa1_pipeline.py --planilha dados/scout_individual_dados.xlsx

# fixture sintética, só para regressão da lógica de validação:
python3 scripts/gerar_fixture_teste.py
python3 scripts/etapa1_pipeline.py --planilha dados/_fixture_teste.xlsx
```
