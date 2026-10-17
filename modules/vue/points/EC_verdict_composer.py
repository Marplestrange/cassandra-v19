# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Vue d'ensemble : composition du verdict (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : vue
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.2.0)  #a9d7c7
# HÔTE CN    : CN_composer.py · verdict.composer @1.0
# RÔLE       : transforme les relevés de toutes les sources en un verdict, des compteurs et les gestes à faire.
# MÉTHODE    : fonction pure ; une source muette n'est jamais « stable » ; la première panne est citée ; une machine attendue hors ligne est une panne.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=verdict.composer contrat=@1.0 version=EC0 empreinte=a9d7c7 ▼▼▼
"""La composition de la vue d'ensemble : une fonction PURE, des relevés (ou rien, quand une source se tait) -> le verdict et les compteurs.

Règles gardées de la V18 :
  - une source muette n'est pas un « tout va bien » : le verdict ne dit « stable » que si chaque source a répondu ;
  - une machine ATTENDUE hors ligne est une panne ; une intermittente ou une retirée n'en est pas une ;
  - un certificat à moins de 7 jours est une panne, à moins de 21 un point à regarder ;
  - le verdict cite le premier problème, et compte les autres.
"""
from __future__ import annotations

SEUIL_TLS_PANNE, SEUIL_TLS_REGARDER = 7, 21


def _aller(onglet, fn, arg, libelle):
    return {"type": "aller", "aller": [onglet, fn, arg], "label": libelle}


def _site18(x):
    """Un site, dans les mots que l'écran lit."""
    return {"domain": x.get("domaine"), "source": x.get("source"), "up": x.get("up"), "http_code": x.get("code"), "response_ms": x.get("ms"),
            "ssl_days": x.get("ssl_jours"), "sauvegarde": None, "scan": None, "fp_compte": x.get("proprietaire_panneau") or "", "comptes": x.get("comptes") or []}


def _quand(t):
    """« 2026-10-08 05:21:36 » -> « le 08/10 à 05:21 » : une date qu'on lit, pas qu'on déchiffre."""
    t = str(t or "")
    if len(t) >= 16 and t[4:5] == "-" and t[10:11] in (" ", "T"):
        return "le %s/%s à %s" % (t[8:10], t[5:7], t[11:16])
    return t


def _pluriel(n, mot):
    return "%d %s" % (n, mot if n == 1 else mot + "s")


