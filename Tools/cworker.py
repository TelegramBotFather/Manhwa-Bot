
from pyrogram.errors import FileReferenceEmpty, FileReferenceExpired, FileReferenceInvalid, UsernameInvalid

from TG.storage import retry_on_flood, igrone_error, queue
from bot import Bot, Vars, logger


from Tools.img2cbz import images_to_cbz
from Tools.img2pdf import ( 
    download_and_convert_images, convert_images_to_pdf,
    ImageDownloadError

)

import os
import shutil
import asyncio

from time import time
from pyrogram.types import InputMediaDocument

from Tools.base import TaskCard, database
from .uploaders import get_target_auto_channel, Uploader


LOGS_MESSAGE = """
{caption}

{url}

`Downloaded By`: `{user_id}`  [{mention}]
`PDF Password`: `{password}`
`Time Taken`: `{time_taken}`"""




class NormalError(BaseException):
  def __init__(self):
    pass


async def send_error(task_card: TaskCard, error_text):
  if task_card.sts:
    docs = await retry_on_flood(task_card.sts.edit)(
      f"{task_card.url} : `{error_text}`"
    )
  else:
    docs = await retry_on_flood(Bot.send_message)(
      int(task_card.user_id), f"{task_card.url} : `{error_text}`"
    )

  await retry_on_flood(docs.copy)(Vars.LOG_CHANNEL) if Vars.LOG_CHANNEL else None



def create_file_async(process):
  """Async wrapper for File creation"""
  async def wrapper(*args, **kwargs):
    return await asyncio.to_thread(process, *args, **kwargs)

  return wrapper



def clean_system(tasks_card: TaskCard, thumb: str| None, values: list):
    """Clean up files and directories based on task settings."""

    def safe_remove(path):
        """Safely remove file or directory."""
        if not path:
            return

        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    if tasks_card.setting.get("thumb") == "constant":
        safe_remove(thumb)

    if queue.check_queue(tasks_card.user_id) is False:
      process_dir = f"Process/{tasks_card.user_id}"
      shutil.rmtree(process_dir, ignore_errors=True)


    for value in values:
        safe_remove(value)



async def copy_media(channel_id, doc, caption):
  try:
    await retry_on_flood(Bot.copy_media_group)(
      channel_id, doc[-1].chat.id,
      doc[-1].id, captions=caption,
    )
  except Exception:

    try:
      await retry_on_flood(Bot.copy_message)(
        channel_id, doc[-1].chat.id,
        doc[-1].id, caption=caption
      )
    except UsernameInvalid:
      pass
    except Exception as e:
      logger.exception(f"Error copying media: {e}")



