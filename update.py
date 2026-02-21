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
# Nouvelle URL DVF CEREMA (l'ancienne /indicateurs/dv3f/communes retourne 404 depuis 2025)
DVF_API   = "https://apidf-preprod.cerema.fr/indicateurs/dv3f/prix/annuel/"
# ARCEP : data.arcep.fr (CKAN) hors ligne — nouvelle source via data.gouv.fr (voir fetch_arcep_fibre)
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


def compute_vivrescore(
    fibre_pct:   Optional[float],
    crime_d:     Optional[dict],
    air_d:       Optional[dict],
    socio_d:     Optional[dict],
    taux_pauv_v: Optional[float],
) -> Optional[int]:
    """
    Score synthétique de qualité de vie 20-100.
    Normalisé sur les dimensions disponibles uniquement.
    Retourne None si aucune dimension enrichie n'est disponible.
    Dimensions : fibre (20pts), sécurité (20pts), air (20pts),
                 revenu médian (20pts), taux de pauvreté (20pts).
    Plancher : 20 (chaque dimension rapporte au minimum 4/20 pts).
    """
    pts = []
    max_pts = 0

    if fibre_pct is not None:
        max_pts += 20
        pts.append(20 if fibre_pct >= 95 else 16 if fibre_pct >= 80
                    else 12 if fibre_pct >= 60 else 8 if fibre_pct >= 40 else 4)

    if crime_d:
        taux = crime_d.get("taux_pour_mille")
        if taux is None:
            taux = 0  # absent → pire catégorie (cohérent avec le pattern iqa is None)
        max_pts += 20
        pts.append(20 if taux <= 5 else 16 if taux <= 15
                    else 12 if taux <= 25 else 8 if taux <= 40 else 4)

    if air_d:
        iqa = air_d.get("iqa_moyen")
        if iqa is None:
            iqa = 6  # absent → pire catégorie (évite le falsy trap de `or 6` sur 0.0)
        max_pts += 20
        pts.append(20 if iqa <= 1 else 16 if iqa <= 2
                    else 12 if iqa <= 3 else 8 if iqa <= 4 else 4)

    rev = socio_d.get("revenu_median") if socio_d else None
    if rev is not None:
        max_pts += 20
        pts.append(20 if rev >= 30000 else 16 if rev >= 25000
                    else 12 if rev >= 20000 else 8 if rev >= 15000 else 4)

    if taux_pauv_v is not None:
        max_pts += 20
        pts.append(20 if taux_pauv_v <= 10 else 16 if taux_pauv_v <= 15
                    else 12 if taux_pauv_v <= 25 else 8 if taux_pauv_v <= 35 else 4)

    if not pts or max_pts == 0:
        return None
    return round(sum(pts) / max_pts * 100)


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
    """
    Récupère les indicateurs DV3F par commune depuis la nouvelle API CEREMA.

    Nouvelle URL (depuis 2025) : /indicateurs/dv3f/prix/annuel/
    Paramètres requis           : echelle=communes, annee=YYYY
    Champ commune               : item["code"]   (pas code_commune)
    Champ prix/m²               : item["pxm2_median_cod111"]  (appartements)
    Champ nb transactions       : item["nbtrans_cod111"]
    """
    log.info("=== ÉTAPE 2 : DVF / immobilier ===")
    dvf: dict[str, dict] = {}

    try:
        current_year = datetime.now().year
        # Sonde : DV3F 2025-1 inclut 2024 ; on essaie 2024 puis 2023 puis 2025
        annee = None
        for try_year in [current_year - 2, current_year - 3, current_year - 1]:
            probe = safe_get(DVF_API, params={"echelle": "communes", "annee": try_year, "page_size": 1}, timeout=30)
            if probe and probe.get("results"):
                annee = try_year
                log.info("DVF : données disponibles pour l'année %d", annee)
                break
            log.info("DVF : aucune donnée pour %d, essai suivant…", try_year)
        if not annee:
            log.warning("DVF : aucune année disponible, abandon.")
            return dvf

        params = {"echelle": "communes", "annee": annee, "page_size": 500, "page": 1}
        page = 1

        while True:
            params["page"] = page
            data = safe_get(DVF_API, params=params, timeout=60)
            if not data or "results" not in data or not data["results"]:
                break

            for item in data["results"]:
                # Le champ commune s'appelle "code" dans la nouvelle API
                raw_code = item.get("code") or item.get("code_commune") or item.get("codgeo", "")
                code = insee_str(raw_code) if raw_code else ""
                pxm2 = item.get("pxm2_median_cod111")   # Prix médian m² – appartements
                if code and pxm2 is not None:
                    dvf[code] = {
                        "prix_m2_median":  round(float(pxm2), 0),
                        "loyer_median":    None,
                        "nb_transactions": item.get("nbtrans_cod111"),
                        "annee_dvf":       annee,
                    }

            log.info("  DVF page %d → %d communes", page, len(dvf))
            if not data.get("next"):
                break
            page += 1
            time.sleep(0.15)

    except Exception as e:
        log.warning("DVF indisponible : %s", e)

    log.info("DVF : %d communes avec données immo", len(dvf))
    return dvf


