# Prompt para Claude Code — "Mapeamento do Celeiro de Ases" (consolidado, versão final)

> Substitui todos os prompts anteriores desta frente. Cole como mensagem única, anexando `celeiro_de_ases_dados.xlsx`.

## Contexto

Frente ligada ao "Projeto Futebol" institucional do Inter (Celeiro de Ases). Mapeia onde estão hoje os egressos das categorias de base do clube. Reaproveita a infraestrutura de repositório do projeto Scout Individual, mas é dado e escopo separados. Título: **"Mapeamento do Celeiro de Ases"**.

## Dado — o que mudou desde a última versão publicada

Estou anexando `celeiro_de_ases_dados.xlsx` atualizado: **33 jogadores** (Victor Gabriel foi removido — não pertence a essa frente). Releia a planilha inteira, não faça remoção pontual do card dele — a contagem de país também muda (Brasil: 19→18).

Três abas, já reconciliadas manualmente — não refaça a junção:
- **`Jogadores`** — cadastro mestre. `Pais_Clube` é `[Inferência]`. `Arquetipo` por posição (Atacante, Meio-campista, Zagueiro, Lateral, Goleiro). `Status` distingue Egresso / Ainda no Internacional / Ainda na base (U17) / Sem clube. `Jogos_Temporada_Atual`, `Jogos_ultimos_3_anos` e `Badge_Atividade` (🟢≥60 / 🟡20-59 / 🔴<20) já calculados. `Valor_Mercado` ausente em 5 jogadores — é `N/D` real, não omitir.
- **`Performance_Carreira`** — formato longo, histórico completo.
- **`Performance_Season`** — formato longo, temporada atual. 13 de 33 sem `ATT/TEC/TAC/DEF/CRE` (radar) — ausência real (sem clube, sem volume mínimo, ou ainda no U17), não erro.

### Validações já conhecidas — não redescubra
Categoria `"Partidas"` sempre corrompida, descarte. `Competicao = "Total do Ano"` é agregado, nunca nome de liga. Kauan (goleiro) tem dado estruturalmente mais pobre — categorias pensadas pra jogador de linha não capturam defesas/gols sofridos dele, é limitação de fonte, não de captura.

## Escopo — decisões fechadas, não reabra

- **Sem lesões, sem Transfermarkt** (mercado/rumores) nesta versão.
- **Mapa-múndi interativo: abandonado, decisão final.** Chips de país clicáveis (contagem real por país, clique filtra a lista) são a solução definitiva — não é solução temporária, não tente implementar mapa de novo.

## Fluxo — duas telas, lista e ficha

1. **Lista:** cabeçalho com chips de país roláveis horizontalmente (contagem por país). Abaixo, jogadores em linhas compactas: avatar/iniciais, nome, clube + país, badge de atividade.
2. **Toque no jogador → ficha em tela cheia** (troca de estado local, não navegação de URL/rota nova): cabeçalho com botão de voltar, avatar, nome, clube. Botão de voltar retorna pra lista no mesmo ponto de rolagem.
3. Mesmo comportamento em mobile e desktop.

### Conteúdo da ficha — resumo vs. completo
- **Resumo (visível direto):** bio básica (idade, altura, pé, posição, camisa), e os 3 KPIs universais — **jogos na temporada atual**, **jogos nos últimos 3 anos** (com badge), **valor de mercado** (ou "N/D"). Nada de métrica por arquétipo aqui — fica leve e igual pra qualquer posição.
- **Completo (atrás do "+"):** métricas-chave do arquétipo (tabela abaixo), radar de atributos quando existir (rotulado "índice Sofascore", nunca como contagem direta), 100% do histórico de `Performance_Carreira` e `Performance_Season`, todas as categorias.

| Arquétipo | Métricas-chave (na visão completa) |
|---|---|
| Atacante | Gols/90, xG, Conversão, Finalizações/jogo, Chutes no alvo/jogo |
| Meio-campista | Passes certos %, Passes decisivos, Grandes chances criadas, Desarmes/jogo |
| Zagueiro | Desarmes/jogo, Interceptações, Duelos aéreos ganhos, Cortes/jogo, Passes certos % |
| Lateral | Desarmes/jogo, Interceptações, Duelos ganhos (chão e aéreo), Cruzamentos certos, Passes certos no terço final |
| Goleiro | Sinalizar limitação de dado explicitamente — não forçar métricas de linha nele |

## Visual esperado — descrição detalhada, siga isso à risca

O padrão visual que validamos e gostamos (testado em protótipo antes deste prompt) é **flat, limpo, denso em informação mas arejado** — não é um dashboard carregado. Especificamente:

- **Cards, não tabelas soltas:** cada bloco de conteúdo (bio, KPIs, radar, histórico) vive dentro de um cartão com fundo branco/claro, borda fina de 1px em cinza bem sutil (não preta, não sombra pesada), cantos arredondados (~12px), padding generoso (16-20px). Nada de sombra profunda, gradiente, ou textura decorativa — superfície plana.
- **Hierarquia por tamanho e peso, não por cor forte:** cada métrica é um par label+valor — o **label vem pequeno e em cinza secundário (não preto), acima**; o **valor vem maior e mais escuro, abaixo**. Não inverta essa hierarquia. Use no máximo duas espessuras de fonte (regular e um médio/semi-bold pra números e títulos) — nunca negrito pesado espalhado pelo texto corrido.
- **Badges como pílulas coloridas pequenas:** o indicador 🟢🟡🔴 de atividade, e qualquer selo de status (ex: "Ainda no Internacional", "N/D"), aparecem como pílula pequena (texto 11-12px, padding curto, cantos bem arredondados), cor de fundo clara e texto na cor escura correspondente à mesma família — nunca texto colorido sobre fundo branco liso pra indicar status.
- **Cabeçalho de jogador consistente:** em toda ficha, mesmo padrão — círculo com iniciais (ou foto se houver) à esquerda, nome em destaque e clube/país como subtítulo menor e mais claro ao lado, sem variar esse layout entre jogadores.
- **Espaçamento generoso entre seções**, não comprimido — cada cartão (bio, KPIs, radar) tem uma margem clara em relação ao próximo, nunca colados.
- **Densidade mobile:** em telas estreitas, tudo empilha em coluna única — nunca grid de 3+ colunas espremendo texto. Números grandes (KPIs) podem ficar em grid de 2 colunas no máximo.
- **Sem emoji decorativo fora dos badges de atividade** (os 🟢🟡🔴 já definidos são a exceção, fazem parte do sistema de status) — ícones de UI (voltar, seta, etc.) usam um conjunto de ícones outline simples e consistente, não emoji misto.

Se tiver dúvida de como algo deveria se comportar visualmente, prefira sempre a opção mais simples/enxuta — o objetivo é parecer um produto polido, não uma planilha exportada.

## Ordem de execução

1. Ler e validar a planilha atualizada (33 jogadores), aplicando as regras já conhecidas. Mostrar contagem final por país antes de prosseguir.
2. Montar estrutura intermediária (JSON por jogador).
3. Construir/ajustar o HTML (lista + ficha, resumo + completo) seguindo a especificação visual acima, mobile-first.
4. Publicar no GitHub Pages, substituindo a versão anterior.

Pare após o passo 1 e me mostre a contagem por país antes de seguir pro resto.
