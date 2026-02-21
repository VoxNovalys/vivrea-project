# VivreÀ — Architecture

**Date :** 2026-02-21
**Type :** Monolithe · Web + Data
**Architecture :** Static JAMstack (sans build step) + Pipeline ETL Python

---

## Résumé exécutif

VivreÀ est un site statique open data couvrant les ~35 000 communes françaises (immobilier DVF, fibre ARCEP, carburants, démographie, sécurité, qualité de l'air, socio-économique). Il se compose de deux couches :

1. **Frontend** : SPA vanilla HTML/CSS/JS sans framework, déployée sur Vercel et GitHub Pages
2. **Pipeline de données** : Script Python 3.12 (`update.py`) générant des fichiers JSON statiques via 8 sources open data gouvernementales

Il n'y a pas de serveur d'application, pas de base de données runtime, et pas de bundler/transpileur. Toute la logique s'exécute côté client ou lors de la phase CI/CD. **Python ne tourne jamais en production** — c'est uniquement un générateur de fichiers statiques.

---

## Stack Technologique

### Couche Frontend (Web)

| Catégorie | Technologie | Version | Justification |
|---|---|---|---|
| Langage | HTML5 | — | 3 fichiers de page (index.html, explorer.html, 404.html) |
| Langage | CSS3 | — | Styles inline + animations custom (shimmer, fadeUp) |
| Langage | JavaScript | ES2020+ vanilla | SPA, routing, Fetch API, Web Worker — aucun framework |
| CSS Framework | Tailwind CSS | v3 (CDN) | Utilitaires, dark mode classe, responsive — sans PostCSS |
| Typographie | Inter | Google Fonts 300–700 | Police principale |
| Web API | Web Worker API | — | `search.worker.js` — filtrage 35k communes hors-thread |
| Web API | History API | — | Routing SPA via `pushState` / `popstate` |
| Web API | Fetch API | — | Chargement JSON, appels APIs externes |
| Web API | sessionStorage | — | Hack GitHub Pages SPA (404.html → redirection /) |
| Monétisation | Google AdSense | ca-pub-2156803616781959 | Publicités sur toutes les pages |
| Affiliation | Amazon Associates | tag vivrea-21 | Liens affiliés contextuels par commune |

### Couche Pipeline de Données (Python)

| Catégorie | Technologie | Version | Justification |
|---|---|---|---|
| Langage | Python | 3.12 | Script ETL complet (update.py, 8 étapes) |
| Bibliothèque | requests | >=2.31.0 | Seule dépendance externe — appels HTTP APIs |
| Stdlib | json | — | Sérialisation JSON compact ou indenté |
| Stdlib | zipfile, io | — | Extraction ZIPs (ARCEP, Carburants, Filosofi, Chômage) |
| Stdlib | xml.etree.ElementTree | — | Parsing flux XML carburants |
| Stdlib | csv, gzip | — | Lecture CSV.GZ SSMSI, CSV Filosofi/Chômage |
| Stdlib | struct | — | Lecture binaire DBF Shapefile ARCEP (sans dépendance externe) |
| Stdlib | pathlib, datetime, logging | — | Utils système et traçabilité |

### Infrastructure & DevOps

| Catégorie | Technologie | Notes |
|---|---|---|
| Déploiement primaire | Vercel | SPA rewrites (5 routes), cache CDN data/ (max-age 3600, stale-while-revalidate 86400) |
| Déploiement secondaire | GitHub Pages | Via GitHub Actions, automatique sur push main |
| CI/CD | GitHub Actions | `.github/workflows/main.yml` — run update.py + commit data/ + deploy Pages |
| Runner | ubuntu-latest | Python 3.12, `pip install requests` |
| Versionning | Git | Déclencheur CI/CD + commit automatique `data/` par `github-actions[bot]` |

---

## Architecture des Données

### Fichiers statiques produits

| Fichier | Format | Rôle |
|---|---|---|
| `data/index.json` | Array of arrays `[nom, code_insee, cp, pop]` | Index 34 875 communes (<1.5 MB), chargé par Web Worker |
| `data/details/{dep}.json` | Array d'objets enrichis | 96 fichiers par département — données complètes par commune |
| `data/carburants.json` | Objet `{updated_at, nb_stations, stations:[…]}` | ~11 000 stations-service, prix temps réel normalisés |
| `data/meta.json` | Objet JSON | Métadonnées pipeline (last_update, nb_communes, version, sources) |

### Structure d'un objet commune enrichi (`data/details/{dep}.json`)

```json
{
  "code_insee":   "75056",           // String 5 chars, toujours
  "nom":          "Paris",
  "codes_postaux": ["75001", "..."],
  "cp":           "75001",           // Premier CP (String)
  "code_dep":     "75",
  "population":   2145906,
  "surface_km2":  105,
  "lat":          48.8566,
  "lon":          2.3522,
  "immo": {
    "prix_m2_median":  9850,         // DVF CEREMA, €/m² médian appt.
    "loyer_median":    null,
    "nb_transactions": 12450,
    "annee_dvf":       2023
  },
  "fibre_pct":    98.5,              // ARCEP, % locaux raccordables FTTH (peut être absent)
  "securite": {
    "taux_pour_mille": 28.4,         // SSMSI, faits pour 1000 hab. (communes > 2000 hab.)
    "annee":           2022
  },
  "air": {
    "iqa_moyen": 2.1,                // ATMO EAQI, 1=Bon … 6=Extrêmement mauvais
    "label":     "Bon",
    "annee":     2023
  },
  "socio": {
    "revenu_median":  24500,         // Filosofi INSEE 2021, €/UC/an
    "taux_chomage":   8.2,           // %, actifs 15-64 ans
    "taux_pauvrete":  13.5           // %, seuil 60% médiane nationale
  }
}
```

> **Tous les champs sont optionnels sauf `code_insee`, `nom`, `code_dep`.** L'UI affiche `—` si un champ est absent. Ne jamais supposer qu'un champ existe.

### Sources de Données Externes (Pipeline ETL)

| API | Organisme | Étape | Format | Données |
|---|---|---|---|---|
| `geo.api.gouv.fr` | Etalab | 1 | JSON | Communes, GPS, population, surface |
| `apidf-preprod.cerema.fr` | CEREMA | 2 | JSON paginé | DVF — prix immobilier médian m² (appt.) |
| `data.gouv.fr` (ARCEP THD) | ARCEP | 3 | ZIP/Shapefile/DBF | Fibre FTTH — taux raccordement par commune |
| `donnees.roulez-eco.fr` | Roulez Éco | 4 | XML/ZIP | Prix carburants temps réel |
| `data.gouv.fr` (SSMSI) | Min. Intérieur | 5 | CSV.GZ (~36 Mo) | Délinquance communale toutes catégories |
| `data.atmo-france.org` | ATMO France | 6 | WFS CSV | Qualité de l'air — IQA EAQI annuel |
| `insee.fr` (Filosofi 2021) | INSEE | 7 | ZIP CSV | Revenus médians, taux de pauvreté |
| `data.gouv.fr` (Chômage) | INSEE | 8 | ZIP CSV | Taux de chômage par commune |

---

## Patterns d'Architecture

### Pattern 1 : Static JAMstack (sans build step)

```
GitHub Actions (CI/CD)
    └─► update.py (Python 3.12)
            ├─ Étape 1 : geo.api.gouv.fr  → data/index.json
            ├─ Étapes 2-8 : APIs diverses → data/details/{dep}.json
            │                             → data/carburants.json
            │                             → data/meta.json
            └─ git commit data/ && git push
                    └─► Vercel CDN + GitHub Pages (auto-deploy)
```

Aucun serveur d'application ni base de données. Toutes les données sont des fichiers JSON servis statiquement. Python ne tourne que lors des runs CI/CD.

### Pattern 2 : SPA History API (sans framework router)

**Table de routage complète :**

| URL | Handler JS | Template | Notes |
|---|---|---|---|
| `/` | `renderHome()` | `#tpl-home` | Page d'accueil + recherche + carburants |
| `/ville/:code` | `renderVille(slug)` | HTML généré | Fiche commune complète (code INSEE ou slug nom) |
| `/comparer/:a[/:b]` | `renderComparePage(codes)` | HTML généré | Mode comparaison 2 colonnes |
| `/a-propos` | `renderStatic('tpl-apropos')` | `#tpl-apropos` | Page statique |
| `/mentions-legales` | `renderStatic('tpl-mentions')` | `#tpl-mentions` | Page statique |
| `/explorer` | — | `explorer.html` | Page autonome (pas SPA) |
| `*` | `render404()` | HTML inline | Affichage 404 SPA (pas de rechargement) |

```
Navigateur
    ├─ Charge index.html (unique point d'entrée SPA)
    ├─ boot() → initWorker() + loadIndex() + route(location.pathname)
    ├─ navigate(path) → history.pushState() → route(path)
    └─ popstate → route() (bouton retour navigateur)

Vercel rewrites (vercel.json) :
    /ville/:code      → /index.html
    /comparer/:path*  → /index.html
    /a-propos         → /index.html
    /mentions-legales → /index.html
    /explorer         → /explorer.html
```

> **Toute nouvelle route SPA doit être ajoutée dans les deux** : `getRoute()` dans `index.html` ET `vercel.json`.

### Pattern 3 : Web Worker asynchrone + Fallback inline

```
Thread principal (index.html)
    ├─ new Worker('/search.worker.js')       ← tentative fichier externe
    │       ↓ onerror (CORS, file://, etc.)
    ├─ new Worker(Blob([WORKER_SRC]))        ← fallback inline (WORKER_SRC string)
    ├─ postMessage({type:'INIT', payload: index_array})
    │       → Worker: normalize 34k noms → postMessage({type:'READY'})
    ├─ postMessage({type:'SEARCH', payload:{query, limit, ch}})
    │       → Worker: scoring + tri → postMessage({type:'RESULTS', payload:{results, ch}})
    └─ workerCbs[ch](results) → résolution Promise (timeout sécurité 5s)
```

> **WORKER_SRC et search.worker.js implémentent le même algorithme.** Toute modification de l'un doit être répercutée sur l'autre.

### Pattern 4 : Cache mémoire en cascade (Lazy loading par département)

```
Requête commune (ex: Paris, code 75056)
    1. depCache['75'] existe ? → retour immédiat (mémoire JS, durée = session onglet)
    2. fetch /data/details/75.json ({ cache: 'default' } → HTTP cache navigateur)
    3. Recherche code_insee dans le tableau
    4. Fallback : geo.api.gouv.fr/communes/75056 ({ cache: 'no-store' })
```

> `depCache` est un objet JS (`{}`) initialisé vide au chargement — il disparaît à la fermeture de l'onglet. Aucun `localStorage`, aucun `sessionStorage` pour les données communes.

### Pattern 5 : Module IIFE (FuelSearch)

```javascript
const FuelSearch = (() => {
  let _promise = null;  // Cache Promise singleton (1 seul fetch par session)
  let _flat    = null;  // Données normalisées en mémoire
  // ... (fonctions privées : load, normalize, search, render)
  return { init };      // API publique minimale
})();
```

**Ordre de chargement critique :**
```html
<script>/* Script principal index.html */</script>   ← définit renderHome(), FuelSearch.init()
<script src="/fuel.js"></script>                      ← définit FuelSearch APRÈS
```
`renderHome()` appelle `FuelSearch.init()` avec `typeof FuelSearch !== 'undefined'` en garde — si `fuel.js` échoue à charger, la recherche carburants est simplement absente, sans erreur.

### Pattern 6 : Lazy loading + Graceful Degradation

```
Chargement page ville
    ├─ fetchByInsee(code)
    │       ├─ depCache hit → données locales
    │       └─ fetch /data/details/{dep}.json → null si réseau down
    ├─ Promise.all([fetchDVF(), fetchFibreARCEP()])  ← parallèle, silencieux
    │       ├─ DVF CEREMA : null si API down → champ immo absent, _immoLinks affiché quand même
    │       └─ ARCEP client-side : null si data.arcep.fr down → fibre_pct absent
    └─ buildVilleHTML(commune) → affiche '—' pour tout champ null/undefined
```

> Toutes les sections de la fiche ville sont optionnelles. Un champ absent n'est jamais une erreur — il affiche `—`. Ne jamais supposer qu'une API externe répondra.

### Pattern 7 : URL comme source de vérité

```
/ville/75056        → Paris, fiche complète
/comparer/75056/69123 → Paris vs Lyon, partageable, bookmarkable
```

L'URL encode tout l'état de navigation. Pas de state applicatif persistant entre pages. Le rechargement d'une URL doit toujours donner le même résultat.

### Pattern 8 : Dual Render Mode

```javascript
buildVilleHTML(commune)   // Vue complète : fiche avec tous les blocs (immo, fibre, sécurité, air, socio, carburants, Amazon)
buildCompactHTML(commune) // Vue réduite  : colonne comparaison (pop, superficie, fibre, immo, carburants)
```

Les deux fonctions acceptent le **même objet commune** — elles ne diffèrent que dans la densité d'affichage. `buildCompactHTML` est utilisé dans la colonne B du mode comparaison.

---

## Décisions Architecturales (ADR)

### ADR-001 : Tailwind CSS v3 via CDN (pas npm)

- **Contexte** : Site statique sans build step, hébergé sur Vercel/GitHub Pages
- **Décision** : CDN `https://cdn.tailwindcss.com` avec `tailwind.config = {...}` inline dans chaque `<script>`
- **Conséquences** : Pas de `@apply`, pas de purge CSS, config dupliquée dans chaque HTML, ~300 KB non-optimisé mais **zéro pipeline, zéro Node.js requis**
- **Alternatives rejetées** : npm + PostCSS + purge (complexité toolchain), UnoCSS (moins répandu)

### ADR-002 : Vanilla JS, pas de framework

- **Contexte** : Données open data en lecture seule, pas d'état distribué, pas de composants réactifs complexes
- **Décision** : History API + template literals HTML + Web Worker pour la recherche
- **Conséquences** : Pas de Virtual DOM, duplication explicite (`esc()`, `getDep()`), pas de composants formels
- **Alternatives rejetées** : React/Vue (build obligatoire, bundle), Alpine.js (non retenu), Svelte (build)

### ADR-003 : Web Worker + fallback WORKER_SRC inline

- **Contexte** : 35k communes à filtrer sans bloquer le thread UI — GitHub Pages sert parfois le Worker avec un MIME type incorrect
- **Décision** : Worker externe `/search.worker.js` + `WORKER_SRC` Blob comme fallback sur `onerror`
- **Conséquences** : Deux implémentations du même algorithme à synchroniser — une divergence serait silencieuse
- **Alternatives rejetées** : Filtrage synchrone (bloque l'UI), WebAssembly (surcomplex pour ce cas)

### ADR-004 : data/index.json en array of arrays

- **Contexte** : Payload envoyé au Worker via `postMessage` + `fetch` — doit être le plus compact possible
- **Décision** : `[nom, code_insee, cp, pop]` au lieu d'objets `{nom:…, code_insee:…}`
- **Conséquences** : Code moins lisible (`c[0]`, `c[1]`, `c[2]`, `c[3]`), mais **~40% plus compact** (~1.4 MB vs ~2.3 MB)
- **Alternatives rejetées** : Array d'objets (trop verbeux), API search server (coût/complexité)

### ADR-005 : Python stdlib uniquement (sauf requests)

- **Contexte** : Pipeline ETL tournant dans GitHub Actions — `pip install` doit être minimal et reproductible
- **Décision** : Pas de pandas, numpy, lxml, dbfread — lecteur DBF maison via `struct` (~80 lignes)
- **Conséquences** : Code plus verbeux pour le parsing DBF, mais **dépendance unique et installation <1s**
- **Alternatives rejetées** : pandas (100 MB+, inutile pour ce use case), dbfread (dépendance externe non nécessaire)

### ADR-006 : Données JSON committées dans Git

- **Contexte** : Pas de serveur d'application, pas de base de données, déploiement statique uniquement
- **Décision** : Python ETL → JSON statique → `git add data/ && git commit` par `github-actions[bot]` → Vercel CDN
- **Conséquences** : Historique Git pollué par les commits data automatiques, clone initial plus lourd, mais **aucune infra runtime requise**
- **Alternatives rejetées** : S3/R2 externe (dépendance cloud payante), API backend live (coût, complexité, cold starts)

---

## Règles Critiques d'Implémentation

> Ces règles sont extraites du `_bmad-output/project-context.md` — **toujours respecter lors de modifications**.

### code_insee est TOUJOURS une String

```javascript
// ✅ CORRECT
code_insee: String(c.code).padStart(5, '0')  // "01001", "75056", "2A004"

// ❌ FAUX — détruit les zéros initiaux ET les codes corses
code_insee: parseInt(c.code)  // 1001, 75056, NaN (2A004 → NaN)
```

Il y a exactement 96 départements, dont `2A` (Corse-du-Sud) et `2B` (Haute-Corse) qui ne sont pas numériques. Tout `parseInt` ou conversion Number sur un code INSEE est une régression garantie.

### Normalisation prix carburant

```python
# Python (update.py)
def normalize_fuel_price(raw_str):
    raw = float(cleaned)
    if raw > 100:
        return round(raw / 1000, 4)  # millièmes → 1732 → 1.732
    return round(raw, 4)             # décimal  → 1.732 → 1.732
```

```javascript
// JavaScript (index.html)
function fmtFuelPrice(raw) {
    if (raw == null || raw === 0) return '—';
    const price = raw > 100 ? raw / 1000 : raw;  // garde-fou côté client
    return price.toFixed(3) + ' €';
}
```

### Tailwind CSS v3 CDN — Contraintes strictes

- **Pas de `@apply`** — seulement des classes utilitaires inline dans le HTML
- **Pas de `package.json`, pas de `tailwind.config.js` fichier** — la config est inline dans `<script>`
- **Tokens custom** : `surface:#111111`, `card:#1a1a1a`, `border:#2a2a2a`
- **Dupliqué** entre `index.html` et `explorer.html` — c'est intentionnel (ADR-002)

> Ajouter un `package.json` avec `tailwindcss` en dépendance ferait détecter le projet comme un projet Node.js par Vercel → comportement de build différent → régression probable.

### explorer.html est une page autonome (pas SPA)

- Navigation via `<a href="/ville/{code}">` standard — **pas `navigate()`**
- `getDep()` et `esc()` sont dupliqués localement — ne pas importer depuis `index.html`
- `window.location.href = '/ville/' + code` dans `goToVille()` — navigation native, pas History API
- Pas de Web Worker, pas de `FuelSearch`, pas de mode comparaison, pas de `depCache`

### Ordre de chargement des scripts (index.html)

```html
<script>/* Script principal : définit navigate(), route(), renderHome()... */</script>
<script src="/fuel.js"></script>  <!-- DOIT être après : renderHome() appelle FuelSearch.init() -->
```

`fuel.js` est chargé **en dernier** car `renderHome()` vérifie `typeof FuelSearch !== 'undefined'` avant d'appeler `FuelSearch.init()`. Inverser l'ordre ne casse rien, mais charger `fuel.js` avant crée une dépendance sur `FuelSearch` avant que le DOM soit prêt.

---

## Anti-patterns et Scénarios d'Échec à Éviter

> Issue du Pre-mortem — ces erreurs ont une forte probabilité d'être introduites par un agent IA ou un développeur non familier avec les contraintes du projet.

| # | Anti-pattern | Symptôme | Cause | Prévention |
|---|---|---|---|---|
| A1 | `parseInt(code_insee)` | Communes corses introuvables, zéros initiaux perdus | Incompréhension String vs Number | Toujours `String(code).padStart(5,'0')` |
| A2 | `@apply` dans une règle CSS | Styles silencieusement ignorés | Tailwind CDN ne supporte pas `@apply` | Classes utilitaires uniquement |
| A3 | Création `package.json` + `npm install tailwindcss` | Build Vercel échoue ou change de comportement | Confond Tailwind CDN avec npm Tailwind | ADR-001 : CDN uniquement, pas npm |
| A4 | Conversion `data/index.json` en array d'objets | Worker casse (`c[0]` undefined) | "Amélioration" lisibilité sans lire ADR-004 | Format array of arrays est intentionnel |
| A5 | `navigate()` utilisé dans `explorer.html` | Erreur runtime (fonction inexistante) | Copie depuis `index.html` sans vérifier le contexte | `explorer.html` est autonome, navigation native uniquement |
| A6 | Affichage prix brut sans `fmtFuelPrice()` | Affiche `1732` au lieu de `1.732 €` | Normalisation raw > 100 inconnue | Toujours passer par `fmtFuelPrice()` |
| A7 | `import`/`export` ES6 ajouté pour "moderniser" | SyntaxError ou Worker silencieusement mort | Pas de bundler, pas de `type="module"` | ES2020+ vanilla uniquement, pas de modules ES |
| A8 | Suppression de `WORKER_SRC` inline | Recherche morte sur GitHub Pages | "Fallback inutile car worker.js existe" | Le fallback est nécessaire pour GitHub Pages/CORS |
| A9 | Ajout d'une route SPA sans màj `vercel.json` | 404 réel sur accès direct ou rechargement | Oubli de la configuration Vercel | Toujours synchroniser `getRoute()` ET `vercel.json` |
| A10 | `depCache` supposé persistant entre pages | Données rechargées inutilement ou données périmées | Confusion avec localStorage | `depCache` est mémoire session onglet uniquement |

---

## Analyse de Défaillance par Composant

| Composant | Mode de défaillance | Impact utilisateur | Mitigation actuelle | Gap restant |
|---|---|---|---|---|
| `data/index.json` absent | Fichier manquant (push raté) | Recherche impossible | Worker affiche "Index indisponible" | Aucun retry automatique |
| `search.worker.js` CORS | Worker externe bloqué | Recherche dégradée | Fallback `WORKER_SRC` Blob inline | WORKER_SRC doit rester synchronisé |
| DVF CEREMA URL changée | 404 sur l'endpoint | Données immo absentes | Retry années N-2, N-3, N-1 puis abandon silencieux | URL CEREMA peut changer à nouveau |
| ARCEP CKAN client-side | `data.arcep.fr` hors ligne | `fibre_pct` absent en fallback | `null` retourné silencieusement | Fallback mort depuis 2025, à supprimer |
| `carburants.json` périmé | Pas de cron GitHub Actions | Prix affichés mais datés | Données présentes mais non fraîches | **Cron non configuré** — risque majeur |
| Vercel rewrite manquant | Nouvelle route sans rewrite | 404 réel sur accès direct | Liste explicite des 5 routes dans vercel.json | Toute nouvelle route doit être ajoutée |
| `depCache` vide (rechargement) | Perte du cache mémoire | Re-fetch `details/{dep}.json` | HTTP cache navigateur (max-age Vercel) | Normal — comportement attendu |
| API externe down (ETL) | `safe_get()` retourne `None` | Champ absent dans les données | 3 retries avec backoff exponentiel | Données absentes pour tout le run |

---

## Limites et Dette Technique Connue

| Problème | Priorité | Impact | Recommandation |
|---|---|---|---|
| **Pas de `schedule: cron` dans main.yml** | 🔴 Haute | Données jamais mises à jour automatiquement | Ajouter `schedule: cron: '0 3 * * 1'` (lundi 3h UTC) |
| **ARCEP CKAN client-side mort** (`fetchFibreARCEP`) | 🟠 Moyenne | Fibre jamais enrichie côté navigateur | Supprimer `fetchFibreARCEP()` — données sont dans le JSON pipeline |
| **`getDep()`, `esc()`, Tailwind config dupliqués** | 🟡 Faible | Maintenance double si modification | Extraire un `common.js` chargé par les deux pages |
| **Aucun test Python ni JS** | 🟠 Moyenne | Régressions non détectées | Ajouter `pytest` (update.py) + `Playwright` (E2E) |
| **`package-lock.json` vide** | 🟡 Faible | Confusion sur le toolchain Node | Supprimer le fichier (aucun package npm utilisé) |
| **WORKER_SRC et search.worker.js non synchronisés** | 🟠 Moyenne | Comportement différent selon le contexte d'exécution | Ajouter un test ou un commentaire de synchronisation |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
_Enrichi via Advanced Elicitation : ADR, Pre-mortem, Critique, Failure Mode Analysis, First Principles_
