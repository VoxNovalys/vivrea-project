# VivreÀ — Inventaire des Composants & Gestion d'État

**Date :** 2026-02-21

Ce document inventorie les composants fonctionnels JavaScript, les vues SPA, les modules, et la stratégie de gestion d'état du projet. VivreÀ est en Vanilla JS sans framework : les "composants" sont des fonctions retournant des fragments HTML (template strings) ou des modules IIFE.

---

## 1. Architecture des Vues (SPA Router — index.html)

Le routeur SPA de `index.html` dispatche selon l'URL vers l'une des vues suivantes. L'URL est la source de vérité.

### Tableau des routes

| Pattern URL | Vue rendue | Fonction principale | Condition |
|---|---|---|---|
| `/` (racine) | Home | `renderHome()` | Aucun paramètre |
| `/?v={code_insee}` | Ville — code INSEE | `renderVille()` | `v` = 5 chars |
| `/?s={slug}` | Ville — nom | `fetchBySlug()` → `renderVille()` | `s` = nom textuel |
| `/?v={c1}&c={c2}` | Compare | `renderComparePage()` | `c` présent |
| `/explorer.html` | Explorateur | (page autonome) | Navigation directe |

**Fonction routeur :** `boot()` — point d'entrée unique, lit `window.location.search`.

---

## 2. Vues SPA (index.html)

### 2.1 Vue Home — `renderHome()`

**Rôle :** Affiche la page d'accueil avec la barre de recherche et les cartes carburants.

**Éléments rendus :**
- Champ de recherche (`#search-input`) avec autocomplétion via Worker
- Liste de résultats (`#results`) — items cliquables → navigation `?v=`
- Bloc carburant national (`#fuel-widget`) — chargé par `loadFuelIntoEl()`

**Dépendances :** Worker READY, `data/index.json` chargé, `data/carburants.json`

---

### 2.2 Vue Ville — `renderVille(communeObject)`

**Rôle :** Affiche la fiche complète d'une commune.

**Sous-composants appelés :**

| Fonction | Rôle | Section HTML produite |
|---|---|---|
| `buildVilleHTML(c)` | Assembleur principal — compose toutes les sections | `#ville-container` complet |
| `buildImmoSection(c)` | Bloc immobilier (prix, DVF, liens) | `.immo-block` |
| `buildAmazonBlock(c)` | Liens de recherche contextuels (LBC, SeLoger) | `.links-block` |
| `loadFuelIntoEl(c, el)` | Stations carburant à proximité | `.fuel-section` |
| `enrich(c)` | Fallback DVF CEREMA si `c.immo` absent | Mise à jour asynchrone |

**Flux de chargement :**
1. `fetchDep(code_dep)` → récupère `details/{dep}.json`
2. `fetchByInsee(code_insee)` → cherche la commune dans le fichier dep
3. Si absente → fallback `API Géo` (`geo.api.gouv.fr`)
4. `enrich(c)` si `c.immo` absent → appel DVF CEREMA
5. `renderVille(c)` → `buildVilleHTML(c)` → injection dans `#app`

---

### 2.3 Vue Compare — `renderComparePage(c1, c2)`

**Rôle :** Affiche deux fiches côte à côte en mode comparaison.

**Éléments rendus :**
- Panneau gauche → `buildCompactHTML(c1)`
- Panneau droit → `buildCompactHTML(c2)`
- Bouton retour + bouton fermer comparaison

**Accès :** URL `?v={insee1}&c={insee2}` ou bouton "Comparer" dans la vue Ville.

**Sous-composant :**

| Fonction | Rôle |
|---|---|
| `buildCompactHTML(c)` | Version condensée de la fiche ville (métriques clés uniquement) |
| `initCmpSearch(side)` | Mini-barre de recherche pour changer une commune dans le comparateur |
| `toggleComparisonMode()` | Active/désactive l'overlay de sélection |
| `closeComparisonMode()` | Remet l'UI en mode vue simple |

---

## 3. Page Explorateur — explorer.html (autonome)

**Rôle :** Tableau interactif avec filtres et tri sur toutes les communes d'un département.

**Architecture :** Page HTML **totalement autonome** — aucune dépendance à `index.html`, pas d'import partagé.

**Fonctions clés :**

