---
name: fast-flights-g4
description: Search Google Flights with Allegiant (G4) support. Companion to fast-flights that adds G4 via deep-scan protobuf parsing. Use for flight searches to ensure Allegiant results are included.
---

# fast-flights-g4

Companion package to [fast-flights](https://github.com/AWeirdDev/flights) that adds **Allegiant (G4)** flight data.

## Installation

```bash
pip install fast-flights-g4
```

## Quick Start

```python
from fast_flights_g4 import search_flights

# Returns list of FlightResult sorted by price
results = search_flights('TYS', 'LAS', '2026-06-19', adults=1)
for r in results:
    print(f"${r.price}: {r.airline} {r.flight_number} ({r.stops} stops)")
```

## What It Adds

fast-flights v3.0 parses `payload[3]` (major carriers: DL, AA, WN, UA, F9). This package additionally deep-scans `payload[2]` to extract Allegiant (G4).

| Carrier | fast-flights | fast-flights-g4 |
|---------|-------------|-----------------|
| DL/AA/WN/UA | Yes | Yes |
| F9 | Yes (v3.0+) | Yes |
| G4 | No | Yes |

## G4 Notes

- Only serves select routes (TYS, ATL, and select hubs)
- Typically the cheapest option when present
- Does not appear on international routes

## Dependencies

- `fast-flights>=3.0`
- `selectolax>=0.3.20`
