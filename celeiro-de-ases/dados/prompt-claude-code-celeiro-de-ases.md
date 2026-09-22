# Prompt para Claude Code — "Mapeamento do Celeiro de Ases"

> Reaproveita a infraestrutura do repositório do projeto Scout Individual (mesmo ambiente de nuvem, mesmo padrão de leitura de planilha local, mesmo estilo de card com "+"), mas é uma frente de dado separada — 34 jogadores egressos da base do Internacional, não os 4 do Scout Individual. Cole como mensagem inicial numa sessão nova do Claude Code.

## Contexto

Frente ligada ao "Projeto Futebol" institucional do Inter (Celeiro de Ases / Expansão e Captação). Mapeia onde estão hoje os egressos das categorias de base do clube. Título da página: **"Mapeamento do Celeiro de Ases"**.

## Fonte de dado

Arquivo `celeiro_de_ases_dados.xlsx`, local (`~/scout-individual/dados/` ou pasta equivalente — confirmar comigo). Três abas, já reconciliadas — **não refaça a junção de dados, ela já foi feita manualmente antes de gerar este arquivo**:

- **`Jogadores`** — cadastro mestre, um jogador por linha. Já inclui `Pais_Clube` (derivado do clube, `[Inferência]` — conferir antes de publicar), `Arquetipo` (por posição), `Status` (`Egresso` / `Ainda no Internacional` / `Ainda na base (U17)` / `Sem clube`), `Jogos_ultimos_3_anos` e `Badge_Atividade` (já calculados). Nomes já normalizados (ex: Gabriel Carvalho = Gabriel Teixeira, mesma pessoa, unificado).
- **`Performance_Carreira`** — formato longo, histórico completo por temporada/competição.
- **`Performance_Season`** — formato longo, temporada atual detalhada. **13 dos 34 jogadores não têm ATT/TEC/TAC/DEF/CRE** (radar) — não é erro, é ausência real de volume mínimo de minutos ou de clube ativo. Trate como estado normal, não como falha de captura.

### Validação obrigatória (mesmas regras já aprendidas no Scout Individual)
- Categoria `"Partidas"` já foi descartada nesta exportação — se aparecer de novo em atualização futura, descarte de novo (é despejo bruto corrompido).
- `Competicao = "Total do Ano"` é agregado, nunca trate como nome de liga real.
- Times sem `Pais_Clube` preenchido (`Pedro Lucas`, `Lucca Drummond` — sem clube no momento) não têm onde ser plotados no mapa. Trate como "sem localização" explícito, não omita silenciosamente da lista.

## Escopo desta versão — nada disso entra agora
- **Sem lesões.**
- **Sem Transfermarkt** (mercado, empresário, rumores) — só o que já está na planilha.

## Arquétipos por posição (5, não 3 — base mais diversa que o Scout Individual)

| Arquétipo | Métricas-chave em destaque |
|---|---|
| **Atacante** | Gols/90, xG, Conversão, Finalizações/jogo, Chutes no alvo/jogo |
| **Meio-campista** | Passes certos %, Passes decisivos, Grandes chances criadas, Desarmes/jogo |
| **Zagueiro** | Desarmes/jogo, Interceptações, Duelos aéreos ganhos, Cortes/jogo, Passes certos % |
| **Lateral** | Desarmes/jogo, Interceptações, Duelos ganhos (chão e aéreo), Cruzamentos certos, Passes certos no terço final |
| **Goleiro** | **Limitação conhecida:** as categorias capturadas (Atacando/Passe/Defendendo) são voltadas a jogador de linha — não há dado de defesas, gols sofridos ou clean sheets pro Kauan (único goleiro da base). O card dele vai ficar bem mais magro que os outros por essa razão estrutural, não por falha de captura. Sinalize isso explicitamente na página dele. |

## Etiqueta de atividade (já calculada, só aplicar)

🟢 ≥60 jogos nos últimos 3 anos (excluindo temporada atual) · 🟡 20-59 · 🔴 <20 — já está na coluna `Badge_Atividade` da aba `Jogadores`, não recalcule.

## Mapa-múndi dinâmico — comportamento esperado

Dois sentidos de interação, os dois obrigatórios:
1. **Clicar num país do mapa** → filtra a lista de jogadores pra só os que têm `Pais_Clube` igual ao país clicado.
2. **Clicar/selecionar um jogador na lista** → o mapa dá destaque visual ao país dele (ex: highlight de cor, zoom ou marcador), **e a tela de métricas-chave se ajusta pra mostrar os highlights daquele jogador especificamente** (arquétipo dele, radar se existir, badge de atividade).

Use um mapa SVG leve com os países como paths clicáveis (existem várias fontes de SVG de mundo de domínio público) — nada de biblioteca pesada de mapas, o resto do site é estático. A maioria dos jogadores está no Brasil (17 de 34) — pense em como isso fica visualmente no mapa sem virar um blob sem informação (ex: ao clicar Brasil, a lista mostra os 17, talvez com sub-agrupamento por clube).

## Estrutura do card — resumo + completo (mesmo padrão do Scout Individual)

1. **Resumo:** nome, clube atual, país, status (badge se for "Ainda no Internacional"/"Ainda na base"/"Sem clube" — visualmente diferente de "Egresso"), badge de atividade (🟢🟡🔴), métricas-chave do arquétipo, radar se existir (rotulado "índice Sofascore", nunca como contagem direta).
2. **Completo (atrás do "+"):** 100% dos dados de `Performance_Carreira` e `Performance_Season`, todas as categorias, todo o histórico de temporadas.

## Output

- HTML estático, mobile-first, GitHub Pages.
- `[Verificado — fonte]` / `[Inferência]` (explicitamente no caso de `Pais_Clube`) / `[Especulação]`.
- Seção de limitações por jogador: nomeie os 13 sem radar, o Kauan sem dado de goleiro, e os 2 sem clube (Pedro Lucas, Lucca Drummond) sem localização no mapa.

## Ordem de execução

1. Ler e validar a planilha (3 abas), aplicar as regras acima, relatório de inconsistências pra eu revisar.
2. Montar estrutura intermediária (JSON por jogador).
3. Construir o mapa interativo + cards (resumo + completo), mobile-first.
4. Publicar no GitHub Pages.

Pare após o passo 1 antes de seguir.
