"""On-disk cache for raw source responses, honoring the source's refresh cadence.

CelesTrak regenerates GP data about every 2 hours and asks clients not to poll faster than that.
Every raw response is saved with its fetch timestamp; a request within the TTL is served from disk.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CachedResponse:
    payload: Any
    fetched_at: datetime
    from_cache: bool


class ResponseCache:
    def __init__(self, cache_dir: Path, ttl: timedelta) -> None:
        self.cache_dir = cache_dir
        self.ttl = ttl

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', key)}.json"

    def get_or_fetch(
        self,
        key: str,
        fetch: Callable[[], Any],
        *,
        now: datetime | None = None,
    ) -> CachedResponse:
        now = now or datetime.now(UTC)
        path = self._path(key)
        if path.exists():
            entry = json.loads(path.read_text())
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
            if now - fetched_at < self.ttl:
                return CachedResponse(entry["payload"], fetched_at, from_cache=True)
        payload = fetch()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": now.isoformat(), "payload": payload}))
        return CachedResponse(payload, now, from_cache=False)
