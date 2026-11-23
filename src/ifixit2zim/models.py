from dataclasses import dataclass
from typing import Any


@dataclass
class IFixitMetadata:
    title: str
    description: str
    stats: list[dict[str, Any]]
    current_year: int
