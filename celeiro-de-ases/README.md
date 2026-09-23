# Mapeamento do Celeiro de Ases

Frente do "Projeto Futebol" institucional do Inter (Celeiro de Ases /
Expansão e Captação) — mapeia onde estão hoje os 51 egressos das
categorias de base do clube. Reaproveita a infraestrutura do repositório
do Scout Individual (mesma sessão de nuvem, mesmo padrão de leitura de
planilha local, mesmo estilo de card com "+"), mas é uma frente de dado
separada. Prompt vigente em `dados/prompt-claude-code-celeiro-FINAL.md`.

**Status**: passos 1 a 4 concluídos na rodada final (33 jogadores) —
leitura/validação, JSON combinado, a página HTML no padrão
**lista → ficha** (`saida/celeiro_de_ases.html`) e publicação no GitHub
Pages. A página inicial do repositório (`index.html`/`docs/index.html`)
lista os dois projetos (Scout Individual e Celeiro de Ases).

## Arquivos

```
celeiro-de-ases/
├── dados/
│   ├── celeiro_de_ases_dados.xlsx        ← fonte oficial (3 abas, já reconciliadas)
│   ├── celeiro_jogadores_master.csv      ← export redundante só da aba Jogadores (mesmo dado do xlsx)
│   ├── prompt-claude-code-celeiro-FINAL.md  ← prompt vigente
│   └── prompt-claude-code-celeiro-de-ases.md ← versão anterior, histórico
├── scripts/
│   ├── etapa1_pipeline.py    ← passo 1: lê e valida as 3 abas
│   ├── etapa2_combinar.py    ← passo 2: combina a saída do passo 1 num JSON por jogador
│   └── gerar_html.py         ← passo 3: monta a página HTML (lista → ficha)
└── saida/
    ├── jogadores_lidos.json              ← saída do passo 1 (aba Jogadores)
    ├── performance_carreira_lida.json    ← saída do passo 1 (Performance_Carreira, por jogador)
    ├── performance_season_lida.json      ← saída do passo 1 (Performance_Season, por jogador)
    ├── relatorio_validacao.txt           ← inconsistências encontradas no passo 1
    ├── <jogador>.json                    ← JSON combinado por jogador (passo 2)
    ├── consolidado.json                  ← todos os jogadores num único arquivo (passo 2)
    └── celeiro_de_ases.html              ← página HTML gerada (passo 3)
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
33 nomes batem 100% entre as 3 abas, zero jogador órfão.

## Validações aplicadas

1. **Categoria `"Partidas"`** — já vem descartada na exportação; o
   pipeline mantém a regra como guarda-chuva caso reapareça numa
   atualização futura.
2. **`Competicao = "Total do Ano"`** — sempre tratado como agregado
   (`tipo_linha: "total_temporada"`), nunca como nome de liga real.
3. **13/33 sem radar (ATT/TEC/TAC/DEF/CRE)** — confirmado exatamente
   como o prompt descreveu (Weverton, Dudu, Pedro Lucas, Guilherme
   Pato, Netto, Bruno Praxedes, Matheus Cadorini, Estêvão, Kauan,
   Gabriel Carvalho, Lucca Drummond, Raykkonen Pereira Soares, Ricardo
   Mathias). Estado normal — ausência real (sem clube, sem volume mínimo
   de minutos, ou ainda no U17) — nunca tratado como falha de captura.
4. **Pedro Lucas e Lucca Drummond sem `Pais_Clube`** — estado explícito,
   mantidos na lista (nunca omitidos silenciosamente) e alcançáveis pelo
   chip "Sem clube".
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

Na rodada final o usuário fechou a decisão: **mapa abandonado em
definitivo**, os chips de país são a solução, não um paliativo. Clicar
num chip filtra a lista; clicar num jogador abre a ficha dele.

## Ajustes de v1.1 (feedback pós-preview)

- **Cor**: acento trocado pro vermelho oficial do Internacional,
  `#E5050F` (fornecido pelo usuário) — light mode usa a cor pura em
  elementos preenchidos (badges, botões ativos) e uma variante mais
  escura (`#B90109`) em texto pequeno sobre fundo claro, pra manter
  contraste AA; dark mode usa uma variante mais clara da mesma matiz
  (`#FF4B52`) em vez do vermelho puro, que teria contraste insuficiente
  em texto pequeno sobre fundo escuro.
