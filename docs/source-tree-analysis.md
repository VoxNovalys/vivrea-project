# VivreÀ — Analyse de l'Arborescence Source

**Date :** 2026-02-21

---

## Arborescence Complète Annotée

```
vivrea-project/                         # Racine du projet — servi par Vercel
│
├── 📄 index.html                       # ★ POINT D'ENTRÉE PRINCIPAL — SPA complète
│                                       #   Router, toutes vues, state, worker bootstrap
│
├── 📄 explorer.html                    # ★ PAGE AUTONOME — Explorateur département
│                                       #   Aucune dépendance à index.html
│
├── 📄 fuel.js                          # Module carburants (IIFE → window.FuelSearch)
│                                       #   Importé par index.html via <script src>
│
├── 📄 search.worker.js                 # Web Worker — indexation et recherche fuzzy
│                                       #   Chargé par new Worker('./search.worker.js')
│
├── 📄 404.html                         # Page d'erreur 404 — SPA fallback Vercel
│
├── 📄 update.py                        # ★ PIPELINE ETL Python — collecte toutes les données
│                                       #   Exécuté par GitHub Actions → génère data/
│
├── 📄 requirements.txt                 # Dépendances Python : requests>=2.31.0 uniquement
│
├── 📄 vercel.json                      # Config Vercel : rewrites SPA + Cache-Control headers
│
├── 📄 package-lock.json                # Lockfile npm (vide — 0 packages npm utilisés)
│
├── 📄 .gitignore                       # Ignores Python/Node/OS ; data/ EST commité
│
├── data/                               # ★ DONNÉES STATIQUES — générées par update.py
│   │                                   #   Servis comme assets statiques par Vercel CDN
│   │
│   ├── 📄 index.json                   # Index global : 34 875 communes [[nom,insee,cp,pop]]
│   │                                   #   Taille : < 1.5 MB. Chargé au démarrage → Worker
│   │
│   ├── 📄 carburants.json              # ~11 000 stations carburant avec prix (maj quotidienne)
│   │                                   #   Chargé par FuelSearch.load()
│   │
│   ├── 📄 meta.json                    # Métadonnées : version, date update, nb_communes
│   │
│   └── details/                        # Fichiers par département (101 fichiers)
│       ├── 📄 01.json                  # Ain — communes enrichies (immo, fibre, sécurité, air, socio)
│       ├── 📄 02.json                  # Aisne
│       ├── ...                         # (95 départements métropolitains)
│       ├── 📄 2A.json                  # Corse-du-Sud — code String (jamais converti en Number)
│       ├── 📄 2B.json                  # Haute-Corse
│       ├── 📄 971.json                 # Guadeloupe
│       ├── 📄 972.json                 # Martinique
│       ├── 📄 973.json                 # Guyane
│       ├── 📄 974.json                 # La Réunion
│       └── 📄 976.json                 # Mayotte
│                                       #   Taille : 100 Ko à 2 Mo / fichier
│                                       #   Chargé à la demande par fetchDep(dep)
│
├── .github/
│   └── workflows/
│       └── 📄 main.yml                 # ★ CI/CD GitHub Actions — pipeline ETL automatique
│                                       #   Déclenché : push main (hors data/) + dispatch manuel
│                                       #   Exécute update.py → commit data/ → push
│
├── docs/                               # Documentation BMAD (générée — ne pas éditer manuellement)
│   ├── 📄 index.md                     # Index de toute la documentation (à générer)
│   ├── 📄 project-overview.md          # Vue d'ensemble du projet (à générer)
│   ├── 📄 architecture.md              # Architecture, ADRs, patterns, anti-patterns
│   ├── 📄 api-contracts.md             # Contrats API internes et externes
│   ├── 📄 data-models-main.md          # Schémas JSON et structures de données
│   ├── 📄 component-inventory-main.md  # Inventaire composants et gestion d'état
│   ├── 📄 source-tree-analysis.md      # Ce fichier
│   └── 📄 project-scan-report.json     # État du workflow document-project
│
├── _bmad-output/                       # Sorties workflow BMAD (planification, specs)
│   └── 📄 project-context.md           # Contexte projet généré par generate-project-context
│
└── _bmad/                              # Outillage BMAD — ne pas modifier
    └── bmm/
        ├── config.yaml                 # Config BMAD : user=Sylvain, lang=French
        └── workflows/                  # Définitions des workflows BMAD
```

---

## Dossiers Critiques

| Dossier / Fichier | Criticité | Rôle |
|---|---|---|
| `index.html` | ★★★ CRITIQUE | SPA principale — tout le frontend est ici |
| `update.py` | ★★★ CRITIQUE | Pipeline ETL — source de toutes les données |
| `data/` | ★★★ CRITIQUE | Données servies — modifiées uniquement par CI/CD |
| `data/details/` | ★★★ CRITIQUE | 101 fichiers par département — cœur du dataset |
| `fuel.js` | ★★ IMPORTANT | Module carburant — peut être mis à jour indépendamment |
| `search.worker.js` | ★★ IMPORTANT | Performance search — ne pas bloquer main thread |
| `explorer.html` | ★★ IMPORTANT | Page autonome — duplication intentionnelle |
| `.github/workflows/main.yml` | ★★ IMPORTANT | Automatisation — toute modification impacte les données |
| `vercel.json` | ★ SENSIBLE | Rewrites SPA — une erreur rend le site non-fonctionnel |

---

## Points d'Entrée

| Point d'entrée | Type | Déclenché par |
|---|---|---|
| `index.html` → `boot()` | SPA main | Navigation navigateur, rechargement |
| `explorer.html` → `init()` | Page autonome | Navigation directe (`/explorer.html?dep=75`) |
| `update.py` → `main()` | ETL Python | GitHub Actions CI/CD ou exécution manuelle |
| `search.worker.js` → `onmessage(INIT)` | Worker | `new Worker()` + `postMessage({type:'INIT'})` dans index.html |

---

## Points d'Intégration

| De | Vers | Mécanisme |
|---|---|---|
| `index.html` | `fuel.js` | `<script src="fuel.js">` → `window.FuelSearch` |
| `index.html` | `search.worker.js` | `new Worker('./search.worker.js')` |
| `index.html` | `data/index.json` | `fetch('/data/index.json')` au démarrage |
| `index.html` | `data/details/{dep}.json` | `fetchDep()` à la demande |
| `index.html` | `geo.api.gouv.fr` | Fallback si commune absente du dep.json |
| `index.html` | `apidf-preprod.cerema.fr` | Fallback DVF si `commune.immo` absent |
| `fuel.js` | `data/carburants.json` | `fetch('/data/carburants.json')` |
| `explorer.html` | `data/details/{dep}.json` | `fetch()` direct à l'initialisation |
| `update.py` | `data/*.json` | Écriture fichiers → commit CI/CD |
| `main.yml` | `update.py` | `python update.py` dans job GitHub Actions |

---

## Fichiers Absents (par conception)

| Fichier attendu | Raison de l'absence |
|---|---|
| `package.json` | Aucun outillage npm — Tailwind via CDN uniquement |
| `webpack.config.js` / `vite.config.js` | Pas de bundler — HTML statique servi directement |
| `*.test.js` | Aucun test automatisé frontend actuellement |
| `Dockerfile` | Pas de container — déploiement Vercel JAMstack |
| `README.md` | Pas de README racine (documentation dans `docs/`) |
| `CHANGELOG.md` | Pas de changelog formel |
| `.env` / `.env.example` | Aucune variable d'environnement nécessaire |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
