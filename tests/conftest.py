from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class DummyResponse:
    payload: Dict[str, Any]

    def json(self) -> Dict[str, Any]:
        return self.payload

