# ══════════════════════════════════════════════════════════════════
# TITRE      : La fiche d'un compte : les champs, leurs longueurs, leurs conversions (au format de la fiche utilisateur Dolibarr)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #e3d4c0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : dit ce qu'est la fiche d'un compte (une trentaine de champs aux noms et aux longueurs de la fiche utilisateur de Dolibarr), valide une saisie en la REFUSANT quand elle est trop longue (jamais en la coupant) et passe des anciens champs de profil à la fiche.
# MÉTHODE    : une table de champs (nom, longueur, forme) ; valider() rend les valeurs propres ou les erreurs ; les six anciens champs de profil se convertissent par des règles écrites ici, vérifiables à la main.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e3d4c0 ▼▼▼
"""La fiche d'un compte.

La fiche garde les noms de la fiche utilisateur de Dolibarr : c'est son FORMAT de profil, pas une dépendance. Sans Dolibarr elle sert telle quelle ; avec lui,
le module dolibarr compare et envoie les champs de sa liste blanche (voir modules/dolibarr). Les longueurs sont celles de la base de Dolibarr (llx_user), lues
sur l'instance d'Orion le 02-11-2026 : lastname, firstname, town 50 · job 128 · téléphones 30 · zip 25 · address, email 255 · lang 6 · color 6 · gender 10.
"""
from __future__ import annotations

import json
import re

# nom : (forme, longueur maximale). Les formes : texte, texte_long, date, booleen, couleur, langue, pays, civilite, genre, reseaux, fuseau, courriel, telephone.
CHAMPS = {
    "civility_code": ("civilite", 6), "gender": ("genre", 10), "lastname": ("texte", 50), "firstname": ("texte", 50),
    "birth": ("date", 10), "job": ("texte", 128), "employee": ("booleen", 1), "ref_employee": ("texte", 50),
    "dateemployment": ("date", 10), "dateemploymentend": ("date", 10),
    "email": ("courriel", 255), "personal_email": ("courriel", 255),
    "office_phone": ("telephone", 30), "user_mobile": ("telephone", 30), "personal_mobile": ("telephone", 30), "office_fax": ("telephone", 30),
    "address": ("texte", 255), "zip": ("texte", 25), "town": ("texte", 50), "country_code": ("pays", 2), "state_code": ("texte", 10),
    "lang": ("langue", 6), "color": ("couleur", 6), "tz": ("fuseau", 64),
    "signature": ("texte_long", 5000), "socialnetworks": ("reseaux", 5000), "note_public": ("texte_long", 5000),
}
ORDRE = tuple(CHAMPS)
DEFAUTS = {k: ("0" if f == "booleen" else "") for k, (f, _) in CHAMPS.items()}
GENRES = ("", "man", "woman", "other")

# Les six anciens champs de profil (table comptes) et ce qu'ils deviennent dans la fiche.
ANCIENS = {"display_name": None, "role_label": "job", "contact_email": "email", "phone": "office_phone", "lang": "lang"}

