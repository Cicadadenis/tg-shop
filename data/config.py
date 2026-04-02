# - *- coding: utf- 8 - *-
import configparser
import os
import requests





def _load_dotenv_if_exists(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


_load_dotenv_if_exists()

config = configparser.ConfigParser()
config.read("settings.ini")

BOT_TOKEN = os.getenv("BOT_TOKEN") or config["settings"].get("token", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Укажите его в .env")

adm = os.getenv("ADMIN_ID") or config["settings"].get("admin_id", "")
sms_api = config["settings"].get("sms", "0")
tt = adm
MethodGetMe = (f'''https://api.telegram.org/bot{BOT_TOKEN}/GetMe''')

id_us = ""
first_name = ""
username = ""
try:
    response = requests.post(MethodGetMe, timeout=10)
    tttm = response.json()

    id_us = tttm["result"]["id"]
    first_name = tttm["result"]["first_name"]
    username = tttm["result"]["username"]
except Exception:
    pass

if "," in adm:
    adm = adm.split(",")
else:
    if len(adm) >= 1:
        adm = [adm]
    else:
        adm = []
        print("***** Вы не указали админ ID *****")

bot_version = "2.9"
bot_description = f"<b>♻ Bot создал Cicada3301</b>\n" \
                  f"<b>⚜ Bot Version:</b> {bot_version}\n" \
                  f"<b>🔗Для выдачи доступов на сутки</b>\n"\
                  f"<b>🎫В случае их нехватки писать ▶️:</b> <a href='https://t.me/satanasat'><b>Cicada</b></a>"
sozdatel = adm[0] if adm else ""