- **Valores ausentes**: hífen (`–`) numa cor bem próxima do fundo
  (`--vazio`), pra ficar discreto em vez de competir com dado real. A
  exceção é o valor de mercado, que na rodada final virou pílula `N/D`
  explícita, como o prompt pediu.
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
python3 scripts/gerar_html.py
```

Testado desktop e mobile (390px), claro e escuro.

## Rodada final — 33 jogadores, padrão lista → ficha

Planilha relida por inteiro (não houve remoção pontual de card): **Victor
Gabriel saiu da frente**, total foi de 34 para 33 e o Brasil de 19 para
18. Coluna nova `Jogos_Temporada_Atual` lida e usada como um dos 3 KPIs
universais.

**Contagem final por país:** Brasil 18 · Portugal 3 · Ucrânia 3 ·
Emirados Árabes Unidos 2 · Estados Unidos 2 · Arábia Saudita 1 ·
Bulgária 1 · Espanha 1 · sem país (sem clube) 2.

**Fluxo novo — duas telas, sem rota nova:**
1. **Lista** — chips de país roláveis na horizontal (contagem real por
   país) e linhas compactas: iniciais, nome, clube · país, pílula de
   atividade.
2. **Ficha em tela cheia** — troca de estado local em JS; o botão de
   voltar devolve a lista **no mesmo ponto de rolagem** (guarda o
   `scrollY` na ida). `Esc` também volta. Mesmo comportamento em mobile
   e desktop.

**Resumo vs. completo na ficha:** o resumo traz só bio (idade, altura,
pé, posição, camisa) e os 3 KPIs universais — jogos na temporada, jogos
nos últimos 3 anos (com a pílula de atividade) e valor de mercado (ou
`N/D` como pílula). Nenhuma métrica por arquétipo no resumo, igual pra
qualquer posição. Atrás do "+": métricas-chave do arquétipo, radar
("índice Sofascore"), 100% de `Performance_Carreira` e
`Performance_Season`, e as limitações da ficha.

**Decisões visuais seguidas à risca:** cartões planos (borda 1px sutil,
raio 12px, sem sombra), hierarquia por tamanho/peso (label pequeno e
cinza **acima**, valor maior e escuro **abaixo**), duas espessuras de
fonte (400/600), status e atividade sempre como pílula (fundo claro +
texto escuro da mesma família, nunca texto colorido solto), cabeçalho de
jogador idêntico em toda ficha, e ícones outline (voltar, seta, +/−) em
SVG — sem emoji de UI.

**Um desvio consciente, sinalizado:** o `Badge_Atividade` (🟢🟡🔴) da
planilha virou pílula colorida com bolinha CSS + palavra (Alta / Média /
Baixa), sem o glifo emoji. A regra de "badges como pílulas" e a de "sem
emoji fora dos badges de atividade" apontavam em direções diferentes; a
pílula carrega exatamente a mesma informação (a faixa aparece no
`title`) e fica consistente com o resto da UI. Fácil de reverter se
preferir o emoji visível.

## Ajustes de UI + planilha com 51 jogadores

**Dado:** a planilha anexada junto com o prompt de ajustes de UI trazia 18
jogadores novos (33 → 51); os 33 anteriores vieram idênticos. Brasil
18 → 28, países novos: Japão, México, Tchéquia, Vietnã. Status novo
"Aposentado" (Taiberson) ganhou chip próprio em vez de ir pro "Sem clube".

**Pendências de dado sinalizadas, não resolvidas aqui:**
- **Cláudio Winck** e **Valdívia** têm histórico completo em
  `Performance_Carreira`, mas não estão na aba `Jogadores` — sem clube,
  país ou status, ficam fora da lista até confirmação.
- **Carlos Miguel** (goleiro, Palmeiras) não aparece em
  `Performance_Season` — ficha mostra traço e ressalva explícita.

**Goleiros (agora 4):** perfil próprio com `Jogos sem sofrer gols`, que a
fonte traz pra parte deles. O texto anterior ("a fonte não traz jogos sem
sofrer gols") ficou falso com o dado novo e foi corrigido; a ressalva
agora cobre só o que de fato falta (defesas, gols sofridos).

**Interface:**
1. Cabeçalho só com rótulo + título ("Projeto Futebol • Celeiro de
   Ases" / "Mapeamento do Celeiro de Ases"), sem texto explicativo.
2. Cabeçalho (título + chips) fixo no topo com `position: sticky`; o
   `padding-top` soma `env(safe-area-inset-top)` e o fundo cobre a faixa
   do notch/barra de status. Trocar de país volta a lista pro topo.
3. **Contrato até** na bio (dd/mm/aaaa, traço quando vazio). Ele nunca
   tinha entrado na versão lista → ficha: a bio seguiu a lista do prompt
   anterior (idade, altura, pé, posição, camisa) e o campo, que existia
   na versão com mapa, se perdeu na reescrita. Bio passou a 3 colunas no
   desktop e 2 no mobile.
