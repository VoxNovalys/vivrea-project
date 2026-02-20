#!/usr/bin/env python3
"""
VivreÀ - Script de mise à jour des données des communes françaises.
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Logging
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
GEO_API   = "https://geo.api.gouv.fr"
DVF_API   = "https://apidf-preprod.cerema.fr/indicateurs/dv3f/communes"
ARCEP_API = "https://data.arcep.fr/api/3/action/datastore_search"
FUEL_API  = "https://donnees.roulez-eco.fr/opendata/instantane"

DATA_DIR    = Path("data")
DETAILS_DIR = DATA_DIR / "details"
INDEX_FILE  = DATA_DIR / "index.json"
FUEL_FILE   = DATA_DIR / "carburants.json"
META_FILE   = DATA_DIR / "meta.json"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "VivreA-Bot/1.0 (+https://vivrea.vox-novalys.fr)"})

RETRY_DELAY = 2
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_get(url: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP %s – %s (tentative %d/%d)", e.response.status_code, url, attempt, MAX_RETRIES)
        except requests.exceptions.RequestException as e:
            log.warning("Réseau : %s – %s (tentative %d/%d)", e, url, attempt, MAX_RETRIES)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)
    log.error("Abandon : %s", url)
    return None


def write_json(path: Path, data, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Écrit : %s (%.1f Ko)", path, path.stat().st_size / 1024)


def insee_str(code) -> str:
    """Retourne un code INSEE normalisé : String 5 chars, zéro-paddé."""
    return str(code).strip().zfill(5) if code else ""


def normalize_fuel_price(raw_str: str) -> Optional[float]:
    """
    Convertit une valeur de prix carburant en euros décimaux (ex: 1.732).

    L'API gouvernementale peut retourner deux formats :
      - Décimal  : "1.732"  → stocker 1.732  (déjà en €)
      - Entier   : "1732"   → stocker 1.732  (millièmes → ÷ 1000)

    Règle : si la valeur brute > 100, c'est des millièmes → diviser par 1000.
    """
    try:
        # Normalise les variantes : virgule décimale, espaces (ex: "1,732" → "1.732")
        cleaned = str(raw_str).strip().replace(' ', '').replace(',', '.')
        raw = float(cleaned)
        if raw <= 0:
            return None
        if raw > 100:
            # Format millièmes (ex: 1732 → 1.732 €)
            return round(raw / 1000, 4)
        else:
            # Format décimal (ex: 1.732 → 1.732 €)
            return round(raw, 4)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Étape 1 – Communes (API Géo)
# ---------------------------------------------------------------------------

def fetch_all_communes() -> list[dict]:
    log.info("=== ÉTAPE 1 : Communes (API Géo) ===")

    deps_data = safe_get(f"{GEO_API}/departements", params={"fields": "code,nom", "limit": 200})
    if not deps_data:
        log.error("Impossible de récupérer les départements.")
        sys.exit(1)

    all_communes: list[dict] = []
    total = len(deps_data)

    for i, dep in enumerate(deps_data, 1):
        code_dep = dep["code"]
        log.info("[%d/%d] Département %s", i, total, code_dep)

        data = safe_get(
            f"{GEO_API}/departements/{code_dep}/communes",
            params={
                "fields": "code,nom,codesPostaux,codeDepartement,codeRegion,population,surface,centre",
                "format": "json",
                "geometry": "centre",
                "limit": 5000,
            },
        )
        if not data:
            log.warning("Aucune donnée pour %s", code_dep)
            continue

        for c in data:
            c["codeDepartement"] = code_dep
        all_communes.extend(data)
        time.sleep(0.05)

    log.info("Total : %d communes", len(all_communes))
    return all_communes


# ---------------------------------------------------------------------------
# Étape 2 – DVF / immobilier
# ---------------------------------------------------------------------------

def fetch_dvf_stats() -> dict[str, dict]:
    log.info("=== ÉTAPE 2 : DVF / immobilier ===")
    dvf: dict[str, dict] = {}

    try:
        annee = datetime.now().year - 1
        params = {"annee": annee, "ordering": "-nb_ventes", "page_size": 500, "page": 1}
        page = 1

        while True:
            params["page"] = page
            data = safe_get(DVF_API, params=params, timeout=45)
            if not data or "results" not in data or not data["results"]:
                break

            for item in data["results"]:
                raw_code = item.get("code_commune") or item.get("codgeo", "")
                code = str(raw_code).strip() if raw_code else ""
                if code:
                    dvf[code] = {
                        "prix_m2_median":  item.get("prix_m2_median"),
                        "loyer_median":    item.get("loyer_median"),
                        "nb_transactions": item.get("nb_ventes"),
                        "annee_dvf":       annee,
                    }

            log.info("  DVF page %d → %d communes", page, len(dvf))
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.1)

    except Exception as e:
        log.warning("DVF indisponible : %s", e)

    log.info("DVF : %d communes", len(dvf))
    return dvf


# ---------------------------------------------------------------------------
# Étape 3 – Fibre ARCEP
# ---------------------------------------------------------------------------

def fetch_arcep_fibre() -> dict[str, float]:
    log.info("=== ÉTAPE 3 : Fibre ARCEP ===")
    fibre: dict[str, float] = {}

    RESOURCE_IDS = [
        "64a4e6f0-fc90-4d37-a9d8-1d8bfe7bab7e",
        "b8e68b0e-2a66-4c15-9d39-1fe3fce67e74",
    ]
    FIBRE_COLS = ["tx_locaux_raccordables_ftth", "taux_ftth", "pct_ftth"]

    try:
        data = None
        for rid in RESOURCE_IDS:
            data = safe_get(ARCEP_API, params={"resource_id": rid, "limit": 32000, "offset": 0}, timeout=60)
            if data and data.get("result", {}).get("records"):
                log.info("ARCEP resource_id=%s → %d enregistrements", rid, len(data["result"]["records"]))
                break
            log.warning("ARCEP resource_id=%s : vide", rid)
            data = None

        if not data:
            log.warning("ARCEP : aucun jeu de données.")
            return fibre

        records = data["result"]["records"]

        # Détecter la colonne fibre
        fibre_col = next((c for c in FIBRE_COLS if records and c in records[0]), None)
        log.info("ARCEP : colonne fibre = %s", fibre_col)

        # Diagnostic : premiers enregistrements pour vérifier le format des codes
        for rec in records[:5]:
            log.info(
                "ARCEP debug – code_commune=%r code_insee=%r %s=%r",
                rec.get("code_commune"),
                rec.get("code_insee"),
                fibre_col or "?",
                rec.get(fibre_col) if fibre_col else None,
            )

        for record in records:
            # ARCEP : code_commune = code INSEE (pas le code postal)
            raw_code = record.get("code_commune") or record.get("code_insee") or ""
            code = insee_str(raw_code)
            if not code:
                continue

            taux_raw = record.get(fibre_col) if fibre_col else None
            if taux_raw is None:
                continue
            try:
                taux = float(taux_raw)
                # Auto-détection ratio [0;1] ou pourcentage [0;100]
                fibre_pct = round(taux if taux > 1 else taux * 100, 1)
                fibre[code] = min(fibre_pct, 100.0)
            except (ValueError, TypeError):
                pass

    except Exception as e:
        log.warning("ARCEP indisponible : %s", e)

    log.info("ARCEP : %d communes avec fibre", len(fibre))
    return fibre


# ---------------------------------------------------------------------------
# Étape 4 – Prix carburants
# ---------------------------------------------------------------------------

def fetch_fuel_prices() -> None:
    """
    Récupère et stocke les prix carburants en euros décimaux (ex: 1.732).

    L'API peut retourner deux formats :
      - valeur="1.732"  → euros décimaux → stocker 1.732
      - valeur="1732"   → millièmes      → diviser par 1000 → stocker 1.732

    La fonction normalize_fuel_price() gère les deux cas automatiquement
    avec le seuil : raw > 100 → millièmes, sinon euros décimaux.
    """
    log.info("=== ÉTAPE 4 : Carburants ===")
    import xml.etree.ElementTree as ET
    import zipfile
    import io

    try:
        r = SESSION.get(FUEL_API, timeout=60, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        log.info("Flux carburants reçu : %.1f Ko", len(r.content) / 1024)

        # ZIP ou XML direct
        if r.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                xml_names = [n for n in z.namelist() if n.lower().endswith(".xml")]
                if not xml_names:
                    raise ValueError("Aucun XML dans le ZIP")
                xml_content = z.read(xml_names[0])
                log.info("XML extrait : %s", xml_names[0])
        else:
            xml_content = r.content

        root = ET.fromstring(xml_content)
        stations: list[dict] = []
        sample_done = False

        for pdv in root.findall("pdv"):
            cp          = (pdv.get("cp") or "").strip()
            ville       = (pdv.findtext("ville") or "").strip()
            adresse     = (pdv.findtext("adresse") or "").strip()
            nom_station = (pdv.findtext("enseignes/enseigne") or "").strip()
            lat_r       = pdv.get("latitude")
            lon_r       = pdv.get("longitude")

            prix: dict[str, float] = {}
            maj:  dict[str, str]   = {}
            for price_el in pdv.findall("prix"):
                nom    = price_el.get("nom", "")
                valeur = price_el.get("valeur", "")
                maj_ts = price_el.get("maj", "")
                if nom:
                    try:
                        price = normalize_fuel_price(valeur)
                        prix[nom] = price if price is not None else 0
                        if maj_ts:
                            maj[nom] = maj_ts
                    except Exception:
                        prix[nom] = 0

            if not prix or not cp:
                continue

            # Log diagnostic sur la première station
            if not sample_done:
                first_k, first_v = next(iter(prix.items()))
                log.info("CARBURANTS sample – cp=%s ville=%s %s=%.4f €", cp, ville, first_k, first_v)
                sample_done = True

            try:
                lat = round(float(lat_r) / 100000, 6) if lat_r else None
                lon = round(float(lon_r) / 100000, 6) if lon_r else None
            except (ValueError, TypeError):
                lat = lon = None

            stations.append({
                "nom":     nom_station,
                "cp":      cp,
                "ville":   ville,
                "adresse": adresse,
                "lat":     lat,
                "lon":     lon,
                "prix":    prix,
                "maj":     maj,
            })

        if not stations:
            log.warning("Aucune station parsée.")
        else:
            write_json(FUEL_FILE, {
                "updated_at":  datetime.utcnow().isoformat() + "Z",
                "nb_stations": len(stations),
                "stations":    stations,
            }, compact=True)
            log.info("Carburants : %d stations → %s", len(stations), FUEL_FILE)

    except Exception as e:
        log.error("Erreur carburants : %s", e)


# ---------------------------------------------------------------------------
# Étape 5 – Index + détails
# ---------------------------------------------------------------------------

def build_index_and_details(communes: list[dict], dvf: dict, fibre: dict) -> None:
    """
    Génère :
    - data/index.json           : index léger pour l'autocomplete (<1.5 Mo)
    - data/details/{dep}.json   : fiches enrichies par département

    RÈGLE : code_insee TOUJOURS stocké en String ("74081", jamais 74081).
    """
    log.info("=== ÉTAPE 5 : Index + détails ===")

    index_entries: list[list] = []
    details_by_dep: dict[str, list[dict]] = {}

    for c in communes:
        code_insee    = insee_str(c.get("code", ""))   # String 5 chars
        nom           = c.get("nom", "")
        code_dep      = str(c.get("codeDepartement", ""))
        codes_postaux = [str(cp) for cp in c.get("codesPostaux", [])]
        cp_principal  = codes_postaux[0] if codes_postaux else ""
        population    = c.get("population") or 0
        centre        = c.get("centre") or {}
        coords        = centre.get("coordinates", [None, None])
        lat, lon      = coords[1], coords[0]

        # Entrée index léger : [nom, code_insee(str), cp(str), pop(int)]
        index_entries.append([nom, code_insee, cp_principal, population])

        # Entrée détail
        detail: dict = {
            "code_insee":    code_insee,        # String — TOUJOURS
            "nom":           nom,
            "codes_postaux": codes_postaux,
            "code_dep":      code_dep,
            "code_region":   str(c.get("codeRegion", "")),
            "population":    population,
            "surface_km2":   round(c.get("surface", 0) / 100, 2) if c.get("surface") else None,
            "lat":           lat,
            "lon":           lon,
        }

        # DVF : lookup String → String
        dvf_data = dvf.get(code_insee)
        if dvf_data:
            detail["immo"] = dvf_data

        # Fibre : lookup String 5-chars → String 5-chars
        fibre_pct = fibre.get(code_insee)
        if fibre_pct is not None:
            detail["fibre_pct"] = fibre_pct

        details_by_dep.setdefault(code_dep, []).append(detail)

    write_json(INDEX_FILE, index_entries, compact=True)

    size_mb = INDEX_FILE.stat().st_size / (1024 * 1024)
    if size_mb > 1.5:
        log.warning("⚠️  Index trop lourd : %.2f Mo", size_mb)
    else:
        log.info("✅ Index OK : %.2f Mo", size_mb)

    for dep_code, dep_list in details_by_dep.items():
        write_json(DETAILS_DIR / f"{dep_code}.json", dep_list, compact=True)

    log.info("Détails : %d départements", len(details_by_dep))


# ---------------------------------------------------------------------------
# Étape 6 – Métadonnées
# ---------------------------------------------------------------------------

def write_meta(nb_communes: int) -> None:
    write_json(META_FILE, {
        "last_update": datetime.utcnow().isoformat() + "Z",
        "nb_communes": nb_communes,
        "version":     "2.2",
        "sources": {
            "communes":   "https://geo.api.gouv.fr",
            "immobilier": "https://apidf-preprod.cerema.fr",
            "fibre":      "https://data.arcep.fr",
            "carburants": "https://donnees.roulez-eco.fr/opendata/instantane",
        },
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║   VivreÀ – Mise à jour des données v2.2     ║")
    log.info("╚══════════════════════════════════════════════╝")
    start = time.time()

    DATA_DIR.mkdir(exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    communes   = fetch_all_communes()
    dvf_stats  = fetch_dvf_stats()
    fibre_data = fetch_arcep_fibre()
    fetch_fuel_prices()
    build_index_and_details(communes, dvf_stats, fibre_data)
    write_meta(len(communes))

    log.info("✅ Terminé en %.1f s – %d communes indexées", time.time() - start, len(communes))


if __name__ == "__main__":
    main()
