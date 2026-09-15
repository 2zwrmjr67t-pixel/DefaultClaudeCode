# Prompt para Claude Code — Projeto "Scout Individual", Etapa 1 (v2)

> Substitui a v1. Incorpora dados reais testados nesta conversa (não mais schema hipotético). Cole como mensagem inicial no Claude Code.

## Escopo desta etapa

Três coisas, nesta ordem:
1. Ler e validar os dados de **performance** (Sofascore) vindos da planilha local.
2. Ler e validar os dados de **mercado/empresário** (Transfermarkt) vindos da mesma planilha.
3. Buscar **notícias recentes** de cada jogador na web.

Nada de HTML, nada de GitHub Pages ainda — isso é etapa futura, só depois que eu validar esta.

## Jogadores da shortlist

| Jogador (nome canônico) | Clube atual | Competição |
|---|---|---|
| André Clóvis | Académico de Viseu | Liga Portugal Betclic (1ª divisão — subiu em 25/26) |
| Thiago Ocampo | Nueva Chicago | Primera Nacional (Argentina, 2ª divisão) |
| Thauan Lara | Portimonense | Liga Portugal 2 |
| Renê | Vitória | Brasileirão Série A |

## Fonte de dado — planilha local

Arquivo Excel em `~/scout-individual/dados/scout_individual_dados.xlsx` (confirmar caminho comigo se for diferente). Leia com `pandas.read_excel(caminho, sheet_name=None)`.

### Aba `Jogadores` — cadastro mestre e chave de junção
Colunas: `Nome, ID_Sofascore, ID_Transfermarkt, ID_FBref, Clube_Atual, Competicao_Atual, Posicao, Data_Nascimento, Pe_Preferido, Nacionalidade, Status`.

**Regra crítica de junção — não é opcional:** o nome do jogador **varia entre fontes**. Já confirmamos isso com dado real: o Sofascore registra "Renê Sousa", o Transfermarkt registra "Renê", e o nome de clube do André Clóvis aparece como "Académico FC" no Transfermarkt (provável abreviação de "Académico de Viseu"). **Nunca junte as abas comparando o texto do campo `Jogador`/`Nome`.** Use sempre `ID_Sofascore` e `ID_Transfermarkt` como chave, resolvendo cada linha das abas de dado contra a aba `Jogadores` primeiro.

### Aba `Performance_Sofascore` — formato longo
Colunas: `Jogador, Temporada, Competicao, Categoria, Metrica, Valor, Data_Coleta`.

Isso já vem estruturado corretamente (testado com exportação real): cada temporada tem uma linha `Competicao = "Total do Ano"` (agregado) e, quando o jogador disputou uma ou mais competições nomeadas naquele ano, uma linha adicional por competição (ex: liga + copa no mesmo ano). Trate `"Total do Ano"` como o agregado, nunca como nome de competição real — não liste isso como se fosse uma liga na página final.

**Validação obrigatória:** cada linha tem uma lista de rótulos (`Metrica`, ex: `MP | MIN | GLS | AST | ASR`) que deveria ter o mesmo número de valores. Já aconteceu de a nota (ASR) vir ausente numa exportação anterior — se o número de valores for menor que o de rótulos, não descarte o excedente silenciosamente. Sinalize a linha como incompleta e reporte quais métricas faltaram, por jogador/temporada.

### Aba `Transfermarkt` — schema real, validado
Colunas: `ID_Transfermarkt, Jogador, Clube_Atual, Valor_Mercado_Texto, Valor_Mercado_Maximo_Texto, Data_Nascimento_Idade, Naturalidade, Nacionalidade, Altura, Posicao, Pe, Contrato_Inicio, Contrato_Fim, Empresario, Data_Coleta`.

Pontos de atenção reais, já identificados:
- `Valor_Mercado_Texto` vem como string formatada (ex: `"€400 mil"`, `"€2.50 mi."`), não como número — normalize pra número (euros) na sua estrutura de saída, mas preserve o texto original também, para conferência.
- `Valor_Mercado_Maximo_Texto` (maior valor histórico de mercado) **não tem fonte automatizada nem manual confirmada ainda** — normalmente vem em branco. Trate como campo opcional, não obrigatório; não trave a validação por causa dele.
- O fetch automático direto ao Transfermarkt está bloqueado neste projeto (testado e confirmado) — não tente automatizar a extração, os dados dessa aba são sempre inserção manual.

Ignore por enquanto a aba `Noticias` (é cache manual opcional, não a fonte da pesquisa ativa descrita abaixo).

## Pesquisa de notícias — comportamento esperado

Pra cada jogador, busque notícia recente (**janela de 15 dias**, contados a partir de hoje).

**Já testei manualmente antes de pedir isso — o resultado real deve te preparar:** pra jogadores desse nível (2ª divisão portuguesa, 2ª divisão argentina, ou 1ª divisão recém-promovida), é normal e esperado **não encontrar nada dentro de 15 dias**. No teste que fiz, o André Clóvis não tinha nenhuma notícia nos últimos 15 dias — o item mais recente tinha mais de um mês.

Por isso:
- **Nunca force um item antigo pra preencher a lacuna.** Se não achar nada dentro da janela, o resultado correto é um estado explícito de "sem notícia recente" — não o item mais próximo disponível apresentado como se fosse atual.
- Se decidir mostrar o item mais recente mesmo fora da janela (como contexto, não como notícia fresca), rotule com a idade real em dias, nunca omita isso.
- Datas de publicação são obrigatórias em cada item; não invente nem resuma além do que a fonte diz.

## Entregável desta etapa

Não construa o HTML final ainda. O que preciso validar antes de seguir:

1. Um script que lê a planilha inteira (as três abas relevantes), junta os dados **por ID**, valida (incluindo os alertas de qualidade descritos acima) e gera uma saída estruturada intermediária (JSON, um arquivo por jogador ou um único consolidado — documente o formato escolhido) combinando performance + mercado/empresário + resultado da pesquisa de notícia.
2. Um relatório curto listando qualquer inconsistência encontrada — linhas incompletas, falha de junção por ID, métrica faltando, valor de mercado ausente — pra eu revisar antes de confiar no pipeline.

Rode isso pros 4 jogadores e me mostre o resultado. Só depois de eu validar avançamos pro output em HTML publicado no GitHub Pages.
