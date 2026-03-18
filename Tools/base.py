import asyncio
import random
import shutil
import string
from typing import Dict, Optional, Tuple

from bot import logger, Vars
import string
from typing import Dict, Optional, Tuple

from bot import logger
from pyrogram.errors import FloodWait
from .db import database, get_episode_number
from .img2pdf import thumbnali_images
from bot import Bot
from os import path as ospath
import pyrogram.errors
from io import BytesIO

import time

#from collections import OrderedDict
from threading import Lock, Timer

from Tools.img2pdf import download_and_convert_images


def igrone_error(func, sync=False):
    async def wrapper(*args, **kwargs):
        try:
            if sync:
                return await asyncio.to_thread(func, *args, **kwargs)
            else:
                tasks = await asyncio.gather(*[func(*args, **kwargs)])
                return tasks[0]
        except Exception:
            return None

    return wrapper

def retry_on_flood(func):
    async def wrapper(*args, **kwargs):
        while True:
            try:
                return await func(*args, **kwargs)
            except FloodWait as e:
                await asyncio.sleep(int(e.value) + 3)
                logger.warning(f'FloodWait: waiting {e.value}s')
                await asyncio.sleep(e.value + 3)

            except (ValueError, pyrogram.errors.QueryIdInvalid, pyrogram.errors.MessageNotModified):
                raise


            except(pyrogram.errors.exceptions.bad_request_400.WebpageCurlFailed, pyrogram.errors.exceptions.bad_request_400.WebpageMediaEmpty, pyrogram.errors.exceptions.bad_request_400.PeerIdInvalid, pyrogram.errors.exceptions.bad_request_400.UsernameNotOccupied, pyrogram.errors.exceptions.bad_request_400.BadRequest, pyrogram.errors.exceptions.bad_request_400.MessageIdInvalid):
                raise

            except Exception as e:
                if "stat: path should be string, bytes, os.PathLike or integer, not NoneType" in str(e):
                    raise

                logger.exception(e)
                raise

    return wrapper



class MangaCard:
    __slots__ = ('url', 'title', 'poster', 'msg', 'chapters', 'webs', 'data')

    def __init__(
        self, 
        webs=None, url: str = "", 
        title: str = "", poster: str = "", 
        msg: str = "",  chapters: list = [], 
        data: dict = {}
    ):
        self.url = url
        self.title = title
        self.poster = poster
        self.msg = msg
        self.chapters = [] if chapters is None else chapters
        self.webs = webs
        self.data = {} if data is None else data

    def __repr__(self):
        return f"MangaCard({self.title})"

    def load_to_class(self, data: dict) -> 'MangaCard':
        slots = self.__slots__
        for key, val in data.items():
            if key in slots:
                setattr(self, key, val)
            else:
                self.data[key] = val
        return self


    def load_to_dict(self) -> dict:
        result = {}
        slots = self.__slots__

        for i in range(len(slots)):
            key = slots[i]
            if key == "data":
                result.update(self.data)
            else:
                result[key] = getattr(self, key)
        return result

    def update_dict(self, data: dict) -> None:
        slots = self.__slots__
        for key, val in data.items():
            if key in slots:
                setattr(self, key, val)
            else:
                self.data[key] = val

    @classmethod
    def from_dict(cls, data: dict) -> 'MangaCard':
        obj = cls.__new__(cls)

        obj.url = ""
        obj.title = ""
        obj.poster = ""
        obj.msg = ""
        obj.chapters = []
        obj.webs = None
        obj.data = {}

        obj.load_to_class(data)
        return obj


class Subscribes:
  """A class to manage user-specific subscriptions."""
  __slots__ = ('user_id', "manga_url", "webs", "lastest_chapter", "manga_title")

  def __init__(self, webs: str, manga_url: str, lastest_chapter: str, manga_title: str):
    self.manga_url: str = manga_url
    self.manga_title: str = manga_title
    self.webs: str = webs
    self.lastest_chapter: str = lastest_chapter

  def load_to_dict(self):
     return {"url": self.manga_url, "title": self.manga_title, "lastest_chapter": self.lastest_chapter}


def clean(txt, length=-1):
    remove_char = [
        "_", "&", ";", ":", "'", "|", "*", "?", ">", "<", "`", 
        "!", "@", "#", "$", "%", "^", "~", "+", "=", "/", 
        "\\", "\n",
    ]
    translator = txt.maketrans("", "", "".join(remove_char))
    txt = txt.translate(translator)

    txt = txt.replace("None", "")
    txt = txt.replace(".jpg", "")

    return txt[:length] if length != -1 else txt



