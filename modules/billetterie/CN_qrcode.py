# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #7b5f78
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : un générateur de QR code (mode octets, correction M, versions 1 à 10), sans bibliothèque.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7b5f78 ▼▼▼
"""Billetterie : un générateur de QR code (mode octets, correction M, versions 1 à 10), sans bibliothèque.

C'est le même que celui de l'interface (interface/CN_qr.js), pour que le billet en PDF et le billet à l'écran portent le MÊME dessin : les deux sont vérifiés, module par module,
contre la bibliothèque de référence `qrcode` (8 masques, versions 1 à 10). `matrice(texte)` rend une liste de lignes de booléens (True = module noir).
"""
from __future__ import annotations

ECC = (0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)          # octets de correction par bloc (niveau M)
NB = (0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)                     # nombre de blocs


def _modules_bruts(v):
    r = (16 * v + 128) * v + 64
    if v >= 2:
        n = v // 7 + 2
        r -= (25 * n - 10) * n - 55
        if v >= 7:
            r -= 36
    return r


def _donnees(v):
    return _modules_bruts(v) // 8 - ECC[v] * NB[v]


_EXP, _LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i], _LOG[_x] = _x, _i
    _x <<= 1
    if _x & 256:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return _EXP[_LOG[a] + _LOG[b]] if a and b else 0


def _diviseur(deg):
    r = [0] * deg
    r[deg - 1] = 1
    racine = 1
    for _ in range(deg):
        for j in range(deg):
            r[j] = _mul(r[j], racine)
            if j + 1 < deg:
                r[j] ^= r[j + 1]
        racine = _mul(racine, 2)
    return r


def _reste(data, div):
    r = [0] * len(div)
    for b in data:
        f = b ^ r.pop(0)
        r.append(0)
        for i, c in enumerate(div):
            r[i] ^= _mul(c, f)
    return r


def _mots(data, v):
    bits = []

    def pousse(val, n):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)
    pousse(4, 4)
    pousse(len(data), 16 if v >= 10 else 8)
    for b in data:
        pousse(b, 8)
    cap = _donnees(v) * 8
    pousse(0, min(4, cap - len(bits)))
    pousse(0, (8 - len(bits) % 8) % 8)
    pad = 0xEC
    while len(bits) < cap:
        pousse(pad, 8)
        pad ^= 0xEC ^ 0x11
    return [sum(bits[i + k] << (7 - k) for k in range(8)) for i in range(0, len(bits), 8)]


def _entrelacer(data, v):
    nb, lecc, brut = NB[v], ECC[v], _modules_bruts(v) // 8
    courts, long_court, div, blocs, k = nb - brut % nb, brut // nb, _diviseur(ECC[v]), [], 0
    for i in range(nb):
        dat = data[k:k + long_court - lecc + (0 if i < courts else 1)]
        k += len(dat)
        e = _reste(dat, div)
        if i < courts:
            dat = dat + [0]
        blocs.append(dat + e)
    out = []
    for i in range(len(blocs[0])):
        for j, b in enumerate(blocs):
            if i != long_court - lecc or j >= courts:
                out.append(b[i])
    return out


_COND = (lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
         lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0, lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0)


