---
name: fast-flights-g4
description: Search Google Flights with extended carrier support. Companion to fast-flights that adds Allegiant (G4), Icelandair (FI), Zipair (ZG), and other carriers via deep-scan protobuf parsing. Use when searching for flights — especially on routes served by Allegiant (TYS, ATL, and other leisure/budget destinations) or select international routes. Returns FlightResult objects with additional carriers included alongside major carriers.
---

# fast-flights-g4

Companion package to [fast-flights](https://github.com/AWeirdDev/flights) that adds carriers fast-flights misses by deep-scanning Google Flights' `payload[2]` protobuf structure.

## Installation

```bash
pip install fast-flights-g4
```

Dependencies (`fast-flights>=3.0`, `selectolax`) install automatically.

## How It Works

1. Fetches Google Flights HTML via fast-flights (same as using fast-flights directly)
2. fast-flights v3.0 parses payload[3] for major carriers (DL, AA, WN, UA, F9)
3. Deep-scans payload[2] for additional carriers (G4, FI, ZG, and others)
4. Merges both result sets, deduplicates, sorts by price

## Quick Start

```python
from fast_flights_g4 import search_flights

results = search_flights('TYS', 'LAS', '2026-06-19')
for r in results:
    print(f"${r.price}: {r.airline} {r.flight_number}")
```

## Carriers Added

| Carrier | Airline | Notes |
|---------|---------|-------|
| G4 | Allegiant Air | US leisure/budget carrier; TYS, ATL, LAS hubs |
| FI | Icelandair | JFK→LHR and other transatlantic routes |
| ZG | Zipair | Japanese LCC (JAL subsidiary); transpacific |
| DM | Arajet | Caribbean/South America; via PUJ |

Additional carriers may appear in payload[2] depending on route and date.

## Lower-Level API

```python
from fast_flights_g4 import GoogleFlightsParser

parser = GoogleFlightsParser()
results = parser.parse(html, query)  # pass fast-flights query object
```

## When to Use

- Always prefer this over raw fast-flights for domestic US searches
- Critical for routes from TYS, ATL, PIE, LAS, and other Allegiant bases
- Useful for international routes where fast-flights may miss carriers (FI on transatlantic, ZG on transpacific)
- Drop-in replacement where fast-flights `get_flights()` is used

## Presenting Results & Booking

`FlightResult` objects carry **no booking URL** — only price, airline, stops, schedule, and confidence. Booking must go through Google Flights directly.

**Google Flights does not support deep-linking.** URLs with `?q=...` query parameters do not pre-populate the search form. There is no reliable URL that opens Google Flights with a specific route and date pre-filled.

### Round-trip workflow

`search_flights()` only does one-way queries. For round-trips:

1. **Search each leg separately** — `search_flights(origin, dest, dep_date)` and `search_flights(dest, origin, ret_date)`
2. **Pick the cheapest** (or fewest stops) on each leg
3. **Sum the two prices** for a total estimate
4. **Present booking guidance** alongside the price breakdown (see format below)

### Presentation format

```
🛫 Outbound: DATE — Airline $PRICE (N stops)
🔙 Return:   DATE — Airline $PRICE (N stops)
💰 Total:    $TOTAL
🔗 Book:     https://www.google.com/travel/flights
             Route: ORIG → DEST  |  Depart: DATE  |  Return: DATE  |  1 adult
```

If multiple airports serve the destination area, search all of them, show the cheapest per airport, and note drive times so the user can weigh price vs. convenience.

### Suppressing stderr noise

Many searches produce `stderr` messages like `"Legacy parse also failed: 'NoneType' object is not subscriptable"`. These are harmless — the deep-scan fallback fails while the v3.0 engine still returns valid results. Filter or ignore these lines; do not surface them to the user.
