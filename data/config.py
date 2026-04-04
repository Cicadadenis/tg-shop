# - *- coding: utf- 8 - *-
import configparser
import os
import sys
import requests


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Дефолтная витрина бота: подпись и файл баннера (если в БД нет своего фото)
DEFAULT_SHOP_MENU_CAPTION = "ㅤㅤㅤㅤ🔥 ⛧ 𝕊𝔸𝕋𝔸𝕟𝔸 𝕊𝕙𝕠𝕡 ⛧ 🔥"
DEFAULT_MENU_BANNER_PATH = os.path.join(BASE_DIR, "assets", "default_menu_banner.png")


def get_default_menu_banner_path() -> str | None:
    if os.path.isfile(DEFAULT_MENU_BANNER_PATH):
        return DEFAULT_MENU_BANNER_PATH
    return None
ENV_PATH = os.path.join(BASE_DIR, ".env")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.ini")


def _tg_api_call(method: str, token: str, params: dict | None = None) -> tuple[bool, dict, str]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        response = requests.get(url, params=params, timeout=10)
        payload = response.json()
    except Exception as exc:
        return False, {}, f"Ошибка сети: {exc}"

    if payload.get("ok"):
        return True, payload.get("result", {}), ""

    return False, {}, payload.get("description", "Неизвестная ошибка Telegram API")


def _validate_bot_token(token: str) -> tuple[bool, str, dict]:
    if not token or ":" not in token:
        return False, "Неверный формат токена.", {}

    ok, result, error = _tg_api_call("getMe", token)
    if not ok:
        return False, f"Токен невалиден: {error}", {}

    return True, "", result


def _prompt_and_create_env(path: str = ENV_PATH) -> None:
    if os.path.exists(path):
        return

    if not sys.stdin or not sys.stdin.isatty():
        raise RuntimeError("Файл .env не найден, но нет интерактивного ввода для его создания.")

    print("Файл .env не найден. Запускаю настройку...")

    while True:
        token = input("Введите BOT_TOKEN: ").strip()
        valid, error, bot_info = _validate_bot_token(token)
        if valid:
            bot_name = bot_info.get("username") or bot_info.get("first_name") or "бот"
            print(f"Токен валиден ({bot_name}).")
            break
        print(error)

    admin_id = input("Введите ADMIN_ID: ").strip()

    with open(path, "w", encoding="utf-8") as env_file:
        env_file.write(f"BOT_TOKEN={token}\n")
        env_file.write(f"ADMIN_ID={admin_id}\n")

    os.environ["BOT_TOKEN"] = token
    os.environ["ADMIN_ID"] = admin_id
    print("Файл .env успешно создан.")




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


_prompt_and_create_env(ENV_PATH)
_load_dotenv_if_exists(ENV_PATH)

config = configparser.ConfigParser()
config.read(SETTINGS_PATH, encoding="utf-8")


def _settings_get(name: str, default: str = "") -> str:
    if config.has_section("settings"):
        return config["settings"].get(name, default)
    return default

BOT_TOKEN = os.getenv("BOT_TOKEN") or _settings_get("token", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Укажите его в .env")

adm = os.getenv("ADMIN_ID") or _settings_get("admin_id", "")
sms_api = _settings_get("sms", "0")
tt = adm
MethodGetMe = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

id_us = ""
first_name = ""
username = ""
try:
    response = requests.get(MethodGetMe, timeout=10)
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
start_command_description = _settings_get("start_command_description", "🏆ПОДАРИ ДУШЕ ДЖЕКПОТ🏆").strip()
if not start_command_description:
    start_command_description = "🏆ПОДАРИ ДУШЕ ДЖЕКПОТ🏆"
sozdatel = adm[0] if adm else ""