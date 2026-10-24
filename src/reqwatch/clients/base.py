"""Shared HTTP behaviour for all ATS clients.

Rules (Phase 0 verification): public unauthenticated endpoints only,
descriptive User-Agent, self-throttle, exponential backoff + jitter on
429/5xx, respect Retry-After. No logins, no CAPTCHA handling, postings only.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

import httpx

DEFAULT_UA = "Reqwatch/1.0 (job-market research; portfolio project)"


@dataclass
class RawPosting:
    source_posting_id: str
    title: str
    location: str | None
    department: str | None
    description_raw: str  # HTML or plain text as served; cleaned before storage, never stored raw


@dataclass
class BoardFetch:
    postings: list[RawPosting]
    schema_hash: str
    field_names: list[str]
    http_status: int


class BoardError(Exception):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def get_with_backoff(url: str, *, user_agent: str = DEFAULT_UA, max_attempts: int = 4,
                     base_delay: float = 1.0, timeout: float = 30.0,
                     transport: httpx.BaseTransport | None = None) -> httpx.Response:
    """GET with backoff+jitter. Raises BoardError after max_attempts or on 4xx (except 429)."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with httpx.Client(headers={"User-Agent": user_agent}, timeout=timeout, transport=transport) as client:
                resp = client.get(url)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after and retry_after.isdigit()) else \
                    base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                last_exc = BoardError(f"HTTP {resp.status_code} for {url}", resp.status_code)
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                continue
            raise BoardError(f"HTTP {resp.status_code} for {url}", resp.status_code)
        except httpx.HTTPError as exc:  # network error: retryable
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.5))
    raise BoardError(f"Failed after {max_attempts} attempts: {url} ({last_exc})",
                     getattr(last_exc, "http_status", None))
