---
title: 'VivreScore — Score synthétique de qualité de vie par commune'
slug: 'vivrescore'
created: '2026-02-21'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.12 (stdlib + requests)', 'Vanilla JS ES2022', 'Tailwind CSS CDN v3', 'HTML5']
files_to_modify: ['update.py', 'index.html', 'explorer.html']
code_patterns:
  - 'Bento card : bg-card border border-border rounded-2xl p-5'
  - 'Badge coloré 3 niveaux : emerald (≥75) / amber (≥50) / rose (<50) / gray (null)'
  - 'bar-fill progress bar : bg-black/20 rounded-full h-1.5'
  - 'Sort button : data-key + onclick=setSort() + updateSortUI() gère classes asc/desc'
  - 'Null-safe positional array : a[4] != null ? a[4] : (sortDir === "asc" ? Infinity : -Infinity)'
  - 'Score stocké Python → JSON, jamais calculé côté JS (source de vérité unique)'
test_patterns: ['Aucun test automatisé — tests manuels documentés en section Testing Strategy']
adversarial_review: 'Effectuée 2026-02-21 — 12 findings (1 Critical, 4 High, 4 Medium, 2 Low) — tous corrigés dans cette version'
---

# Tech-Spec: VivreScore — Score synthétique de qualité de vie par commune

**Created:** 2026-02-21
**Reviewed:** 2026-02-21 (adversarial review — 12 findings corrigés)

---

## Overview

### Problem Statement

L'application VivreÀ expose 6 dimensions de données par commune (immobilier, fibre, qualité de l'air, sécurité, données socio-économiques, carburants) mais aucune synthèse agrégée. L'utilisateur doit lire tous les blocs individuellement pour évaluer globalement une commune. L'explorateur départemental (`explorer.html`) ne permet pas de trier par qualité de vie globale — il est impossible de trouver "les meilleures communes du Rhône" sans cliquer sur chacune.

### Solution

Ajouter une fonction Python `compute_vivrescore()` dans `update.py` calculant un score entier **20–100** basé sur 5 dimensions de qualité de vie (fibre, sécurité, air, revenu, chômage). Ce score est stocké dans `data/index.json` (comme 5e élément `c[4]`) et dans `data/details/{dep}.json` (comme champ `"vivrescore"`). Il est affiché comme badge coloré dans les fiches commune et comme colonne triable dans l'explorateur. Zéro calcul côté navigateur — source de vérité unique dans le pipeline Python.

> **Plage réelle : 20–100** (pas 0–100). Chaque dimension rapporte au minimum 4/20 pts. Normalisé sur les dimensions disponibles : le plancher est toujours 20, jamais 0.

### Scope

**In Scope :**
- Fonction Python `compute_vivrescore()` dans `update.py`
- Stockage dans `data/index.json` comme `c[4]` (entier 20-100 ou `null`)
- Stockage dans `data/details/{dep}.json` comme champ `"vivrescore"` (absent si `null`)
- Badge score dans `buildVilleHTML()` dans `index.html` (nouvelle bento card dans la grille principale)
- Badge score dans `buildCompactHTML()` dans `index.html` (mode comparaison)
- Bouton de tri "Score" + logique `sortData()` + badge dans `communeRow()` dans `explorer.html`

**Out of Scope :**
- Personnalisation des pondérations par l'utilisateur
- Affichage de la formule ou du détail de calcul à l'utilisateur
- Modification de `search.worker.js` ou du `WORKER_SRC` inline (aucun impact, `c[4]` ignoré)
- Refactoring `common.js`

---

## Context for Development

### Codebase Patterns

**Convention de couleurs sémantiques (obligatoire dans tout le projet) :**
- Bon (≥75/100) : `text-emerald-400` / `bg-emerald-500/10` / `bg-emerald-400`
- Moyen (≥50/100) : `text-amber-400` / `bg-amber-500/10` / `bg-amber-400`
- Mauvais (<50/100) : `text-rose-400` / `bg-rose-500/10` / `bg-rose-400`
- Absent (null) : `text-gray-500` / `bg-card` / pas de barre de progression

**Bento card existante (modèle à reproduire exactement) :**
```html
<div class="bento-card bg-card border border-border rounded-2xl p-5">
  <p class="text-xs text-gray-500 uppercase tracking-wider mb-1">LABEL</p>
  <p class="text-2xl font-bold {couleur}">{valeur}</p>
  <div class="mt-2 bg-black/20 rounded-full h-1.5">
    <div class="bar-fill h-1.5 rounded-full {barCouleur}" style="width:{pct}%"></div>
  </div>
</div>
```