# ---------------------------------------------------------------------------
# Étape 3 – Fibre ARCEP (source : data.gouv.fr, Shapefile/DBF)
# ---------------------------------------------------------------------------
# L'ancien portail data.arcep.fr (CKAN) est hors ligne depuis 2025.
# Les données sont désormais publiées sur :
#   https://www.data.gouv.fr/fr/datasets/le-marche-du-haut-et-tres-haut-debit-fixe-deploiements/
# Format : ZIP contenant un Shapefile ; le fichier .dbf contient les attributs.
# Colonnes utiles : INSEE_COM (code commune), ftth (locaux raccordables), Locaux (total)
# ---------------------------------------------------------------------------

ARCEP_DATAGOUV_SLUG = "le-marche-du-haut-et-tres-haut-debit-fixe-deploiements"

# SSMSI – délinquance enregistrée (CSV.GZ communal, ≈36 Mo)
CRIME_DATASET = (
    "bases-statistiques-communale-departementale-et-regionale-de-la-delinquance"
    "-enregistree-par-la-police-et-la-gendarmerie-nationales"
)

# INSEE Filosofi 2021 – revenus et pauvreté par commune (ZIP CSV, ≈1 Mo)
FILOSOFI_URL = (
    "https://www.insee.fr/fr/statistiques/fichier/7756729/"
    "base-cc-filosofi-2021-geo2025_csv.zip"
)

# ATMO France GeoServer – IQA commune (WFS CSV)
ATMO_WFS_BASE = "https://data.atmo-france.org/geoserver/ind/ows"


def _read_dbf(data: bytes) -> list[dict]:
    """Lecteur DBF minimaliste (struct), sans dépendance externe.
    Supporte les champs de type C (char) et N/F (numérique)."""
    import io, struct

    buf = io.BytesIO(data)
    header = buf.read(32)
    if len(header) < 32:
        return []

    num_records  = struct.unpack_from("<I", header, 4)[0]
    header_size  = struct.unpack_from("<H", header, 8)[0]
    record_size  = struct.unpack_from("<H", header, 10)[0]

    fields: list[tuple[str, str, int]] = []
    while True:
        fd = buf.read(32)
        if not fd or fd[0] == 0x0D or len(fd) < 32:
            break
        name  = fd[0:11].split(b"\x00")[0].decode("latin-1").strip()
        ftype = chr(fd[11])
        flen  = fd[16]
        fields.append((name, ftype, flen))

    buf.seek(header_size)
    records = []
    for _ in range(num_records):
        raw = buf.read(record_size)
        if not raw or len(raw) < record_size or raw[0] == 0x2A:   # 0x2A = supprimé
            continue
        rec: dict = {}
        pos = 1   # sauter le flag de suppression
        for name, ftype, flen in fields:
            raw_val = raw[pos: pos + flen].decode("latin-1", errors="replace").strip()
            if ftype in ("N", "F"):
                try:
                    rec[name] = float(raw_val) if raw_val else 0.0
                except ValueError:
                    rec[name] = 0.0
            else:
                rec[name] = raw_val
            pos += flen
        records.append(rec)
    return records


