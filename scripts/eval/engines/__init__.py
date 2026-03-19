"""Engine registry — discovers and loads engine modules from this directory."""

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType


def _validate_engine(mod: ModuleType) -> None:
    """Check that a module has the required engine interface."""
    for attr in ("VERSION", "DESCRIPTION", "generate"):
        if not hasattr(mod, attr):
            raise AttributeError(
                f"Engine {mod.__name__} missing required attribute: {attr}"
            )
    if not callable(mod.generate):
        raise TypeError(f"Engine {mod.__name__}.generate must be callable")


def load_engine(name: str) -> ModuleType:
    """Load a specific engine by name (e.g. 'v1')."""
    mod = importlib.import_module(f".{name}", package=__name__)
    _validate_engine(mod)
    return mod


def list_engines() -> list[dict]:
    """Discover all engines and return their metadata."""
    engines = []
    pkg_path = Path(__file__).parent

    for info in pkgutil.iter_modules([str(pkg_path)]):
        if info.name.startswith("_"):
            continue
        try:
            mod = load_engine(info.name)
            engines.append(
                {
                    "name": mod.VERSION,
                    "description": mod.DESCRIPTION,
                    "parent": getattr(mod, "PARENT", None),
                    "module": info.name,
                }
            )
        except (AttributeError, TypeError):
            pass

    engines.sort(key=lambda e: e["name"])
    return engines