def get_file_name(data: list, setting: dict = {}):
    regex = setting.get('regex', None)

    flen = setting.get('file_name_len', "30")
    try:
        flen = int(flen)
    except Exception:
        flen = 30

    if len(data) > 1:
        episode_number1 = str(get_episode_number(data[0].get("title", "None")))
        if not episode_number1 or (episode_number1 == "None"):
            episode_number1 = clean(data[0].get("title", "None"))
        else:
            episode_number1 = episode_number1.zfill(int(regex)) if regex else episode_number1

        episode_number2 = str(get_episode_number(data[-1].get("title", "None")))
        if not episode_number2 or (episode_number2 == "None"):
            episode_number2 = clean(data[-1].get("title", "None"))
        else:
            episode_number2 = episode_number2.zfill(int(regex)) if regex else episode_number2

        episode_number = f"{episode_number1} - {episode_number2}"
    else:
        episode_number = str(get_episode_number(data[0].get("title", "None")))
        if (episode_number == "None") or not episode_number:
            episode_number = clean(data[0].get("title", "None"))
        else:
            episode_number = episode_number.zfill(int(regex)) if regex else episode_number

    orginal_manga_title = data[0].get("manga_title", "")
    manga_title = clean(orginal_manga_title, flen)

    return orginal_manga_title, manga_title, episode_number


async def process_thumbnail_pdf(thumb_path):
    import os
    from PIL import Image, ImageOps

    if not thumb_path or not os.path.exists(thumb_path):
        return None

    try:
        img = await asyncio.to_thread(Image.open, thumb_path)
        img = await asyncio.to_thread(lambda: img.convert("RGB"))

        img = await asyncio.to_thread(lambda: ImageOps.contain(img, (320, 320), Image.LANCZOS))


        img = await asyncio.to_thread(lambda: ImageOps.pad(img, (320, 320), color=(0, 0, 0)))


        await asyncio.to_thread(img.save, thumb_path, "JPEG", quality=95)

    except Exception:
        pass

    return thumb_path

async def load_images_(u_id, p, b_url=None, p_fn=None):
    import base64
    import os

    s = {}
    us = await database.get_settings(u_id)

    md = f"Process/{u_id}"
    os.makedirs(md, exist_ok=True)

    prs = [
        ("banner1_file_path", us.get("banner1", None)), 
        ("banner2_file_path", us.get("banner2", None)), 
        ("thumb_file_name", us.get("thumb", None))
    ]

    def s64(b6, fp):
        try:
            if b6.startswith("data:"):
                b6 = b6.split(",", 1)[1]

            d = base64.b64decode(b6)
            with open(fp, "wb") as f:
                f.write(d)

            return fp
        except Exception:
            return None

    for k, v in prs:
        t = None
        fp = f"{md}/{k}.jpg"
        if ospath.exists(fp):
            t = fp
            s[k] = t

        elif v and v.startswith("http"):
            t = await igrone_error(thumbnali_images)(image_url=v, download_dir=md, file_name=k)
            t = await process_thumbnail_pdf(thumb_path=t)
            s[k] = t

        elif v and v.startswith("data:image"):
            t = s64(v, fp)
            s[k] = t

        elif v and (v.startswith("/9j") or v.startswith("iVBOR") or len(v) > 500):
            try:
                t = s64(v, fp)
                s[k] = t
            except Exception:
                t = await igrone_error(Bot.download_media)(v, file_name=fp)
                t = await process_thumbnail_pdf(thumb_path=t)
                s[k] = t

        elif v == "constant":
            t = await igrone_error(thumbnali_images)(image_url=p, download_dir=md, file_name=p_fn, base_url=b_url)
            t = await process_thumbnail_pdf(thumb_path=t)

            s[k] = t
        elif v:
            t = await igrone_error(Bot.download_media)(v, file_name=fp)
            t = await process_thumbnail_pdf(thumb_path=t)
            s[k] = t

    return s