**Pattern mini card (buildCompactHTML, modèle à reproduire) :**
```html
<div class="bg-card border border-border rounded-xl p-3">
  <p class="text-xs text-gray-500 mb-0.5">LABEL</p>
  <p class="text-base font-bold {couleur}">{valeur}</p>
</div>
```

**Pattern sort button (explorer.html, lignes 131-134) :**
```html
<button class="sort-btn text-xs px-3 py-1.5 bg-card border border-border rounded-lg
               hover:border-indigo-500/40 text-gray-400 transition-colors"
        data-key="score" onclick="setSort('score')">Score</button>
```
`updateSortUI()` gère automatiquement les classes `asc`/`desc`/`text-indigo-400` via `data-key`.

**Règle null dans les tris (corrigée F5) :**
```javascript
// Nulls TOUJOURS en fin de liste, quelle que soit la direction
va = a[4] != null ? a[4] : (sortDir === 'asc' ? Infinity : -Infinity);
vb = b[4] != null ? b[4] : (sortDir === 'asc' ? Infinity : -Infinity);
```
> ⚠️ Ne pas utiliser `?? -1` : placerait les nulls en tête en tri ascendant.

**Règle esc() :** le score est un entier JSON (20-100 ou null), jamais une chaîne externe → `esc()` non requis sur la valeur numérique elle-même.

### Files to Reference

| File | Rôle | Lignes clés |
| ---- | ---- | ----------- |
| `update.py` | Pipeline ETL — `build_index_and_details()` à modifier | 832–920 |
| `update.py` | Helpers existants — insérer `compute_vivrescore()` juste après `normalize_fuel_price()` | ~100 |
| `index.html` | `buildVilleHTML()` — bloc de calcul de couleurs puis grille bento | 617–700 |
| `index.html` | `buildCompactHTML()` — grille 2x2 de mini cards | 937–982 |
| `explorer.html` | Sort buttons HTML | 129–135 |
| `explorer.html` | `sortData()` + `setSort()` | 270–287 |
| `explorer.html` | `communeRow()` | 331–359 |

### Technical Decisions

**TD-01 : Score calculé en Python, stocké en JSON, jamais recalculé en JS**
Source de vérité unique. Élimine le risque de divergence entre explorateur et fiche ville. La formule évolue dans un seul fichier (`update.py`).

**TD-02 : Score stocké dans index.json ET details/{dep}.json**
L'explorateur lit `index.json` (`c[4]`), la fiche ville lit `details/{dep}.json` (`c.vivrescore`). Deux points de stockage, un seul calcul Python.

**TD-03 : Normalisation sur dimensions disponibles uniquement**
Communes rurales sans données crime/air ne sont pas pénalisées. Score = `sum(pts) / max_pts * 100`, normalisé sur les dimensions effectivement renseignées. Conséquence : une commune avec seulement `fibre_pct=95` obtient 100/100 — ce score est "parfait pour les données disponibles", pas un absolu comparable à une commune avec 5 dimensions. Ce comportement est documenté et acceptable pour la v1.

**TD-04 : Score entier 20-100 (pas float), `None` si aucune dimension**
Le plancher à 20 reflète le minimum par dimension (4/20 pts × 100 % = 20). `None` → `null` JSON → `—` dans l'UI. Lisibilité affichage "/100", compacité JSON, cohérence UX.

---

## Implementation Plan

### Tasks

Les tâches sont ordonnées par dépendance : Python d'abord (source de données), puis JS (consommateurs).

---

