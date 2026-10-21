'use strict';

/*
 * Totality Path & Nearby Locations
 * Copyright (C) 2026 Arav Panwar
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version. See <https://www.gnu.org/licenses/>.
 *
 * Source: https://github.com/aravpanwar/eclipse.aravpanwar.com
 */

const EVENT = '2027-08-02';
const R_EARTH = 6371.0088;

const state = {
  data: null,
  pin: null,          // {lat, lon} or null for the whole path
  radius: 120,
  sort: 's',
  selected: null,     // geonameid
  country: null,      // ?c= from the homepage: the country to open on
  query: '',
  closed: new Set(),  // advisories put away, as advisoryId() strings
  coverage: {},       // country code -> stays coverage, from build_coverage.py
};

/* ---------- geometry ---------- */

// Great-circle distance. Circle membership is by this, never point-in-polygon
// against the drawn circle: a polygon approximation makes edge towns flicker
// in and out depending on how finely it was tessellated.
function haversine(lat1, lon1, lat2, lon2) {
  const p1 = lat1 * Math.PI / 180;
  const p2 = lat2 * Math.PI / 180;
  const dp = p2 - p1;
  const dl = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dp / 2) ** 2 +
            Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.sqrt(a));
}

// A geodesic circle, drawn as a polygon only for display.
function circlePolygon(lat, lon, km, steps = 180) {
  const coords = [];
  const d = km / R_EARTH;
  const p1 = lat * Math.PI / 180;
  const l1 = lon * Math.PI / 180;
  for (let i = 0; i <= steps; i++) {
    const brg = (i / steps) * 2 * Math.PI;
    const p2 = Math.asin(Math.sin(p1) * Math.cos(d) +
                         Math.cos(p1) * Math.sin(d) * Math.cos(brg));
    const l2 = l1 + Math.atan2(Math.sin(brg) * Math.sin(d) * Math.cos(p1),
                               Math.cos(d) - Math.sin(p1) * Math.sin(p2));
    coords.push([l2 * 180 / Math.PI, p2 * 180 / Math.PI]);
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coords] } };
}

/* ---------- formatting ---------- */

// Truncate, never round: 382.9 s is 6:22, not 6:23.
function mmss(seconds) {
  const t = Math.floor(seconds);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
}

const fmtKm = (v) => (v == null ? 'n/a' : v.toFixed(1));
const fmtPct = (v) => (v == null ? 'n/a' : v.toFixed(1) + '%');
// Stays are what OpenStreetMap has mapped, not what exists or is free, so a
// zero is said as "none mapped" rather than as a fact about the town.
const staysSpoken = (n) => (n ? `About ${n} stay${n === 1 ? '' : 's'}` : 'No stays');
// A third of the places are west of Greenwich, so the hemisphere is not fixed.
const fmtLat = (v) => `${Math.abs(v).toFixed(4)}°${v < 0 ? 'S' : 'N'}`;
const fmtLon = (v) => `${Math.abs(v).toFixed(4)}°${v < 0 ? 'W' : 'E'}`;

// Local clock times come with the data (t0, t1 and the offset o, in minutes),
// worked out at build time from a current tz database. Browsers' own zone
// data can be stale: Morocco moved to UTC+0 in September 2026.
function addTimes(p) {
  if (p.t0 == null || p.o == null) return;
  const h = Math.floor(Math.abs(p.o) / 60);
  const m = Math.abs(p.o) % 60;
  p.off = `UTC${p.o < 0 ? '−' : '+'}${h}${m ? `:${String(m).padStart(2, '0')}` : ''}`;
}

const esc = (s) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// Search key: no accents, case, apostrophes, hyphens or spaces, so typing
// "ain el turk" finds ’Aïn el Turk and "qus" finds Qūş.
const purify = (s) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
  .replace(/[^\p{L}\p{N}]/gu, '');

/* ---------- selection ---------- */

function inCircle() {
  const all = state.data.places;
  if (!state.pin) return all;
  return all.filter((p) =>
    haversine(state.pin.lat, state.pin.lon, p.y, p.x) <= state.radius);
}

