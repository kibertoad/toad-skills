"""List regenerable tool-cache folders under a root whose newest file is older than a cutoff.

Usage: python -I cache_scan.py <root> <output list file> <days>

Walks with os.walk and prunes node_modules and .git trees, checking only node_modules/.cache at the top
of each node_modules. Cargo target folders are not walked into; each build directory directly inside one
(debug, release, a custom CARGO_TARGET_DIR such as target/perfwork) is listed and aged on its own.
Ages a folder by the newest file inside it, not by the folder's own timestamp.
Prints a summary per top-level folder under the root and writes the old paths, one per line, to the
output file. It deletes nothing.
"""

import os
import sys
import time

ROOT, OUT, DAYS = sys.argv[1], sys.argv[2], float(sys.argv[3])
CUTOFF = time.time() - DAYS * 86400
# Regenerable caches only. Not here on purpose: .wrangler (holds wrangler's local D1/KV/R2 state),
# node_modules, bin/obj/dist/build outputs, .venv.
NAMES = {".turbo", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__", ".vite", ".parcel-cache", ".nx", ".eslintcache"}


def newest_and_size(path: str) -> tuple[float, int]:
    newest, size = os.path.getmtime(path), 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                st = os.stat(os.path.join(base, name))
            except OSError:
                continue
            newest = max(newest, st.st_mtime)
            size += st.st_size
    return newest, size


def is_cargo_target(base: str, full: str) -> bool:
    # A folder named target with a Cargo.toml beside it, or with the CACHEDIR.TAG cargo writes into it.
    return os.path.isfile(os.path.join(base, "Cargo.toml")) or os.path.isfile(os.path.join(full, "CACHEDIR.TAG"))


found: list[tuple[str, str]] = []
for base, dirs, _files in os.walk(ROOT):
    keep = []
    for d in dirs:
        full = os.path.join(base, d)
        if d == "node_modules":
            cache = os.path.join(full, ".cache")
            if os.path.isdir(cache):
                found.append((cache, "node_modules/.cache"))
        elif d == ".git":
            continue
        elif d in NAMES:
            found.append((full, d))
        elif d == "target" and is_cargo_target(base, full):
            try:
                builds = [e.path for e in os.scandir(full) if e.is_dir(follow_symlinks=False)]
            except OSError:
                builds = []
            found.extend((b, "cargo target") for b in builds)
        else:
            keep.append(d)
    dirs[:] = keep

old, total = [], 0
for path, kind in found:
    newest, size = newest_and_size(path)
    if newest < CUTOFF:
        old.append((path, kind, size))
        total += size
print(f"cache folders found: {len(found)}; older than {DAYS} days: {len(old)}, {total / 2**20:.1f} MB")
by_top: dict[str, list[tuple[str, str, int]]] = {}
for entry in old:
    by_top.setdefault(os.path.relpath(entry[0], ROOT).split(os.sep)[0], []).append(entry)
for top, entries in sorted(by_top.items()):
    kinds = sorted({kind for _path, kind, _size in entries})
    mb = sum(size for _path, _kind, size in entries) / 2**20
    print(f"  {top:<28} {len(entries):>5} folders  {mb:>10.1f} MB  {', '.join(kinds)}")
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(path for path, _kind, _size in old))
