# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les mesures de première classe du Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.2.6  #275970
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les mesures de première classe du Sensorium : capteurs enfichables, état à trois valeurs, clés suivies, vue minimale cloisonnée, relations, prévision, auto-observation.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.6 empreinte=275970 ▼▼▼
"""Les mesures de première classe du Sensorium : capteurs enfichables, état à trois valeurs, clés suivies, vue minimale cloisonnée, relations, prévision, auto-observation.

Tout vit dans la base du module (migration 004) : le noyau, le registre et le collecteur root ne changent pas. Le calcul de l'état est pur (CN_mesures_etat.py) ; ici, l'accès à la base,
les droits, les plafonds et les événements. Les fonctions prennent `ctx` : elles se testent avec le vrai contexte d'un noyau monté, ou avec un faux.
"""
import logging
import re
import threading
import time

try:
    from . import CN_mesures_etat as me
except ImportError:                        # chargé hors de son paquet (les bancs, l'outil de scellé) : le dossier est sur le chemin
    import CN_mesures_etat as me

log = logging.getLogger("sensorium.capteurs")

ESPACES_RESERVES = ("monde", "sensorium", "noyau", "systeme", "cassandra", "web")
RELATIONS = ("depend_de", "heberge_par", "certifie_par", "resout_par", "decrit")       # toutes se lisent « de DÉPEND DE vers » : si `vers` tombe, `de` est touché
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@\-]{0,159}$")
SYSTEMES = ("noyau", "cassandra")
MAX_CAPTEURS, MAX_CAPTEURS_PAR_COMPTE = 200, 50
MAX_SUIVIES, MAX_SUIVIES_PAR_SUIVEUR = 500, 50
MAX_LECTURES_PAR_APPEL = 50
MAX_LIENS, MAX_LIENS_PAR_AUTEUR = 5000, 500
PAS_LECTURE_S = 1.0                  # une clé ne reçoit pas plus d'une lecture par seconde
HISTO_PAS_S = 300                    # un point d'historique au plus toutes les cinq minutes (sauf changement d'état)
HISTO_MAX = 2000                     # par clé : environ sept jours à cinq minutes
HISTO_JOURS = 14
FRAICHEUR_MONDE_S = 180              # le monde est relu toutes les 60 s : trois relevés manqués = muet
_VERROU = threading.RLock()
_maintenant = time.time


def _db(ctx):
    return ctx.stockage


def compter(db, nom, n=1):
    db.ecrire("INSERT INTO sensorium_compteurs(nom, n, maj) VALUES (?,?,?) ON CONFLICT(nom) DO UPDATE SET n = n + excluded.n, maj = excluded.maj", (nom, int(n), _maintenant()))


def privilegie(ctx) -> bool:
    """Qui voit tout : un moteur (sans compte), un compte système, un administrateur. Les autres ne voient que ce qui leur est publié."""
    c = ctx.compte
    return (not c) or c in SYSTEMES or bool(ctx.est_admin(c))


def emetteur(ctx) -> str:
    """À qui est un capteur : au compte qui agit ; pour un moteur du noyau (compte commun « noyau »), au MODULE qui agit : « noyau:<module> ».
    Un compte est une adresse ou « agent:<nom> » : il ne peut pas s'appeler « noyau:… ». Sans appelant connu (ancien noyau), on reste à « noyau »."""
    c = ctx.compte
    a = getattr(ctx, "appelant", "") if c == "noyau" else ""
    return "noyau:%s" % a if a else c


def _un(db, sql, params=()):
    r = db.lire(sql, params)
    return dict(r[0]) if r else None


# ---------------------------------------------------------------------- l'état d'une clé
def etat_de(db, cle, maintenant):
    """(calcul, ligne de lecture ou None, capteur ou None, depuis) : l'état de la clé À CET INSTANT (une lecture muette se périme sans que personne n'écrive)."""
    lec = _un(db, "SELECT * FROM sensorium_lectures WHERE cle=?", (cle,))
    cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (cle,))
    if cap is None and cle.startswith("monde."):
        cap = {"fraicheur_s": FRAICHEUR_MONDE_S, "confiance_min": 0}
    calcul = me.calculer_etat(lec, cap, maintenant)
    if lec is None:
        return calcul, None, cap, None
    if calcul["etat"] == lec["etat"]:
        depuis = lec["depuis"]
    elif calcul["raison"].startswith("muette") and cap:
        depuis = min(maintenant, lec["recu_a"] + float(cap.get("fraicheur_s") or 300))
    else:
        depuis = maintenant
    return calcul, lec, cap, depuis


def _visibilite(db, cle):
    r = _un(db, "SELECT * FROM sensorium_visibilites WHERE cle=?", (cle,))
    return r["visibilite"] if r else "instance"


def _libelle(db, cle, cap):
    if cap and cap.get("libelle"):
        return cap["libelle"]
    r = _un(db, "SELECT libelle FROM sensorium_visibilites WHERE cle=?", (cle,))
    return (r or {}).get("libelle") or ""


