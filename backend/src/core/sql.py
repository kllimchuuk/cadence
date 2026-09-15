from enum import StrEnum

from sqlalchemy import CheckConstraint


def enum_check(column: str, name: str, values: type[StrEnum]) -> CheckConstraint:
    allowed = ", ".join(f"'{member.value}'" for member in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)
