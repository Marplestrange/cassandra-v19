# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Flotte : lecture de la sonde d'une machine (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : flotte
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #ac84ee
# HÔTE CN    : CN_module.py · lire_sortie @1.0
# RÔLE       : transforme la sortie brute de la sonde d'une machine en mesures : une clé, une valeur dite en français, une gravité (info ou warning).
# MÉTHODE    : fonction pure : une ligne, une mesure ; une ligne illisible est ignorée, jamais une erreur ; les seuils de gravité (disque 90 %, mémoire 95 %, charge double des cœurs, 85 °C, 35 jours) sont ceux de la politique du dépôt.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=lire_sortie contrat=@1.0 version=EC0 empreinte=ac84ee ▼▼▼

def lire_sortie(sortie):
    """La sortie d'une sonde -> [(clé, valeur, gravité)] : disque.<point>, ram, uptime, charge, redemarrage_requis, services_en_echec, os, raid, temperature, mises_a_jour."""
    out = []
    for l in (sortie or "").replace("\r", "").splitlines():
        p = l.strip().split()
        if not p:
            continue
        k = p[0]
        try:
            if k == "DISK" and len(p) >= 4:
                pct = int(p[2].rstrip("%"))
                out.append(("disque.%s" % p[1], "%d%% utilisé, %s Go libres" % (pct, p[3]), "warning" if pct >= 90 else "info"))
            elif k == "RAM" and len(p) >= 2:
                v = int(float(p[1]))
                out.append(("ram", "%d%% utilisée" % v, "warning" if v >= 95 else "info"))
            elif k == "UP" and len(p) >= 2 and p[1].isdigit():
                sec = int(p[1])
                out.append(("uptime", ("%d j %d h" % (sec // 86400, sec % 86400 // 3600)) if sec >= 86400 else ("%d h %d min" % (sec // 3600, sec % 3600 // 60)), "info"))
            elif k == "LOAD" and len(p) >= 2:
                c = float(p[1])
                n = int(p[2]) if len(p) > 2 and p[2].isdigit() else 1
                out.append(("charge", "%.2f sur %d cœur%s" % (c, n, "s" if n > 1 else ""), "warning" if c > 2 * n else "info"))
            elif k == "REBOOT" and len(p) >= 2:
                out.append(("redemarrage_requis", p[1], "warning" if p[1] == "oui" else "info"))
            elif k == "FAILED":
                reste = l.strip()[6:].strip()
                noms = [x.strip() for x in (reste.split("|") if "|" in reste else reste.split()) if x.strip()]
                out.append(("services_en_echec", ("%d : %s" % (len(noms), ", ".join(noms))) if noms else "0", "warning" if noms else "info"))
            elif k == "OS" and len(p) >= 2:
                out.append(("os", " ".join(p[1:])[:80], "info"))
            elif k == "RAID" and len(p) >= 2:
                motif = " ".join(p[1:])
                out.append(("raid", motif, "warning" if "_" in motif else "info"))
            elif k == "TEMP" and len(p) >= 2:
                t = int(p[1]) / 1000.0
                out.append(("temperature", "%.0f °C" % t, "warning" if t >= 85 else "info"))
            elif k == "WU" and len(p) >= 2 and p[1].lstrip("-").isdigit():
                j = int(p[1])
                out.append(("mises_a_jour", "dernière mise à jour il y a %d j" % j, "warning" if j > 35 else "info"))
        except Exception:
            continue
    return out

def point_lire_sortie(entree):
    """Le point d'évolution `lire_sortie` (contrat 1.0)."""
    return {"valeur": lire_sortie(entree["sortie"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_lire_sortie(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de flotte (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_lire_sortie.json ; corpus doré dans contrats/CN_lire_sortie.corpus.json (sorties de l'ancien code, données synthétiques).
