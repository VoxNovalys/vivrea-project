# VivreÀ — Modèles de Données

**Date :** 2026-02-21

Ce document décrit l'ensemble des structures de données du projet : fichiers JSON statiques servis par le CDN, objets internes JavaScript, et structures intermédiaires du pipeline Python.

---

## 1. Schémas des Fichiers JSON Statiques

### 1.1 `data/index.json` — Index des communes

**Format :** Array of arrays (intentionnel — ~40% plus compact qu'un tableau d'objets)

```
[ [nom, code_insee, cp, pop], ... ]
```

| Position | Champ | Type | Contraintes |
|---|---|---|---|
| 0 | `nom` | String | Nom officiel de la commune |
| 1 | `code_insee` | String | 5 chars, zfill(5), JAMAIS Number |
| 2 | `cp` | String | Code postal (premier si plusieurs) |
| 3 | `pop` | Number | Population, peut être 0 |

**Exemples de valeurs :**
```javascript
["Paris",   "75056", "75001", 2145906]
["Ajaccio", "2A004", "20090", 72176]   // Corse : code toujours String
["Bettex",  "73034", "73260", 0]       // Population inconnue → 0
```

**Caractéristiques :**
- Taille : ~34 875 entrées, < 1.5 MB
- Chargé une seule fois au démarrage → transmis au Web Worker via `INIT`
- Le Worker normalise les noms (NFD lowercase, sans diacritiques) pour la recherche

---

### 1.2 `data/details/{dep}.json` — Détails par département

**Format :** Array d'objets commune enrichis. `dep` = code département String (ex: `"75"`, `"2A"`, `"971"`)

**Objet commune — champs de base (toujours présents) :**

| Champ | Type | Contraintes |
|---|---|---|
| `code_insee` | String | 5 chars, zfill(5). **INVARIANT CRITIQUE** |
| `nom` | String | Nom officiel |
| `codes_postaux` | Array\<String\> | Au moins 1 élément |
| `cp` | String | Premier code postal |
| `code_dep` | String | Code département (ex: `"75"`, `"2A"`) |
| `population` | Number | Peut être 0 |
| `surface_km2` | Number\|null | null si non disponible |
| `lat` | Number\|null | Latitude WGS84. null si non disponible |
| `lon` | Number\|null | Longitude WGS84. null si non disponible |

**Objet commune — champs enrichis (TOUS OPTIONNELS, peuvent être absents) :**

```javascript
// Immobilier (DVF CEREMA)
"immo": {
  "prix_m2_median":  9850,    // Number (€/m²), peut être null
  "loyer_median":    null,    // toujours null (champ réservé)
  "nb_transactions": 12450,   // Number, peut être null
  "annee_dvf":       2023     // Number (millésime des données)
}

// Télécommunications (ARCEP)
"fibre_pct": 98.5             // Number (%), peut être absent

// Sécurité (SSMSI/data.gouv.fr)
"securite": {
  "taux_pour_mille": 28.4,    // Number (crimes/délits pour 1000 hab.)
  "annee":           2022     // Number (millésime)
}

// Qualité de l'air (ATMO France WFS)
"air": {
  "iqa_moyen": 2.1,           // Number (échelle EAQI 1–6)
  "label":     "Bon",         // String ("Très bon"|"Bon"|"Moyen"|"Dégradé"|"Mauvais"|"Très mauvais")
  "annee":     2023           // Number (millésime)
}

// Données socio-économiques (Filosofi + INSEE BPE)
"socio": {
  "revenu_median":  24500,    // Number (€/UC/an)
  "taux_chomage":   8.2,      // Number (%)
  "taux_pauvrete":  13500     // Number (%, ou valeur absolue — champ en cours de stabilisation)
}
```

**Taille typique :** 100 Ko à 2 Mo selon le département

---

### 1.3 `data/carburants.json` — Prix carburants

**Format :** Objet racine avec métadonnées + tableau de stations

```javascript
{
  "updated_at":  "2026-02-20T19:29:56.986639Z",  // ISO 8601 UTC
  "nb_stations": 11432,                           // Number
  "stations": [ ...StationObject ]
}
```

**Objet Station :**

| Champ | Type | Contraintes |
|---|---|---|
| `nom` | String | Nom de l'enseigne |
| `cp` | String | Code postal |
| `ville` | String | Nom de la ville |
| `adresse` | String | Adresse complète |
| `lat` | Number\|null | Latitude WGS84 |
| `lon` | Number\|null | Longitude WGS84 |
| `prix` | Object | Clés: SP95, SP98, Gazole, E10, E85, GPLc |
| `maj` | Object | Clés: carburant → timestamp ISO |

**Objet Prix :**
```javascript
"prix": {
  "SP95":   1.732,   // Number (€, décimal) — JAMAIS en millièmes
  "SP98":   1.869,
  "Gazole": 1.651,
  "E10":    1.689,
  "E85":    0.829,
  "GPLc":   null     // null si non disponible
}
```

**Règle critique :** Si `raw > 100` → diviser par 1000 (garde-fou contre données source en millièmes).

---

### 1.4 `data/meta.json` — Métadonnées du dataset

```javascript
{
  "last_update":  "2026-02-20T19:29:56.986639Z",  // ISO 8601 UTC
  "nb_communes":  34875,                            // Number
  "version":      "2.2",                            // String sémantique
  "sources": {
    "communes":    "https://geo.api.gouv.fr",
    "immobilier":  "https://apidf-preprod.cerema.fr",
    "fibre":       "https://data.arcep.fr",
    "carburants":  "https://donnees.roulez-eco.fr/opendata/instantane"
  }
}
```

---

## 2. Objets Internes JavaScript

