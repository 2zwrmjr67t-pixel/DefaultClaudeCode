# Shopee Price Tracker

Monitora preços na Shopee via Affiliate Open API — itens específicos
e grupos por palavra-chave (ex: "mesa sala industrial") — com painel
web hospedado (acessível de notebook ou celular, de qualquer lugar)
e alerta no Telegram quando o preço cai abaixo do alvo.

## Estrutura

- `watchlist.json` — lista do que monitorar (editável pelo painel)
- `panel.py` + `templates/index.html` — painel web para
  adicionar/editar/remover/ativar itens sem tocar em código
- `shopee_client.py` — autenticação e chamadas à API da Shopee
- `db.py` — histórico de preços em SQLite
- `main.py` — job que roda a coleta e dispara alertas
- `telegram_alert.py` — envio de notificação
- `Procfile` — comando de start em produção (gunicorn)
- `.github/workflows/daily.yml` — agendamento alternativo via GitHub
  Actions (ver nota abaixo — use Railway OU isso, não os dois)

## Setup local (testar antes de publicar)

1. `pip install -r requirements.txt`
2. Copie `.env.example` para `.env` e preencha:
   - Credenciais Shopee: cadastre-se em `affiliate.shopee.com.br`,
     ative "Open API" no painel (aprovação manual, leva alguns dias)
   - Credenciais Telegram: crie um bot com @BotFather
3. Rode o painel: `python panel.py` → abra `http://localhost:5000`
4. Teste a coleta manualmente: `python main.py`

## ⚠️ Antes de rodar em produção

**[Inferência]** O formato de assinatura HMAC em `shopee_client.py`
segue o padrão mais comum documentado publicamente para essa API,
mas não foi validado contra a API real. Antes de publicar:

1. Teste a autenticação no Explorer oficial:
   `https://open-api.affiliate.shopee.co.id/explorer/v2`
2. Compare o schema de `productOfferV2` com o retornado pelo
   Explorer — nomes de campos (`priceMin`, `ratingStar` etc.) podem
   precisar de ajuste
3. Erro de assinatura geralmente vem claro na resposta
   (`invalid signature`) — ajuste `_build_signature` conforme a doc

## Deploy na Railway (acesso de qualquer lugar, URL fixa)

Escolhida por oferecer **volume persistente** mesmo no plano
inicial — sem isso, watchlist e histórico se perderiam a cada
reinício do servidor.

1. Suba este projeto num repositório no GitHub
2. Em [railway.app](https://railway.app), crie um projeto → "Deploy from GitHub repo"
3. Em **Settings → Volumes**, crie um volume e monte em `/data`
4. Em **Variables**, adicione:
   - `DATA_DIR=/data`
   - `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - `PAINEL_SENHA=alguma-senha-sua` (protege o painel — sem isso,
     qualquer pessoa com a URL consegue editar sua watchlist)
5. A Railway detecta o `Procfile` e sobe o painel automaticamente
   numa URL tipo `shopee-tracker-production.up.railway.app`
6. Acesse a URL com `?senha=alguma-senha-sua` na primeira vez — um
   cookie guarda isso por 30 dias, não precisa repetir toda hora

### Agendar a coleta diária na própria Railway

1. No mesmo projeto, **+ New → Cron Job**
2. Comando: `python main.py`
3. Schedule: `0 12 * * *` (12:00 UTC ≈ 09:00 em Porto Alegre — ajustar
   no horário de verão)
4. Monte o **mesmo volume** (`/data`) e use as **mesmas variáveis**
   de ambiente do painel — assim os dois serviços leem/gravam o
   mesmo `watchlist.json` e `price_history.db`

Isso substitui o `.github/workflows/daily.yml` — mantenha só um dos
dois caminhos, senão você acaba com histórico de preço gravado em
dois lugares diferentes e desalinhados.

## Segurança

O painel fica numa URL pública. A senha simples (`PAINEL_SENHA`)
resolve pro uso pessoal, mas é proteção básica — não é um sistema de
login de verdade. Se em algum momento isso crescer ou envolver dados
mais sensíveis, vale trocar por autenticação real.

## Limitações conhecidas

- `productOfferV2` retorna dados básicos (título, imagem, preço) —
  não traz atributos estruturados (material, dimensões), então
  "estilo industrial" depende da qualidade do termo de busca
- SQLite num volume persistente funciona bem em escala pessoal; se
  crescer muito, migrar pra um banco hospedado (Postgres, por ex.)
