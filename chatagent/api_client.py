# api_client.py - ApiClient class for LLM API communication
# -*- coding: utf-8 -*-

import json
import os
import random
import threading
import time
from collections import OrderedDict
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from abstractions import BaseApiClient


class ApiClient(BaseApiClient):
    """
    Concrete implementation of ``BaseApiClient`` for DeepSeek / OpenAI-compatible
    endpoints.

    Includes rate limiting (token bucket), LRU response caching, and
    automatic retry with exponential back-off.

    OOP features demonstrated:
      • Inheritance  : implements the ``BaseApiClient`` abstract interface
      • Encapsulation: threading locks hide concurrency details from callers
      • __str__      : shows endpoint, model, and current effective rate
      • __repr__     : programmer-facing format
    """

    def __init__(self, api_key: str, endpoint: str, model: str = "deepseek-chat",
                 rate_per_min: float = 8.0, burst: float = 2.0):
        self.api_key: str = api_key
        self.endpoint: str = endpoint.rstrip("/")
        self.model: str = model

        # Token bucket for rate limiting
        self._rate = float(rate_per_min)
        self._allowance = float(rate_per_min)
        self._burst = float(burst)
        self._last_time = time.time()
        self._rate_lock = threading.Lock()

        # LRU response cache
        self._cache: OrderedDict = OrderedDict()
        self._cache_cap = 64
        self._cache_lock = threading.Lock()

        # Shared HTTP session with retry
        self._session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.2,
                      status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["POST"])
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._session.mount("http://", HTTPAdapter(max_retries=retry))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the API endpoint appears reachable."""
        try:
            r = self._session.get(self.endpoint.replace("/v1", ""), timeout=5)
            return r.status_code < 500
        except Exception:
            return False

    def send_request(self, messages: List[dict],
                     temperature: float = 0.6,
                     max_tokens: int = 300,
                     timeout: int = 30) -> str:
        """
        Send a chat completion request to the LLM API.
        Returns the assistant's reply string, or an error string on failure.
        """
        try:
            cache_key = json.dumps(
                {"m": messages, "t": temperature, "mx": max_tokens},
                ensure_ascii=False, sort_keys=True
            )
            cached = self._cache_get(cache_key)
            if cached:
                return cached
        except Exception:
            cache_key = None

        self._throttle()

        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        attempts, max_attempts, backoff = 0, 4, 1.0
        while True:
            attempts += 1
            try:
                r = self._session.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"},
                    json=payload, timeout=timeout
                )
            except Exception as e:
                if attempts >= max_attempts:
                    return f"[ERR] {e}"
                time.sleep(backoff)
                backoff = min(backoff * 2, 8)
                continue

            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                wait_s = float(ra) if ra else (backoff + random.random())
                self._adapt_rate(0.7)
                if attempts >= max_attempts:
                    return "[ERR429] Rate limit exceeded"
                time.sleep(wait_s)
                continue

            if r.status_code == 200:
                try:
                    out = r.json()["choices"][0]["message"]["content"]
                except Exception:
                    out = "(parse error)"
                if cache_key:
                    self._cache_put(cache_key, out)
                return out

            if 500 <= r.status_code < 600:
                if attempts >= max_attempts:
                    return f"[ERR{r.status_code}] {r.text[:200]}"
                time.sleep(backoff)
                backoff = min(backoff * 2, 12)
                continue

            return f"[HTTP{r.status_code}] {r.text[:200]}"

    # ------------------------------------------------------------------
    # Token bucket helpers (thread-safe)
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Block briefly if the token bucket is empty."""
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_time
            self._last_time = now
            self._allowance = min(
                self._rate + self._burst,
                self._allowance + elapsed * (self._rate / 60.0)
            )
            if self._allowance >= 1:
                self._allowance -= 1
                return
            missing = 1 - self._allowance
            wait = missing / (self._rate / 60.0)
        time.sleep(min(max(wait, 0.05), 3.0))
        with self._rate_lock:
            self._allowance = max(0.0, self._allowance - 1)

    def _adapt_rate(self, factor: float) -> None:
        with self._rate_lock:
            self._rate = max(1.0, self._rate * factor)

    # ------------------------------------------------------------------
    # LRU cache helpers (thread-safe)
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Optional[str]:
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def _cache_put(self, key: str, val: str) -> None:
        with self._cache_lock:
            self._cache[key] = val
            self._cache.move_to_end(key)
            if len(self._cache) > self._cache_cap:
                self._cache.popitem(last=False)

    def __str__(self) -> str:
        """Human-readable summary: endpoint, model, and effective rate."""
        with self._rate_lock:
            rate = round(self._rate, 1)
        return (
            f"ApiClient(endpoint={self.endpoint!r}, model={self.model!r}, "
            f"rate={rate}/min)"
        )

    def __repr__(self) -> str:
        return f"ApiClient(endpoint={self.endpoint!r}, model={self.model!r})"