- [x] **Tâche 1 : Ajouter `compute_vivrescore()` dans `update.py`**
  - **Fichier :** `update.py`
  - **Action :** Insérer la fonction après `normalize_fuel_price()` (vers la ligne 105), avant les fonctions `fetch_*`
  - **Code exact à insérer :**
    ```python
    def compute_vivrescore(
        fibre_pct: Optional[float],
        crime_d:   Optional[dict],
        air_d:     Optional[dict],
        socio_d:   Optional[dict],
        chom_v:    Optional[float],
    ) -> Optional[int]:
        """
        Score synthétique de qualité de vie 20-100.
        Normalisé sur les dimensions disponibles uniquement.
        Retourne None si aucune dimension enrichie n'est disponible.
        Dimensions : fibre (20pts), sécurité (20pts), air (20pts),
                     revenu médian (20pts), chômage (20pts).
        Plancher : 20 (chaque dimension rapporte au minimum 4/20 pts).
        """
        pts = []
        max_pts = 0

        if fibre_pct is not None:
            max_pts += 20
            pts.append(20 if fibre_pct >= 95 else 16 if fibre_pct >= 80
                        else 12 if fibre_pct >= 60 else 8 if fibre_pct >= 40 else 4)

        if crime_d:
            taux = crime_d.get("taux_pour_mille") or 0
            max_pts += 20
            pts.append(20 if taux <= 5 else 16 if taux <= 15
                        else 12 if taux <= 25 else 8 if taux <= 40 else 4)

        if air_d:
            iqa = air_d.get("iqa_moyen")
            if iqa is None:
                iqa = 6  # absent → pire catégorie (pas de `or 6` : évite le remplacement de 0.0)
            max_pts += 20
            pts.append(20 if iqa <= 1 else 16 if iqa <= 2
                        else 12 if iqa <= 3 else 8 if iqa <= 4 else 4)

        rev = socio_d.get("revenu_median") if socio_d else None
        if rev is not None:
            max_pts += 20
            pts.append(20 if rev >= 30000 else 16 if rev >= 25000
                        else 12 if rev >= 20000 else 8 if rev >= 15000 else 4)

        if chom_v is not None:
            max_pts += 20
            pts.append(20 if chom_v <= 4 else 16 if chom_v <= 7
                        else 12 if chom_v <= 10 else 8 if chom_v <= 15 else 4)

        if not pts or max_pts == 0:
            return None
        return round(sum(pts) / max_pts * 100)
    ```

---

- [x] **Tâche 2 : Intégrer le score dans `build_index_and_details()`**
  - **Fichier :** `update.py`
  - **Contexte critique :** Dans `build_index_and_details()`, les variables `fibre_pct` (ligne 886), `crime_d` (ligne 891), `air_d` (ligne 896), `socio_d` et `chom_v` (lignes 901-902) sont assignées **après** la ligne 865. Le calcul du score et l'append à `index_entries` doivent donc intervenir **après la ligne 908** (`detail["socio"] = socio_entry`).

  - **Action A — Supprimer la ligne 865 :**
    ```python
    # SUPPRIMER cette ligne (ligne 865 actuelle) :
    index_entries.append([nom, code_insee, cp_principal, population])
    ```

  - **Action B — Insérer après la ligne 908, avant `details_by_dep.setdefault(...)`** :

    Contexte actuel autour de la ligne 908-909 :
    ```python
    # ... (lignes 886-907 : assignation de fibre_pct, crime_d, air_d, socio_d, chom_v)
            detail["socio"] = socio_entry             # ← ligne 908 (fin des enrichissements)
            details_by_dep.setdefault(code_dep, []).append(detail)  # ← ligne 909
    ```

    Insérer entre ces deux lignes :
    ```python
            detail["socio"] = socio_entry             # ← ligne 908 (inchangée)

            # VivreScore — calculé après TOUTES les dimensions enrichies
            vivrescore = compute_vivrescore(fibre_pct, crime_d, air_d, socio_d, chom_v)
            index_entries.append([nom, code_insee, cp_principal, population, vivrescore])
            if vivrescore is not None:
                detail["vivrescore"] = vivrescore

            details_by_dep.setdefault(code_dep, []).append(detail)  # ← ligne 909 (inchangée)
    ```

  - **Note :** `vivrescore` est calculé une seule fois et réutilisé pour les deux stockages (index et detail). Ne pas appeler `compute_vivrescore()` deux fois.

---