class TaskCard:
    """ A class to manage user-specific tasks. """
    def __init__(
        self, webs, sts, picturesList, 
        user_id, chat_id, priority, 
        tasks_id=None, data_list: list = [],
        update_mode: bool = False,
        settings: dict = {}
    ):
        self.picturesList = picturesList or []
        self.poster: str = data_list[0].get("poster", "") # data

        self.webs = webs
        self.sts = sts
        self.setting = settings
        self.orginal_manga_title, self.manga_title, self.episode_number = get_file_name(data_list, self.setting)

        if len(data_list) == 1:
            self.url = data_list[0].get("url", "") # data
        else:
            self.url = f"{data_list[0].get('url', '')} - {data_list[-1].get('url', '')}"

        self.tasks_id = tasks_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.priority = priority
        self.update_mode = update_mode

    def run_process(self) -> None:
        if not self.tasks_id:
            return 
        if not self.webs:
            return 

        cs = getattr(self.webs, "cs", False)
        self.main_dir = f"Process/{self.tasks_id}"
        self.download_dir = f"{self.main_dir}/pictures"
        self.compressed_dir = f"{self.main_dir}/compress"

        self.processsing = asyncio.create_task(
            download_and_convert_images(
                self.picturesList, self.download_dir, 
                self.webs.url, cs=cs
            )
        )


    async def close(self) -> None:
        if self.processsing:
            self.processsing.cancel()

        shutil.rmtree(self.main_dir, ignore_errors=True)
        if self.sts:
            await igrone_error(self.sts.delete)()


    async def get_banner(self) -> dict:
        tasks = await asyncio.gather(
            load_images_(
                self.user_id, 
                self.poster, 
                self.webs.url, 
                self.manga_title
            )
        )
        return tasks[0]