def vue_de(ctx, pour=None):
    """(société, privilégié) selon lesquels on regarde. Par défaut : ceux de l'acte. `pour` ne sert qu'à un appelant PRIVILÉGIÉ (un moteur sans compte, qui travaille pour quelqu'un) : un compte
    (« ses » droits et sa société) ou « * » (personne : seules les mesures publiées pour toutes). Un appelant ordinaire qui passe `pour` n'en tire rien : jamais la vue d'un autre."""
    if pour is None or not privilegie(ctx):
        return ctx.societe, privilegie(ctx)
    pour = str(pour)
    if pour in ("", "*"):
        return "", False
    return ctx.societe_de(pour), pour in SYSTEMES or bool(ctx.est_admin(pour))


def _peut_voir(ctx, db, cle, vue=None) -> bool:
    societe, prive = vue if vue is not None else vue_de(ctx)
    return me.visible_pour(_visibilite(db, cle), societe, prive)


# ---------------------------------------------------------------------- l'enregistrement d'une lecture (capteur ou monde)
def _suiveur_prive(ctx, suiveur) -> bool:
    return suiveur in SYSTEMES or bool(ctx.est_admin(suiveur))


def _suiveur_a_le_droit(ctx, suiveur) -> bool:
    """Ce suiveur a-t-il ENCORE le droit `suivre` ? Un administrateur ou un compte système n'en a pas besoin. Au moindre doute (service des droits injoignable), non : mieux vaut se taire que parler à tort."""
    if _suiveur_prive(ctx, suiveur):
        return True
    try:
        return bool(ctx._intro["droits"].a(suiveur, "sensorium.suivre", ctx.societe_de(suiveur)))
    except Exception as ex:
        log.warning("droit suivre non vérifiable pour %s : %s", suiveur, ex)
        return False


def _suiveur_voit(ctx, db, suiveur, cle) -> bool:
    """Ce suiveur voit-il ENCORE cette clé (publication courante, société de son compte) et a-t-il toujours le droit de suivre ? Revérifié à chaque annonce : un suivi accepté hier ne vaut ni droit de regard ni droit de suivre aujourd'hui."""
    return _suiveur_a_le_droit(ctx, suiveur) and me.visible_pour(_visibilite(db, cle), ctx.societe_de(suiveur), _suiveur_prive(ctx, suiveur))


def _annoncer(ctx, db, cle, lec_etat, calcul, depuis, annonce, annonce_a, maintenant):
    """Annonce au bus un changement d'état d'une clé SUIVIE : un événement par suiveur (portée = son compte), fusionné si la clé a déjà parlé il y a moins de 30 s."""
    suiveurs = [r["suiveur"] for r in db.lire("SELECT suiveur FROM sensorium_suivies WHERE cle=?", (cle,))]
    avant = annonce or "inconnu"
    if not suiveurs:
        db.ecrire("UPDATE sensorium_lectures SET annonce=?, annonce_a=? WHERE cle=?", (lec_etat, annonce_a, cle))        # personne n'écoute : `avant` reste exact pour le premier qui suivra
        return
    if not me.doit_annoncer(avant, lec_etat, annonce_a, maintenant):
        if lec_etat != avant:
            compter(db, "evenements_fusionnes")
        return
    for s in suiveurs:
        if not _suiveur_voit(ctx, db, s, cle):                  # le suivi reste (il redevient actif si la clé est republiée), mais RIEN ne part vers qui ne voit plus la mesure
            compter(db, "evenements_masques")
            continue
        try:
            ctx.emettre("mesure.change", objet=("mesure", cle), compte=s,
                        donnees={"cle": cle, "avant": avant, "apres": lec_etat, "depuis": depuis, "suiveur": s,
                                 "raison": calcul["raison"] if _suiveur_prive(ctx, s) else me.raison_courte(calcul["raison"])})
        except Exception as ex:                                  # un bus en panne ne fait pas perdre la lecture
            log.warning("mesure.change non émis (%s) : %s", cle, ex)
            compter(db, "evenements_en_echec")
    db.ecrire("UPDATE sensorium_lectures SET annonce=?, annonce_a=? WHERE cle=?", (lec_etat, maintenant, cle))
    compter(db, "evenements_annonces", len(suiveurs))


