"""Celery background tasks.

Re-exports `poll_system_stats` and `get_danger_data` so Celery's beat
schedule (`src.tasks.poll_system_stats` in main.py) and the few callers
that did `from src.tasks import ...` keep resolving without edits.
"""

from src.tasks.intel_tasks import get_danger_data, poll_system_stats

__all__ = ["get_danger_data", "poll_system_stats"]
