from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path

import pefile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("search", nargs="+", type=Path)
    parser.add_argument("--load-direct", action="store_true")
    args = parser.parse_args()
    index: dict[str, Path] = {}
    for root in args.search:
        if root.exists():
            for path in root.rglob("*.dll"):
                index.setdefault(path.name.lower(), path)
            for path in root.rglob("*.exe"):
                index.setdefault(path.name.lower(), path)
    if args.load_direct:
        handles = [os.add_dll_directory(str(root)) for root in args.search if root.is_dir()]
        image = pefile.PE(str(args.binary))
        for imported in getattr(image, "DIRECTORY_ENTRY_IMPORT", []):
            name = imported.dll.decode(errors="replace")
            try:
                ctypes.WinDLL(name)
                print(f"LOAD_OK={name}")
            except OSError as error:
                print(f"LOAD_FAIL={name} ERROR={error}")
        try:
            ctypes.WinDLL(str(args.binary))
            print(f"LOAD_OK={args.binary.name}")
        except OSError as error:
            print(f"LOAD_FAIL={args.binary.name} ERROR={error}")
        del handles
    pending = [args.binary]
    visited: set[str] = set()
    missing: set[tuple[str, str]] = set()
    while pending:
        path = pending.pop()
        key = str(path).lower()
        if key in visited:
            continue
        visited.add(key)
        try:
            image = pefile.PE(str(path), fast_load=True)
            image.parse_data_directories(
                directories=[
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
                ]
            )
        except pefile.PEFormatError:
            continue
        for imported in getattr(image, "DIRECTORY_ENTRY_IMPORT", []):
            name = imported.dll.decode(errors="replace").lower()
            if name.startswith("api-ms-") or name.startswith("ext-ms-"):
                continue
            dependency = index.get(name)
            if dependency is None:
                missing.add((name, path.name))
            else:
                pending.append(dependency)
        for imported in getattr(image, "DIRECTORY_ENTRY_DELAY_IMPORT", []):
            name = imported.dll.decode(errors="replace").lower()
            if name.startswith("api-ms-") or name.startswith("ext-ms-"):
                continue
            dependency = index.get(name)
            if dependency is None:
                missing.add((name, path.name))
            else:
                pending.append(dependency)
    print(f"SCANNED={len(visited)}")
    for name, parent in sorted(missing):
        print(f"MISSING={name} PARENT={parent}")


if __name__ == "__main__":
    main()
