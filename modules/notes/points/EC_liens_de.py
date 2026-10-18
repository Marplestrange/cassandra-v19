# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Notes : liens d'une note (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #490a86
# HÔTE CN    : CN_module.py · liens_de @1.0
# RÔLE       : repère les liens « [[…]] » d'une note : vers une autre note, vers un projet, ou une inclusion.
# MÉTHODE    : fonction pure : une expression régulière trouve chaque lien ; « type:référence » désigne autre chose qu'une note ; un « ! » devant fait une inclusion.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=liens_de contrat=@1.0 version=EC0 empreinte=490a86 ▼▼▼
import re

RE_LIEN = re.compile(r"!?\[\[([^\]|]{1,160})(?:\|[^\]]*)?\]\]")

def liens_de(corps):
    """`[[N-0011]]` vers une note, `[[projet:12]]` vers un projet ; `![[…]]` inclut au lieu de renvoyer ; `[[N-0012#^ancre]]` vise un paragraphe."""
    out = []
    for m in RE_LIEN.finditer(str(corps or "")):
        brut = m.group(1).strip()
        if ":" in brut:
            kind, _, ref = brut.partition(":")
            kind, ref = kind.strip().lower(), ref.strip()
        else:
            kind, ref = "note", brut
        out.append({"kind": kind, "ref": ref, "brut": brut, "inclus": m.group(0).startswith("!")})
    return out

def point_liens_de(entree):
    """Le point d'évolution `liens_de` (contrat 1.0)."""
    return {"valeur": liens_de(entree["corps"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_liens_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de notes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_liens_de.json ; corpus doré dans contrats/CN_liens_de.corpus.json (sorties de l'ancien code, données synthétiques).
