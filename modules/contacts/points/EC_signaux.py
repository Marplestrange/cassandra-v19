# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : rapprochement des doublons par seaux (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.2.0)  #111e6e
# HÔTE CN    : CN_module.py · signaux @1.0
# RÔLE       : trouve toutes les paires de fiches qui se ressemblent (adresse, nom, numéro, société, site) et dit ce qui les motive.
# MÉTHODE    : fonction pure ; par SEAUX (une clé = un seau) plutôt que chacun contre chacun : mille fiches feraient un demi-million de comparaisons ; un seau de plus de huit fiches est ignoré.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=signaux contrat=@1.0 version=EC0 empreinte=111e6e ▼▼▼
import re
import unicodedata

FORMES = ("sarl", "sas", "sasu", "sa", "eurl", "sci", "scop", "scic", "snc", "gmbh", "ltd", "limited", "inc", "llc", "bv", "srl", "spa", "ag",
          "et fils", "and sons", "et cie", "and co", "group", "groupe")
LOCAL_MIN = 4
LOCAL_VIDES = ("contact", "info", "bonjour", "hello", "accueil", "secretariat", "secretaire", "admin", "administration", "compta", "comptabilite", "facture", "factures",
               "commande", "commandes", "service", "support", "sav", "direction", "commercial", "commerciaux", "noreply", "no-reply", "nepasrepondre", "postmaster",
               "webmaster", "rh", "recrutement", "devis", "client", "clients")

def aplatir(s):
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())

def norm_nom(s):
    """Le nom, comparable : aplati, débarrassé de sa forme juridique. Un nom sans aucune lettre garde la signature de ses symboles."""
    t = aplatir(s)
    if not t:
        brut = " ".join(str(s or "").split())
        return ("sym:" + brut.lower()) if brut else ""
    for f in FORMES:
        t = re.sub(r"(^|\s)%s(\s|$)" % re.escape(f), " ", t)
    return " ".join(t.split())

def norm_tel(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[-9:] if len(d) >= 9 else ""

def norm_site(s):
    t = re.sub(r"^[a-z]+://", "", str(s or "").strip().lower()).split("/")[0]
    t = re.sub(r"^www\.", "", t)
    return t if "." in t else ""

def _signaux(fiches):
    """Tous les rapprochements, paire par paire, avec ce qui les motive. Par SEAUX plutôt que chacun contre chacun : mille fiches feraient un demi-million de comparaisons."""
    seaux = {}

    def poser(cle, valeur, fid, dit):
        if valeur:
            seaux.setdefault((cle, valeur), []).append((fid, dit))
    for c in fiches:
        fid = c["id"]
        for a in c.get("emails") or []:
            a = a.strip().lower()
            if not a:
                continue
            poser("adresse", a, fid, "%s des deux côtés" % a)
            loc = a.split("@")[0]
            if len(loc) >= LOCAL_MIN and loc not in LOCAL_VIDES:
                poser("local", loc, fid, "« %s » chez deux domaines" % loc)
        nom = norm_nom(c.get("display_name"))
        poser("nom", nom, fid, "« %s » une fois le nom normalisé" % nom)
        tel = norm_tel(c.get("phone")) or norm_tel(c.get("mobile"))
        poser("tel", tel, fid, "même numéro, …%s" % tel[-4:])
        soc = norm_nom(c.get("company"))
        poser("societe", soc, fid, "même société : « %s »" % soc)
        site = norm_site(c.get("website"))
        poser("site", site, fid, "même site : %s" % site)
    paires = {}
    for (cle, _), lot in seaux.items():
        if len(lot) < 2 or len(lot) > 8:
            continue
        for i in range(len(lot)):
            for j in range(i + 1, len(lot)):
                a, b = sorted((lot[i][0], lot[j][0]))
                if a != b:
                    paires.setdefault((a, b), {})[cle] = lot[i][1]
    return paires

def signaux(entree):
    """Le point d'évolution `signaux` (contrat 1.0) : des fiches en entrée, les paires à rapprocher et ce qui les motive en sortie."""
    paires = _signaux(entree["fiches"])
    return {"paires": [{"a": a, "b": b, "signaux": sig} for (a, b), sig in paires.items()]}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `signaux(entree)` est le point d'évolution. Les normaliseurs (aplatir, norm_nom, norm_tel, norm_site) sont COPIÉS ici : une EC ne peut importer que la bibliothèque standard
#      pure, jamais le module. L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni l'ordre des paires rendues.
# CN : appelée par `signaux(fiches, appeler)` de CN_module.py (ctx.point), qui ne transmet que les champs utiles (jamais la photo ni les notes) et rebâtit le dictionnaire des paires.
# LIEN : contrat dans contrats/CN_signaux.json ; corpus doré dans contrats/CN_signaux.corpus.json (sorties de l'ancienne fonction, 17-10-2026, données synthétiques).