class AQueue:
    __slots__ = ('storage_data', 'data_users', 'ongoing_tasks', 'maxsize')

    def __init__(self, maxsize: Optional[int] = None):
        self.storage_data: Dict[str, Tuple[TaskCard, bool]] = {}  # {task_id: TaskCard, True}
        #self.data_users: Dict[int, List[str]] = {}  # {user_id: [task_ids]}
        self.ongoing_tasks: Dict[str, TaskCard] = {} # {user_id: TaskCard}
        self.maxsize = maxsize

    async def get_random_id(self) -> str:
        """Generate unique 7-char task ID"""
        chars = string.ascii_letters + string.digits + "s"
        while True:
            task_id = ''.join(random.choices(chars, k=7))
            if task_id not in self.storage_data and task_id not in self.ongoing_tasks:
                return task_id

    async def put(self, tasks: TaskCard, updates: bool = False) -> str:
        """Add task to queue"""

        if self.maxsize and len(self.storage_data) >= self.maxsize:
            raise asyncio.QueueFull("Queue full")

        await database.ensure_user(tasks.user_id)
        tasks.tasks_id = await self.get_random_id()

        if not tasks.setting:
            tasks.setting = await database.get_settings(tasks.user_id)

        self.storage_data[tasks.tasks_id] = (tasks, updates)

        if Vars.IS_PRIVATE:
            tasks.run_process()

        return tasks.tasks_id

    def get_available_tasks(self, user_id=None):
        def extract_sort_value(item):
            if item is None:
                return (2, 0)  # Put None at end
            if isinstance(item, int):
                return (0, item)  # Type 0 for integers
            elif isinstance(item, str):
                s = str(item).lower()
                if s == 'none':
                    return (2, 0)  # Put 'None' at end
                elif '-' in s:
                    # For "10-11", take the first number
                    try:
                        num = int(s.split('-')[0])
                        return (1, num)  # Type 1 for hyphenated strings
                    except Exception:
                        return (3, s)  # Type 3 for other strings
                else:
                    # For other strings like "222", "333"
                    try:
                        num = int(s)
                        return (0, num)  # Same as integers
                    except Exception:
                        return (3, s)  # Can't convert, sort alphabetically
            else:
                return (3, str(item))  # Other types

        # Get all tasks
        all_tasks = []
        for task, is_completed in self.storage_data.values():
            if user_id is None or task.user_id == user_id:
                all_tasks.append((task, is_completed))

        # Filter out ongoing tasks
        available_tasks = [
            (task, is_completed) for task, is_completed in all_tasks
            if task.user_id not in self.ongoing_tasks
        ]

        # Sort by episode_number
        available_tasks.sort(key=lambda x: extract_sort_value(x[0].episode_number))

        return available_tasks[0] if available_tasks else None

    async def get(self, worker_id: int) -> Tuple[TaskCard, bool]:
        """Get next available task with better error handling"""
        while True:
            try:
                if not self.storage_data:
                    await asyncio.sleep(0.9)
                    continue

                available_task = self.get_available_tasks()

                if not available_task:
                    await asyncio.sleep(0.1)
                    continue

                self.ongoing_tasks[available_task[0].user_id] = available_task[0]
                del self.storage_data[str(available_task[0].tasks_id)]

                return available_task

            except Exception as e:
                logger.exception(f"Error in queue get: {e}")
                await asyncio.sleep(1)


    async def delete_task(self, task_id: str) -> bool:
        """Delete specific task"""
        if task_id in self.storage_data:
            if self.storage_data[task_id][1] is not True:
                task_card, _ = self.storage_data.pop(task_id)

                await igrone_error(task_card.close)()

                if task_id in self.ongoing_tasks:
                    del self.storage_data[task_id]

            return True

        return False

    async def delete_tasks(self, user_id: int) -> int:
        """Delete all tasks for user"""
        async def check_delete(str_, tuple_task_card):
            try:
                del self.storage_data[str_]
                task_card = tuple_task_card[0]

                await igrone_error(task_card.close)()

                return None
            except Exception as e:
                logger.exception(f"Error deleting task {str_}: {e}")
                return None

        process_ = [
            asyncio.wait_for(asyncio.create_task(check_delete(str_, tuple_task_card)),
                20
            )
            for str_, tuple_task_card in self.storage_data.items()
            if str(tuple_task_card[0].user_id) == str(user_id)
        ]

        await asyncio.gather(*process_, return_exceptions=True)

        return len(process_)

    def get_count(self, user_id: int = 0) -> int:
        """Get user's pending task count or total Users in queue"""
        try:
            if user_id == 0:
                # Count unique users with pending tasks
                unique_users = set()

                for task, is_completed in self.storage_data.values():
                    if task.user_id not in unique_users:
                        unique_users.add(int(task.user_id))


                for task, is_completed in self.storage_data.values():
                    if task.user_id not in unique_users:
                        unique_users.add(int(task.user_id))

                for task in self.ongoing_tasks.values():
                    if task.user_id not in unique_users:
                        unique_users.add(int(task.user_id))

                return len(unique_users)
            else:
                user_id_str = str(user_id)  # Convert to string if stored as string

                ongoing_tasks = sum(1 for task in self.ongoing_tasks.values() if str(task.user_id) == user_id_str)
                total_tasks = ongoing_tasks + sum(1 for task, completed in self.storage_data.values() if str(task.user_id) == user_id_str)
                return total_tasks



        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error counting tasks for user {user_id}: {e}")
            return 0

    def task_exists(self, task_id: str) -> bool:
        """Check if task exists"""
        return task_id in self.storage_data or task_id in self.ongoing_tasks

    def qsize(self) -> int:
        return len(self.storage_data)

    def empty(self) -> bool:
        return not self.storage_data

    async def task_done(self, tasks_card: TaskCard) -> bool:
        """Mark task as done"""
        if tasks_card.user_id in self.ongoing_tasks:
            del self.ongoing_tasks[tasks_card.user_id]
            if tasks_card.tasks_id in self.storage_data:
                 self.storage_data.pop(str(tasks_card.tasks_id))
            return True

        return False

    def get_ongoing_count(self, user_id: int) -> int:
        """Get user's ongoing task count"""
        return sum(1 for t in self.ongoing_tasks.values() if int(t.user_id) == user_id)


    def check_queue(self, user_id) -> bool:
        return any(int(task[0].user_id) == user_id for task in list(self.storage_data.values()))


queue = AQueue()