- [x] **Tâche 3 : Badge VivreScore dans `buildVilleHTML()` — `index.html`**
  - **Fichier :** `index.html`
  - **Action A — Ajouter les variables de couleur** dans le bloc de calcul existant (vers la ligne 617, aux côtés des variables `fc`, `fb`, `secColor`, `airColor`, etc.) :
    ```javascript
    const _vs      = c.vivrescore ?? null;
    const vsColor  = _vs == null ? 'text-gray-500'     : _vs >= 75 ? 'text-emerald-400' : _vs >= 50 ? 'text-amber-400'  : 'text-rose-400';
    const vsBg     = _vs == null ? 'bg-card'            : _vs >= 75 ? 'bg-emerald-500/10': _vs >= 50 ? 'bg-amber-500/10' : 'bg-rose-500/10';
    const vsBarCol = _vs == null ? 'bg-gray-700'        : _vs >= 75 ? 'bg-emerald-400'   : _vs >= 50 ? 'bg-amber-400'    : 'bg-rose-400';
    ```
  - **Action B — Modifier la grille** : remplacer `lg:grid-cols-4` par `lg:grid-cols-5` dans le `div` conteneur de la grille bento de `buildVilleHTML()`.
  - **Action C — Ajouter la bento card** en **première position** dans la grille (avant la card Population) :
    ```html
    <div class="bento-card ${vsBg} border border-border rounded-2xl p-5">
      <p class="text-xs text-gray-500 uppercase tracking-wider mb-1">VivreScore</p>
      <p class="text-2xl font-bold ${vsColor}">
        ${_vs != null ? _vs : '—'}${_vs != null ? '<span class="text-sm font-normal text-gray-500"> /100</span>' : ''}
      </p>
      ${_vs != null
        ? `<div class="mt-2 bg-black/20 rounded-full h-1.5"><div class="bar-fill h-1.5 rounded-full ${vsBarCol}" style="width:${_vs}%"></div></div>`
        : '<p class="text-xs text-gray-600 mt-1">Données insuffisantes</p>'}
    </div>
    ```

---