async def send_manga_chapter(
  tasks_card: TaskCard,
):
  #tasks_card.update_mode = True
  start_time = time()
  error_msg = None

  download_dir = None
  compressed_dir = None

  pdf_output_path = None
  cbz_output_path = None

  password = None
  banner_setting = await tasks_card.get_banner()
  thumb = banner_setting.get("thumb_file_name", None)
  banner1 = banner_setting.get("banner1_file_path", None)
  banner2 = banner_setting.get("banner2_file_path", None)

  media_docs = []

  if not tasks_card.picturesList:
    await igrone_error(send_error)(tasks_card, "Error at Getting Picture")
    raise NormalError()

  if getattr(tasks_card, "processsing", None) is None:
    tasks_card.run_process()

  main_dir = tasks_card.main_dir
  download_dir = tasks_card.download_dir
  compressed_dir = tasks_card.compressed_dir

  main_dir = f"Process/{tasks_card.tasks_id}"
  download_dir = f"{main_dir}/pictures"
  compressed_dir = f"{main_dir}/compress"


  try:
    file_name = tasks_card.setting.get('file_name', None)
    if not file_name:
      file_name = "Chapter {episode_number} {manga_title}"

    if tasks_card.webs.sf == "mf" and "Vol" in tasks_card.manga_title or "Volume" in tasks_card.manga_title:
      file_name = file_name.replace("Chapter", "Vol")

    caption = tasks_card.setting.get('caption', "<blockquote>{file_name}</blockquote>")
    if not caption:
      caption = "<blockquote>{file_name}</blockquote>"

    replacements = {
      "{file_name}": file_name,
      "{episode_number}": str(tasks_card.episode_number),
      "{chapter_num}": str(tasks_card.episode_number),
      "{manga_title}": tasks_card.manga_title,
    }

    for key, value in replacements.items():
      file_name = file_name.replace(key, value)

    for key, value in replacements.items():
      caption = caption.replace(key, value)

    downloads_list = await tasks_card.processsing


    await igrone_error(tasks_card.sts.edit)("<code>Converting.....</code>") if tasks_card.sts else None

    file_type = tasks_card.setting.get('type', ['PDF'])
    if not file_type:
      file_type = ['PDF']


    processing_tasks = []
    if "PDF" in file_type:
      pdf_output_path = f"{main_dir}/{file_name}.pdf"

      password = tasks_card.setting.get('password', None)
      try:
        compress = int(tasks_card.setting.get("compress", "80"))
      except Exception:
        try:
          compress = int(await database.get_value(str(tasks_card.user_id), "compress"))
        except Exception:
          compress = 80

      if not compress:
        compress = 80

      hyperLink = tasks_card.setting.get("hyper", None)

      ## from here
      processing_tasks.append(create_file_async(convert_images_to_pdf)(
        downloads_list, pdf_output_path,
        compressed_dir, password, compress, hyperLink,
        banner1, banner2
      ))


    if "CBZ" in file_type:
      cbz_output_path = f"{main_dir}/{file_name}.cbz"
      processing_tasks.append(create_file_async(images_to_cbz)(
        downloads_list, cbz_output_path
      ))


    processing_tasks = await asyncio.gather(*processing_tasks)
    for task in processing_tasks:
      if task is not None:
        await igrone_error(send_error)(tasks_card, str(task))
        raise NormalError()


    if pdf_output_path:
      media_docs.append(InputMediaDocument(pdf_output_path, caption=caption, thumb=thumb))

    if cbz_output_path:
      media_docs.append(InputMediaDocument(cbz_output_path, caption=caption, thumb=thumb))

    await igrone_error(tasks_card.sts.edit)("<code>Uploading.....</code>") if tasks_card.sts else None

    if len(media_docs) < 0:
      await igrone_error(send_error)(tasks_card, "<i> Not Any File Type Found </i>")
      raise NormalError()


    doc = await retry_on_flood(Bot.send_media_group)(int(tasks_card.chat_id), media_docs)

    await igrone_error(tasks_card.sts.edit)("<code>Uploading to targets.....</code>") if tasks_card.sts else None


    await Uploader().upload_to_targets_channels(
      doc[-1], original_ep_num=str(tasks_card.episode_number),
      search_name=tasks_card.orginal_manga_title, user_id=str(tasks_card.user_id),
    )

    dump = tasks_card.setting.get('dump', None)
    try:
      dump = int(dump)
    except Exception: 
      dump = dump

    if Vars.CONSTANT_DUMP_CHANNEL:
        await copy_media(Vars.CONSTANT_DUMP_CHANNEL, doc, caption)

    if dump:
        await copy_media(dump, doc, caption)

    if Vars.LOG_CHANNEL:
      time_taken = time() - start_time
      minutes, seconds = divmod(int(time_taken), 60)
      time_taken = f"{minutes}m, {seconds}s"

      user = await igrone_error(Bot.get_users)(int(tasks_card.user_id))

      log_caption = LOGS_MESSAGE.format(
        caption=caption,
        url=tasks_card.url,
        user_id=tasks_card.user_id,
        mention=user.mention() if user else "[None]",
        password=password,
        time_taken=time_taken
      )
      caption = ["", log_caption] if len(doc) > 1 else log_caption
      await copy_media(Vars.LOG_CHANNEL, doc, caption)

  except NormalError:
    error_msg = True
    pass

  except ImageDownloadError:
    error_msg = True
    await igrone_error(send_error)(tasks_card, f"Error at Downloading Picture at {tasks_card.url}")
    if tasks_card.sts:
      await retry_on_flood(tasks_card.sts.edit_text)(f"<code>Error at Downloading Picture</code> : {tasks_card.url} ")
    else:
      await retry_on_flood(Bot.send_message)(int(tasks_card.user_id), f"<code>Error at Downloading Picture</code> : {tasks_card.url} ")
  except (FileReferenceExpired, FileReferenceEmpty, FileReferenceInvalid):
    error_msg = True
    if tasks_card.sts:
      await retry_on_flood(tasks_card.sts.edit_text)("<b><i>Change Your Thumb or Banner and Try Again... </i></b> ")
    else:
      await retry_on_flood(Bot.send_message)(int(tasks_card.user_id), "<b><i>Change Your Thumb or Banner and Try Again... </i></b> ")

  except Exception as e:
    error_msg = True
    await igrone_error(send_error)(
      tasks_card, str(e)
    )

    logger.exception(f"Error processing task: {e}")

  finally:
    clean_system(
      tasks_card, thumb, 
      [

        pdf_output_path, cbz_output_path, 
        download_dir, compressed_dir, main_dir
      ]
    )

    if not error_msg:
      await igrone_error(tasks_card.sts.delete)() if tasks_card.sts else None



async def worker(worker_id: int = 1):
  while True:
    tasks_card, _ = await queue.get(worker_id)
    logger.info(f"Worker {worker_id} processing task {tasks_card.tasks_id}")
    await retry_on_flood(tasks_card.sts.edit)("<code>Processing.....</code>") if tasks_card.sts else None
    try:
      if tasks_card.picturesList:
        try: 
          await send_manga_chapter(tasks_card)
        except Exception as error:
          logger.exception(f"Worker {worker_id} encountered an error: {error}")
          await send_error(tasks_card, error)
      else:
        await igrone_error(send_error)(
          tasks_card, "Error at Getting Picture",
        )

    except Exception as err:
      logger.exception(f"Worker {worker_id} encountered an error: {err}")
    finally:
      await queue.task_done(tasks_card)