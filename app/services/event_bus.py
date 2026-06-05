import logging
from typing import Callable

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[Callable]] = {}


def subscribe(event_name: str, callback: Callable):
    if event_name not in _subscribers:
        _subscribers[event_name] = []
    _subscribers[event_name].append(callback)


def unsubscribe(event_name: str, callback: Callable):
    if event_name in _subscribers:
        _subscribers[event_name] = [cb for cb in _subscribers[event_name] if cb != callback]


def emit(event_name: str, data: dict | None = None):
    if event_name not in _subscribers:
        return
    for callback in _subscribers[event_name]:
        try:
            callback(event_name, data or {})
        except Exception as e:
            logger.error(f"Event handler error for '{event_name}': {e}")


def clear_all():
    _subscribers.clear()
