
from typing import Tuple
from .db import database
import re
from bot import DEFAULT_SETTINGS, Vars, Bot
from pyrogram.types import Chat, Message, InlineKeyboardButton, InlineKeyboardMarkup
from .base import TTLCache, retry_on_flood
from loguru import logger
import asyncio


from operator import methodcaller



channel_info_cache = TTLCache(
  default_timeout=7200,  # 2 hours
  cleanup_interval=60     # Clean every minute to free memory quickly
)
channel_msg_cache = TTLCache(
  default_timeout=400, 
  cleanup_interval=60
)

text_to_remove = [
  ".pdf", ".cbz", "chapter", "ch-", "ch", ":", "꞉", 
  "!", "⌯", "⇉", "$", "%", "^", "~", "+",
  "•", "~", "||", "-", ",", "manga", "manhwa",
  "manhua", "pornhwa", ":"
]

class ChannelInfoCache:
  __slots__ = ('id', "title", "channel_info", "clean_title")


  def __init__(
    self, channel_id: int, 
    channel_title: str, channel_info: Chat
  ):
    self.id = channel_id
    self.title = channel_title
    self.channel_info = channel_info
    self.clean_title = clean_text_(channel_title)


  async def _get_recent_messages(self, count: int, msg_id: int = 0) -> list:
    """Get recent messages from a channel efficiently"""
    if (msg_id == 0) and (self.channel_info.id in channel_msg_cache):
      msg_id = channel_msg_cache[self.channel_info.id]
      msg_id = int(msg_id)

    try:
      if msg_id == 0:
        await asyncio.sleep(2)
        test_msg = await retry_on_flood(Bot.send_message)(self.channel_info.id, "...")
        msg_id = test_msg.id

        await retry_on_flood(test_msg.delete)()

      logger.debug(f"Getting recent messages from channel {self.id} with msg_id {msg_id}")
      messages_ids = [i for i in range(msg_id-count, msg_id+count)]


      messages = await retry_on_flood(Bot.get_messages)(
        chat_id=self.channel_info.id, message_ids=messages_ids
      )

      if not isinstance(messages, list):
        messages = [messages]

      new_messages = [msg for msg in messages if getattr(msg, 'empty', None) is True]
      channel_msg_cache[self.channel_info.id] = new_messages[-1].id if new_messages else msg_id

      return new_messages

    except ValueError:
      return []


    except Exception as e:
      logger.exception(f"Failed to get recent messages: {e}")
      return []


async def get_channel_info(channel_id) -> ChannelInfoCache | None:
  try: 
    channel_id = int(channel_id)
  except Exception: 
    channel_id = channel_id

  if channel_id in channel_info_cache:
    return channel_info_cache[channel_id]

  try:
    channel_info = await retry_on_flood(Bot.get_chat)(channel_id)

    if not isinstance(channel_info, Chat):
      return None

    channel_class = ChannelInfoCache(
      channel_id=channel_id,
      channel_title=channel_info.title,
      channel_info=channel_info
    )
    channel_info_cache[channel_id] = channel_class

    return channel_class
  except Exception:
    return None



def clean_text_(text: str) -> str:
  """Clean and normalize text by removing mentions, brackets, and unwanted words"""
  text = text.lower()
  text = re.sub(r'@\w+|[\[\{\(].*?[\]\}\)]', '', text)

  if text_to_remove:
    text = str(text).strip()
    for word in text_to_remove:
      text = text.replace(word, '')

  return text.strip()


