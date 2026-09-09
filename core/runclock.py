"""One monotonic clock per run, shared by every thread.

Main, the generator and the controllers each used to start their own clock,
so a release deadline, a green onset and the run duration were measured from
three different origins and could not be placed on one timeline.
"""
import time

_started_at = None


def start():
    """Fix the run origin. Called once, on the main thread, before any thread."""
    global _started_at
    _started_at = time.monotonic()


def elapsed():
    """Seconds since the origin, or None if the run has not started."""
    return None if _started_at is None else time.monotonic() - _started_at


def reset():
    global _started_at
    _started_at = None
