# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Notes : rendu Markdown d'une note (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #fd843a
# HÔTE CN    : CN_module.py · md_vers_html @1.0
# RÔLE       : rend le Markdown d'une note en HTML, suffisant pour lire et imprimer.
# MÉTHODE    : fonction pure : une passe ligne à ligne, un petit automate pour les listes ; un texte est toujours échappé avant d'être balisé.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=md_vers_html contrat=@1.0 version=EC0 empreinte=fd843a ▼▼▼
import re

RE_LIEN = re.compile(r"!?\[\[([^\]|]{1,160})(?:\|[^\]]*)?\]\]")

def echapper(t):
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def inline(t):
    t = echapper(t)
    t = RE_LIEN.sub(lambda m: "<b>%s</b>" % m.group(1), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)

def md_vers_html(md):
    """Rendu suffisant pour lire et imprimer : titres, listes, citations, gras, code. Un moteur Markdown complet serait un second moteur à maintenir."""
    out, liste = [], False
    for ligne in str(md or "").split("\n"):
        l = ligne.rstrip()
        m = re.match(r"^(#{1,6})\s+(.+)$", l)
        if m:
            if liste:
                out.append("</ul>")
                liste = False
            n = min(3, len(m.group(1)) + 1)
            out.append("<h%d>%s</h%d>" % (n, inline(m.group(2)), n))
            continue
        if re.match(r"^\s*[-*]\s+", l):
            if not liste:
                out.append("<ul>")
                liste = True
            out.append("<li>%s</li>" % inline(re.sub(r"^\s*[-*]\s+", "", l)))
            continue
        if liste:
            out.append("</ul>")
            liste = False
        if l.startswith(">"):
            out.append("<blockquote>%s</blockquote>" % inline(l.lstrip("> ")))
        elif l.strip():
            out.append("<p>%s</p>" % inline(l))
    if liste:
        out.append("</ul>")
    return "\n".join(out)

def point_md_vers_html(entree):
    """Le point d'évolution `md_vers_html` (contrat 1.0)."""
    return {"html": md_vers_html(entree["md"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_md_vers_html(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de notes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_md_vers_html.json ; corpus doré dans contrats/CN_md_vers_html.corpus.json (sorties de l'ancien code, données synthétiques).
