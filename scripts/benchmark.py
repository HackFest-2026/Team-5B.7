#!/usr/bin/env python
"""
Benchmark script — measures pricing engine and API throughput and latency.

Measures:
  - Direct Engine throughput (RPS) and latency distribution (p50, p95, p99, mean)
  - End-to-end FastAPI HTTP API latency distribution, concurrency, volume, and error rate

Usage:
    python scripts/benchmark.py [--iterations 5000] [--api-iterations 1000] [--concurrency 4]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.schema.pack import DomainPack
from engine.runtime import compute_price

DOMAINS = {
    "hospitality": {
        "file": "hospitality.json",
        "signals": {
            "room_type": "deluxe",
            "occupancy_pct": 90,
            "stay_date_dow": "sat",
            "loyalty_tier": "gold",
        },
    },
    "ecommerce": {
        "file": "ecommerce.json",
        "signals": {
            "category": "electronics",
            "mrp": 10000,
            "inventory_pct": 20,
            "demand_score": 70,
            "customer_tier": "prime",
        },
    },
    "banking": {
        "file": "banking.json",
        "signals": {
            "loan_type": "personal",
            "credit_score": 750,
            "loan_amount": 200000,
            "loan_term_months": 60,
            "customer_segment": "regular",
        },
    },
    "ev_charging": {
        "file": "ev_charging.json",
        "signals": {
            "charger_type": "fast",
            "time_of_day": "peak",
            "grid_load": 85,
            "membership": "basic",
        },
    },
    "airline": {
        "file": "airline.json",
        "signals": {
            "cabin_class": "economy",
            "base_fare": 150,
            "distance_km": 1200,
            "demand_index": 50,
            "available_seats": 200,
            "total_seats": 300,
            "days_to_departure": 10,
        },
    },
}


def benchmark_engine_domain(name: str, pack: DomainPack, signals: dict, iterations: int) -> dict:
    latencies = []

    # Warm-up (50 runs)
    for _ in range(50):
        compute_price(pack, signals)

    for _ in range(iterations):
        t0 = time.perf_counter()
        compute_price(pack, signals)
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    n = len(latencies)
    total_ms = sum(latencies)

    return {
        "domain": name,
        "mode": "engine_in_memory",
        "iterations": n,
        "concurrency": 1,
        "errors": 0,
        "error_rate_pct": 0.0,
        "p50_ms": round(latencies[int(n * 0.50)], 4),
        "p95_ms": round(latencies[int(n * 0.95)], 4),
        "p99_ms": round(latencies[int(n * 0.99)], 4),
        "mean_ms": round(total_ms / n, 4),
        "rps": round(1000 / (total_ms / n), 1),
    }


def benchmark_api_domain(name: str, signals: dict, iterations: int, concurrency: int) -> dict:
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    payload = {"domain": name, "signals": signals}

    # Warm-up (20 requests)
    for _ in range(20):
        client.post("/v1/price", json=payload)

    latencies = []
    errors = 0

    def _worker_task(_) -> float:
        nonlocal errors
        t0 = time.perf_counter()
        try:
            resp = client.post("/v1/price", json=payload)
            if resp.status_code != 200:
                errors += 1
        except Exception:
            errors += 1
        return (time.perf_counter() - t0) * 1000

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_worker_task, i) for i in range(iterations)]
        for f in concurrent.futures.as_completed(futures):
            latencies.append(f.result())
    t_total_wall_sec = time.perf_counter() - t_start

    latencies.sort()
    n = len(latencies)
    total_latency_ms = sum(latencies)

    return {
        "domain": name,
        "mode": "api_http",
        "iterations": n,
        "concurrency": concurrency,
        "errors": errors,
        "error_rate_pct": round(errors / n * 100, 2),
        "p50_ms": round(latencies[int(n * 0.50)], 4),
        "p95_ms": round(latencies[int(n * 0.95)], 4),
        "p99_ms": round(latencies[int(n * 0.99)], 4),
        "mean_ms": round(total_latency_ms / n, 4),
        "rps": round(n / t_total_wall_sec, 1),
        "wall_time_sec": round(t_total_wall_sec, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Monetize360 Performance Benchmark")
    parser.add_argument("--iterations", type=int, default=5000, help="Iterations per domain for engine benchmark")
    parser.add_argument("--api-iterations", type=int, default=500, help="Iterations per domain for API benchmark")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrency workers for API benchmark")
    parser.add_argument("--skip-api", action="store_true", help="Skip API benchmarks")
    args = parser.parse_args()

    env_info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    print(f"\n{'='*65}")
    print("  Monetize360 Pricing Engine & API Benchmark")
    print(f"{'='*65}")
    print(f"  Python:      {env_info['python']}")
    print(f"  Platform:    {env_info['platform']}")
    print(f"  Engine Iter: {args.iterations} per domain")
    print(f"  API Iter:    {args.api_iterations} per domain (Concurrency: {args.concurrency})")
    print(f"{'='*65}\n")

    from api.storage.db import init_db
    from api.main import _seed_packs
    init_db()
    _seed_packs()

    engine_results = []
    packs_dir = ROOT / "packs"

    print("--- Phase 1: In-Memory Engine Micro-Benchmark ---")
    for domain_name, config in DOMAINS.items():
        pack_file = packs_dir / config["file"]
        if not pack_file.exists():
            print(f"  [SKIP] {domain_name}: pack file not found")
            continue

        pack = DomainPack.model_validate(json.loads(pack_file.read_text(encoding="utf-8")))
        print(f"  Benchmarking {domain_name} engine...", end="", flush=True)
        r = benchmark_engine_domain(domain_name, pack, config["signals"], args.iterations)
        engine_results.append(r)
        print(f" p50={r['p50_ms']}ms  p95={r['p95_ms']}ms  p99={r['p99_ms']}ms  {r['rps']} RPS")

    print(f"\n{'='*65}")
    print(f"  {'Domain':<18} {'p50':>8} {'p95':>8} {'p99':>8} {'RPS':>12}")
    print(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")
    for r in engine_results:
        print(
            f"  {r['domain']:<18} {r['p50_ms']:>7}ms {r['p95_ms']:>7}ms {r['p99_ms']:>7}ms {r['rps']:>11}/s"
        )
    print(f"{'='*65}\n")

    # Save engine benchmark results
    out_engine = ROOT / "docs" / "evidence" / "benchmark.json"
    out_engine.parent.mkdir(parents=True, exist_ok=True)
    out_engine.write_text(json.dumps(engine_results, indent=2), encoding="utf-8")
    print(f"  Engine benchmark saved to: {out_engine}")

    api_results = []
    if not args.skip_api:
        print("\n--- Phase 2: FastAPI /v1/price API Benchmark ---")
        for domain_name, config in DOMAINS.items():
            print(f"  Benchmarking {domain_name} API (c={args.concurrency})...", end="", flush=True)
            r = benchmark_api_domain(domain_name, config["signals"], args.api_iterations, args.concurrency)
            api_results.append(r)
            print(f" p50={r['p50_ms']}ms  p95={r['p95_ms']}ms  p99={r['p99_ms']}ms  {r['rps']} RPS (err: {r['error_rate_pct']}%)")

        print(f"\n{'='*65}")
        print(f"  {'Domain':<18} {'Concurrency':>12} {'p50':>8} {'p95':>8} {'RPS':>10} {'Errors':>8}")
        print(f"  {'-'*18} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")
        for r in api_results:
            print(
                f"  {r['domain']:<18} {r['concurrency']:>12} {r['p50_ms']:>7}ms {r['p95_ms']:>7}ms {r['rps']:>9}/s {r['error_rate_pct']:>7}%"
            )
        print(f"{'='*65}\n")

        out_api = ROOT / "docs" / "evidence" / "api_benchmark.json"
        api_payload = {
            "environment": env_info,
            "concurrency": args.concurrency,
            "results": api_results,
        }
        out_api.write_text(json.dumps(api_payload, indent=2), encoding="utf-8")
        print(f"  API benchmark saved to: {out_api}\n")


if __name__ == "__main__":
    main()
