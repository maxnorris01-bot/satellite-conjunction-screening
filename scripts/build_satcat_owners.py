"""Regenerate `config/satcat_owners.yaml` from CelesTrak's SATCAT sources page (deliberate only).

    curl -sS -o sources.html https://celestrak.org/satcat/sources.php
    uv run python scripts/build_satcat_owners.py sources.html

The page (https://celestrak.org/satcat/sources.php) is the code list behind SATCAT's `OWNER`
field. It's an HTML table with no JSON/CSV form, so rather than scraping it on every run, the table
is vendored and refreshed by hand. A code missing from the table still reaches the report; only
its readable name is null. Commit a regenerated table on its own, with the date in the message.
"""

from __future__ import annotations

import html
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "config" / "satcat_owners.yaml"
ROW = re.compile(r"<tr[^>]*>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", re.S)


def parse(page: str) -> dict[str, str]:
    body = page[page.index("<tbody>") :]
    owners: dict[str, str] = {}
    for code, desc in ROW.findall(body):
        code = html.unescape(code).strip()
        name = " ".join(html.unescape(re.sub(r"<[^>]+>", "", desc)).split())
        if code in owners:
            raise ValueError(f"duplicate code {code!r}")
        owners[code] = name
    return owners


def main() -> int:
    owners = parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
    header = (
        "# SATCAT OWNER code -> readable name, vendored from\n"
        "# https://celestrak.org/satcat/sources.php\n"
        f"# ({len(owners)} codes, copied {datetime.now(UTC):%Y-%m-%d}). Regenerate only\n"
        "# deliberately: see scripts/build_satcat_owners.py. OWNER is SATCAT's 'source or\n"
        "# ownership': usually the registering state, occasionally an organization. It is not\n"
        "# the operator (no SATCAT field is); e.g. Iridium NEXT satellites are 'US', not 'IRID'.\n"
    )
    OUT.write_text(header + yaml.safe_dump(owners, sort_keys=True, allow_unicode=True))
    print(f"wrote {len(owners)} codes to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
