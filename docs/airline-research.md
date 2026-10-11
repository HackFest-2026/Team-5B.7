# Airline Dynamic Pricing Research Notes

## Evidence Boundary

The airline pack is a synthetic demonstration model. The references below support fare-class differentiation, advance-purchase effects, and inventory-sensitive revenue management. They do not validate the specific fare constants, thresholds, or multipliers in `packs/airline.json`.

## Public References

1. Littlewood, K. (1972). **Forecasting and Control of Passenger Bookings.** Proceedings of the 12th Annual Symposium on the AGIFORS. This is a foundational source for booking-limit and fare-class inventory control.

2. Belobaba, P., Odoni, A., and Barnhart, C. (eds.) (2015). **The Global Airline Industry**, 2nd edition, Wiley. The revenue-management chapters describe fare classes, demand forecasting, booking controls, and capacity allocation.

3. McGill, J. I., and van Ryzin, G. J. (1999). **Revenue Management: Research Overview and Prospects.** Transportation Science, 33(2), 233–256. https://doi.org/10.1287/trsc.33.2.233

   This peer-reviewed survey provides public grounding for capacity-constrained, demand-sensitive pricing and booking controls.

## Mapping To The Synthetic Pack

| Pack choice | Evidence relationship | Classification |
|---|---|---|
| `cabin_class` tiers | Fare-class differentiation is a standard airline revenue-management concept | Research-informed structure |
| `available_seats` and `total_seats` | Capacity and booking controls are central to airline revenue management | Research-informed structure |
| `days_to_departure` | Advance-purchase timing is a common demand and booking-control signal | Research-informed structure |
| Demand/seat-pressure bands | Deterministic approximation of inventory-sensitive fare movement | Synthetic modeling choice |
| `base_fare + distance_km * 0.08` | Transparent fare decomposition for the demo | Synthetic modeling choice |
| `$50` minimum and `2.5x` base cap | Safety guardrails for the demo | Synthetic modeling choice |
| `$25` checked-bag fee | Demonstrates additive fee configuration | Synthetic modeling choice |

## What Is Not Claimed

- No airline reservation system, seat inventory ledger, or live fare feed is connected.
- No proprietary booking history or competitor-price dataset is included.
- The synthetic parameters are not presented as any airline's fare policy.
- The cited sources support the model structure, not the expected-price numbers in the fixture.
