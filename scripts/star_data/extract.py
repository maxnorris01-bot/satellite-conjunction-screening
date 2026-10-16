"""Extract Gaia DR3 stars brighter than a G limit from the ESA Gaia archive, cell by cell.

    W=~/Desktop/Projects/star-data-2026-10/work
    uv run python -m scripts.star_data.extract run    --out $W
    uv run python -m scripts.star_data.extract counts --out $W

`run` asks the archive's TAP service (https://gea.esac.esa.int/tap-server/tap) for one level-3
HEALPix cell at a time, using the cell's `source_id` range (the route that measured fast: the same
query took 5.9 s on ESA and 93 s on VizieR's copy). Every star is in exactly one ID range, so the
union is complete; a star's final position can sit in a neighbouring tile, which pack.py handles.
Each cell is saved as a raw CSV (gzip) and a parsed `.npz`; a finished cell is never asked for
again, so an interrupted run resumes.

Politeness: 2 workers by default, a pause between requests, exponential backoff with the server's
`Retry-After` honoured, and HTML replies (the archive's downtime page) treated as "try later", not
as data. Everything is written under --out; nothing here touches the repo or any bucket.

`counts` stores the archive's own totals (per cell and per whole magnitude) to check against.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scripts.star_data.healpix import cell_source_id_range, n_cells

TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
USER_AGENT = (
    "star-data-build (portfolio project; "
    "github.com/maxnorris01-bot/satellite-conjunction-screening)"
)
COLUMNS = "source_id, ra, dec, phot_g_mean_mag, bp_rp, parallax, parallax_error, pmra, pmdec"
FIELDS = [
    "source_id",
    "ra",
    "dec",
    "phot_g_mean_mag",
    "bp_rp",
    "parallax",
    "parallax_error",
    "pmra",
    "pmdec",
]
ORDER = 3
MAX_ATTEMPTS = 8
MAXREC = 3_000_000  # the archive's hard output limit; without it a reply stops at 50,000 rows


class TryLater(Exception):
    """A reply that isn't data (downtime page, 429, 5xx, timeout)."""

    def __init__(self, msg: str, wait: float | None = None) -> None:
        super().__init__(msg)
        self.wait = wait


def tap_csv(query: str, timeout: float = 900.0) -> bytes:
    url = (
        TAP
        + "?"
        + urllib.parse.urlencode(
            {
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "csv",
                "MAXREC": str(MAXREC),  # the sync default is 50,000 rows, and it cuts off silently
                "QUERY": query,
            }
        )
    )
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            body = gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
    except urllib.error.HTTPError as e:
        retry = e.headers.get("Retry-After")
        wait = float(retry) if retry and retry.isdigit() else None
        if e.code == 429 or e.code >= 500:
            raise TryLater(f"HTTP {e.code}", wait) from e
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise TryLater(f"network: {e}") from e
    head = body[:200].lstrip().lower()
    if head.startswith(b"<") or b"<html" in head:
        raise TryLater("HTML reply (archive downtime page?)")
    if b"error" in head[:60] and b"," not in head:
        raise TryLater("TAP error reply: " + body[:120].decode("utf-8", "replace"))
    return body


def tap_with_retry(query: str, label: str) -> tuple[bytes, int]:
    last = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return tap_csv(query), attempt
        except TryLater as e:
            last = str(e)
            wait = e.wait if e.wait is not None else min(300.0, 10.0 * 2 ** (attempt - 1))
            print(f"  {label}: attempt {attempt} failed ({last}); waiting {wait:.0f}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{label}: gave up after {MAX_ATTEMPTS} attempts ({last})")


def parse_cell(csv_bytes: bytes) -> dict[str, np.ndarray]:
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    if rows and set(FIELDS) - set(rows[0]):
        raise ValueError(f"unexpected columns: {list(rows[0])}")

    def col(name: str, dtype: str) -> np.ndarray:
        if dtype == "i8":
            return np.array([int(r[name]) for r in rows], dtype=np.int64)
        return np.array(
            [float(r[name]) if r[name] not in ("", "null") else np.nan for r in rows], dtype=dtype
        )

    return {
        "source_id": col("source_id", "i8"),
        "ra": col("ra", "f8"),
        "dec": col("dec", "f8"),
        "g": col("phot_g_mean_mag", "f4"),
        "bp_rp": col("bp_rp", "f4"),
        "parallax": col("parallax", "f4"),
        "parallax_error": col("parallax_error", "f4"),
        "pmra": col("pmra", "f4"),
        "pmdec": col("pmdec", "f4"),
    }


def cell_query(cell: int, g_limit: float) -> str:
    lo, hi = cell_source_id_range(cell, ORDER)
    return (
        f"SELECT {COLUMNS} FROM gaiadr3.gaia_source "
        f"WHERE source_id >= {lo} AND source_id < {hi} AND phot_g_mean_mag < {g_limit}"
    )