def enregistrer(ctx, cle, valeur, gravite="", observe_a=None, confiance=None, detail="", cap=None, rapide=True):
    """Une lecture acceptée : dernière lecture, état, historique, annonce. Rend (None, calcul) ou (motif de refus, None)."""
    db, now = _db(ctx), _maintenant()
    with _VERROU:
        prev = _un(db, "SELECT * FROM sensorium_lectures WHERE cle=?", (cle,))
        if rapide and prev and 0 <= now - prev["recu_a"] < PAS_LECTURE_S:
            return "trop_vite", None
        num = me.nombre(valeur)
        txt = "" if num is not None else me.texte_sur(valeur, 200)
        if gravite not in me.GRAVITES:
            gravite = me.gravite_des_seuils(num, (cap or {}).get("alerte"), (cap or {}).get("critique"), (cap or {}).get("pire", "haut")) if cap else "ok"
        dec = me.decalage(observe_a, now)
        conf = me.confiance_effective(confiance, dec)
        lec = {"recu_a": now, "gravite": gravite, "confiance": conf}
        calcul = me.calculer_etat(lec, cap or {"fraicheur_s": FRAICHEUR_MONDE_S}, now)
        depuis = prev["depuis"] if prev and prev["etat"] == calcul["etat"] else now
        db.ecrire("INSERT INTO sensorium_lectures(cle, valeur_num, valeur_txt, gravite, observe_a, recu_a, confiance, decalage_s, detail, etat, raison, depuis, annonce, annonce_a) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cle) DO UPDATE SET valeur_num=excluded.valeur_num, valeur_txt=excluded.valeur_txt, gravite=excluded.gravite, "
                  "observe_a=excluded.observe_a, recu_a=excluded.recu_a, confiance=excluded.confiance, decalage_s=excluded.decalage_s, detail=excluded.detail, etat=excluded.etat, "
                  "raison=excluded.raison, depuis=excluded.depuis",
                  (cle, num, txt, gravite, me.nombre(observe_a), now, conf, dec, me.texte_sur(detail, 500), calcul["etat"], calcul["raison"], depuis,
                   prev["annonce"] if prev else "", prev["annonce_a"] if prev else None))
        if num is not None:
            dernier = _un(db, "SELECT t, etat FROM sensorium_historique WHERE cle=? ORDER BY id DESC LIMIT 1", (cle,))
            if dernier is None or now - dernier["t"] >= HISTO_PAS_S or dernier["etat"] != calcul["etat"]:
                db.ecrire("INSERT INTO sensorium_historique(cle, t, valeur, etat) VALUES (?,?,?,?)", (cle, now, num, calcul["etat"]))
                db.ecrire("DELETE FROM sensorium_historique WHERE cle=? AND id <= (SELECT id FROM sensorium_historique WHERE cle=? ORDER BY id DESC LIMIT 1 OFFSET ?)", (cle, cle, HISTO_MAX))
        compter(db, "lectures_acceptees")
        _annoncer(ctx, db, cle, calcul["etat"], calcul, depuis, prev["annonce"] if prev else "", prev["annonce_a"] if prev else None, now)
    return None, calcul


def ingerer_monde(ctx, rows):
    """Après chaque relève du monde réussie : les lignes dont la clé `monde.<wkey>` est suivie ou publiée deviennent des lectures. Collecteur muet : rien n'est écrit, les clés se périment."""
    db = _db(ctx)
    voulues = {r["cle"] for r in db.lire("SELECT cle FROM sensorium_suivies WHERE cle LIKE 'monde.%' UNION SELECT cle FROM sensorium_visibilites WHERE cle LIKE 'monde.%'")}
    compter(db, "releves_monde")
    db.ecrire("INSERT INTO sensorium_compteurs(nom, n, maj) VALUES ('dernier_monde', 0, ?) ON CONFLICT(nom) DO UPDATE SET maj=excluded.maj", (_maintenant(),))
    if not voulues:
        return 0
    n = 0
    for r in rows or []:
        cle = "monde." + str(r.get("wkey") or "")
        if cle not in voulues or not me.cle_valide(cle):
            continue
        sev = r.get("severity")
        g = "warning" if sev == "warning" else "critical" if sev == "critical" else "ok"
        refus, _ = enregistrer(ctx, cle, r.get("value"), g, detail=r.get("detail") or "", rapide=False)
        n += 0 if refus else 1
    return n


CLE_MOTEUR_WEB = "web.moteur"
LENT_MOTEUR_WEB_MS = 3000


def ingerer_sante_web(ctx, sante):
    """La santé du moteur de recherche (capacité `web.sante_moteur`, TIRÉE par le Sensorium : le module Web n'a aucun droit d'agir) devient la mesure `web.moteur`. Le Sensorium en est le seul émetteur
    (espace `web` réservé). Pas de module Web, pas de moteur configuré, réponse illisible : AUCUNE lecture (la mesure se périme en `inconnu`, jamais un « ok » inventé)."""
    if not isinstance(sante, dict) or not sante.get("configure"):
        return 0
    db = _db(ctx)
    cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (CLE_MOTEUR_WEB,))
    if cap is None:
        prop = _un(db, "SELECT proprietaire FROM sensorium_espaces WHERE espace='web'")
        if prop and prop["proprietaire"] != "sensorium":
            compter(db, "refus_espace_autre")
            return 0
        if not prop:
            db.ecrire("INSERT INTO sensorium_espaces(espace, proprietaire, cree_le) VALUES ('web', 'sensorium', ?)", (_maintenant(),))
        db.ecrire("INSERT INTO sensorium_capteurs(cle, espace, proprietaire, libelle, unite, fraicheur_s, alerte, critique, pire, confiance_min, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (CLE_MOTEUR_WEB, "web", "sensorium", "Moteur de recherche", "ms", 180, LENT_MOTEUR_WEB_MS, None, "haut", 0, _maintenant()))
        cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (CLE_MOTEUR_WEB,))
    ok = bool(sante.get("ok"))
    latence = me.nombre(sante.get("latence_ms")) if ok else None
    gravite = "critical" if not ok else ""                       # vide : les seuils du capteur jugent la latence
    refus, _ = enregistrer(ctx, CLE_MOTEUR_WEB, latence, gravite, detail=sante.get("motif") or "", cap=cap, rapide=False)
    return 0 if refus else 1


