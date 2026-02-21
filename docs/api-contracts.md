# VivreÀ — Contrats API & Protocoles de Communication

**Date :** 2026-02-21

Ce document couvre l'ensemble des interfaces de communication du projet :
1. Fetches internes (fichiers JSON statiques servis par Vercel/GitHub Pages)
2. Appels externes côté navigateur (APIs tierces)
3. Protocole Web Worker (messages typés)
4. Appels du pipeline Python ETL (APIs gouvernementales)

---

## 1. Fetches Internes — Données Statiques

Ces appels accèdent aux fichiers JSON générés par le pipeline Python et servis via CDN.

### 1.1 Index des communes

```
GET /data/index.json
Cache: 'default' (HTTP cache navigateur)
Cache-Control Vercel: public, max-age=3600, stale-while-revalidate=86400
```

**Réponse :** Array of arrays JSON

```javascript
// Format : [nom, code_insee, cp, pop]
[
  ["Paris",    "75056", "75001", 2145906],
  ["Lyon",     "69123", "69001", 522969],
  ["Ajaccio",  "2A004", "20090", 72176],   // code Corse : toujours String
  // ... 34 875 entrées
]
```

**Utilisé par :** `loadIndex()` → `worker.postMessage({type:'INIT', payload})` dans `index.html`
**Utilisé par :** `loadData()` dans `explorer.html`
**Taille typique :** < 1.5 MB

---

### 1.2 Détails par département

```
GET /data/details/{dep}.json
Cache: 'default' (HTTP cache navigateur)
dep: code département String (ex: "75", "2A", "971")
```

**Réponse :** Array d'objets commune enrichis

```javascript
[
  {
    "code_insee":    "75056",       // String 5 chars — JAMAIS Number
    "nom":           "Paris",
    "codes_postaux": ["75001", "75002", "..."],
    "cp":            "75001",       // String
    "code_dep":      "75",          // String
    "population":    2145906,       // Number, peut être 0
    "surface_km2":   105,           // Number, peut être null
    "lat":           48.8566,       // Number, peut être null
    "lon":           2.3522,        // Number, peut être null

    // Champs enrichis — TOUS OPTIONNELS (peuvent être absents)
    "immo": {
      "prix_m2_median":  9850,      // Number (€/m²)
      "loyer_median":    null,      // toujours null actuellement
      "nb_transactions": 12450,    // Number, peut être null
      "annee_dvf":       2023      // Number (année)
    },
    "fibre_pct":  98.5,             // Number (%), peut être absent
    "securite": {
      "taux_pour_mille": 28.4,     // Number
      "annee":           2022      // Number
    },
    "air": {
      "iqa_moyen": 2.1,            // Number (1–6 EAQI)
      "label":     "Bon",          // String
      "annee":     2023            // Number
    },
    "socio": {
      "revenu_median":  24500,     // Number (€/UC/an)
      "taux_chomage":   8.2,       // Number (%)
      "taux_pauvrete":  13500      // Number (%)
    }
  }
]
```

**Utilisé par :** `fetchDep(dep)` → `fetchByInsee()` → `fetchBySlug()` dans `index.html`
**Taille typique :** Variable (~100 Ko à ~2 Mo selon le département)

---

### 1.3 Prix carburants

```
GET /data/carburants.json
Cache: 'default' dans FuelSearch, 'no-store' dans fetchJSON
Cache-Control Vercel: public, max-age=3600, stale-while-revalidate=86400
```

**Réponse :**

```javascript
{
  "updated_at":  "2026-02-20T19:29:56.986639Z",  // ISO 8601
  "nb_stations": 11432,
  "stations": [
    {
      "nom":      "Total Energies",
      "cp":       "75012",
      "ville":    "Paris",
      "adresse":  "12 Rue de Lyon",
      "lat":      48.8432,         // Number, peut être null
      "lon":      2.3698,          // Number, peut être null
      "prix": {
        "SP95":   1.732,           // Number (€, décimal) — JAMAIS millièmes
        "SP98":   1.869,
        "Gazole": 1.651,
        "E10":    1.689,
        "E85":    0.829,
        "GPLc":   null             // null si non disponible
      },
      "maj": {
        "SP95":   "2026-02-20T14:23:00",  // ISO, peut être absent
        "Gazole": "2026-02-20T14:23:00"
      }
    }
  ]
}
```

**Utilisé par :** `FuelSearch` (fuel.js) et `loadFuelIntoEl()` (index.html)
**Règle critique :** Les prix sont toujours en euros décimaux (ex: 1.732). Si `raw > 100` → diviser par 1000 (garde-fou).

---

### 1.4 Métadonnées

```
GET /data/meta.json
Cache: standard
```

**Réponse :**

```javascript
{
  "last_update":  "2026-02-20T19:29:56.986639Z",
  "nb_communes":  34875,
  "version":      "2.2",
  "sources": {
    "communes":    "https://geo.api.gouv.fr",
    "immobilier":  "https://apidf-preprod.cerema.fr",
    "fibre":       "https://data.arcep.fr",
    "carburants":  "https://donnees.roulez-eco.fr/opendata/instantane"
  }
}
```

