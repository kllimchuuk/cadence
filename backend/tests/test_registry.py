import importlib
from pathlib import Path

from core.registry import metadata

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _model_modules() -> list[str]:
    return [
        f"{path.parent.name}.models" for path in sorted(SRC_DIR.glob("*/models.py"))
    ]


def test_every_model_module_is_registered() -> None:
    modules = _model_modules()
    registered = set(metadata.tables)

    for module in modules:
        importlib.import_module(module)

    assert modules
    assert set(metadata.tables) == registered