### 2.1 Objet Commune Normalisé (mémoire JS)

Produit par `geoMap()` (depuis API Géo) ou directement depuis `details/{dep}.json`. C'est la forme canonique manipulée par toutes les fonctions JS.

```javascript
{
  // Champs de base — toujours présents après normalisation
  code_insee:    "75056",          // String 5 chars
  nom:           "Paris",
  codes_postaux: ["75001", ...],   // Array<String>
  cp:            "75001",          // String
  code_dep:      "75",             // String
  population:    2145906,          // Number
  surface_km2:   105,              // Number|null
  lat:           48.8566,          // Number|null
  lon:           2.3522,           // Number|null

  // Champs enrichis — optionnels (voir 1.2)
  immo?:     { prix_m2_median, loyer_median, nb_transactions, annee_dvf },
  fibre_pct?: Number,
  securite?:  { taux_pour_mille, annee },
  air?:       { iqa_moyen, label, annee },
  socio?:     { revenu_median, taux_chomage, taux_pauvrete }
}
```

### 2.2 Objet Résultat de Recherche (Worker → Main thread)

Format retourné par le Web Worker dans `RESULTS.payload.results[]` :

```javascript
{
  nom:        "Paris",    // String
  code_insee: "75056",   // String
  cp:         "75001",   // String
  pop:        2145906    // Number
}
```

Ces objets correspondent aux éléments de `data/index.json` reformatés en objets nommés.

### 2.3 Objet État Application (`state`) — index.html

Variable globale `state` dans `index.html` gérant l'état de l'application SPA :

```javascript
const state = {
  workerReady:  false,         // Boolean — worker initialisé et prêt
  workerSize:   0,             // Number — nombre de communes indexées
  workerCbs:    {},            // Object<channelId, resolver> — callbacks en attente
  cmpMode:      false,         // Boolean — mode comparaison actif
  cmpLeft:      null,          // CommuneObject|null — commune gauche (comparaison)
  cmpRight:     null,          // CommuneObject|null — commune droite (comparaison)
  cmpSearchFor: null,          // 'left'|'right'|null — côté en cours de recherche
}
```

**Note :** L'URL est la source de vérité principale (SPA routing). `state` contient uniquement les données d'UI transitoires non représentables dans l'URL.

---

## 3. Structures Intermédiaires Python (Pipeline ETL)

### 3.1 Objet Commune Python

Dictionnaire construit dans `fetch_all_communes()` puis enrichi par chaque étape :

```python
{
    # Champs de base (API Géo Communes)
    "code_insee":    "75056",         # str, zfill(5) via insee_str()
    "nom":           "Paris",
    "codes_postaux": ["75001", ...],  # list[str]
    "cp":            "75001",         # str (premier code)
    "code_dep":      "75",            # str
    "population":    2145906,         # int, peut être 0
    "surface_km2":   105,             # int|None (surface_ha / 100)
    "lat":           48.8566,         # float|None
    "lon":           2.3522,          # float|None

    # Champs enrichis ajoutés séquentiellement
    "immo":     { ... },              # étape fetch_dvf_stats()
    "fibre_pct": 98.5,               # étape fetch_arcep_fibre()
    "securite": { ... },              # étape fetch_crime_data()
    "air":      { ... },              # étape fetch_air_quality()
    "socio":    { ... },              # étape fetch_filosofi() + fetch_chomage()
}
```

### 3.2 Tables de Lookup Python (dictionnaires en mémoire)

Ces structures sont temporaires, construites en RAM pendant le run ETL puis discardées :

```python
# DVF CEREMA — dict { code_insee → immo_dict }
dvf_stats: dict[str, dict] = {
    "75056": {
        "prix_m2_median":  9850.0,
        "nb_transactions": 12450,
        "annee_dvf":       2023
    }
}

# ARCEP — dict { code_insee → fibre_pct }
arcep_data: dict[str, float] = {
    "75056": 98.5
}

# SSMSI Criminalité — dict { code_insee → { faits_total, pop, annee } }
crime_data: dict[str, dict] = {
    "75056": {
        "taux_pour_mille": 28.4,
        "annee": 2022
    }
}

# ATMO Qualité de l'air — dict { code_insee → { iqa_moyen, label, annee } }
air_data: dict[str, dict] = {
    "75056": {
        "iqa_moyen": 2.1,
        "label": "Bon",
        "annee": 2023
    }
}

# Filosofi — dict { code_insee → { revenu_median, taux_chomage, taux_pauvrete } }
socio_data: dict[str, dict] = {
    "75056": {
        "revenu_median":  24500,
        "taux_chomage":   8.2,
        "taux_pauvrete":  13500
    }
}
```

---

## 4. Invariants et Règles de Validation

| Invariant | Règle | Conséquence si violée |
|---|---|---|
| `code_insee` toujours String | `str(code).zfill(5)` en Python, `String(code).padStart(5,'0')` en JS | Lookups dict ratés, fichiers JSON mal nommés |
| Prix carburant en euros décimaux | `raw > 100` → `raw / 1000` | Affichage de prix × 1000 erronés |
| Champs optionnels jamais accédés sans vérification | `commune.immo?.prix_m2_median` | TypeError en production |
| `lat`/`lon` API Géo = `[lon, lat]` | `coords[1]` = lat, `coords[0]` = lon | Géolocalisation inversée |
| Coordonnées carburants API source = 1/100000 degré | Diviser par 100000 | Stations placées hors de France |
| Code Corse `"2A"` / `"2B"` | Jamais converti en Number | `2A` devient `NaN`, `2B` aussi |
| `population` peut être `0` | Ne pas utiliser `pop || default` | Communes avec 0 hab. traitées comme nulles |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
