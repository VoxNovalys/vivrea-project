---
project_name: 'VivreÀ'
user_name: 'Sylvain'
date: '2026-02-21'
sections_completed:
  - technology_stack
  - language_rules
  - framework_rules
  - api_rules
  - quality_rules
  - workflow_rules
  - anti_patterns
status: 'complete'
rule_count: 52
optimized_for_llm: true
---

# Project Context for AI Agents

_Ce fichier contient les règles critiques et les patterns que les agents IA doivent respecter lors de l'implémentation de code dans ce projet. Focalisé sur les détails non-évidents que les agents pourraient manquer._

---

## Technology Stack & Versions

### État actuel (à mettre à jour si la stack évolue)
- **Frontend** : Vanilla HTML/CSS/JavaScript — aucun framework JS
- **CSS** : Tailwind CSS v3 via CDN (`cdn.tailwindcss.com`) — PAS de build, PAS de PostCSS, PAS de `@apply`
  - Config inline dans `<script>` : tokens custom `surface:#111111`, `card:#1a1a1a`, `border:#2a2a2a`
  - Seules les classes utilitaires standard + ces tokens sont disponibles — pas de classes arbitraires `[]`
- **Police** : Inter via Google Fonts CDN
- **Python** : Python 3.9+ — stdlib uniquement (zipfile, csv, gzip, struct, xml.etree, io)
  - Seule dépendance externe : `requests>=2.31.0`
  - NE PAS introduire pandas, shapefile, dbfread ou toute librairie lourde
- **Déploiement** : Vercel — site statique, rewrites SPA dans `vercel.json`
- **Dark mode** : Tailwind `darkMode: 'class'` — `<html class="dark">` hardcodé, pas de toggle
- **Cible navigateurs** : Firefox, Edge, Chrome (evergreen modernes) — pas de polyfills nécessaires

### Principes directeurs (stables dans le temps)
- **Légèreté avant tout** : aucune dépendance JS côté client non justifiée
- **Chargement rapide** : `data/index.json` doit rester < 1,5 Mo ; données détaillées paginées par département
- **Open Data fiables** : toujours privilégier les sources gouvernementales officielles (geo.api.gouv.fr, data.gouv.fr, insee.fr, arcep, atmo-france.org)
- **Sécurité XSS** : toute donnée externe insérée dans le DOM passe par `esc()`
- **Navigateurs cibles** : Firefox, Edge, Chrome evergreen — APIs utilisées : Web Worker, fetch, History API, navigator.clipboard, URL.createObjectURL

## Critical Implementation Rules

### JavaScript — Règles critiques

- **code_insee TOUJOURS String 5 chars** : `String(code).padStart(5, '0')`.
  Jamais un Number — les comparaisons strictes et lookups JSON échoueraient.

- **Départements outre-mer** : code dep sur 3 chars si code_insee commence par "97".
  `dep = code.startsWith('97') ? code.slice(0,3) : code.slice(0,2)`
  Cette logique est présente dans index.html ET explorer.html — les garder synchronisées.

- **XSS** : toute valeur externe ou issue des données JSON injectée dans le DOM
  doit passer par `esc()`. fuel.js a sa propre copie de `esc()` — cohérence obligatoire.

- **fetchJSON vs fetchExternal** :
  - `fetchJSON(url)` → données locales `/data/...` avec `cache: 'no-store'`
  - `fetchExternal(url)` → APIs tierces sans headers custom (évite preflight CORS)

- **Cache depCache** : cache mémoire de session, volontairement non-persistant.
  Ne pas ajouter de logique d'invalidation — un rechargement de page suffit.

- **FuelSearch** : module IIFE dans fuel.js, chargé uniquement dans index.html.
  Son cache interne (_promise, _flat) est indépendant du depCache et du Web Worker.
  Appel conditionnel : `if (typeof FuelSearch !== 'undefined') FuelSearch.init(...)`.

- **Web Worker** : le code inline WORKER_SRC dans index.html est le fallback de
  search.worker.js — toujours garder les deux synchronisés si l'un est modifié.

- **SPA vs page directe** :
  - index.html = SPA → navigation via `navigate(path, event)`, jamais de `<a href>` direct
  - explorer.html = page autonome → liens `<a href>` normaux, pas de `navigate()`

### Python — Règles critiques

- **insee_str(code)** : toujours utiliser cette fonction (`str(code).strip().zfill(5)`).

- **safe_get()** : tous les appels HTTP passent par cette fonction (retry + backoff).
  Jamais `SESSION.get()` directement.

- **write_json(path, data, compact)** :
  - `compact=True` → index et détails (optimisation taille)
  - `compact=False` → meta.json (lisibilité)

