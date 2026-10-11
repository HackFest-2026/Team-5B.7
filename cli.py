#!/usr/bin/env python
"""
Monetize360 Command Line Interface (CLI)

Usage:
    python cli.py price --pack packs/ecommerce.json --context '{"category":"electronics","mrp":1000,"inventory_pct":15}'
    python cli.py validate --pack packs/ecommerce.json
    python cli.py benchmark
    python cli.py list-packs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))

from engine.runtime import PricingError, compute_price
from engine.validate import validate_pack
from engine.schema.pack import DomainPack


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monetize360 — Universal Dynamic Pricing Engine CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    # Price evaluation command
    price_parser = subparsers.add_parser("price", help="Evaluate a price for a given context")
    price_parser.add_argument("--pack", required=True, help="Path to domain pack JSON")
    price_parser.add_argument(
        "--context",
        required=True,
        help="JSON string of context signals (e.g. '{\"mrp\": 1000}')",
    )

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate a domain pack JSON file")
    val_parser.add_argument("--pack", required=True, help="Path to domain pack JSON")

    # List packs command
    subparsers.add_parser("list-packs", help="List all available pre-packaged domain packs")

    # Benchmark command
    subparsers.add_parser("benchmark", help="Run latency and throughput benchmarks")

    args = parser.parse_args()

    if args.command == "price":
        pack_path = Path(args.pack)
        if not pack_path.exists():
            print(f"Error: Pack file '{args.pack}' not found.", file=sys.stderr)
            sys.exit(1)

        try:
            pack_dict = json.loads(pack_path.read_text(encoding="utf-8"))
            pack = DomainPack.model_validate(pack_dict)
            context = json.loads(args.context)
        except Exception as e:
            print(f"Error parsing input: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            result = compute_price(pack, context)
        except PricingError as e:
            print(f"Pricing Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result.to_dict(), indent=2))

    elif args.command == "validate":
        pack_path = Path(args.pack)
        if not pack_path.exists():
            print(f"Error: Pack file '{args.pack}' not found.", file=sys.stderr)
            sys.exit(1)

        try:
            pack_dict = json.loads(pack_path.read_text(encoding="utf-8"))
            pack = DomainPack.model_validate(pack_dict)
        except Exception as e:
            print(f"Schema Error: {e}", file=sys.stderr)
            sys.exit(1)

        res = validate_pack(pack)
        print(json.dumps(res.to_dict(), indent=2))
        sys.exit(0 if res.valid else 1)

    elif args.command == "list-packs":
        packs_dir = ROOT / "packs"
        for p in sorted(packs_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            print(f"• [{data.get('pack_id')}] - v{data.get('version')} ({data.get('description')})")

    elif args.command == "benchmark":
        from scripts.benchmark import main as run_benchmark
        run_benchmark()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
