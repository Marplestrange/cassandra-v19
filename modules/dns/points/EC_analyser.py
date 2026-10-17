# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dns : analyse d'une réponse DNS (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dns
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #2319a5
# HÔTE CN    : CN_module.py · analyser @1.0
# RÔLE       : décode une réponse DNS (RFC 1035) : suit la compression des noms et rend les enregistrements A, AAAA, NS, CNAME, MX, TXT et CAA sous forme normalisée.
# MÉTHODE    : fonction pure sur des octets : un lecteur de noms qui refuse les boucles, puis une lecture enregistrement par enregistrement ; une réponse illisible est rendue comme erreur.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=analyser contrat=@1.0 version=EC0 empreinte=2319a5 ▼▼▼
import ipaddress
import struct

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}

CODES = {v: k for k, v in TYPES.items()}

def lire_nom(b, i):
    """(nom, position suivante) en suivant la compression ; refuse les boucles."""
    parts, saut, fin = [], 0, None
    while True:
        if i >= len(b):
            raise ValueError("nom tronqué")
        n = b[i]
        if n == 0:
            i += 1
            break
        if n & 0xC0 == 0xC0:
            if i + 1 >= len(b):
                raise ValueError("pointeur tronqué")
            if fin is None:
                fin = i + 2
            i = ((n & 0x3F) << 8) | b[i + 1]
            saut += 1
            if saut > 20:
                raise ValueError("boucle de compression")
            continue
        parts.append(b[i + 1:i + 1 + n].decode("ascii", "replace"))
        i += 1 + n
    return ".".join(parts), (fin if fin is not None else i)

def analyser(b, ident):
    """Rend (code de réponse, tronqué, [(type, valeur normalisée)])."""
    if len(b) < 12:
        raise ValueError("réponse trop courte")
    rid, flags, qd, an, _, _ = struct.unpack(">HHHHHH", b[:12])
    if rid != ident:
        raise ValueError("identifiant inattendu")
    i = 12
    for _ in range(qd):
        _, i = lire_nom(b, i)
        i += 4
    sortie = []
    for _ in range(an):
        _, i = lire_nom(b, i)
        typ, _, _, ln = struct.unpack(">HHIH", b[i:i + 10])
        i += 10
        d = b[i:i + ln]
        if len(d) < ln:
            raise ValueError("donnée tronquée")
        t = CODES.get(typ)
        if t == "A" and ln == 4:
            sortie.append((t, str(ipaddress.IPv4Address(d))))
        elif t == "AAAA" and ln == 16:
            sortie.append((t, str(ipaddress.IPv6Address(d))))
        elif t in ("NS", "CNAME"):
            sortie.append((t, lire_nom(b, i)[0].lower()))
        elif t == "MX":
            sortie.append((t, "%d %s" % (struct.unpack(">H", d[:2])[0], lire_nom(b, i + 2)[0].lower())))
        elif t == "TXT":
            morceaux, j = [], 0
            while j < ln:
                n = d[j]
                morceaux.append(d[j + 1:j + 1 + n].decode("utf-8", "replace"))
                j += 1 + n
            sortie.append((t, "".join(morceaux)))
        elif t == "CAA" and ln >= 2:
            sortie.append((t, '%d %s "%s"' % (d[0], d[2:2 + d[1]].decode("ascii", "replace"), d[2 + d[1]:].decode("utf-8", "replace"))))
        i += ln
    return flags & 0x0F, bool(flags & 0x0200), sortie

import base64


def point_analyser(entree):
    """Le point d'évolution `analyser` (contrat 1.0) : une réponse DNS (base64) et l'identifiant attendu en entrée ; le code de réponse, le drapeau de troncature et les enregistrements en sortie.
    Une réponse illisible n'est pas une panne : elle est rendue dans « erreur », et la façade la relève en ValueError comme avant."""
    try:
        rcode, tronque, rr = analyser(base64.b64decode(entree["reponse"]), entree["ident"])
    except (ValueError, struct.error) as e:
        return {"erreur": str(e)}
    return {"rcode": rcode, "tronque": tronque, "enregistrements": [[t, v] for t, v in rr]}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_analyser(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dns (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_analyser.json ; corpus doré dans contrats/CN_analyser.corpus.json (sorties de l'ancien code, données synthétiques).
