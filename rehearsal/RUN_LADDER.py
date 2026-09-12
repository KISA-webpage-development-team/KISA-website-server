"""Read-only concurrency ladder against production.

Usage:  venv/bin/python rehearsal/RUN_LADDER.py "label for this run"

Sends only GETs to the board page and one comment thread at concurrency
1, 10, 20 and 40, prints median / p95 / max, and appends to ladder_results.txt next to this file.
"""
import ssl, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # python without CA certs: still fine for a timing probe
    CTX = ssl._create_unverified_context()

BASE = "https://umichkisa-api.com"
PATHS = {
    "board page": "/api/v2/boards/community/posts/?size=10&page=0",
    "comments (post 522)": "/api/v2/comments/522/",
}
LEVELS = (1, 10, 20, 40)


def get(path):
    started = time.time()
    try:
        urllib.request.urlopen(BASE + path, timeout=60, context=CTX).read()
        return 200, time.time() - started
    except urllib.error.HTTPError as error:
        return error.code, time.time() - started
    except Exception as error:
        return type(error).__name__, time.time() - started


label = sys.argv[1] if len(sys.argv) > 1 else "ladder"
lines = [f"== {label}  ({datetime.now():%Y-%m-%d %H:%M}) =="]
print(lines[0])
for name, path in PATHS.items():
    for n in LEVELS:
        with ThreadPoolExecutor(n) as pool:
            results = list(pool.map(lambda _: get(path), range(n)))
        times = sorted(t for _, t in results)
        ok = sum(1 for status, _ in results if status == 200)
        p95 = times[max(int(len(times) * 0.95) - 1, 0)]
        line = f"  {name:20} n={n:<3} ok={ok}/{n}  median={times[len(times)//2]:.2f}s  p95={p95:.2f}s  max={times[-1]:.2f}s"
        print(line, flush=True)
        lines.append(line)

with open(Path(__file__).resolve().parent / "ladder_results.txt", "a") as out:
    out.write("\n".join(lines) + "\n\n")
