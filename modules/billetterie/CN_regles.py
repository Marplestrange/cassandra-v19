# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #a4b6d2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les règles de chaque fiche (ce qui est permis d'enregistrer, et ce qui part avec).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a4b6d2 ▼▼▼
"""Billetterie : les règles de chaque fiche (ce qui est permis d'enregistrer, et ce qui part avec).

Un `preparer` reçoit la transaction, ce que l'appelant a donné (`d`, seulement les champs précisés) et la fiche d'avant (None si neuve) ;
il rend les colonnes à écrire, ou lève ValueError avec une phrase qui dit quoi corriger. Un champ non précisé garde sa valeur d'avant
(ou son défaut pour une fiche neuve) : on peut ne modifier qu'un seul champ.
L'argent est en CENTIMES entiers.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from . import CN_identifiants as ids

STATUTS_PERSONNE = ("Particulier", "Association", "Société")
ROLES_FORMULE = ("artiste", "cachet", "independant")
CONFS = ("assis", "debout")
ACHATS = ("general", "obligatoire", "libre")
CANAUX = ("boutique", "caisse", "revendeur")
_MAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ── petits outils ────────────────────────────────────────────────────────────
def pris(d, avant, nom, defaut=None):
    """La valeur d'un champ : celle qu'on donne, sinon celle d'avant, sinon le défaut."""
    if nom in d and d[nom] is not None:
        return d[nom]
    if avant is not None and nom in avant:
        return avant[nom]
    return defaut


def texte(v, n=200):
    return str(v if v is not None else "").strip()[:n]


def entier(v, nom, minimum=0, maximum=10 ** 9):
    try:
        x = int(v)
    except (TypeError, ValueError):
        raise ValueError("%s : un nombre entier est attendu" % nom)
    if isinstance(v, float) and v != x:
        raise ValueError("%s : un nombre entier est attendu (l'argent se donne en centimes)" % nom)
    if x < minimum or x > maximum:
        raise ValueError("%s : entre %d et %d" % (nom, minimum, maximum))
    return x


def booleen(v):
    return 1 if v in (1, True, "1", "oui", "true", "vrai") else 0


def jour(v, nom):
    v = texte(v, 10)
    if v == "":
        return ""
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError("%s : une date AAAA-MM-JJ est attendue" % nom)
    return v


def heure(v, nom):
    v = texte(v, 5)
    if v and not _HEURE.match(v):
        raise ValueError("%s : une heure HH:MM est attendue" % nom)
    return v


def requis(v, nom, n=120):
    v = texte(v, n)
    if not v:
        raise ValueError("%s est obligatoire" % nom)
    return v


def ligne(tx, table, ident):
    if ident in (None, "", 0):
        return None
    r = tx.execute("SELECT * FROM %s WHERE id = ?" % table, (int(ident),)).fetchone()
    return dict(r) if r else None


def mail_valide(v, nom="courriel"):
    v = texte(v, 160)
    if v and not _MAIL.match(v):
        raise ValueError("%s : adresse invalide" % nom)
    return v