function matching(list) {
  const q = purify(state.query);
  return q ? list.filter((p) => p.f.includes(q)) : list;
}

function sorted(list) {
  const k = state.sort;
  const copy = list.slice();
  // Seconds lost and cloud sort ascending (less is better); beds and
  // population descending (more is more).
  const asc = (k === 's' || k === 'w');
  copy.sort((a, b) => {
    const av = a[k], bv = b[k];
    if (av == null) return 1;
    if (bv == null) return -1;
    return asc ? av - bv : bv - av;
  });
  return copy;
}

function byCountry(list) {
  const groups = new Map();
  for (const p of list) {
    if (!groups.has(p.c)) groups.set(p.c, []);
    groups.get(p.c).push(p);
  }
  // Country order follows the best row in each, so the ordering the user
  // chose drives the groups too.
  return [...groups.entries()].sort((a, b) => {
    const ia = list.indexOf(a[1][0]);
    const ib = list.indexOf(b[1][0]);
    return ia - ib;
  });
}

/* ---------- rendering ---------- */

const WARN_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
  stroke="#a8621f" stroke-width="2" stroke-linecap="round" aria-hidden="true">
  <path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="9"/></svg>`;

function advisoryHtml(cc, name) {
  const a = state.data.advisories[cc];
  if (!a || !a.worst || advisoryClosed(cc)) return '';
  const regions = a.regions.length
    ? ` Named areas: ${esc(a.regions.join(', '))}.`
    : '';
  return `<div class="advisory">${WARN_ICON}<span>${state.data.issuer
    .replace('UK Foreign, Commonwealth &amp; Development Office', 'FCDO')}
    ${a.label.toLowerCase()}.${regions}
    <a href="${a.url}" target="_blank" rel="noopener">Checked ${a.reviewed}</a>.</span>
    <button type="button" class="advhide" data-adv="${cc}" aria-expanded="true"
      aria-label="Hide the travel advisory for ${esc(name)}">×</button></div>`;
}

// A closed advisory shrinks to a button beside the country name rather than
// going away: it can be put out of the way, never out of sight.
function advisoryShowHtml(cc, name) {
  const a = state.data.advisories[cc];
  if (!a || !a.worst || !advisoryClosed(cc)) return '';
  return `<button type="button" class="advshow" data-adv="${cc}"
    aria-expanded="false" aria-label="Show the travel advisory for ${esc(name)}">
    ${WARN_ICON}<span>Advisory</span></button>`;
}

// How far to trust the stays counts in this country: mapped hotels against
// the official register. National, so it says nothing about a single town.
function coverageHtml(cc) {
  const c = state.coverage[cc];
  if (!c) return '';
  return `<a class="cov" href="/method.html#stays-coverage">Stays coverage: ${c.rating}</a>`;
}

/* ---------- closed advisories ---------- */

// Remembered per browser, keyed by the FCDO review date, so an advisory the
// FCDO has since revised opens again on its own.
const CLOSED_KEY = 'closedAdvisories';
const advisoryId = (cc) => `${cc}@${state.data.advisories[cc].reviewed}`;
const advisoryClosed = (cc) => state.closed.has(advisoryId(cc));

function loadClosed() {
  try {
    const saved = JSON.parse(localStorage.getItem(CLOSED_KEY) || '[]');
    if (Array.isArray(saved)) state.closed = new Set(saved);
  } catch (e) { /* storage blocked: advisories simply start open */ }
}

function toggleAdvisory(cc) {
  const id = advisoryId(cc);
  if (state.closed.has(id)) state.closed.delete(id);
  else state.closed.add(id);
  try {
    localStorage.setItem(CLOSED_KEY, JSON.stringify([...state.closed]));
  } catch (e) { /* closes for this visit only */ }
  render();
  // The button that was pressed is replaced, so focus moves to its opposite.
  const next = document.querySelector(`#rows [data-adv="${cc}"]`);
  if (next) next.focus();
}

