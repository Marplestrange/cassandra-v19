# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : appariement des colonnes d'un CSV (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.2)  #cbdfba
# HÔTE CN    : CN_module.py · csv_apparier @1.0
# RÔLE       : reconnaît les colonnes d'un CSV de contacts (Google, Outlook, français, anglais) et dit à quel champ de la fiche chacune correspond.
# MÉTHODE    : fonction pure : chaque en-tête est aplati (sans accents ni ponctuation) puis cherché dans la table des libellés connus.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=csv_apparier contrat=@1.0 version=EC0 empreinte=cbdfba ▼▼▼
import re
import unicodedata

CSV_CHAMPS = {
    "display_name": ("name", "nom complet", "full name", "display name", "nom affiche", "contact"),
    "_prenom": ("first name", "given name", "prenom"),
    "_nom": ("last name", "family name", "surname", "nom de famille", "nom"),
    "emails": ("e mail 1 value", "e mail address", "email address", "email", "e mail", "courriel", "adresse de messagerie", "adresse e mail", "e mail 2 value",
               "e mail address 2", "adresse de messagerie 2"),
    "phone": ("phone 1 value", "business phone", "home phone", "telephone", "telephone professionnel", "telephone domicile", "tel", "phone"),
    "mobile": ("phone 2 value", "mobile phone", "mobile", "portable", "telephone mobile", "cell phone"),
    "company": ("organization name", "organization 1 name", "company", "societe", "entreprise", "organisation"),
    "job_title": ("organization title", "organization 1 title", "job title", "fonction", "titre", "poste"),
    "address": ("address 1 formatted", "home address", "business street", "adresse", "rue", "adresse professionnelle", "address"),
    "website": ("website 1 value", "web page", "site web", "site", "url"),
    "anniversaire": ("birthday", "anniversaire", "date de naissance", "birth date"),
    "notes": ("notes", "note", "remarques", "comments"),
}

def aplatir(s):
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())

def csv_apparier(entetes):
    connus = {lib: champ for champ, libs in CSV_CHAMPS.items() for lib in libs}
    return {str(i): connus[aplatir(e)] for i, e in enumerate(entetes) if aplatir(e) in connus}

def point_csv_apparier(entree):
    """Le point d'évolution `csv_apparier` (contrat 1.0) : les en-têtes en entrée, {indice de colonne: champ de la fiche} en sortie."""
    return {"appariement": csv_apparier(entree["entetes"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_csv_apparier(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_csv_apparier.json ; corpus doré dans contrats/CN_csv_apparier.corpus.json (sorties de l'ancien code, données synthétiques).