def tour_suivi(ctx):
    """Le moteur de fraîcheur : une clé suivie dont l'émetteur s'est tu passe à `inconnu` (et l'annonce) ; sans lui, un capteur muet ne ferait jamais d'événement. Purge l'historique ancien."""
    db, now = _db(ctx), _maintenant()
    n = 0
    with _VERROU:
        for r in db.lire("SELECT DISTINCT cle FROM sensorium_suivies"):
            cle = r["cle"]
            calcul, lec, cap, depuis = etat_de(db, cle, now)
            if lec is None:
                continue
            if calcul["etat"] != lec["etat"]:
                db.ecrire("UPDATE sensorium_lectures SET etat=?, raison=?, depuis=? WHERE cle=?", (calcul["etat"], calcul["raison"], depuis, cle))
                _annoncer(ctx, db, cle, calcul["etat"], calcul, depuis, lec["annonce"], lec["annonce_a"], now)
                n += 1
        db.ecrire("DELETE FROM sensorium_historique WHERE t < ?", (now - HISTO_JOURS * 86400,))
        compter(db, "tours_suivi")
        db.ecrire("INSERT INTO sensorium_compteurs(nom, n, maj) VALUES ('dernier_tour', 0, ?) ON CONFLICT(nom) DO UPDATE SET maj=excluded.maj", (now,))
    return n


# ---------------------------------------------------------------------- capteurs : déclarer, retirer, alimenter
def capteur_declarer(ctx, cle="", libelle="", unite="", fraicheur_s=300, alerte=None, critique=None, pire="haut", confiance_min=0):
    """Déclare (ou met à jour) un capteur. Ne lève JAMAIS pour une erreur de l'appelant : un échec répété ferait rétrograder la capacité pour tous ; le refus se dit dans la réponse."""
    db, qui = _db(ctx), emetteur(ctx)
    refus = lambda m: {"ok": False, "refuse": m, "cle": str(cle)[:120]}
    if not me.cle_valide(cle):
        return refus("clé illisible")
    esp = me.espace_de(cle)
    if not me.ESPACE.match(esp) or esp in ESPACES_RESERVES or "." not in cle:
        return refus("espace réservé ou clé sans espace (« espace.nom »)")
    f = me.nombre(fraicheur_s)
    if f is None or not 5 <= f <= 7 * 86400:
        return refus("fraîcheur attendue : de 5 s à 7 jours")
    if pire not in ("haut", "bas"):
        return refus("« pire » : haut ou bas")
    cm = me.nombre(confiance_min)
    if cm is None or not 0 <= cm <= 1:
        return refus("confiance minimale : de 0 à 1")
    a, c = (None if alerte is None else me.nombre(alerte)), (None if critique is None else me.nombre(critique))
    if (alerte is not None and a is None) or (critique is not None and c is None):
        return refus("seuils numériques")
    with _VERROU:
        prop = _un(db, "SELECT proprietaire FROM sensorium_espaces WHERE espace=?", (esp,))
        if prop and prop["proprietaire"] != qui:
            compter(db, "refus_espace_autre")
            return refus("cet espace appartient à un autre compte")
        deja = _un(db, "SELECT cle FROM sensorium_capteurs WHERE cle=?", (cle,))
        if not deja:
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_capteurs")[0]["n"] >= MAX_CAPTEURS:
                return refus("plafond atteint : %d capteurs" % MAX_CAPTEURS)
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_capteurs WHERE proprietaire=?", (qui,))[0]["n"] >= MAX_CAPTEURS_PAR_COMPTE:
                return refus("plafond atteint : %d capteurs par compte" % MAX_CAPTEURS_PAR_COMPTE)
        if not prop:
            db.ecrire("INSERT INTO sensorium_espaces(espace, proprietaire, cree_le) VALUES (?,?,?)", (esp, qui, _maintenant()))
        db.ecrire("INSERT INTO sensorium_capteurs(cle, espace, proprietaire, libelle, unite, fraicheur_s, alerte, critique, pire, confiance_min, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                  "ON CONFLICT(cle) DO UPDATE SET libelle=excluded.libelle, unite=excluded.unite, fraicheur_s=excluded.fraicheur_s, alerte=excluded.alerte, critique=excluded.critique, "
                  "pire=excluded.pire, confiance_min=excluded.confiance_min",
                  (cle, esp, qui, me.texte_sur(libelle, 120), me.texte_sur(unite, 20), int(f), a, c, pire, cm, _maintenant()))
    return {"ok": True, "cle": cle, "espace": esp, "nouveau": not deja, "espace_nouveau": not prop}


def declare_prouve(ctx, res):
    return (not res.get("ok")) or bool(_un(_db(ctx), "SELECT 1 AS x FROM sensorium_capteurs WHERE cle=?", (res["cle"],)))


def declare_defait(ctx, res):
    if res.get("ok") and res.get("nouveau"):
        db = _db(ctx)
        db.ecrire("DELETE FROM sensorium_capteurs WHERE cle=?", (res["cle"],))
        if res.get("espace_nouveau"):
            db.ecrire("DELETE FROM sensorium_espaces WHERE espace=?", (res["espace"],))


