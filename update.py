#!/usr/bin/env python3
"""
VivreÀ - Script de mise à jour des données des communes françaises.
Indexe les 35 000 communes via l'API Géo officielle + données enrichies.
"""

import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("vivrea-update")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
GEO_API       = "https://geo.api.gouv.fr"
DVF_API       = "https://apidf-preprod.cerema.fr/indicateurs/dv3f/communes"
ARCEP_API     = "https://data.arcep.fr/api/3/action/datastore_search"
FUEL_API      = "https://donnees.roulez-eco.fr/opendata/instantane"
# Le flux est un ZIP contenant un XML PrixCarburants_instantane_YYYYMMDD.xml
# L'URL retourne directement un application/zip

DATA_DIR      = Path("data")
DETAILS_DIR   = DATA_DIR / "details"
INDEX_FILE    = DATA_DIR / "index.json"
FUEL_FILE     = DATA_DIR / "carburants.json"
META_FILE     = DATA_DIR / "meta.json"

SESSION       = requests.Session()
SESSION.headers.update({"User-Agent": "VivreA-Bot/1.0 (+https://vivrea.vox-novalys.fr)"})

RETRY_DELAY   = 2   # secondes entre retries
MAX_RETRIES   = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_get(url: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
    """GET avec retry exponentiel ; retourne None en cas d'échec définitif."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP %s sur %s (tentative %d/%d)", e.response.status_code, url, attempt, MAX_RETRIES)
        except requests.exceptions.RequestException as e:
            log.warning("Erreur réseau sur %s : %s (tentative %d/%d)", url, e, attempt, MAX_RETRIES)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)
    log.error("Abandon après %d tentatives : %s", MAX_RETRIES, url)
    return None


def write_json(path: Path, data, compact: bool = False) -> None:
    """Écrit un fichier JSON (compact ou indenté), crée les parents si besoin."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Écrit : %s (%.1f Ko)", path, path.stat().st_size / 1024)


# ---------------------------------------------------------------------------
# Étape 1 – Récupération de toutes les communes via l'API Géo
# ---------------------------------------------------------------------------

def fetch_all_communes() -> list[dict]:
    """
    Récupère la liste complète des communes françaises.
    Champs demandés : code, nom, codePostal, codeDepartement, population.
    L'API Géo limite à 1000 résultats par requête → on itère par département.
    """
    log.info("=== ÉTAPE 1 : Récupération des communes (API Géo) ===")

    # Liste des départements (incluant DOM)
    deps_data = safe_get(f"{GEO_API}/departements", params={"fields": "code,nom", "limit": 200})
    if not deps_data:
        log.error("Impossible de récupérer les départements. Arrêt.")
        sys.exit(1)

    all_communes: list[dict] = []
    total_deps = len(deps_data)

    for i, dep in enumerate(deps_data, 1):
        code_dep = dep["code"]
        log.info("[%d/%d] Département %s – %s", i, total_deps, code_dep, dep.get("nom", ""))

        communes_data = safe_get(
            f"{GEO_API}/departements/{code_dep}/communes",
            params={
                "fields": "code,nom,codesPostaux,codeDepartement,codeRegion,population,surface,centre,contour",
                "format": "json",
                "geometry": "centre",
                "limit": 5000,
            },
        )
        if not communes_data:
            log.warning("Aucune donnée pour le département %s, on continue.", code_dep)
            continue

        for c in communes_data:
            c["codeDepartement"] = code_dep  # s'assurer que le champ est présent
        all_communes.extend(communes_data)
        time.sleep(0.05)  # politesse envers l'API

    log.info("Total communes récupérées : %d", len(all_communes))
    return all_communes


# ---------------------------------------------------------------------------
# Étape 2 – Données DVF / immobilier (prix m²)
# ---------------------------------------------------------------------------

def fetch_dvf_stats() -> dict[str, dict]:
    """
    Récupère les prix médians DVF par commune via l'API Cerema.
    Retourne un dict {code_insee: {prix_m2, nb_transactions, annee}}.
    """
    log.info("=== ÉTAPE 2 : Données DVF / immobilier ===")
    dvf_by_commune: dict[str, dict] = {}

    try:
        # L'API DVF Cerema supporte le filtrage par année (dernière disponible)
        annee = datetime.now().year - 1  # N-1 pour avoir des données complètes
        params = {
            "annee": annee,
            "ordering": "-nb_ventes",
            "page_size": 500,
            "page": 1,
        }
        page = 1
        total_fetched = 0

        while True:
            params["page"] = page
            data = safe_get(DVF_API, params=params, timeout=45)
            if not data or "results" not in data:
                break

            results = data["results"]
            if not results:
                break

            for item in results:
                code = item.get("code_commune") or item.get("codgeo", "")
                if code:
                    dvf_by_commune[code] = {
                        "prix_m2_median": item.get("prix_m2_median"),
                        "loyer_median":   item.get("loyer_median"),
                        "nb_transactions": item.get("nb_ventes"),
                        "annee_dvf":       annee,
                    }

            total_fetched += len(results)
            log.info("  DVF page %d → %d communes", page, total_fetched)

            if not data.get("next"):
                break
            page += 1
            time.sleep(0.1)

    except Exception as e:
        log.warning("DVF partiellement indisponible : %s", e)

    log.info("DVF : %d communes avec données", len(dvf_by_commune))
    return dvf_by_commune


