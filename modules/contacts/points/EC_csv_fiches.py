# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : fiches d'un CSV (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.1)  #daa490
# HÔTE CN    : CN_module.py · csv_fiches @1.0
# RÔLE       : transforme les lignes d'un CSV de contacts en fiches, selon l'appariement des colonnes.
# MÉTHODE    : fonction pure : une fiche par ligne ; un nom recomposé du prénom et du nom si aucun nom complet n'est donné ; une ligne sans nom ni adresse est ignorée.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=csv_fiches contrat=@1.0 version=EC0 empreinte=daa490 ▼▼▼
import re

def csv_fiches(d, appariement):
    fiches = []
    for ligne in d["lignes"]:
        f, prenom, nom = {"emails": []}, "", ""
        for i, champ in appariement.items():
            try:
                v = str(ligne[int(i)] or "").strip()
            except (IndexError, ValueError):
                v = ""
            if not v:
                continue
            if champ == "_prenom":
                prenom = v
            elif champ == "_nom":
                nom = v
            elif champ == "emails":
                for a in re.split(r"[;,\s]+", v):
                    a = a.strip().lower()
                    if "@" in a and a not in f["emails"]:
                        f["emails"].append(a)
            elif champ not in f:
                f[champ] = v
        if not f.get("display_name"):
            f["display_name"] = " ".join(x for x in (prenom, nom) if x)
        if f.get("display_name") or f["emails"]:
            fiches.append(f)
    return fiches

def point_csv_fiches(entree):
    """Le point d'évolution `csv_fiches` (contrat 1.0) : les lignes et l'appariement en entrée, les fiches en sortie."""
    return {"fiches": csv_fiches({"lignes": entree["lignes"]}, entree["appariement"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_csv_fiches(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_csv_fiches.json ; corpus doré dans contrats/CN_csv_fiches.corpus.json (sorties de l'ancien code, données synthétiques).