def convert_format(text):
  """
  Safer version that only converts valid URLs
  """
  replacement = {
    "||": "&#124;&#124;",
    "|": "&#124;",
  }
  for key, value in replacement.items():
    text = str(text).replace(key, value)

  lines = text.strip().split('\n')
  converted_lines = []

  skip_text = [
      "b", "i", "strong", "em", "u", "del", "strike", "spoiler",
      "emoji", "code", "pre", "blockquote", "tg-spoiler",
      "blockquote expandable", "||", "|", "/"
  ]

  url_pattern = r'https?://[^\s<>"\'\)]+'

  for line in lines:
    try:
      pattern = r'<([^>]+)>\s*(' + url_pattern + r')'
      match = re.search(pattern, line)

      if match:
          text_inside = match.group(1).strip()

          # Skip HTML formatting tags
          if text_inside.lower() in [tag.lower() for tag in skip_text]:
              converted_lines.append(line)
              continue

          link = match.group(2)

          if ' ' in text_inside or len(text_inside) > 20:
              new_line = re.sub(pattern, f"<a href='{link}'>{text_inside}</a>", line)
              converted_lines.append(new_line)
          else:
              converted_lines.append(line)
      else:
          converted_lines.append(line)

    except Exception:
      converted_lines.append(line)
      continue

  return '\n'.join(converted_lines)


def convert_button_format(text: str):
  return_button = []

  lines = str(text).strip().split('\n')
  for line in lines:
      line_button = []

      # Skip empty lines
      if not line.strip():
          continue

      if "|" in line:
          buttons = line.split("|")
          for button_part in buttons:
              button_part = button_part.strip()
              if "-" not in button_part:
                  continue

              parts = button_part.split("-", 1)
              if len(parts) != 2:
                  continue

              button_text = parts[0].strip()
              button_url = parts[1].strip()

              if button_text and button_url and button_url.startswith("http"):
                  line_button.append(InlineKeyboardButton(button_text, url=button_url))
      else:
          # Handle single button format
          if "-" in line:
              parts = line.split("-", 1)
              if len(parts) == 2:
                  button_text = parts[0].strip()
                  button_url = parts[1].strip()

                  if button_text and button_url and button_url.startswith("http"):
                      line_button.append(InlineKeyboardButton(button_text, url=button_url))

      if line_button:
          return_button.append(line_button)

  return InlineKeyboardMarkup(return_button) if return_button else None








def split_channel_name(channel_name: str):
  """Split channel name by various separators and clean each part"""
  separators = ["||", "|", "/"]

  for sep in separators:
      if sep in channel_name:
          parts = channel_name.split(sep)
          return [clean_text_(part.strip().lower()) for part in parts]

  return [clean_text_(channel_name.strip().lower())]










async def search_channel_photo(
  channel_info,
  last_id, 
  BATCH_SIZE: int = 100,
):
  pin = getattr(channel_info, 'pinned_message', None)
  if pin and getattr(pin, 'photo', None):
      return pin.photo.file_id

  try:
    last_id = int(last_id)
    if last_id < 1:
          return None
  except Exception:
      return None

  start = 0
  while start <= last_id:
      end = min(start + BATCH_SIZE - 1, last_id)

      try:
          msgs = await retry_on_flood(Bot.get_messages)(
            channel_info.id,
            [
              i for i in range(start, end + 1)
            ]
          )

          if isinstance(msgs, list):
              for m in msgs:
                  if m and m.photo:
                      return m.photo.file_id
          elif msgs and msgs.photo:
              return msgs.photo.file_id

      except Exception:
          pass

      start = end + 1

  return None


