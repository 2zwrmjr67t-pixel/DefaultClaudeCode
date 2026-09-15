# Prompt para Claude Code — Projeto "Scout Individual", v1 completa

> Consolida tudo o que foi testado e validado nesta conversa. Cole como mensagem inicial no Claude Code. Este é o build completo — dado + página HTML publicada — não mais uma etapa isolada.

## Contexto

Projeto pessoal, conectado ao trabalho no GT digital do Internacional, mas fora da estrutura institucional. Acompanhamento individual de 4 jogadores nomeados (não análise de liga inteira — isso é fora de escopo).

## Jogadores e arquétipos

| Jogador | Clube | Competição | Arquétipo | Métricas-chave |
|---|---|---|---|---|
| André Clóvis | Académico de Viseu | Liga Portugal Betclic | Centroavante | Gols/90, xG/90, Conversão, Finalizações/jogo, Chutes no alvo/jogo, Grandes chances perdidas |
| Thiago Ocampo | Nueva Chicago | Primera Nacional (Argentina) | Ponta/Extremo | Gols/90, xG/90, Assistências/xA, Dribles certos, Grandes chances criadas, Passes decisivos |
| Thauan Lara | Portimonense | Liga Portugal 2 | Lateral/Ala | Desarmes/jogo, Interceptações, Duelos ganhos (chão e aéreo), Cruzamentos certos, Passes certos no terço final |
| Renê | Vitória | Brasileirão Série A | Ponta/Extremo* | mesmas do arquétipo acima |

**\*Ressalva sobre o Renê:** classificado como "Ponta/Extremo" pela etiqueta oficial do Transfermarkt, mas o volume de gols dele (8 em 20 jogos, ~0.53 gols/90) é mais próximo de centroavante do que de ponta pura. Isso é `[Inferência]`, não `[Verificado]` — marque isso explicitamente na página dele, não assuma silenciosamente um dos dois.

O arquétipo de cada jogador fica na aba `Jogadores` (coluna `Arquetipo`) — leia de lá, não hardcode.

## Fonte de dado — planilha local

`~/scout-individual/dados/scout_individual_dados.xlsx` (confirmar caminho comigo se for diferente). Leia com `pandas.read_excel(caminho, sheet_name=None)`. Abas e uso:

| Aba | Conteúdo | Uso na página |
|---|---|---|
| `Jogadores` | Cadastro mestre, IDs, arquétipo | Chave de junção — **sempre por ID, nunca por nome de texto** (nomes divergem entre fontes: "Renê" vs "Renê Sousa", "Académico FC" vs "Académico de Viseu") |
| `Performance_Sofascore` | Formato longo por categoria/temporada, histórico de carreira | Gráfico de evolução por temporada (o "minutos por temporada" que já prototipamos) |
| `Performance_Season` | Formato longo, dado "por jogo" já normalizado pelo Sofascore (temporada atual, mais granular) | Fonte primária das métricas-chave por arquétipo e da visão completa/expandida |
| `Radar_Atributos` | ATT, TEC, TAC, DEF, CRE por jogador | Radar visual — **rotular sempre como "índice proprietário Sofascore"**, nunca misturar com métrica de contagem direta |
| `Transfermarkt` | Valor de mercado, contrato, empresário, posição | Bloco de mercado |
| `Lesoes` | Status de lesão atual/histórico | Selo de status (verde "sem lesão" / vermelho com detalhe se houver) |
| `Rumores` | Clubes interessados, datas | Seção separada, rotulada `[Especulação]` |
| `Noticias` | Cache manual opcional | Não é fonte principal — a pesquisa ativa (abaixo) é a fonte real |

### Validações obrigatórias (já vimos essas falhas acontecerem — não repita)
1. **`Performance_Season`: descarte qualquer linha com `Categoria = "Partidas"`.** É despejo bruto corrompido da página, não uma categoria real — duplica (mal) o que já vem certo nas outras categorias.
2. **Contagem de métricas:** se o número de valores for menor que o de rótulos numa linha (já aconteceu com a nota ASR), sinalize como incompleta, não descarte o excedente silenciosamente.
3. **Junção sempre por ID.** Nunca compare texto de nome/clube entre abas.
4. **Nem todo jogador tem todas as categorias.** Ex: Thiago Ocampo não tem `Desempenho de corrida` no `Performance_Season` — trate como ausência normal (provável limitação de rastreamento físico na liga dele), não como erro a corrigir.

## Pesquisa de notícias — comportamento e correção de bug já identificada

Janela de **15 dias**. Já testamos manualmente e encontramos um bug real na primeira tentativa: a busca trouxe uma notícia de prêmio de 10 dias atrás em vez de um resultado de partida de 2 dias atrás que existia e era mais relevante. Correção obrigatória:
- **Monte a query incluindo clube + termo de evento** (ex: `"Renê" "Vitória" gols` ou `"Renê" "Vitória" jogo`), não só o nome do jogador — isso indexa muito melhor cobertura de resultado de partida.
- **Ordene os candidatos por data de publicação real, não por relevância do buscador**, e escolha o mais recente dentro da janela.
- Se não achar nada dentro de 15 dias, **estado explícito de "sem notícia recente"** — nunca forçar um item antigo como se fosse fresco. Se mostrar contexto histórico mesmo assim, rotule a idade real em dias.

O mesmo princípio de estado vazio explícito vale pra **rumores** (aba `Rumores`) — Thauan Lara e Thiago Ocampo não têm nenhum registro; não é erro, é resultado real.

## Estrutura da página — resumo + completo

Cada jogador tem uma página com dois níveis de visibilidade, não um só:

1. **Resumo (visível por padrão):** cabeçalho (nome, clube, competição, selo de lesão), bloco de métricas-chave do arquétipo dele, radar de atributos, bloco de mercado, notícia mais recente (ou estado vazio), rumores mais recentes (ou estado vazio) — layout já validado nos mockups desta conversa.
2. **Completo (atrás de um "mostrar mais"/expandir):** **100% dos dados extraídos**, sem filtro de arquétipo — todas as categorias do `Performance_Season` e `Performance_Sofascore` (Geral, Finalização, Jogo coletivo, Passe, Defendendo, Adicional/xG, Cartões, Desempenho de corrida), histórico completo de temporadas, todos os rumores registrados (não só os 2 mais recentes).

Use um padrão nativo de HTML/CSS pra isso (ex: `<details>`/`<summary>`, ou toggle simples com JS) — nada que dependa de biblioteca externa pesada, já que o resto do projeto é estático.

## Output

- HTML estático, **mobile-first obrigatório** — teste em viewport estreito antes de considerar pronto, não só em desktop.
- Hospedagem via GitHub Pages.
- Todo dado marcado: `[Verificado — fonte]` / `[Inferência]` / `[Especulação]` — aplique isso explicitamente no caso do arquétipo do Renê e em qualquer inferência de posição.
- Seção de limitações por jogador, nomeando o que não tem fonte confiável (ex: Desempenho de corrida ausente pro Thiago Ocampo).

## Ordem de execução pedida

1. Ler e validar a planilha inteira (todas as 7 abas de dado), aplicando as 4 validações obrigatórias acima. Me mostrar um relatório de inconsistências antes de continuar.
2. Montar a estrutura de dado intermediária (JSON por jogador) juntando performance + mercado + lesão + rumor + notícia.
3. Construir o HTML (resumo + completo, mobile-first) usando os arquétipos definidos.
4. Publicar no GitHub Pages.

Pare e me mostre o resultado depois do passo 1 antes de seguir pros próximos — mesmo sendo a v1 "completa", ainda quero validar a leitura de dado antes de gerar página.
