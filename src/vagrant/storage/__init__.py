"""Storage module for history and environments."""

from vagrant.storage.environments import Environment, EnvironmentManager
from vagrant.storage.history import HistoryEntry, HistoryStorage

__all__ = [
    "HistoryEntry",
    "HistoryStorage",
    "Environment",
    "EnvironmentManager",
]