def capteur_retirer(ctx, cle=""):
    """Retire un capteur du compte qui le possède, avec sa lecture et son historique."""
    db = _db(ctx)
    with _VERROU:
        cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (str(cle),))
        if not cap or cap["proprietaire"] != emetteur(ctx):
            return {"ok": False, "refuse": "capteur inconnu ou d'un autre compte", "cle": str(cle)[:120]}
        db.ecrire("DELETE FROM sensorium_capteurs WHERE cle=?", (cap["cle"],))
        db.ecrire("DELETE FROM sensorium_lectures WHERE cle=?", (cap["cle"],))
        db.ecrire("DELETE FROM sensorium_historique WHERE cle=?", (cap["cle"],))
    return {"ok": True, "cle": cap["cle"], "avant": cap}


def retire_prouve(ctx, res):
    return (not res.get("ok")) or not _un(_db(ctx), "SELECT 1 AS x FROM sensorium_capteurs WHERE cle=?", (res["cle"],))


def retire_defait(ctx, res):
    a = res.get("avant")
    if a:
        _db(ctx).ecrire("INSERT OR REPLACE INTO sensorium_capteurs(cle, espace, proprietaire, libelle, unite, fraicheur_s, alerte, critique, pire, confiance_min, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (a["cle"], a["espace"], a["proprietaire"], a["libelle"], a["unite"], a["fraicheur_s"], a["alerte"], a["critique"], a["pire"], a["confiance_min"], a["cree_le"]))


def capteur_alimenter(ctx, lectures=None):
    """Jusqu'à 50 lectures d'un coup. Chacune est acceptée ou refusée avec son motif ; l'appel, lui, ne lève pas pour la faute d'un émetteur (voir capteur_declarer)."""
    db, qui = _db(ctx), emetteur(ctx)
    if not isinstance(lectures, list):
        return {"ok": False, "refuse": "« lectures » : une liste", "acceptees": [], "refusees": [], "t": _maintenant()}
    acceptees, refusees = [], []
    for brut in lectures[:MAX_LECTURES_PAR_APPEL]:
        if not isinstance(brut, dict):
            refusees.append({"cle": "", "motif": "lecture illisible"})
            continue
        cle = str(brut.get("cle") or "")
        cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (cle,)) if me.cle_valide(cle) else None
        if cap is None:
            refusees.append({"cle": cle[:120], "motif": "capteur non déclaré"})
        elif cap["proprietaire"] != qui:
            refusees.append({"cle": cle, "motif": "capteur d'un autre compte"})
            compter(db, "refus_espace_autre")
        else:
            motif, _ = enregistrer(ctx, cle, brut.get("valeur"), str(brut.get("gravite") or ""), brut.get("observe_a"), brut.get("confiance"), brut.get("detail") or "", cap)
            (refusees if motif else acceptees).append({"cle": cle, "motif": motif} if motif else cle)
    for _ in lectures[MAX_LECTURES_PAR_APPEL:]:
        refusees.append({"cle": "", "motif": "plus de %d lectures par appel" % MAX_LECTURES_PAR_APPEL})
    if refusees:
        compter(db, "lectures_refusees", len(refusees))
    return {"ok": True, "acceptees": acceptees, "refusees": refusees[:MAX_LECTURES_PAR_APPEL], "t": _maintenant()}


def alimente_prouve(ctx, res):
    if not res.get("acceptees"):
        return True
    return bool(_un(_db(ctx), "SELECT 1 AS x FROM sensorium_lectures WHERE cle=? AND recu_a >= ?", (res["acceptees"][-1], res["t"] - 1)))


# ---------------------------------------------------------------------- clés suivies, visibilité
def mesure_suivre(ctx, cle="", motif=""):
    db, qui = _db(ctx), ctx.compte
    cle = str(cle)
    if not me.cle_valide(cle) or not _peut_voir(ctx, db, cle):
        return {"ok": False, "refuse": "clé inconnue ou non visible pour ce compte", "cle": cle[:120]}
    with _VERROU:
        deja = _un(db, "SELECT 1 AS x FROM sensorium_suivies WHERE cle=? AND suiveur=?", (cle, qui))
        if not deja:
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_suivies")[0]["n"] >= MAX_SUIVIES:
                return {"ok": False, "refuse": "plafond atteint : %d clés suivies" % MAX_SUIVIES, "cle": cle}
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_suivies WHERE suiveur=?", (qui,))[0]["n"] >= MAX_SUIVIES_PAR_SUIVEUR:
                return {"ok": False, "refuse": "plafond atteint : %d clés suivies par compte" % MAX_SUIVIES_PAR_SUIVEUR, "cle": cle}
            db.ecrire("INSERT INTO sensorium_suivies(cle, suiveur, motif, cree_le) VALUES (?,?,?,?)", (cle, qui, me.texte_sur(motif, 200), _maintenant()))
    return {"ok": True, "cle": cle, "nouveau": not deja}