| Fonction | Rôle |
|---|---|
| `init()` | Point d'entrée — lit `?dep=` de l'URL, appelle `loadData()` |
| `loadData()` | Fetch `data/details/{dep}.json` |
| `getDep(code_insee)` | Extrait le code département (dupliqué de index.html) |
| `applyFilters()` | Filtre le tableau selon les critères UI |
| `sortData(col)` | Tri par colonne |
| `render()` | Génère les lignes `communeRow()` + pagination |
| `communeRow(c)` | Génère une ligne `<tr>` pour une commune |
| `goToVille(code_insee)` | Navigation vers `index.html?v={code}` |
| `renderPagination()` | Composant pagination (50 communes/page) |
| `goPage(n)` | Navigation entre pages |
| `esc(s)` | Escape HTML (dupliqué de index.html) |

**Variables d'état locales :**
```javascript
let data = [];          // Array — toutes les communes du département chargé
let filtered = [];      // Array — données après filtres
let sortCol = null;     // String|null — colonne de tri active
let sortAsc = true;     // Boolean — sens du tri
let currentPage = 1;    // Number — page courante
const PER_PAGE = 50;    // Number — constante
```

**Note technique :** `getDep()` et `esc()` sont intentionnellement dupliqués depuis `index.html` pour maintenir l'autonomie de cette page.

---

## 4. Modules JavaScript

### 4.1 `fuel.js` — Module FuelSearch (IIFE)

**Pattern :** IIFE exposant un objet `FuelSearch` sur `window`.

**Interface publique :**

```javascript
window.FuelSearch = {
  load():    Promise<FuelData>,   // Singleton — une seule requête même si appelé N fois
  search(ville, cp, limit):       // Retourne stations proches (par ville/CP)
  render(stations, el):           // Injecte HTML dans l'élément DOM fourni
  init(cp, ville, el):            // Combine load + search + render
}
```

**Fonctions internes :**

| Fonction | Rôle |
|---|---|
| `normalize(str)` | Normalise nom ville (lowercase, sans diacritiques, sans tirets) |
| `fmtPrix(v)` | Formate prix carburant (2 décimales, "—" si null) |
| `fmtDate(iso)` | Formate timestamp ISO en "il y a X jours" |

**État interne :**
```javascript
let _promise = null;    // Promise singleton — évite les requêtes multiples
let _cache = null;      // FuelData — données carburant en mémoire
```

---

### 4.2 `search.worker.js` — Web Worker de recherche

**Rôle :** Indexation et recherche fuzzy sur 34 875 communes dans un thread dédié.

**Messages reçus :**

| Type | Payload | Effet |
|---|---|---|
| `INIT` | `[[nom, code_insee, cp, pop], ...]` | Normalise les noms → répond `READY` |
| `SEARCH` | `{ query, limit, ch }` | Recherche → répond `RESULTS` |

**Messages émis :**

| Type | Payload |
|---|---|
| `READY` | `{ size: 34875 }` |
| `RESULTS` | `{ ch, results: [{ nom, code_insee, cp, pop }] }` |

**Algorithme de scoring (SEARCH) :**

| Score | Condition |
|---|---|
| 100 | Correspondance exacte normalisée |
| 90 | Code INSEE exact |
| 80 | Préfixe exact (commence par la requête) |
| 60 | Début de mot (après `-` ou espace) |
| 40 | Contient la requête |
| 20 | Code postal commence par la requête (≥2 chars) |

