# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Certificats TLS
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : certificats
# ZONE       : CN
# VERSION CN : 0.3.2  #79f320
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Certificats TLS : la veille (ce que voient les visiteurs, le quota) et le cycle de vie (demande, validation, révocation, archivage, audit).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.2 empreinte=79f320 ▼▼▼
"""Certificats TLS : ce que les visiteurs voient, combien d'émissions il reste, et le cycle de vie d'un certificat.

Porté de la V18 (`_ssl_probe`, `ssl_quota_state`, `_ssl_quota_note`, `_cert_sonde_jours`), avec ses leçons :
  - le certificat SERVI sur le port 443 fait foi : la base d'un panneau peut affirmer n'importe quoi (« expires » y est une DURÉE de validité, pas une date) ;
  - « sans certificat » ne se dit que sur constat de la sonde : un hôte qu'on n'a pas pu joindre est INCONNU, il n'est pas « sans » ;
  - un certificat ÉCHU se lit quand même : la vérification de chaîne refuse la poignée de main, la sonde la refait SANS vérifier pour lire la date, puis dit pourquoi
    la vérification a refusé (sinon un échu passait pour « inconnu ») ;
  - Let's Encrypt compte cinq certificats par semaine et par domaine enregistré : on compte les émissions ABOUTIES, on inscrit aussi les échecs (ok=0) ;
  - on ne harcèle pas : une lecture par hôte et par heure, sans dépasser un budget de temps.
Le renouvellement se fait par le panneau (fastpanel.ssl_renouveler, qui émet fastpanel.certificat_renouvele) ; ce module tient le registre, la veille, les demandes et
le journal d'audit. Il ne détient jamais une clé privée.
"""
from __future__ import annotations

import re
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone

LIMITE_SEMAINE = 5
FENETRE_S = 7 * 24 * 3600
LIMITE_ECHECS_HEURE = 5
BUDGET_S = 540
RE_HOTE = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
SOURCES = {"fastpanel": "FastPanel", "importe": "Importé", "sonde": "Sondé seulement"}

# Les modèles : un profil prêt à l'emploi. « approbation » : une demande sur un hôte déjà suivi se valide d'office quand le modèle n'en exige pas.
MODELES = [
    {"id": "public", "nom": "Site public", "validite_j": 90, "algo": "ECDSA P-256", "max_sans": 5, "renouvelle_a_j": 30, "approbation": False, "autorite": "Let's Encrypt"},
    {"id": "wildcard", "nom": "Wildcard (DNS-01)", "validite_j": 90, "algo": "ECDSA P-256", "max_sans": 1, "renouvelle_a_j": 30, "approbation": True, "autorite": "Let's Encrypt"},
    {"id": "courrier", "nom": "Courrier (SAN mail/imap/smtp)", "validite_j": 365, "algo": "RSA 2048", "max_sans": 5, "renouvelle_a_j": 0, "approbation": True, "autorite": "Importée"},
]
AUTORITES = [
    {"id": "le", "nom": "Let's Encrypt", "voie": "FastPanel (PUT /api/certificates/{id}/renew/external)", "gestes": ["Renouveler", "Sonder"],
     "revocation": "Non prouvée par le panneau : Cassandra marque le certificat « révoqué » et le retire du suivi ; la révocation chez l'autorité reste à faire.",
     "quota": "5 émissions abouties par semaine et par domaine enregistré ; 5 validations ratées par heure et par hôte."},
    {"id": "importee", "nom": "Autorité importée", "voie": "Saisie du certificat public (PEM)", "gestes": ["Importer", "Sonder", "Rappeler"],
     "revocation": "Chez l'autorité : Cassandra consigne la révocation.", "quota": "Aucun : l'achat et le renouvellement se font chez l'autorité."},
]

_MOIS = {m: i + 1 for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))}


def nom_hote(d):
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def domaine_enregistre(domaine):
    p = [x for x in nom_hote(domaine).strip(".").split(".") if x]
    if len(p) < 2:
        return ""
    if len(p) >= 3 and len(p[-1]) == 2 and p[-2] in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def _date_openssl(t):
    """« Nov  2 12:00:00 2026 GMT » -> datetime naïf UTC."""
    m = re.match(r"\s*([A-Z][a-z]{2})\s+(\d+)\s+(\d+):(\d+):(\d+)\s+(\d{4})", t or "")
    if not m or m.group(1) not in _MOIS:
        raise ValueError("date illisible : %r" % t)
    return datetime(int(m.group(6)), _MOIS[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))