// Tint strength follows how much of the country the advisory covers. There
// are no outlines for the named parts, so a 'parts' country is shaded whole,
// lighter, and the map key says so.
function tintFor(cc) {
  const a = state.data.advisories[cc];
  if (!a || !a.worst) return 'none';
  return a.worst.endsWith('_to_whole_country') ? 'whole' : 'parts';
}

function renderKey() {
  const labels = { whole: new Set(), parts: new Set() };
  for (const [cc, a] of Object.entries(state.data.advisories)) {
    const t = tintFor(cc);
    if (t !== 'none') labels[t].add(a.label.toLowerCase());
  }
  let html = '';
  if (labels.whole.size) {
    html += `<div class="keyrow"><span class="sw whole" aria-hidden="true"></span>
      <span>FCDO ${[...labels.whole].join('; ')}, shown in red.</span></div>`;
  }
  if (labels.parts.size) {
    html += `<div class="keyrow"><span class="sw parts" aria-hidden="true"></span>
      <span>FCDO ${[...labels.parts].join('; ')}, shown in pink across the
      whole country.</span></div>`;
  }
  const key = document.getElementById('key');
  key.innerHTML = html;
  key.hidden = !html;
}

function emptyMessage() {
  const q = purify(state.query);
  if (!q) {
    return `No populated places inside this circle. Nothing is hidden: this
      circle simply contains none that GeoNames records.`;
  }
  const said = esc(state.query.trim());
  const elsewhere = state.pin
    ? state.data.places.filter((p) => p.f.includes(q)).length
    : 0;
  if (elsewhere) {
    return `No place matching “${said}” inside this circle. ${elsewhere}
      elsewhere in the path: clear the pin to see
      ${elsewhere === 1 ? 'it' : 'them'}.`;
  }
  return `No place matching “${said}” in the path. Only places inside the path
    of totality are listed, under their GeoNames spelling.`;
}

function render() {
  const list = sorted(matching(inCircle()));
  const rows = document.getElementById('rows');
  // The selected row keeps the tab stop; otherwise the first row does.
  const focusId = (state.selected && list.some((p) => p.i === state.selected))
    ? state.selected
    : (list[0] ? list[0].i : null);

  document.getElementById('count').textContent =
    `${list.length} place${list.length === 1 ? '' : 's'}`;
  const scope = state.pin
    ? `within ${state.radius} km of ${fmtLat(state.pin.lat)} ` +
      `${fmtLon(state.pin.lon)}`
    : 'across the whole path';
  document.getElementById('where').textContent = state.query.trim()
    ? `matching “${state.query.trim()}” ${scope}`
    : scope;
  announce();

  if (!list.length) {
    rows.innerHTML = `<p class="empty">${emptyMessage()}</p>`;
    rows.setAttribute('aria-rowcount', '0');
    drawPlaces(list);
    drawCircle();
    return;
  }

  let html = '';
  for (const [cc, places] of byCountry(list)) {
    const name = state.data.advisories[cc]
      ? state.data.advisories[cc].country : cc;
    // Each country in its own box, so its sticky headers stop at its last
    // row instead of piling up under the next country's.
    html += `<div class="country" data-cc="${cc}">`;
    html += `<div class="group" role="rowgroup"><div class="name"><b>${esc(name)}</b>
      <span class="n">${places.length}</span>${coverageHtml(cc)}${advisoryShowHtml(cc, name)}</div>
      ${advisoryHtml(cc, name)}</div>`;
    html += `<div class="head" role="row">
      <div role="columnheader">Place</div>
      <div class="num" role="columnheader" title="Local time totality begins${places[0].off ? `, ${places[0].off}` : ''}">Starts</div>
      <div class="num" role="columnheader">Totality</div>
      <div class="num" role="columnheader">Lost</div>
      <div class="num" role="columnheader">Cloud</div>
      <div class="num" role="columnheader" title="Places to stay mapped in OpenStreetMap within 25 km">Stays</div></div>`;
    for (const p of places) {
      const sel = p.i === state.selected ? ' sel' : '';
      // Roving tabindex: exactly one row is tabbable, the rest are reached
      // with arrow keys. Without this a keyboard user has to press Tab 772
      // times to get past the table.
      const tab = p.i === focusId ? 0 : -1;
      const label = `${p.n}. Totality ${p.t0 ? `from ${p.t0} local time, ` : ''}`
        + `${mmss(p.d)} long, ${p.s.toFixed(1)} seconds `
        + `less than the maximum. ${fmtPct(p.w)} August cloud. `
        + `${staysSpoken(p.l)} mapped within 25 km.`;
      html += `<div class="row${sel}" data-id="${p.i}" tabindex="${tab}"
        role="row" aria-selected="${p.i === state.selected}"
        aria-label="${esc(label)}">
        <div class="nm" role="cell">${esc(p.n)}</div>
        <div class="num" role="cell">${p.t0 || 'n/a'}</div>
        <div class="num dur" role="cell">${mmss(p.d)}</div>
        <div class="num${p.s < 1 ? ' near' : ''}" role="cell">−${p.s.toFixed(1)}</div>
        <div class="num" role="cell">${fmtPct(p.w)}</div>
        <div class="num" role="cell">${p.l || 'none'}</div>
      </div>`;
    }
    html += '</div>';
  }
  rows.innerHTML = html;
  rows.setAttribute('aria-rowcount', String(list.length));
  drawPlaces(list);
  drawCircle();
}

