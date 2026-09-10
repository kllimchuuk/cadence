import re
import secrets

from users.repository import UserRepository

_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9]+")
_FALLBACK_BASE = "learner"


def _slugify(base: str) -> str:
    slug = _SLUG_PATTERN.sub("", base).strip()
    return slug[:40] or _FALLBACK_BASE


async def generate_unique_nickname(base: str, users: UserRepository) -> str:
    slug = _slugify(base)

    if await users.get_by_nickname(slug) is None:
        return slug

    for _ in range(10):
        candidate = f"{slug}-{secrets.token_hex(3)}"
        if await users.get_by_nickname(candidate) is None:
            return candidate

    raise RuntimeError("Could not generate a unique nickname")
