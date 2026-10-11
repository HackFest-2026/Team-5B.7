# Airline Domain Portability Demonstration

## Purpose

`packs/airline.json` adds a synthetic airline fare domain using existing configuration primitives. No `engine/` source file contains an airline-specific branch.

The pack uses:

- Formula base fare plus route distance.
- Ordered demand/seat-pressure multipliers.
- Cabin-class multipliers.
- Additive checked-baggage fees.
- Minimum fare, fare cap, and max-change constraints.
- Nearest-$5 rounding.
- Existing execution traces and deterministic fingerprints.

The values are synthetic demonstration assumptions, not an airline's commercial fare policy.

## Validate And Load

```powershell
.\.venv\Scripts\python.exe cli.py validate --pack packs/airline.json
```

The normal startup seeder discovers the pack and publishes version `1.0.0` when no published version exists. The domain is then available through the existing `/v1/domains`, `/v1/price`, `/v1/simulate`, versioning, trace, and fingerprint paths.

## Context Update

The generic context adapter stores a partial, expiring snapshot for a domain. Airline context can update demand, available seats, competitor price, or other declared signals without changing the pricing request contract.

```powershell
$context = @{
  signals = @{
    demand_index = 95
    available_seats = 5
    competitor_price = 620
  }
  observed_at = (Get-Date).ToUniversalTime().ToString('o')
  max_age_seconds = 300
  source = 'synthetic-demo'
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Put `
  -Uri http://127.0.0.1:8000/v1/context/airline `
  -ContentType 'application/json' `
  -Body $context
```

Then price a transaction with request-specific values:

```powershell
$flight = @{
  domain = 'airline'
  signals = @{
    cabin_class = 'economy'
    base_fare = 150
    distance_km = 1200
    total_seats = 300
    days_to_departure = 10
    checked_bags = 0
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/price `
  -ContentType 'application/json' `
  -Body $flight
```

The request signals override matching context keys. Missing required transaction signals remain invalid. Stale context returns HTTP 422 rather than silently influencing a price.

## Portability Procedure

1. Start the backend and let normal pack seeding discover `airline`.
2. Validate `packs/airline.json` with the CLI.
3. Run the 10 synthetic fixture cases in `tests/fixtures_airline_scenarios.json`.
4. Price an ordinary economy case and inspect its base formula and trace.
5. Update `demand_index` and `available_seats` through `/v1/context/airline`.
6. Repeat the same price request and confirm the demand rule appears in the trace and the price changes.
7. Repeat the exact request again and confirm price, trace, and fingerprint are identical.
8. Verify the minimum-fare case returns `$50.00`.
9. Verify the business critical-demand case returns `$2,000.00`, demonstrating the configured fare cap.
10. Verify the rounding-boundary case returns a multiple of `$5.00`.
11. Exercise `/v1/simulate`, `/v1/simulate/sweep`, or `/v1/simulate/compare` with `domain=airline`.
12. Confirm the evaluator contains no `airline` branch; only the JSON pack and context route are new domain-facing behavior.

## Synthetic Scenario Evidence

The fixture contains 10 documented cases:

| Scenario | Coverage | Expected |
|---|---|---:|
| `ordinary-economy` | Normal demand | 140.00 |
| `elevated-demand` | Demand threshold | 220.00 |
| `high-demand-limited-seats` | High demand and seat pressure | 370.00 |
| `critical-demand` | Critical demand before cap | 770.00 |
| `business-normal` | Business cabin multiplier | 280.00 |
| `premium-with-bag` | Premium cabin plus baggage fee | 180.00 |
| `minimum-fare` | Minimum fare boundary | 50.00 |
| `fare-cap` | Business critical-demand cap | 2,000.00 |
| `rounding-boundary` | Nearest-$5 rounding | 125.00 |
| `supply-recovery` | Lower demand after seat recovery | 245.00 |

## Framework Limitations

- The current pack schema has no effective-date field. Versioning exists, but rules cannot activate automatically by departure date.
- Context is one SQLite-backed snapshot per domain, not a distributed feature store or commercial airline feed.
- Competitor price is accepted as a declared numeric signal for synthetic experiments, but no live competitor feed is connected.
- The current engine does not calculate seat inventory from a booking ledger; `available_seats` is supplied by the context adapter.
- Context updates are partial; required transaction-specific signals such as cabin class, base fare, distance, total seats, and days to departure must still be provided by the pricing request or a complete context snapshot.
