# Mapeamento do Celeiro de Ases

Frente do "Projeto Futebol" institucional do Inter (Celeiro de Ases /
Expansão e Captação) — mapeia onde estão hoje os 34 egressos das
categorias de base do clube. Reaproveita a infraestrutura do repositório
do Scout Individual (mesma sessão de nuvem, mesmo padrão de leitura de
planilha local, mesmo estilo de card com "+"), mas é uma frente de dado
separada. Prompt vigente em `dados/prompt-claude-code-celeiro-de-ases.md`.

**Status**: passos 1, 2, 3 e 4 concluídos — leitura/validação,
JSON combinado, a página HTML (lista filtrável por país + cards,
mobile-first, `saida/mapa_preview.html`) e publicação no GitHub Pages.
A página inicial do repositório (`index.html`/`docs/index.html`) agora
lista os dois projetos (Scout Individual e Celeiro de Ases).

## Arquivos

```
celeiro-de-ases/
├── dados/
│   ├── celeiro_de_ases_dados.xlsx        ← fonte oficial (3 abas, já reconciliadas)
│   ├── celeiro_jogadores_master.csv      ← export redundante só da aba Jogadores (mesmo dado do xlsx)
│   └── prompt-claude-code-celeiro-de-ases.md
├── scripts/
│   ├── etapa1_pipeline.py    ← passo 1: lê e valida as 3 abas
│   ├── etapa2_combinar.py    ← passo 2: combina a saída do passo 1 num JSON por jogador
│   └── gerar_mapa_html.py    ← passo 3: monta a página HTML (mapa + lista + cards)
└── saida/
    ├── jogadores_lidos.json              ← saída do passo 1 (aba Jogadores)
    ├── performance_carreira_lida.json    ← saída do passo 1 (Performance_Carreira, por jogador)
    ├── performance_season_lida.json      ← saída do passo 1 (Performance_Season, por jogador)
    ├── relatorio_validacao.txt           ← inconsistências encontradas no passo 1
    ├── <jogador>.json                    ← JSON combinado por jogador (passo 2)
    ├── consolidado.json                  ← todos os jogadores num único arquivo (passo 2)
    └── mapa_preview.html                 ← página HTML gerada (passo 3)
```

## Formato da fonte (bem diferente do Scout Individual)

`Performance_Carreira` e `Performance_Season` vêm em **formato longo de
verdade** — uma linha = uma métrica só (`Jogador, Temporada, Competicao,
Categoria, Metrica, Valor`), não os blocos pipe-delimitados
(`Colunas_Metricas | Valores`) do Scout Individual. Muito mais simples
de parsear; não existe a validação de "métrica sem valor correspondente"
porque não há bloco pra descasar.

As 3 abas (`Jogadores`, `Performance_Carreira`, `Performance_Season`)
terminam com 1 linha em branco + 1 linha de nota do autor da planilha
(ex.: `"Pais_Clube é [Inferência]..."` na aba Jogadores) — não é dado
real, descartada por regra estrutural (linha sem `SofascoreID` /
sem `Temporada`+`Competicao`+`Categoria`+`Metrica`, mesma lógica do
descarte da categoria `"Partidas"`).

## Junção — já vinha pronta

O prompt é explícito: **"não refaça a junção de dados, ela já foi feita
manualmente antes de gerar este arquivo"**. Confirmado nesta rodada: os
34 nomes batem 100% entre as 3 abas, zero jogador órfão.

## Validações aplicadas

1. **Categoria `"Partidas"`** — já vem descartada na exportação; o
   pipeline mantém a regra como guarda-chuva caso reapareça numa
   atualização futura.
2. **`Competicao = "Total do Ano"`** — sempre tratado como agregado
   (`tipo_linha: "total_temporada"`), nunca como nome de liga real.
3. **13/34 sem radar (ATT/TEC/TAC/DEF/CRE)** — confirmado exatamente
   como o prompt descreveu (Weverton, Dudu, Pedro Lucas, Guilherme
   Pato, Netto, Bruno Praxedes, Matheus Cadorini, Estêvão, Kauan,
   Gabriel Carvalho, Lucca Drummond, Raykkonen Pereira Soares, Ricardo
   Mathias). Estado normal — ausência real de volume mínimo de minutos
   ou de clube ativo — nunca tratado como falha de captura.
4. **Pedro Lucas e Lucca Drummond sem `Pais_Clube`** — "sem
   localização no mapa" explícito, mantidos na lista (nunca omitidos
   silenciosamente), com botão próprio fora do fluxo do mapa.
