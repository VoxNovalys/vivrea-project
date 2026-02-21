# VivreÀ — Guide de Développement

**Date :** 2026-02-21

---

## 1. Prérequis

| Outil | Version | Usage |
|---|---|---|
| Python | 3.12+ | Pipeline ETL (`update.py`) |
| Git | Toute version récente | Gestion du code + commit des données |
| Navigateur moderne | Chrome/Firefox/Edge | Développement et test frontend |
| Serveur HTTP local | Voir §2.2 | Servir les fichiers statiques en dev |

**Aucun Node.js requis** pour le frontend (Tailwind via CDN, pas de bundler).

### Dépendances Python

```bash
pip install requests>=2.31.0
# ou depuis requirements.txt :
pip install -r requirements.txt
```

Aucune autre dépendance. La stdlib Python 3.12 est utilisée pour tout le reste (csv, gzip, zipfile, xml.etree, json, os, datetime, etc.).

---

## 2. Setup Développement Frontend

### 2.1 Cloner le projet

```bash
git clone <url-repo>
cd vivrea-project
```

### 2.2 Serveur HTTP local (obligatoire)

Le frontend **ne peut pas être ouvert en `file://`** — les fetch CORS et le Web Worker exigent un serveur HTTP.

Options recommandées :

```bash
# Python (aucune installation requise)
python -m http.server 8080

# Node (si disponible)
npx serve .

# VS Code : extension "Live Server" → clic droit sur index.html
```

Accès : `http://localhost:8080`

### 2.3 Données de développement

Les fichiers `data/` sont **committés dans le dépôt** et toujours à jour après chaque run CI/CD. Aucune génération locale nécessaire pour développer le frontend — les données sont prêtes à l'emploi.

Pour tester avec des données fraîches : voir §3 (pipeline ETL).

---

## 3. Pipeline ETL (update.py)

### 3.1 Exécution locale

```bash
python update.py
```

**Durée approximative :** 5 à 15 minutes selon la bande passante (téléchargements ~70 Mo de données source).

**Sorties générées :**
- `data/index.json` — index global des 34 875 communes
- `data/details/{dep}.json` — 101 fichiers par département
- `data/carburants.json` — prix carburants en temps réel
- `data/meta.json` — métadonnées du dataset

### 3.2 Variables d'environnement

Aucune variable d'environnement requise. Les tokens API ne sont pas nécessaires car toutes les APIs utilisées sont publiques et sans authentification.

### 3.3 Étapes du pipeline

| Étape | Fonction | Source | Durée |
|---|---|---|---|
| 1 | `fetch_all_communes()` | API Géo gouv.fr | ~30s |
| 2 | `fetch_dvf_stats()` | DVF CEREMA (pagination 500/page) | ~3 min |
| 3 | `fetch_arcep_fibre()` | data.gouv.fr → ZIP DBF ~31 Mo | ~2 min |
| 4 | `fetch_fuel_prices()` | donnees.roulez-eco.fr → XML/ZIP | ~30s |
| 5 | `fetch_crime_data()` | data.gouv.fr → CSV GZ ~36 Mo | ~2 min |
| 6 | `fetch_air_quality()` | ATMO France WFS → CSV | ~1 min |
| 7 | `fetch_filosofi()` | INSEE → ZIP CSV | ~1 min |
| 8 | `fetch_chomage()` | data.gouv.fr → ZIP CSV | ~1 min |

### 3.4 Gestion d'erreurs pipeline

Le pipeline utilise `safe_get()` avec 3 retries et backoff exponentiel (2s × tentative). Si une étape externe échoue, les données correspondantes sont simplement absentes (champs optionnels) — le pipeline ne s'arrête pas.

---

## 4. Workflow de Modification Frontend

### 4.1 Modifier index.html

1. Éditer `index.html` directement
2. Rafraîchir le navigateur — pas de compilation
3. Inspecter la console pour les erreurs JavaScript
4. Tester avec `?v=75056` (Paris), `?v=2A004` (Ajaccio), `?v=97100` (Basse-Terre)