- **Pipeline de données** : les étapes 1-7 sont tolérantes aux pannes (retournent `{}`
  en cas d'échec). L'étape 8 (build_index_and_details) dépend de toutes les autres.
  Évolution prévue : arguments CLI pour relancer une étape isolément.

- **Détection format CSV** : auto-détecter le séparateur avec
  `";" if text.count(";") > text.count(",") else ","` — les fichiers INSEE varient.

- **Décompression GZ** : détecter avec `raw[:2] == b"\x1f\x8b"` avant décompression.

### Architecture SPA (index.html)

- **Router** : `getRoute(path)` → `route(path)` → `render*()`.
  Ajouter une vue = 1) cas dans `getRoute()`, 2) fonction `render*()`,
  3) rewrite dans `vercel.json` si c'est une route SPA.

- **vercel.json — rewrites** : préférer le catch-all plutôt que les routes explicites :
  `{ "source": "/((?!data|explorer\\.html|fuel\\.js|search\\.worker\\.js).*)",
     "destination": "/index.html" }`
  Les fichiers statiques Vercel sont servis avant les rewrites — aucun risque de collision.

- **404.html — double rôle** :
  - Héritage GitHub Pages : redirige vers `/` en stockant le chemin dans `sessionStorage`
  - `index.html` le récupère au boot : `sessionStorage.getItem('spa_redirect')`
  - Sur Vercel, ce mécanisme est le filet de sécurité pour les routes hors rewrites
  - Ne pas supprimer ce fichier — le garder synchronisé avec le design du site

- **SEO** : chaque vue doit appeler `setSEO(title, desc, canonical)` — obligatoire.

- **Templates vs fonctions** :
  - Vues statiques (home, apropos, mentions) → `<template id="tpl-*">` + `cloneNode(true)`
  - Vues dynamiques (ville, compare) → `buildVilleHTML()` / `buildCompactHTML()`

- **Mode comparaison** : `isComparing` remis à `false` à chaque `route()`.
  URL partageable : `/comparer/{codeA}/{codeB}`.

- **AdSense** : `(adsbygoogle||[]).push({})` toujours dans un `try/catch`.

### Structure des données JSON

- **index.json** : tableau de tableaux `[nom, code_insee, cp, population]`.
  Accès positionnel : `c[0]`=nom, `c[1]`=code_insee, `c[2]`=cp, `c[3]`=population.
  Taille max : 1,5 Mo — vérifiée automatiquement dans `update.py`.

- **details/{dep}.json** : tableau d'objets par département.
  Champs garantis : `code_insee`(String), `nom`, `codes_postaux`, `code_dep`, `population`.
  Champs optionnels (absents si données indisponibles) : `immo`, `fibre_pct`,
  `securite`, `air`, `socio`. Règle : champ absent = afficher `—`, jamais d'erreur.

- **carburants.json** : `{ updated_at, nb_stations, stations[] }`.
  Prix en euros décimaux (ex: 1.732). Champ `maj` par carburant (timestamp ISO).

### Duplications connues à maintenir synchronisées

Jusqu'à extraction dans un futur `common.js`, ces fonctions sont dupliquées :
- `getDep(code_insee)` : dans index.html ET explorer.html (logique identique)
- `esc(s)` : dans index.html, fuel.js ET explorer.html
- Config Tailwind et styles CSS de base : dans index.html ET explorer.html
Règle : toute modification de l'une doit être répercutée dans les autres.

### Couleurs sémantiques (convention obligatoire)

- Fibre FTTH : ≥80% → emerald · ≥40% → amber · <40% → rose
- Sécurité (taux‰) : ≤15 → emerald · ≤40 → amber · >40 → rose
- Qualité de l'air (EAQI 1-6) : 1 → emerald · 2 → lime · 3 → amber · 4 → orange · 5-6 → rose
- Donnée absente : `text-gray-500` + `bg-card` + valeur `—`

### APIs externes — Règles critiques (état 2026)

- **DVF CEREMA (immobilier)** :
  - URL : `https://apidf-preprod.cerema.fr/indicateurs/dv3f/prix/annuel/`
  - Params : `echelle=communes`, `annee=YYYY`, `page_size=500`
  - Champ commune : `item["code"]` · Prix : `pxm2_median_cod111` · Nb : `nbtrans_cod111`
  - Sonde d'année : `current_year-2` → `current_year-3` → `current_year-1`
  - ⚠️ Ancienne URL `/indicateurs/dv3f/communes` → 404 depuis 2025
  - Fallback client-side dans `renderVille()` : CORS permissif, fonctionnel

