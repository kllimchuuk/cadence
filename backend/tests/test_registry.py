from pathlib import Path

import core.registry
from core.base_model import Base

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _model_modules() -> set[str]:
    return {f"{path.parent.name}.models" for path in SRC_DIR.glob("*/models.py")}


def _registered_modules() -> set[str]:
    return {
        value.__module__
        for value in vars(core.registry).values()
        if isinstance(value, type) and issubclass(value, Base) and value is not Base
    }


def test_every_model_module_is_registered() -> None:
    modules = _model_modules()

    assert modules
    assert _registered_modules() == modules
