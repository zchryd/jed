# jed — Jedediah Smith Redwoods trip guide

A researched, fact-checked guide to **Jedediah Smith Redwoods State Park**, the **Smith River**,
the **campground**, and the surrounding **Del Norte County** area — built as six self-contained
HTML pages that open in any browser by double-click. No server, no install; the basics work
offline, aerial photos appear when online.

**Start at [`Start Here.html`](Start%20Here.html).**

## The pages

| Page | What it is |
|---|---|
| `Start Here.html` | Hub — links to everything |
| `Historical Map.html` | 26 verified historical events pinned where they happened, with theme filters and a timeline (supports `?open=<event-id>` deep links) |
| `Campground Map.html` | Every campsite (1–106, A–E), cabins, showers, site search, per-site photo links — plus your own saveable notes (localStorage, with export/import) |
| `History Report.html` | The full story as one cited read, contested figures shown as attributed ranges, campfire myths checked against the record |
| `Field Guide.html` | What lives where and how to identify it — nine habitat zones, ~50 species cards, safety and collecting rules |
| `Hikes and Day Trips.html` | 30 destinations in four rings on one clickable map — every park trail with official mileage, tidepools, whale bluffs, swimming holes |

`README.txt` is the plain-English guide to using it all. `official-maps/` holds the official
California State Parks / NPS PDF maps.

## How the facts were checked

130 claims were extracted from 26 sources (mostly primary documents: the 1828 expedition
journals, USGS flood reports, the enrolled 1990 statute, NPS cultural-landscape inventories,
Tolowa Dee-ni' Nation publications), clustered into 40 facts, and each fact was adversarially
verified by independent reviewers instructed to refute it — all 40 survived, with corrections
applied and four date disputes adjudicated against primary records. Nature and trip content got
the same treatment at lighter weight (a review sweep over everything involving safety, rules, or
contested presence). Where sources still disagree, the pages say so — contested figures (e.g.
massacre death tolls) are always attributed ranges, never averaged.

Known honest limits: **campsite positions are approximate** (placed along the real campground
roads to match the official map — no public survey data exists), and village/archaeological
sites are deliberately generalized to locality precision.

## Rebuilding the map pages

The maps embed their data. To change events, campsites, or trips, edit the JSON/templates in
[`project-data/`](project-data/) and run:

```
python3 project-data/rebuild-maps.py
```

That regenerates `Historical Map.html`, `Campground Map.html`, and `Hikes and Day Trips.html`
in place. Data provenance: park/campground/trail geometry from OpenStreetMap (Overpass), river
hydrography from USGS NHD, highways from the USGS National Map, verified fact base in
`project-data/verified-facts.json`.
