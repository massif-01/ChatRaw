"""Consistent SQLite backup (including WAL); never overwrite an existing file."""

import argparse
import sqlite3
from pathlib import Path
from urllib.parse import quote


def backup(source: Path, destination: Path):
    source = source.resolve(strict=True)
    destination = destination.absolute()
    # Exclusive reservation also makes accidental overwrite fail before opening SQLite.
    with destination.open("xb"):
        pass
    destination.chmod(0o600)
    try:
        with sqlite3.connect(
            "file:" + quote(str(source)) + "?mode=ro", uri=True
        ) as origin:
            with sqlite3.connect(destination) as copy:
                origin.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    backup(args.source, args.destination)
    print("SQLite backup verified")


if __name__ == "__main__":
    main()