def fetch_arcep_fibre() -> dict[str, float]:
    """
    Télécharge le ZIP Commune le plus récent depuis data.gouv.fr (ARCEP THD),
    parse le DBF et retourne {code_insee: fibre_pct}.
    Aucune dépendance extra (struct + zipfile de la stdlib).
    """
    import io, zipfile

    log.info("=== ÉTAPE 3 : Fibre ARCEP (data.gouv.fr) ===")
    fibre: dict[str, float] = {}

    try:
        # 1. Récupérer la liste des ressources du dataset
        meta = safe_get(
            f"https://www.data.gouv.fr/api/1/datasets/{ARCEP_DATAGOUV_SLUG}/",
            timeout=20,
        )
        if not meta or not meta.get("resources"):
            log.warning("ARCEP : impossible de lister les ressources data.gouv.fr")
            return fibre

        # 2. Trouver le ZIP Commune le plus récent (1er dans la liste = le plus récent)
        commune_zips = [
            r for r in meta["resources"]
            if r.get("format", "").lower() == "zip"
            and "commune" in (r.get("title", "") + r.get("url", "")).lower()
        ]
        if not commune_zips:
            log.warning("ARCEP : aucun ZIP Commune trouvé dans le dataset")
            return fibre

        zip_url = commune_zips[0].get("url") or commune_zips[0].get("latest")
        log.info("ARCEP : téléchargement %s", zip_url)

        # 3. Télécharger le ZIP (≈31 Mo)
        resp = SESSION.get(zip_url, timeout=180, stream=False)
        resp.raise_for_status()
        log.info("ARCEP : ZIP reçu (%.1f Mo)", len(resp.content) / 1024 / 1024)

        # 4. Extraire et parser le DBF
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            dbf_names = [n for n in z.namelist() if n.lower().endswith(".dbf")]
            if not dbf_names:
                log.warning("ARCEP : aucun fichier .dbf dans le ZIP")
                return fibre
            log.info("ARCEP : lecture %s", dbf_names[0])
            dbf_data = z.read(dbf_names[0])

        records = _read_dbf(dbf_data)
        log.info("ARCEP : %d enregistrements DBF", len(records))
        if records:
            log.info("ARCEP : colonnes = %s", list(records[0].keys()))

        # 5. Calculer le taux FTTH par commune
        for rec in records:
            code   = str(rec.get("INSEE_COM", "")).strip().zfill(5)
            locaux = float(rec.get("Locaux", 0) or 0)
            ftth   = float(rec.get("ftth",   0) or 0)
            if code and locaux > 0:
                pct = round(ftth / locaux * 100, 1)
                fibre[code] = min(pct, 100.0)

    except Exception as e:
        log.warning("ARCEP indisponible : %s", e)

    log.info("ARCEP : %d communes avec données fibre", len(fibre))
    return fibre


# ── Ancienne section supprimée (CKAN data.arcep.fr hors ligne depuis 2025) ──
# Les fonctions find_arcep_resource_ids() et l'ancien fetch_arcep_fibre() ont
# été remplacées par la version ci-dessus utilisant data.gouv.fr.


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
# Étape 5 – Sécurité / criminalité (SSMSI – data.gouv.fr)
# ---------------------------------------------------------------------------

