#!/usr/bin/env python3
"""
Extract the Google Photos versions supported by a Morphe patch bundle (.mpp).

A .mpp is a JAR/ZIP of compiled Kotlin classes. Each patch declares its
compatible packages/versions via the `compatiblePackages` annotation, whose
arguments are compiled into the class file's constant pool as UTF-8 strings.
By scanning the class files we can recover the exact same list morphe-cli
uses at patch time — no need to hardcode it in download_apk.py.

Filtering strategy (two tiers):
  1. Strict: only class files that contain BOTH the package name AND a
     Photos-shaped version string. This is the most precise.
  2. Relaxed: if tier 1 yields nothing (e.g. a patch uses a shared helper to
     declare the compatible package), scan every class file for
     Photos-shaped version strings, but only if the JAR references
     com.google.android.apps.photos anywhere.

Output: comma-separated list of versions on stdout, highest first.
Exit codes:
  0 — versions found and printed (or --check-only succeeded)
  1 — no supported versions found
  2 — bad usage
"""
import argparse
import os
import re
import sys
import zipfile

PACKAGE_NAME = "com.google.android.apps.photos"

# Google Photos versions: X.Y.Z.<build-id>, where build-id is 6+ digits
# (e.g. 7.93.0.982110057). That long final component makes the pattern very
# selective — it does not match library versions like 1.2.3 or API levels.
BUILD_VERSION_RE_BYTES = re.compile(rb"\b(\d+\.\d+\.\d+\.\d{6,})\b")


def _parse_version_tuple(ver_str):
    parts = re.findall(r"\d+", ver_str or "")
    return tuple(int(p) for p in parts) if parts else (0,)


def _scan_strict(zf):
    """Package name and version string in the same class file."""
    versions = set()
    pkg_bytes = PACKAGE_NAME.encode("ascii")
    for name in zf.namelist():
        if not name.endswith(".class"):
            continue
        try:
            data = zf.read(name)
        except (zipfile.BadZipFile, OSError):
            continue
        if pkg_bytes not in data:
            continue
        for m in BUILD_VERSION_RE_BYTES.finditer(data):
            versions.add(m.group(1).decode("ascii"))
    return versions


def _jar_references_package(zf):
    pkg_bytes = PACKAGE_NAME.encode("ascii")
    for name in zf.namelist():
        if not name.endswith(".class"):
            continue
        try:
            if pkg_bytes in zf.read(name):
                return True
        except (zipfile.BadZipFile, OSError):
            continue
    return False


def _scan_relaxed(zf):
    """Any class file, but only if the JAR references the package somewhere."""
    if not _jar_references_package(zf):
        return set()
    versions = set()
    for name in zf.namelist():
        if not name.endswith(".class"):
            continue
        try:
            data = zf.read(name)
        except (zipfile.BadZipFile, OSError):
            continue
        for m in BUILD_VERSION_RE_BYTES.finditer(data):
            versions.add(m.group(1).decode("ascii"))
    return versions


def find_supported_versions(patch_file):
    if not os.path.isfile(patch_file):
        print(f"[get_supported_versions] {patch_file} not found", file=sys.stderr)
        return set()
    try:
        with zipfile.ZipFile(patch_file) as zf:
            versions = _scan_strict(zf)
            if versions:
                print(
                    f"[get_supported_versions] Strict scan found {len(versions)} version(s).",
                    file=sys.stderr,
                )
                return versions
            versions = _scan_relaxed(zf)
            if versions:
                print(
                    f"[get_supported_versions] Relaxed scan found {len(versions)} version(s).",
                    file=sys.stderr,
                )
            return versions
    except (zipfile.BadZipFile, OSError) as e:
        print(f"[get_supported_versions] Cannot read {patch_file}: {e}", file=sys.stderr)
        return set()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("patch_file", help="Path to patches-*.mpp (or .jar)")
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 0 if versions were found, 1 if none; do not print them.",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.patch_file):
        print(f"[get_supported_versions] {args.patch_file} not found", file=sys.stderr)
        sys.exit(2)

    versions = find_supported_versions(args.patch_file)
    if not versions:
        print(
            f"[get_supported_versions] No supported versions found for {PACKAGE_NAME}.",
            file=sys.stderr,
        )
        sys.exit(1)

    ordered = sorted(versions, key=_parse_version_tuple, reverse=True)
    if args.check_only:
        sys.exit(0)
    print(",".join(ordered))


if __name__ == "__main__":
    main()