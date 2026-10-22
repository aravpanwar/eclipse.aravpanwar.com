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
  view: 'map',        // 'map' or 'path'
  query: '',
  closed: new Set(),  // advisories put away, as advisoryId() strings
  coverage: {},       // country code -> stays coverage, from build_coverage.py
  outside: [],        // towns within 100 km outside the path: partial only
  outsideNames: {},   // country code -> name, for countries only outside towns have
  outsideRange: 100,  // km, from the outside data file
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

// Towns inside the path and towns just outside it share one id space
// (GeoNames ids), so a selection or a ?place= link can point at either.
function findPlace(id) {
  return state.data.places.find((q) => q.i === id) || state.outside.find((q) => q.i === id);
}

function outsideInCircle() {
  if (!state.pin) return state.outside;
  return state.outside.filter((p) =>
    haversine(state.pin.lat, state.pin.lon, p.y, p.x) <= state.radius);
}

const countryName = (cc) => (state.data.advisories[cc] || {}).country || state.outsideNames[cc] || cc;
const fmtOff = (o) => `UTC${o < 0 ? '−' : '+'}${Math.floor(Math.abs(o) / 60)}${Math.abs(o) % 60 ? `:${String(Math.abs(o) % 60).padStart(2, '0')}` : ''}`;

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
  let html = `<div class="keyrow"><span class="sw path dash" aria-hidden="true"></span>
      <span>Path of totality</span></div>
    <div class="keyrow"><span class="sw centre" aria-hidden="true"></span>
      <span>Centre line</span></div>
    <div class="keyrow"><span class="sw dot" aria-hidden="true"></span>
      <span>Town in totality, sized by population</span></div>
    <div class="keyrow"><span class="sw dot hollow" aria-hidden="true"></span>
      <span>Town within ${state.outsideRange} km outside the path: partial eclipse only</span></div>`;
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

function outsideGroupHtml(outs, focusId) {
  let html = `<div class="country out" data-cc="OUT">
    <div class="group" role="rowgroup"><div class="name"><b>Outside the path of totality</b>
      <span class="n">${outs.length}</span></div>
    <p class="outsub">Partial eclipse only. Distance is straight-line to the
      edge of totality, not a road distance.</p>
    <div class="head" role="row">
      <div role="columnheader">Place</div>
      <div class="num" role="columnheader" title="Local time of the most coverage">Peak</div>
      <div class="num" role="columnheader" title="Share of the sun covered at its peak">Covered</div>
      <div class="num" role="columnheader" title="Straight-line distance to the edge of totality">To totality</div></div></div>`;
  for (const p of outs) {
    const sel = p.i === state.selected ? ' sel' : '';
    const tab = p.i === focusId ? 0 : -1;
    const label = `${p.n}, ${countryName(p.c)}. Outside the path of totality: `
      + `${p.v.toFixed(1)}% of the sun covered at ${p.m} local time, `
      + `${Math.round(p.e)} km in a straight line to the edge of totality.`;
    html += `<div class="row out${sel}" data-id="${p.i}" tabindex="${tab}"
      role="row" aria-selected="${p.i === state.selected}" aria-label="${esc(label)}">
      <div class="nm" role="cell">${esc(p.n)} <span class="cc">${p.c}</span></div>
      <div class="num" role="cell">${p.m}</div>
      <div class="num dur" role="cell">${p.v.toFixed(1)}%</div>
      <div class="num" role="cell">${Math.round(p.e)} km</div>
    </div>`;
  }
  return html + '</div>';
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
  return `No place matching “${said}”. Towns inside the path of totality and
    within ${state.outsideRange} km outside it are listed, under their GeoNames spelling.`;
}

