# - *- coding: utf- 8 - *-
#
import os
import requests
import click
import pyperclip
from aiogram import types
from aiogram import Dispatcher, executor

from aiogram import Bot, Dispatcher, types
from data.config import BOT_TOKEN


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

URL_TRANSFERSH = 'https://transfer.sh'

@dp.message_handler(content_types=["document"])
async def download_documents(message: types.Message):
   dow = (f"{message.document.file_name}")
   await message.document.download(destination=dow)
   with open("./den/F2J2297415.pdf, 'rb'") as data:
      click.echo('Загрузка файла')
      r = requests.post(URL_TRANSFERSH, files=data)
      download_url = r.text[20:]
      click.echo(f'Скачать отсюда: https://transfer.sh/get/{download_url}')
      pyperclip.copy(download_url)





if __name__ == "__main__":
    executor.start(dp)