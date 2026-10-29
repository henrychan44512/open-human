"""Write the distribution zip, with entry names that survive any locale.

Windows ships a bsdtar whose name handling goes through the OEM codepage: give it
a path like ``humans/我爸/human_data.md`` and the archive gets cp936 bytes with
the UTF-8 flag cleared, i.e. mojibake on every other machine. tar also refuses
``-T`` lists containing such paths ("Couldn't visit directory"). Python's
``zipfile`` encodes non-ASCII names as UTF-8 *and* sets flag bit 11, so the file
is readable by Explorer, 7-Zip and unzip alike.

Called by ``scripts/pack_beta.ps1``; the file list (UTF-8, one relative path per
line) is built there. Already-compressed payloads are stored, the rest deflates.
"""

from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

# Only formats where deflate is wasted work: the bytes are already compressed.
STORED = {".zip", ".gz", ".7z", ".xz", ".bz2"}

# The archive must still be runnable after someone unzips it elsewhere.
REQUIRED = ("LICENSE", "README.md", "pyproject.toml", "Open Human.cmd", "src/openhuman/cli.py",
            "humans/_template/human_data.md", ".venv/Scripts/python.exe")
# Personal state and local settings never travel.
FORBIDDEN = ("data/", "dist/", ".git/", "config.toml", "vendor/webview2/")


def read_list(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def build(root: Path, items: list[str], out: Path, *, required: tuple[str, ...] = REQUIRED,
          forbidden: tuple[str, ...] = FORBIDDEN) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    written: set[str] = set()
    skipped: list[str] = []
    payload = 0

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        for n, rel in enumerate(items, 1):
            src = root / rel
            if not src.exists():
                skipped.append(rel)  # a log or temp file vanished mid-pack
                continue
            arc = rel.replace("\\", "/")
            if src.suffix.lower() in STORED:
                zf.write(src, arc, compress_type=zipfile.ZIP_STORED, compresslevel=0)
            else:
                zf.write(src, arc, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
            written.add(arc)
            payload += src.stat().st_size
            if n % 1000 == 0:
                print(f"  {n:,}/{len(items):,} files, {payload / (1 << 20):,.0f} MB", flush=True)

    names = verify(out, written, required=required, forbidden=forbidden)
    non_ascii = sorted(n for n in names if not n.isascii())
    size = out.stat().st_size / (1 << 20)
    print(f"  {len(names):,} entries, {size:,.0f} MB, {time.time() - started:,.0f}s")
    if non_ascii:
        print(f"  {len(non_ascii)} non-ASCII name(s), e.g. {non_ascii[0]}")
    if skipped:
        print(f"  {len(skipped)} vanished during packing (not fatal): {skipped[0]}")
    return 0


def verify(out: Path, expected: set[str] | None = None, *, required: tuple[str, ...] = REQUIRED,
           forbidden: tuple[str, ...] = FORBIDDEN) -> set[str]:
    """Read the archive back. A promise without a check is just a hope."""
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        bad = zf.testzip()
    if bad:
        raise SystemExit(f"corrupt entry in the archive: {bad}")
    if expected:
        missing = expected - names
        if missing:
            raise SystemExit("archive is missing: " + ", ".join(sorted(missing)[:5]))
    gone = [r for r in required if r not in names]
    if gone:
        raise SystemExit("archive is missing: " + ", ".join(gone))
    leaked = sorted(n for n in names if any(n == f or n.startswith(f) for f in forbidden))
    if leaked:
        raise SystemExit("archive leaked: " + ", ".join(leaked[:3]))
    return names


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, help="repo root the file list is relative to")
    ap.add_argument("--list", type=Path, help="UTF-8 file list, one relative path per line")
    ap.add_argument("--out", required=True, type=Path, help="zip to write, or to check with --check")
    ap.add_argument("--check", action="store_true", help="only re-read an existing archive and validate it")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    if args.check:
        names = verify(out)
        print(f"  ok: {len(names):,} entries, {out.stat().st_size / (1 << 20):,.0f} MB")
        return 0
    if not (args.root and args.list):
        ap.error("--root and --list are required unless --check is given")
    return build(args.root.resolve(), read_list(args.list), out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