def lire_x509(donnees, forme="DER"):
    """Ce que dit un certificat (DER ou PEM), lu par `openssl x509` : {echeance_dt, emis, emetteur, noms, algo, empreinte}. Lève ValueError si ce n'est pas un certificat.
    Seul le certificat PUBLIC passe ici : jamais une clé."""
    try:
        p = subprocess.run(["openssl", "x509", "-inform", forme, "-noout", "-text", "-fingerprint", "-sha256"], input=donnees, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as ex:
        raise ValueError("openssl indisponible : %s" % ex)
    if p.returncode != 0:
        raise ValueError("ce n'est pas un certificat lisible")
    t = p.stdout.decode("utf-8", "replace")
    fin = re.search(r"Not After\s*:\s*(.+)", t)
    deb = re.search(r"Not Before\s*:\s*(.+)", t)
    if not fin:
        raise ValueError("le certificat ne dit pas son échéance")
    iss = re.search(r"Issuer:\s*(.+)", t)
    org = re.search(r"\bO\s*=\s*([^,/\n]+)", iss.group(1)) if iss else None
    cn = re.search(r"\bCN\s*=\s*([^,/\n]+)", iss.group(1)) if iss else None
    san = re.search(r"Subject Alternative Name:[^\n]*\n\s*([^\n]+)", t)
    noms = [x.strip()[4:] for x in (san.group(1).split(",") if san else []) if x.strip().startswith("DNS:")]
    if "rsaEncryption" in t:
        taille = re.search(r"Public-Key:\s*\((\d+) bit\)", t)
        algo = "RSA %s" % (taille.group(1) if taille else "?")
    elif "id-ecPublicKey" in t:
        courbe = re.search(r"ASN1 OID:\s*(\S+)", t)
        algo = {"prime256v1": "ECDSA P-256", "secp384r1": "ECDSA P-384", "secp521r1": "ECDSA P-521"}.get(courbe.group(1) if courbe else "", "ECDSA")
    else:
        algo = "inconnu"
    emp = re.search(r"Fingerprint=(.+)", t)
    return {"echeance_dt": _date_openssl(fin.group(1)), "emis": _date_openssl(deb.group(1)).strftime("%Y-%m-%d") if deb else "",
            "emetteur": ((org or cn).group(1).strip() if (org or cn) else ""), "noms": noms, "algo": algo, "empreinte": emp.group(1).strip() if emp else ""}


def _jours(fin):
    return (fin - datetime.now(timezone.utc).replace(tzinfo=None)).days


def lire_certificat(hote, delai):
    """{jours, echeance, emetteur, noms[, algo, empreinte, emis, verif]} du certificat servi, ou {erreur}. Jamais une exception.
    Un certificat que la chaîne refuse (échu, auto-signé, mauvais nom) se lit quand même : `verif` dit pourquoi la vérification a refusé."""
    verif = ""
    try:
        c = ssl.create_default_context()
        with socket.create_connection((hote, 443), timeout=delai) as brut:
            with c.wrap_socket(brut, server_hostname=hote) as tls:
                cert = tls.getpeercert()
                der = tls.getpeercert(binary_form=True)
    except ssl.SSLCertVerificationError as ex:
        verif = (getattr(ex, "verify_message", "") or str(ex))[:140]
        try:
            c = ssl.create_default_context()
            c.check_hostname = False
            c.verify_mode = ssl.CERT_NONE                       # la SEULE lecture sans vérification : pour DIRE ce que le serveur sert, jamais pour s'y fier
            with socket.create_connection((hote, 443), timeout=delai) as brut:
                with c.wrap_socket(brut, server_hostname=hote) as tls:
                    der = tls.getpeercert(binary_form=True)
            x = lire_x509(der)
        except (OSError, ssl.SSLError, ValueError) as ex2:
            return {"erreur": "certificat refusé (%s) et illisible : %s" % (verif, str(ex2)[:80])}
        return {"jours": _jours(x["echeance_dt"]), "echeance": x["echeance_dt"].strftime("%Y-%m-%d"), "emetteur": x["emetteur"], "noms": x["noms"], "algo": x["algo"],
                "empreinte": x["empreinte"], "emis": x["emis"], "verif": verif}
    except (OSError, ssl.SSLError, ValueError) as ex:
        return {"erreur": str(ex)[:160]}
    fin = cert.get("notAfter", "")
    if not fin:
        return {"erreur": "le certificat ne dit pas son échéance"}
    d = datetime.strptime(fin, "%b %d %H:%M:%S %Y %Z")
    emetteur = next((v for champ in (cert.get("issuer") or ()) for k, v in champ if k == "organizationName"), "")
    r = {"jours": _jours(d), "echeance": d.strftime("%Y-%m-%d"), "emetteur": emetteur, "noms": [v for k, v in (cert.get("subjectAltName") or ()) if k == "DNS"]}
    try:                                                         # l'algorithme et l'empreinte : un plus, jamais une raison d'échouer
        x = lire_x509(der)
        r.update(algo=x["algo"], empreinte=x["empreinte"], emis=x["emis"])
    except ValueError:
        pass
    return r


def lire_route(ctx, fonction: str, **args):
    """Une fonction de l'hébergement lue par le panneau détecté (Panel Detect), sans nommer le panneau. Aucune route : PermissionError, comme un module absent."""
    r = ctx.executer_lecture("paneldetect.route", fonction=fonction)
    cap = r.get("capacite") if isinstance(r, dict) else ""
    if not cap:
        raise PermissionError("aucun panneau d'hébergement ne sert « %s »" % fonction)
    return ctx.executer_lecture(cap, **args)


def brancher(ctx):
    db = ctx.stockage

    def entier(nom, defaut):
        try:
            return int(ctx.reglage(nom, "") or defaut)
        except (TypeError, ValueError):
            return defaut

    def metas():
        return {r["hote"]: r for r in db.lire("SELECT * FROM cert_meta")}

    def meta_poser(hote, **champs):
        """Une ligne par hôte, créée à la première écriture ; ne touche que les champs donnés."""
        db.ecrire("INSERT INTO cert_meta(hote, maj) VALUES (?, ?) ON CONFLICT(hote) DO NOTHING", (hote, time.time()))
        for k, v in champs.items():
            if k not in ("source", "etat_force", "auto", "site", "proprietaire", "note"):
                raise ValueError("champ inconnu : %s" % k)
            db.ecrire("UPDATE cert_meta SET %s=?, maj=? WHERE hote=?" % k, (v, time.time(), hote))

    def panneau():
        """Les domaines du panneau, ou None si le panneau ne répond pas (« injoignable » n'est pas « aucun site »)."""
        try:
            r = lire_route(ctx, "sites")
        except Exception:
            return None
        return r if isinstance(r, list) else None

    def hotes_panneau():
        return {nom_hote(x.get("domaine")) for x in (panneau() or []) if isinstance(x, dict)}

    def hotes():
        m = metas()
        s = hotes_panneau()
        s |= {nom_hote(x) for x in str(ctx.reglage("hotes", "") or "").split(",") if x.strip()}
        s |= {h for h, r in m.items() if r["source"] == "importe"}
        return sorted(x for x in s if x and "." in x and m.get(x, {}).get("etat_force", "") not in ("archive", "revoque"))

    def hotes_sonde():
        """Ce que la sonde lit : les hôtes suivis, plus les sites que le module Sites connaît hors du panneau (déclarés à la main, inscrits dans une fiche).
        Sites ne lit plus les certificats lui-même quand ce module est là : sans cela, un site déclaré n'aurait plus d'échéance nulle part.
        Ces hôtes ne comptent que pour la lecture : ils n'entrent pas dans `hotes()`, qui décide aussi des demandes."""
        s = set(hotes())
        try:
            r = ctx.executer_lecture("sites.vue")
        except Exception:
            r = None
        if isinstance(r, dict):
            m = metas()
            for x in r.get("sites") or []:
                h = nom_hote(x.get("domaine")) if isinstance(x, dict) else ""
                if h and "." in h and m.get(h, {}).get("etat_force", "") not in ("archive", "revoque"):
                    s.add(h)
        return sorted(s)

    # ------------------------------------------------------------------ qui voit quoi
    def admin():
        return (not ctx.compte) or ctx.est_admin(ctx.compte)

    def voit(hote, m):
        """Un administrateur (et la machine) voit tout ; un titulaire ne voit que les certificats qu'il a lui-même demandés ou qu'on lui a attribués."""
        return admin() or (m.get(hote, {}).get("proprietaire", "") == ctx.compte)

    def journaliser(action, objet, resultat="ok", note=""):
        db.ecrire("INSERT INTO audit(ts, acteur, type_acteur, action, objet, resultat, note) VALUES (?,?,?,?,?,?,?)",
                  (time.time(), ctx.compte or "noyau", ctx.acteur or "module", action, str(objet)[:200], resultat, str(note)[:300]))

    # ------------------------------------------------------------------ le quota
    def quota_de(domaine):
        d = domaine_enregistre(domaine) or nom_hote(domaine)
        depuis = time.time() - FENETRE_S
        lignes = db.lire("SELECT ts FROM emissions WHERE domaine=? AND ok=1 AND ts>=? ORDER BY ts", (d, depuis))
        utilisees = len(lignes)
        libre = ""
        if utilisees >= LIMITE_SEMAINE:
            libre = datetime.fromtimestamp(lignes[utilisees - LIMITE_SEMAINE]["ts"] + FENETRE_S).strftime("%d/%m/%Y à %H:%M")
        echecs = db.lire("SELECT COUNT(*) n FROM emissions WHERE domaine=? AND ok=0 AND ts>=?", (d, time.time() - 3600))[0]["n"]
        return {"domaine": d, "utilisees": utilisees, "restantes": max(0, LIMITE_SEMAINE - utilisees), "limite": LIMITE_SEMAINE, "bloque": utilisees >= LIMITE_SEMAINE, "libre_le": libre,
                "echecs_heure": echecs, "bloque_echecs": echecs >= LIMITE_ECHECS_HEURE}

    def emission(c):
        """Les émissions faites par le panneau, lues dans le journal du bus : on ne dépend pas de ce module (il peut être absent ou débranché),
        et un événement n'est compté qu'une fois grâce au curseur."""
        curseur = db.lire("SELECT valeur FROM curseur WHERE cle='evenement'")
        dernier = int(curseur[0]["valeur"]) if curseur else 0
        neufs = sorted((e for e in ctx.evenements("fastpanel.certificat_renouvele", 500) if e["id"] > dernier), key=lambda e: e["id"])
        for e in neufs:
            domaine = nom_hote((e.get("donnees") or {}).get("domaine") or "")
            if domaine:
                db.ecrire("INSERT INTO emissions(ts, domaine, ok, acteur) VALUES (?, ?, 1, ?)", (e["ts"], domaine_enregistre(domaine) or domaine, str(e.get("acteur") or "")[:60]))
                db.ecrire("INSERT INTO audit(ts, acteur, type_acteur, action, objet, resultat, note) VALUES (?,?,?,?,?,?,?)",
                          (e["ts"], str(e.get("compte") or "noyau")[:60], str(e.get("acteur") or "")[:30], "renouvellement", domaine, "ok", "preuve : la date d'émission a changé"))
                c.emettre("certificat.renouvele", objet=("certificat", domaine), donnees={"domaine": domaine})
        if neufs:
            db.ecrire("INSERT INTO curseur(cle, valeur) VALUES ('evenement', ?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (str(neufs[-1]["id"]),))

    # ------------------------------------------------------------------ la sonde
    def sonde(c):
        emission(c)
        debut = time.time()
        delai = entier("delai_s", 5)
        seuil = entier("seuil_jours", 21)
        m = metas()
        for h in hotes_sonde():
            if time.time() - debut > BUDGET_S:
                break
            r = lire_certificat(h, delai)
            avant = c.lire("certificat", h, portee=c.TOUT)
            if "erreur" in r:
                if m.get(h, {}).get("source") == "importe" and avant:
                    continue                                       # un certificat importé qui ne répond pas garde ce qu'on en sait : on ne l'efface pas
                c.poser("certificat", h, h, etat="inconnu", donnees={"erreur": r["erreur"], "mesure": time.time()})        # on n'a pas pu le lire : ni « sans », ni « ok »
                continue
            etat = "echu" if r["jours"] <= 0 else ("proche" if r["jours"] <= seuil else "valide")
            c.poser("certificat", h, h, etat=etat, donnees=dict(r, mesure=time.time(), erreur=""))
            if etat in ("echu", "proche") and (not avant or avant["etat"] not in ("echu", "proche")):
                c.emettre("certificat.proche_expiration", objet=("certificat", h), donnees={"hote": h, "jours": r["jours"], "echeance": r["echeance"]})

    def det_expiration(c):
        sortie = []
        m = metas()
        for o in c.lister(portee=c.TOUT, type="certificat"):
            if o["etat"] not in ("echu", "proche") or m.get(o["id"], {}).get("etat_force"):
                continue
            q = quota_de(o["id"])
            note = ("Quota Let's Encrypt épuisé pour %s : libre le %s." % (q["domaine"], q["libre_le"])) if q["bloque"] else ("Il reste %d émission(s) cette semaine pour %s." % (q["restantes"], q["domaine"]))
            sortie.append({"objet": ("certificat", o["id"]), "titre": ("Certificat échu : %s" % o["id"]) if o["etat"] == "echu" else "Certificat de %s : %d jour(s)" % (o["id"], o["donnees"]["jours"]),
                           "detail": "échéance le %s. %s" % (o["donnees"]["echeance"], note), "niveau": "critique" if o["etat"] == "echu" or o["donnees"]["jours"] < 7 else "attention"})
        return sortie

    # ------------------------------------------------------------------ lectures
    def relire(c, hote=""):
        h = nom_hote(hote)
        if "." not in h or " " in h or "/" in h:
            raise ValueError("nom d'hôte invalide")
        r = dict(lire_certificat(h, entier("delai_s", 5)), hote=h)
        journaliser("relire_expiration", h, "echec" if "erreur" in r else "ok", r.get("erreur", ""))
        return r

    def etat(c):
        return {"certificats": [dict(o["donnees"], hote=o["id"], etat=o["etat"]) for o in c.lister(portee=c.TOUT, type="certificat")]}

    def quota(c, domaine=""):
        if not nom_hote(domaine):
            raise ValueError("domaine requis")
        return quota_de(domaine)

    def seuil(c):
        """Le seuil d'alerte, tel que CE module le tient : les autres modules (fastpanel) le LISENT ici, ils n'en gardent pas un second."""
        return {"jours": entier("seuil_jours", 21), "defaut": 21}

    def fiche(o, m, sources_panneau):
        d = o["donnees"] or {}
        mm = m.get(o["id"], {})
        force = mm.get("etat_force", "")
        src = mm.get("source") or ("fastpanel" if o["id"] in sources_panneau else "sonde")
        return {"hote": o["id"], "etat": force or o["etat"], "etat_sonde": o["etat"], "jours": d.get("jours"), "echeance": d.get("echeance", ""), "emis": d.get("emis", ""),
                "emetteur": d.get("emetteur", ""), "noms": d.get("noms", []), "algo": d.get("algo", ""), "empreinte": d.get("empreinte", ""), "erreur": d.get("erreur", ""),
                "verif": d.get("verif", ""), "mesure": d.get("mesure", 0), "source": src, "auto": bool(mm.get("auto")), "site": mm.get("site", ""), "proprietaire": mm.get("proprietaire", ""),
                "note": mm.get("note", ""), "force": force}

    def lister(c, avec_archives=True):
        m = metas()
        p = panneau()
        sp = {nom_hote(x.get("domaine")) for x in (p or []) if isinstance(x, dict)}
        fiches = [fiche(o, m, sp) for o in c.lister(portee=c.TOUT, type="certificat") if voit(o["id"], m)]
        if not avec_archives:
            fiches = [f for f in fiches if f["force"] != "archive"]
        doms = sorted({domaine_enregistre(f["hote"]) for f in fiches if f["source"] == "fastpanel" and domaine_enregistre(f["hote"])})
        return {"certificats": sorted(fiches, key=lambda f: (f["jours"] is None, f["jours"] if f["jours"] is not None else 0)), "seuil": entier("seuil_jours", 21),
                "quotas": [quota_de(d) for d in doms], "panneau": {"joignable": p is not None, "sites": len(p or [])}, "admin": admin()}

    def lire(c, hote=""):
        h = nom_hote(hote)
        r = lister(c)
        f = next((x for x in r["certificats"] if x["hote"] == h), None)
        if f is None:
            raise ValueError("aucun certificat suivi pour %s (ou il n'est pas à vous)" % h)
        evts = db.lire("SELECT ts, acteur, type_acteur, action, resultat, note FROM audit WHERE objet=? ORDER BY ts DESC LIMIT 60", (h,))
        return {"certificat": f, "historique": evts, "quota": quota_de(h)}

    def _rsa_faible(algo):
        m = re.match(r"RSA (\d+)", algo or "")
        return bool(m) and int(m.group(1)) < 2048

    def synthese(c):
        r = lister(c, avec_archives=False)
        actifs = [f for f in r["certificats"] if f["force"] not in ("archive", "revoque")]
        n = lambda e: sum(1 for f in actifs if f["etat"] == e)       # noqa: E731
        tranches = [("Échus", lambda j: j <= 0), ("0–7 j", lambda j: 0 < j <= 7), ("8–21 j", lambda j: 7 < j <= 21), ("22–30 j", lambda j: 21 < j <= 30),
                    ("31–60 j", lambda j: 30 < j <= 60), ("61–90 j", lambda j: 60 < j <= 90), ("> 90 j", lambda j: j > 90)]
        histo = [{"tranche": t, "n": sum(1 for f in actifs if f["jours"] is not None and fn(f["jours"]))} for t, fn in tranches]
        criteres = [
            {"texte": "Aucun certificat échu", "ok": n("echu") == 0},
            {"texte": "Tous lisibles par la sonde", "ok": n("inconnu") == 0},
            {"texte": "Aucun sous le seuil sans renouvellement automatique", "ok": not [f for f in actifs if f["etat"] == "proche" and not f["auto"]]},
            {"texte": "Algorithme au moins RSA 2048 ou ECDSA P-256", "ok": not [f for f in actifs if _rsa_faible(f["algo"])]},
            {"texte": "La chaîne est acceptée par un client (vérification TLS)", "ok": not [f for f in actifs if f["verif"] and f["etat"] != "echu"]},
        ]
        return {"suivis": len(actifs), "valides": n("valide"), "proches": n("proche"), "echus": n("echu"), "inconnus": n("inconnu"), "seuil": r["seuil"], "histogramme": histo,
                "criteres": criteres, "conformite": int(round(100.0 * n("valide") / len(actifs))) if actifs else 0,
                "a_traiter": [f for f in actifs if f["etat"] in ("echu", "proche", "inconnu")], "quotas": r["quotas"], "panneau": r["panneau"]}

    def demandes(c):
        lignes = db.lire("SELECT * FROM demande ORDER BY id DESC LIMIT 300")
        if not admin():
            lignes = [x for x in lignes if x["demandeur"] == ctx.compte]
        return {"demandes": lignes, "modeles": MODELES, "moi": ctx.compte}

    def autorites(c):
        p = panneau()
        out = []
        for a in AUTORITES:
            etat_a = ("actif" if p is not None else "injoignable") if a["id"] == "le" else "actif"
            out.append(dict(a, etat=etat_a))
        return {"autorites": out}

    def modeles(c):
        return {"modeles": MODELES}

    def parametres(c):
        """Les trois réglages du module, tels que l'écran les montre (la liste des hôtes en une chaîne)."""
        return {"seuil_jours": entier("seuil_jours", 21), "delai_s": entier("delai_s", 5), "hotes": str(ctx.reglage("hotes", "") or "")}

    def cles(c):
        """Des métadonnées, JAMAIS la clé : algorithme, empreinte du certificat, emplacement, âge."""
        r = lister(c, avec_archives=False)
        lignes = []
        for f in r["certificats"]:
            if f["etat"] == "inconnu" or not f["algo"]:
                continue
            age = None
            if f["emis"]:
                try:
                    age = (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.strptime(f["emis"], "%Y-%m-%d")).days
                except ValueError:
                    age = None
            lignes.append({"hote": f["hote"], "algo": f["algo"], "empreinte": f["empreinte"], "age_j": age,
                           "emplacement": {"fastpanel": "sur le serveur, géré par le panneau", "importe": "chez le propriétaire de l'hôte (non connu)"}.get(f["source"], "inconnu (certificat sondé)")})
        return {"cles": lignes}

    def audit(c, resultat="", limite=200):
        req, args, cond = "SELECT * FROM audit", [], []
        if resultat:
            cond.append("resultat=?")
            args.append(resultat)
        if not admin():
            cond.append("acteur=?")
            args.append(ctx.compte)
        if cond:
            req += " WHERE " + " AND ".join(cond)
        return {"audit": db.lire(req + " ORDER BY ts DESC LIMIT %d" % max(1, min(int(limite), 1000)), tuple(args))}

    def rapport(c, nom=""):
        r = lister(c)
        if nom == "Conformité":
            s = synthese(c)
            return {"colonnes": ["Critère", "Conforme"], "lignes": [[k["texte"], "oui" if k["ok"] else "non"] for k in s["criteres"]] + [["Certificats valides", "%d %%" % s["conformite"]]]}
        if nom == "Échéances à 90 jours":
            return {"colonnes": ["Hôte", "État", "Jours", "Échéance", "Source"], "lignes": [[f["hote"], f["etat"], f["jours"], f["echeance"], SOURCES.get(f["source"], f["source"])]
                                                                                       for f in r["certificats"] if f["jours"] is not None and f["jours"] <= 90 and f["force"] not in ("archive", "revoque")]}
        if nom == "Quotas d'émission":
            return {"colonnes": ["Domaine", "Utilisées", "Limite", "Bloqué", "Libre le"], "lignes": [[q["domaine"], q["utilisees"], q["limite"], "oui" if q["bloque"] else "non", q["libre_le"]] for q in r["quotas"]]}
        if nom == "Inventaire complet":
            return {"colonnes": ["Hôte", "Noms", "État", "Jours", "Échéance", "Source", "Émetteur", "Algorithme", "Empreinte"],
                    "lignes": [[f["hote"], " ".join(f["noms"]), f["etat"], f["jours"], f["echeance"], SOURCES.get(f["source"], f["source"]), f["emetteur"], f["algo"], f["empreinte"]] for f in r["certificats"]]}
        raise ValueError("rapport inconnu : %s" % nom)

    def jours_de(quand):
        """Le nombre de jours entre aujourd'hui et une date « AAAA-MM-JJ… » (négatif : dépassée) ; None si elle est illisible."""
        s = str(quand or "")[:10]
        try:
            t = time.mktime(time.strptime(s, "%Y-%m-%d"))
        except Exception:
            return None
        return int(round((t - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) / 86400))

    def item_jour(bande, quoi, titre, detail="", nat="", ref="", poids=0, ou="", geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": nat, "ref": str(ref or ""), "poids": int(poids), "ou": ou,
                "geste": list(geste) if geste else None}

    def signal_jour(c):
        """Les certificats qui expirent dans les 21 jours (la machine : administrateur seulement)."""
        out = []
        m = metas()
        for o in c.lister(portee=c.TOUT, type="certificat"):
            if m.get(o["id"], {}).get("etat_force"):
                continue
            d = o["donnees"].get("jours")
            if not isinstance(d, int) or d < 0 or d > 21:
                continue
            out.append(item_jour("brule" if d <= 7 else "regarder", "ssl", o["id"], "Certificat : %d jour(s)." % d, "site", o["id"], 200 - d, "sites", geste=("Voir le site", "ouvrir")))
        return {"items": out}

    # ------------------------------------------------------------------ écritures : les demandes
    def _hote_valide(h):
        h = (h or "").strip().lower()
        if not RE_HOTE.match(h):
            raise ValueError("nom d'hôte invalide : %r" % h)
        return h

    def _modele(nom):
        mo = next((x for x in MODELES if x["id"] == nom or x["nom"] == nom), None)
        if mo is None:
            raise ValueError("modèle inconnu : %s" % nom)
        return mo

    def _demande(i):
        r = db.lire("SELECT * FROM demande WHERE id=?", (int(i),))
        if not r:
            raise ValueError("demande inconnue : %s" % i)
        return r[0]

    def _maj_demande(i, **ch):
        for k, v in ch.items():
            db.ecrire("UPDATE demande SET %s=?, maj=? WHERE id=?" % k, (v, time.time(), int(i)))

    def _proprio_ou_admin(d):
        if not (admin() or d["demandeur"] == ctx.compte):
            raise PermissionError("cette demande n'est pas la vôtre")

    def demander(c, hote="", sans=None, modele="public", site="", justification="", brouillon=False):
        h = _hote_valide(hote)
        liste = sans if isinstance(sans, list) else [x for x in re.split(r"[\s,]+", str(sans or "")) if x]
        liste = [_hote_valide(x) for x in liste]
        mo = _modele(modele)
        if len(liste) > 20:
            raise ValueError("20 noms alternatifs au plus")
        if (mo["id"] == "wildcard" or h.startswith("*.")) and not str(justification).strip():
            raise ValueError("un wildcard exige une justification")
        if h.startswith("*.") and mo["id"] != "wildcard":
            raise ValueError("un nom en « *. » demande le modèle Wildcard (validation DNS-01)")
        suivi = c.lire("certificat", h, portee=c.TOUT)
        if suivi and suivi["etat"] == "valide" and not metas().get(h, {}).get("etat_force"):
            raise ValueError("%s a déjà un certificat valide : utilisez « Renouveler »" % h)
        if db.lire("SELECT 1 FROM demande WHERE hote=? AND etat IN ('brouillon','a_valider','validee')", (h,)):
            raise ValueError("une demande est déjà en cours pour %s" % h)
        etat_d, valideur = "brouillon", ""
        if not brouillon:
            etat_d = "a_valider"
            if not mo["approbation"] and h in set(hotes()):
                etat_d, valideur = "validee", "automatique (modèle sans approbation, hôte déjà suivi)"
        i = db.ecrire("INSERT INTO demande(hote, sans, modele, site, demandeur, etat, valideur, justification, cree, maj) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (h, " ".join(liste), mo["id"], str(site)[:120], ctx.compte or "noyau", etat_d, valideur, str(justification)[:500], time.time(), time.time()))
        if ctx.compte:
            meta_poser(h, proprietaire=ctx.compte, site=str(site)[:120])
        journaliser("demande." + ("brouillon" if brouillon else "soumise"), h, "ok", "modèle %s" % mo["nom"])
        if etat_d == "a_valider":
            c.emettre("certificat.demande", objet=("certificat", h), donnees={"demande": i, "hote": h})
        return {"id": i, "etat": etat_d, "avant": ""}

    def demande_defaire(c, res):
        if res.get("avant"):
            _maj_demande(res["id"], etat=res["avant"])
        else:
            db.ecrire("DELETE FROM demande WHERE id=?", (res["id"],))

    def demande_prouve(c, res):
        return bool(db.lire("SELECT 1 FROM demande WHERE id=? AND etat=?", (res["id"], res["etat"])))

    def soumettre(c, id=0):
        d = _demande(id)
        _proprio_ou_admin(d)
        if d["etat"] != "brouillon":
            raise ValueError("seul un brouillon se soumet")
        mo = _modele(d["modele"])
        nouv, valideur = "a_valider", ""
        if not mo["approbation"] and d["hote"] in set(hotes()):
            nouv, valideur = "validee", "automatique (modèle sans approbation, hôte déjà suivi)"
        _maj_demande(d["id"], etat=nouv, valideur=valideur)
        journaliser("demande.soumise", d["hote"])
        if nouv == "a_valider":
            c.emettre("certificat.demande", objet=("certificat", d["hote"]), donnees={"demande": d["id"], "hote": d["hote"]})
        return {"id": d["id"], "avant": d["etat"], "etat": nouv}

    def valider(c, id=0):
        d = _demande(id)
        if d["etat"] != "a_valider":
            raise ValueError("cette demande n'attend pas de validation")
        if ctx.compte and d["demandeur"] == ctx.compte:
            journaliser("permission.refusee", d["hote"], "refus", "on ne valide pas sa propre demande")
            raise PermissionError("on ne valide pas sa propre demande")
        _maj_demande(d["id"], etat="validee", valideur=ctx.compte or "noyau")
        journaliser("demande.validee", d["hote"])
        c.emettre("certificat.valide", objet=("certificat", d["hote"]), donnees={"demande": d["id"], "hote": d["hote"]})
        return {"id": d["id"], "avant": "a_valider", "etat": "validee"}

    def refuser(c, id=0, motif=""):
        d = _demande(id)
        if d["etat"] != "a_valider":
            raise ValueError("cette demande n'attend pas de validation")
        if not str(motif).strip():
            raise ValueError("un motif est obligatoire : il est transmis au demandeur")
        if ctx.compte and d["demandeur"] == ctx.compte:
            raise PermissionError("on ne refuse pas sa propre demande")
        _maj_demande(d["id"], etat="refusee", valideur=ctx.compte or "noyau", motif=str(motif)[:300])
        journaliser("demande.refusee", d["hote"], "ok", str(motif)[:200])
        c.emettre("certificat.refuse", objet=("certificat", d["hote"]), donnees={"demande": d["id"], "hote": d["hote"]})
        return {"id": d["id"], "avant": "a_valider", "etat": "refusee"}

    def rouvrir(c, id=0):
        d = _demande(id)
        _proprio_ou_admin(d)
        if d["etat"] not in ("refusee", "echec"):
            raise ValueError("seule une demande refusée ou en échec se rouvre")
        _maj_demande(d["id"], etat="brouillon", motif="")
        journaliser("demande.rouverte", d["hote"])
        return {"id": d["id"], "avant": d["etat"], "etat": "brouillon"}

    def cloturer_demande(c, id=0, ok=True, motif=""):
        """Après le geste du panneau (fastpanel.ssl_renouveler) : la demande est émise, ou en échec avec son motif. Un échec s'inscrit au quota (ok=0)."""
        d = _demande(id)
        if d["etat"] != "validee":
            raise ValueError("seule une demande validée se clôt")
        nouv = "emise" if ok else "echec"
        _maj_demande(d["id"], etat=nouv, motif="" if ok else str(motif)[:300])
        if not ok:
            db.ecrire("INSERT INTO emissions(ts, domaine, ok, acteur, motif) VALUES (?,?,0,?,?)", (time.time(), domaine_enregistre(d["hote"]) or d["hote"], ctx.compte or "noyau", str(motif)[:200]))
        journaliser("emission", d["hote"], "ok" if ok else "echec", "" if ok else motif)
        if ok:
            c.emettre("certificat.emis", objet=("certificat", d["hote"]), donnees={"demande": d["id"], "hote": d["hote"]})
        return {"id": d["id"], "avant": "validee", "etat": nouv}

    def noter_echec(c, hote="", motif=""):
        """Un renouvellement qui a échoué (le panneau a refusé, ou la date d'émission n'a pas changé) : il ne s'inscrivait nulle part, alors que l'autorité compte aussi les ratés."""
        h = nom_hote(hote)
        if "." not in h:
            raise ValueError("nom d'hôte invalide")
        i = db.ecrire("INSERT INTO emissions(ts, domaine, ok, acteur, motif) VALUES (?,?,0,?,?)", (time.time(), domaine_enregistre(h) or h, ctx.compte or "noyau", str(motif)[:200]))
        journaliser("renouvellement", h, "echec", str(motif)[:200])
        return {"id": i, "hote": h}

    def echec_defaire(c, res):
        db.ecrire("DELETE FROM emissions WHERE id=?", (res["id"],))

    def echec_prouve(c, res):
        return bool(db.lire("SELECT 1 FROM emissions WHERE id=? AND ok=0", (res["id"],)))

    # ------------------------------------------------------------------ écritures : l'état d'un certificat
    def _suivi(h):
        h = nom_hote(h)
        if ctx.lire("certificat", h, portee=ctx.TOUT) is None or not voit(h, metas()):
            raise ValueError("aucun certificat suivi pour %s" % h)
        return h

    def revoquer(c, hote="", raison=""):
        h = _suivi(hote)
        m = metas().get(h, {})
        src = m.get("source") or ("fastpanel" if h in hotes_panneau() else "sonde")
        if src == "sonde":
            raise ValueError("%s n'est que sondé : il ne se révoque pas d'ici (il est géré ailleurs)" % h)
        if m.get("etat_force") == "revoque":
            raise ValueError("déjà révoqué")
        if not str(raison).strip():
            raise ValueError("une raison est obligatoire")
        avant = m.get("etat_force", "")
        meta_poser(h, etat_force="revoque", note=str(raison)[:200])
        journaliser("revocation", h, "ok", str(raison)[:200])
        c.emettre("certificat.revoque", objet=("certificat", h), donnees={"hote": h, "raison": str(raison)[:200]})
        return {"hote": h, "avant": avant, "etat": "revoque"}

    def archiver(c, hote=""):
        h = _suivi(hote)
        m = metas().get(h, {})
        etat_f = m.get("etat_force", "")
        if etat_f == "archive":
            raise ValueError("déjà archivé")
        if etat_f == "revoque":
            # un révoqué s'archive pour sortir de la liste : la raison de sa révocation suit, et le désarchivage le rend révoqué
            meta_poser(h, etat_force="archive", note="révoqué : " + m.get("note", ""))
        else:
            meta_poser(h, etat_force="archive")
        journaliser("archivage", h, "ok", "révoqué" if etat_f == "revoque" else "")
        c.emettre("certificat.archive", objet=("certificat", h), donnees={"hote": h})
        return {"hote": h, "avant": etat_f, "etat": "archive"}

    def desarchiver(c, hote=""):
        h = _suivi(hote)
        if metas().get(h, {}).get("etat_force") != "archive":
            raise ValueError("ce certificat n'est pas archivé")
        note = metas().get(h, {}).get("note", "")
        if note.startswith("révoqué : "):
            meta_poser(h, etat_force="revoque", note=note[len("révoqué : "):])
            apres = "revoque"
        else:
            meta_poser(h, etat_force="")
            apres = ""
        journaliser("desarchivage", h)
        return {"hote": h, "avant": "archive", "etat": apres}

    def force_defaire(c, res):
        meta_poser(res["hote"], etat_force=res["avant"])

    def force_prouve(c, res):
        return metas().get(res["hote"], {}).get("etat_force", "") == res["etat"]

    def importer(c, hote="", pem=""):
        """Le certificat PUBLIC d'un hôte dont le renouvellement se fait ailleurs. Une clé privée collée par erreur est refusée et n'est jamais lue."""
        h = _hote_valide(hote)
        texte = str(pem or "")
        if "PRIVATE KEY" in texte:
            raise ValueError("une clé privée a été collée : retirez-la. Cassandra refuse de la recevoir")
        if "BEGIN CERTIFICATE" not in texte:
            raise ValueError("ce texte n'est pas un certificat PEM")
        x = lire_x509(texte.encode("utf-8", "replace"), "PEM")
        if h not in x["noms"] and not any(n.startswith("*.") and h.endswith(n[1:]) and h.count(".") == n.count(".") for n in x["noms"]):
            raise ValueError("le certificat ne couvre pas %s (il couvre : %s)" % (h, ", ".join(x["noms"]) or "aucun nom"))
        j = _jours(x["echeance_dt"])
        etat_c = "echu" if j <= 0 else ("proche" if j <= entier("seuil_jours", 21) else "valide")
        c.poser("certificat", h, h, etat=etat_c, donnees={"jours": j, "echeance": x["echeance_dt"].strftime("%Y-%m-%d"), "emetteur": x["emetteur"], "noms": x["noms"], "algo": x["algo"],
                                                          "empreinte": x["empreinte"], "emis": x["emis"], "mesure": time.time(), "erreur": ""})
        meta_poser(h, source="importe", proprietaire=ctx.compte or "")
        journaliser("import", h, "ok", "certificat public (PEM)")
        return {"hote": h, "jours": j}

    def importer_defaire(c, res):
        ctx.retirer("certificat", res["hote"])
        db.ecrire("DELETE FROM cert_meta WHERE hote=?", (res["hote"],))

    def importer_prouve(c, res):
        return ctx.lire("certificat", res["hote"], portee=ctx.TOUT) is not None

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("sonde", sonde)
    c.moteur("emission", emission)
    c.detecteur("expiration_proche", det_expiration)
    for nom, f in (("relire_expiration", relire), ("etat", etat), ("signal_jour", signal_jour), ("quota", quota), ("seuil", seuil), ("lister", lister), ("lire", lire),
                   ("synthese", synthese), ("demandes", demandes), ("autorites", autorites), ("modeles", modeles), ("parametres", parametres), ("cles", cles), ("audit", audit), ("rapport", rapport)):
        c.implementer(nom, f)
    c.implementer("demander", demander, demande_prouve, demande_defaire, simuler=lambda x, hote="", **_: "créerait une demande de certificat pour %s" % hote)
    c.implementer("soumettre", soumettre, demande_prouve, demande_defaire, simuler=lambda x, id=0, **_: "soumettrait la demande %s" % id)
    c.implementer("valider", valider, demande_prouve, demande_defaire, simuler=lambda x, id=0, **_: "validerait la demande %s" % id)
    c.implementer("refuser", refuser, demande_prouve, demande_defaire, simuler=lambda x, id=0, **_: "refuserait la demande %s" % id)
    c.implementer("rouvrir", rouvrir, demande_prouve, demande_defaire, simuler=lambda x, id=0, **_: "rouvrirait la demande %s" % id)
    c.implementer("cloturer_demande", cloturer_demande, demande_prouve, demande_defaire, simuler=lambda x, id=0, **_: "clorait la demande %s" % id)
    c.implementer("noter_echec", noter_echec, echec_prouve, echec_defaire, simuler=lambda x, hote="", **_: "inscrirait un échec d'émission pour %s" % hote)
    c.implementer("revoquer", revoquer, force_prouve, force_defaire, simuler=lambda x, hote="", **_: "marquerait %s « révoqué » et le retirerait du suivi" % hote)
    c.implementer("archiver", archiver, force_prouve, force_defaire, simuler=lambda x, hote="", **_: "archiverait %s" % hote)
    c.implementer("desarchiver", desarchiver, force_prouve, force_defaire, simuler=lambda x, hote="", **_: "désarchiverait %s" % hote)
    c.implementer("importer", importer, importer_prouve, importer_defaire, simuler=lambda x, hote="", **_: "importerait le certificat public de %s" % hote)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : nom_hote, domaine_enregistre, lire_x509, lire_certificat, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
