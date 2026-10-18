# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : Les ports publiés par Docker : ils passent par FORWARD, à côté d'INPUT — un pare-feu qui ne regarde qu'INPUT ne les voit pas (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #9425f5
# HÔTE CN    : CN_module.py · docker_publies @1.0
# RÔLE       : Les ports publiés par Docker : ils passent par FORWARD, à côté d'INPUT — un pare-feu qui ne regarde qu'INPUT ne les voit pas.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=docker_publies contrat=@1.0 version=EC0 empreinte=9425f5 ▼▼▼
import shlex

def _val(j, *opts):
    """(valeur, niée) de la première option trouvée parmi `opts`."""
    for i, x in enumerate(j):
        if x in opts and i + 1 < len(j):
            return j[i + 1], (i > 0 and j[i - 1] == "!")
    return "", False

def _ports(j):
    v, _ = _val(j, "--dport", "--dports", "--destination-port", "--destination-ports")
    out = []
    for morceau in v.split(","):
        a, _, b = morceau.partition(":")
        if a.isdigit():
            out.append((int(a), int(b) if b.isdigit() else int(a)))
    return out

def docker_publies(texte):
    """Les ports publiés par Docker : ils passent par FORWARD, à côté d'INPUT — un pare-feu qui ne regarde qu'INPUT ne les voit pas."""
    out = []
    for l in (texte or "").splitlines():
        try:
            j = shlex.split(l)
        except ValueError:
            continue
        if "DNAT" not in j:
            continue
        d, _ = _val(j, "-d")
        vers, _ = _val(j, "--to-destination")
        p, _ = _val(j, "-p")
        ports = _ports(j)
        out.append({"port": ports[0][0] if ports else 0, "proto": p or "tcp", "vers": vers, "portee": "machine" if d.startswith("127.") else ("tout" if not d else d)})
    return out

def point_docker_publies(entree):
    """Le point d'évolution `docker_publies` (contrat 1.0)."""
    return {"valeur": docker_publies(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_docker_publies(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_docker_publies.json ; corpus doré dans contrats/CN_docker_publies.corpus.json (sorties de l'ancien code, données synthétiques).
