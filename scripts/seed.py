#!/usr/bin/env python
"""
Seed script — loads all domain packs into the database and publishes them.

Usage:
    python scripts/seed.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from api.storage import init_db, upsert_pack, get_published_pack, publish_pack

PACKS_DIR = ROOT / "packs"


def main():
    print("\n  Monetize360 — Seeding domain packs")
    print("  " + "="*40)

    init_db()

    for pack_file in sorted(PACKS_DIR.glob("*.json")):
        try:
            data = json.loads(pack_file.read_text())
            pack_id = data.get("pack_id")
            version = data.get("version", "1.0.0")

            if not pack_id:
                print(f"  [SKIP] {pack_file.name}: no pack_id")
                continue

            existing = get_published_pack(pack_id)

            if existing and existing["version"] == version:
                upsert_pack(pack_id, version, data, status=existing["status"], actor="seed")
                print(f"  [OK]   {pack_id} v{version} already published")
            else:
                upsert_pack(pack_id, version, data, status="draft", actor="seed")
                publish_pack(pack_id, version, actor="seed")
                print(f"  [PUB]  {pack_id} v{version} published")

        except Exception as exc:
            print(f"  [ERR]  {pack_file.name}: {exc}")

    print("  " + "="*40)
    print("  Done.\n")


if __name__ == "__main__":
    main()
