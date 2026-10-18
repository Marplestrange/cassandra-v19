# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : aplatir un HTML (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #317ab4
# HÔTE CN    : CN_module.py · html_en_texte @1.0
# RÔLE       : rend en texte lisible un message qui n'a que du HTML : les balises tombent, les entités reviennent en lettres.
# MÉTHODE    : fonction pure : un petit analyseur HTML collecte le texte hors scripts et styles ; les blancs sont resserrés ; un HTML cassé se replie sur un retrait brutal des balises.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=html_en_texte contrat=@1.0 version=EC0 empreinte=317ab4 ▼▼▼
from html.parser import HTMLParser
import re

class _Texte(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sortie, self.ignore = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self.ignore += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.sortie.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title"):
            self.ignore = max(0, self.ignore - 1)
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.sortie.append("\n")

    def handle_data(self, data):
        if not self.ignore:
            self.sortie.append(data)

def html_en_texte(page):
    """Un HTML sans partie texte, aplati : les balises tombent, les entités reviennent en lettres, les blancs se resserrent."""
    if not page:
        return ""
    p = _Texte()
    try:
        p.feed(page)
        p.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", page)
    t = "".join(p.sortie)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()

def point_html_en_texte(entree):
    """Le point d'évolution `html_en_texte` (contrat 1.0)."""
    return {"valeur": html_en_texte(entree["page"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_html_en_texte(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_html_en_texte.json ; corpus doré dans contrats/CN_html_en_texte.corpus.json (sorties de l'ancien code, données synthétiques).