def suivre_prouve(ctx, res):
    return (not res.get("ok")) or bool(_un(_db(ctx), "SELECT 1 AS x FROM sensorium_suivies WHERE cle=? AND suiveur=?", (res["cle"], ctx.compte)))


def suivre_defait(ctx, res):
    if res.get("ok") and res.get("nouveau"):
        _db(ctx).ecrire("DELETE FROM sensorium_suivies WHERE cle=? AND suiveur=?", (res["cle"], ctx.compte))


def mesure_ne_plus_suivre(ctx, cle=""):
    db = _db(ctx)
    avant = _un(db, "SELECT * FROM sensorium_suivies WHERE cle=? AND suiveur=?", (str(cle), ctx.compte))
    if avant:
        db.ecrire("DELETE FROM sensorium_suivies WHERE cle=? AND suiveur=?", (avant["cle"], ctx.compte))
    return {"ok": bool(avant), "cle": str(cle)[:120], "avant": avant}


def ne_suit_prouve(ctx, res):
    return not _un(_db(ctx), "SELECT 1 AS x FROM sensorium_suivies WHERE cle=? AND suiveur=?", (res["cle"], ctx.compte))


def ne_suit_defait(ctx, res):
    a = res.get("avant")
    if a:
        _db(ctx).ecrire("INSERT OR REPLACE INTO sensorium_suivies(cle, suiveur, motif, cree_le) VALUES (?,?,?,?)", (a["cle"], a["suiveur"], a["motif"], a["cree_le"]))


def mesure_publier(ctx, cle="", visibilite="instance", libelle=""):
    """Un administrateur décide à qui une clé montre son ÉTAT (jamais ses valeurs) : `instance` (défaut), `societes:1,2` ou `toutes`."""
    db = _db(ctx)
    cle = str(cle)
    if not me.cle_valide(cle) or not me.visibilite_valide(visibilite):
        return {"ok": False, "refuse": "clé ou visibilité illisible", "cle": cle[:120]}
    if not (privilegie(ctx)):
        return {"ok": False, "refuse": "réservé aux administrateurs", "cle": cle}
    if not (_un(db, "SELECT 1 AS x FROM sensorium_capteurs WHERE cle=?", (cle,)) or cle.startswith("monde.") or _un(db, "SELECT 1 AS x FROM sensorium_lectures WHERE cle=?", (cle,))):
        return {"ok": False, "refuse": "clé inconnue (ni capteur, ni mesure du monde)", "cle": cle}
    avant = _un(db, "SELECT * FROM sensorium_visibilites WHERE cle=?", (cle,))
    db.ecrire("INSERT INTO sensorium_visibilites(cle, visibilite, libelle, par, maj) VALUES (?,?,?,?,?) ON CONFLICT(cle) DO UPDATE SET visibilite=excluded.visibilite, "
              "libelle=CASE WHEN excluded.libelle<>'' THEN excluded.libelle ELSE sensorium_visibilites.libelle END, par=excluded.par, maj=excluded.maj",
              (cle, visibilite, me.texte_sur(libelle, 120), ctx.compte, _maintenant()))
    return {"ok": True, "cle": cle, "visibilite": visibilite, "avant": avant}


def publier_prouve(ctx, res):
    if not res.get("ok"):
        return True
    r = _un(_db(ctx), "SELECT visibilite FROM sensorium_visibilites WHERE cle=?", (res["cle"],))
    return bool(r) and r["visibilite"] == res["visibilite"]


def publier_defait(ctx, res):
    a = res.get("avant")
    db = _db(ctx)
    if not res.get("ok"):
        return
    if a:
        db.ecrire("INSERT OR REPLACE INTO sensorium_visibilites(cle, visibilite, libelle, par, maj) VALUES (?,?,?,?,?)", (a["cle"], a["visibilite"], a["libelle"], a["par"], a["maj"]))
    else:
        db.ecrire("DELETE FROM sensorium_visibilites WHERE cle=?", (res["cle"],))


# ---------------------------------------------------------------------- lectures : minimale (cloisonnée), détaillée, suivies, prévision, auto-observation
def mesure_etat(ctx, cle="", pour=None):
    """L'état d'UNE clé, en quatre champs. Une clé inconnue et une clé non publiée pour la société du demandeur rendent EXACTEMENT la même chose.
    `pour` : voir vue_de (un moteur qui lit pour le compte d'un utilisateur, jamais en privilégié)."""
    db, cle = _db(ctx), str(cle)
    if not me.cle_valide(cle) or not _peut_voir(ctx, db, cle, vue_de(ctx, pour)):
        return me.invisible(cle[:120])
    calcul, lec, cap, depuis = etat_de(db, cle, _maintenant())
    return me.minimal(cle, _libelle(db, cle, cap), calcul, depuis)


