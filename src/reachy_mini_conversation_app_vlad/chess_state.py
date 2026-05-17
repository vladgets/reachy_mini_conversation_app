"""Shared in-process store for chess analysis pushed by the browser extension."""

import threading

_lock: threading.Lock = threading.Lock()
_state: dict = {}


def update(data: dict) -> None:
    with _lock:
        _state.clear()
        _state.update(data)


def get() -> dict:
    with _lock:
        return dict(_state)
