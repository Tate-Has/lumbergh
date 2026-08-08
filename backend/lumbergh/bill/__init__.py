"""Bill's instruction bundle: tracked here, materialized into his session workdir.

``AGENTS.md`` is re-rendered on every summon so Bill improves when Lumbergh upgrades;
``preferences.md``, ``briefs/``, and ``reports/`` are the user's and are only ever created.
"""

import re
from pathlib import Path

from lumbergh.constants import CONFIG_DIR

_SRC = Path(__file__).resolve().parent
DEFAULT_PERSONALITY = "professional"
CUSTOM_PERSONALITY = "custom"

# The slug rule ``AGENTS.md`` gives Bill for a task name, which is also a brief's filename.
# Lives beside TASK_KINDS so `lb` can refuse a bad slug without a round trip, and so the
# server's jail and the client's check can never disagree about what a slug is. A slug
# cannot traverse, which is what lets a remote caller name a brief without knowing — or
# being told — any path on the server.
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_HELP = "a slug is lowercase letters, digits and hyphens only, no slashes (e.g. flaky-login)"

# The two task shapes Bill can dispatch. Lives here, the lightest module on both
# sides of the protocol, so the `lb` CLI can validate `--kind` without a round trip
# and without importing the FastAPI router (and GitPython behind it) just for a set.
TASK_KINDS = frozenset({"ship", "scout"})


def home() -> Path:
    return CONFIG_DIR / "bill"


def preferences_path(home_dir: Path | None = None) -> Path:
    return (home_dir or home()) / "preferences.md"


def read_preferences(home_dir: Path | None = None) -> str:
    path = preferences_path(home_dir)
    return path.read_text() if path.is_file() else ""


def append_preference(
    date: str, text: str, reason: str, home_dir: Path | None = None
) -> tuple[Path, str]:
    """Add one dated bullet to ``preferences.md`` and return it with the file's path.

    Append-only, and deliberately so: the file is the user's, hand-edited, and a caller
    that could rewrite it could silently drop their standing opinions. Existing bytes are
    never touched — only a missing final newline is supplied, so a file that was saved
    without one doesn't get the new bullet glued onto its last line.

    A preference is one line by definition, so newlines inside ``text``/``reason`` collapse
    rather than splitting one preference into a bullet plus an orphan line.
    """
    path = preferences_path(home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text((_SRC / "preferences_seed.md").read_text())

    bullet = f"- {date}: {' '.join(text.split())} Reason: {' '.join(reason.split())}"
    existing = path.read_text()
    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(f"{existing}{separator}{bullet}\n")
    return path, bullet


def available_personalities() -> list[str]:
    """The preset personality keys shipped on disk (e.g. ``professional``, ``lumbergh``).

    Discovered from the ``personality_*.md`` files so adding a preset needs no code change
    here or in the settings validator that consumes this.
    """
    return sorted(p.stem.removeprefix("personality_") for p in _SRC.glob("personality_*.md"))


def _personality_body(personality: str, custom_text: str | None = None) -> str:
    if personality == CUSTOM_PERSONALITY:
        body = (custom_text or "").strip()
        if body:
            return body
        personality = DEFAULT_PERSONALITY
    path = _SRC / f"personality_{personality}.md"
    if not path.is_file():
        path = _SRC / f"personality_{DEFAULT_PERSONALITY}.md"
    return path.read_text().strip()


def render(personality: str = DEFAULT_PERSONALITY, custom_text: str | None = None) -> str:
    template = (_SRC / "AGENTS.md.template").read_text()
    return template.replace("{{PERSONALITY}}", _personality_body(personality, custom_text))


def materialize(
    personality: str = DEFAULT_PERSONALITY,
    custom_text: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    target = home_dir or home()
    target.mkdir(parents=True, exist_ok=True)
    (target / "briefs").mkdir(exist_ok=True)
    (target / "reports").mkdir(exist_ok=True)

    (target / "AGENTS.md").write_text(render(personality, custom_text))

    claude = target / "CLAUDE.md"
    if not claude.exists():
        claude.symlink_to("AGENTS.md")

    prefs = target / "preferences.md"
    if not prefs.exists():
        prefs.write_text((_SRC / "preferences_seed.md").read_text())

    return target