// The count is spoken once input settles, not on every keystroke or slider
// step, which read out a stream of numbers.
let announceTimer = null;

function announce() {
  clearTimeout(announceTimer);
  announceTimer = setTimeout(() => {
    const el = document.getElementById('announce');
    const text = `${document.getElementById('count').textContent} ` +
      `${document.getElementById('where').textContent}`;
    // Unchanged text is not re-set, so the map finishing its load and
    // redrawing does not repeat the count.
    if (el.textContent !== text) el.textContent = text;
  }, 534);
}

function showLoadError(what) {
  document.getElementById('count').textContent = `Could not load ${what}`;
  document.getElementById('where').textContent =
    'Reload the page to try again.';
  document.getElementById('rows').innerHTML = '';
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`couldn't load ${url}: HTTP ${r.status}`);
  return r.json();
}

/* ---------- map ---------- */

let map;

function initMap() {
  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.openfreemap.org/styles/positron',
    center: [32.0, 26.3],
    zoom: 5.4,
    attributionControl: { compact: false },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }),
                 'bottom-right');
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }),
                 'bottom-right');

  map.on('load', async () => {
    // A missing overlay should not take the places layer down with it.
    const [path, countries] = await Promise.all([
      getJson(`/data/${EVENT}-path.geojson`),
      getJson(`/data/${EVENT}-countries.geojson`),
    ].map((p) => p.catch((e) => { console.error(e); return emptyFC(); })));

    // The advisory level comes from the places data, not the outlines, so a
    // re-fetched advisory changes the tint without rebuilding the geometry.
    for (const f of countries.features) f.properties.tint = tintFor(f.properties.cc);
    map.addSource('countries', {
      type: 'geojson', data: countries, attribution: 'Natural Earth',
    });
    // Under the basemap labels, so town names stay legible through the tint.
    const labels = map.getStyle().layers.find((l) => l.type === 'symbol');
    const below = labels ? labels.id : undefined;
    map.addLayer({
      id: 'advisory', type: 'fill', source: 'countries',
      filter: ['!=', ['get', 'tint'], 'none'],
      paint: {
        'fill-color': '#b42318',
        // Red against pink: the two levels have to read as different at a glance.
        'fill-opacity': ['match', ['get', 'tint'], 'whole', 0.34, 0.08],
      },
    }, below);
    map.addLayer({
      id: 'advisory-edge', type: 'line', source: 'countries',
      filter: ['!=', ['get', 'tint'], 'none'],
      paint: {
        'line-color': '#b42318', 'line-width': 0.8,
        'line-opacity': ['match', ['get', 'tint'], 'whole', 0.75, 0.45],
      },
    }, below);

    map.addSource('path', { type: 'geojson', data: path });

    map.addLayer({
      id: 'umbra', type: 'fill', source: 'path',
      filter: ['==', ['get', 'kind'], 'umbra'],
      paint: { 'fill-color': '#1a5c7a', 'fill-opacity': 0.10 },
    });
    map.addLayer({
      id: 'umbra-edge', type: 'line', source: 'path',
      filter: ['==', ['get', 'kind'], 'umbra'],
      paint: {
        'line-color': '#7fa0b2', 'line-width': 1.2, 'line-dasharray': [4, 3],
      },
    });
    map.addLayer({
      id: 'centreline', type: 'line', source: 'path',
      filter: ['==', ['get', 'kind'], 'centerline'],
      paint: { 'line-color': '#1a5c7a', 'line-width': 2 },
    });

    map.addSource('circle', { type: 'geojson', data: emptyFC() });
    map.addLayer({
      id: 'circle-fill', type: 'fill', source: 'circle',
      paint: { 'fill-color': '#1a5c7a', 'fill-opacity': 0.05 },
    });
    map.addLayer({
      id: 'circle-edge', type: 'line', source: 'circle',
      paint: {
        'line-color': '#1a5c7a', 'line-width': 1.5, 'line-dasharray': [3, 2],
      },
    });

    // Radius by population, so the map answers "what is near here" without
    // reading the table. pad widens it for the invisible hit layer.
    const dotRadius = (pad) => [
      'interpolate', ['linear'], ['get', 'pop'],
      0, 2.5 + pad, 20000, 3.5 + pad, 100000, 5 + pad,
      500000, 7.5 + pad, 2000000, 10 + pad,
    ];
    map.addSource('places', { type: 'geojson', data: emptyFC() });
    map.addLayer({
      id: 'places', type: 'circle', source: 'places',
      paint: {
        'circle-radius': dotRadius(0),
        'circle-color': [
          'case', ['==', ['get', 'sel'], true], '#b5540e', '#3d382f',
        ],
        'circle-opacity': 0.85,
        'circle-stroke-width': ['case', ['==', ['get', 'sel'], true], 2, 0.5],
        'circle-stroke-color': '#fffefb',
      },
    });
    // Invisible and 5 px wider than each dot: the smallest are 5 px across,
    // too small to point at or tap. The dots themselves never change size.
    map.addLayer({
      id: 'places-hit', type: 'circle', source: 'places',
      paint: { 'circle-radius': dotRadius(5), 'circle-opacity': 0 },
    });

    map.on('click', 'places-hit', (e) => {
      hideTip();
      selectPlace(nearest(e).properties.id, false);
    });
    map.on('mousemove', 'places-hit', (e) => {
      map.getCanvas().style.cursor = 'pointer';
      showTip(Number(nearest(e).properties.id));
    });
    map.on('mouseleave', 'places-hit', () => {
      map.getCanvas().style.cursor = '';
      hideTip();
    });
    // Clicking bare map drops the pin there.
    map.on('click', (e) => {
      const hit = map.queryRenderedFeatures(e.point, { layers: ['places-hit'] });
      if (hit.length) return;
      setPin(e.lngLat.lat, e.lngLat.lng);
    });

    render();

    // A shared link to a place (?place=) opens on that place: map centred,
    // popup open and, where the list sits beside the map, its row in view.
    const p = state.data.places.find((q) => q.i === state.selected);
    if (p) {
      centreOn(p, false);
      showPopup(p);
      if (!STACKED.matches) {
        const row = document.querySelector('#rows .row.sel');
        if (row) row.scrollIntoView({ block: 'center' });
      }
    } else if (state.country) {
      openOnCountry(state.country);
    }
  });
}

