"""Small HTTP helper with retries. Failures stay visible."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 "
    "safe-time-evrp/0.1"
)


def fetch_bytes(url: str, *, timeout: float = 120, retries: int = 5) -> tuple[int, bytes]:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                return status, response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 404, 405, 410}:
                raise
            last_error = exc
            _sleep(attempt, b"")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            _sleep(attempt, b"")
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def fetch_json(
    url: str,
    *,
    accept: str = "application/json",
    timeout: float = 60,
    retries: int = 5,
) -> tuple[int, object]:
    last: tuple[int, object] = (0, {"error": "no attempt"})
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": accept},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                payload = json.loads(response.read().decode("utf-8"))
                return status, payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last = (exc.code, {"error": exc.reason, "body": detail})
            if exc.code not in {429, 500, 502, 503, 504}:
                return last
            _sleep(attempt, b"")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = (0, {"error": str(exc)})
            _sleep(attempt, b"")
    return last


def download_file(url: str, destination: Path, *, timeout: float = 300, retries: int = 5) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                temporary.open("wb") as handle,
            ):
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
            temporary.replace(destination)
            return
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            last_error = exc
            if temporary.exists():
                temporary.unlink()
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {403, 404, 410}:
                raise
            _sleep(attempt, b"")
    raise RuntimeError(f"download {url} failed after {retries} attempts: {last_error}")


def _sleep(attempt: int, _body: bytes) -> None:
    time.sleep(min(8, 2**attempt))
