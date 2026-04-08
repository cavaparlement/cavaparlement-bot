import os, requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = "@cavaparlement"

text = """📥 Arrivée · Sénat [TEST]
🔵 Mme DUPONT Julie ➡️ Collaborateur/trice de M. MARTIN Pierre
🏛️ Les Républicains (LR) · Alpes-Maritimes
📅 Depuis : 02/04/2026

#Senat #LR"""

url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
r = requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": text}, timeout=10)
print(r.status_code, r.json())
