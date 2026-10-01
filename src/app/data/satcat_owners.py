"""Readable names for SATCAT `OWNER` codes, from the vendored `config/satcat_owners.yaml`.

`OWNER` is SATCAT's "source or ownership" code: usually the registering state ("US", "PRC"),
occasionally an organization ("ESA", "IRID"). It is not the operator - SATCAT has no operator
field, and e.g. Iridium NEXT satellites are "US", not "IRID". Hence the report field is named
`satcat_owner`, not `owner`. The table is refreshed by hand (scripts/build_satcat_owners.py); a
code it doesn't know still reaches the report, with a null name.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

OWNERS_PATH = Path(__file__).resolve().parents[3] / "config" / "satcat_owners.yaml"


@cache
def owner_names(path: Path = OWNERS_PATH) -> dict[str, str]:
    data: dict[str, str] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def owner_record(code: str | None) -> dict[str, Any] | None:
    """`{"code": ..., "name": ...}` for the report, or None when there's no SATCAT owner."""
    if code is None:
        return None
    return {"code": code, "name": owner_names().get(code)}
