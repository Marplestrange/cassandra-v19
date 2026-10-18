# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : décodage d'un CSV (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.2)  #4dcc08
# HÔTE CN    : CN_module.py · csv_decoder @1.0
# RÔLE       : trouve l'encodage d'un fichier CSV de contacts et le lit en texte.
# MÉTHODE    : fonction pure : UTF-8 d'abord parce qu'il échoue franchement sur ce qui n'en est pas ; cp1252 accepte presque tout ; une marque d'ordre des octets est retirée.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=csv_decoder contrat=@1.0 version=EC0 empreinte=4dcc08 ▼▼▼

def csv_decoder(octets):
    """UTF-8 d'abord parce qu'il ÉCHOUE franchement sur ce qui n'en est pas, alors que cp1252 accepte n'importe quels octets sans jamais lever."""
    if octets[:3] == b"\xef\xbb\xbf":
        return octets[3:].decode("utf-8", "replace"), "utf-8-bom"
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return octets.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return octets.decode("utf-8", "replace"), "utf-8 (approché)"

import base64


def point_csv_decoder(entree):
    """Le point d'évolution `csv_decoder` (contrat 1.0) : les octets du fichier (base64) en entrée, le texte et l'encodage reconnu en sortie."""
    texte, enc = csv_decoder(base64.b64decode(entree["octets"]))
    return {"texte": texte, "encodage": enc}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_csv_decoder(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_csv_decoder.json ; corpus doré dans contrats/CN_csv_decoder.corpus.json (sorties de l'ancien code, données synthétiques).