async def update_notify(
  post_info, user_id,
  manga_title, episode_number,
  channel_info: ChannelInfoCache
) -> None:
  user_id = str(user_id)
  uts = await database.get_settings(user_id)
  if not uts:
    return None

  update_channel = uts.get('update_c', None)
  update_text = uts.get('update_t', None)
  update_sticker = uts.get('update_s', None)
  update_button = uts.get('update_b', None)

  if not update_channel and Vars.IS_PRIVATE:
    update_channel = DEFAULT_SETTINGS.get('update_c', None)

  if not update_text and Vars.IS_PRIVATE:
    update_text = DEFAULT_SETTINGS.get('update_t', None)
    update_sticker = DEFAULT_SETTINGS.get('update_s', None)
    update_button = DEFAULT_SETTINGS.get('update_b', None)

  post_info = post_info[-1] if isinstance(post_info, list) else post_info

  if not update_channel or not update_text:
    await database.ensure_user(user_id)
    return

  try:
    replacements = {
      "{manga_title}": manga_title,
      "{chapter_num}": str(episode_number),
      "{channel_title}": channel_info.title,
      "{channel_link}": getattr(channel_info.channel_info, 'invite_link', ''),
      "{read_link}": getattr(post_info, 'link', ''),
    }

    for key, value in replacements.items():
      update_text = str(update_text).replace(key, value)

    if update_button:
      for key, value in replacements.items():
        update_button = str(update_button).replace(key, value)

    update_text = convert_format(update_text)
    update_button = convert_button_format(update_button)
  except Exception as er:
    logger.exception(f"Error converting update text: {er}")
    return 

  try:
    update_channel = int(update_channel)
  except Exception: 
    update_channel = update_channel

  try:
    message_list = await channel_info._get_recent_messages(10)

    for xcheck in message_list:
      try:
        if xcheck.text == update_text:
          return
        elif xcheck.caption == update_text:
          return
      except Exception:
        continue

  except Exception as e:
    logger.exception(f"Error checking messages: {e}")

  target_sticker = uts.get("target_s", None)

  await retry_on_flood(Bot.send_sticker)(channel_info.id, target_sticker) if target_sticker else None

  post_photo = await search_channel_photo(channel_info, post_info.id)
  if post_photo:
    await retry_on_flood(Bot.send_photo)(
      update_channel, post_photo,
      caption=update_text,
      reply_markup=update_button,
    )
  else:
    await retry_on_flood(Bot.send_message)(
      update_channel, update_text,
      reply_markup=update_button,
    )


  await retry_on_flood(Bot.send_sticker)(update_channel, update_sticker) if update_sticker else None






async def get_target_auto_channel(user_id: str = "") -> Tuple[list, list]:

  target_channel_ = []
  update_channel_ = []

  if Vars.IS_PRIVATE is True:
    async for user_info in database.get_users():
      target_channel_.extend(user_info.get('target_channels', []))
      update_channel_.extend(user_info.get('auto_channels', []))

  else:
    target_channel_ = await database.get_target_channel(user_id)
    update_channel_ = await database.get_auto_channel(user_id)

  if not isinstance(target_channel_, list):
    target_channel_ = [target_channel_]

  if not isinstance(update_channel_, list):
    update_channel_ = [update_channel_]

  return target_channel_, update_channel_





