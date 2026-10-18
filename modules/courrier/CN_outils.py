# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les outils PURS du courrier
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : CN
# VERSION CN : 0.1.1  #495eb8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les outils PURS du courrier : aucun réseau, aucune base. Noms de dossiers IMAP (UTF-7 modifié), analyse des messages, nettoyage du HTML.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=495eb8 ▼▼▼
"""Les outils PURS du courrier : aucun réseau, aucune base. Noms de dossiers IMAP (UTF-7 modifié), analyse des messages, nettoyage du HTML.

Le nettoyage du HTML est une LISTE BLANCHE bâtie sur un vrai analyseur (html.parser), pas une série d'expressions régulières qui retirent ce qu'on
connaît : en V18 on retirait les balises dangereuses une à une, et tout ce qu'on n'avait pas pensé à retirer passait. Ici ne passe que ce qui est
nommé : balises de mise en forme, attributs de mise en forme, quelques propriétés de style, des adresses http, https et mailto. Un message ne gagne
jamais le droit d'exécuter quoi que ce soit ni de charger quoi que ce soit sans qu'on l'ait accepté.
"""
from __future__ import annotations

import base64
import email
import html
import re
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from datetime import timezone
from urllib.parse import urlsplit


# ------------------------------------------------------------------ noms de dossiers : UTF-7 modifié (RFC 3501)
_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


def utf7_decoder(s):
    """« envoy&AOk-s » -> « envoyés ». Le calcul est un POINT D'ÉVOLUTION : points/EC_utf7_decoder.py."""
    return _point("utf7_decoder", {"s": s})["valeur"]


def utf7_encoder(s):
    """« envoyés » -> « envoy&AOk-s » ; un « & » littéral devient « &- »."""
    sortie, tampon = [], ""

    def vider():
        nonlocal tampon
        if tampon:
            sortie.append("&" + base64.b64encode(tampon.encode("utf-16-be")).decode("ascii").rstrip("=").replace("/", ",") + "-")
            tampon = ""
    for ch in s or "":
        if ch == "&":
            vider()
            sortie.append("&-")
        elif 0x20 <= ord(ch) <= 0x7E:
            vider()
            sortie.append(ch)
        else:
            tampon += ch
    vider()
    return "".join(sortie)


def citer(nom):
    """Un nom de dossier utilisable en argument IMAP : cité s'il contient un espace ou un caractère spécial, sans quoi le serveur n'en voit que le premier mot."""
    if any(ch in nom for ch in ' "()[]{}%*\\'):
        return '"%s"' % nom.replace("\\", "\\\\").replace('"', '\\"')
    return nom


# ------------------------------------------------------------------ en-têtes
def decoder_entete(s):
    """decoder_entete. Le calcul est un POINT D'ÉVOLUTION : points/EC_decoder_entete.py."""
    return _point("decoder_entete", {"s": s})["valeur"]


def date_iso(brut):
    """Date normalisée et TRIABLE : les en-têtes Date arrivent dans une dizaine de formats et de fuseaux, trier la chaîne brute mélangerait janvier et juillet. Le calcul est un POINT D'ÉVOLUTION : points/EC_date_iso.py."""
    return _appeler_point("date_iso", {"brut": brut})["valeur"]


def adresse_parts(brut):
    """(nom affiché, adresse en minuscules) d'un en-tête From/To. Le calcul est un POINT D'ÉVOLUTION : points/EC_adresse_parts.py."""
    return tuple(_point("adresse_parts", {"brut": brut})["valeur"])          # un couple, comme avant : le tour JSON en fait une liste


def cle_de_fil(msg):
    """La racine des References, sinon In-Reply-To, sinon l'identifiant du message, sinon l'objet normalisé : l'objet seul regrouperait à tort tous les « Re: facture »."""
    refs = (msg.get("References") or "").split()
    if refs:
        return refs[0].strip()[:200]
    for entete in ("In-Reply-To", "Message-ID"):
        v = (msg.get(entete) or "").strip()
        if v:
            return v[:200]
    suj = re.sub(r"^\s*((re|fwd|tr|fw)\s*:\s*)+", "", decoder_entete(msg.get("Subject")), flags=re.I).strip().lower()
    return ("suj:" + suj)[:200] if suj else ""