def fetch_crime_data() -> dict[str, dict]:
    """
    Télécharge les statistiques de délinquance communale (SSMSI / data.gouv.fr).
    CSV(.GZ) ≈ 36 Mo, colonnes : Code.commune, faits, POP, annee.
    Additionne tous les faits de toutes les catégories pour l'année la plus récente.
    Retourne {code_insee: {"taux_pour_mille": X, "annee": Y}}.
    Communes < 2 000 hab non couvertes par cette base.
    """
    import gzip, csv, io

    log.info("=== ÉTAPE 5 : Criminalité (SSMSI) ===")
    crime: dict[str, dict] = {}

    try:
        meta = safe_get(
            f"https://www.data.gouv.fr/api/1/datasets/{CRIME_DATASET}/",
            timeout=20,
        )
        if not meta or not meta.get("resources"):
            log.warning("Crime : dataset non trouvé sur data.gouv.fr")
            return crime

        # Chercher la ressource CSV communale (pas dépt. ni régionale)
        commune_res = None
        for r in meta["resources"]:
            title = ((r.get("title") or "") + (r.get("description") or "")).lower()
            fmt   = r.get("format", "").lower()
            url_l = r.get("url", "").lower()
            is_csv = ("csv" in fmt or url_l.endswith(".csv")
                      or url_l.endswith(".csv.gz") or url_l.endswith(".gz"))
            if is_csv and ("commun" in title or "com." in title):
                commune_res = r
                break

        # Fallback : première ressource CSV/GZ trouvée
        if not commune_res:
            for r in meta["resources"]:
                fmt   = r.get("format", "").lower()
                url_l = r.get("url", "").lower()
                if "csv" in fmt or url_l.endswith((".csv", ".csv.gz", ".gz")):
                    commune_res = r
                    break

        if not commune_res:
            log.warning("Crime : aucune ressource CSV trouvée")
            return crime

        url = commune_res.get("url") or commune_res.get("latest")
        log.info("Crime : téléchargement %s", url)
        resp = SESSION.get(url, timeout=300, stream=False)
        resp.raise_for_status()
        raw = resp.content
        log.info("Crime : %.1f Mo reçu", len(raw) / 1024 / 1024)

        # Décompresser GZ si nécessaire
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)

        text = raw.decode("utf-8-sig", errors="replace")
        sep  = ";" if text.count(";") > text.count(",") else ","

        # Nouveau format 2025 : CODGEO_2025, nombre, taux_pour_mille (pré-calculé),
        # est_diffuse ('diff'=public, 'ndiff'=secret), insee_pop
        # Ancien format : Code.commune / CODGEO, faits, POP — rétrocompatibilité
        faits_by:  dict[str, float] = {}
        pop_by:    dict[str, int]   = {}
        annee_by:  dict[str, int]   = {}

        for row in csv.DictReader(io.StringIO(text), delimiter=sep):
            code = (
                row.get("CODGEO_2025") or row.get("Code.commune") or
                row.get("CODGEO") or row.get("code_commune") or ""
            ).strip()
            if not code:
                continue
            code = code.zfill(5)

            try:
                annee = int(str(row.get("annee") or row.get("Annee") or "0")[:4])
            except (ValueError, TypeError):
                annee = 0

            prev = annee_by.get(code, 0)
            if annee < prev:
                continue  # ignorer les années antérieures

            # Nouveau format : utiliser nombre + insee_pop
            nombre_str = row.get("nombre") or row.get("faits") or row.get("valeur") or ""
            est_diff   = (row.get("est_diffuse") or "diff").lower()
            if est_diff == "ndiff" or nombre_str in ("NA", "na", ""):
                continue  # données secrètes ou manquantes

            try:
                nombre = float(nombre_str.replace(",", "."))
            except (ValueError, TypeError):
                nombre = 0.0

            pop_str = row.get("insee_pop") or row.get("POP") or row.get("pop") or "0"
            try:
                pop = int(float(pop_str.replace(",", ".") if isinstance(pop_str, str) else pop_str))
            except (ValueError, TypeError):
                pop = 0

            if annee > prev:
                # Année plus récente → réinitialiser l'accumulateur
                faits_by[code] = nombre
                annee_by[code] = annee
                if pop > 0:
                    pop_by[code] = pop
            else:
                # Même année, indicateur différent → cumuler
                faits_by[code] = faits_by.get(code, 0.0) + nombre
                if pop > 0:
                    pop_by[code] = pop

        for code, total_faits in faits_by.items():
            pop  = pop_by.get(code, 0)
            year = annee_by.get(code, 0)
            if pop > 0:
                crime[code] = {
                    "taux_pour_mille": round(total_faits / pop * 1000, 1),
                    "annee":           year,
                }

    except Exception as e:
        log.warning("Crime indisponible : %s", e)

    log.info("Crime : %d communes couvertes", len(crime))
    return crime


# ---------------------------------------------------------------------------
# Étape 6 – Qualité de l'air (ATMO France WFS)
# ---------------------------------------------------------------------------

