#!/usr/bin/env python3
"""
Strip non-arm64-v8a native libraries from APK(s) in place.

Idempotent: if an APK already contains only lib/arm64-v8a/, it is left
untouched (no read/decompress/rewrite pass) and 0 is reported.

Usage:
    python strip_arch.py patched-mod-unsigned.apk patched-original-unsigned.apk

Exit codes:
    0 — success (whether anything was stripped or not)
    2 — bad usage
"""
import os
import sys
import zipfile

# Any entry under these prefixes is removed. Everything else is preserved verbatim.
DROP_PREFIXES = (
    "lib/armeabi-v7a/",
    "lib/x86/",
    "lib/x86_64/",
)


def strip(src: str) -> int:
    if not os.path.isfile(src):
        print(f"[strip_arch] {src}: not found, skipping")
        return 0

    # First pass: figure out whether anything actually needs dropping.
    try:
        with zipfile.ZipFile(src, "r") as zin:
            to_drop = [
                item.filename
                for item in zin.infolist()
                if any(item.filename.startswith(p) for p in DROP_PREFIXES)
            ]
    except zipfile.BadZipFile as e:
        print(f"[strip_arch] {src}: not a valid zip/APK ({e}) — skipping")
        return 0

    if not to_drop:
        print(f"[strip_arch] {src}: already arm64-only, nothing to strip")
        return 0

    drop_set = set(to_drop)
    tmp = src + ".stripped"

    # Second pass: rewrite without the dropped entries.
    try:
        with zipfile.ZipFile(src, "r") as zin, \
             zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename in drop_set:
                    continue
                zout.writestr(item, zin.read(item.filename))
        os.replace(tmp, src)
    except Exception as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        print(f"[strip_arch] {src}: failed to strip ({e})")
        raise

    print(f"[strip_arch] {src}: dropped {len(to_drop)} non-arm64 entries")
    return len(to_drop)


def main():
    if len(sys.argv) < 2:
        print("usage: strip_arch.py <apk> [<apk> ...]", file=sys.stderr)
        sys.exit(2)

    total = 0
    for path in sys.argv[1:]:
        total += strip(path)

    print(f"[strip_arch] done — total entries dropped: {total}")


if __name__ == "__main__":
    main()