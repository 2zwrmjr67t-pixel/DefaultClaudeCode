# Prompt para Claude Code — Ajustes de UI, Celeiro de Ases

> Ajuste sobre a versão já publicada. Não mexe em dado, só em interface. Cole na mesma sessão/repositório.

## O que ajustar

### 1. Título e subtítulo — cortar o resto do texto do cabeçalho
Manter só:
```
PROJETO FUTEBOL • CELEIRO DE ASES
Mapeamento do Celeiro de Ases
```
(primeira linha menor/rótulo, segunda linha como título principal). Remover qualquer texto explicativo adicional que esteja no cabeçalho hoje — só essas duas linhas.

### 2. Header fixo, lista rolável por baixo
O cabeçalho (título + chips de país) deve ficar **fixo no topo da tela** (`position: sticky` ou `fixed`, com o espaçamento correto pra não sobrepor conteúdo). Só a lista de jogadores rola por baixo dele. Isso vale principalmente pro mobile — hoje, ao rolar a lista, o contexto de país (chips) some da tela; queremos que ele continue visível o tempo todo, pra não perder a visão de qual país está sendo filtrado.

Atenção ao safe-area do iOS (notch/barra de status) — o header fixo precisa respeitar isso, não pode ficar colado ou cortado atrás da barra do sistema.

### 3. Contrato até — está faltando na ficha mobile
O campo **"Contrato até"** (coluna `Contrato_Ate` na aba `Jogadores`) não está aparecendo na bio da ficha do jogador na versão mobile — confirmar se sumiu só ali ou se nunca foi incluído nessa view, e adicionar junto aos outros campos de bio (idade, altura, pé, posição, camisa).

## O que não muda
Fluxo lista → ficha com botão de voltar, KPIs do resumo (jogos temporada atual, jogos últimos 3 anos com badge, valor de mercado), arquétipos na visão completa, mapa-múndi permanece descartado (chips são a solução definitiva).

Me mostre como ficou antes de publicar por cima da versão atual.