def vue_minimale(ctx, cles=None):
    """Les états visibles pour le demandeur : tout pour un administrateur ; pour les autres, les clés publiées pour la société de l'acte. Jamais une valeur."""
    db, now = _db(ctx), _maintenant()
    if cles is None:
        toutes = [r["cle"] for r in db.lire("SELECT cle FROM sensorium_capteurs UNION SELECT cle FROM sensorium_visibilites UNION SELECT cle FROM sensorium_lectures ORDER BY 1 LIMIT 500")]
    elif isinstance(cles, list):
        toutes = [str(c) for c in cles[:100]]
    else:
        toutes = []
    sortie = []
    for cle in toutes:
        if not me.cle_valide(cle) or not _peut_voir(ctx, db, cle):
            if cles is not None:
                sortie.append(me.invisible(cle[:120]))
            continue
        calcul, lec, cap, depuis = etat_de(db, cle, now)
        sortie.append(me.minimal(cle, _libelle(db, cle, cap), calcul, depuis))
    return {"mesures": sortie, "maintenant": now}


def mesure_detail(ctx, cle=""):
    db, cle = _db(ctx), str(cle)
    if not me.cle_valide(cle):
        raise ValueError("clé illisible")
    calcul, lec, cap, depuis = etat_de(db, cle, _maintenant())
    if lec is None and cap is None:
        raise ValueError("mesure inconnue : « %s »" % cle[:120])
    return {"cle": cle, "libelle": _libelle(db, cle, cap), "unite": (cap or {}).get("unite", ""), "etat": calcul["etat"], "raison": calcul["raison"], "age_s": calcul["age_s"], "depuis": depuis,
            "valeur": (lec["valeur_num"] if lec and lec["valeur_num"] is not None else (lec or {}).get("valeur_txt")), "gravite": (lec or {}).get("gravite"),
            "observe_a": (lec or {}).get("observe_a"), "recu_a": (lec or {}).get("recu_a"), "confiance": (lec or {}).get("confiance"), "decalage_s": (lec or {}).get("decalage_s"),
            "detail": (lec or {}).get("detail", ""), "capteur": cap, "visibilite": _visibilite(db, cle),
            "suivie_par": [r["suiveur"] for r in db.lire("SELECT suiveur FROM sensorium_suivies WHERE cle=?", (cle,))]}


def mesures_suivies(ctx):
    db, now = _db(ctx), _maintenant()
    sortie = []
    for r in db.lire("SELECT cle, COUNT(*) AS suiveurs FROM sensorium_suivies GROUP BY cle ORDER BY cle"):
        calcul, lec, cap, depuis = etat_de(db, r["cle"], now)
        sortie.append({"cle": r["cle"], "suiveurs": r["suiveurs"], "etat": calcul["etat"], "raison": calcul["raison"], "depuis": depuis})
    return {"suivies": sortie, "maintenant": now}


def prevision_mesure(ctx, cle="", niveau=""):
    """Combien de jours avant le seuil d'un capteur numérique (point d'évolution `pente` sur son historique) ; jamais une date inventée."""
    db, cle = _db(ctx), str(cle)
    cap = _un(db, "SELECT * FROM sensorium_capteurs WHERE cle=?", (cle,)) if me.cle_valide(cle) else None
    if cap is None:
        raise ValueError("capteur inconnu : « %s »" % cle[:120])
    niveau = niveau or ("critique" if cap["critique"] is not None else "alerte")
    seuil = cap["critique"] if niveau == "critique" else cap["alerte"]
    pts = [(r["t"] / 86400.0, r["valeur"]) for r in db.lire("SELECT t, valeur FROM sensorium_historique WHERE cle=? AND valeur IS NOT NULL ORDER BY t", (cle,))]

    def pente(p):
        s = ctx.point("pente", {"points": [list(x) for x in p]})
        v = s.get("valeur") if isinstance(s, dict) else None
        return (v[0], v[1]) if isinstance(v, (list, tuple)) and len(v) == 2 else (None, 0.0)
    r = me.prevision(pts, seuil, cap["pire"], pente)
    return dict(r, cle=cle, niveau=niveau, seuil=seuil, points=len(pts))


def autoobservation(ctx):
    db, now = _db(ctx), _maintenant()
    cpt = {r["nom"]: {"n": r["n"], "maj": r["maj"]} for r in db.lire("SELECT nom, n, maj FROM sensorium_compteurs")}
    n = lambda t: db.lire("SELECT COUNT(*) AS n FROM %s" % t)[0]["n"]
    tour = cpt.get("dernier_tour", {}).get("maj")
    monde = cpt.get("dernier_monde", {}).get("maj")
    return {"maintenant": now, "horloge_fiable": me.horloge_fiable(now),
            "capteurs": n("sensorium_capteurs"), "espaces": n("sensorium_espaces"), "lectures": n("sensorium_lectures"), "historique": n("sensorium_historique"),
            "suivies": n("sensorium_suivies"), "publiees": n("sensorium_visibilites"), "liens": n("sensorium_liens"),
            "compteurs": {k: v["n"] for k, v in cpt.items() if not k.startswith("dernier_")},
            "dernier_tour_suivi_il_y_a_s": None if tour is None else round(now - tour, 1), "dernier_monde_il_y_a_s": None if monde is None else round(now - monde, 1),
            "plafonds": {"capteurs": MAX_CAPTEURS, "capteurs_par_compte": MAX_CAPTEURS_PAR_COMPTE, "suivies": MAX_SUIVIES, "suivies_par_suiveur": MAX_SUIVIES_PAR_SUIVEUR,
                         "lectures_par_appel": MAX_LECTURES_PAR_APPEL, "historique_par_cle": HISTO_MAX, "liens": MAX_LIENS},
            "suivi_en_retard": tour is not None and now - tour > 300}