- [x] **Tâche 4 : Badge VivreScore dans `buildCompactHTML()` — `index.html`**
  - **Fichier :** `index.html`
  - **Action A — Ajouter les variables de couleur** en tête de `buildCompactHTML(c)` (mêmes calculs `_vs`, `vsColor` qu'en tâche 3, à dupliquer dans le scope de cette fonction) :
    ```javascript
    const _vs     = c.vivrescore ?? null;
    const vsColor = _vs == null ? 'text-gray-500' : _vs >= 75 ? 'text-emerald-400' : _vs >= 50 ? 'text-amber-400' : 'text-rose-400';
    ```
  - **Action B — Ajouter la mini card** dans la grille 2-colonnes (ligne ~948), en **première position** et avec `col-span-2` pour occuper toute la largeur (les 4 autres cards standard remplissent les 2 lignes suivantes) :
    ```html
    <div class="col-span-2 bg-card border border-border rounded-xl p-3">
      <p class="text-xs text-gray-500 mb-0.5">VivreScore</p>
      <p class="text-base font-bold ${vsColor}">
        ${_vs != null ? _vs + '<span class="text-xs font-normal text-gray-500"> /100</span>' : '—'}
      </p>
    </div>
    ```
  - **Note layout :** `col-span-2` sur la première card + 4 cards standard en 2 colonnes → 3 lignes propres, pas de card orpheline.

---

- [x] **Tâche 5 : Bouton de tri "Score" dans `explorer.html`**
  - **Fichier :** `explorer.html`
  - **Action :** Ajouter le bouton après le bouton "Code postal" (ligne 134) :
    ```html
    <button class="sort-btn text-xs px-3 py-1.5 bg-card border border-border rounded-lg hover:border-indigo-500/40 text-gray-400 transition-colors"
            data-key="score" onclick="setSort('score')">Score</button>
    ```

---

- [x] **Tâche 6 : Mettre à jour `sortData()` et `setSort()` dans `explorer.html`**
  - **Fichier :** `explorer.html`

  - **Action A — Ajouter le cas `'score'`** dans `sortData()`. Le bloc doit être inséré **avant `return 0;`** (la clause par défaut), après le bloc `sortKey === 'cp'`. Contexte exact :
    ```javascript
    // ... (blocs existants : 'nom', 'pop', 'dep', 'cp')
    if (sortKey === 'cp') {
      // ... bloc cp existant ...
    }
    // ↓ INSÉRER ICI — avant le return 0 par défaut
    if (sortKey === 'score') {
      const va = a[4] != null ? a[4] : (sortDir === 'asc' ? Infinity : -Infinity);
      const vb = b[4] != null ? b[4] : (sortDir === 'asc' ? Infinity : -Infinity);
      return sortDir === 'asc' ? va - vb : vb - va;
    }
    return 0;  // ← laisser ce return en place, intact
    ```

  - **Action B — Direction par défaut desc pour score** dans `setSort()` :
    ```javascript
    // AVANT
    sortDir = key === 'pop' ? 'desc' : 'asc';
    // APRÈS
    sortDir = (key === 'pop' || key === 'score') ? 'desc' : 'asc';
    ```

  - **Action C — Mettre à jour le commentaire `sortKey`** au-dessus de `sortData()` (ligne ~270) pour inclure `'score'` dans la liste des clés supportées :
    ```javascript
    // sortKey: 'nom' | 'pop' | 'dep' | 'cp' | 'score'
    ```

---

- [x] **Tâche 7 : Badge score dans `communeRow()` dans `explorer.html`**
  - **Fichier :** `explorer.html`
  - **Action A — Extraire `c[4]`** en tête de `communeRow(c, i)` (après les lignes 332-337) :
    ```javascript
    const score      = c[4] ?? null;
    const scoreColor = score == null ? 'text-gray-500'
                     : score >= 75  ? 'text-emerald-400'
                     : score >= 50  ? 'text-amber-400'
                     : 'text-rose-400';
    ```
  - **Action B — Modifier la div flex du bas de la carte** (ligne ~351-358) pour afficher le badge score à gauche du lien "Voir ↗" :
    ```html
    <div class="flex items-center justify-between">
      <span class="text-xs font-mono text-gray-600">${esc(code)}</span>
      <div class="flex items-center gap-2">
        ${score != null
          ? `<span class="text-xs font-bold ${scoreColor}">${score}<span class="text-gray-600 font-normal">/100</span></span>`
          : ''}
        <a href="/ville/${esc(code)}" onclick="event.stopPropagation()"
           class="text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/20 hover:border-indigo-500/50 rounded-lg px-3 py-1 transition-colors">
          Voir ↗
        </a>
      </div>
    </div>
    ```

---

### Acceptance Criteria

- [x] **AC-01 — Calcul Python : cas nominal**
  - Given : `update.py` est exécuté avec données réelles disponibles
  - When : `compute_vivrescore(fibre_pct=90, crime_d={"taux_pour_mille":12}, air_d={"iqa_moyen":2.0}, socio_d={"revenu_median":22000}, chom_v=8.0)` est appelée
  - Then : retourne un entier entre **20 et 100** inclus (valeur attendue : 72)

- [x] **AC-02 — Calcul Python : toutes données absentes**
  - Given : commune sans aucune donnée enrichie
  - When : `compute_vivrescore(None, None, None, None, None)` est appelée
  - Then : retourne `None`

- [x] **AC-03 — Calcul Python : données partielles**
  - Given : commune avec seulement `fibre_pct=95` et `chom_v=5.0` (3 autres absentes)
  - When : `compute_vivrescore(95, None, None, None, 5.0)` est appelée
  - Then : retourne un score basé sur 2 dimensions (max_pts=40), normalisé 20-100 (valeur attendue : 90)

- [x] **AC-04 — Format `data/index.json`**
  - Given : `update.py` a été exécuté
  - When : `data/index.json` est lu
  - Then : chaque entrée est un tableau de 5 éléments `[String, String, String, Number, Number|null]`
  - And : la taille du fichier reste ≤ 1.5 Mo (vérification automatique existante ligne 913-917)

- [x] **AC-05 — Format `data/details/{dep}.json`**
  - Given : `update.py` a été exécuté pour un département avec données enrichies
  - When : une commune avec score calculable est lue depuis `details/69.json` (Rhône)
  - Then : l'objet contient un champ `"vivrescore"` de type entier 20-100
  - And : les communes sans score calculable n'ont pas le champ `"vivrescore"` (absent, pas `null`)

- [x] **AC-06 — Badge fiche ville : données complètes**
  - Given : l'utilisateur navigue vers `/ville/69123` (Lyon, données enrichies disponibles)
  - When : la page se charge
  - Then : une bento card "VivreScore" est visible avec un score coloré (emerald/amber/rose selon valeur)
  - And : une barre de progression reflète le score en largeur CSS (`width:{score}%`)
  - And : le format affiché est `{score} /100` (ex : `72 /100`)

- [x] **AC-07 — Badge fiche ville : données absentes**
  - Given : l'utilisateur navigue vers une commune sans données enrichies
  - When : la page se charge
  - Then : la bento card "VivreScore" affiche `—` en gris (`text-gray-500`)
  - And : le texte "Données insuffisantes" s'affiche sous la valeur (pas de barre de progression)

- [x] **AC-08 — Badge mode comparaison**
  - Given : l'utilisateur navigue vers `/comparer/75056/69123`
  - When : les deux fiches compactes sont affichées
  - Then : chaque fiche contient une mini card "VivreScore" avec la valeur colorée selon les seuils
  - And : une commune sans score affiche `—`

- [x] **AC-09 — Tri explorateur : tri décroissant par défaut**
  - Given : l'utilisateur est sur `explorer.html` avec un département chargé (ex: `?dep=69`)
  - When : il clique sur le bouton "Score"
  - Then : les communes sont triées par score décroissant (meilleure commune en premier)
  - And : le bouton "Score" reçoit la classe CSS `text-indigo-400` (vérifiable via `document.querySelector('[data-key="score"]').classList.contains('text-indigo-400')`)

- [x] **AC-10 — Tri explorateur : inversion**
  - Given : le tri Score décroissant est actif
  - When : l'utilisateur clique une deuxième fois sur "Score"
  - Then : le tri s'inverse en croissant (score le plus bas en premier)
  - And : le bouton "Score" reçoit la classe CSS `asc`

- [x] **AC-11 — Nulls en fin de liste**
  - Given : l'explorateur contient des communes avec et sans score
  - When : le tri par Score est actif (décroissant OU croissant)
  - Then : toutes les communes avec un score apparaissent avant les communes sans score (`null`)
  - And : les communes sans score (`—`) sont regroupées en fin de liste dans les deux directions

- [x] **AC-12 — Badge score dans les cartes de l'explorateur**
  - Given : l'explorateur est chargé avec `?dep=69` (Rhône — département avec données enrichies)
  - When : les cartes sont rendues
  - Then : la carte de la commune code `69123` (Lyon) affiche un badge score numérique coloré à gauche du lien "Voir ↗"
  - And : la couleur du score respecte les seuils ≥75=`text-emerald-400`, ≥50=`text-amber-400`, <50=`text-rose-400`, null=absent

---

## Additional Context

### Dependencies

Aucune dépendance externe. Le score s'appuie exclusivement sur les champs déjà calculés dans les dictionnaires `fibre`, `crime`, `air`, `socio`, `chomage` — tous disponibles dans le scope de `build_index_and_details()` **après la ligne 908**. Un run `python update.py` est nécessaire pour régénérer les fichiers JSON avant de tester le frontend.

### Testing Strategy

**Ordre de test recommandé :**

1. **Valider Python isolément** (avant de toucher au JS) :
   ```bash
   python -c "
   from update import compute_vivrescore
   print(compute_vivrescore(90, {'taux_pour_mille':12}, {'iqa_moyen':2.0}, {'revenu_median':22000}, 8.0))  # → 72
   print(compute_vivrescore(None, None, None, None, None))   # → None
   print(compute_vivrescore(95, None, None, None, 5.0))      # → 90
   print(compute_vivrescore(0, {'taux_pour_mille':100}, {'iqa_moyen':None}, {'revenu_median':5000}, 50.0))  # → 20 (plancher)
   "
   ```

2. **Exécuter le pipeline complet :**
   ```bash
   python update.py
   ```
   Vérifier dans les logs :
   - `✅ Index OK : X.XX Mo` (doit rester < 1.5 Mo)
   - Absence de warnings/erreurs sur `compute_vivrescore`

3. **Vérifier le format JSON :**
   ```bash
   python -c "import json; d=json.load(open('data/index.json')); print(len(d[0]), d[0])"
   # → 5 ['Paris', '75056', '75001', 2103778, null]  (ou un entier pour les communes avec données)
   python -c "import json; d=json.load(open('data/details/69.json')); print([c.get('vivrescore') for c in d[:5]])"
   ```

4. **Tests navigateur** (serveur `python -m http.server 8080`) :
   - `http://localhost:8080/ville/69123` → score Lyon visible et coloré
   - `http://localhost:8080/ville/75056` → score Paris (peut être null si données absentes)
   - `http://localhost:8080/ville/48091` → commune rurale → `—` et "Données insuffisantes"
   - `http://localhost:8080/comparer/75056/69123` → scores dans les deux fiches compactes
   - `http://localhost:8080/explorer.html?dep=69` → tri Score, nulls en dernier (desc ET asc), badges colorés

### Notes

**Plafond à 20, pas 0 :**
Le minimum par dimension est 4/20 pts. Avec toutes dimensions renseignées au pire : `20/100 * 100 = 20`. Avec une seule dimension au pire : `4/20 * 100 = 20`. Le score ne peut donc jamais être inférieur à 20 si au moins une dimension est disponible. C'est volontaire — les communes rurales sans certaines données ne doivent pas être dépréciées arbitrairement.

**Dimensions volontairement exclues du score :**
- `immo.prix_m2_median` : prix relatifs à la région et au budget (Paris à 9 000€/m² n'est pas "mauvais" per se)
- `socio.taux_pauvrete` : corrélé à `revenu_median` → évite le double-comptage

**Comparabilité inter-communes :**
Une commune avec seulement fibre à 95% obtient 100/100 ("parfait sur les données disponibles"), tandis qu'une commune avec 5 dimensions à 95% obtient aussi 100/100. Les scores ne sont donc pleinement comparables qu'entre communes ayant le même nombre de dimensions renseignées. C'est un compromis accepté (TD-03) : la pénalisation pour données manquantes défavoriserait injustement les communes rurales.

**Seuils de la formule — base et évolutivité :**
Les seuils sont fondés sur les percentiles observés dans les données françaises 2021-2023. Ils peuvent être affinés dans une itération future en modifiant uniquement `compute_vivrescore()` dans `update.py` — l'architecture garantit que le recalcul se propage automatiquement à tous les fichiers JSON au prochain run.

**Worker — aucune modification requise :**
`search.worker.js` (et le `WORKER_SRC` inline dans `index.html`) accèdent à `c[0]`-`c[3]` uniquement. `c[4]` est reçu mais ignoré silencieusement — le comportement de recherche est inchangé. Les résultats retournés restent `{nom, code_insee, cp, pop}`.

---

### Adversarial Review — Findings Log

| ID | Sévérité | Finding | Statut |
|----|----------|---------|--------|
| F1 | Critical | T2 : NameError fatal — `fibre_pct`/`crime_d`/`air_d`/`socio_d`/`chom_v` assignés APRÈS ligne 865 | ✅ Corrigé — T2 réécrit : DELETE ligne 865, INSERT après ligne 908 |
| F2 | High | Score range "0-100" faux — plancher réel à 20 | ✅ Corrigé — "20-100" partout |
| F3 | High | Grille `lg:grid-cols-4` avec 5 cards laissée "à arbitrer" | ✅ Corrigé — T3-B : `lg:grid-cols-5` explicite |
| F4 | High | buildCompactHTML 5 cards en 2-col grid sans résolution | ✅ Corrigé — T4-B : `col-span-2` sur VivreScore card |
| F5 | High | Null sentinel `?? -1` incorrect pour tri ascendant | ✅ Corrigé — `!= null ? val : (asc ? Infinity : -Infinity)` |
| F6 | Medium | T6-A insertion "après bloc cp" ambiguë (risque dead code) | ✅ Corrigé — T6-A : insertion explicitement AVANT `return 0;` avec contexte |
| F7 | Medium | AC-12 non testable (pas de commune spécifique) | ✅ Corrigé — AC-12 : commune `69123` (Lyon, dep=69) |
| F8 | Medium | `iqa_moyen or 6` remplace 0.0 (falsy trap) | ✅ Corrigé — T1 : `iqa = ...; if iqa is None: iqa = 6` |
| F9 | Medium | Comparabilité inter-communes non documentée | ✅ Corrigé — Note ajoutée en Additional Context |
| F10 | Medium | "0-100" en multiple endroits (AC-01, TD-04, docstring) | ✅ Corrigé — "20-100" partout |
| F11 | Low | Commentaire `sortKey` non mis à jour en T6 | ✅ Corrigé — T6-C : mise à jour du commentaire `sortKey` |
| F12 | Low | AC-09 assert sur pseudo-élément CSS (flèche ↓) non testable | ✅ Corrigé — AC-09 : assert sur classe CSS `text-indigo-400` |

## Review Notes — Quick Dev (2026-02-21)

- Revue adversariale post-implémentation effectuée (10 findings)
- Findings : 8 Real, 1 Undecided, 1 Noise
- Résolution : Auto-fix (option F)
- Fixed (8 Real) : F1 (progress bar normalisée), F2 (col-span-2 lg:col-span-1 mobile), F3 (var shadowing), F4 (doc déploiement stale data), F5 (taux is None), F6 (template literal), F7 (commentaire format index), F9 (contraste /100)
- Skipped : F8 (Undecided — taille index.json), F10 (Noise — ?? null)
- Tests Python : 6/6 assertions passées
