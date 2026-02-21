# VivreÀ — Guide de Déploiement

**Date :** 2026-02-21

---

## 1. Architecture de Déploiement

```
GitHub Repository (main branch)
        │
        ├── Push to main (hors data/)
        │         │
        │         ▼
        │   GitHub Actions (main.yml)
        │         │
        │         ├── python update.py   (ETL ~10 min)
        │         │
        │         └── git commit & push data/
        │                   │
        │                   ▼
        └──────────── Vercel CDN
                          │
                    Cache-Control headers
                    (public, max-age=3600,
                     stale-while-revalidate=86400)
                          │
                          ▼
                   Utilisateurs finaux
                   (navigateur cache +
                    Vercel Edge Network)
```

**Modèle :** JAMstack — pas de runtime serveur. Tous les assets sont des fichiers statiques servis par Vercel depuis son edge network mondial.

---

## 2. Vercel — Configuration

### 2.1 Rewrites SPA (vercel.json)

Toutes les routes inconnues sont redirigées vers `index.html` pour permettre le routing SPA côté client :

```json
{
  "rewrites": [
    { "source": "/(?!data|explorer|fuel|search\\.worker|404).*", "destination": "/index.html" }
  ]
}
```

**Note :** Les chemins `data/`, `explorer.html`, `fuel.js`, `search.worker.js`, et `404.html` sont exclus du rewrite — ils sont servis directement.

### 2.2 Cache-Control des données

```json
{
  "headers": [
    {
      "source": "/data/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600, stale-while-revalidate=86400" }
      ]
    }
  ]
}
```

| Paramètre | Valeur | Effet |
|---|---|---|
| `max-age=3600` | 1 heure | Le navigateur ne refetch pas pendant 1h |
| `stale-while-revalidate=86400` | 24 heures | Sert la version en cache pendant le revalidation |

### 2.3 Déploiement Vercel

Vercel détecte automatiquement les push sur la branche `main` et déploie les nouveaux assets. Aucune configuration supplémentaire requise pour le CDN.

**URL de production :** `https://vivrea.vox-novalys.fr`

---

## 3. GitHub Actions — Pipeline CI/CD

### 3.1 Fichier : `.github/workflows/main.yml`

**Déclencheurs :**
- `push` sur `main` (uniquement si les fichiers modifiés ne sont PAS dans `data/`)
- `workflow_dispatch` (déclenchement manuel depuis l'UI GitHub)

**Pas de cron schedule** — le pipeline n'est pas automatiquement périodique. Pour une mise à jour régulière des données, il faut déclencher manuellement ou ajouter un `schedule:` dans le workflow.

### 3.2 Étapes du Job CI/CD

```yaml
1. Checkout repository (actions/checkout)
2. Setup Python 3.12
3. pip install -r requirements.txt
4. python update.py              # ~10 minutes
5. git config user + email (bot)
6. git add data/
7. git commit -m "chore(data): mise à jour automatique"
8. git push origin main
```

### 3.3 Permissions

Le job utilise le token GitHub Actions standard (`GITHUB_TOKEN`) avec permissions d'écriture sur le dépôt pour pouvoir committer les fichiers `data/`.

---

## 4. Données — Stratégie de Commit

Les fichiers `data/` sont **committés dans le dépôt Git** — c'est un choix architectural délibéré (ADR-06 dans `docs/architecture.md`).

**Justification :**
- Historique des données disponible (rollback possible)
- Pas de stockage externe nécessaire (S3, base de données)
- Vercel sert directement les fichiers du dépôt
- Données accessibles même sans exécuter le pipeline

**Impact sur la taille du dépôt :** Les fichiers `data/` font ~100-200 Mo au total. Git les compresse efficacement car le contenu JSON change peu entre deux runs.

**Mise à jour manuelle :**
```bash
python update.py
git add data/
git commit -m "chore(data): mise à jour manuelle"
git push
```

---

## 5. Variables d'Environnement Nécessaires

**Aucune.** Toutes les APIs utilisées sont publiques et ne nécessitent pas de token. Le pipeline fonctionne sans configuration d'environnement.

---

## 6. Rollback

En cas de données corrompues :

```bash
# Voir l'historique des commits data/
git log --oneline -- data/

# Revenir aux données d'un commit précédent
git checkout <commit-hash> -- data/
git commit -m "fix(data): rollback données corrompues"
git push
```

Vercel déploiera automatiquement la version restaurée.

---

## 7. Monitoring et Alertes

**Aucun monitoring automatique n'est configuré.** Les métriques de déploiement sont visibles dans :
- Dashboard Vercel (deployments, analytics)
- GitHub Actions (logs du job ETL)
- `data/meta.json` → champ `last_update` (date du dernier run ETL réussi)

**Vérification manuelle :** Comparer `last_update` de `data/meta.json` avec la date actuelle pour s'assurer que les données ne sont pas trop anciennes.

---

## 8. Limitations Connues

| Limitation | Impact | Workaround |
|---|---|---|
| Pas de cron schedule | Données jamais rafraîchies automatiquement | Déclencher manuellement (workflow_dispatch) |
| Pas de test pipeline | Régression possible si une API source change son format | Vérifier `data/meta.json` après chaque run |
| Pas d'alertes si pipeline échoue | Données obsolètes non détectées | Vérifier GitHub Actions manuellement |
| Vercel cache 1h | Données mises à jour non visibles immédiatement | Purger le cache Vercel manuellement si critique |
| ARCEP CKAN down (client-side) | Fallback fibre côté navigateur non-fonctionnel | `fibre_pct` dans les fichiers dep.json reste valide |
| Changement de schéma JSON (ex: ajout VivreScore) | `data/index.json` committé est dans l'ancien format — les nouveaux champs affichent `—` jusqu'au prochain run | Déclencher `python update.py` manuellement immédiatement après le déploiement du changement de schéma |

---

_Généré par le workflow BMAD `document-project` — 2026-02-21_