### 4.2 Modifier fuel.js

1. Éditer `fuel.js`
2. Vider le cache navigateur (le module utilise un singleton en mémoire)
3. Tester via `http://localhost:8080/?v=75056` → section carburants

### 4.3 Modifier search.worker.js

1. Éditer `search.worker.js`
2. **Important :** Mettre à jour également `WORKER_SRC` dans `index.html` (fallback inline) si la logique change — les deux doivent rester synchrones
3. Tester : taper dans la barre de recherche, vérifier `#worker-status`

### 4.4 Modifier explorer.html

1. Éditer `explorer.html` directement
2. Tester via `http://localhost:8080/explorer.html?dep=75`
3. Attention : `getDep()` et `esc()` sont dupliqués ici — ne pas créer de dépendance vers `index.html`

---

## 5. Règles de Développement Critiques

### 5.1 Sécurité XSS — utiliser `esc()` systématiquement

```javascript
// ✅ CORRECT — toujours échapper avant innerHTML
el.innerHTML = `<span>${esc(commune.nom)}</span>`;

// ❌ DANGEREUX — injection directe
el.innerHTML = `<span>${commune.nom}</span>`;
```

### 5.2 code_insee — toujours String

```javascript
// ✅ CORRECT
const dep = code_insee.substring(0, 2);

// ❌ DANGEREUX — conversion en Number
const dep = parseInt(code_insee);  // "2A" → NaN, "01" → 1 (perd le zéro)
```

### 5.3 Classes Tailwind — noms complets uniquement

```javascript
// ✅ CORRECT — classe complète
const cls = isPositive ? 'text-green-600' : 'text-red-500';

// ❌ INCORRECT — Tailwind CDN ne peut pas détecter les classes dynamiques partielles
const cls = `text-${color}-600`;
```

### 5.4 Champs optionnels — toujours vérifier avec ?.

```javascript
// ✅ CORRECT
const prix = commune.immo?.prix_m2_median ?? '—';

// ❌ DANGEREUX — crash si immo absent
const prix = commune.immo.prix_m2_median;
```

### 5.5 Ne pas ajouter de dépendances npm

Le projet est intentionnellement sans outillage npm. Toute dépendance frontend doit passer par CDN (et être justifiée dans un ADR). Ne pas créer de `package.json`.

---

## 6. Tests Manuels Recommandés

| Scenario | URL de test | Ce qu'on vérifie |
|---|---|---|
| Commune métropolitaine standard | `?v=69123` (Lyon) | Données complètes (immo, fibre, socio, air) |
| Commune Corse | `?v=2A004` (Ajaccio) | code_insee "2A004" correctement géré |
| DOM-TOM | `?v=97100` (Basse-Terre) | Département 971 chargé |
| Petite commune | `?v=01001` (L'Abergement-Clémenciat) | Données partielles gérées avec `—` |
| Recherche par nom | `?s=saint-étienne` | Slug vers findBySlug + API Géo fallback |
| Mode comparaison | `?v=75056&c=69123` | Deux fiches côte à côte |
| Explorateur | `/explorer.html?dep=13` | Tableau Bouches-du-Rhône |
| Worker status | Home + console | `#worker-status` affiche le nb de communes |

---

## 7. Débogage

### Console navigateur

```javascript
// Vérifier l'état du worker
console.log(state);  // workerReady, workerSize

// Tester la recherche manuellement
wSearch('paris', 5).then(console.log);

// Tester le module carburant
FuelSearch.load().then(d => console.log(d.nb_stations, 'stations'));
```

### Pipeline Python

```bash
# Activer les logs détaillés
python update.py 2>&1 | tee update.log

# Tester une seule étape (modifier update.py temporairement pour appeler une seule fonction)
python -c "import update; print(update.fetch_fuel_prices())"
```

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
