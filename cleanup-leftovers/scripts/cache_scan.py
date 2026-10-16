"""List regenerable tool-cache folders under a root whose newest file is older than a cutoff.

Usage: python -I cache_scan.py <root> <output list file> <days>

Walks with os.walk and prunes node_modules and .git trees, checking only node_modules/.cache at the top
of each node_modules. Ages a folder by the newest file inside it, not by the folder's own timestamp.
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


found = []
for base, dirs, _files in os.walk(ROOT):
    keep = []
    for d in dirs:
        full = os.path.join(base, d)
        if d == "node_modules":
            cache = os.path.join(full, ".cache")
            if os.path.isdir(cache):
                found.append(cache)
        elif d == ".git":
            continue
        elif d in NAMES:
            found.append(full)
        else:
            keep.append(d)
    dirs[:] = keep

old, total = [], 0
for path in found:
    newest, size = newest_and_size(path)
    if newest < CUTOFF:
        old.append(path)
        total += size
print(f"cache folders found: {len(found)}; older than {DAYS} days: {len(old)}, {total / 2**20:.1f} MB")
by_top: dict[str, list[str]] = {}
for path in old:
    by_top.setdefault(os.path.relpath(path, ROOT).split(os.sep)[0], []).append(path)
for top, paths in sorted(by_top.items()):
    kinds = sorted({"node_modules/.cache" if os.path.basename(p) == ".cache" else os.path.basename(p) for p in paths})
    print(f"  {top:<28} {len(paths):>5} folders  {', '.join(kinds)}")
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(old))