def fetch_air_quality() -> dict[str, dict]:
    """
    Récupère l'indice de qualité de l'air (IQA ATMO) par commune.
    Source : GeoServer ATMO France, couche ind_atmo_{year}, type_zone=COM.
    Essaie l'année la plus récente (année-1 → année-2 → année-3).
    Retourne {code_insee: {"iqa_moyen": X, "label": "...", "annee": Y}}.
    """
    import csv, io

    log.info("=== ÉTAPE 6 : Qualité de l'air (ATMO France) ===")
    air: dict[str, dict] = {}

    # Correspondance code_qual → libellé EAQI
    _labels = {
        1: "Bon", 2: "Moyen", 3: "Dégradé",
        4: "Mauvais", 5: "Très mauvais", 6: "Extrêmement mauvais",
    }

    current_year = datetime.now().year

    for year in range(current_year - 1, current_year - 4, -1):
        date_str = f"{year}-12-31"
        params = {
            "service":      "WFS",
            "version":      "2.0.0",
            "request":      "GetFeature",
            "TypeNames":    "ind:ind_atmo",
            "outputformat": "csv",
            "CQL_FILTER":   f"type_zone='commune' AND date_ech='{date_str}'",
        }
        try:
            resp = SESSION.get(ATMO_WFS_BASE, params=params, timeout=120)
            if resp.status_code != 200 or len(resp.content) < 1000:
                log.info("Air : ind:ind_atmo %d non disponible, essai suivant…", year)
                continue

            text = resp.content.decode("utf-8-sig", errors="replace")
            # Détecter une réponse d'erreur XML
            if "<ExceptionReport" in text[:500] or "ServiceException" in text[:500]:
                log.info("Air : ind:ind_atmo %d erreur WFS, essai suivant…", year)
                continue

            total_by: dict[str, int] = {}
            count_by: dict[str, int] = {}

            for row in csv.DictReader(io.StringIO(text)):
                if (row.get("type_zone") or "").upper() != "COMMUNE":
                    continue
                code = (row.get("code_zone") or "").strip().zfill(5)
                if not code:
                    continue
                try:
                    qual = int(row.get("code_qual") or "0")
                except (ValueError, TypeError):
                    continue
                if qual <= 0:
                    continue
                total_by[code] = total_by.get(code, 0) + qual
                count_by[code] = count_by.get(code, 0) + 1

            if not total_by:
                log.info("Air : ind_atmo_%d – aucune donnée commune trouvée", year)
                continue

            for code in total_by:
                iqa = round(total_by[code] / count_by[code], 1)
                air[code] = {
                    "iqa_moyen": iqa,
                    "label":     _labels.get(min(round(iqa), 6), "Inconnu"),
                    "annee":     year,
                }

            log.info("Air : %d communes (année %d)", len(air), year)
            break

        except Exception as e2:
            log.info("Air : erreur %d – %s", year, e2)
            continue

    if not air:
        log.warning("Air : aucune donnée disponible (ATMO France WFS inaccessible ?)")
    return air


# ---------------------------------------------------------------------------
# Étape 7 – Revenus / pauvreté (INSEE Filosofi 2021)
# ---------------------------------------------------------------------------

def fetch_filosofi() -> dict[str, dict]:
    """
    Télécharge la base Filosofi 2021 (ZIP CSV ≈ 1 Mo) depuis insee.fr.
    Colonnes : CODGEO, MED21 (revenu médian €/UC/an), TP6021 (taux pauvreté %).
    Retourne {code_insee: {"revenu_median": X, "taux_pauvrete": Y, "annee": 2021}}.
    """
    import zipfile, csv, io

    log.info("=== ÉTAPE 7 : Filosofi INSEE (revenus / pauvreté) ===")
    socio: dict[str, dict] = {}

    try:
        resp = SESSION.get(FILOSOFI_URL, timeout=120)
        resp.raise_for_status()
        log.info("Filosofi : %.1f Mo reçu", len(resp.content) / 1024 / 1024)

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            csv_names = [
                n for n in z.namelist()
                if n.lower().endswith(".csv")
                and "meta" not in n.lower()
                and "doc"  not in n.lower()
            ]
            if not csv_names:
                csv_names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                log.warning("Filosofi : aucun CSV dans le ZIP")
                return socio

            log.info("Filosofi : lecture %s", csv_names[0])
            raw = z.read(csv_names[0])

        text = raw.decode("utf-8-sig", errors="replace")
        sep  = ";" if text.count(";") > text.count(",") else ","

        for row in csv.DictReader(io.StringIO(text), delimiter=sep):
            # Nouveau format SDMX long (GEO, FILOSOFI_MEASURE, OBS_VALUE) — INSEE 2025
            # Rétrocompatibilité : ancien format large (CODGEO, MED21, TP6021)
            code = (row.get("GEO") or row.get("CODGEO") or row.get("codgeo") or "").strip()
            if not code:
                continue
            # Nouveau format : GEO_OBJECT='COM' pour les communes
            geo_obj = row.get("GEO_OBJECT", "")
            if geo_obj and geo_obj.upper() not in ("COM", "COMMUNE"):
                continue
            code = code.zfill(5)

            measure = row.get("FILOSOFI_MEASURE", "")
            if measure:
                # Nouveau format SDMX long — pivoter par mesure
                value_str = (row.get("OBS_VALUE") or "").strip()
                if not value_str:
                    continue
                if measure == "MED_SL":      # Revenu médian /UC/an (≈ ancien MED21)
                    try:
                        med = float(value_str.replace(",", "."))
                        entry = socio.setdefault(code, {"annee": 2021})
                        entry["revenu_median"] = round(med, 0)
                    except (ValueError, TypeError):
                        pass
                elif measure == "PR_MD60":   # Taux pauvreté 60 % (≈ ancien TP6021)
                    try:
                        tp = float(value_str.replace(",", "."))
                        entry = socio.setdefault(code, {"annee": 2021})
                        entry["taux_pauvrete"] = round(tp, 1)
                    except (ValueError, TypeError):
                        pass
            else:
                # Ancien format large — rétrocompatibilité
                try:
                    med = float((row.get("MED21") or row.get("med21") or "").replace(",", "."))
                except (ValueError, TypeError):
                    med = None
                try:
                    tp = float((row.get("TP6021") or row.get("tp6021") or "").replace(",", "."))
                except (ValueError, TypeError):
                    tp = None
                if med is not None or tp is not None:
                    socio[code] = {
                        "revenu_median": round(med, 0) if med is not None else None,
                        "taux_pauvrete": round(tp, 1)  if tp  is not None else None,
                        "annee":         2021,
                    }

    except Exception as e:
        log.warning("Filosofi indisponible : %s", e)

    log.info("Filosofi : %d communes", len(socio))
    return socio