def _composer(admin, compte, s, maintenant=""):
    """`s` : {'sites','flotte','metriques','sante','incidents','fil','notifs','autonomie'} — chaque valeur est le résultat d'une capacité, ou None si elle a échoué."""
    s = s or {}
    muettes = [k for k in ("sites", "flotte", "metriques", "incidents") if s.get(k) is None and (admin or k == "sites")]
    sites = sorted([_site18(x) for x in ((s.get("sites") or {}).get("sites") or [])], key=lambda x: (0 if x["up"] is False else 1, str(x["domain"] or "")))
    tombes = [x for x in sites if x["up"] is False]
    en_ligne = sum(1 for x in sites if x["up"] is True)
    tls = sorted((x["ssl_days"], x["domain"]) for x in sites if isinstance(x["ssl_days"], (int, float)))
    tls_min = tls[0] if tls else None
    notifs = ((s.get("notifs") or {}).get("notifications") or [])
    cloche = {"total": len(notifs), "lignes": [{"niveau": n.get("niveau") or "info", "titre": n.get("titre") or "", "id": n.get("id")} for n in notifs[:6]],
              "compteurs": {"critiques": sum(1 for n in notifs if n.get("niveau") == "critique")}}

    pannes, regarder = [], []
    for x in tombes:
        pannes.append({"titre": "%s ne répond pas%s" % (x["domain"], (" (code %s)" % x["http_code"]) if x.get("http_code") else ""), "geste": _aller("mysites", "stOpen", x["domain"], "Voir %s" % x["domain"])})
    if tls_min and tls_min[0] < SEUIL_TLS_PANNE:
        pannes.append({"titre": "certificat de %s : %d jour(s)" % (tls_min[1], tls_min[0]), "geste": _aller("mysites", "stOpen", tls_min[1], "Voir le site")})
    elif tls_min and tls_min[0] < SEUIL_TLS_REGARDER:
        regarder.append({"titre": "certificat de %s dans %d jours" % (tls_min[1], tls_min[0]), "geste": _aller("mysites", "stOpen", tls_min[1], "Voir le site")})

    machines, machines_hl, inc_ouverts, m, vivant = [], [], [], {}, False
    if admin:
        fl = s.get("flotte") or {}
        machines = [z for z in (fl.get("machines") or []) if isinstance(z, dict) and z.get("statut") == "attendue" and not z.get("disparue")]
        machines_hl = [z for z in machines if z.get("etat") == "erreur" or z.get("en_ligne") is False]
        for z in machines_hl:
            dc = str(z.get("dernier_contact") or "")
            pannes.append({"titre": "%s est attendue et ne répond plus%s" % (z.get("nom"), (" depuis %s" % _quand(dc)) if dc and dc != "maintenant" else ""), "geste": _aller("fleet", "flOpen", z.get("nom"), "Voir %s" % z.get("nom"))})
        inc = (s.get("incidents") or {}).get("incidents") or []
        inc_ouverts = [i for i in inc if str(i.get("statut") or "ouvert") == "ouvert"]
        for i in inc_ouverts[:3]:
            regarder.append({"titre": "incident ouvert : %s" % str(i.get("titre") or i.get("cle") or "?")[:80], "geste": _aller("proactive", "pfVue", "inc", "Voir les incidents")})
        m = s.get("metriques") or {}
        vivant = s.get("metriques") is not None
        disque = m.get("disk") if isinstance(m.get("disk"), (int, float)) else None
        if disque is not None and disque >= 95:
            pannes.append({"titre": "disque plein à %d %%" % round(disque), "geste": _aller("history", "mxOpen", "disk", "Voir le disque")})
        elif disque is not None and disque >= 85:
            regarder.append({"titre": "disque plein à %d %%" % round(disque), "geste": _aller("history", "mxOpen", "disk", "Voir le disque")})
        if not vivant:
            muettes = ["collecteur" if k == "metriques" else k for k in muettes]

    if pannes:
        niveau = "panne"
        t0 = pannes[0]["titre"]
        titre = t0 if "." in t0.split(" ")[0] else t0[0].upper() + t0[1:]          # jamais « B.fr » : un nom de domaine garde sa casse
        if len(pannes) > 1:
            titre = "%d pannes : %s%s" % (len(pannes), pannes[0]["titre"], (" et %s" % pannes[1]["titre"]) if len(pannes) == 2 else ", et %d autres" % (len(pannes) - 1))
        sous = "%s sur %d répond%s." % (_pluriel(en_ligne, "site"), len(sites), "ent" if en_ligne > 1 else "") + ((" %s à regarder derrière." % _pluriel(len(regarder), "point")) if regarder else "")
    elif muettes:
        niveau = "inconnu"
        titre = "Inconnu : %s se tai%s" % (", ".join(muettes[:3]), "sent" if len(muettes) > 1 else "t")
        sous = "Une source ne répond pas : le verdict ne dit pas « stable » tant qu'elle se tait. Les autres relevés restent lisibles plus bas."
    elif regarder:
        niveau = "regarder"
        titre = "Rien de cassé, %s à regarder" % _pluriel(len(regarder), "point")
        sous = "%s répondent. À regarder : %s." % (_pluriel(en_ligne, "site"), " ; ".join(r["titre"] for r in regarder[:3]))
    else:
        niveau = "stable"
        titre = "Rien ne demande un geste"
        sous = "%s répondent%s, certificats à jour." % (_pluriel(en_ligne, "site"), (", %d machine%s attendue%s en ligne" % (len(machines), "s" if len(machines) > 1 else "", "s" if len(machines) > 1 else "")) if machines else "")

    gestes = [p["geste"] for p in pannes[:2]] + [r["geste"] for r in regarder[:1]]
    gestes.append(_aller("overview", "vuAller", "gestes", "Tout ce qui demande un geste"))

    compteurs = []
    if admin:
        score = (s.get("sante") or {}).get("score")
        compteurs.append({"cle": "sante", "nom": "Santé", "valeur": score, "unite": "", "niveau": "inconnu" if score is None else ("panne" if score < 50 else "regarder" if score < 80 else "ok"),
                          "detail": "score du collecteur" if score is not None else "pas de score", "source": "collecteur" if vivant else "collecteur muet", "aller": ["history", "mxOpen", "fleet_up"]})
    compteurs.append({"cle": "sites", "nom": "Sites en ligne", "valeur": "%d / %d" % (en_ligne, len(sites)), "niveau": "panne" if tombes else ("ok" if sites else "inconnu"),
                      "detail": (tombes[0]["domain"] + " · ne répond pas") if tombes else ("tous répondent" if sites else "aucun site suivi"), "source": "sonde", "aller": ["mysites", "stFiltre", "tombes"]})
    compteurs.append({"cle": "tls", "nom": "TLS", "valeur": ("%d j" % tls_min[0]) if tls_min else "—",
                      "niveau": ("panne" if tls_min[0] < SEUIL_TLS_PANNE else "regarder" if tls_min[0] < SEUIL_TLS_REGARDER else "ok") if tls_min else "inconnu",
                      "detail": ("%s · %d autre%s" % (tls_min[1], len(tls) - 1, "s" if len(tls) > 2 else "")) if tls_min else "aucun certificat connu", "source": "sonde · 1 h", "aller": ["mysites", "stOpen", tls_min[1] if tls_min else None]})
    if admin:
        compteurs.append({"cle": "disque", "nom": "Disque", "valeur": ("%d %%" % round(disque)) if disque is not None else "—",
                          "niveau": "inconnu" if disque is None else ("panne" if disque >= 95 else "regarder" if disque >= 85 else "ok"),
                          "detail": "occupé", "source": "collecteur", "aller": ["history", "mxOpen", "disk"]})
        compteurs.append({"cle": "flotte", "nom": "Flotte attendue", "valeur": "%d / %d" % (len(machines) - len(machines_hl), len(machines)), "niveau": "panne" if machines_hl else ("ok" if machines else "inconnu"),
                          "detail": machines_hl[0].get("nom") if machines_hl else ("toutes en ligne" if machines else "aucune machine attendue"), "source": "présence", "aller": ["fleet", "flVue", "signaux"]})
        compteurs.append({"cle": "incidents", "nom": "Incidents ouverts", "valeur": len(inc_ouverts), "niveau": "regarder" if inc_ouverts else "ok",
                          "detail": str(inc_ouverts[0].get("titre") or inc_ouverts[0].get("cle") or "")[:60] if inc_ouverts else "aucun", "source": "proactivité", "aller": ["proactive", "pfVue", "inc"]})
    compteurs.append({"cle": "notifs", "nom": "Notifications", "valeur": cloche["total"], "niveau": "panne" if cloche["compteurs"]["critiques"] else ("regarder" if cloche["total"] else "ok"),
                      "detail": "ouvertes", "source": "notifications", "aller": ["bureau", None, None]})

    sortie = {"ok": True, "admin": bool(admin), "compte": compte, "niveau": niveau, "titre": titre, "sous_titre": sous, "gestes": gestes, "pannes": pannes, "regarder": regarder,
              "muettes": muettes, "compteurs": compteurs, "cloche": cloche, "sites": sites[:10], "n_sites": len(sites), "releve": maintenant}
    if admin:
        sortie["cassandra"] = {"collecteur": vivant, "palier": (s.get("autonomie") or {}).get("palier")}
        sortie["flotte"] = {"machines": [{"nom": z.get("nom"), "en_ligne": z.get("en_ligne"), "etat": z.get("etat"), "dernier_contact": z.get("dernier_contact"), "os": z.get("os")} for z in machines[:8]],
                            "compte": {}, "hors_ligne": [z.get("nom") for z in machines_hl]}
        sortie["fil"] = ((s.get("fil") or {}).get("fil") or [])[:8]
        sortie["machine"] = {"cpu": m.get("cpu"), "ram": m.get("ram"), "disk": m.get("disk"), "load_1m": m.get("load_1m"), "vivant": vivant, "source": "collecteur"}
        sortie["ages"] = {"sonde": None, "sites": None, "flotte": (s.get("flotte") or {}).get("releve"), "mesures": None, "machine": maintenant if vivant else None}
    return sortie


def composer(entree):
    """Le point d'évolution `verdict.composer` (contrat 1.0) : des DONNÉES en entrée (admin, compte, sources, quand), des DONNÉES en sortie (le verdict)."""
    return _composer(bool(entree["admin"]), entree.get("compte", ""), entree.get("sources") or {}, entree.get("quand", ""))
# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `composer(entree)` est le point d'évolution. L'évolution peut en remplacer le corps ; elle ne peut changer ni sa signature, ni les invariants du contrat
#      (une source muette n'est jamais « stable » ; une panne l'emporte sur le silence), ni importer autre chose que la bibliothèque standard pure.
# CN : appelée uniquement par la façade `composer` de CN_composer.py, par ctx.point("verdict.composer", ...) du noyau, qui valide le contrat à l'entrée et à la sortie.
# LIEN : contrat dans ../contrats/CN_verdict_composer.json ; corpus doré dans ../contrats/CN_verdict_composer.corpus.json (sorties de l'ancien composer, 17-10-2026).