---

## 2. Appels Externes — Côté Navigateur

Ces appels sont effectués via `fetchJSON()` (avec `cache:'no-store'`) ou `fetchExternal()` (sans header custom, évite le preflight CORS).

### 2.1 API Géo — Fallback commune par code INSEE

```
GET https://geo.api.gouv.fr/communes/{code_insee}
    ?fields=code,nom,codesPostaux,codeDepartement,population,surface,centre
Cache: 'no-store'
```

**Utilisé par :** `fetchByInsee()` si commune absente du fichier `details/{dep}.json`

**Réponse :**

```javascript
{
  "code":             "75056",
  "nom":              "Paris",
  "codesPostaux":     ["75001", "75002"],
  "codeDepartement":  "75",
  "population":       2145906,
  "surface":          10540,           // hectares (à diviser par 100 pour km²)
  "centre": {
    "type":        "Point",
    "coordinates": [2.3522, 48.8566]   // [lon, lat]
  }
}
```

**Mapping via `geoMap()`** :

```javascript
function geoMap(c) {
  const coords = c.centre?.coordinates || [null, null];
  return {
    code_insee:    String(c.code).padStart(5, '0'),
    nom:           c.nom,
    codes_postaux: (c.codesPostaux || []).map(String),
    cp:            String((c.codesPostaux || [])[0] || ''),
    code_dep:      String(c.codeDepartement || ''),
    population:    c.population || 0,
    surface_km2:   c.surface ? Math.round(c.surface / 100) : null,
    lat: coords[1], lon: coords[0],
  };
}
```

---

### 2.2 API Géo — Fallback commune par nom (slug)

```
GET https://geo.api.gouv.fr/communes
    ?nom={nom_encodé}&fields=code,nom,codesPostaux,codeDepartement,population,surface,centre&limit=1
Cache: 'no-store'
```

**Utilisé par :** `fetchBySlug()` lorsque l'URL contient un slug textuel au lieu d'un code INSEE.

---

### 2.3 DVF CEREMA — Données immobilières (fallback client-side)

```
GET https://apidf-preprod.cerema.fr/indicateurs/dv3f/prix/annuel/
    ?code={code_insee}&echelle=communes&annee={annee}
Cache: 'no-store' (via fetchExternal)
```

**Stratégie :** Tentée pour les années N-2, N-3, N-4 en séquence jusqu'à obtenir un résultat.

**Réponse :**

```javascript
{
  "count": 1,
  "results": [
    {
      "pxm2_median_cod111": 9850.0,    // Prix médian m² appartements
      "nbtrans_cod111":     345         // Nombre de transactions
    }
  ]
}
```

**Note :** Ce fallback est déclenché seulement si `commune.immo` est absent du fichier `details/{dep}.json`. L'URL CEREMA a changé en 2025 (ancienne `/indicateurs/dv3f/communes` → 404).

---

### 2.4 ARCEP CKAN — Fibre FTTH (fallback client-side, MORT)

```
GET https://data.arcep.fr/api/3/action/datastore_search
    ?resource_id={rid}&filters={"code_commune":"{code_insee}"}&limit=5
```

> ⚠️ **data.arcep.fr est hors ligne depuis 2025.** Ce fallback ne retourne jamais de données. La fonction `fetchFibreARCEP()` est à supprimer.

---

## 3. Protocole Web Worker

Communication par messages typés entre le thread principal (`index.html`) et le worker (`search.worker.js` ou WORKER_SRC inline).

### Messages entrants (thread principal → worker)

#### INIT

```javascript
worker.postMessage({
  type:    'INIT',
  payload: [[nom, code_insee, cp, pop], ...]  // data/index.json complet
})
```

**Effet :** Le worker normalise 34k noms (NFD lowercase sans diacritiques) et répond `READY`.

#### SEARCH

```javascript
worker.postMessage({
  type: 'SEARCH',
  payload: {
    query: "paris",   // String — terme de recherche brut
    limit: 8,         // Number — max résultats (défaut: 8)
    ch:    "MAIN_42"  // String — channel ID unique pour corréler la réponse
  }
})
```

### Messages sortants (worker → thread principal)

#### READY

```javascript
{ type: 'READY', payload: { size: 34875 } }
```

Déclenché après INIT. Met à jour `state.workerReady = true` et `state.workerSize`.

#### RESULTS

```javascript
{
  type: 'RESULTS',
  payload: {
    ch: "MAIN_42",   // Channel ID — corrèle avec workerCbs[ch]
    results: [
      { nom: "Paris", code_insee: "75056", cp: "75001", pop: 2145906 },
      // ... (limit entrées max)
    ]
  }
}
```

**Algorithme de scoring :**

| Score | Condition |
|---|---|
| 100 | Correspondance exacte normalisée |
| 90 | Code INSEE exact |
| 80 | Préfixe exact (commence par la requête) |
| 60 | Début de mot (séparateur `-` ou espace) |
| 40 | Contient la requête |
| 20 | Code postal commence par la requête (≥2 chars) |