# « fr » -> « fr_FR » se déduit ; ces langues-là ne se déduisent pas (la variante usuelle de Dolibarr)
LANGUES_DOLIBARR = {"en": "en_US", "pt": "pt_PT", "zh": "zh_CN", "ja": "ja_JP", "sv": "sv_SE", "da": "da_DK", "el": "el_GR", "cs": "cs_CZ", "uk": "uk_UA", "ko": "ko_KR", "he": "he_IL", "ar": "ar_SA"}
RE_COURRIEL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_TEL = re.compile(r"^[0-9+()./\- ]*$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_COULEUR = re.compile(r"^[0-9a-fA-F]{6}$")
RE_LANGUE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?$")
RE_FUSEAU = re.compile(r"^[A-Za-z]+(/[A-Za-z0-9_+-]+)+$|^UTC$")
RE_CIVILITE = re.compile(r"^[A-Za-z0-9._-]{0,6}$")


def langue_courte(lang: str) -> str:
    """« fr_FR » -> « fr » : la forme de l'ancienne colonne comptes.lang."""
    return (lang or "fr").split("_")[0].lower()[:5] or "fr"


def langue_dolibarr(lang: str) -> str:
    """« fr » -> « fr_FR » (la forme de Dolibarr) ; une forme déjà longue est gardée."""
    lang = (lang or "").strip()
    if not lang:
        return ""
    if "_" in lang:
        a, _, b = lang.partition("_")
        return "%s_%s" % (a.lower(), b.upper())
    return LANGUES_DOLIBARR.get(lang.lower(), "%s_%s" % (lang.lower(), lang.upper()))


def couper_nom(nom_affiche: str):
    """« Marie Anne Dupont » -> (« Marie Anne », « Dupont ») : le dernier mot est le nom, le reste le prénom. Un seul mot : tout va dans le nom."""
    mots = (nom_affiche or "").split()
    if not mots:
        return "", ""
    if len(mots) == 1:
        return "", mots[0]
    return " ".join(mots[:-1]), mots[-1]


def nom_affiche(fiche: dict) -> str:
    """Le nom affiché partout : prénom puis nom."""
    return " ".join(x for x in ((fiche.get("firstname") or "").strip(), (fiche.get("lastname") or "").strip()) if x)


def depuis_ancien(display_name="", role_label="", contact_email="", phone="", lang="") -> dict:
    """La fiche d'un compte d'avant la fiche : les règles de la migration (voir docs de la maquette « Mon compte », Mise à niveau)."""
    prenom, nom = couper_nom(display_name)
    return {"firstname": prenom, "lastname": nom, "job": role_label or "", "email": contact_email or "", "office_phone": phone or "", "lang": langue_dolibarr(lang)}


def _un(nom, forme, maxi, v):
    """(valeur propre, erreur)."""
    if forme == "booleen":
        if isinstance(v, str):
            v = v.strip().lower()
        return ("1" if v in (True, 1, "1", "true", "oui", "yes") else "0"), None
    if forme == "reseaux":
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False, sort_keys=True)
        v = str(v or "").strip()
        if v:
            try:
                o = json.loads(v)
            except ValueError:
                return None, "%s : un objet JSON attendu (réseau -> identifiant)" % nom
            if not isinstance(o, dict) or not all(isinstance(k, str) and isinstance(x, str) for k, x in o.items()):
                return None, "%s : un objet JSON attendu (réseau -> identifiant)" % nom
            v = json.dumps(o, ensure_ascii=False, sort_keys=True)
    else:
        v = str(v if v is not None else "").strip()
    if forme == "couleur":
        v = v.lstrip("#")
        if v and not RE_COULEUR.match(v):
            return None, "%s : six chiffres hexadécimaux, sans #" % nom
    elif forme == "date":
        if v and not RE_DATE.match(v):
            return None, "%s : une date AAAA-MM-JJ" % nom
    elif forme == "courriel":
        if v and not RE_COURRIEL.match(v):
            return None, "%s : une adresse e-mail valide" % nom
    elif forme == "telephone":
        if not RE_TEL.match(v):
            return None, "%s : chiffres, espaces et + ( ) . - seulement" % nom
    elif forme == "langue":
        if v:
            v = langue_dolibarr(v)                       # « fr » devient « fr_FR », la forme de Dolibarr
            if not RE_LANGUE.match(v):
                return None, "%s : une langue comme fr_FR" % nom
    elif forme == "pays":
        v = v.upper()
        if v and not re.match(r"^[A-Z]{2}$", v):
            return None, "%s : un code pays à deux lettres (FR, BE…)" % nom
    elif forme == "civilite":
        if not RE_CIVILITE.match(v):
            return None, "%s : six caractères au plus (MR, MME, DR…)" % nom
    elif forme == "genre":
        if v not in GENRES:
            return None, "%s : man, woman ou other" % nom
    elif forme == "fuseau":
        if v:
            try:
                import zoneinfo
                try:
                    zoneinfo.ZoneInfo(v)
                except zoneinfo.ZoneInfoNotFoundError:
                    # une machine sans base de fuseaux (Windows sans tzdata) : on juge la FORME du nom, faute de pouvoir le chercher
                    if zoneinfo.available_timezones() or not RE_FUSEAU.match(v):
                        raise
            except Exception:
                return None, "%s : un fuseau horaire comme Europe/Paris" % nom
    if len(v) > maxi:
        return None, "%s : %d caractères au plus (%d saisis) ; rien n'est coupé" % (nom, maxi, len(v))
    return v, None


def valider(champs: dict):
    """(valeurs propres, erreurs). Un champ inconnu est une erreur ; une valeur trop longue est REFUSÉE, jamais coupée."""
    propres, erreurs = {}, []
    for k, v in (champs or {}).items():
        if k not in CHAMPS:
            erreurs.append("%s : champ inconnu de la fiche" % k)
            continue
        forme, maxi = CHAMPS[k]
        val, err = _un(k, forme, maxi, v)
        if err:
            erreurs.append(err)
        else:
            propres[k] = val
    return propres, erreurs
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : CHAMPS, valider, depuis_ancien, nom_affiche, couper_nom, langue_dolibarr
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : noyau/CN_identite.py (écrit et lit la fiche), docs/CN_maquette-mon-compte.html (la maquette, page Mise à niveau)