**Fallback inline :** Si `search.worker.js` ne peut être chargé (CSP ou file://), `index.html` contient `WORKER_SRC` — un string du code worker créé en Blob URL (`URL.createObjectURL`).

---

## 5. Gestion d'État

### 5.1 Stratégie globale

VivreÀ utilise une stratégie **URL-as-truth** couplée à un **objet `state` minimal** pour les données transitoires d'UI.

| Source de vérité | Ce qu'elle contient |
|---|---|
| **URL** (`window.location.search`) | Commune affichée (`?v=`), mode comparaison (`?c=`), slug textuel (`?s=`) |
| **`state` objet JS** | Données UI transitoires (mode comparaison, callbacks worker, état worker) |
| **Mémoire module** (`fuel.js`) | Cache carburant (singleton Promise) |
| **Worker thread** | Index de recherche normalisé (34k communes) |

### 5.2 Objet `state` (index.html)

```javascript
const state = {
  workerReady:  false,   // Boolean — worker prêt à répondre à SEARCH
  workerSize:   0,       // Number — nb communes indexées (affiché dans #worker-status)
  workerCbs:    {},      // Map<channelId → resolver> — corrèle requêtes SEARCH et réponses RESULTS
  cmpMode:      false,   // Boolean — overlay comparaison visible
  cmpLeft:      null,    // CommuneObject|null — commune gauche du comparateur
  cmpRight:     null,    // CommuneObject|null — commune droite du comparateur
  cmpSearchFor: null,    // 'left'|'right'|null — côté en cours de remplacement
}
```

### 5.3 Cycle de vie de l'état

```
DOMContentLoaded
  └─ fetch /data/index.json
       └─ worker.postMessage(INIT)
            └─ onmessage(READY) → state.workerReady = true
                 └─ boot() — lit URL → route vers renderHome|renderVille|renderComparePage
                      └─ Interactions utilisateur → changements URL → boot() à nouveau
```

### 5.4 Pattern de callback Worker (`wSearch`)

```javascript
// Génère un channelId unique → enregistre un resolver dans state.workerCbs
// → envoie SEARCH → worker répond RESULTS avec le même ch
// → resolver appelé → Promise résolue
// Timeout 5s de sécurité si le worker ne répond pas

function wSearch(query, limit=8) {
  return new Promise((resolve, reject) => {
    const ch = `MAIN_${Date.now()}_${Math.random()}`;
    state.workerCbs[ch] = resolve;
    worker.postMessage({ type: 'SEARCH', payload: { query, limit, ch } });
    setTimeout(() => {
      if (state.workerCbs[ch]) {
        delete state.workerCbs[ch];
        resolve([]);  // timeout → résout avec liste vide
      }
    }, 5000);
  });
}
```

### 5.5 Pas de state management framework

**Choix délibéré (ADR-02) :** Aucun Redux, MobX, Zustand, Pinia ou Context API. La complexité du projet (5 écrans max, pas de mutations concurrentes) ne justifie pas de framework de state. L'URL remplace avantageusement un store pour la persistance et le partage de liens.

---

## 6. Fonctions Utilitaires Partagées

Ces fonctions sont utilisées dans plusieurs contextes de `index.html` :

| Fonction | Signature | Rôle |
|---|---|---|
| `fetchJSON(url)` | `async (url) → Object\|null` | Fetch avec `cache:'no-store'`, retourne null si erreur |
| `fetchExternal(url)` | `async (url) → Object\|null` | Fetch sans header custom (évite preflight CORS) |
| `fetchDep(dep)` | `async (dep) → Array\|null` | Fetch `data/details/{dep}.json` |
| `fetchByInsee(code)` | `async (code) → CommuneObject\|null` | Cherche commune dans dep.json, fallback API Géo |
| `fetchBySlug(slug)` | `async (slug) → CommuneObject\|null` | Cherche par nom → API Géo |
| `geoMap(apiGeoObj)` | `(obj) → CommuneObject` | Convertit réponse API Géo en objet interne |
| `enrich(c)` | `async (c) → void` | Fallback DVF CEREMA si `c.immo` absent |
| `esc(s)` | `(str) → String` | Escape HTML (< > & " ') — **anti-XSS critique** |
| `getDep(code_insee)` | `(str) → String` | Extrait code département depuis code INSEE |

**Note sécurité :** `esc()` doit être appelée sur **toutes** les données utilisateur ou API injectées en innerHTML. Son absence est la principale source potentielle de XSS dans ce projet.

---

## 7. Design System (Tailwind CSS CDN)

**Version :** Tailwind CSS v3 via CDN (`<script src="https://cdn.tailwindcss.com">`)

**Contraintes spécifiques CDN :**
- Aucun `@apply` ni directive PostCSS
- Config inline uniquement via `tailwind.config = { ... }` dans `<script>`
- Classes purgées dynamiquement à la volée — pas de JIT persistant
- Classes dynamiques construites par concaténation de strings DOIVENT utiliser des noms complets (`text-red-500` et non `text-${color}-500`)

**Palettes utilisées :** Bleu (interactif), Gris (neutre), Vert (positif/fibre), Ambre/Rouge (alertes), Emerald (carburants)

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