# ---------------------------------------------------------------------------
# Étape 3 – Score Fibre ARCEP
# ---------------------------------------------------------------------------

def fetch_arcep_fibre() -> dict[str, float]:
    """
    Récupère le taux de couverture fibre par commune via les données ARCEP.
    Retourne {code_insee: taux_percent}.
    """
    log.info("=== ÉTAPE 3 : Couverture Fibre (ARCEP) ===")
    fibre_by_commune: dict[str, float] = {}

    try:
        # Jeu de données ARCEP : déploiement du très haut débit par commune
        # Resource ID du dataset "observatoire-du-deploiement-des-réseaux-fh-et-ftth"
        ARCEP_RESOURCE_ID = "64a4e6f0-fc90-4d37-a9d8-1d8bfe7bab7e"
        params = {
            "resource_id": ARCEP_RESOURCE_ID,
            "limit": 32000,
            "offset": 0,
            "fields": "code_commune,tx_locaux_raccordables_ftth",
        }
        data = safe_get(ARCEP_API, params=params, timeout=60)
        if data and "result" in data and "records" in data["result"]:
            for record in data["result"]["records"]:
                code = record.get("code_commune", "")
                taux = record.get("tx_locaux_raccordables_ftth")
                if code and taux is not None:
                    try:
                        fibre_by_commune[str(code).zfill(5)] = round(float(taux) * 100, 1)
                    except (ValueError, TypeError):
                        pass
    except Exception as e:
        log.warning("ARCEP partiellement indisponible : %s", e)

    log.info("ARCEP Fibre : %d communes avec données", len(fibre_by_commune))
    return fibre_by_commune


# ---------------------------------------------------------------------------
# Étape 4 – Prix carburants (flux instantané)
# ---------------------------------------------------------------------------