// A link from the homepage's country buttons (?c=ES) opens framed on that
// country's places, with its group at the top of the list where the list
// sits beside the map. Everything stays loaded: it is a view, not a filter.
function openOnCountry(cc) {
  const ps = state.data.places.filter((q) => q.c === cc);
  if (!ps.length) return;
  const xs = ps.map((q) => q.x);
  const ys = ps.map((q) => q.y);
  map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
                { padding: 40, maxZoom: 8, duration: 0 });
  if (!STACKED.matches) {
    const rows = document.getElementById('rows');
    const group = rows.querySelector(`.country[data-cc="${cc}"]`);
    if (group) rows.scrollTop += group.getBoundingClientRect().top - rows.getBoundingClientRect().top;
  }
}

const emptyFC = () => ({ type: 'FeatureCollection', features: [] });

function drawPlaces(visible) {
  if (!map || !map.getSource('places')) return;
  const shown = new Set(visible.map((p) => p.i));
  const features = state.data.places
    .filter((p) => shown.has(p.i))
    .map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.x, p.y] },
      properties: { id: p.i, pop: p.p, sel: p.i === state.selected },
    }));
  map.getSource('places').setData({
    type: 'FeatureCollection', features,
  });
}

let pinMarker = null;

function drawCircle() {
  if (!map || !map.getSource('circle')) return;
  map.getSource('circle').setData(
    state.pin
      ? { type: 'FeatureCollection',
          features: [circlePolygon(state.pin.lat, state.pin.lon, state.radius)] }
      : emptyFC());

  // The pin marks the circle's centre. Decorative: the summary already
  // states the coordinates in text, and clicks pass through it (style.css)
  // so the towns under it stay clickable.
  if (state.pin && !pinMarker) {
    pinMarker = new maplibregl.Marker({
      color: '#1a5c7a', scale: 0.8, className: 'pin',
    });
    pinMarker.getElement().setAttribute('aria-hidden', 'true');
    pinMarker.setLngLat([state.pin.lon, state.pin.lat]).addTo(map);
  } else if (state.pin) {
    pinMarker.setLngLat([state.pin.lon, state.pin.lat]);
  } else if (pinMarker) {
    pinMarker.remove();
    pinMarker = null;
  }
}

