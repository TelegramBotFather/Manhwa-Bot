from loguru import logger
import requests
from cloudscraper import create_scraper
from asyncio import to_thread
from json import JSONDecodeError

from requests.exceptions import HTTPError, ConnectionError, Timeout
from asyncio.exceptions import CancelledError
from typing import Optional


tor_proxies = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

class Scraper:
  __slots__ = ('scraper', 'headers', 'tor', 'session')

  def __init__(self, headers: Optional[dict] = None, tor: bool = False):
    self.scraper = create_scraper(browser='chrome')
    self.session = requests.Session()
    self.headers = headers or {}
    self.tor = tor

  def _internal_request(self, method: str, url: str, use_cs: bool, **kwargs):
      if 'headers' not in kwargs:
          kwargs['headers'] = self.headers

      if self.tor:
          kwargs['proxies'] = tor_proxies

      executor = self.scraper if use_cs else requests

      with executor.request(method, url, **kwargs) as r:
          r.raise_for_status()
          return r

  async def _make_request(self, method, url, rjson=False, cs=False, **kwargs):
      kwargs.setdefault("timeout", 80)
      try:
          response = await to_thread(self._internal_request, method, url, cs, **kwargs)

          if response and response.status_code == 200:
              return response.json() if rjson else response.text
          return None

      except (JSONDecodeError, CancelledError, HTTPError, ConnectionError, Timeout) as e:
          logger.error(f"{type(e).__name__}: {e} at {url}")
      except Exception as e:
          logger.exception(f"Unexpected Scraper Error: {e}")
      return None

  async def get(self, url, rjson=False, cs=False, **kwargs):
      return await self._make_request("GET", url, rjson, cs, **kwargs)

  async def post(self, url, rjson=False, cs=False, **kwargs):
      return await self._make_request("POST", url, rjson, cs, **kwargs)