# ---------------------------------------------------------------------------
# Étape 8 – Index + détails
# ---------------------------------------------------------------------------

def build_index_and_details(
    communes: list[dict],
    dvf:      dict,
    fibre:    dict,
    crime:    dict,
    air:      dict,
    socio:    dict,
) -> None:
    """
    Génère :
    - data/index.json           : index léger pour l'autocomplete (<1.5 Mo)
    - data/details/{dep}.json   : fiches enrichies par département

    RÈGLE : code_insee TOUJOURS stocké en String ("74081", jamais 74081).
    """
    log.info("=== ÉTAPE 8 : Index + détails ===")

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

        # Criminalité (SSMSI)
        crime_d = crime.get(code_insee)
        if crime_d:
            detail["securite"] = crime_d

        # Qualité de l'air (ATMO France)
        air_d = air.get(code_insee)
        if air_d:
            detail["air"] = air_d

        # Socio-économique : Filosofi
        socio_d = socio.get(code_insee)
        if socio_d:
            detail["socio"] = dict(socio_d)

        # VivreScore — calculé après TOUTES les dimensions enrichies
        # Entrée index léger : [nom, code_insee(str), cp(str), pop(int), vivrescore(int|null)]
        taux_pauv_v = socio_d.get("taux_pauvrete") if socio_d else None
        vivrescore = compute_vivrescore(fibre_pct, crime_d, air_d, socio_d, taux_pauv_v)
        index_entries.append([nom, code_insee, cp_principal, population, vivrescore])
        if vivrescore is not None:
            detail["vivrescore"] = vivrescore

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
        "version":     "2.3",
        "sources": {
            "communes":    "https://geo.api.gouv.fr",
            "immobilier":  "https://apidf-preprod.cerema.fr",
            "fibre":       "https://www.data.gouv.fr (ARCEP)",
            "carburants":  "https://donnees.roulez-eco.fr/opendata/instantane",
            "criminalite": "https://www.data.gouv.fr (SSMSI)",
            "air":         "https://data.atmo-france.org",
            "revenus":     "https://www.insee.fr (Filosofi 2021)",
            "pauvrete":    "https://www.insee.fr (Filosofi 2021)",
        },
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║   VivreÀ – Mise à jour des données v2.3     ║")
    log.info("╚══════════════════════════════════════════════╝")
    start = time.time()

    DATA_DIR.mkdir(exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    communes   = fetch_all_communes()
    dvf_stats  = fetch_dvf_stats()
    fibre_data = fetch_arcep_fibre()
    fetch_fuel_prices()
    crime_data = fetch_crime_data()
    air_data   = fetch_air_quality()
    socio_data = fetch_filosofi()
    build_index_and_details(
        communes, dvf_stats, fibre_data,
        crime_data, air_data, socio_data,
    )
    write_meta(len(communes))

    log.info("✅ Terminé en %.1f s – %d communes indexées", time.time() - start, len(communes))


if __name__ == "__main__":
    main()