- **ARCEP Fibre (data.gouv.fr)** :
  - Dataset : `le-marche-du-haut-et-tres-haut-debit-fixe-deploiements`
  - Format : ZIP → DBF parsé avec `_read_dbf()` (stdlib, pas de lib externe)
  - Colonnes : `INSEE_COM`, `ftth`, `Locaux` · Calcul : `min(ftth/Locaux*100, 100.0)`
  - ⚠️ `data.arcep.fr` (CKAN) hors ligne depuis 2025
  - ⚠️ Fallback client-side CKAN dans `renderVille()` est mort — à remplacer

- **Carburants (roulez-eco.fr)** :
  - Format : ZIP ou XML (détecter `content[:2] == b"PK"`)
  - Coordonnées brutes divisées par 100 000 · `normalize_fuel_price()` obligatoire
  - Recherche basée sur les coordonnées de **la commune affichée** (lat/lon du JSON)
  - Jamais de géolocalisation navigateur — rayon 10 km autour de la commune
  - Fallback si lat/lon absents : filtre par code postal puis département

- **Criminalité SSMSI** : CSV.GZ · Uniquement communes ≥ 2 000 hab
- **Qualité de l'air ATMO** : WFS CSV · Sonde année `current_year-1` → `-2` → `-3`
- **INSEE Filosofi** : ZIP CSV · Colonnes `CODGEO`, `MED21`, `TP6021`
- **INSEE RP 2021 (chômage)** : ZIP CSV · Colonnes `CODGEO`, `CHOM1564_P`, `ACT1564_P`

### Protocole de diagnostic API en panne

Si une donnée disparaît après une mise à jour :
1. Vérifier `data/meta.json` → `last_update` et `sources`
2. Tester l'URL de l'API manuellement (retourne-t-elle du JSON/CSV valide ?)
3. Chercher un message de rupture dans les logs GitHub Actions
4. Vérifier si l'URL ou le format a changé sur data.gouv.fr / insee.fr
5. Mettre à jour `update.py` + les éventuels fallbacks client dans `index.html`

### GitHub Actions & Déploiement

- **Fichier** : `.github/workflows/main.yml`
- **Python** : 3.12 (utiliser cette version pour les tests locaux)
- **Déclencheurs actuels** : push sur `main` (hors `data/`) + `workflow_dispatch` manuel
- **⚠️ Pas de mise à jour hebdomadaire automatique** : aucun `schedule: cron` configuré.
  À ajouter : `schedule: - cron: '0 3 * * 1'` (lundi 3h UTC)
- **Double déploiement** : GitHub Pages ET Vercel — les deux sont actifs
- **Commit data** : le bot commit `data/` automatiquement après chaque run réussi
- **Règle** : ne jamais committer manuellement dans `data/` — laisser le CI le faire

### Conventions de code

- **Nommage JS** : camelCase fonctions/variables · préfixe `_` pour privé de module
  (`_promise`, `_flat`, `_seq`). Pas de variables globales hors `state{}` et `depCache`.
- **Nommage Python** : snake_case · UPPER_SNAKE_CASE pour constantes.
- **Nombres affichés** : toujours `toLocaleString('fr')` — jamais `.toString()` brut.
- **console.log** : les logs existants sont diagnostics intentionnels (DVF, ARCEP, Worker).
  Ne pas en laisser pour du débogage temporaire.

### Gestion de l'état global JS

- Tout nouvel état applicatif → ajouter dans l'objet `state` existant :
  `state.workerReady`, `state.workerSize`, `state.currentCommune`
- Variables de module privées → préfixe `_` dans leur scope (`_mainDebounce`, `_ddIdx`)
- `depCache` et `workerCbs` sont des objets de cache/callbacks — ne pas les mélanger
  avec l'état applicatif
- `isComparing` est une exception historique — les futures features doivent utiliser `state`
- Éviter les fermetures (closures) qui capturent des références DOM obsolètes après
  navigation SPA — nettoyer les event listeners dans `route()` si nécessaire

### URLs immobilières — Feature en cours

Comportement voulu (à compléter) :
- Bouton **Achat** → LeBonCoin vente + SeLoger achat, pré-filtrés sur la commune, rayon 30 km
- Bouton **Location** → LeBonCoin location + SeLoger locations, même rayon

Slug de commune : `nom.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')`
Ce pattern gère tous les noms français y compris DOM-TOM et Corse.

Implémentation actuelle (partielle) dans `buildVilleHTML()` :
- LeBonCoin : `?category=9&locations={slug}` — rayon non encore pré-réglé
- SeLoger : `/immobilier/achat/immo-{slug}-{code_dep}/` — pas de rayon explicite
- ⚠️ Le rayon 30 km n'est pas encore passé en paramètre URL — feature à compléter

