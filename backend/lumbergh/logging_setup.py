"""Where the application's own log lines go.

Nothing configured logging, so `lumbergh.*` loggers inherited a root logger with
no handler: everything below WARNING was dropped on the floor. State transitions,
the reason a session looked stuck, the exception a background task swallowed —
none of it was reachable without editing the source.

`LUMBERGH_LOG_LEVEL=debug` turns on the per-poll detail; the default stays quiet
enough to leave on forever.
"""

import logging
import os
import sys

APP_LOGGER = "lumbergh"
LEVEL_ENV_VAR = "LUMBERGH_LOG_LEVEL"
DEFAULT_LEVEL = logging.INFO


def resolve_level(name: str | None) -> int:
    """A level name to a level, falling back to INFO.

    A typo in an environment variable must not take the server down, and it must
    not silently mean "log nothing" either.
    """
    if not name or not name.strip():
        return DEFAULT_LEVEL
    level = logging.getLevelNamesMapping().get(name.strip().upper())
    return level if isinstance(level, int) else DEFAULT_LEVEL


def configure_logging(level_name: str | None = None) -> int:
    """Give the app's loggers a handler. Returns the level applied.

    Only the ``lumbergh`` namespace is touched — uvicorn configures its own
    loggers, and stamping over those changes how the server reports itself.
    """
    level = resolve_level(level_name if level_name is not None else os.environ.get(LEVEL_ENV_VAR))
    logger = logging.getLogger(APP_LOGGER)
    logger.setLevel(level)
    # Propagation stays on: our handler is what prints, and cutting the chain also
    # cuts every downstream listener — pytest's caplog among them. Nothing reaches
    # the root's last-resort handler while a handler here has already taken it.

    for handler in logger.handlers:
        handler.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
    return level
