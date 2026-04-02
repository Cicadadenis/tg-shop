# - *- coding: utf- 8 - *-
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


cicada = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔗 Зашифр. Ссылку', callback_data='uurl')],
        [InlineKeyboardButton(text='☑️ Пробив по IP', callback_data='ip')],
        [InlineKeyboardButton(text='🔐 Генератор паролей', callback_data='gen_pass')],
        [InlineKeyboardButton(text='🧰 Генератор ников', callback_data='gen_nick')],
        [InlineKeyboardButton(text='🔝 user!! agent!!', callback_data='gen_agent')],
        [InlineKeyboardButton(text='🌐 Генератор прокси', callback_data='gen_proxy')],
    ]
)

uss = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='1️⃣  ANDROID ✅', callback_data='uss_android')],
        [InlineKeyboardButton(text='2️⃣  IOS ✅', callback_data='uss_ios')],
        [InlineKeyboardButton(text='3️⃣   Linux  ✅', callback_data='uss_linux')],
        [InlineKeyboardButton(text='4️⃣    windows   ✅', callback_data='uss_windows')],
    ]
)

soglasie = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='✅ Да', callback_data='dada'),
            InlineKeyboardButton(text='❌ Нет', callback_data='nene'),
        ]
    ]
)
soglasie2 = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='✅ Да', callback_data='dada2'),
            InlineKeyboardButton(text='❌ Нет', callback_data='nene2'),
        ]
    ]
)

gen_ent = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🧬 Сгенерировать', callback_data='gen_agnt')],
        [InlineKeyboardButton(text='⚙️ Параметры', callback_data='settings_pass')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='back_gen')],
    ]
)
gen_pass = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🧬 Сгенерировать', callback_data='generate_pass')],
        [InlineKeyboardButton(text='⚙️ Параметры', callback_data='settings_pass')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='back_gen')],
    ]
)

gen_pro = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔄 Сгенерировать', callback_data='generate_proxy')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='back_gen')],
    ]
)

cicada3301 = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text='🏞 Получить id фото:', callback_data='id_foto')]]
)

podmena2 = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text='Подробнее', callback_data='pd2')]]
)
podmena = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Тарифы', callback_data='tarif')],
        [InlineKeyboardButton(text='Видео', callback_data='vid')],
        [InlineKeyboardButton(text='Проверим ?', callback_data='proverit')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='tttt')],
    ]
)

tariff = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Базовый', callback_data='bazovii')],
        [InlineKeyboardButton(text='Расширенный', callback_data='rashir')],
        [InlineKeyboardButton(text='VIP', callback_data='vip')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='tttt')],
    ]
)

tar_baza_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Купить', callback_data='baz_chench'),
            InlineKeyboardButton(text='◀️ Назад', callback_data='pd2'),
        ]
    ]
)

tar_rash_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Купить', callback_data='rash_chench'),
            InlineKeyboardButton(text='◀️ Назад', callback_data='pd2'),
        ]
    ]
)

tar_vip_back = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Купить', callback_data='vip_chench'),
            InlineKeyboardButton(text='◀️ Назад', callback_data='pd2'),
        ]
    ]
)
oplata = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='оплатил', callback_data='opt'),
            InlineKeyboardButton(text='◀️ Назад', callback_data='tttt'),
        ]
    ]
)