class Uploader:
  __slots__ = ()

  async def slot_channels(
    self, user_id: str = "",
    return_target: bool = False, 
    return_update: bool = False
  ) -> list | tuple:

    target_channel_, update_channel_ = await get_target_auto_channel(user_id)

    async def process_channels(channels):
        if not isinstance(channels, list):
            return []

        # Get channel info for all valid channels
        coros = [get_channel_info(c) for c in channels if c]
        results = await asyncio.gather(*coros)
        # Filter and sort
        filtered = [r for r in results if isinstance(r, ChannelInfoCache)]
        filtered.sort(key=lambda x: str(x.title))
        return filtered

    try:
      target_task_ = asyncio.create_task(process_channels(target_channel_))
      update_task_ = asyncio.create_task(process_channels(update_channel_))

      if return_target:
        update_task_.cancel()
        target_channel_ = await target_task_

        return target_channel_
      elif return_update:
        target_task_.cancel()
        update_channel_ = await update_task_

        return update_channel_
      else:
        target_channel_ = await target_task_
        update_channel_ = await update_task_

        return (target_channel_, update_channel_)
    except Exception as e:
      logger.exception(e)

      return [] if return_target else [] if return_update else ([], [])


  async def get_channels_by_pattern(
      self,
      pattern: str,
      user_id: str = "",
      case_sensitive: bool = False,
      return_target: bool = False,
      return_update: bool = False
  ) -> list[ChannelInfoCache]:

    """Get channels matching a regex pattern"""
    target_channel_, update_channel_ = await get_target_auto_channel(user_id)

    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)

    results_channels = []
    async def matches_pattern(channel_id: int) -> None:
      if not channel_id or not isinstance(channel_id, int):
        return None

      channel = await get_channel_info(channel_id)
      if not channel:
        return None

      search_title =  str(channel.title).lower()
      search_title = clean_text_(search_title)

      if bool(regex.search(search_title)) is True:
        results_channels.append(channel)


    process_channels = target_channel_ if return_target else update_channel_ 

    for i in range(0, len(process_channels), 30):
      channels_batch = process_channels[i:i+30]
      await asyncio.gather(*(matches_pattern(item) for item in channels_batch))
      await asyncio.sleep(1)

    return results_channels


  # Main Function ;- Call

  async def upload_to_targets_channels(
    self,
    docs: Message, original_ep_num: str,
    search_name: str, user_id: str
  ) -> None:

    user_id = str(user_id)
    search_term = str(search_name).lower().strip()
    search_term = clean_text_(search_term)


    target_channel, auto_channels = await get_target_auto_channel(user_id)

    target_channel = await self.get_channels_by_pattern(
      search_term, user_id, case_sensitive=True,
      return_target=True
    )

    if not target_channel:
      return

    if not isinstance(target_channel, list):
      return

    try:

      channel_info, post_info  = await self.check_update_need_or_not(
        target_channel_=target_channel, search_name=search_name, 
        doc_channel_id=docs.chat.id,
        doc_message_id=docs.id,
        file_name=docs.document.file_name,
        original_ep_num=original_ep_num,
      )

      if not post_info or not channel_info:
        return


      del target_channel

      if not isinstance(auto_channels, list):
        return

      if channel_info.id in auto_channels:
        await update_notify(
          post_info=post_info, user_id=user_id,
          manga_title=search_name, episode_number=original_ep_num,
          channel_info=channel_info
        )
        return

    except Exception as er:
      logger.exception(f"Error in upload_to_targets_channels: {er}")

  async def check_update_need_or_not(
    self,
    target_channel_: list[ChannelInfoCache],
    search_name: str, 
    doc_channel_id: int,
    doc_message_id: int, 
    file_name: str, 
    original_ep_num: str,
  ):
    """ """
    episode_str = str(original_ep_num) if original_ep_num else ""
    search_name = search_name.lower().strip()
    search_name = clean_text_(search_name)

    semaphore = asyncio.Semaphore(25)
    processed_channels = set()


    async def check_single(channel_class: ChannelInfoCache):
      """Check a single channel with minimal operations"""
      async with semaphore:
        if channel_class.id in processed_channels:
          return None

        processed_channels.add(channel_class.id)

        try:
          channel_full_name = split_channel_name(channel_class.title)

          if not isinstance(channel_full_name, list):
            channel_full_name = [channel_full_name]

          channel_full_name = [part for part in channel_full_name if part]

          logger.info(f"{channel_full_name} {search_name}")
          search_term = [search_name]
          if not any(term.lower() in name.lower() for name in channel_full_name for term in search_term):
            return None

          logger.debug(f"Found {search_term} in {channel_full_name}")

          messages = await channel_class._get_recent_messages(10)


          for msg in messages:
            if msg.document:
              doc_name = msg.document.file_name

              if doc_name == file_name:
                return None

              if episode_str and episode_str in doc_name:
                return None


          return channel_class

        except Exception:
          return None

    async def copy_to_matched(matched_channel: ChannelInfoCache):
      try:
        copied = await retry_on_flood(Bot.copy_media_group)(
           matched_channel.id,
           doc_channel_id,
           doc_message_id
         )
      except Exception:
          copied = await retry_on_flood(Bot.copy_message)(
            matched_channel.id,
            doc_channel_id,
            doc_message_id
          )

      return copied

    tasks = [asyncio.create_task(check_single(cid)) for cid in target_channel_]

    copied = None
    matched_channel = None

    for task in asyncio.as_completed(tasks):
      matched_channel = await task
      if matched_channel:
        copied = asyncio.create_task(copy_to_matched(matched_channel))

        for t in tasks:
          if not t.done():
            t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        copied = await copied
        break

    processed_channels.clear()

    return matched_channel, copied