5. **Kauan (único goleiro)** — limitação estrutural sinalizada
   explicitamente na própria página: categorias capturadas
   (Atacando/Passe/Defendendo) são voltadas a jogador de linha, sem
   defesas/gols sofridos/clean sheets. Card mais magro por essa razão,
   não por falha de captura.

Dois bugs de robustez do próprio parser, achados e corrigidos durante a
checagem desta rodada:
- Linha de nota de rodapé da planilha sendo lida como se fosse um
  jogador/dado real (faltava checar se as colunas-chave estavam todas
  vazias, não só a primeira).
- Valores vazios de radar (`NaN` do pandas) virando a string literal
  `"nan"` em vez de `None` — escondia os 13 jogadores sem radar como se
  tivessem radar completo.

Resultado do passo 1: **0 `[ERRO]`, 0 `[ALERTA]`, 24 `[INFO]`** — tudo
estado já esperado pelo próprio prompt.

## Escopo desta versão

Por pedido explícito do prompt: **sem lesões**, **sem Transfermarkt**
(mercado além do que já veio na planilha, empresário detalhado,
rumores). Valor de mercado, contrato e agente aparecem porque já
estavam na aba `Jogadores`.

## Arquétipos (5, não 3 — base mais diversa que o Scout Individual)

| Arquétipo | Métricas-chave |
|---|---|
| Atacante | Gols/90, xG (total da temporada, não por 90), Conversão, Finalizações/jogo, Chutes no alvo/jogo |
| Meio-campista | Passes certos, Passes decisivos, Grandes chances criadas, Desarmes/jogo |
| Zagueiro | Desarmes/jogo, Interceptações, Duelos aéreos ganhos, Cortes/jogo, Passes certos |
| Lateral | Desarmes/jogo, Interceptações, Duelos ganhos (chão e aéreo), Cruzamentos certos, Passes certos no terço final |
| Goleiro | Sem perfil de métricas-chave — limitação estrutural sinalizada na página (só 1 jogador, Kauan) |

## Mapa — tentado, removido a pedido do usuário

O prompt sugeria "mapa SVG leve com países como paths clicáveis" e
citava fontes públicas de SVG de mundo. Tentei buscar uma (Wikimedia e
outras) e o proxy de rede deste ambiente bloqueou o host por política
("policy denial") — sem fonte geográfica confiável disponível aqui.
Em vez de desenhar litorais à mão, a v1 usou um **mapa de símbolos
proporcionais** (SVG próprio, graticule + um círculo por país,
área ~ nº de jogadores) — funcional, mas depois de revisar o usuário
pediu pra tirar o mapa-múndi inteiro e manter só o cabeçalho com nome
do país. Feito: `gerar_mapa_svg()` foi removida do script, e a seção
"Países" agora é só a fileira de chips clicáveis (mesma lógica de
filtro de antes, sem o SVG).

Os dois sentidos de interação pedidos continuam implementados sem o
mapa: clicar num chip de país filtra a lista; clicar num jogador na
lista atualiza o painel de métricas-chave pra aquele jogador
especificamente (o destaque de país agora é só o chip ficando ativo).
Brasil (19/34 jogadores) mostra a lista sub-agrupada por clube em vez
de uma lista plana, como o prompt pediu.

## Ajustes de v1.1 (feedback pós-preview)

- **Cor**: acento trocado pro vermelho oficial do Internacional,
  `#E5050F` (fornecido pelo usuário) — light mode usa a cor pura em
  elementos preenchidos (badges, botões ativos) e uma variante mais
  escura (`#B90109`) em texto pequeno sobre fundo claro, pra manter
  contraste AA; dark mode usa uma variante mais clara da mesma matiz
  (`#FF4B52`) em vez do vermelho puro, que teria contraste insuficiente
  em texto pequeno sobre fundo escuro.
- **Valores ausentes**: `"N/D"` trocado por um hífen (`–`) numa cor bem
  próxima do fundo (`--vazio`, ~30% de opacidade), pra ficar visualmente
  discreto em vez de competir com dado real.
- **Totais em negrito**: linhas `"Total do Ano"` na tabela de histórico
  de carreira agora em negrito, pra se distinguir das linhas de
  competição individual.
- **Bônus**: `<meta name="format-detection" content="telephone=no,...">`
  adicionada — Safari/iOS às vezes transforma números soltos (como os
  da coluna MP da tabela) em links de telefone azuis; a meta tag evita
  isso.

## Rodar

```bash
# passo 1: le e valida a planilha
python3 scripts/etapa1_pipeline.py

# passo 2: combina em JSON por jogador
python3 scripts/etapa2_combinar.py

# passo 3: gera a pagina HTML
python3 scripts/gerar_mapa_html.py
```

Testado desktop e mobile (390px), claro e escuro.
