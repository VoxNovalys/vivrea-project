/**
 * VivreÀ – Web Worker : filtrage des communes en arrière-plan.
 * Reçoit les messages {type, payload} depuis le thread principal.
 *
 * Messages entrants :
 *   { type: 'INIT',   payload: [ [nom, code_insee, cp, pop], ... ] }
 *   { type: 'SEARCH', payload: { query: string, limit: number } }
 *
 * Messages sortants :
 *   { type: 'READY' }
 *   { type: 'RESULTS', payload: [ {nom, code_insee, cp, pop}, ... ] }
 */

'use strict';

let index = [];   // Tableau brut reçu du thread principal
let normalized = []; // Noms normalisés (sans accents, lowercase) pour comparaison rapide

/**
 * Normalise une chaîne : minuscules, suppression des diacritiques, trim.
 */
function normalize(str) {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

/**
 * Score de pertinence pour trier les résultats.
 * Préfixe exact > début de mot > contient > partiel
 */
function score(normName, normQuery) {
  if (normName === normQuery)           return 100;
  if (normName.startsWith(normQuery))   return 80;
  const words = normName.split(/[-\s]+/);
  if (words.some(w => w.startsWith(normQuery))) return 60;
  if (normName.includes(normQuery))     return 40;
  return 0;
}

self.onmessage = function (e) {
  const { type, payload } = e.data;

  if (type === 'INIT') {
    index = payload;
    // Pré-calcul des noms normalisés une seule fois
    normalized = index.map(c => normalize(c[0]));
    self.postMessage({ type: 'READY', payload: { size: index.length } });
    return;
  }

  if (type === 'SEARCH') {
    const { query, limit = 8 } = payload;
    const q = normalize(query);

    if (q.length < 1) {
      self.postMessage({ type: 'RESULTS', payload: [] });
      return;
    }

    const results = [];

    for (let i = 0; i < normalized.length; i++) {
      const normName = normalized[i];
      // Vérification rapide : contient-il au moins le début de la requête ?
      if (!normName.includes(q) && !normalized[i].startsWith(q)) {
        // Vérification secondaire sur code postal
        const cp = index[i][2] || '';
        if (!cp.startsWith(q)) continue;
      }

      const s = score(normName, q);
      if (s > 0 || (index[i][2] || '').startsWith(q)) {
        results.push({
          nom:        index[i][0],
          code_insee: index[i][1],
          cp:         index[i][2],
          pop:        index[i][3],
          _score:     s || 20,
        });
      }
    }

    // Tri par score décroissant, puis population décroissante
    results.sort((a, b) => b._score - a._score || b.pop - a.pop);

    // On supprime le champ _score avant d'envoyer
    const top = results.slice(0, limit).map(({ _score, ...r }) => r);
    self.postMessage({ type: 'RESULTS', payload: top });
    return;
  }
};