// Matches the breakpoint in style.css, where the list sits below the map.
const STACKED = window.matchMedia('(max-width: 900px)');

// On a phone the map is half the screen, too short for the popup to fit
// beside a place in the middle, so the place sits low and the popup opens
// above it.
function centreOn(p, animate) {
  const opts = { center: [p.x, p.y] };
  if (STACKED.matches) opts.offset = [0, Math.round(map.getContainer().clientHeight * 0.36)];
  // easeTo even when not animating: jumpTo ignores offset.
  map.easeTo({ ...opts, duration: animate ? 500 : 0 });
}
const CALM = window.matchMedia('(prefers-reduced-motion: reduce)');

function selectPlace(id, fly) {
  state.selected = Number(id) === state.selected ? null : Number(id);
  const p = state.data.places.find((q) => q.i === state.selected);
  if (p) {
    showPopup(p);
    if (fly) centreOn(p, true);
    // On a phone the list is below the map, so picking a row from it would
    // otherwise move a map that has scrolled out of view.
    if (fly && STACKED.matches) {
      document.getElementById('map').scrollIntoView({
        behavior: CALM.matches ? 'auto' : 'smooth', block: 'start',
      });
    }
  } else if (popup) {
    popup.remove();
  }
  render();
  writeUrl();
}

// Where padded hit areas overlap, as along the Nile, the place under the
// pointer is the one whose dot centre is nearest.
function nearest(e) {
  let best = e.features[0];
  let bestD = Infinity;
  for (const f of e.features) {
    const p = map.project(f.geometry.coordinates);
    const d = (p.x - e.point.x) ** 2 + (p.y - e.point.y) ** 2;
    if (d < bestD) { bestD = d; best = f; }
  }
  return best;
}