# ── salles ───────────────────────────────────────────────────────────────────
def preparer_salle(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    assis, debout = entier(g("assis", 0), "capacité assise"), entier(g("debout", 0), "capacité debout")
    if assis + debout <= 0:
        raise ValueError("une salle a au moins une capacité (assise ou debout)")
    return {"nom": requis(g("nom"), "le nom de la salle"), "adresse": texte(g("adresse", ""), 300), "contact": texte(g("contact", ""), 200),
            "location": entier(g("location", 0), "prix de location"), "acompte": entier(g("acompte", 0), "acompte"), "caution": entier(g("caution", 0), "caution"),
            "assis": assis, "debout": debout, "pmr": booleen(g("pmr", 1)), "erp": texte(g("erp", ""), 120),
            "heure_fin": heure(g("heure_fin", ""), "heure limite de fin"), "bruit": texte(g("bruit", ""), 300), "alcool": texte(g("alcool", ""), 300),
            "age": texte(g("age", ""), 200), "equipements": texte(g("equipements", ""), 400), "annulation": texte(g("annulation", ""), 300), "assurance": texte(g("assurance", ""), 300)}


def dependances_salle(tx, s):
    n = tx.execute("SELECT COUNT(*) FROM evenements WHERE salle_id = ?", (s["id"],)).fetchone()[0]
    return ["utilisée par %d événement(s)" % n] if n else []


# ── formules ─────────────────────────────────────────────────────────────────
def preparer_formule(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    role = g("role")
    if avant and "role" in d and d["role"] is not None and d["role"] != avant["role"]:
        raise ValueError("le groupe d'une formule est définitif (une formule d'artiste ne devient jamais une formule de revendeur)")
    if role not in ROLES_FORMULE:
        raise ValueError("pour qui : artiste (vend lui-même), cachet (ne vend pas) ou independant (revendeur)")
    n = lambda k: entier(g(k, 0), k)
    forfait, com, fixe, palier_n, palier_com = n("forfait"), n("com"), n("fixe"), n("palier_n"), n("palier_com")
    if role == "artiste":
        fixe = palier_n = palier_com = 0
    elif role == "cachet":
        com = fixe = palier_n = palier_com = 0
    else:
        forfait = 0
    return {"nom": requis(g("nom"), "le nom de la formule"), "role": role, "forfait": forfait, "com": com, "fixe": fixe,
            "palier": 1 if (role == "independant" and palier_n > 0) else 0, "palier_n": palier_n, "palier_com": palier_com, "note": texte(g("note", ""), 300)}


def dependances_formule(tx, f):
    r = []
    for sql, lib in (("SELECT COUNT(*) FROM artistes WHERE formule_id = ?", "artiste(s)"), ("SELECT COUNT(*) FROM passages WHERE formule_id = ?", "passage(s)"),
                     ("SELECT COUNT(*) FROM affectations WHERE formule_id = ?", "affectation(s)")):
        n = tx.execute(sql, (f["id"],)).fetchone()[0]
        if n:
            r.append("%d %s" % (n, lib))
    return r


# ── artistes ─────────────────────────────────────────────────────────────────
def compte_libre(tx, table, compte, avant):
    """Un compte ne se lie qu'à UNE fiche de revendeur et qu'à UNE fiche d'artiste : son espace montre ses chiffres, pas ceux d'un autre."""
    compte = texte(compte, 160)
    if compte and tx.execute("SELECT 1 FROM %s WHERE compte = ? AND id <> ?" % table, (compte, avant["id"] if avant else 0)).fetchone():
        raise ValueError("ce compte est déjà lié à une autre fiche de %s" % ("revendeur" if table == "revendeurs" else "artiste"))
    return compte


def preparer_artiste(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    statut = g("statut", "Particulier")
    if statut not in STATUTS_PERSONNE:
        raise ValueError("statut : %s" % ", ".join(STATUTS_PERSONNE))
    fid = g("formule_id")
    f = ligne(tx, "formules", fid) if fid else None
    if fid and not f:
        raise ValueError("formule introuvable")
    if f and f["role"] == "independant":
        raise ValueError("une formule de revendeur ne va pas à un artiste : choisissez une formule d'artiste")
    vend = booleen(g("vend", 0))
    if vend and (not f or f["role"] != "artiste"):
        raise ValueError("un artiste qui vend a une formule d'artiste (forfait + commission), pas un cachet fixe")
    return {"scene": requis(g("scene"), "le nom de scène"), "legal": texte(g("legal", ""), 160), "genre": texte(g("genre", ""), 80), "statut": statut,
            "mail": mail_valide(g("mail", "")), "tel": texte(g("tel", ""), 40), "rider": texte(g("rider", ""), 600), "bio": texte(g("bio", ""), 600),
            "formule_id": f["id"] if f else None, "vend": vend, "siret": re.sub(r"\s", "", texte(g("siret", ""), 20)), "ape": texte(g("ape", ""), 8).upper(), "tva": texte(g("tva", ""), 20),
            "adresse": texte(g("adresse", ""), 200), "code_postal": texte(g("code_postal", ""), 12), "ville": texte(g("ville", ""), 80), "pays": texte(g("pays", "FR"), 2).upper() or "FR",
            "adhesion_fin": jour(g("adhesion_fin", ""), "fin d'adhésion"), "compte": compte_libre(tx, "artistes", g("compte", ""), avant)}


def apres_artiste(tx, avant, a):
    """Un artiste qui vend s'ajoute aux revendeurs (même fiche, deux casquettes) ; qui cesse de vendre voit son compte revendeur suspendu, jamais effacé (ses ventes restent)."""
    effets = {}
    if a["vend"]:
        r = ligne(tx, "revendeurs", a["revendeur_id"])
        if not r:
            ref = ids.nouvelle_ref(tx, "revendeur")
            code = ids.nouveau_code(tx, a["scene"])
            rid = tx.execute("INSERT INTO revendeurs(ref, code, nom, type, statut, mail, tel, artiste_id, compte, siret, ape, tva, adresse, code_postal, ville, pays) "
                             "VALUES (?,?,?,'artiste',?,?,?,?,?,?,?,?,?,?,?,?)",
                             (ref, code, a["scene"], a["statut"], a["mail"], a["tel"], a["id"], a["compte"], a["siret"], a["ape"], a["tva"], a["adresse"], a["code_postal"], a["ville"], a["pays"])).lastrowid
            tx.execute("UPDATE artistes SET revendeur_id = ? WHERE id = ?", (rid, a["id"]))
            effets["revendeur_cree"] = {"id": rid, "ref": ref, "code": code, "nom": a["scene"]}
        else:
            if not r["actif"]:
                effets["reactive"] = r["id"]
                tx.execute("UPDATE revendeurs SET actif = 1, suspendu_motif = '' WHERE id = ?", (r["id"],))
            tx.execute("UPDATE revendeurs SET nom = ?, mail = ?, tel = ?, compte = ? WHERE id = ?", (a["scene"], a["mail"], a["tel"], a["compte"], r["id"]))
    elif a["revendeur_id"]:
        r = ligne(tx, "revendeurs", a["revendeur_id"])
        if r and r["actif"]:
            effets["suspendu"] = r["id"]
            tx.execute("UPDATE revendeurs SET actif = 0, suspendu_motif = 'l''artiste ne vend plus' WHERE id = ?", (r["id"],))
    return effets


def defaire_apres_artiste(tx, e):
    if e.get("revendeur_cree"):
        c = e["revendeur_cree"]
        tx.execute("DELETE FROM revendeurs WHERE id = ?", (c["id"],))
        ids.retirer(tx, "revendeur", c["ref"], c["nom"], "créée puis annulée")
        ids.retirer(tx, "code", c["code"], c["nom"], "créée puis annulée")
    if e.get("reactive"):
        tx.execute("UPDATE revendeurs SET actif = 0 WHERE id = ?", (e["reactive"],))
    if e.get("suspendu"):
        tx.execute("UPDATE revendeurs SET actif = 1, suspendu_motif = '' WHERE id = ?", (e["suspendu"],))


def dependances_artiste(tx, a):
    out = []
    n = tx.execute("SELECT COUNT(*) FROM passages WHERE artiste_id = ?", (a["id"],)).fetchone()[0]
    if n:
        out.append("%d passage(s) au programme" % n)
    n = tx.execute("SELECT COUNT(*) FROM mouvements WHERE porteur = 'artiste' AND porteur_id = ?", (a["id"],)).fetchone()[0]
    if n:
        out.append("%d ligne(s) au registre (l'argent ne s'efface pas)" % n)
    return out


# ── revendeurs ───────────────────────────────────────────────────────────────
def preparer_revendeur(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    if avant is None:
        if g("type", "independant") != "independant":
            raise ValueError("un revendeur « artiste » naît de la fiche de l'artiste (case « vend lui-même »)")
    elif "type" in d and d["type"] is not None and d["type"] != avant["type"]:
        raise ValueError("le type d'un revendeur ne change pas")
    statut = g("statut", "Particulier")
    if statut not in STATUTS_PERSONNE:
        raise ValueError("statut : %s" % ", ".join(STATUTS_PERSONNE))
    nom = requis(g("nom"), "le nom du revendeur")
    vals = {"nom": nom, "statut": statut, "mail": mail_valide(g("mail", "")), "tel": texte(g("tel", ""), 40), "compte": compte_libre(tx, "revendeurs", g("compte", ""), avant),
            "siret": re.sub(r"\s", "", texte(g("siret", ""), 20)), "ape": texte(g("ape", ""), 8).upper(), "tva": texte(g("tva", ""), 20),
            "adresse": texte(g("adresse", ""), 200), "code_postal": texte(g("code_postal", ""), 12), "ville": texte(g("ville", ""), 80), "pays": texte(g("pays", "FR"), 2).upper() or "FR",
            "actif": booleen(g("actif", 1)), "suspendu_motif": texte(g("suspendu_motif", ""), 200)}
    if avant is None:
        vals["type"] = "independant"
        vals["code"] = ids.nouveau_code(tx, nom)
    return vals


def dependances_revendeur(tx, r):
    out = []
    if r["artiste_id"]:
        out.append("c'est la casquette vendeur de l'artiste : décochez « vend lui-même » sur sa fiche")
    n = tx.execute("SELECT COUNT(*) FROM affectations WHERE revendeur_id = ?", (r["id"],)).fetchone()[0]
    if n:
        out.append("%d affectation(s) à des événements" % n)
    n = tx.execute("SELECT COUNT(*) FROM commandes WHERE revendeur_id = ?", (r["id"],)).fetchone()[0]
    if n:
        out.append("%d commande(s) lui sont attribuées" % n)
    n = tx.execute("SELECT COUNT(*) FROM mouvements WHERE porteur = 'revendeur' AND porteur_id = ?", (r["id"],)).fetchone()[0]
    if n:
        out.append("%d ligne(s) au registre (l'argent ne s'efface pas)" % n)
    return out


# ── événements ───────────────────────────────────────────────────────────────
def capacite(salle, conf):
    return (salle["assis"] if conf == "assis" else salle["debout"]) if salle else 0


def preparer_evenement(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    conf = g("conf", "debout")
    if conf not in CONFS:
        raise ValueError("configuration : assis ou debout")
    sid = g("salle_id")
    s = ligne(tx, "salles", sid) if sid else None
    if sid and not s:
        raise ValueError("salle introuvable")
    if s and capacite(s, conf) <= 0:
        raise ValueError("la salle « %s » n'a pas de configuration %s" % (s["nom"], conf))
    achat = g("achat", "general")
    if achat not in ACHATS:
        raise ValueError("achat : %s" % ", ".join(ACHATS))
    fsc = g("frais_sans_compte")
    return {"nom": requis(g("nom"), "le nom de l'événement"), "date_iso": jour(g("date_iso", ""), "date"), "salle_id": s["id"] if s else None, "conf": conf,
            "quota": entier(g("quota", 0), "places mises en vente"), "prix": entier(g("prix", 0), "prix de la place"),
            "type": texte(g("type", ""), 40), "description": texte(g("description", ""), 4000), "accroche": texte(g("accroche", ""), 300), "tags": texte(g("tags", ""), 200),
            "portes": heure(g("portes", "19:30"), "ouverture des portes"), "debut": heure(g("debut", "20:00"), "début"), "fin": heure(g("fin", "23:00"), "fin"),
            "age": texte(g("age", "Tous publics"), 80), "responsable": texte(g("responsable", ""), 120), "projet_ref": texte(g("projet_ref", ""), 60), "achat": achat,
            "frais_sans_compte": None if fsc in (None, "") else entier(fsc, "frais sans compte"), "pause": entier(g("pause", 10), "pause entre les passages", 0, 120)}


def jauge(tx, evt):
    """Quota + invitations contre la capacité de la salle : la jauge de sécurité. Les invitations comptent, pas dans le chiffre d'affaires."""
    s = ligne(tx, "salles", evt["salle_id"])
    inv = tx.execute("SELECT COALESCE(SUM(quota),0) FROM invitations WHERE evenement_id = ?", (evt["id"],)).fetchone()[0]
    cap = capacite(s, evt["conf"])
    return {"capacite": cap, "quota": evt["quota"], "invitations": inv, "total": evt["quota"] + inv, "depasse": bool(s) and evt["quota"] + inv > cap}


def dependances_evenement(tx, e):
    out = []
    for table, lib in (("commandes", "commande(s)"), ("billets", "billet(s)"), ("types_billets", "type(s) de billet"), ("passages", "passage(s)"), ("affectations", "affectation(s)"), ("invitations", "invitation(s)")):
        n = tx.execute("SELECT COUNT(*) FROM %s WHERE evenement_id = ?" % table, (e["id"],)).fetchone()[0]
        if n:
            out.append("%d %s (à retirer d'abord)" % (n, lib))
    return out


# ── types de billets, passages, affectations, invitations ────────────────────
def _evenement(tx, d, avant):
    eid = pris(d, avant, "evenement_id")
    e = ligne(tx, "evenements", eid)
    if not e:
        raise ValueError("événement introuvable")
    return e


def preparer_type(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    e = _evenement(tx, d, avant)
    canaux = [c for c in str(g("canaux", "boutique,caisse,revendeur")).split(",") if c.strip()]
    mauvais = [c for c in canaux if c.strip() not in CANAUX]
    if mauvais or not canaux:
        raise ValueError("canaux : %s (au moins un)" % ", ".join(CANAUX))
    ouv, fer = jour(g("ouverture", ""), "ouverture de la vente"), jour(g("fermeture", ""), "fermeture de la vente")
    if ouv and fer and ouv > fer:
        raise ValueError("la vente ne peut pas fermer avant d'ouvrir")
    vals = {"evenement_id": e["id"], "nom": requis(g("nom"), "le nom du billet", 60), "description": texte(g("description", ""), 200), "prix": entier(g("prix", 0), "prix"),
            "quota": entier(g("quota", 0), "quota"), "entrees": entier(g("entrees", 1), "entrées par billet", 1, 20), "visible": booleen(g("visible", 1)),
            "ouverture": ouv, "fermeture": fer, "canaux": ",".join(c.strip() for c in canaux), "rang": entier(g("rang", 0), "rang", 0, 999),
            "porte": requis(g("porte", "Entrée principale"), "la porte", 40)}
    clash = tx.execute("SELECT id FROM types_billets WHERE evenement_id = ? AND nom = ? AND id <> ?", (e["id"], vals["nom"], (avant or {}).get("id", 0))).fetchone()
    if clash:
        raise ValueError("cet événement a déjà un billet « %s »" % vals["nom"])
    return vals


def dependances_type(tx, t):
    n = tx.execute("SELECT COUNT(*) FROM lignes_commande WHERE type_billet_id = ?", (t["id"],)).fetchone()[0]
    return ["%d ligne(s) de commande : il a déjà été vendu ou réservé" % n] if n else []


def preparer_passage(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    e = _evenement(tx, d, avant)
    a = ligne(tx, "artistes", g("artiste_id"))
    if not a:
        raise ValueError("artiste introuvable")
    fid = g("formule_id") or a["formule_id"]
    f = ligne(tx, "formules", fid) if fid else None
    if fid and not f:
        raise ValueError("formule introuvable")
    if f and f["role"] == "independant":
        raise ValueError("un passage prend une formule d'artiste, jamais une formule de revendeur")
    if avant is None and "ordre" not in d:
        ordre = tx.execute("SELECT COALESCE(MAX(ordre),0)+1 FROM passages WHERE evenement_id = ?", (e["id"],)).fetchone()[0]
    else:
        ordre = entier(g("ordre", 1), "ordre de passage", 1, 99)
    if tx.execute("SELECT 1 FROM passages WHERE evenement_id = ? AND ordre = ? AND id <> ?", (e["id"], ordre, (avant or {}).get("id", 0))).fetchone():
        raise ValueError("un passage a déjà le rang %d : réordonnez le programme" % ordre)
    return {"evenement_id": e["id"], "artiste_id": a["id"], "ordre": ordre, "duree": entier(g("duree", 30), "durée du passage (minutes)", 1, 600), "formule_id": f["id"] if f else None}


def preparer_affectation(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    e = _evenement(tx, d, avant)
    r = ligne(tx, "revendeurs", g("revendeur_id"))
    if not r:
        raise ValueError("revendeur introuvable")
    if r["type"] != "independant":
        raise ValueError("un artiste vendeur vend par son passage (sa formule d'artiste), pas par une affectation de revendeur")
    if not r["actif"]:
        raise ValueError("ce revendeur est suspendu")
    f = ligne(tx, "formules", g("formule_id"))
    if not f:
        raise ValueError("formule introuvable")
    if f["role"] != "independant":
        raise ValueError("un revendeur indépendant prend une formule de revendeur, jamais une formule d'artiste")
    return {"evenement_id": e["id"], "revendeur_id": r["id"], "formule_id": f["id"], "quota": entier(g("quota", 0), "quota de places")}


def preparer_invitation(tx, d, avant):
    g = lambda k, df=None: pris(d, avant, k, df)
    e = _evenement(tx, d, avant)
    quota = entier(g("quota", 0), "quota d'invitations")
    if avant and quota < avant["emises"]:
        raise ValueError("%d invitation(s) déjà émise(s) : le quota ne peut pas descendre en dessous" % avant["emises"])
    return {"evenement_id": e["id"], "categorie": requis(g("categorie"), "la catégorie d'invités", 60), "quota": quota, "porte": requis(g("porte", "Backstage"), "la porte", 40)}


def integrite(f):
    """Convertit une violation d'unicité SQLite en phrase."""
    def enveloppe(*a, **k):
        try:
            return f(*a, **k)
        except sqlite3.IntegrityError as ex:
            raise ValueError("doublon : %s" % str(ex).replace("UNIQUE constraint failed: ", "").replace("_", " "))
    return enveloppe
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : pris, texte, entier, booleen, jour, heure, requis, ligne …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