function render() {
  const list = sorted(matching(inCircle()));
  // Outside towns join the list only when they answer something: a search
  // or a pin. The whole-path view stays about totality.
  const asked = state.query.trim() || state.pin;
  const outs = asked
    ? matching(outsideInCircle()).slice().sort((a, b) => a.e - b.e)
    : [];
  const rows = document.getElementById('rows');
  // The selected row keeps the tab stop; otherwise the first row does.
  const both = list.concat(outs);
  const focusId = (state.selected && both.some((p) => p.i === state.selected))
    ? state.selected
    : (both[0] ? both[0].i : null);

  document.getElementById('count').textContent =
    `${list.length} place${list.length === 1 ? '' : 's'}`;
  const scope = state.pin
    ? `within ${state.radius} km of ${fmtLat(state.pin.lat)} ` +
      `${fmtLon(state.pin.lon)}`
    : 'across the whole path';
  document.getElementById('pinHint').hidden = !!state.pin;
  document.querySelector('.controls').classList.toggle('nopin', !state.pin);
  document.getElementById('where').textContent = state.query.trim()
    ? `matching “${state.query.trim()}” ${scope}`
    : scope;
  announce();

  if (outs.length) {
    document.getElementById('count').textContent =
      `${list.length} in totality, ${outs.length} outside`;
  }

  if (!list.length && !outs.length) {
    rows.innerHTML = `<p class="empty">${emptyMessage()}</p>`;
    rows.setAttribute('aria-rowcount', '0');
    drawPlaces(list, outs);
    drawCircle();
    // An empty list must not stop the card and the chart marker: a town
    // picked on the chart while a search matches nothing is still picked.
    renderTown();
    profileMarks();
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
      ${advisoryHtml(cc, name)}`;
    html += `<div class="head" role="row">
      <div role="columnheader">Place</div>
      <div class="num" role="columnheader" title="Local time totality begins${places[0].off ? `, ${places[0].off}` : ''}">Starts</div>
      <div class="num" role="columnheader">Totality</div>
      <div class="num" role="columnheader">Cloud</div>
      <div class="num" role="columnheader" title="Places to stay mapped in OpenStreetMap within 25 km">Stays</div></div></div>`;
    for (const p of places) {
      const sel = p.i === state.selected ? ' sel' : '';
      // Roving tabindex: exactly one row is tabbable, the rest are reached
      // with arrow keys. Without this a keyboard user has to press Tab 772
      // times to get past the table.
      const tab = p.i === focusId ? 0 : -1;
      const label = `${p.n}. Totality ${p.t0 ? `from ${p.t0} local time, ` : ''}`
        + `${mmss(p.d)} long. ${fmtPct(p.w)} August cloud. `
        + `${staysSpoken(p.l)} mapped within 25 km.`;
      html += `<div class="row${sel}" data-id="${p.i}" tabindex="${tab}"
        role="row" aria-selected="${p.i === state.selected}"
        aria-label="${esc(label)}">
        <div class="nm" role="cell">${esc(p.n)}</div>
        <div class="num" role="cell">${p.t0 || 'n/a'}</div>
        <div class="num dur" role="cell">${mmss(p.d)}</div>
        <div class="num" role="cell">${fmtPct(p.w)}</div>
        <div class="num" role="cell">${p.l || 'none'}</div>
      </div>`;
    }
    html += '</div>';
  }
  if (!list.length) {
    html += `<p class="empty small">No town in the path of totality matches.</p>`;
  }
  if (outs.length) html += outsideGroupHtml(outs, focusId);
  if (!asked && state.outside.length) {
    html += `<p class="outnote">${state.outside.length.toLocaleString('en-GB')} towns
      within ${state.outsideRange} km outside the path are on the map as hollow
      dots. They see a partial eclipse only. Search for one, or drop a pin, to list them.</p>`;
  }
  rows.innerHTML = html;
  rows.setAttribute('aria-rowcount', String(list.length + outs.length));
  drawPlaces(list, outs);
  drawCircle();
  renderTown();
  profileMarks();
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
    // One name per place, in English where the tiles carry one. name:latin
    // comes before name_en because the tiles fill name_en from the local name
    // when there is no English one, and in Morocco that local name is often
    // written in three scripts at once.
    for (const l of map.getStyle().layers) {
      if (l.type !== 'symbol') continue;
      const f = map.getLayoutProperty(l.id, 'text-field');
      if (f && JSON.stringify(f).includes('name')) {
        map.setLayoutProperty(l.id, 'text-field', ['coalesce',
          ['get', 'name:en'], ['get', 'name:latin'], ['get', 'name_en'], ['get', 'name']]);
      }
    }
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
      paint: { 'fill-color': '#1a5c7a', 'fill-opacity': 0.15 },
    });
    map.addLayer({
      id: 'umbra-edge', type: 'line', source: 'path',
      filter: ['==', ['get', 'kind'], 'umbra'],
      paint: {
        // Dashed: the edges are known to about 1 to 2 km, and dashes keep them
        // apart from the solid centre line and the grey country borders.
        'line-color': '#1a5c7a', 'line-width': 1.8, 'line-opacity': 0.95,
        'line-dasharray': [3, 2],
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
      // Solid, because the dashed teal line is the edge of totality.
      paint: { 'line-color': '#1a5c7a', 'line-width': 1.5 },
    });

    // Radius by population, so the map answers "what is near here" without
    // reading the table. pad widens it for the invisible hit layer.
    const dotRadius = (pad) => [
      'interpolate', ['linear'], ['get', 'pop'],
      0, 2.5 + pad, 20000, 3.5 + pad, 100000, 5 + pad,
      500000, 7.5 + pad, 2000000, 10 + pad,
    ];
    // Towns outside the path: hollow, under the filled dots of the towns in
    // totality, so the two never read as the same thing.
    map.addSource('outside', { type: 'geojson', data: emptyFC() });
    map.addLayer({
      id: 'outside', type: 'circle', source: 'outside',
      paint: {
        'circle-radius': dotRadius(0),
        'circle-color': '#fffefb',
        'circle-opacity': 0.75,
        'circle-stroke-width': ['case', ['==', ['get', 'sel'], true], 2.5, 1.2],
        'circle-stroke-color': ['case', ['==', ['get', 'sel'], true], '#b5540e', '#3d382f'],
      },
    });
    map.addLayer({
      id: 'outside-hit', type: 'circle', source: 'outside',
      paint: { 'circle-radius': dotRadius(5), 'circle-opacity': 0 },
    });

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

    // A town in totality wins over an outside town under the same pointer.
    const HIT = ['places-hit', 'outside-hit'];
    const under = (point) => {
      const inside = map.queryRenderedFeatures(point, { layers: ['places-hit'] });
      const fs = inside.length ? inside : map.queryRenderedFeatures(point, { layers: ['outside-hit'] });
      return fs.length ? Number(nearest({ features: fs, point }).properties.id) : null;
    };
    map.on('click', (e) => {
      const id = under(e.point);
      if (id) { hideTip(); selectPlace(id, false); return; }
      // Clicking bare map drops the pin there.
      setPin(e.lngLat.lat, e.lngLat.lng);
    });
    map.on('mousemove', (e) => {
      const id = under(e.point);
      map.getCanvas().style.cursor = id ? 'pointer' : '';
      if (id) showTip(id); else hideTip();
    });
    map.on('mouseout', () => hideTip());

    render();

    // A shared link to a place (?place=) opens on that place: map centred,
    // its card open and, where the list sits beside the map, its row in view.
    const p = findPlace(state.selected);
    if (p) {
      centreOn(p, false);
      renderTown();
      if (!STACKED.matches) {
        const row = document.querySelector('#rows .row.sel');
        if (row) row.scrollIntoView({ block: 'center' });
      }
    } else if (state.country) {
      openOnCountry(state.country);
    } else if (state.pin) {
      // A shared pin link opens framed on its circle, not on the default view.
      const ring = circlePolygon(state.pin.lat, state.pin.lon, state.radius).geometry.coordinates[0];
      const xs = ring.map((c) => c[0]);
      const ys = ring.map((c) => c[1]);
      map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
                    { padding: 30, duration: 0 });
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

function drawPlaces(visible, outs) {
  if (!map || !map.getSource('places')) return;
  // Every outside town shows on the whole-path view; a search or a pin
  // narrows them like the towns in totality.
  const outShown = (state.query.trim() || state.pin) ? (outs || []) : state.outside;
  map.getSource('outside').setData({
    type: 'FeatureCollection',
    features: outShown.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.x, p.y] },
      properties: { id: p.i, pop: p.p, sel: p.i === state.selected },
    })),
  });
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

function centreOn(p, animate) {
  const opts = { center: [p.x, p.y] };
  // easeTo even when not animating: jumpTo ignores offset.
  map.easeTo({ ...opts, duration: animate ? 500 : 0 });
}
const CALM = window.matchMedia('(prefers-reduced-motion: reduce)');

function selectPlace(id, fly) {
  state.selected = Number(id) === state.selected ? null : Number(id);
  const p = findPlace(state.selected);
  if (p) {
    renderTown();
    if (fly) centreOn(p, true);
    // On a phone the list is below the map, so picking a row from it would
    // otherwise move a map that has scrolled out of view.
    if (fly && STACKED.matches) {
      document.getElementById('map').scrollIntoView({
        behavior: CALM.matches ? 'auto' : 'smooth', block: 'start',
      });
    }
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

// Hover label: name, start time and totality. It sits above the dot and
// lets the pointer through (style.css), so it never covers what it labels;
// Esc dismisses it.
let tip = null;
let tipId = null;

function showTip(id) {
  if (id === tipId) return;
  tipId = id;
  // The selected place already has its card open.
  const p = id === state.selected ? null : findPlace(id);
  if (!p) {
    if (tip) tip.remove();
    return;
  }
  const text = p.v != null
    ? `${p.v.toFixed(1)}% covered, ${Math.round(p.e)} km to totality`
    : `${p.t0 ? `${p.t0}, ` : ''}${mmss(p.d)}`;
  if (!tip) {
    tip = new maplibregl.Popup({
      closeButton: false, closeOnClick: false, anchor: 'bottom',
      offset: 9, className: 'tip',
    });
  }
  tip.setLngLat([p.x, p.y])
    .setHTML(`<b>${esc(p.n)}</b> <span>${text}</span>`)
    .addTo(map);
}

function hideTip() {
  if (tip) tip.remove();
  tipId = null;
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideTip();
});


const TC = (n, v) => `<div><dt>${n}</dt><dd>${v}</dd></div>`;

// The FCDO line on a town card, or nothing when the country has no advisory.
function advLine(adv, country, after) {
  if (!adv || !adv.worst || !adv.label) return '';
  return `<p class="tc-adv">The UK FCDO ${esc(adv.label.toLowerCase()
    .replace('the whole country', country).replace('the country', country))}. ${after}</p>`;
}

// The selected place, in the column beside the map rather than over it.
function renderTown() {
  const el = document.getElementById('town');
  const p = state.selected && findPlace(state.selected);
  if (!p) { el.hidden = true; el.innerHTML = ''; return; }
  if (p.v != null) { renderOutsideTown(el, p); return; }
  const adv = state.data.advisories[p.c];
  const country = adv ? adv.country : p.c;
  el.innerHTML = `
    <div class="tc-head"><h2>${esc(p.n)}</h2><span class="tc-cc">${esc(country)}</span>
      ${state.view === 'path' ? '<button type="button" class="tc-map">Show on map</button>' : ''}
      <button type="button" class="tc-close" aria-label="Close ${esc(p.n)}">×</button></div>
    <div class="tc-main">
      <div><div class="tc-big">${mmss(p.d)}</div>
        <div class="tc-sub">of totality</div></div>
      <div><div class="tc-time">${p.t0 ? `${p.t0} to ${p.t1}` : 'n/a'}</div>
        <div class="tc-sub">local time${p.off ? `, ${p.off}` : ''}</div></div>
    </div>
    <dl class="tc-facts">
      ${TC('August cloud', fmtPct(p.w))}${TC('Sun altitude', `${p.a.toFixed(0)}°`)}
      ${TC('From centre line', `${fmtKm(p.k)} km`)}${TC('Stays, 25 km', p.l ? `~${p.l}` : 'none')}
      ${TC('Stays, 80 km', p.L ? `~${p.L}` : 'none')}
    </dl>
    ${advLine(adv, country, `The named areas are under ${esc(country)} in the list.`)}`;
  el.hidden = false;
  el.querySelector('.tc-close').onclick = () => selectPlace(p.i, false);
  const back = el.querySelector('.tc-map');
  if (back) back.onclick = () => { setView('map'); centreOn(p, false); };
}

// A town outside the path: how much of the sun is covered and when, how far
// totality is, and the one safety fact a partial eclipse needs.
function renderOutsideTown(el, p) {
  const adv = state.data.advisories[p.c];
  // Outside towns have no country group in the list to name the areas, so
  // the line points at the FCDO page instead.
  const named = adv ? `<a href="${esc(adv.url)}" target="_blank" rel="noopener">Read the FCDO advice</a>.` : '';
  el.innerHTML = `
    <div class="tc-head"><h2>${esc(p.n)}</h2><span class="tc-cc">${esc(countryName(p.c))}</span>
      <button type="button" class="tc-close" aria-label="Close ${esc(p.n)}">×</button></div>
    <p class="tc-kind">Outside the path of totality: a partial eclipse here</p>
    <div class="tc-main">
      <div><div class="tc-big">${p.v.toFixed(1)}%</div>
        <div class="tc-sub">of the sun covered at its peak</div></div>
      <div><div class="tc-time">${p.m}</div>
        <div class="tc-sub">local time, ${fmtOff(p.o)}</div></div>
    </div>
    <dl class="tc-facts">
      ${TC('To the edge of totality', `${fmtKm(p.e)} km`)}
      ${TC('To the centre line', `${fmtKm(p.k)} km`)}
      ${TC('Sun altitude', `${p.a.toFixed(0)}°`)}
    </dl>
    <p class="tc-note">Straight-line distances, not road distances. Totality is
      longest along the centre line.</p>
    <p class="tc-safe">${WARN_ICON}<span>Never look at a partial eclipse without
      eclipse glasses, even at 99%. Only totality itself is safe to look at.</span></p>
    ${advLine(adv, countryName(p.c), named)}`;
  el.hidden = false;
  el.querySelector('.tc-close').onclick = () => selectPlace(p.i, false);
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
  if (state.view === 'path') q.set('view', 'cloud');
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
  if (q.get('view') === 'cloud') state.view = 'path';
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
  // Optional: without it the site is exactly as before.
  try {
    const outside = await getJson(`/data/${EVENT}-outside.json`);
    state.outside = outside.places;
    state.outsideNames = outside.countries;
    state.outsideRange = outside.range_km;
    for (const p of state.outside) p.f = purify(p.n);
  } catch (e) {
    console.error(e);
  }
  loadClosed();
  renderKey();
  // On a phone the key would push the list below the fold; it starts closed.
  try { state.profile = await getJson(`/data/${EVENT}-centre-profile.json`); } catch (e) { state.profile = []; }
  bindViews();
  if (STACKED.matches) document.getElementById('keybox').open = false;
  window.addEventListener('resize', () => { if (state.view === 'path') drawProfile(); });

  // Countries with a town in totality. The advisories also cover countries
  // that only have towns outside the path, so they are not counted here.
  document.getElementById('stats').innerHTML =
    `<span>${state.data.places.length} places</span>
     <span>${new Set(state.data.places.map((p) => p.c)).size} countries</span>`;
  document.getElementById('csvIn').href = `/data/${EVENT}-places.csv`;
  document.getElementById('csvOut').href = `/data/${EVENT}-outside.csv`;

  bind();
  if (state.pin) document.getElementById('clearPin').hidden = false;
  // The list goes up before the map, so a slow or blocked tile server
  // leaves a working table instead of an empty page.
  render();
  try {
    initMap();
    if (state.view === 'path') setView('path');
  } catch (e) {
    console.error(e);
    const el = document.getElementById('map');
    el.classList.add('failed');
    el.textContent = 'The map could not be loaded. The list still works.';
  }
}

/* ---------- view: totality and cloud along the path ---------- */

const PLON = [-7, 52];
const CLOUD_MAX = 80;
// Line colour by totality, shortest dark to longest bright. A single-hue
// ramp still grades under red-green colour blindness, and red already means
// an FCDO advisory on this site.
const RAMP = [[0, [96, 46, 140]], [0.35, [190, 58, 90]], [0.7, [238, 124, 50]], [1, [252, 231, 146]]];
let P = null;   // scales and sizes of the last draw

function rampColour(stops, f) {
  for (let i = 1; i < stops.length; i++) {
    const [f1, c1] = stops[i];
    const [f0, c0] = stops[i - 1];
    if (f <= f1) {
      const t = (f - f0) / ((f1 - f0) || 1);
      return `rgb(${c0.map((c, k) => Math.round(c + (c1[k] - c) * t)).join(',')})`;
    }
  }
  return `rgb(${stops[stops.length - 1][1].join(',')})`;
}

// Country spans along the axis. Two countries that share most of a span, as
// Spain and Morocco do across the strait, share one label. A country with a
// single town, Gibraltar, has a span of no width and joins the one it sits in.
function countrySpans() {
  const by = new Map();
  for (const p of state.data.places) {
    const s = by.get(p.c) || { cc: [p.c], lo: p.x, hi: p.x, ws: [] };
    s.lo = Math.min(s.lo, p.x); s.hi = Math.max(s.hi, p.x);
    if (p.w != null) s.ws.push(p.w);
    by.set(p.c, s);
  }
  const spans = [...by.values()].sort((a, b) => a.lo - b.lo);
  const out = [];
  for (const s of spans) {
    const prev = out[out.length - 1];
    if (prev && prev.hi > s.lo) {
      const overlap = Math.min(prev.hi, s.hi) - s.lo;
      if (overlap >= 0.5 * Math.min(prev.hi - prev.lo, s.hi - s.lo)) {
        prev.cc.push(...s.cc); prev.ws.push(...s.ws); prev.hi = Math.max(prev.hi, s.hi); continue;
      }
      const mid = (s.lo + prev.hi) / 2;
      prev.hi = mid; s.lo = mid;
    }
    out.push({ ...s, ws: [...s.ws] });
  }
  return out;
}

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

function drawProfile() {
  const svg = document.getElementById('psvg');
  const W = svg.clientWidth;
  const H = svg.clientHeight;
  if (!W || !H || !state.data) return;
  const narrow = W < 600;
  const m = { l: narrow ? 34 : 50, r: narrow ? 10 : 20 };
  const t0 = 26;                                  // totality chart top
  const t1 = Math.round(t0 + (H - 120) * 0.6);    // totality chart bottom
  const sy = t1 + 10;                             // country strip
  const c0 = sy + 50;                             // cloud chart top
  const c1 = H - 8;                               // cloud chart bottom
  const x = (lon) => m.l + (lon - PLON[0]) / (PLON[1] - PLON[0]) * (W - m.l - m.r);
  const y = (s) => t1 - (s / 400) * (t1 - t0);
  const yc = (w) => c1 - (Math.min(w, CLOUD_MAX) / CLOUD_MAX) * (c1 - c0);
  P = { x, y, yc, m, W, H, t0, t1, c0, c1 };
  let h = '';

  // Totality chart.
  h += `<text class="ax" x="${m.l}" y="${t0 - 10}">Totality</text>`;
  for (const s of [120, 240, 360]) {
    h += `<line class="pg" x1="${m.l}" x2="${W - m.r}" y1="${y(s)}" y2="${y(s)}"/>`;
    h += `<text class="pt" x="${m.l - 7}" y="${y(s) + 3.5}" text-anchor="end">${s / 60}:00</text>`;
  }
  for (const p of state.data.places) {
    h += `<circle class="pd" data-id="${p.i}" cx="${x(p.x).toFixed(1)}" cy="${y(p.d).toFixed(1)}" r="${narrow ? 1.6 : 2}"/>`;
  }
  const pts = (state.profile || []).filter((r) => r[1] && r[0] >= PLON[0] && r[0] <= PLON[1]);
  if (pts.length) {
    const lo = Math.min(...pts.map((r) => r[1]));
    const hi = Math.max(...pts.map((r) => r[1]));
    const ramp = RAMP;
    // The legend swatch runs through the same colours as the line.
    document.querySelector('.pl-line').style.background =
      `linear-gradient(to right, ${ramp.map(([f]) => rampColour(ramp, f)).join(', ')})`;
    const span = W - m.l - m.r;
    h += `<defs><linearGradient id="tg" gradientUnits="userSpaceOnUse" x1="${m.l}" x2="${W - m.r}" y1="0" y2="0">
      ${pts.map((r) => `<stop offset="${((x(r[0]) - m.l) / span).toFixed(4)}" stop-color="${rampColour(ramp, (r[1] - lo) / (hi - lo))}"/>`).join('')}
      </linearGradient></defs>`;
    h += `<path class="pc" stroke="url(#tg)" d="M${pts.map((r) => `${x(r[0]).toFixed(1)},${y(r[1]).toFixed(1)}`).join('L')}"/>`;
    const pk = pts.reduce((a, b) => (b[1] > a[1] ? b : a));
    h += `<text class="pkl" x="${x(pk[0])}" y="${y(pk[1]) - 9}" text-anchor="middle">${mmss(state.data.event.peak)} longest</text>`;
  }

  // Country strip, with each country's median cloud.
  const spans = countrySpans();
  for (const s of spans) {
    const pad = Math.max(0, 1.2 - (s.hi - s.lo)) / 2;
    const x0 = x(s.lo - pad) + 0.5;
    const x1 = x(s.hi + pad) - 0.5;
    const names = s.cc.map((c) => (state.data.advisories[c] || { country: c }).country);
    const full = names.join(', ');
    const label = (x1 - x0) > full.length * 5.7 + 6 ? full : s.cc.join(' ');
    h += `<g class="pcn" data-cc="${s.cc[0]}"><rect x="${x0}" y="${sy}" width="${x1 - x0}" height="18"/>
      <text x="${(x0 + x1) / 2}" y="${sy + 12.5}" text-anchor="middle">${esc(label)}</text></g>`;
  }

  // Cloud chart: median August cloud of the towns in each 1 degree of longitude.
  h += `<text class="ax" x="${m.l}" y="${c0 - 12}">August cloud at eclipse time</text>`;
  for (const w of [25, 50, 75]) {
    h += `<line class="pg" x1="${m.l}" x2="${W - m.r}" y1="${yc(w)}" y2="${yc(w)}"/>`;
    h += `<text class="pt" x="${m.l - 7}" y="${yc(w) + 3.5}" text-anchor="end">${w}%</text>`;
  }
  h += `<line class="pbase" x1="${m.l}" x2="${W - m.r}" y1="${c1}" y2="${c1}"/>`;
  const bins = new Map();
  for (const p of state.data.places) {
    if (p.w == null) continue;
    const k = Math.floor(p.x);
    if (!bins.has(k)) bins.set(k, []);
    bins.get(k).push(p.w);
  }
  for (const [k, ws] of bins) {
    const med = median(ws);
    h += `<rect class="pbar" x="${x(k) + 0.5}" y="${yc(med)}" width="${Math.max(1, x(k + 1) - x(k) - 1)}" height="${c1 - yc(med)}"><title>${med.toFixed(1)}% cloud, ${ws.length} towns</title></rect>`;
  }
  for (const s of spans) {
    if (!s.ws.length) continue;
    const med = median(s.ws);
    const top = Math.min(...[...bins].filter(([k]) => k + 1 > s.lo && k < s.hi).map(([, ws]) => yc(median(ws))));
    h += `<text class="pcm" x="${x((s.lo + s.hi) / 2)}" y="${Math.max(c0 + 10, top - 6)}" text-anchor="middle">${med < 10 ? med.toFixed(1) : Math.round(med)}%</text>`;
  }

  h += `<g id="psel"></g>`;
  svg.innerHTML = h;
  svg.onclick = (e) => {
    const g = e.target.closest('.pcn');
    if (g) { setView('map'); openOnCountry(g.dataset.cc); return; }
    const r = svg.getBoundingClientRect();
    const px = e.clientX - r.left;
    const py = e.clientY - r.top;
    let best = null;
    let bd = 100;
    for (const p of state.data.places) {
      const d = (x(p.x) - px) ** 2 + (y(p.d) - py) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    if (best) selectPlace(best.i, false);
  };
  profileMarks();
}

// The selected place, marked on both charts.
function profileMarks() {
  const sel = document.getElementById('psel');
  if (!P || !sel) return;
  const { x, y, yc, W, t1, c0, c1 } = P;
  const p = state.selected && state.data.places.find((q) => q.i === state.selected);
  if (!p) {
    sel.innerHTML = '';
    for (const t of document.querySelectorAll('#psvg .pcm')) t.style.visibility = '';
    return;
  }
  const sx = x(p.x);
  const right = sx < W - 160;
  const a = right ? 'start' : 'end';
  const dx = right ? 10 : -10;
  sel.innerHTML = `<line class="psl" x1="${sx}" x2="${sx}" y1="${y(p.d)}" y2="${c1}"/>
    <circle class="ps" cx="${sx}" cy="${y(p.d)}" r="5"/>
    <text class="psn" x="${sx + dx}" y="${y(p.d) + 15}" text-anchor="${a}">${esc(p.n)} ${mmss(p.d)}</text>
    ${p.w != null ? `<circle class="ps" cx="${sx}" cy="${yc(p.w)}" r="4"/>
    <text class="psn psw" x="${sx + dx}" y="${Math.max(c0 + 12, yc(p.w) - 7)}" text-anchor="${a}">${fmtPct(p.w)}</text>` : ''}`;

  // A country's median cloud label can sit where the selected town's figure
  // goes. The town's figure is the one being looked at, so the median steps
  // aside, and comes back when the town is deselected or another is picked.
  const medians = document.querySelectorAll('#psvg .pcm');
  for (const t of medians) t.style.visibility = '';
  const own = sel.querySelector('.psw');
  if (!own) return;
  const a2 = own.getBBox();
  for (const t of medians) {
    const b = t.getBBox();
    if (a2.x < b.x + b.width + 4 && b.x < a2.x + a2.width + 4
        && a2.y < b.y + b.height + 2 && b.y < a2.y + a2.height + 2) {
      t.style.visibility = 'hidden';
    }
  }
}

function setView(v) {
  state.view = v === 'path' ? 'path' : 'map';
  const path = state.view === 'path';
  document.getElementById('pathview').hidden = !path;
  document.getElementById('mapwrap').hidden = path;
  for (const t of document.querySelectorAll('.views [role="tab"]')) {
    const on = t.dataset.view === state.view;
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
  }
  if (path) drawProfile();
  else if (map) map.resize();
  renderTown();
  writeUrl();
}

function bindViews() {
  const tabs = [...document.querySelectorAll('.views [role="tab"]')];
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => setView(t.dataset.view));
    t.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus();
      setView(n.dataset.view);
    });
  });
}

main();