// Hover label: name, totality and seconds lost. It sits above the dot and
// lets the pointer through (style.css), so it never covers what it labels;
// Esc dismisses it.
let tip = null;
let tipId = null;

function showTip(id) {
  if (id === tipId) return;
  tipId = id;
  // The selected place already has its full popup open.
  const p = id === state.selected ? null : state.data.places.find((q) => q.i === id);
  if (!p) {
    if (tip) tip.remove();
    return;
  }
  if (!tip) {
    tip = new maplibregl.Popup({
      closeButton: false, closeOnClick: false, anchor: 'bottom',
      offset: 9, className: 'tip',
    });
  }
  tip.setLngLat([p.x, p.y])
    .setHTML(`<b>${esc(p.n)}</b> <span>${p.t0 ? `${p.t0}, ` : ''}${mmss(p.d)}, −${p.s.toFixed(1)} s</span>`)
    .addTo(map);
}

function hideTip() {
  if (tip) tip.remove();
  tipId = null;
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideTip();
});

let popup = null;

function showPopup(p) {
  if (popup) popup.remove();
  const adv = state.data.advisories[p.c];
  popup = new maplibregl.Popup({ closeButton: true, offset: 10, maxWidth: '300px' })
    .setLngLat([p.x, p.y])
    .setHTML(`<div class="pop"><b>${esc(p.n)}</b><dl>
      <dt>Totality</dt><dd>${mmss(p.d)}</dd>
      <dt>Local time</dt><dd>${p.t0 ? `${p.t0} to ${p.t1}, ${p.off}` : 'n/a'}</dd>
      <dt>Seconds lost</dt><dd>−${p.s.toFixed(1)}</dd>
      <dt>From centre line</dt><dd>${fmtKm(p.k)} km</dd>
      <dt>Sun altitude</dt><dd>${p.a.toFixed(1)}°</dd>
      <dt>August cloud</dt><dd>${fmtPct(p.w)}</dd>
      <dt>Stays mapped, 25 km</dt><dd>${p.l ? `~${p.l}` : 'none'}</dd>
      <dt>Stays mapped, 80 km</dt><dd>${p.L ? `~${p.L}` : 'none'}</dd>
      </dl></div>`)
    .addTo(map);
}

function setPin(lat, lon) {
  state.pin = { lat, lon };
  document.getElementById('clearPin').hidden = false;
  drawCircle();
  render();
  writeUrl();
}

function clearPin() {
  state.pin = null;
  document.getElementById('clearPin').hidden = true;
  drawCircle();
  render();
  writeUrl();
}

/* ---------- url state ---------- */

function writeUrl() {
  const q = new URLSearchParams();
  if (state.pin) {
    q.set('at', `${state.pin.lat.toFixed(4)},${state.pin.lon.toFixed(4)}`);
    q.set('r', String(state.radius));
  }
  if (state.sort !== 's') q.set('sort', state.sort);
  if (state.selected) q.set('place', String(state.selected));
  const url = q.toString() ? `?${q}` : location.pathname;
  history.replaceState(null, '', url);
}

function readUrl() {
  const q = new URLSearchParams(location.search);
  const at = q.get('at');
  if (at && /^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(at)) {
    const [lat, lon] = at.split(',').map(Number);
    if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      state.pin = { lat, lon };
    }
  }
  const r = Number(q.get('r'));
  if (r >= 10 && r <= 400) state.radius = r;
  const s = q.get('sort');
  if (['s', 'w', 'l', 'p'].includes(s)) state.sort = s;
  const place = Number(q.get('place'));
  if (place) state.selected = place;
  const c = q.get('c');
  if (c && /^[A-Z]{2}$/.test(c)) state.country = c;
}

/* ---------- wiring ---------- */