def fetch_cell(out: Path, cell: int, g_limit: float, pause: float) -> dict[str, object]:
    npz = out / "cells" / f"c{ORDER}_{cell:04d}.npz"
    if npz.exists():
        meta = json.loads((out / "cells" / f"c{ORDER}_{cell:04d}.json").read_text())
        return {**meta, "skipped": True}
    time.sleep(pause)
    t0 = time.time()
    body, attempts = tap_with_retry(cell_query(cell, g_limit), f"cell {cell}")
    seconds = time.time() - t0
    arrays = parse_cell(body)
    n = len(arrays["source_id"])
    lo, hi = cell_source_id_range(cell, ORDER)
    if n and not ((arrays["source_id"] >= lo).all() and (arrays["source_id"] < hi).all()):
        raise ValueError(f"cell {cell}: a source_id outside the requested range")
    if len(np.unique(arrays["source_id"])) != n:
        raise ValueError(f"cell {cell}: duplicate source_id in one reply")
    counts_file = out / "archive_counts.json"
    if counts_file.exists():  # never keep a cell that disagrees with the archive's own count
        expected = int(json.loads(counts_file.read_text())["cells"].get(str(cell), 0))
        if n != expected:
            raise ValueError(f"cell {cell}: got {n} rows, the archive counts {expected}")
    raw_path = out / "raw" / f"c{ORDER}_{cell:04d}.csv.gz"
    raw_path.write_bytes(gzip.compress(body, 6, mtime=0))
    meta = {
        "cell": cell,
        "order": ORDER,
        "rows": n,
        "csv_bytes": len(body),
        "csv_sha256": hashlib.sha256(body).hexdigest(),
        "seconds": round(seconds, 2),
        "attempts": attempts,
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "g_limit": g_limit,
    }
    np.savez_compressed(npz, **arrays)
    (out / "cells" / f"c{ORDER}_{cell:04d}.json").write_text(json.dumps(meta))
    return {**meta, "skipped": False}


def cmd_run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    for d in ("cells", "raw"):
        (out / d).mkdir(parents=True, exist_ok=True)
    cells = list(range(n_cells(ORDER)))
    if args.cells:
        a, _, b = args.cells.partition("-")
        cells = list(range(int(a), int(b or a) + 1))
    started = time.time()
    done = rows = skipped = failed = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch_cell, out, c, args.g_limit, args.pause): c for c in cells}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                meta = fut.result()
            except Exception as e:  # keep going; the cell is retried on the next run
                failed += 1
                print(f"FAILED cell {c}: {e}", flush=True)
                continue
            with lock:
                done += 1
                rows += int(meta["rows"])  # type: ignore[call-overload]
                skipped += bool(meta["skipped"])
                elapsed = time.time() - started
                fetched = done - skipped
                eta = (
                    (len(cells) - done - failed) * (elapsed / max(fetched, 1)) / args.workers
                    if fetched
                    else 0
                )
                took = "(cached)" if meta["skipped"] else f"{float(meta['seconds']):.1f}s"  # type: ignore[arg-type]
                print(
                    f"[{done + failed}/{len(cells)}] cell {c:>3}: {meta['rows']:>6} rows {took} | "
                    f"total {rows:,} rows | elapsed {elapsed / 60:.1f} min, "
                    f"ETA ~{eta / 60:.0f} min",
                    flush=True,
                )
    print(
        f"finished: {done} cells ok ({skipped} cached), {failed} failed, {rows:,} rows", flush=True
    )
    return 1 if failed else 0


def cmd_counts(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    shift = 35 + 2 * (12 - ORDER)
    print("per-cell totals ...", flush=True)
    body, _ = tap_with_retry(
        f"SELECT source_id / {2**shift} AS cell, COUNT(*) AS n FROM gaiadr3.gaia_source "
        f"WHERE phot_g_mean_mag < {args.g_limit} GROUP BY cell",
        "per-cell counts",
    )
    cells = {int(r["cell"]): int(r["n"]) for r in csv.DictReader(io.StringIO(body.decode()))}
    print("per-magnitude totals ...", flush=True)
    body, _ = tap_with_retry(
        f"SELECT FLOOR(phot_g_mean_mag) AS gbin, COUNT(*) AS n FROM gaiadr3.gaia_source "
        f"WHERE phot_g_mean_mag < {args.g_limit} GROUP BY gbin",
        "per-magnitude counts",
    )
    bins = {int(float(r["gbin"])): int(r["n"]) for r in csv.DictReader(io.StringIO(body.decode()))}
    result = {
        "g_limit": args.g_limit,
        "order": ORDER,
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "total": sum(cells.values()),
        "cells": cells,
        "by_floor_g": dict(sorted(bins.items())),
    }
    (out / "archive_counts.json").write_text(json.dumps(result, indent=1))
    print(f"archive total G<{args.g_limit}: {result['total']:,} in {len(cells)} cells", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "counts"):
        s = sub.add_parser(name)
        s.add_argument("--out", required=True, help="work folder (outside the repo)")
        s.add_argument("--g-limit", type=float, default=13.0)
        if name == "run":
            s.add_argument("--workers", type=int, default=2)
            s.add_argument("--pause", type=float, default=0.5, help="seconds before each request")
            s.add_argument("--cells", help="a cell or a range 'a-b' (default: all 768)")
    args = p.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_counts(args)


if __name__ == "__main__":
    sys.exit(main())
