import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
LEARNER_OWNED = ("analysis", "persona", "practice", "progress", "weaknesses")
OWNED_ENTITY_ARGUMENT = "record"
USER_ARGUMENT = "user_id"


def repository_classes(package: str) -> list[ast.ClassDef]:
    tree = ast.parse((SRC_DIR / package / "repository.py").read_text())
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


def methods(node: ast.ClassDef) -> list[ast.AsyncFunctionDef]:
    return [member for member in node.body if isinstance(member, ast.AsyncFunctionDef)]


def argument_names(method: ast.AsyncFunctionDef) -> set[str]:
    return {argument.arg for argument in method.args.args}


def loads_name(method: ast.AsyncFunctionDef, name: str) -> bool:
    return any(
        isinstance(node, ast.Name)
        and node.id == name
        and isinstance(node.ctx, ast.Load)
        for node in ast.walk(method)
    )


def interface_methods() -> list[tuple[str, str, ast.AsyncFunctionDef]]:
    return [
        (package, node.name, method)
        for package in LEARNER_OWNED
        for node in repository_classes(package)
        if not node.name.endswith("Impl")
        for method in methods(node)
    ]


def implementation_methods() -> list[tuple[str, str, ast.AsyncFunctionDef]]:
    return [
        (package, node.name, method)
        for package in LEARNER_OWNED
        for node in repository_classes(package)
        if node.name.endswith("Impl")
        for method in methods(node)
        if USER_ARGUMENT in argument_names(method)
    ]


@pytest.mark.parametrize(
    ("package", "class_name", "method"),
    interface_methods(),
    ids=lambda value: value if isinstance(value, str) else value.name,
)
def test_learner_repository_methods_are_scoped_to_a_user(
    package: str, class_name: str, method: ast.AsyncFunctionDef
) -> None:
    names = argument_names(method)

    assert USER_ARGUMENT in names or OWNED_ENTITY_ARGUMENT in names, (
        f"{package}.{class_name}.{method.name} takes neither "
        f"{USER_ARGUMENT} nor an already owned {OWNED_ENTITY_ARGUMENT}"
    )


@pytest.mark.parametrize(
    ("package", "class_name", "method"),
    implementation_methods(),
    ids=lambda value: value if isinstance(value, str) else value.name,
)
def test_learner_repository_methods_use_the_user_they_are_given(
    package: str, class_name: str, method: ast.AsyncFunctionDef
) -> None:
    assert loads_name(
        method, USER_ARGUMENT
    ), f"{package}.{class_name}.{method.name} accepts {USER_ARGUMENT} but never uses it"


def test_every_learner_owned_package_has_repository_interfaces() -> None:
    assert interface_methods()
    assert {package for package, _, _ in interface_methods()} == set(LEARNER_OWNED)
