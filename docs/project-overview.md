# VivreÀ — Vue d'Ensemble du Projet

**Date :** 2026-02-21

---

## Résumé Exécutif

**VivreÀ** est un outil web d'aide à la décision résidentielle qui agrège des données publiques françaises (immobilier, fibre optique, carburants, sécurité, qualité de l'air, revenus, chômage) pour permettre aux citoyens de comparer les communes avant un déménagement.

Le projet est une **SPA (Single Page Application) statique** couplée à un **pipeline ETL Python**, déployée sur Vercel sans aucun runtime serveur. Les données sont pré-calculées et servies comme assets JSON depuis un CDN.

---

## Fiche Technique

| Propriété | Valeur |
|---|---|
| **Nom** | VivreÀ |
| **URL production** | https://vivrea.vox-novalys.fr |
| **Type** | JAMstack — SPA statique + Python ETL |
| **Architecture** | Monolithe — 1 partie (web+data hybrid) |
| **Version dataset** | 2.2 |
| **Communes couvertes** | 34 875 (France entière + DOM-TOM) |
| **Déploiement** | Vercel CDN + GitHub Actions |
| **Dernière mise à jour** | 2026-02-21 |

---

## Stack Technologique

### Frontend

| Technologie | Version | Rôle |
|---|---|---|
| HTML5 | — | Structure SPA |
| JavaScript (ES2022+) | — | Logique applicative (Vanilla JS, pas de framework) |
| Tailwind CSS | v3 (CDN) | Styles utilitaires |
| Web Worker API | — | Recherche en arrière-plan (34k communes) |
| Fetch API | — | Chargement des données JSON |

### Pipeline de Données

| Technologie | Version | Rôle |
|---|---|---|
| Python | 3.12+ | Langage ETL |
| requests | ≥2.31.0 | Appels HTTP avec retry |
| stdlib (csv, gzip, zipfile, xml, json) | — | Traitement des données sources |

### Infrastructure

| Service | Rôle |
|---|---|
| GitHub | Source control + déclenche CI/CD |
| GitHub Actions | Exécution du pipeline ETL |
| Vercel | CDN + hébergement statique + rewrites SPA |
| Git | Stockage des données JSON (data/ commité) |

---

## Sources de Données

| Donnée | Source | Fréquence |
|---|---|---|
| Communes (limites, population) | API Géo — geo.api.gouv.fr | À la demande (CI/CD) |
| Prix immobilier | DVF CEREMA — apidf-preprod.cerema.fr | Annuelle |
| Fibre FTTH | ARCEP — data.gouv.fr (Shapefile) | À la demande (CI/CD) |
| Prix carburants | donnees.roulez-eco.fr (XML) | Quotidienne |
| Criminalité | SSMSI — data.gouv.fr (CSV GZ) | Annuelle |
| Qualité de l'air | ATMO France (WFS CSV) | Annuelle |
| Revenus / Pauvreté | INSEE Filosofi — data.gouv.fr | Annuelle |
| Chômage | INSEE BPE — data.gouv.fr | Annuelle |

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Recherche de commune** | Autocomplétion fuzzy sur 34 875 communes (Worker) |
| **Fiche commune** | Prix immobilier, fibre, sécurité, air, revenus, carburants |
| **Mode comparaison** | Deux fiches côte à côte (`?v=X&c=Y`) |
| **Explorateur département** | Tableau filtrable et triable par département |
| **Liens externes** | LeBonCoin et SeLoger pré-filtrés par commune |
| **Liens Amazon** | Déménagement contextuel |
| **Stations carburant** | Prix en temps réel par ville/code postal |

---

## Structure du Dépôt

```
vivrea-project/
├── index.html          # SPA principale (point d'entrée)
├── explorer.html       # Explorateur département (page autonome)
├── fuel.js             # Module carburants (IIFE)
├── search.worker.js    # Web Worker recherche
├── update.py           # Pipeline ETL Python
├── vercel.json         # Config Vercel
├── data/               # Données JSON générées (committées)
│   ├── index.json      # Index 34 875 communes
│   ├── carburants.json # Prix carburants
│   ├── meta.json       # Métadonnées
│   └── details/        # 101 fichiers par département
├── .github/workflows/  # CI/CD GitHub Actions
└── docs/               # Documentation (ce dossier)
```

→ Voir `docs/source-tree-analysis.md` pour l'arborescence complète annotée.

---

## Documentation Disponible

| Document | Description |
|---|---|
| [architecture.md](architecture.md) | Architecture, ADRs, patterns, anti-patterns, dette technique |
| [api-contracts.md](api-contracts.md) | Contrats API internes, externes et protocole Web Worker |
| [data-models-main.md](data-models-main.md) | Schémas JSON et structures de données |
| [component-inventory-main.md](component-inventory-main.md) | Inventaire composants, vues SPA et gestion d'état |
| [source-tree-analysis.md](source-tree-analysis.md) | Arborescence annotée avec points d'entrée et d'intégration |
| [development-guide.md](development-guide.md) | Setup, workflow de modification, règles critiques, débogage |
| [deployment-guide.md](deployment-guide.md) | CI/CD, Vercel, stratégie données, rollback |
| [index.md](index.md) | Index complet de toute la documentation |

---

## Principes Architecturaux Clés

1. **Zéro runtime serveur** — tout est statique, la logique est dans le navigateur
2. **URL = source de vérité** — état partageable via URL, pas de store
3. **Dégradation gracieuse** — chaque section affiche `—` si sa donnée est absente
4. **code_insee toujours String** — invariant critique, jamais converti en Number
5. **Pas de dépendances npm** — Tailwind CDN, Vanilla JS, stdlib Python uniquement

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