ROLES_DRAPEAUX = (("\\drafts", "drafts"), ("\\sent", "sent"), ("\\trash", "trash"), ("\\junk", "junk"), ("\\archive", "archive"), ("\\all", "all"))
ROLES_NOMS = {"drafts": ("draft", "brouillon"), "sent": ("sent", "envoy"), "trash": ("trash", "corbeille", "deleted"), "junk": ("junk", "spam", "indésirable"), "archive": ("archive",)}


def role_drapeau(flags):
    """Le rôle ANNONCÉ PAR LE SERVEUR : la seule source qui fasse autorité, le nom n'est qu'une supposition."""
    for att, role in ROLES_DRAPEAUX:
        if att in (flags or ""):
            return role
    return ""


def role_du_dossier(nom, flags):
    """role_du_dossier. Le calcul est un POINT D'ÉVOLUTION : points/EC_role_du_dossier.py."""
    return _point("role_du_dossier", {"nom": nom, "flags": flags})["valeur"]


def roles_uniques(dossiers, appeler):
    """UN RÔLE N'APPARTIENT QU'À UN DOSSIER. Sur une boîte OVH, `Trash` porte le drapeau et `Deleted Messages` contient « deleted » : les deux décrochaient. Le calcul est un POINT D'ÉVOLUTION : points/EC_roles_uniques.py."""
    return appeler("roles_uniques", {"dossiers": dossiers})["valeur"]


def ensemble_uid(uids):
    """Un jeu d'UID pour une commande IMAP. Tout ce qui n'est pas un entier est écarté : une valeur libre concaténée dans une commande IMAP y injecterait une commande."""
    if isinstance(uids, (str, bytes, int)):
        uids = [uids]
    propres = []
    for u in uids or []:
        s = (u.decode() if isinstance(u, bytes) else str(u)).strip()
        if s.isdigit() and s not in propres:
            propres.append(s)
    return propres


# ------------------------------------------------------------------ classement : traiter, attente, technique
NOREPLY = re.compile(r"(no-?reply|ne-?pas-?repondre|donotreply|notification|mailer-daemon|postmaster|bounce|newsletter|no-?answer|automat|robot|daemon|support\+|billing@|facturation@)", re.I)
TECH_EXP = re.compile(r"(certbot|let'?s\s*encrypt|cron|logwatch|monit|nagios|zabbix|netdata|fail2ban|backup|borg|restic|rsnapshot|mdadm|smartd|unattended-upgrades|postmaster|mailer-daemon|no-?reply@|root@|admin@)", re.I)
TECH_SUJ = re.compile(r"(cron\s*<|certificat|certificate|expir|renew|sauvegarde|backup|disk\s*(space|usage)|s\.m\.a\.r\.t|raid|degraded|failed|échec|erreur\s*serveur|security\s*update|reboot required|anacron|logwatch)", re.I)


def motif_technique(m):
    """Motif technique reconnu, ou ''. Un signal sur l'EXPÉDITEUR est exigé : « sauvegarde » dans l'objet d'un client parle d'un devis, pas d'un serveur. Le calcul est un POINT D'ÉVOLUTION : points/EC_motif_technique.py."""
    return _point("motif_technique", {"m": m})["valeur"]


def etat_du_message(m):
    """« tech », « attente » ou « traiter ». Le calcul est un POINT D'ÉVOLUTION : points/EC_entetes.py (opération « etat »)."""
    return _point("entetes", {"op": "etat", "m": m})["valeur"]


# ------------------------------------------------------------------ corps et pièces jointes
def corps(msg):
    """(texte, html) séparés : aplatir le HTML en texte détruit la mise en forme d'une facture ou d'une lettre d'information."""
    texte, page = "", ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if str(part.get("Content-Disposition", "")).lower().startswith("attachment"):
            continue
        ct = part.get_content_type()
        if ct not in ("text/plain", "text/html"):
            continue
        try:
            charge = part.get_payload(decode=True)
            if not charge:
                continue
            dec = charge.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ct == "text/plain" and not texte:
            texte = dec
        elif ct == "text/html" and not page:
            page = dec
    if not texte and page:
        texte = html_en_texte(page)
    return texte.strip()[:20000], page.strip()[:400000]


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
    """Un HTML sans partie texte, aplati : les balises tombent, les entités reviennent en lettres, les blancs se resserrent. Le calcul est un POINT D'ÉVOLUTION : points/EC_html_en_texte.py."""
    return _point("html_en_texte", {"page": page})["valeur"]


