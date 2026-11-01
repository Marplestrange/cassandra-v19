# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dolibarr : Les règles que la fiche de Dolibarr applique avant d'écrire : champs obligatoires, valeurs permises, courriel et adresse web valides, SIREN (9 chiffres) et SIRET (14) pour un tiers français (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dolibarr
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #cab7dd
# HÔTE CN    : CN_module.py · regles_dolibarr @1.0
# RÔLE       : Les règles que la fiche de Dolibarr applique avant d'écrire : champs obligatoires, valeurs permises, courriel et adresse web valides, SIREN (9 chiffres) et SIRET (14) pour un tiers français.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=regles_dolibarr contrat=@1.0 version=EC0 empreinte=cab7dd ▼▼▼
import re

_COURRIEL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_ENUM = {"client": ("0", "1", "2", "3"), "fournisseur": ("0", "1"), "status": ("0", "1"), "tva_assuj": ("0", "1"), "no_email": ("0", "1"), "type": ("0", "1"), "priv": ("0", "1"),
         "statut": ("0", "1"), "status_buy": ("0", "1"), "price_base_type": ("HT", "TTC"), "usage_opportunity": ("0", "1"), "usage_task": ("0", "1"), "usage_bill_time": ("0", "1"),
         "public": ("0", "1")}

_OBLIGATOIRE = {"tiers": ("name",), "contacts": ("lastname",), "produits": ("label",), "projets": ("title",)}

def _regles_dolibarr(objet, champs, creation):
    """Les règles que la fiche de Dolibarr applique avant d'écrire : champs obligatoires, valeurs permises, courriel et adresse web valides, SIREN (9 chiffres) et SIRET (14) pour un tiers français.
    Dolibarr les refuse de toute façon ; les dire ICI évite un aller-retour et un « HTTP 500 » muet. Ce qui n'est pas prouvé ici est laissé à Dolibarr, dont le message est rendu tel quel."""
    if creation:
        for k in _OBLIGATOIRE.get(objet, ()):
            if not str(champs.get(k) or "").strip():
                raise ValueError("%s : obligatoire (comme dans la fiche Dolibarr)" % k)
    for k, permis in _ENUM.items():
        if k in champs and str(champs[k]) not in permis and not (champs[k] in (None, "")):
            raise ValueError("%s : une de ces valeurs : %s" % (k, ", ".join(permis)))
    if champs.get("email") and not _COURRIEL.match(str(champs["email"]).strip()):
        raise ValueError("email : adresse invalide (ErrorBadEMail dans Dolibarr)")
    if champs.get("url") and not re.match(r"^https?://[^\s/]+\.[^\s]{2,}", str(champs["url"]).strip()):
        raise ValueError("url : adresse web invalide, avec http:// ou https:// (ErrorBadUrl dans Dolibarr)")
    if objet == "tiers" and str(champs.get("country_id", "1")) == "1":
        for k, n, nom in (("idprof1", 9, "SIREN"), ("idprof2", 14, "SIRET")):
            v = re.sub(r"\s", "", str(champs.get(k) or ""))
            if v and not (v.isdigit() and len(v) == n):
                raise ValueError("%s (%s) : %d chiffres pour un tiers français" % (k, nom, n))
    return champs

def point_regles_dolibarr(entree):
    """Le point d'évolution `regles_dolibarr` (contrat 1.0)."""
    return {"valeur": _regles_dolibarr(entree["objet"], entree["champs"], entree["creation"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_regles_dolibarr(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dolibarr (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_regles_dolibarr.json ; corpus doré dans contrats/CN_regles_dolibarr.corpus.json (sorties de l'ancien code, données synthétiques).
