# VivreÀ — Index de la Documentation

**Date de génération :** 2026-02-21
**Généré par :** Workflow BMAD `document-project` v1.2.0

---

## Vue d'ensemble

VivreÀ est un outil d'aide à la décision résidentielle — SPA statique JAMstack + pipeline ETL Python. Couverture : 34 875 communes françaises avec données immobilières, fibre, carburants, sécurité, qualité de l'air et socio-économiques.

---

## Documents de Référence

### Point d'Entrée

| Document | Description | Audience |
|---|---|---|
| [project-overview.md](project-overview.md) | Vue d'ensemble : stack, fonctionnalités, sources, structure | Tous |

---

### Architecture & Conception

| Document | Description | Audience |
|---|---|---|
| [architecture.md](architecture.md) | Architecture complète : patterns, ADRs (6), anti-patterns, dette technique, analyse first-principles | Développeurs, Architectes |
| [source-tree-analysis.md](source-tree-analysis.md) | Arborescence annotée, points d'entrée, points d'intégration, fichiers absents | Développeurs |

---

### Données & Interfaces

| Document | Description | Audience |
|---|---|---|
| [api-contracts.md](api-contracts.md) | Contrats JSON statiques, APIs externes (navigateur + Python), protocole Web Worker, gestion erreurs | Développeurs |
| [data-models-main.md](data-models-main.md) | Schémas JSON (index, details, carburants, meta), objets JS internes, structures Python, invariants | Développeurs |

---

### Composants & État

| Document | Description | Audience |
|---|---|---|
| [component-inventory-main.md](component-inventory-main.md) | Vues SPA, modules JS (fuel.js, search.worker.js), gestion d'état, design system | Développeurs Frontend |

---

### Guides Opérationnels

| Document | Description | Audience |
|---|---|---|
| [development-guide.md](development-guide.md) | Prérequis, setup local, règles critiques, tests manuels, débogage | Développeurs |
| [deployment-guide.md](deployment-guide.md) | CI/CD GitHub Actions, Vercel config, stratégie données committées, rollback | DevOps, Développeurs |

---

### Métadonnées Workflow

| Document | Description |
|---|---|
| [project-scan-report.json](project-scan-report.json) | État du workflow document-project (étapes complétées, outputs) |

---

## Navigation Rapide par Thème

### "Comment fonctionne la recherche ?"
→ [component-inventory-main.md §4.2](component-inventory-main.md) — Web Worker
→ [api-contracts.md §3](api-contracts.md) — Protocole Worker (INIT/SEARCH/RESULTS)

### "Quels sont les champs d'une commune ?"
→ [data-models-main.md §1.2](data-models-main.md) — Schéma details/{dep}.json
→ [api-contracts.md §1.2](api-contracts.md) — Format de réponse avec exemples

### "Comment les prix carburant sont-ils normalisés ?"
→ [api-contracts.md §1.3](api-contracts.md) — Règle prix > 100 → ÷ 1000
→ [data-models-main.md §1.3](data-models-main.md) — Schéma carburants.json

### "Comment ajouter une nouvelle source de données ?"
→ [deployment-guide.md §3](deployment-guide.md) — Étapes du pipeline ETL
→ [architecture.md](architecture.md) — ADRs et contraintes architecturales
→ [api-contracts.md §4](api-contracts.md) — Pattern APIs Python

### "Pourquoi code_insee est toujours String ?"
→ [data-models-main.md §4](data-models-main.md) — Invariants et règles de validation
→ [architecture.md](architecture.md) — Section "Règles d'implémentation critiques"

### "Comment déployer une mise à jour ?"
→ [deployment-guide.md](deployment-guide.md) — Guide complet CI/CD

### "Comment développer en local ?"
→ [development-guide.md](development-guide.md) — Guide complet

### "Quelles sont les décisions d'architecture et pourquoi ?"
→ [architecture.md](architecture.md) — Section ADRs (ADR-01 à ADR-06)

### "Quels sont les risques et la dette technique ?"
→ [architecture.md](architecture.md) — Sections "Anti-patterns", "Failure Mode Analysis", "Dette technique"

---

## Statut de la Documentation

| Document | Statut | Complétude |
|---|---|---|
| project-overview.md | ✅ Généré | Complet |
| architecture.md | ✅ Généré + Enrichi (Elicitation) | Complet |
| api-contracts.md | ✅ Généré | Complet |
| data-models-main.md | ✅ Généré | Complet |
| component-inventory-main.md | ✅ Généré | Complet |
| source-tree-analysis.md | ✅ Généré | Complet |
| development-guide.md | ✅ Généré | Complet |
| deployment-guide.md | ✅ Généré | Complet |
| index.md | ✅ Généré | Complet |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
