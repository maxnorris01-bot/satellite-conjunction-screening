"""Upload a finished star-data folder to the bucket under a versioned prefix. DRY RUN by default.

    python upload.py plan   --src stars-v1 [--prefix stars/v1/]     # list what would be sent
    python upload.py put    --src stars-v1 --go                     # send it
    python upload.py verify --src stars-v1                          # check the public URLs
    python upload.py delete --prefix stars/v1/ --go                 # rollback: remove the prefix

Standalone on purpose (boto3 and the standard library only), so it can be copied into a throwaway
Fly Machine built from the app's own image, where the bucket's credentials are already in the
environment under the names `app.publish` uses: BUCKET_NAME, AWS_ENDPOINT_URL_S3,
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY. Credentials are read by boto3 from the environment and
never printed. Nothing outside the given prefix is read, written or deleted.

Headers (set per file; the path is versioned, so the cache lifetime is a year):
    *.bin.gz       ContentType application/octet-stream, ContentEncoding gzip, immutable
    manifest.json  ContentType application/json, immutable
    glow.json      ContentType application/json, immutable
    glow-o7.jpg    ContentType image/jpeg, immutable
The manifest is sent last, so a viewer that finds a manifest finds every file it lists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

PUBLIC_BASE = "https://satellite-conjunction-screening.fly.storage.tigris.dev/"
CACHE_CONTROL = "public, max-age=31536000, immutable"


def headers_for(rel: str) -> dict[str, str]:
    if rel.endswith(".bin.gz"):
        return {
            "ContentType": "application/octet-stream",
            "ContentEncoding": "gzip",
            "CacheControl": CACHE_CONTROL,
        }
    if rel.endswith(".json"):
        return {"ContentType": "application/json", "CacheControl": CACHE_CONTROL}
    if rel.endswith(".jpg"):
        return {"ContentType": "image/jpeg", "CacheControl": CACHE_CONTROL}
    raise ValueError(f"no upload rule for {rel}")


def plan(src: Path, prefix: str) -> list[tuple[Path, str, dict[str, str]]]:
    """(local file, bucket key, headers) for every file to send, manifest last."""
    keep = {"manifest.json", "glow.json", "glow-o7.jpg"}
    files: list[Path] = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        if rel in keep or (rel.startswith(("tiles/", "details/")) and rel.endswith(".bin.gz")):
            files.append(p)
    files.sort(key=lambda p: (p.relative_to(src).as_posix() == "manifest.json", p.as_posix()))
    out = []
    for p in files:
        rel = p.relative_to(src).as_posix()
        out.append((p, prefix + rel, headers_for(rel)))
    return out


def _client():  # type: ignore[no-untyped-def]
    import os

    import boto3

    bucket = os.environ.get("BUCKET_NAME")
    if not bucket:
        sys.exit("BUCKET_NAME is not set (run this inside the app's Machine, not on a laptop)")
    return boto3.client("s3"), bucket


def cmd_plan(a: argparse.Namespace) -> int:
    items = plan(Path(a.src).expanduser(), a.prefix)
    total = sum(p.stat().st_size for p, _, _ in items)
    print(f"{len(items)} files, {total / 1e6:.1f} MB, prefix {a.prefix}")
    for p, key, h in items[:3] + items[-2:]:
        print(f"  {key}  {p.stat().st_size:>9,} B  {h}")
    return 0


def cmd_put(a: argparse.Namespace) -> int:
    items = plan(Path(a.src).expanduser(), a.prefix)
    if not a.go:
        print("dry run (no --go): nothing sent")
        return cmd_plan(a)
    s3, bucket = _client()
    existing = s3.list_objects_v2(Bucket=bucket, Prefix=a.prefix, MaxKeys=1).get("KeyCount", 0)
    if existing and not a.overwrite:
        sys.exit(f"{a.prefix} already has objects; pick a new version prefix or pass --overwrite")
    for i, (p, key, h) in enumerate(items, 1):
        s3.put_object(Bucket=bucket, Key=key, Body=p.read_bytes(), **h)
        if i % 100 == 0 or i == len(items):
            print(f"  {i}/{len(items)} sent", flush=True)
    print(f"done: {len(items)} files under {a.prefix} (manifest last)")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    src = Path(a.src).expanduser()
    m = json.loads((src / "manifest.json").read_text())
    base = PUBLIC_BASE + a.prefix
    bad = 0
    sample = m["tiles"][:: max(1, len(m["tiles"]) // a.sample)]
    for t in sample:
        for f, want in ((t["file"], t["sha256"]), (t["details_file"], t["details_sha256"])):
            req = urllib.request.Request(base + f, headers={"Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                enc = r.headers.get("Content-Encoding")
                cc = r.headers.get("Cache-Control")
            ok = hashlib.sha256(body).hexdigest() == want
            bad += not ok
            print(f"  {'ok ' if ok else 'BAD'} {f} encoding={enc} cache={cc}")
    print("verify:", "all sampled files match the manifest" if not bad else f"{bad} mismatches")
    return 1 if bad else 0


def cmd_delete(a: argparse.Namespace) -> int:
    if not a.prefix.startswith("stars/") or len(a.prefix) < 8:
        sys.exit("refusing: the prefix must be a stars/<version>/ path")
    s3, bucket = _client()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=a.prefix):
        keys += [o["Key"] for o in page.get("Contents", [])]
    print(f"{len(keys)} objects under {a.prefix}")
    if not a.go:
        print("dry run (no --go): nothing deleted")
        return 0
    for i in range(0, len(keys), 1000):
        chunk = [{"Key": k} for k in keys[i : i + 1000]]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": chunk})
    print(f"deleted {len(keys)} objects")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "put", "verify", "delete"):
        s = sub.add_parser(name)
        s.add_argument("--prefix", default="stars/v1/")
        if name != "delete":
            s.add_argument("--src", required=True)
        if name in ("put", "delete"):
            s.add_argument(
                "--go", action="store_true", help="actually do it (default is a dry run)"
            )
        if name == "put":
            s.add_argument("--overwrite", action="store_true")
        if name == "verify":
            s.add_argument("--sample", type=int, default=12)
    a = p.parse_args(argv)
    return {"plan": cmd_plan, "put": cmd_put, "verify": cmd_verify, "delete": cmd_delete}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
