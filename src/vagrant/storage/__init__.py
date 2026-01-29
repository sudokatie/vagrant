"""Storage module for history and environments."""

from vagrant.storage.history import HistoryEntry, HistoryStorage
from vagrant.storage.environments import Environment, EnvironmentManager

__all__ = [
    "HistoryEntry",
    "HistoryStorage",
    "Environment",
    "EnvironmentManager",
]
