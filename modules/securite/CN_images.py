# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sécurité › En images
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.3.4  #6490db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sécurité › En images : la page de diagrammes. Fonction PURE : l'état de sécurité (analyse.etat) + les totaux du collecteur -> tout ce que dessine l'écran.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.4 empreinte=6490db ▼▼▼
"""Sécurité › En images : la page de diagrammes. Fonction PURE : l'état de sécurité (analyse.etat) + les totaux du collecteur -> tout ce que dessine l'écran.

Décision de Drisse (V18, 10-10, « garde tout ») : une page de diagrammes validée sur maquette. Tout vient de mesures déjà prises : l'état de l'onglet, les totaux d'attaques que tient le collecteur,
les résultats des outils, les mesures du Sensorium (courriel, box, tailnet). Rien n'est inventé : une source muette est une section vide et le dit (« manques »), jamais des zéros posés comme des mesures.
"""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta

PAYS = {"FR": "France", "US": "États-Unis", "CN": "Chine", "RU": "Russie", "KR": "Corée du Sud", "JP": "Japon", "DE": "Allemagne", "NL": "Pays-Bas", "GB": "Royaume-Uni", "IN": "Inde",
        "BR": "Brésil", "SG": "Singapour", "HK": "Hong Kong", "ID": "Indonésie", "CA": "Canada", "VN": "Viêt Nam", "TW": "Taïwan", "UA": "Ukraine", "IR": "Iran", "TR": "Turquie", "IT": "Italie",
        "ES": "Espagne", "PL": "Pologne", "RO": "Roumanie", "BG": "Bulgarie", "SE": "Suède", "FI": "Finlande", "LT": "Lituanie", "TH": "Thaïlande", "AR": "Argentine", "MX": "Mexique",
        "ZA": "Afrique du Sud", "AU": "Australie", "?": "inconnu"}
RESEAUX_DE_CONFIANCE = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "100.64.0.0/10", "::1/128", "fc00::/7", "fe80::/10", "fd7a:115c:a1e0::/48")
BOX = (("box.acces_distant", "Accès distant à la box"), ("box.upnp", "UPnP"), ("box.dmz", "DMZ"), ("box.ipv6", "Pare-feu IPv6"), ("box.wifi", "Wi-Fi"), ("box.redirections", "Redirections"),
       ("box.appareils", "Appareils"), ("dns_local", "DNS de la maison"), ("tailnet.appareils", "Tailnet"), ("tailnet.partage", "Partages du tailnet"))
NOMS_OUTILS = {"lynis": "Lynis", "trivy": "Trivy", "clamav": "ClamAV", "crowdsec": "CrowdSec"}


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


def de_confiance(adresse, extra=()):
    """de_confiance. Le calcul est un POINT D'ÉVOLUTION : points/EC_de_confiance.py."""
    return _appeler_point("de_confiance", {"adresse": adresse, "extra": extra})["valeur"]


def courriel_etats(valeur):
    """[spf, dkim, dmarc] : (niveau, mot) lus dans la mesure du Sensorium d'un domaine."""
    v = str(valeur or "")
    if "AUCUN SPF" in v or "OUVERT À TOUS" in v:
        spf = ("danger", "absent ou ouvert à tous")
    elif "n'y est pas" in v:
        spf = ("warn", "sans cette machine")
    else:
        spf = ("ok", "strict" if "strict" in v else "souple (~all)")
    i = v.find("DKIM : ")
    dk = v[i + 7:].split("·")[0] if i >= 0 else ""
    dkim = ("danger", "aucune signature") if (i < 0 or "aucune" in dk) else ("ok", "signé (%s)" % dk.strip()[:30])
    if "AUCUN DMARC" in v:
        dmarc = ("danger", "absent")
    elif "p=none" in v or "surveillance" in v:
        dmarc = ("warn", "surveillance seule")
    else:
        dmarc = ("ok", "rejette" if "rejette" in v else "quarantaine")
    return [spf, dkim, dmarc]