### Anti-patterns à éviter absolument

- **Ne JAMAIS traiter code_insee comme un Number** — toujours String 5 chars.
- **Ne JAMAIS appeler SESSION.get() directement** en Python — toujours `safe_get()`.
- **Ne JAMAIS injecter du HTML sans esc()** — même données JSON locales.
- **Ne JAMAIS ajouter une dépendance Python lourde** — stdlib + requests uniquement.
- **Ne JAMAIS modifier data/ manuellement** — géré par le CI uniquement.
- **Ne JAMAIS utiliser navigate() dans explorer.html** — page autonome.
- **Ne JAMAIS omettre try/catch autour de AdSense** push.
- **Ne JAMAIS ajouter de variable globale loose** — utiliser `state{}` ou préfixe `_`.

### Gestion des erreurs

- **JS** : `fetchJSON`/`fetchExternal` retournent `null` silencieusement.
  Toujours vérifier `if (!data)` avant usage.
- **Python** : chaque étape capture `except Exception` et retourne `{}`.
  Une étape qui échoue ne crashe pas le pipeline.
- **Timeouts Python** : `safe_get()` = 30s par défaut · gros downloads = 60-300s explicite.

### Performances & UX

- **Skeleton** : afficher `.skeleton` pendant tout chargement async — jamais de spinner bloquant.
- **Debounce** : 120ms recherche principale · 150ms comparaison · 180ms explorer.html.
- **Animations** : `.fade-up` après chargement (0.3-0.35s). Pas d'animation au-dessus
  de la ligne de flottaison.
- **index.json** : chargé une seule fois au démarrage (Web Worker) — ne pas re-fetcher
  lors d'une navigation SPA.

### Accessibilité & SEO

- `setSEO(title, desc, canonical)` obligatoire dans chaque vue — gère title, meta,
  og:title, og:description, og:url, canonical.
- SVG inline sans aria-label : dette technique connue — ajouter `aria-hidden="true"`
  sur les SVG décoratifs lors de futures modifications.
- Pas de sitemap ni structured data (JSON-LD) actuellement — évolutions futures.

### Stratégie de tests (à implémenter)

Aucun test automatisé actuellement. Stratégie recommandée pour les futurs agents :
- **Python (`update.py`)** : pytest — tester `normalize_fuel_price()`, `insee_str()`,
  `_read_dbf()`, détection de séparateur CSV, normalisation des coordonnées GPS.
- **JS/SPA** : Playwright — tester la navigation SPA, la recherche de communes,
  le mode comparaison, l'affichage des fiches ville.
- **Prérequis** : aucun build system nécessaire pour pytest. Playwright nécessite Node.js.

---

## Usage Guidelines

**Pour les agents IA :**

- Lire ce fichier en entier avant d'implémenter du code sur ce projet
- Respecter TOUTES les règles — notamment code_insee String, esc(), safe_get()
- En cas de doute, choisir l'option la plus restrictive
- Signaler toute règle devenue obsolète ou tout nouveau pattern découvert
- Les sections marquées ⚠️ indiquent des points de fragilité connus à traiter en priorité

**Pour Sylvain :**

- Mettre à jour ce fichier quand la stack ou les patterns évoluent
- Réviser trimestriellement pour retirer les règles devenues évidentes
- Les "Features en cours" documentées ici sont la feuille de route prioritaire :
  - Rayon 30 km sur les URLs LeBonCoin / SeLoger
  - Remplacement du fallback ARCEP CKAN (hors ligne)
  - Ajout du `schedule: cron` GitHub Actions pour la mise à jour hebdomadaire automatique
  - Extraction d'un `common.js` partagé entre index.html et explorer.html

**Fichiers clés du projet :**

| Fichier | Rôle |
|---------|------|
| `index.html` | SPA principale (router, vues, worker, carburants) |
| `explorer.html` | Page autonome liste/filtre communes |
| `fuel.js` | Module FuelSearch (chargé dans index.html uniquement) |
| `search.worker.js` | Web Worker recherche off-thread |
| `update.py` | Pipeline Python mise à jour données (8 étapes) |
| `data/index.json` | Index léger communes (< 1,5 Mo) |
| `data/details/{dep}.json` | Fiches enrichies par département |
| `data/carburants.json` | Prix carburants en temps réel |
| `data/meta.json` | Métadonnées dernière mise à jour |
| `.github/workflows/main.yml` | CI/CD GitHub Actions (Python 3.12) |
| `vercel.json` | Rewrites SPA + headers cache |
| `404.html` | Fallback SPA (héritage GitHub Pages) |

_Dernière mise à jour : 2026-02-21_
