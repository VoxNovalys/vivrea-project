'use strict';
/**
 * FuelSearch – Recherche locale de prix carburants.
 *
 * Source unique : /data/carburants.json  (généré par GitHub Actions)
 * Aucun appel vers une API externe côté navigateur.
 *
 * API publique : FuelSearch.init(inputId, selectId, btnId, resultsId)
 */
const FuelSearch = (() => {
  const FUEL_URL = '/data/carburants.json';

  let _promise = null;   // Promise unique (cache mémoire après 1er chargement)
  let _flat    = null;   // tableau normalisé plat

  // ── Chargement avec cache mémoire ───────────────────────────────────────
  function load() {
    if (_promise) return _promise;
    _promise = fetch(FUEL_URL, { cache: 'default' })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => { _flat = normalize(data); return _flat; })
      .catch(err => { _promise = null; throw err; });
    return _promise;
  }

  // ── Normalisation : stations[]{prix:{SP95:1.73,…}} → tableau plat ───────
  // Format carburants.json :
  //   { stations: [{ nom, cp, ville, adresse, lat, lon, prix:{…}, maj:{…} }] }
  function normalize(data) {
    const out = [];
    for (const s of (data.stations || [])) {
      for (const [type, prix] of Object.entries(s.prix || {})) {
        if (!prix) continue;            // ignorer 0 et manquant
        out.push({
          nom:       s.nom      || '',
          cp:        s.cp       || '',
          ville:     s.ville    || '',
          adresse:   s.adresse  || '',
          lat:       s.lat      ?? null,
          lon:       s.lon      ?? null,
          carburant: type,
          prix,
          maj:       (s.maj || {})[type] || '',
        });
      }
    }
    return out;
  }

  // ── Recherche / filtres / tri ────────────────────────────────────────────
  // Normalise une chaîne : minuscules + suppression accents
  function norm(s) {
    return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function search(q, carburant) {
    if (!_flat) return [];
    const term = norm(q.trim());
    return _flat
      .filter(r => {
        if (carburant && carburant !== 'Tous' && r.carburant !== carburant) return false;
        if (!term) return true;
        return (
          norm(r.ville).includes(term)   ||
          norm(r.nom).includes(term)     ||
          norm(r.adresse).includes(term) ||
          r.cp.startsWith(term)
        );
      })
      .sort((a, b) => a.prix - b.prix)
      .slice(0, 20);
  }

  // ── Helpers d'affichage ──────────────────────────────────────────────────
  function esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmtPrix(n) {
    return (n && n > 0) ? n.toFixed(3) + '\u00a0€' : '—';
  }

  function fmtDate(s) {
    if (!s) return '—';
    try {
      return new Date(s).toLocaleString('fr-FR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return s; }
  }

  function render(container, results, q) {
    if (!results.length) {
      container.innerHTML = `
        <p class="text-sm text-gray-500 text-center py-5">
          Aucune station trouvée pour <em class="text-gray-300">${esc(q)}</em>.
        </p>`;
      return;
    }

    const nb = results.length;
    container.innerHTML = `
      <p class="text-xs text-gray-600 mt-3 mb-2">
        ${nb} résultat${nb > 1 ? 's' : ''} · trié${nb > 1 ? 's' : ''} par prix croissant
      </p>
      <div class="space-y-1.5">
        ${results.map(r => `
          <div class="bg-surface border border-border rounded-xl px-4 py-3
                      flex flex-wrap items-center gap-3 justify-between">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-white truncate leading-snug">
                ${esc(r.nom || r.ville)}
              </p>
              <p class="text-xs text-gray-500 truncate">
                ${esc(r.adresse || '—')}${r.adresse ? ' — ' : ''}${esc(r.adresse ? r.ville : '')}
              </p>
              <p class="text-xs text-gray-700 mt-0.5">Màj\u00a0: ${fmtDate(r.maj)}</p>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-xs font-medium px-2.5 py-0.5 rounded-full
                           bg-amber-500/20 text-amber-300">
                ${esc(r.carburant)}
              </span>
              <span class="text-xl font-bold text-white tabular-nums">
                ${fmtPrix(r.prix)}
              </span>
            </div>
          </div>`).join('')}
      </div>`;
  }

  // ── Initialisation des handlers DOM ─────────────────────────────────────
  function init(inputId, selectId, btnId, resultsId) {
    const input   = document.getElementById(inputId);
    const select  = document.getElementById(selectId);
    const btn     = document.getElementById(btnId);
    const results = document.getElementById(resultsId);
    if (!input || !btn || !results) return;

    let _pending = false;

    async function doSearch() {
      if (_pending) return;
      const q    = input.value.trim();
      const carb = select ? select.value : 'Tous';
      if (!q) { results.innerHTML = ''; return; }

      _pending = true;
      results.innerHTML = `<div class="skeleton h-14 rounded-xl mt-3"></div>`;

      try {
        await load();                        // premier appel : charge et cache
        const found = search(q, carb);
        render(results, found, q);
      } catch {
        results.innerHTML = `<p class="text-sm text-red-400 text-center py-4">Données indisponibles.</p>`;
      } finally {
        _pending = false;
      }
    }

    btn.addEventListener('click', doSearch);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    if (select) select.addEventListener('change', () => { if (input.value.trim()) doSearch(); });
  }

  return { init };
})();
