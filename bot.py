import pyrogram
from time import time 
from loguru import logger

from pyrogram import idle
import random, os, shutil, asyncio

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import sys 

from config import *

remove_site_sf = ["cf"]

def load_fsb_vars(self):
  channel = Vars.FORCE_SUB_CHANNEL
  try:
    if "," in Vars.FORCE_SUB_CHANNEL:
      for channel_line in channel.split(","):
        self.FSB.append(
          (channel_line.split(":")[0], channel_line.split(":")[1])
        )
    else:
      self.FSB.append((channel.split(":")[0], channel.split(":")[1]))
  except Exception:
    logger.error(" FORCE_SUB_CHANNEL is not set correctly! ")
    self.FSB = []


class Manhwa_Bot(pyrogram.Client):
  def __init__(self):
    super().__init__(
      "ManhwaBot",
      api_id=Vars.API_ID,
      api_hash=Vars.API_HASH,
      bot_token=Vars.BOT_TOKEN,
      plugins=Vars.plugins,
      workers=50,
    )
    self.__version__ = pyrogram.__version__
    self.FSB = []

  async def start(self):
    await super().start()

    async def run_flask():
      cmds = ("gunicorn", "app:app")
      process = await asyncio.create_subprocess_exec(
        *cmds,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
      )
      stdout, stderr = await process.communicate()

      if process.returncode != 0:
        logger.error(f"Flask app failed to start: {stderr.decode()}")

      logger.info("Webs app started successfully")

    usr_bot_me = await self.get_me()

    if os.path.exists("restart_msg.txt"):
      with open("restart_msg.txt", "r") as f:
        chat_id, message_id = f.read().split(":")
        f.close()

      try: await self.edit_message_text(int(chat_id), int(message_id), "<code>Restarted Successfully</code>")
      except Exception as e: logger.exception(e)

      os.remove("restart_msg.txt")

    if os.path.exists("Process"):
      shutil.rmtree("Process")

    if Vars.FORCE_SUB_CHANNEL:
      load_fsb_vars(self)

    logger.info("""

    ██╗    ██╗██╗███████╗ █████╗ ██████╗ ██████╗     ██████╗  ██████╗ ████████╗███████╗
    ██║    ██║██║╚══███╔╝██╔══██╗██╔══██╗██╔══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝
    ██║ █╗ ██║██║  ███╔╝ ███████║██████╔╝██║  ██║    ██████╔╝██║   ██║   ██║   ███████╗
    ██║███╗██║██║ ███╔╝  ██╔══██║██╔══██╗██║  ██║    ██╔══██╗██║   ██║   ██║   ╚════██║
    ╚███╔███╔╝██║███████╗██║  ██║██║  ██║██████╔╝    ██████╔╝╚██████╔╝   ██║   ███████║
     ╚══╝╚══╝ ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝     ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝

    """)
    self.username = usr_bot_me.username
    logger.info("Make By https://t.me/Wizard_Bots ")
    logger.info(f"Manhwa Bot Started as {usr_bot_me.first_name} | @{usr_bot_me.username}")

    if Vars.WEBS_HOST:
      await run_flask()

    MSG = f"""<blockquote><b>🔥 SYSTEMS ONLINE. READY TO RUMBLE. 🔥

DC Mode: {usr_bot_me.dc_id}

Sleep mode deactivated. Neural cores at 100%. Feed me tasks, and watch magic happen. Let’s. Get. Dangerous.</b></blockquote>"""

    PICS = random.choice(Vars.PICS)

    button = InlineKeyboardMarkup([[
      InlineKeyboardButton('*Start Now*', url= f"https://t.me/{self.username}?start=start"),
      InlineKeyboardButton("*Channel*", url = "telegram.me/Wizard_Bots")
    ]])

    if isinstance(Vars.UPDATE_CHANNEL, int):
      try: await self.send_photo(Vars.UPDATE_CHANNEL, photo=PICS, caption=MSG, reply_markup=button)
      except Exception: pass


  async def stop(self):
    await super().stop()
    logger.info("Manhwa Bot Stopped")


Bot = Manhwa_Bot()
