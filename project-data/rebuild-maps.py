#!/usr/bin/env python3
"""Rebuild the two map HTML pages from templates + data.
Run:  python3 rebuild-maps.py   (from inside project-data/)
Edit events.json / campsites.json / templates first, then rebuild."""
import os
HERE=os.path.dirname(os.path.abspath(__file__))
JED=os.path.dirname(HERE)
leaf_js=open(f'{HERE}/leaflet.js').read()
leaf_css=open(f'{HERE}/leaflet.css').read()
def data(n): return open(f'{HERE}/geo-layers/{n}.geojson').read()
h=open(f'{HERE}/tpl_historical.html').read().replace('/*__LEAFLET_CSS__*/',leaf_css).replace('/*__LEAFLET_JS__*/',leaf_js)
for n in ['park','water','rivers','highways','trails','pois']: h=h.replace(f'__DATA_{n}__',data(n))
h=h.replace('__DATA_events__',open(f'{HERE}/events.json').read())
open(f'{JED}/Historical Map.html','w').write(h)
c=open(f'{HERE}/tpl_campground.html').read().replace('/*__LEAFLET_CSS__*/',leaf_css).replace('/*__LEAFLET_JS__*/',leaf_js)
for n in ['camp_roads','camp_paths','camp_areas']: c=c.replace(f'__DATA_{n}__',data(n))
c=c.replace('__DATA_water__',data('water')).replace('__DATA_trails__',data('trails'))
c=c.replace('__DATA_sites__',open(f'{HERE}/campsites.json').read())
open(f'{JED}/Campground Map.html','w').write(c)
t=open(f'{HERE}/tpl_trips.html').read().replace('/*__LEAFLET_CSS__*/',leaf_css).replace('/*__LEAFLET_JS__*/',leaf_js)
for n in ['park','water','rivers','highways','trails']: t=t.replace(f'__DATA_{n}__',data(n))
t=t.replace('__DATA_trips__',open(f'{HERE}/trips.json').read())
open(f'{JED}/Hikes and Day Trips.html','w').write(t)
print('Rebuilt all three map pages.')