def matrice(texte, masque=None):
    data = list(str(texte).encode("utf-8"))
    v = 1
    while v <= 10 and len(data) + (3 if v >= 10 else 2) > _donnees(v):
        v += 1
    if v > 10:
        raise ValueError("texte trop long pour un QR code")
    taille = v * 4 + 17
    mod = [[False] * taille for _ in range(taille)]
    fn = [[False] * taille for _ in range(taille)]

    def poser(x, y, noir):
        mod[y][x] = noir
        fn[y][x] = True

    for i in range(taille):
        poser(6, i, i % 2 == 0)
        poser(i, 6, i % 2 == 0)

    def repere(cx, cy):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                d, x, y = max(abs(dx), abs(dy)), cx + dx, cy + dy
                if 0 <= x < taille and 0 <= y < taille:
                    poser(x, y, d not in (2, 4))
    repere(3, 3)
    repere(taille - 4, 3)
    repere(3, taille - 4)
    pos = []
    if v > 1:
        n = v // 7 + 2
        pas = -(-(v * 4 + 4) // (n * 2 - 2)) * 2
        pos.append(6)
        p = taille - 7
        while len(pos) < n:
            pos.insert(1, p)
            p -= pas
    for i, cy in enumerate(pos):
        for j, cx in enumerate(pos):
            if (i == 0 and j == 0) or (i == 0 and j == len(pos) - 1) or (i == len(pos) - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    poser(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def format_(m):
        d = (0 << 3) | m
        r = d
        for _ in range(10):
            r = (r << 1) ^ ((r >> 9) * 0x537)
        bits = ((d << 10) | r) ^ 0x5412

        def b(i):
            return ((bits >> i) & 1) != 0
        for i in range(0, 6):
            poser(8, i, b(i))
        poser(8, 7, b(6))
        poser(8, 8, b(7))
        poser(7, 8, b(8))
        for i in range(9, 15):
            poser(14 - i, 8, b(i))
        for i in range(8):
            poser(taille - 1 - i, 8, b(i))
        for i in range(8, 15):
            poser(8, taille - 15 + i, b(i))
        poser(8, taille - 8, True)
    format_(0)
    if v >= 7:
        r = v
        for _ in range(12):
            r = (r << 1) ^ ((r >> 11) * 0x1F25)
        bits = (v << 12) | r
        for i in range(18):
            b, a, c = ((bits >> i) & 1) != 0, taille - 11 + i % 3, i // 3
            poser(a, c, b)
            poser(c, a, b)
    tout = _entrelacer(_mots(data, v), v)
    i, droite = 0, taille - 1
    while droite >= 1:
        if droite == 6:
            droite = 5
        for vert in range(taille):
            for j in range(2):
                x = droite - j
                haut = ((droite + 1) & 2) == 0
                y = taille - 1 - vert if haut else vert
                if not fn[y][x] and i < len(tout) * 8:
                    mod[y][x] = ((tout[i >> 3] >> (7 - (i & 7))) & 1) != 0
                    i += 1
        droite -= 2

    def masquer(m):
        for y in range(taille):
            for x in range(taille):
                if not fn[y][x] and _COND[m](x, y):
                    mod[y][x] = not mod[y][x]

    def penalite():
        p = 0
        for y in range(taille):
            for lig in (mod[y], [r[y] for r in mod]):
                run = 1
                for x in range(1, taille):
                    if lig[x] == lig[x - 1]:
                        run += 1
                        if run == 5:
                            p += 3
                        elif run > 5:
                            p += 1
                    else:
                        run = 1
        for y in range(taille - 1):
            for x in range(taille - 1):
                c = mod[y][x]
                if c == mod[y][x + 1] and c == mod[y + 1][x] and c == mod[y + 1][x + 1]:
                    p += 3
        sch = [True, False, True, True, True, False, True]
        for y in range(taille):
            for lig in (mod[y], [r[y] for r in mod]):
                for x in range(taille - 6):
                    if lig[x:x + 7] == sch:
                        av = x >= 4 and not any(lig[x - 4:x])
                        ap = x + 11 <= taille and not any(lig[x + 7:x + 11])
                        if av or ap:
                            p += 40
        noirs = sum(1 for r in mod for c in r if c)
        return p + (abs(noirs * 20 - taille * taille * 10) // (taille * taille)) * 10
    meilleur = masque
    if meilleur is None:
        mini = None
        for m in range(8):
            masquer(m)
            format_(m)
            pen = penalite()
            if mini is None or pen < mini:
                mini, meilleur = pen, m
            masquer(m)
    masquer(meilleur)
    format_(meilleur)
    return mod
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _modules_bruts, _donnees, _mul, _diviseur, _reste, _mots, _entrelacer, matrice
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
