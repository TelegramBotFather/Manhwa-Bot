import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
uvloop.install()

from Tools.auto import get_updates_manga, logger
from Tools.my_token import expired_token_
from Tools.db import database
import os, shutil
from Tools.cworker import worker
from bot import Bot, Vars



folder_path = "Process"
if os.path.exists(folder_path) and os.path.isdir(folder_path):
  shutil.rmtree(folder_path)


async def main_exp_():
  sleep_timeout = 1 # mins
  while True:
    try:
      await get_updates_manga()
      if Vars.SHORTENER:
        await database.remove_expired_users()
        expired_token_()
    except Exception as err:
      logger.exception(f"Error in main_exp_: {err}")
    finally:
      await asyncio.sleep(sleep_timeout * 60)

async def worker_tasks():
  tasks = [
    asyncio.create_task(worker(i))
    for i in range(10)
  ]
  tasks.append(asyncio.create_task(main_exp_()))
  await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
  loop = asyncio.get_event_loop()
  loop.create_task(worker_tasks())
  Bot.run()

