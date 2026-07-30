"""Bill's instruction bundle: tracked here, materialized into his session workdir.

``AGENTS.md`` is re-rendered on every summon so Bill improves when Lumbergh upgrades;
``preferences.md``, ``briefs/``, and ``reports/`` are the user's and are only ever created.
"""

from pathlib import Path

from lumbergh.constants import CONFIG_DIR

_SRC = Path(__file__).resolve().parent
DEFAULT_PERSONALITY = "professional"
CUSTOM_PERSONALITY = "custom"

# The two task shapes Bill can dispatch. Lives here, the lightest module on both
# sides of the protocol, so the `lb` CLI can validate `--kind` without a round trip
# and without importing the FastAPI router (and GitPython behind it) just for a set.
TASK_KINDS = frozenset({"ship", "scout"})


def home() -> Path:
    return CONFIG_DIR / "bill"


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