def pieces_jointes(msg):
    out, idx = [], 0
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_maintype() == "multipart":
            continue
        disp = str(part.get("Content-Disposition", "") or "")
        nom = decoder_entete(part.get_filename()) if part.get_filename() else ""
        cid = (part.get("Content-ID") or "").strip("<>")
        if not nom and not disp.lower().startswith("attachment"):
            continue
        try:
            taille = len(part.get_payload(decode=True) or b"")
        except Exception:
            taille = 0
        out.append({"index": idx, "nom": nom or "piece-%d" % idx, "type": part.get_content_type(), "taille": taille, "inline": ("inline" in disp.lower()) and bool(cid), "cid": cid})
        idx += 1
    return out


def piece_numero(msg, index):
    """(nom, type, octets) de la n-ième pièce jointe, ou None."""
    i = 0
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_maintype() == "multipart":
            continue
        disp = str(part.get("Content-Disposition", "") or "")
        nom = part.get_filename()
        if not nom and not disp.lower().startswith("attachment"):
            continue
        if i == int(index):
            return (decoder_entete(nom) if nom else "piece-%d" % i), part.get_content_type(), part.get_payload(decode=True) or b""
        i += 1
    return None


# ------------------------------------------------------------------ le HTML, par liste blanche
BALISES = {"a", "abbr", "b", "big", "blockquote", "br", "caption", "center", "cite", "code", "col", "colgroup", "dd", "div", "dl", "dt", "em", "font", "h1", "h2", "h3", "h4", "h5",
           "h6", "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span", "strike", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "tt", "u", "ul"}
VIDES = {"br", "col", "hr", "img"}
A_JETER = {"script", "style", "iframe", "frame", "frameset", "object", "embed", "applet", "noscript", "form", "head", "title", "svg", "math", "template", "textarea", "select",
           "button", "audio", "video", "canvas", "dialog", "xmp", "plaintext", "listing", "noembed", "noframes"}
ATTRIBUTS = {"align", "valign", "width", "height", "colspan", "rowspan", "bgcolor", "color", "border", "cellpadding", "cellspacing", "dir", "lang", "title", "size", "face", "alt", "span", "nowrap"}
STYLES = {"color", "background-color", "font-size", "font-weight", "font-style", "font-family", "text-align", "text-decoration", "width", "height", "max-width", "min-width", "margin", "margin-top",
          "margin-bottom", "margin-left", "margin-right", "padding", "padding-top", "padding-bottom", "padding-left", "padding-right", "border", "border-top", "border-bottom", "border-left",
          "border-right", "border-collapse", "border-spacing", "line-height", "vertical-align", "white-space", "display", "text-transform", "letter-spacing"}
VALEUR_STYLE = re.compile(r"^[-#a-z0-9.,%()\s\"'!]+$", re.I)
EXT_FICHIER = {"pdf", "doc", "docx", "xls", "xlsx", "odt", "ods", "ppt", "pptx", "zip", "rar", "png", "jpg", "jpeg", "gif", "webp", "svg", "txt", "csv", "json", "xml", "html", "htm", "php", "asp",
               "aspx", "jsp", "mp3", "mp4", "mov", "avi", "wav", "ics", "vcf", "eml"}
DOMAINE_TXT = re.compile(r"(?i)\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b")
DATA_IMAGE = re.compile(r"^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=\s]+$", re.I)


