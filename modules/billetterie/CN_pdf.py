# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #f320dd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le billet en PDF (une page par billet : l'événement, le lieu, l'heure, le nom, le numéro, le QR code et le code de contrôle à saisir à la main).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f320dd ▼▼▼
"""Billetterie : le billet en PDF (une page par billet : l'événement, le lieu, l'heure, le nom, le numéro, le QR code et le code de contrôle à saisir à la main).

Un PDF écrit à la main, sans bibliothèque : des textes (polices standard du PDF, jeu de caractères Windows) et le QR code dessiné en rectangles noirs (vectoriel : net à l'impression).
Le QR est le même que celui de l'écran (CN_qrcode.py). Rien n'est recopié d'ailleurs : tout ce que le billet dit vient de la base, au moment où on le demande.
"""
from __future__ import annotations

from . import CN_qrcode as qr

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
LARGEUR, HAUTEUR = 595, 842


def date_longue(iso: str) -> str:
    from datetime import date
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return "Date à venir"
    return "%s %d %s %d" % (JOURS[d.weekday()], d.day, MOIS[d.month - 1], d.year)


def _chaine(t) -> bytes:
    """Un texte pour un PDF : jeu de caractères Windows, parenthèses et barres échappées ; ce qui n'existe pas dans ce jeu devient « ? »."""
    b = str(t).encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _largeur_approx(t, taille, gras=False) -> float:
    return len(str(t)) * taille * (0.56 if gras else 0.5)


def _coupe(t, taille, largeur, gras=False):
    """Découpe un texte en lignes qui tiennent dans la largeur (approximation par le nombre de caractères : assez pour un titre d'événement)."""
    mots, lignes, cur = str(t).split(), [], ""
    for m in mots:
        essai = (cur + " " + m).strip()
        if _largeur_approx(essai, taille, gras) <= largeur or not cur:
            cur = essai
        else:
            lignes.append(cur)
            cur = m
    if cur:
        lignes.append(cur)
    return lignes or [""]


def _page(b: dict) -> bytes:
    """Le contenu graphique d'une page de billet."""
    c = []
    texte = lambda x, y, t, police="F1", taille=12, centre=False, gris=0.0: c.append(
        b"BT /%s %d Tf %.2f g %.1f %.1f Td (%s) Tj ET" % (police.encode(), taille, gris, (LARGEUR / 2 - _largeur_approx(t, taille, police == "F2") / 2) if centre else x, y, _chaine(t)))
    c.append(b"0.059 0.463 0.431 rg 0 %d %d 10 re f 0 g" % (HAUTEUR - 10, LARGEUR))                      # le liseré du haut, couleur de la marque
    texte(50, HAUTEUR - 60, (b.get("organisateur") or "Billetterie").upper(), "F2", 11, gris=0.35)
    texte(LARGEUR - 50 - _largeur_approx("BILLET", 11, True), HAUTEUR - 60, "BILLET", "F2", 11, gris=0.35)
    y = HAUTEUR - 110
    for ligne in _coupe(b["evenement"], 26, LARGEUR - 100, True):
        texte(50, y, ligne, "F2", 26)
        y -= 32
    y -= 6
    texte(50, y, date_longue(b.get("date", "")), "F1", 15)
    y -= 22
    horaires = "Portes %s · début %s" % (b.get("portes", ""), b.get("debut", "")) if b.get("portes") or b.get("debut") else ""
    if horaires:
        texte(50, y, horaires, "F1", 13, gris=0.25)
        y -= 20
    lieu = " — ".join(x for x in (b.get("lieu"), b.get("adresse")) if x)
    for ligne in _coupe(lieu, 12, LARGEUR - 100):
        if ligne:
            texte(50, y, ligne, "F1", 12, gris=0.25)
            y -= 17
    # le QR code, au centre, vectoriel
    mat = qr.matrice(b["qr"])
    marge, n = 4, len(mat)
    cote = 230.0
    pas = cote / (n + 2 * marge)
    x0, y0 = (LARGEUR - cote) / 2, y - 40 - cote
    c.append(b"1 g %.2f %.2f %.2f %.2f re f 0 g" % (x0, y0, cote, cote))
    for j, lig in enumerate(mat):
        i = 0
        while i < n:
            if lig[i]:
                k = 1
                while i + k < n and lig[i + k]:
                    k += 1
                c.append(b"%.3f %.3f %.3f %.3f re" % (x0 + (marge + i) * pas, y0 + cote - (marge + j + 1) * pas, k * pas, pas))
                i += k
            else:
                i += 1
    c.append(b"f")
    y = y0 - 34
    texte(0, y, b["numero"], "F3", 24, centre=True)
    y -= 22
    texte(0, y, "Code de contrôle : %s" % b["code"], "F4", 13, centre=True, gris=0.25)
    y -= 26
    if b.get("nom"):
        texte(0, y, b["nom"], "F2", 14, centre=True)
        y -= 20
    if b.get("type"):
        texte(0, y, b["type"], "F1", 12, centre=True, gris=0.25)
    texte(50, 70, "Présentez ce billet à l'entrée, sur téléphone ou imprimé. En cas de lecture impossible, l'ouvreur peut saisir le code de contrôle.", "F1", 9, gris=0.4)
    if b.get("contact"):
        texte(50, 56, "Une question : %s" % b["contact"], "F1", 9, gris=0.4)
    return b"\n".join(c)


def billets_pdf(billets: list) -> bytes:
    """Un PDF, une page par billet. `billets` : [{organisateur, evenement, date, portes, debut, lieu, adresse, nom, type, numero, code, qr, contact}]."""
    if not billets:
        raise ValueError("aucun billet à imprimer")
    objets = [b"<< /Type /Catalog /Pages 2 0 R >>", None]                    # 1 catalogue, 2 arbre des pages (rempli ensuite)
    polices = []
    for nom, base in (("F1", "Helvetica"), ("F2", "Helvetica-Bold"), ("F3", "Courier-Bold"), ("F4", "Courier")):
        objets.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % base.encode())
        polices.append(b"/%s %d 0 R" % (nom.encode(), len(objets)))
    ressources = b"<< /Font << %s >> >>" % b" ".join(polices)
    pages = []
    for b in billets:
        flux = _page(b)
        objets.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(flux), flux))
        cid = len(objets)
        objets.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources %s /Contents %d 0 R >>" % (LARGEUR, HAUTEUR, ressources, cid))
        pages.append(len(objets))
    objets[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % p for p in pages), len(pages))
    sortie, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objets, 1):
        offsets.append(len(sortie))
        sortie += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    for o in offsets:
        sortie += b"%010d 00000 n \n" % o
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, xref)
    return bytes(sortie)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : date_longue, _chaine, _largeur_approx, _coupe, _page, billets_pdf
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
