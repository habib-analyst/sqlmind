"""sqlmind: SQL-native agent memory with bounded differential consolidation."""

from .store import SqlMind, DEFAULT_K, DEFAULT_TAU, DEFAULT_MF, DEFAULT_MD

__version__ = "0.1.0"
__all__ = ["SqlMind", "DEFAULT_K", "DEFAULT_TAU", "DEFAULT_MF", "DEFAULT_MD"]
