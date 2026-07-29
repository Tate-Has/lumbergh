"""Bill's instruction bundle: tracked here, materialized into his session workdir.

``AGENTS.md`` is re-rendered on every summon so Bill improves when Lumbergh upgrades;
``preferences.md``, ``briefs/``, and ``reports/`` are the user's and are only ever created.
"""

from pathlib import Path

from lumbergh.constants import CONFIG_DIR

_SRC = Path(__file__).resolve().parent
DEFAULT_PERSONALITY = "professional"

# The two task shapes Bill can dispatch. Lives here, the lightest module on both
# sides of the protocol, so the `lb` CLI can validate `--kind` without a round trip
# and without importing the FastAPI router (and GitPython behind it) just for a set.
TASK_KINDS = frozenset({"ship", "scout"})


def home() -> Path:
    return CONFIG_DIR / "bill"


def _personality_body(personality: str) -> str:
    path = _SRC / f"personality_{personality}.md"
    if not path.is_file():
        path = _SRC / f"personality_{DEFAULT_PERSONALITY}.md"
    return path.read_text().strip()


def render(personality: str = DEFAULT_PERSONALITY) -> str:
    template = (_SRC / "AGENTS.md.template").read_text()
    return template.replace("{{PERSONALITY}}", _personality_body(personality))


def materialize(personality: str = DEFAULT_PERSONALITY, home_dir: Path | None = None) -> Path:
    target = home_dir or home()
    target.mkdir(parents=True, exist_ok=True)
    (target / "briefs").mkdir(exist_ok=True)
    (target / "reports").mkdir(exist_ok=True)

    (target / "AGENTS.md").write_text(render(personality))

    claude = target / "CLAUDE.md"
    if not claude.exists():
        claude.symlink_to("AGENTS.md")

    prefs = target / "preferences.md"
    if not prefs.exists():
        prefs.write_text((_SRC / "preferences_seed.md").read_text())

    return target
