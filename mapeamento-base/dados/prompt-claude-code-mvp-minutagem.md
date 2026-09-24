# Prompt para Claude Code — MVP "Mapeamento de Base" (minutagem)

> Substitui todos os prompts anteriores. Cole como mensagem única, anexando `mapeamento_base_mvp.xlsx`. Objetivo: MVP simples, entregue hoje.

## Escopo

É uma página de ranking de minutos dos **245 egressos validados de 7 clubes formadores** (Internacional, Palmeiras, Flamengo, São Paulo, Corinthians, Fluminense, Santos). Reaproveite o visual da página atual do Celeiro de Ases: tema, tipografia, cartões e pílulas, como está hoje. Publique em **`mapeamento-base/saida/index.html`** e não apague a página antiga.

Cabeçalho, só estas duas linhas:
```
PROJETO FUTEBOL • MAPEAMENTO DE BASE
Para onde vão as crias da base
```

## Dado — `mapeamento_base_mvp.xlsx`

Tudo já vem calculado. Não recalcule, não junte por nome; a chave é `ID_Base`.

- **`Jogadores`** — 245 linhas, já ordenadas do maior para o menor. Colunas usadas na página: `Ranking`, `Nome`, `Clube_Formador`, `Clube_Atual`, `Pais_Clube`, `Status_Atual`, `Posicao`, `Idade`, `Contrato_Ate`, `Minutos_ultimos_3_anos`, `Jogos_ultimos_3_anos`, `Badge_Minutos`, `Trajetoria_Curta`, `Min_2023`, `Min_2024`, `Min_2025`, `Min_Temporada_Atual_2026`.
- **`Minutos_por_Temporada`** — apoio, com o detalhe por temporada e competição. Não precisa aparecer na página.
- **`Legenda`** — regras. Vira uma nota curta recolhível no rodapé.

## Tela 1 — Ranking

- **Header fixo** (sticky, respeitando a safe-area do iOS): título, mais duas fileiras de chips roláveis na horizontal:
  1. Clube formador: Todos + os 7 clubes, com contagem.
  2. País do clube atual, com contagem que recalcula conforme o formador escolhido.
  
  Os dois filtros se combinam. Só a lista rola.
- **Cada linha:** posição no ranking, iniciais, nome, "clube atual · país", pílula pequena do clube formador e, à direita, a **pílula com os minutos dos últimos 3 anos** (formato `12.866`, separador de milhar) na cor do badge.
- **Cor do badge:** 🟢 ≥ 4.500 · 🟡 1.500–4.499 · 🔴 < 1.500. Se for `N/D`, a pílula fica cinza com o texto "em coleta" e o jogador vai para o fim da lista.
- A ordem da lista é sempre por minutos, do maior para o menor, também depois de aplicar os filtros. O número do ranking é o geral; não renumerar ao filtrar.

## Tela 2 — Ficha

Toque no nome abre a ficha em tela cheia, com botão de voltar que devolve à lista na mesma posição de rolagem. **Sem "+", sem expandir, sem radar, sem métricas por posição.**

1. **Cabeçalho:** iniciais, nome, "clube atual · país" e uma pílula de status.
2. **Bio:** idade, posição, clube formador, contrato até (mostrar N/D se vazio).
3. **Minutos:**
   - Destaque: minutos nos últimos 3 anos, com badge. Abaixo, os jogos nos últimos 3 anos.
   - Linha por temporada: 2023 · 2024 · 2025 (barras horizontais simples ou só números, o que ficar mais limpo no celular).
   - Separado: temporada atual (2026).
   - Se `Trajetoria_Curta = True`, mostrar a pílula discreta "trajetória curta".

## Visual

É o mesmo padrão das telas atuais: cartões planos, label pequeno e cinza acima, valor grande abaixo, pílulas para status e badge, coluna única no celular, sem emojis além dos badges. Remova o texto de rodapé atual ("Fonte única…").

## Execução

1. Ler a planilha e me mostrar três coisas: o total (esperado: 245), a contagem por clube formador (Internacional 55, Palmeiras 44, Flamengo 38, São Paulo 38, Corinthians 29, Fluminense 22, Santos 19) e o total com N/D (esperado: 1). **Pare aqui.**
2. Construir a página (ranking + ficha), mobile-first.
3. Publicar em `mapeamento-base/saida/index.html`.