def fetch_fuel_prices() -> None:
    """
    Récupère le flux instantané des prix carburants et le stocke en JSON.
    Le flux source est XML → on le parse et on l'agrège par commune.
    """
    log.info("=== ÉTAPE 4 : Prix carburants (flux instantané) ===")
    import xml.etree.ElementTree as ET
    import zipfile
    import io

    try:
        # Désactive le cache HTTP côté serveur
        r = SESSION.get(FUEL_API, timeout=60, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        log.info("Content-Type reçu : %s – taille : %.1f Ko", content_type, len(r.content) / 1024)

        # Le flux peut être un ZIP ou directement du XML
        xml_content: bytes | None = None

        if b"PK" == r.content[:2]:  # signature ZIP
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                xml_names = [n for n in z.namelist() if n.lower().endswith(".xml")]
                if not xml_names:
                    raise ValueError("Aucun fichier XML dans le ZIP carburants")
                xml_content = z.read(xml_names[0])
                log.info("XML extrait : %s", xml_names[0])
        else:
            xml_content = r.content  # flux XML direct

        root = ET.fromstring(xml_content)
        stations: list[dict] = []

        for pdv in root.findall("pdv"):
            code_postal = (pdv.get("cp") or "").strip()
            ville       = (pdv.findtext("ville") or "").strip()
            lat_raw     = pdv.get("latitude")
            lon_raw     = pdv.get("longitude")

            prix: dict[str, float] = {}
            for price_el in pdv.findall("prix"):
                nom    = price_el.get("nom", "")
                valeur = price_el.get("valeur")
                if nom and valeur:
                    try:
                        # L'API fournit les prix en millièmes d'euro (ex: 1759 → 1.759 €)
                        prix[nom] = round(float(valeur) / 1000, 4)
                    except ValueError:
                        pass

            if prix and code_postal:
                try:
                    lat = round(float(lat_raw) / 100000, 6) if lat_raw else None
                    lon = round(float(lon_raw) / 100000, 6) if lon_raw else None
                except (ValueError, TypeError):
                    lat = lon = None
                stations.append({
                    "cp":    code_postal,
                    "ville": ville,
                    "lat":   lat,
                    "lon":   lon,
                    "prix":  prix,
                })

        if not stations:
            log.warning("Aucune station parsée – vérifiez le format XML.")
        else:
            payload = {
                "updated_at":  datetime.utcnow().isoformat() + "Z",
                "nb_stations": len(stations),
                "stations":    stations,
            }
            write_json(FUEL_FILE, payload, compact=True)
            log.info("Carburants : %d stations écrites dans %s", len(stations), FUEL_FILE)

    except Exception as e:
        log.error("Erreur flux carburants : %s", e)
        # On ne plante pas le pipeline : les données existantes restent valides


# ---------------------------------------------------------------------------
# Étape 5 – Construction de l'index et des fichiers détails
# ---------------------------------------------------------------------------

def build_index_and_details(
    communes: list[dict],
    dvf: dict[str, dict],
    fibre: dict[str, float],
) -> None:
    """
    Construit :
    - data/index.json  : index léger (< 1.5 Mo) pour l'autocomplete
    - data/details/{dep}.json : détails enrichis par département
    """
    log.info("=== ÉTAPE 5 : Construction index + détails ===")

    index_entries: list[dict] = []
    details_by_dep: dict[str, list[dict]] = {}

    for c in communes:
        code_insee = c.get("code", "")
        nom        = c.get("nom", "")
        code_dep   = c.get("codeDepartement", code_insee[:2] if len(code_insee) >= 2 else "")
        codes_postaux = c.get("codesPostaux", [])
        cp_principal = codes_postaux[0] if codes_postaux else ""
        population = c.get("population") or 0
        centre     = c.get("centre", {})
        lat        = centre.get("coordinates", [None, None])[1] if centre else None
        lon        = centre.get("coordinates", [None, None])[0] if centre else None

        # ---- Entrée index léger ----
        index_entries.append([
            nom,
            code_insee,
            cp_principal,
            population,
        ])

        # ---- Entrée détail enrichi ----
        detail = {
            "code_insee":     code_insee,
            "nom":            nom,
            "codes_postaux":  codes_postaux,
            "code_dep":       code_dep,
            "code_region":    c.get("codeRegion", ""),
            "population":     population,
            "surface_km2":    round(c.get("surface", 0) / 100, 2) if c.get("surface") else None,
            "lat":            lat,
            "lon":            lon,
        }

        # Enrichissement DVF
        if code_insee in dvf:
            detail["immo"] = dvf[code_insee]

        # Enrichissement Fibre
        taux = fibre.get(code_insee)
        if taux is not None:
            detail["fibre_pct"] = taux

        details_by_dep.setdefault(code_dep, []).append(detail)

    # Écriture index compact
    write_json(INDEX_FILE, index_entries, compact=True)

    # Vérification taille index
    index_size_mb = INDEX_FILE.stat().st_size / (1024 * 1024)
    if index_size_mb > 1.5:
        log.warning("⚠️  Index trop lourd : %.2f Mo (cible < 1.5 Mo)", index_size_mb)
    else:
        log.info("✅ Index OK : %.2f Mo", index_size_mb)

    # Écriture fichiers détails par département
    for dep_code, dep_communes in details_by_dep.items():
        dep_file = DETAILS_DIR / f"{dep_code}.json"
        write_json(dep_file, dep_communes, compact=True)

    log.info("Détails écrits pour %d départements", len(details_by_dep))


# ---------------------------------------------------------------------------
# Étape 6 – Métadonnées
# ---------------------------------------------------------------------------

def write_meta(nb_communes: int) -> None:
    meta = {
        "last_update": datetime.utcnow().isoformat() + "Z",
        "nb_communes": nb_communes,
        "version": "2.0",
        "sources": {
            "communes": "https://geo.api.gouv.fr",
            "immobilier": "https://apidf-preprod.cerema.fr",
            "fibre": "https://data.arcep.fr",
            "carburants": "https://donnees.roulez-eco.fr/opendata/instantane",
        },
    }
    write_json(META_FILE, meta)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║   VivreÀ – Mise à jour des données          ║")
    log.info("╚══════════════════════════════════════════════╝")
    start = time.time()

    # Création des répertoires
    DATA_DIR.mkdir(exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    # Pipeline de données
    communes   = fetch_all_communes()
    dvf_stats  = fetch_dvf_stats()
    fibre_data = fetch_arcep_fibre()
    fetch_fuel_prices()
    build_index_and_details(communes, dvf_stats, fibre_data)
    write_meta(len(communes))

    elapsed = time.time() - start
    log.info("✅ Mise à jour terminée en %.1f secondes.", elapsed)
    log.info("   → %d communes indexées", len(communes))


if __name__ == "__main__":
    main()