def suivies_muettes(ctx):
    """Le détecteur : UN constat qui résume les clés suivies devenues muettes."""
    m = [s for s in mesures_suivies(ctx)["suivies"] if s["etat"] == "inconnu" and s["raison"].startswith("muette")]
    if not m:
        return []
    return [{"objet": ("mesure", "(suivies)"), "titre": "%d mesure%s suivie%s ne répond%s plus" % (len(m), "s" if len(m) > 1 else "", "s" if len(m) > 1 else "", "ent" if len(m) > 1 else ""),
             "detail": ", ".join(s["cle"] for s in m[:5]) + (" …" if len(m) > 5 else "")}]


# ---------------------------------------------------------------------- relations
def lien_poser(ctx, de="", relation="depend_de", vers=""):
    db, qui = _db(ctx), ctx.compte
    if relation not in RELATIONS:
        return {"ok": False, "refuse": "relation : %s" % ", ".join(RELATIONS)}
    if not (isinstance(de, str) and isinstance(vers, str) and REF.match(de) and REF.match(vers)) or de == vers:
        return {"ok": False, "refuse": "références illisibles ou identiques (« type/id »)"}
    with _VERROU:
        deja = _un(db, "SELECT 1 AS x FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (de, relation, vers))
        if not deja:
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_liens")[0]["n"] >= MAX_LIENS:
                return {"ok": False, "refuse": "plafond atteint : %d liens" % MAX_LIENS}
            if db.lire("SELECT COUNT(*) AS n FROM sensorium_liens WHERE par=?", (qui,))[0]["n"] >= MAX_LIENS_PAR_AUTEUR:
                return {"ok": False, "refuse": "plafond atteint : %d liens par compte" % MAX_LIENS_PAR_AUTEUR}
            db.ecrire("INSERT INTO sensorium_liens(de, relation, vers, par, cree_le) VALUES (?,?,?,?,?)", (de, relation, vers, qui, _maintenant()))
    return {"ok": True, "de": de, "relation": relation, "vers": vers, "nouveau": not deja}


def lien_prouve(ctx, res):
    return (not res.get("ok")) or bool(_un(_db(ctx), "SELECT 1 AS x FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (res["de"], res["relation"], res["vers"])))


def lien_defait(ctx, res):
    if res.get("ok") and res.get("nouveau"):
        _db(ctx).ecrire("DELETE FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (res["de"], res["relation"], res["vers"]))


def lien_retirer(ctx, de="", relation="depend_de", vers=""):
    db = _db(ctx)
    avant = _un(db, "SELECT * FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (str(de), str(relation), str(vers)))
    if avant and avant["par"] != ctx.compte and not privilegie(ctx):          # on ne retire que ses propres liens ; un administrateur ou un compte système peut nettoyer
        return {"ok": False, "refuse": "ce lien a été posé par un autre compte", "de": str(de)[:160], "relation": str(relation)[:20], "vers": str(vers)[:160], "avant": None}
    if avant:
        db.ecrire("DELETE FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (avant["de"], avant["relation"], avant["vers"]))
    return {"ok": bool(avant), "de": str(de)[:160], "relation": str(relation)[:20], "vers": str(vers)[:160], "avant": avant}


def delie_prouve(ctx, res):
    return (not res.get("ok") and res.get("avant") is None) or not _un(_db(ctx), "SELECT 1 AS x FROM sensorium_liens WHERE de=? AND relation=? AND vers=?", (res["de"], res["relation"], res["vers"]))


def delie_defait(ctx, res):
    a = res.get("avant")
    if a:
        _db(ctx).ecrire("INSERT OR REPLACE INTO sensorium_liens(de, relation, vers, par, cree_le) VALUES (?,?,?,?,?)", (a["de"], a["relation"], a["vers"], a["par"], a["cree_le"]))


def liens(ctx, objet=""):
    db, o = _db(ctx), str(objet)
    if not REF.match(o):
        raise ValueError("référence illisible")
    return {"objet": o, "depend_de": [dict(r) for r in db.lire("SELECT relation, vers AS objet FROM sensorium_liens WHERE de=? ORDER BY relation, vers LIMIT 200", (o,))],
            "dependants": [dict(r) for r in db.lire("SELECT relation, de AS objet FROM sensorium_liens WHERE vers=? ORDER BY relation, de LIMIT 200", (o,))]}


def impact(ctx, objet="", profondeur=6):
    o = str(objet)
    if not REF.match(o):
        raise ValueError("référence illisible")
    try:
        p = max(1, min(6, int(profondeur)))
    except (TypeError, ValueError):
        p = 6
    tous = [(r["de"], r["relation"], r["vers"]) for r in _db(ctx).lire("SELECT de, relation, vers FROM sensorium_liens LIMIT ?", (MAX_LIENS,))]
    return me.impact(tous, o, p, 200)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _db, compter, privilegie, _un, etat_de, _visibilite, _libelle, _peut_voir …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
