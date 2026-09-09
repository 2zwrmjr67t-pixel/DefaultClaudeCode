# Shopee Price Tracker

Monitora preços na Shopee via Affiliate Open API — tanto itens
específicos quanto grupos por palavra-chave (ex: "mesa sala
industrial") — e alerta no Telegram quando o preço cai abaixo do alvo.

## Estrutura

- `watchlist.json` — lista do que monitorar (editável pelo painel)
- `panel.py` + `templates/index.html` — painel web local para
  adicionar/editar/remover/ativar itens sem tocar em código
- `shopee_client.py` — autenticação e chamadas à API da Shopee
- `db.py` — histórico de preços em SQLite (`price_history.db`)
- `main.py` — job que roda a coleta e dispara alertas
- `telegram_alert.py` — envio de notificação
- `.github/workflows/daily.yml` — agendamento diário via GitHub Actions

## Setup

1. `pip install -r requirements.txt`
2. Copie `.env.example` para `.env` e preencha:
   - Credenciais Shopee: cadastre-se em `affiliate.shopee.com.br`,
     ative "Open API" no painel (aprovação manual, leva alguns dias)
   - Credenciais Telegram: crie um bot com @BotFather
3. Rode o painel para montar sua watchlist: `python panel.py` →
   abra `http://localhost:5000`
4. Teste a coleta manualmente: `python main.py`

## ⚠️ Antes de rodar em produção

**[Inferência]** O formato de assinatura HMAC em `shopee_client.py`
segue o padrão mais comum documentado publicamente para essa API,
mas não foi validado contra a API real nesta sessão. Antes de usar
de verdade:

1. Teste a autenticação no Explorer oficial:
   `https://open-api.affiliate.shopee.co.id/explorer/v2`
2. Compare o schema de `productOfferV2` (nomes de campos, tipos de
   `sortType`/`listType`) com o retornado pelo Explorer — os nomes
   usados aqui (`priceMin`, `ratingStar` etc.) podem precisar de ajuste.
3. Se a assinatura falhar, o erro da API geralmente indica isso
   claramente (`invalid signature`) — ajuste `_build_signature`
   conforme a doc.

## Agendamento (GitHub Actions)

Depois que tudo estiver validado localmente:

1. Suba este repositório no GitHub
2. Em **Settings → Secrets → Actions**, adicione:
   `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. O workflow já está configurado pra rodar 1x/dia e commitar o
   histórico de volta no repo (`price_history.db`)
4. O `watchlist.json` também deve ser commitado — edite localmente
   pelo painel e dê `git push` quando quiser atualizar o que roda no
   agendamento

## Limitações conhecidas

- `productOfferV2` retorna dados básicos (título, imagem, preço) —
  não traz atributos estruturados (material, dimensões), então
  "estilo industrial" depende da qualidade do termo de busca
- Painel roda local, não é exposto publicamente — pensado para uso
  pessoal na sua máquina
- SQLite commitado no repo funciona bem em escala pessoal; se a
  watchlist crescer muito, migrar pra um banco hospedado
