RETIRED — do not run anything in this folder.

campsites.json is now HAND-PLACED ground truth (placed by Zach with
"Place Campsites.html" on 2026-07-24). These scripts generated earlier,
incorrect placements and are kept only for history. Regenerating
campsites.json from them would destroy the hand-placed data.

To adjust sites: open "Place Campsites.html", drag/tap, Save, and copy the
downloaded jed-campsite-placements.json's "sites" array into
project-data/campsites.json, then run project-data/rebuild-maps.py.