**Timeout sécurité :** Si le worker ne répond pas en 5 secondes, `wSearch()` résout avec `[]`.

---

## 4. APIs Pipeline Python (update.py)

Ces appels sont effectués **uniquement lors du run CI/CD** (GitHub Actions), jamais en production navigateur.

### Session commune

```python
SESSION = requests.Session()
SESSION.headers = {"User-Agent": "VivreA-Bot/1.0 (+https://vivrea.vox-novalys.fr)"}
MAX_RETRIES = 3
RETRY_DELAY = 2  # secondes, multiplié par le numéro de tentative
```

### Étape 1 — API Géo Communes

```
GET https://geo.api.gouv.fr/departements?fields=code,nom&limit=200
GET https://geo.api.gouv.fr/departements/{code}/communes
    ?fields=code,nom,codesPostaux,codeDepartement,codeRegion,population,surface,centre
    &format=json&geometry=centre&limit=5000
```

### Étape 2 — DVF CEREMA (pagination)

```
GET https://apidf-preprod.cerema.fr/indicateurs/dv3f/prix/annuel/
    ?echelle=communes&annee={annee}&page_size=500&page={n}
```

Pagination via champ `next` dans la réponse. Sonde les années N-2, N-3, N-1 pour trouver des données disponibles.

**Champs utilisés :**
- `item["code"]` ou `item["code_commune"]` ou `item["codgeo"]` → code INSEE commune
- `item["pxm2_median_cod111"]` → prix médian m² appartements
- `item["nbtrans_cod111"]` → nombre de transactions

### Étape 3 — ARCEP data.gouv.fr (Shapefile)

```
GET https://www.data.gouv.fr/api/1/datasets/le-marche-du-haut-et-tres-haut-debit-fixe-deploiements/
→ Extraire l'URL du ZIP Commune le plus récent
GET {zip_url}  (≈31 Mo, timeout=180s)
→ Extraire le .dbf → _read_dbf() → calcul taux FTTH
```

**Colonnes DBF utilisées :**
- `INSEE_COM` → code INSEE commune (String, zfill(5))
- `ftth` → locaux raccordables FTTH (Number)
- `Locaux` → total locaux (Number)
- `fibre_pct = round(ftth / Locaux * 100, 1)`

### Étape 4 — Carburants (XML/ZIP)

```
GET https://donnees.roulez-eco.fr/opendata/instantane
→ Détecte ZIP (PK header) ou XML direct
→ Parse XML ElementTree → normalize_fuel_price()
```

**Normalisation lat/lon API :** Les coordonnées sont en 1/100000 de degré décimal.
```python
lat = round(float(lat_r) / 100000, 6)  # ex: 4884320 → 48.843200
```

### Étape 5 — SSMSI Criminalité

```
GET https://www.data.gouv.fr/api/1/datasets/{CRIME_DATASET}/
→ Trouver ressource CSV communale (format gz ou csv, titre contenant "commune")
GET {csv_gz_url}  (≈36 Mo)
→ gzip.decompress → csv.reader → agréger par code commune + année max
```

**Colonnes CSV :** `Code.commune`, `faits`, `POP`, `annee`
**Calcul :** `taux_pour_mille = sum(faits) / POP * 1000`

### Étape 6 — ATMO Qualité de l'air (WFS)

```
GET https://data.atmo-france.org/geoserver/ind/ows
    ?service=WFS&version=2.0.0&request=GetFeature&typeNames=ind:ind_atmo_com_an
    &outputFormat=csv&CQL_FILTER=annee={annee}
→ csv.reader → IQA moyen par commune + label EAQI
```

**Tentatives :** Années N-1, N-2, N-3 jusqu'à obtenir des données.

### Étape 7 — Filosofi INSEE (revenus)

```
GET https://www.insee.fr/fr/statistiques/fichier/7756729/base-cc-filosofi-2021-geo2025_csv.zip
→ zipfile → CSV → colonnes : codgeo, med21, tp6021 (pauvreté)
```

### Étape 8 — Chômage INSEE

```
GET https://www.data.gouv.fr/api/1/datasets/... (chômage BPE/INSEE)
→ ZIP → CSV → taux chômage par commune
```

---

## 5. Gestion des Erreurs et Comportements Dégradés

| Contexte | Comportement si erreur |
|---|---|
| `fetchJSON()` (JS) | Retourne `null` silencieusement — la section affiche `—` |
| `fetchExternal()` (JS) | Retourne `null` silencieusement — pas de preflight CORS |
| `safe_get()` (Python) | 3 retries avec backoff → log erreur → retourne `None` |
| Worker timeout (5s) | `wSearch()` résout avec `[]` — pas de résultat affiché |
| `data/index.json` absent | Worker affiche "Index indisponible" dans `#worker-status` |
| DVF CEREMA down | Bloc immo affiché sans prix, liens LBC/SeLoger restent visibles |
| ARCEP CKAN (client-side) | `null` silencieux — `fibre_pct` absent de l'objet commune |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
