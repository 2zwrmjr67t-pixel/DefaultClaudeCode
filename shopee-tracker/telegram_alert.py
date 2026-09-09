"""
Alerta via Telegram bot.

Setup rápido:
1. Fale com @BotFather no Telegram, crie um bot, copie o token.
2. Envie uma mensagem qualquer pro seu bot, depois acesse
   https://api.telegram.org/bot<TOKEN>/getUpdates para achar seu chat_id.
3. Coloque TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env
"""
import os
import requests


def send_alert(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[aviso] Telegram não configurado — alerta apenas no console:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    resp.raise_for_status()