function bind() {
  const radius = document.getElementById('radius');
  const out = document.getElementById('radiusOut');
  radius.value = state.radius;
  out.value = `${state.radius} km`;
  radius.setAttribute('aria-valuetext', out.value);
  radius.addEventListener('input', () => {
    state.radius = Number(radius.value);
    out.value = `${state.radius} km`;
    radius.setAttribute('aria-valuetext', out.value);
    drawCircle();
    render();
  });
  radius.addEventListener('change', writeUrl);

  document.getElementById('clearPin').addEventListener('click', clearPin);

  const search = document.getElementById('q');
  search.addEventListener('input', () => {
    state.query = search.value;
    render();
  });
  search.addEventListener('keydown', (e) => {
    const rows = document.getElementById('rows');
    if (e.key === 'Enter') {
      // Enter shows the top match, the first row as currently sorted.
      e.preventDefault();
      const first = rows.querySelector('.row');
      if (first && Number(first.dataset.id) !== state.selected) {
        selectPlace(first.dataset.id, true);
      }
    } else if (e.key === 'ArrowDown') {
      const row = rows.querySelector('.row[tabindex="0"]');
      if (row) {
        e.preventDefault();
        row.focus();
      }
    } else if (e.key === 'Escape' && search.value) {
      e.preventDefault();
      search.value = '';
      state.query = '';
      render();
    }
  });

  document.getElementById('sortbar').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    state.sort = b.dataset.sort;
    for (const x of document.querySelectorAll('#sortbar button')) {
      const on = x === b;
      x.classList.toggle('active', on);
      x.setAttribute('aria-pressed', String(on));
    }
    render();
    writeUrl();
  });

  const rows = document.getElementById('rows');
  rows.addEventListener('click', (e) => {
    const adv = e.target.closest('[data-adv]');
    if (adv) {
      toggleAdvisory(adv.dataset.adv);
      return;
    }
    const row = e.target.closest('.row');
    if (row) selectPlace(row.dataset.id, true);
  });
  rows.addEventListener('keydown', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;

    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      selectPlace(row.dataset.id, true);
      return;
    }

    // Arrow keys move between rows, so the table is one tab stop.
    const all = [...rows.querySelectorAll('.row')];
    const at = all.indexOf(row);
    let to = -1;
    if (e.key === 'ArrowDown') to = Math.min(at + 1, all.length - 1);
    else if (e.key === 'ArrowUp') to = Math.max(at - 1, 0);
    else if (e.key === 'Home') to = 0;
    else if (e.key === 'End') to = all.length - 1;
    else if (e.key === 'PageDown') to = Math.min(at + 10, all.length - 1);
    else if (e.key === 'PageUp') to = Math.max(at - 10, 0);
    else return;

    e.preventDefault();
    if (to === at) return;
    row.tabIndex = -1;
    all[to].tabIndex = 0;
    all[to].focus();
    all[to].scrollIntoView({ block: 'nearest' });
  });
}

async function main() {
  readUrl();
  try {
    state.data = await getJson(`/data/${EVENT}-places.json`);
  } catch (e) {
    console.error(e);
    showLoadError('the list of places');
    return;
  }
  // Optional: without it the list simply shows no coverage ratings.
  try {
    state.coverage = (await getJson(`/data/${EVENT}-coverage.json`)).by_country;
  } catch (e) {
    console.error(e);
  }
  for (const p of state.data.places) {
    p.f = purify(p.n);
    addTimes(p);
  }
  loadClosed();
  renderKey();

  document.getElementById('dt').textContent = state.data.event.delta_t;
  document.getElementById('stats').innerHTML =
    `<span>ΔT ${state.data.event.delta_t} s</span>
     <span>${state.data.places.length} places</span>
     <span>${Object.keys(state.data.advisories).length} countries</span>`;
  document.querySelector('nav a[download]').href =
    `/data/${EVENT}-places.csv`;

  bind();
  if (state.pin) document.getElementById('clearPin').hidden = false;
  // The list goes up before the map, so a slow or blocked tile server
  // leaves a working table instead of an empty page.
  render();
  try {
    initMap();
  } catch (e) {
    console.error(e);
    const el = document.getElementById('map');
    el.classList.add('failed');
    el.textContent = 'The map could not be loaded. The list still works.';
  }
}

main();