def composer(d, secu=None, certs=None, gestes=None, docker_ps=None, maintenant=None, confiance=()):
    """`d` : l'état de sécurité (analyse.etat). `secu` : le paquet du collecteur (None : il se tait). `certs` : [{"domaine", "jours"}] triés. `gestes` : le journal des gestes récents."""
    maintenant = maintenant or datetime.now()
    V = d.get("verdict") or {}
    secu_ok = isinstance(secu, dict)
    S = secu if secu_ok else {}
    diverses = {r["cle"]: r for r in S.get("diverses") or []}

    # les familles : celles du verdict, plus le courriel et la sauvegarde
    fams = [{"lib": f["lib"], "niveau": f["niveau"] or "ok", "dit": f["dit"]} for f in V.get("familles") or []]
    courriel = [{"domaine": k.split(".", 1)[1], "etats": courriel_etats(diverses[k]["valeur"])} for k in sorted(diverses) if k.startswith("domaine_courriel.")]
    verts = sum(1 for c in courriel for e in c["etats"] if e[0] == "ok")
    total_c = sum(len(c["etats"]) for c in courriel)
    if courriel:
        danger = any(e[0] == "danger" for c in courriel for e in c["etats"])
        fams.append({"lib": "Courriel", "niveau": "ok" if verts == total_c else ("panne" if danger and verts == 0 else "regarder"),
                     "dit": "%d contrôle%s sur %d au vert" % (verts, "s" if verts > 1 else "", total_c)})
    sv = S.get("sauvegarde")
    if sv:
        fams.append({"lib": "Sauvegarde", "niveau": "regarder" if sv.get("severity") == "warning" else "ok", "dit": str(sv.get("value") or "")[:80]})
    indice = max(0, 100 - sum(6 if f["niveau"] == "regarder" else 15 if f["niveau"] == "panne" else 0 for f in fams))

    # l'histoire des attaques
    heures = S.get("heures") or []
    jours7 = sorted({h["jour"] for h in heures} | {(maintenant - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)})[-7:]
    grille = {(h["jour"], h["heure"]): h["attaques"] for h in heures}
    sites = S.get("sites") or []
    attaquants = S.get("attaquants") or []

    # qui peut joindre quoi : le service sur l'anneau le plus lointain qui l'atteint
    E = d.get("exposition") or []
    anneaux = [{"lib": "Internet", "services": [s["nom"] for s in E if s["internet"] == "oui"]},
               {"lib": "Réseau local", "services": [s["nom"] for s in E if s["reseau"] and s["internet"] != "oui"]},
               {"lib": "Le parc et Tailscale", "services": [s["nom"] for s in E if not s["reseau"] and s["internet"] != "oui" and (s.get("parc") or s["tailscale"])]},
               {"lib": "La machine seule", "services": [s["nom"] for s in E if not s["reseau"] and s["internet"] != "oui" and not (s.get("parc") or s["tailscale"])]}]
    redir = d.get("box_redirections")
    ports_net = len(redir) if redir is not None else len(anneaux[0]["services"])

    O = d.get("outils") or {}

    def R(k):
        return (O.get(k) or {}).get("resultat") or {}
    cs, tv, ly, cl = R("crowdsec"), R("trivy"), R("lynis"), R("clamav")
    bannies = {str(b.get("ip") or "").split(":", 1)[-1] if str(b.get("ip") or "").startswith("Ip:") else str(b.get("ip") or "") for b in (cs.get("bannies") or [])}
    conteneurs = {}
    for ligne in (docker_ps or "").splitlines():
        image, _, nom = ligne.partition("|")
        conteneurs.setdefault(image, nom)
    f2b, maj = d.get("fail2ban") or {}, d.get("maj") or {}
    box = []
    for cle, lib in BOX:
        m = diverses.get(cle)
        if m:
            warn = (m.get("severite") or "") in ("warning", "critical") or (cle == "box.wifi" and "WPS actif" in str(m.get("valeur")))
            box.append({"lib": lib, "dit": str(m.get("valeur") or "")[:120], "niveau": "warn" if warn else "ok"})
    gardiens = [k for k, o in O.items() if o.get("installe")]
    certs = certs or []
    n_ips, total_ips = S.get("ips_n", 0), S.get("ips_total") or 1
    kpis = [
        {"v": str(ports_net), "lib": "port%s ouvert%s sur Internet" % ("s" if ports_net > 1 else "", "s" if ports_net > 1 else ""),
         "dit": " · ".join("%s %d" % (r["proto"].upper(), r["port"]) for r in (redir or [])) or "relevé sur la machine", "niveau": "ok"},
        {"v": str(n_ips) if secu_ok else "—", "lib": "adresses attaquantes", "dit": ("10 jours · les 10 plus actives font %d %%" % round(100 * (S.get("ips_top10") or 0) / total_ips)) if secu_ok else "le collecteur ne répond pas",
         "niveau": ("warn" if n_ips else "ok") if secu_ok else "warn"},
        {"v": ("%d j" % certs[0]["jours"]) if certs else "—", "lib": "avant le 1er certificat", "dit": certs[0]["domaine"] if certs else "aucun relevé",
         "niveau": "danger" if certs and certs[0]["jours"] < 7 else "warn" if certs and certs[0]["jours"] < 21 else "ok"},
        {"v": "%d / %d" % (verts, total_c) if total_c else "—", "lib": "contrôles courriel au vert", "dit": "SPF, DKIM, DMARC × %d domaine%s" % (len(courriel), "s" if len(courriel) > 1 else ""),
         "niveau": "ok" if verts == total_c else "warn"},
        {"v": str(maj.get("securite_en_attente", 0)), "lib": "correctif%s en attente" % ("s" if maj.get("securite_en_attente", 0) > 1 else ""),
         "dit": "correctifs automatiques chaque nuit" if maj.get("auto_actif") else "rien d'automatique", "niveau": "warn" if maj.get("securite_en_attente") else "ok"},
        {"v": "%d / %d" % (len(gardiens), len(O) or 4), "lib": "gardiens en service", "dit": ", ".join(NOMS_OUTILS.get(k, k) for k in gardiens) or "aucun installé",
         "niveau": "ok" if len(gardiens) == len(O) else "warn"}]
    jails = f2b.get("jails") or []
    return {
        "ok": True, "mesure": d.get("mesure"), "titre": V.get("titre"), "niveau": V.get("niveau"), "indice": indice, "familles": fams, "kpis": kpis,
        "jours": [{"jour": r["jour"], "sondes": r.get("s") or 0, "refus": r.get("r") or 0, "requetes": r.get("n") or 0, "robots": r.get("b") or 0} for r in S.get("jours") or []],
        "chaleur": {"jours": jours7, "grille": [[grille.get((j, h), 0) for h in range(24)] for j in jours7]},
        "chemins": [{"chemin": r["chemin"], "n": r["n"]} for r in S.get("chemins") or []],
        "robots": [{"site": r["site"], "n": r["n"], "part": round(100 * (r.get("b") or 0) / r["n"]) if r["n"] else 0, "noms": (S.get("robots") or {}).get(r["site"], []), "gere": False} for r in sites],
        "attaquants": [{"ip": a["ip"], "n": a["n"], "jours": a["jours"], "premier": a["premier"], "dernier": a["dernier"], "banni": a["ip"] in bannies, "confiance": de_confiance(a["ip"], confiance)} for a in attaquants],
        "gestes": gestes or [], "sites_geres": [],
        "anneaux": anneaux, "certs": certs, "courriel": courriel, "box": box,
        "pays": [{"pays": PAYS.get(p["pays"], p["pays"]), "n": p["n"]} for p in (cs.get("pays_7j") or [])],
        "scenarios": cs.get("scenarios_24h") or [],
        "trivy": [{"image": i.get("image"), "critiques": i.get("critiques", 0), "hautes": i.get("hautes", 0), "conteneur": conteneurs.get(i.get("image"), "")} for i in (tv.get("images") or []) if not i.get("erreur")],
        "trivy_accepte": (O.get("trivy") or {}).get("niveau") == "accepte",
        "gardiens": {"lynis": {"score": ly.get("score"), "avertissements": len(ly.get("avertissements") or []), "conseils": ly.get("suggestions_n", 0), "installe": (O.get("lynis") or {}).get("installe")},
                     "clamav": {"menaces": len(cl.get("infectes") or []), "duree": cl.get("duree_min"), "installe": (O.get("clamav") or {}).get("installe")},
                     "crowdsec": {"locales": cs.get("decisions_locales", 0), "communaute": cs.get("liste_communautaire", 0), "alertes": cs.get("alertes_24h", 0), "actif": bool(cs.get("moteur") and cs.get("videur")),
                                  "installe": (O.get("crowdsec") or {}).get("installe")},
                     "fail2ban": {"prisons": len(jails), "total": sum(j.get("total", 0) for j in jails), "bannies": sum(j.get("bannies", 0) for j in jails), "actif": bool(f2b.get("actif"))}},
        "manques": [] if secu_ok else ["collecteur"],
    }
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : de_confiance, courriel_etats, composer
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