""" Make By AI """
class TTLCache:
    """
    A dictionary-like class that automatically removes entries after a specified time.

    Features:
    - Behaves like a regular dictionary (supports get, set, delete, membership tests)
    - Each entry has its own expiration time
    - Automatic cleanup of expired entries
    - Thread-safe operations
    """

    def __init__(self, default_timeout=60, cleanup_interval=30):
        """
        Initialize the TimedDict.

        Args:
            default_timeout (int): Default time in seconds after which entries expire
            cleanup_interval (int): How often to run cleanup in seconds (0 to disable)
        """
        self._dict = {}  # Main storage: key -> (value, expiry_time)
        self._default_timeout = default_timeout
        self._lock = Lock()

        # Start periodic cleanup if interval > 0
        self._cleanup_interval = cleanup_interval
        if cleanup_interval > 0:
            self._start_cleanup_timer()

    def _start_cleanup_timer(self):
        """Start the periodic cleanup timer."""
        self._cleanup_timer = Timer(self._cleanup_interval, self._cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup(self):
        """Remove all expired entries."""
        current_time = time.time()
        with self._lock:
            # Collect keys to delete
            keys_to_delete = [
                key for key, (_, expiry) in self._dict.items()
                if expiry <= current_time
            ]
            # Delete expired keys
            for key in keys_to_delete:
                del self._dict[key]

        # Restart timer if still needed
        if self._cleanup_interval > 0:
            self._start_cleanup_timer()

    def __getitem__(self, key):
        """Get value for key, raising KeyError if expired or not found."""
        with self._lock:
            if key not in self._dict:
                raise KeyError(key)

            value, expiry = self._dict[key]
            if time.time() > expiry:
                # Entry has expired
                del self._dict[key]
                raise KeyError(f"Key '{key}' has expired")

            return value

    def __setitem__(self, key, value):
        """Set value with default timeout."""
        self.set(key, value, self._default_timeout)

    def set(self, key, value, timeout=None):
        """
        Set a key with optional custom timeout.

        Args:
            key: The key to set
            value: The value to store
            timeout: Custom timeout in seconds (uses default_timeout if None)
        """
        expiry = time.time() + (timeout if timeout is not None else self._default_timeout)
        with self._lock:
            self._dict[key] = (value, expiry)

    def __delitem__(self, key):
        """Delete a key."""
        with self._lock:
            del self._dict[key]

    def __contains__(self, key):
        """Check if key exists and is not expired."""
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def get(self, key, default=None):
        """Get value with default if key doesn't exist or is expired."""
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def pop(self, key, default=None):
        """
        Remove and return value for key.
        Returns default if key doesn't exist or is expired.
        """
        try:
            value = self.__getitem__(key)
            with self._lock:
                del self._dict[key]
            return value
        except KeyError:
            return default

    def keys(self):
        """Return list of non-expired keys."""
        current_time = time.time()
        with self._lock:
            # First clean up expired entries
            keys_to_delete = [
                key for key, (_, expiry) in self._dict.items()
                if expiry <= current_time
            ]
            for key in keys_to_delete:
                del self._dict[key]

            return list(self._dict.keys())

    def values(self):
        """Return list of non-expired values."""
        current_time = time.time()
        with self._lock:
            values = []
            keys_to_delete = []

            for key, (value, expiry) in self._dict.items():
                if expiry > current_time:
                    values.append(value)
                else:
                    keys_to_delete.append(key)

            # Clean up expired entries
            for key in keys_to_delete:
                del self._dict[key]

            return values

    def items(self):
        """Return list of (key, value) pairs for non-expired entries."""
        current_time = time.time()
        with self._lock:
            items = []
            keys_to_delete = []

            for key, (value, expiry) in self._dict.items():
                if expiry > current_time:
                    items.append((key, value))
                else:
                    keys_to_delete.append(key)

            # Clean up expired entries
            for key in keys_to_delete:
                del self._dict[key]

            return items

    def __len__(self):
        """Return number of non-expired entries."""
        return len(self.keys())

    def __iter__(self):
        """Iterate over non-expired keys."""
        return iter(self.keys())

    def clear(self):
        """Remove all entries."""
        with self._lock:
            self._dict.clear()

    def update(self, other_dict):
        """Update with another dictionary, using default timeout."""
        with self._lock:
            for key, value in other_dict.items():
                self[key] = value

    def setdefault(self, key, default=None):
        """
        Get value if key exists, otherwise set to default and return default.
        """
        try:
            return self.__getitem__(key)
        except KeyError:
            self[key] = default
            return default

    def get_expiry_time(self, key):
        """
        Get expiry time for a key as timestamp.
        Returns None if key doesn't exist.
        """
        with self._lock:
            if key in self._dict:
                return self._dict[key][1]
            return None

    def refresh_key(self, key, timeout=None):
        """
        Reset the expiry time for an existing key.
        Returns True if successful, False if key doesn't exist.
        """
        with self._lock:
            if key in self._dict:
                value, _ = self._dict[key]
                expiry = time.time() + (timeout if timeout is not None else self._default_timeout)
                self._dict[key] = (value, expiry)
                return True
            return False

    def __repr__(self):
        """String representation."""
        items = self.items()
        return f"TimedDict({dict(items)})"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up."""
        self.clear()
        if hasattr(self, '_cleanup_timer'):
            self._cleanup_timer.cancel()