def style_sur(valeur):
    """Les seules propriétés de mise en forme, avec des valeurs sans url(), sans expression, sans @import, sans accolade."""
    sortie = []
    for decl in (valeur or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        bas = val.lower()
        if prop in STYLES and VALEUR_STYLE.match(val) and not any(x in bas for x in ("url(", "expression", "javascript", "@import", "behavior", "binding", "\\")):
            sortie.append("%s:%s" % (prop, val))
    return ";".join(sortie)


def hote_de(url):
    try:
        h = (urlsplit(url).hostname or "").lower()
    except ValueError:
        h = ""
    return h[4:] if h.startswith("www.") else h


class _Nettoyeur(HTMLParser):
    def __init__(self, images):
        super().__init__(convert_charrefs=True)
        self.images, self.sortie, self.ignore, self.piles, self.lien = images, [], 0, [], None
        self.images_distantes = False

    def handle_starttag(self, tag, attrs):
        if tag in A_JETER:
            self.ignore += 1
            return
        if self.ignore or tag not in BALISES:
            return
        a = {k.lower(): (v or "") for k, v in attrs if k}
        if tag == "a":
            self.piles.append("a")
            url = html.unescape(a.get("href", "")).strip()
            bas = url.lower()
            if bas.startswith("mailto:"):
                self.sortie.append('<a href="%s">' % html.escape(url, quote=True))
                self.lien = None
            elif bas.startswith(("http://", "https://")):
                h = html.escape(url, quote=True)
                self.sortie.append('<a href="%s" target="_blank" rel="noopener noreferrer" title="%s">' % (h, h))
                self.lien = {"url": url, "texte": [], "ouvert": len(self.sortie)}
            else:
                self.sortie.append("<a>")                       # inerte : relatif, fichier, data:, javascript:, « # »
                self.lien = None
            return
        if tag == "img":
            self.sortie.append(self._image(a))
            return
        out = ["<", tag]
        for k, v in a.items():
            if k in ATTRIBUTS:
                out.append(' %s="%s"' % (k, html.escape(v, quote=True)))
            elif k == "style":
                s = style_sur(v)
                if s:
                    out.append(' style="%s"' % html.escape(s, quote=True))
        out.append(">")
        self.sortie.append("".join(out))
        if tag not in VIDES:
            self.piles.append(tag)

    def _image(self, a):
        src = html.unescape(a.get("src", "")).strip()
        bas = src.lower()
        attrs = ""
        for k in ("alt", "width", "height", "title"):
            if k in a:
                attrs += ' %s="%s"' % (k, html.escape(a[k], quote=True))
        def petit(v):
            return re.match(r"^\s*[01](px)?\s*$", v or "") is not None
        pixel = petit(a.get("width")) or petit(a.get("height")) or re.search(r"(width|height)\s*:\s*[01](px)?\s*(;|$)", a.get("style", ""), re.I) is not None
        if DATA_IMAGE.match(src):
            return "<img src=\"%s\"%s>" % (html.escape(src, quote=True), attrs)
        if bas.startswith("cid:"):
            return '<img data-cid="%s"%s>' % (html.escape(src[4:], quote=True), attrs)
        if bas.startswith(("http://", "https://")):
            self.images_distantes = True
            if pixel:
                return '<img data-tracker-src="%s"%s>' % (html.escape(src, quote=True), attrs)       # un pixel espion n'est JAMAIS chargé
            if self.images:
                return '<img src="%s"%s>' % (html.escape(src, quote=True), attrs)
            return '<img data-blocked-src="%s"%s>' % (html.escape(src, quote=True), attrs)
        return "<img%s>" % attrs

    def handle_endtag(self, tag):
        if tag in A_JETER:
            self.ignore = max(0, self.ignore - 1)
            return
        if self.ignore or tag not in BALISES or tag in VIDES:
            return
        if tag in self.piles:
            while self.piles:
                t = self.piles.pop()
                self.sortie.append("</%s>" % t)
                if t == "a" and self.lien:
                    self._avertir()
                if t == tag:
                    break

    def _avertir(self):
        """Un texte qui affiche un domaine pour mener ailleurs le dit juste après lui."""
        l, self.lien = self.lien, None
        vu = "".join(l["texte"])
        hote = hote_de(l["url"])
        m = next((x for x in DOMAINE_TXT.finditer(vu) if x.group(1).rsplit(".", 1)[-1].lower() not in EXT_FICHIER), None)
        if m and hote:
            dom = m.group(1).lower()
            dom = dom[4:] if dom.startswith("www.") else dom
            if not (hote == dom or hote.endswith("." + dom) or dom.endswith("." + hote)):
                self.sortie.append(' <span class="alerte-lien" title="Le texte du lien affiche %s ; il mène à %s">⚠ mène à %s</span>' % (html.escape(dom), html.escape(hote), html.escape(hote)))

    def handle_data(self, data):
        if self.ignore:
            return
        if self.lien is not None:
            self.lien["texte"].append(data)
        self.sortie.append(html.escape(data))

    def resultat(self):
        while self.piles:
            t = self.piles.pop()
            self.sortie.append("</%s>" % t)
            if t == "a" and self.lien:
                self._avertir()
        return "".join(self.sortie)[:400000]


def assainir_html(page, images=False):
    """(html sûr, des images distantes sont-elles présentes ?). Rien n'est exécuté ; aucune image distante n'est chargée sans l'accord de celui qui lit."""
    n = _Nettoyeur(images)
    try:
        n.feed(page or "")
        n.close()
    except Exception:
        return html.escape(html_en_texte(page or "")), False
    return n.resultat(), n.images_distantes
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : utf7_decoder, utf7_encoder, citer, decoder_entete, date_iso, adresse_parts, cle_de_fil, role_drapeau …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
