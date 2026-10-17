# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le carnet d'adresses
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : CN
# VERSION CN : 0.3.0  #91d7ee
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le carnet d'adresses.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=91d7ee ▼▼▼
"""Le carnet d'adresses.

Porté de la V18 (`contact_*`, `contacts_*`, vCard, CSV), avec ses leçons :
  - l'enregistrement est un PATCH : sur une fiche existante, un champ non fourni n'est pas touché, une chaîne vide l'efface. En V18, chaque enregistrement
    réécrivait toutes les colonnes et remplaçait les adresses : un client qui n'envoyait que {id, favori} effaçait le reste (contact_save réécrivait tout) ;
  - une adresse n'appartient qu'à UNE fiche : on la refuse plutôt que de la voler en silence ;
  - supprimer = corbeille de trente jours, RIEN n'est effacé (ni adresses ni liens) : on restaure là où la fiche était ; seule la purge détruit, et
    elle garde de quoi défaire ;
  - un dossier supprimé ne supprime pas ses fiches (elles retournent « sans dossier ») : on supprime pour ranger, pas pour détruire ;
  - les comptes de dossier ne comptent que les fiches VIVANTES (ni archivées ni à la corbeille) : un « 12 » qui en montre 9 n'inspire plus confiance ;
  - les doublons sont PROPOSÉS, jamais fusionnés d'office ; seul l'accord d'adresse (et les jumelles d'import) se traite en lot ; la mémoire des paires
    « pas la même personne » évite que les mêmes faux doublons reviennent chaque semaine ;
  - la fusion garde tout : adresses, liens, champs vides de la destination, étiquettes, notes ; la source reste à la corbeille ;
  - un nom sans aucune lettre garde une signature de ses symboles ; « J. Danet » et « Julie Danet » se reconnaissent (dernier mot identique) ;
  - un numéro se compare par ses neuf derniers chiffres ;
  - un lien posé par déduction (`auto`) ne remplace jamais un lien posé à la main ;
  - l'import CSV montre ce qu'il a compris AVANT d'écrire ; UTF-8 d'abord (il échoue franchement), cp1252 ensuite (il accepte tout) ;
  - un modèle ne reçoit que ce que l'administrateur a choisi (vue expurgée : la présence des coordonnées est dite, jamais leur valeur).
"""
from __future__ import annotations

import base64
import csv
import io
import re
import time
import unicodedata
from datetime import datetime

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CHAMPS = (("display_name", 120), ("company", 120), ("job_title", 120), ("phone", 60), ("mobile", 60), ("address", 300), ("website", 200), ("notes", 4000), ("tags", 200))
LIENS = ("project", "domain", "server", "note", "event", "task", "url", "reminder")
ROLES = ("technique", "propriétaire", "hébergeur", "registrar", "client", "prestataire", "facturation", "autre")
CORBEILLE_J = 30
LOT_MAX = 500
PHOTO_MAX = 210_000
PHOTO_RE = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=\s]+$")
FORMES = ("sarl", "sas", "sasu", "sa", "eurl", "sci", "scop", "scic", "snc", "gmbh", "ltd", "limited", "inc", "llc", "bv", "srl", "spa", "ag",
          "et fils", "and sons", "et cie", "and co", "group", "groupe")
LOCAL_MIN = 4
LOCAL_VIDES = ("contact", "info", "bonjour", "hello", "accueil", "secretariat", "secretaire", "admin", "administration", "compta", "comptabilite", "facture", "factures",
               "commande", "commandes", "service", "support", "sav", "direction", "commercial", "commerciaux", "noreply", "no-reply", "nepasrepondre", "postmaster",
               "webmaster", "rh", "recrutement", "devis", "client", "clients")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
PRIVES = ("emails", "addr", "phone", "mobile", "address")
CSV_MAX = 6 * 1024 * 1024
IMPORT_MAX = 5000
# ------------------------------------------------------------------ comparaison de noms, numéros, sites
def aplatir(s):
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def norm_nom(s):
    """Le nom, comparable : aplati, débarrassé de sa forme juridique. Un nom sans aucune lettre garde la signature de ses symboles."""
    t = aplatir(s)
    if not t:
        brut = " ".join(str(s or "").split())
        return ("sym:" + brut.lower()) if brut else ""
    for f in FORMES:
        t = re.sub(r"(^|\s)%s(\s|$)" % re.escape(f), " ", t)
    return " ".join(t.split())


def initiales(a, b):
    """« J. Danet » est-il la forme abrégée de « Julie Danet » ? Le DERNIER mot doit être identique et les précédents se correspondre lettre à lettre."""
    x, y = norm_nom(a).split(), norm_nom(b).split()
    if len(x) < 2 or len(y) < 2 or len(x) != len(y) or x[-1] != y[-1]:
        return False
    abrege = False
    for m, n in zip(x[:-1], y[:-1]):
        if m == n:
            continue
        if (len(m) == 1 and n.startswith(m)) or (len(n) == 1 and m.startswith(n)):
            abrege = True
            continue
        return False
    return abrege


def norm_tel(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[-9:] if len(d) >= 9 else ""


def norm_site(s):
    t = re.sub(r"^[a-z]+://", "", str(s or "").strip().lower()).split("/")[0]
    t = re.sub(r"^www\.", "", t)
    return t if "." in t else ""


def norm_domaine(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^[a-z]+://", "", d).split("/")[0]
    return d[4:] if d.startswith("www.") else d


def remplissage(c):
    """Combien cette fiche porte d'informations : sert à choisir laquelle garder."""
    n = sum(1 for k in ("display_name", "company", "job_title", "phone", "mobile", "address", "website", "notes", "anniversaire", "vault_ref") if str(c.get(k) or "").strip())
    n += len(c.get("emails") or [])
    if c.get("photo"):
        n += 2
    if c.get("favorite"):
        n += 3
    return n


def meilleure(a, b):
    """Laquelle mérite d'absorber l'autre : la plus renseignée, et à égalité la plus ancienne (la plus citée ailleurs). Une PROPOSITION seulement."""
    ra, rb = remplissage(a), remplissage(b)
    if ra != rb:
        return a["id"] if ra > rb else b["id"]
    if a["created_at"] != b["created_at"]:
        return a["id"] if a["created_at"] < b["created_at"] else b["id"]
    return min(a["id"], b["id"])


def signaux(fiches, appeler):
    """Tous les rapprochements, paire par paire, avec ce qui les motive. Le calcul (par SEAUX plutôt que chacun contre chacun) est un POINT D'ÉVOLUTION : points/EC_signaux.py.
    Cette façade ne transmet que les champs utiles (jamais la photo ni les notes) et rebâtit le dictionnaire {(a, b): {motif: ce qui le dit}}."""
    champs = ("id", "emails", "display_name", "phone", "mobile", "company", "website")
    sortie = appeler("signaux", {"fiches": [{k: f.get(k) for k in champs} for f in fiches]})
    return {(p["a"], p["b"]): p["signaux"] for p in sortie["paires"]}


def jumelles(a, b, sig):
    """Deux fiches écrites par la même passe d'import : nom ET numéro identiques, même source, créées dans la même minute. Rien d'autre ne se fusionne en lot."""
    if "nom" not in sig or "tel" not in sig:
        return False
    if not a.get("source") or a.get("source") != b.get("source"):
        return False
    return int(a["created_at"] // 60) == int(b["created_at"] // 60)


# ------------------------------------------------------------------ vCard et CSV
def vcard_ecrire(fiches, appeler):
    """Le fichier vCard des fiches. L'écriture (échappements, repli à 75 octets) est un POINT D'ÉVOLUTION : points/EC_vcard_ecrire.py."""
    return appeler("vcard_ecrire", {"fiches": fiches})["vcard"]


def vcard_lire(texte, appeler):
    """Les fiches d'un fichier vCard. La lecture, tolérante, est un POINT D'ÉVOLUTION : points/EC_vcard_lire.py."""
    return appeler("vcard_lire", {"texte": texte or ""})["fiches"]


def csv_decoder(octets):
    """UTF-8 d'abord parce qu'il ÉCHOUE franchement sur ce qui n'en est pas, alors que cp1252 accepte n'importe quels octets sans jamais lever."""
    if octets[:3] == b"\xef\xbb\xbf":
        return octets[3:].decode("utf-8", "replace"), "utf-8-bom"
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return octets.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return octets.decode("utf-8", "replace"), "utf-8 (approché)"


def csv_lire(octets):
    if not octets:
        raise ValueError("fichier vide")
    if len(octets) > CSV_MAX:
        raise ValueError("fichier trop volumineux (%d Ko)" % (len(octets) // 1024))
    texte, enc = csv_decoder(octets)
    tete = texte.split("\n", 1)[0]
    sep = max((";", ",", "\t", "|"), key=lambda c: tete.count(c))      # csv.Sniffer se trompe sur les fichiers courts : on compte sur l'en-tête
    lignes = [l for l in csv.reader(io.StringIO(texte), delimiter=sep) if any((x or "").strip() for x in l)]
    if len(lignes) < 2:
        raise ValueError("aucune ligne de données")
    return {"entetes": [(x or "").strip() for x in lignes[0]], "lignes": lignes[1:], "encodage": enc, "separateur": sep}


def csv_apparier(entetes, appeler):
    """La colonne de chaque champ de la fiche. L'appariement est un POINT D'ÉVOLUTION : points/EC_csv_apparier.py."""
    return appeler("csv_apparier", {"entetes": list(entetes)})["appariement"]


def csv_fiches(d, appariement, appeler):
    """Les fiches lues d'un CSV. La lecture des lignes est un POINT D'ÉVOLUTION : points/EC_csv_fiches.py."""
    return appeler("csv_fiches", {"lignes": d["lignes"], "appariement": appariement})["fiches"]


def brancher(ctx):
    db = ctx.stockage

    # ------------------------------------------------------------------ le compte et la vue
    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("un carnet est celui d'un compte : aucun compte n'agit")
        return c

    def reglage_bool(nom, defaut):
        v = ctx.reglage(nom, "")
        return defaut if v in ("", None) else bool(v)

    def public(c):
        """Ce qu'un humain voit en entier, un modèle seulement dans la mesure choisie par l'administrateur."""
        if ctx.acteur not in ("itare", "cassandra", "agent") or str(ctx.reglage("vue_modele", "") or "expurgee") == "complete":
            return c
        prives = list(PRIVES) + ([] if reglage_bool("notes_au_modele", True) else ["notes"])
        sortie = {k: v for k, v in c.items() if k not in prives and k != "links" and k != "photo"}
        sortie.update(has_email=bool(c.get("emails")), has_phone=bool(c.get("phone") or c.get("mobile")), has_address=bool(c.get("address")), has_notes=bool(c.get("notes")), redacted=True)
        if "links" in c:
            sortie["links"] = c["links"]
        return sortie

    # ------------------------------------------------------------------ lecture d'une fiche
    def brute(cid, compte, vivante=False):
        r = db.lire("SELECT * FROM contacts WHERE id=? AND compte=?", (int(cid), compte))
        if not r or (vivante and r[0]["supprime_at"] is not None):
            return None
        return r[0]

    def exiger(cid, compte):
        try:
            f = brute(int(cid), compte)
        except (TypeError, ValueError):
            f = None
        if f is None:
            raise ValueError("fiche introuvable")
        return f

    def avec_adresses(rows):
        rows = [dict(r) for r in rows]
        adrs = {}
        for i in range(0, len(rows), 400):
            lot = [r["id"] for r in rows[i:i + 400]]
            for e in db.lire("SELECT contact_id, addr FROM emails WHERE contact_id IN (%s) ORDER BY is_primary DESC, addr" % ",".join("?" * len(lot)), lot):
                adrs.setdefault(e["contact_id"], []).append(e["addr"])
        for r in rows:
            r["emails"] = adrs.get(r["id"], [])
            r["addr"] = r["emails"][0] if r["emails"] else ""
            r["a_photo"] = bool(r.get("photo"))
        return rows

    def liens_de(cid):
        return db.lire("SELECT kind, ref, role, label, auto FROM liens WHERE contact_id=? ORDER BY kind, role", (int(cid),))

    def instantane(cid, compte):
        f = exiger(cid, compte)
        return {"fiche": f, "emails": [(e["addr"], e["is_primary"]) for e in db.lire("SELECT addr, is_primary FROM emails WHERE contact_id=?", (f["id"],))],
                "liens": [dict(l) for l in db.lire("SELECT * FROM liens WHERE contact_id=?", (f["id"],))]}

    def remettre(compte, snap, avec_id=False):
        """Remet une fiche telle qu'elle était : champs, adresses, rattachements. Recrée la fiche (mêmes identifiants) si elle a disparu."""
        f = snap["fiche"]
        with db.transaction() as cx:
            if not cx.execute("SELECT 1 FROM contacts WHERE id=?", (f["id"],)).fetchone():
                cols = list(f)
                cx.execute("INSERT INTO contacts(%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))), [f[c] for c in cols])
            else:
                cols = [c for c in f if c != "id"]
                cx.execute("UPDATE contacts SET %s WHERE id=?" % ",".join("%s=?" % c for c in cols), [f[c] for c in cols] + [f["id"]])
            cx.execute("DELETE FROM emails WHERE contact_id=?", (f["id"],))
            for addr, prim in snap["emails"]:
                cx.execute("INSERT OR IGNORE INTO emails(contact_id, compte, addr, is_primary) VALUES (?,?,?,?)", (f["id"], compte, addr, prim))
            cx.execute("DELETE FROM liens WHERE contact_id=?", (f["id"],))
            for l in snap["liens"]:
                cx.execute("INSERT OR REPLACE INTO liens(contact_id, kind, ref, role, label, auto, created_at) VALUES (?,?,?,?,?,?,?)",
                           (f["id"], l["kind"], l["ref"], l["role"], l["label"], l["auto"], l["created_at"]))

    # ------------------------------------------------------------------ lectures
    def lister(c, query="", limite=200, favoris=False, dossier_id=None, vue=""):
        compte = compte_agit()
        vue = str(vue or "").strip().lower()
        if vue == "corbeille":
            etat = "supprime_at IS NOT NULL"
        elif vue == "archive":
            etat = "supprime_at IS NULL AND archive=1"
        else:
            etat = "supprime_at IS NULL AND archive=0"
        args = [compte]
        if dossier_id is not None and str(dossier_id) != "":
            etat += " AND dossier_id=?"
            args.append(int(dossier_id))
        out = avec_adresses(db.lire("SELECT * FROM contacts WHERE compte=? AND " + etat, args))
        if favoris:
            out = [x for x in out if x["favorite"]]
        q = str(query or "").strip().lower()
        if q:
            out = [x for x in out if q in (" ".join([x["display_name"], x["company"], " ".join(x["emails"]), x["phone"], x["mobile"], x["tags"]])).lower()]
        out.sort(key=lambda x: (0 if x["favorite"] else 1, x["display_name"].lower()))
        lim = max(1, min(int(limite or 200), 2000))
        return {"contacts": [public(dict(x, photo="")) for x in out[:lim]], "total": len(out)}

    def voir(c, id=0):
        compte = compte_agit()
        f = exiger(id, compte)
        fiche = avec_adresses([f])[0]
        fiche["links"] = liens_de(f["id"])
        return public(fiche)

    def pour_adresse(c, adresse=""):
        compte = compte_agit()
        r = db.lire("SELECT contact_id FROM emails WHERE compte=? AND addr=?", (compte, str(adresse or "").strip().lower()))
        if not r:
            return {"trouvee": False}
        f = brute(r[0]["contact_id"], compte, vivante=True)
        return {"trouvee": f is not None, "contact": public(avec_adresses([f])[0]) if f else None}

    def dossiers(c):
        compte = compte_agit()
        vif = "compte=? AND supprime_at IS NULL AND archive=0"
        n = {r["d"]: r["n"] for r in db.lire("SELECT dossier_id d, COUNT(*) n FROM contacts WHERE " + vif + " GROUP BY 1", (compte,))}
        un = lambda cond: db.lire("SELECT COUNT(*) n FROM contacts WHERE compte=? AND " + cond, (compte,))[0]["n"]
        return {"dossiers": [{"id": r["id"], "nom": r["nom"], "parent_id": r["parent_id"], "n": n.get(r["id"], 0)} for r in db.lire("SELECT id, nom, parent_id FROM dossiers WHERE compte=? ORDER BY parent_id, lower(nom)", (compte,))],
                "tout": sum(n.values()), "sans": n.get(0, 0), "archives": un("supprime_at IS NULL AND archive=1"), "corbeille": un("supprime_at IS NOT NULL")}

    def pour_cible(c, kind="", ref=""):
        compte = compte_agit()
        kind = str(kind or "").strip().lower()
        ref = norm_domaine(ref) if kind == "domain" else str(ref or "").strip()
        rows = db.lire("SELECT l.role, c.* FROM liens l JOIN contacts c ON c.id=l.contact_id WHERE l.kind=? AND l.ref=? AND c.compte=? AND c.supprime_at IS NULL", (kind, ref, compte))
        sortie = avec_adresses(rows)
        for o, r in zip(sortie, rows):
            o["role"] = r["role"]
        sortie.sort(key=lambda x: ROLES.index(x["role"]) if x["role"] in ROLES else 99)
        return {"kind": kind, "ref": ref, "contacts": [public(dict(x, photo="")) for x in sortie]}

    def doublons_calcules(compte):
        fiches = avec_adresses(db.lire("SELECT * FROM contacts WHERE compte=? AND supprime_at IS NULL AND archive=0 LIMIT 1000", (compte,)))
        par_id = {f["id"]: f for f in fiches}
        ecartees = {(r["a"], r["b"]) for r in db.lire("SELECT a, b FROM pas_doublons WHERE compte=?", (compte,))}
        sortie = {"jumelles": [], "sur": [], "probable": [], "possible": [], "piege": []}
        for (a, b), sig in signaux(fiches, ctx.point).items():
            if (a, b) in ecartees:
                continue
            nom_ok = "nom" in sig
            if not nom_ok and initiales(par_id[a]["display_name"], par_id[b]["display_name"]):
                nom_ok = True
                sig["nom"] = "« %s » une fois les initiales développées" % norm_nom(par_id[b]["display_name"])
            appuis = [k for k in ("tel", "societe", "site") if k in sig]
            if "adresse" in sig:
                niv = "sur"
            elif jumelles(par_id[a], par_id[b], sig):
                niv = "jumelles"
            elif not nom_ok and "tel" in sig:
                niv = "piege"
            elif nom_ok and appuis:
                niv = "probable"
            else:
                niv = "possible"
            motif = {"sur": "adresse identique", "jumelles": "jumelles d'import : même nom, même numéro, nées ensemble",
                     "piege": "même numéro, noms différents : famille, pro ou numéro recyclé",
                     "probable": "nom + " + " + ".join({"tel": "téléphone", "societe": "société", "site": "site"}[k] for k in appuis) if appuis else "",
                     "possible": "nom seul" if nom_ok else "même identifiant d'adresse"}[niv]
            sortie[niv].append({"niveau": niv, "a": a, "b": b, "noms": [par_id[a]["display_name"] or "(sans nom)", par_id[b]["display_name"] or "(sans nom)"],
                                "signaux": [sig[k] for k in ("adresse", "nom", "tel", "societe", "site", "local") if k in sig], "motif": motif, "garder": meilleure(par_id[a], par_id[b])})
        return sortie

    def doublons(c):
        compte = compte_agit()
        paires = doublons_calcules(compte)
        return {"paires": paires, "total": sum(len(v) for v in paires.values())}

    def vcard_exporter(c, ids=None):
        compte = compte_agit()
        fiches = avec_adresses(db.lire("SELECT * FROM contacts WHERE compte=? AND supprime_at IS NULL ORDER BY lower(display_name) LIMIT 5000", (compte,)))
        if ids:
            garder = {int(x) for x in ids}
            fiches = [f for f in fiches if f["id"] in garder]
        return {"vcard": vcard_ecrire(fiches, ctx.point), "fiches": len(fiches)}

    def csv_apercu(c, contenu_b64=""):
        compte_agit()
        try:
            d = csv_lire(base64.b64decode(contenu_b64 or "", validate=False))
        except ValueError as ex:
            raise ValueError(str(ex))
        app = csv_apparier(d["entetes"], ctx.point)
        reconnus = sorted(set(app.values()))
        return {"entetes": d["entetes"], "appariement": app, "exemples": [[(x or "")[:60] for x in l] for l in d["lignes"][:3]], "lignes": len(d["lignes"]), "encodage": d["encodage"],
                "separateur": d["separateur"], "reconnus": reconnus, "utilisable": bool({"display_name", "_prenom", "_nom", "emails"} & set(reconnus))}

    # ------------------------------------------------------------------ écrire une fiche
    def valider_adresses(emails):
        liste = []
        for a in emails or []:
            a = str(a or "").strip().lower()
            if not a:
                continue
            if not EMAIL.match(a):
                raise ValueError("adresse invalide : %s" % a)
            if a not in liste:
                liste.append(a)
        return liste

    def proprietaire_adresse(compte, addr):
        r = db.lire("SELECT contact_id FROM emails WHERE compte=? AND addr=?", (compte, addr))
        return r[0]["contact_id"] if r else None

    def photo_ok(v):
        s = str(v or "").strip()
        return s if s and len(s) <= PHOTO_MAX and PHOTO_RE.match(s) else ""

    def creer_fiche(compte, d, source="manuel"):
        """Insère une fiche (dict de champs + 'emails'), rend son identifiant. Les adresses doivent être libres."""
        liste = valider_adresses(d.get("emails"))
        nom = str(d.get("display_name") or "").strip()[:120]
        if not nom and not liste:
            raise ValueError("un nom ou une adresse au minimum")
        for a in liste:
            if proprietaire_adresse(compte, a):
                raise ValueError("l'adresse %s appartient déjà à une autre fiche" % a)
        if not nom:
            nom = liste[0].split("@")[0]
        maintenant = time.time()
        valeurs = {k: str(d.get(k) or "")[:lg] for k, lg in CHAMPS}
        valeurs["display_name"] = nom
        with db.transaction() as cx:
            cur = cx.execute("INSERT INTO contacts(compte, display_name, company, job_title, phone, mobile, address, website, notes, tags, favorite, source, photo, vault_ref, dossier_id, anniversaire, created_at, updated_at) "
                             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (compte, valeurs["display_name"], valeurs["company"], valeurs["job_title"], valeurs["phone"], valeurs["mobile"], valeurs["address"], valeurs["website"], valeurs["notes"],
                              valeurs["tags"], 1 if d.get("favorite") else 0, str(source or "manuel")[:40], photo_ok(d.get("photo")), str(d.get("vault_ref") or "")[:160],
                              int(d.get("dossier_id") or 0), str(d.get("anniversaire") or "")[:20], maintenant, maintenant))
            cid = cur.lastrowid
            for i, a in enumerate(liste):
                cx.execute("INSERT INTO emails(contact_id, compte, addr, is_primary) VALUES (?,?,?,?)", (cid, compte, a, 1 if i == 0 else 0))
        return cid

    def creer(c, display_name="", emails=None, phone="", mobile="", company="", job_title="", address="", website="", notes="", tags="", favorite=False, photo="", vault_ref="",
              dossier_id=0, anniversaire="", source="manuel"):
        compte = compte_agit()
        if dossier_id and not db.lire("SELECT 1 FROM dossiers WHERE id=? AND compte=?", (int(dossier_id), compte)):
            raise ValueError("dossier introuvable")
        cid = creer_fiche(compte, dict(display_name=display_name, emails=emails, phone=phone, mobile=mobile, company=company, job_title=job_title, address=address, website=website,
                                       notes=notes, tags=tags, favorite=favorite, photo=photo, vault_ref=vault_ref, dossier_id=dossier_id, anniversaire=anniversaire), source)
        c.emettre("contact.cree", objet=("contact", str(cid)), donnees={"id": cid})
        return {"id": cid, "compte": compte, "attendu": {"display_name": (display_name or "").strip()[:120], "emails": valider_adresses(emails)}}

    def prouver_cree(c, res):
        f = brute(res["id"], res["compte"], vivante=True)
        if f is None:
            return False
        a = avec_adresses([f])[0]
        return all(a["emails"].count(x) == 1 for x in res["attendu"]["emails"]) and (not res["attendu"]["display_name"] or a["display_name"] == res["attendu"]["display_name"])

    def defaire_cree(c, res):
        with db.transaction() as cx:
            for t, col in (("emails", "contact_id"), ("liens", "contact_id")):
                cx.execute("DELETE FROM %s WHERE %s=?" % (t, col), (res["id"],))
            cx.execute("DELETE FROM contacts WHERE id=? AND compte=?", (res["id"], res["compte"]))

    def modifier(c, id=0, display_name=None, emails=None, phone=None, mobile=None, company=None, job_title=None, address=None, website=None, notes=None, tags=None, favorite=None,
                 photo=None, vault_ref=None, dossier_id=None, anniversaire=None):
        compte = compte_agit()
        avant = instantane(id, compte)
        cid = avant["fiche"]["id"]
        liste = None if emails is None else valider_adresses(emails)
        for a in liste or []:
            p = proprietaire_adresse(compte, a)
            if p and p != cid:
                raise ValueError("l'adresse %s appartient déjà à une autre fiche" % a)
        nom = None if display_name is None else str(display_name or "").strip()[:120]
        if nom is not None and not nom and not (liste if liste is not None else [e[0] for e in avant["emails"]]):
            raise ValueError("un nom ou une adresse au minimum")
        recus = {"display_name": nom, "company": company, "job_title": job_title, "phone": phone, "mobile": mobile, "address": address, "website": website, "notes": notes, "tags": tags}
        sets, args = [], []
        for col, lg in CHAMPS:
            if recus.get(col) is not None:
                sets.append("%s=?" % col)
                args.append(str(recus[col])[:lg])
        if favorite is not None:
            sets.append("favorite=?")
            args.append(1 if favorite else 0)
        if photo is not None:
            sets.append("photo=?")
            args.append(photo_ok(photo))
        if vault_ref is not None:
            sets.append("vault_ref=?")
            args.append(str(vault_ref or "")[:160])
        if dossier_id is not None:
            if dossier_id and not db.lire("SELECT 1 FROM dossiers WHERE id=? AND compte=?", (int(dossier_id), compte)):
                raise ValueError("dossier introuvable")
            sets.append("dossier_id=?")
            args.append(int(dossier_id or 0))
        if anniversaire is not None:
            sets.append("anniversaire=?")
            args.append(str(anniversaire or "")[:20])
        with db.transaction() as cx:
            if sets:
                cx.execute("UPDATE contacts SET %s, updated_at=? WHERE id=?" % ", ".join(sets), args + [time.time(), cid])
            if liste is not None:
                cx.execute("DELETE FROM emails WHERE contact_id=?", (cid,))
                for i, a in enumerate(liste):
                    cx.execute("INSERT INTO emails(contact_id, compte, addr, is_primary) VALUES (?,?,?,?)", (cid, compte, a, 1 if i == 0 else 0))
        c.emettre("contact.modifie", objet=("contact", str(cid)), donnees={"id": cid})
        return {"id": cid, "compte": compte, "avant": avant, "champs": [x.split("=")[0] for x in sets], "emails_fournis": liste}

    def prouver_modifie(c, res):
        a = avec_adresses([brute(res["id"], res["compte"])])[0]
        if res["emails_fournis"] is not None and a["emails"] != res["emails_fournis"]:
            return False
        return True

    def defaire_modifie(c, res):
        remettre(res["compte"], res["avant"])

    def lot(ids):
        sortie = []
        for x in ids if isinstance(ids, (list, tuple)) else [ids]:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0 and v not in sortie:
                sortie.append(v)
        if not sortie:
            raise ValueError("aucune fiche désignée")
        return sortie[:LOT_MAX]

    def maj_lot(compte, ids, sets, args):
        ids = lot(ids)
        mes = [r["id"] for r in db.lire("SELECT id FROM contacts WHERE compte=? AND id IN (%s)" % ",".join("?" * len(ids)), [compte] + ids)]
        if not mes:
            raise ValueError("fiche introuvable")
        avant = {r["id"]: {k: r[k] for k in ("supprime_at", "fusion_vers", "archive", "dossier_id")} for r in db.lire("SELECT id, supprime_at, fusion_vers, archive, dossier_id FROM contacts WHERE id IN (%s)" % ",".join("?" * len(mes)), mes)}
        db.ecrire("UPDATE contacts SET %s, updated_at=? WHERE id IN (%s)" % (sets, ",".join("?" * len(mes))), list(args) + [time.time()] + mes)
        return {"compte": compte, "ids": mes, "avant": {str(k): v for k, v in avant.items()}, "demandees": len(ids)}

    def retour_lot(c, res):
        for k, v in res["avant"].items():
            db.ecrire("UPDATE contacts SET supprime_at=?, fusion_vers=?, archive=?, dossier_id=? WHERE id=? AND compte=?", (v["supprime_at"], v["fusion_vers"], v["archive"], v["dossier_id"], int(k), res["compte"]))

    def supprimer(c, ids=None):
        r = maj_lot(compte_agit(), ids, "supprime_at=?", [time.time()])
        c.emettre("contact.supprime", objet=("contact", "lot"), donnees={"ids": r["ids"]})
        return r

    def prouver_supprime(c, res):
        return all(brute(i, res["compte"])["supprime_at"] is not None for i in res["ids"])

    def restaurer(c, ids=None):
        r = maj_lot(compte_agit(), ids, "supprime_at=NULL, fusion_vers=0", [])
        c.emettre("contact.restaure", objet=("contact", "lot"), donnees={"ids": r["ids"]})
        return r

    def prouver_restaure(c, res):
        return all(brute(i, res["compte"])["supprime_at"] is None for i in res["ids"])

    def archiver(c, ids=None, archive=True):
        r = maj_lot(compte_agit(), ids, "archive=?", [1 if archive else 0])
        r["archive"] = bool(archive)
        return r

    def prouver_archive(c, res):
        return all(bool(brute(i, res["compte"])["archive"]) == res["archive"] for i in res["ids"])

    def deplacer(c, ids=None, dossier_id=0):
        compte = compte_agit()
        d = int(dossier_id or 0)
        if d and not db.lire("SELECT 1 FROM dossiers WHERE id=? AND compte=?", (d, compte)):
            raise ValueError("dossier introuvable")
        r = maj_lot(compte, ids, "dossier_id=?", [d])
        r["dossier_id"] = d
        return r

    def prouver_deplace(c, res):
        return all(brute(i, res["compte"])["dossier_id"] == res["dossier_id"] for i in res["ids"])

    # ------------------------------------------------------------------ dossiers
    def dossier_enregistrer(c, nom="", id=None, parent_id=0):
        compte = compte_agit()
        nom = str(nom or "").strip()[:60]
        if not nom:
            raise ValueError("un dossier a besoin d'un nom")
        pid = int(parent_id or 0)
        if pid:
            p = db.lire("SELECT parent_id FROM dossiers WHERE id=? AND compte=?", (pid, compte))
            if not p:
                raise ValueError("dossier parent introuvable")
            if p[0]["parent_id"]:
                raise ValueError("un sous-dossier ne peut pas en contenir")
        if id:
            avant = db.lire("SELECT * FROM dossiers WHERE id=? AND compte=?", (int(id), compte))
            if not avant:
                raise ValueError("dossier introuvable")
            if pid == int(id):
                raise ValueError("un dossier ne se contient pas lui-même")
            db.ecrire("UPDATE dossiers SET nom=?, parent_id=? WHERE id=?", (nom, pid, int(id)))
            return {"id": int(id), "compte": compte, "nom": nom, "avant": dict(avant[0])}
        did = db.ecrire("INSERT INTO dossiers(compte, nom, parent_id, cree) VALUES (?,?,?,?)", (compte, nom, pid, time.time()))
        return {"id": did, "compte": compte, "nom": nom, "avant": None}

    def prouver_dossier(c, res):
        r = db.lire("SELECT nom FROM dossiers WHERE id=? AND compte=?", (res["id"], res["compte"]))
        return bool(r) and r[0]["nom"] == res["nom"]

    def defaire_dossier(c, res):
        if res["avant"]:
            db.ecrire("UPDATE dossiers SET nom=?, parent_id=? WHERE id=?", (res["avant"]["nom"], res["avant"]["parent_id"], res["id"]))
        else:
            db.ecrire("DELETE FROM dossiers WHERE id=? AND compte=?", (res["id"], res["compte"]))

    def dossier_supprimer(c, id=0):
        compte = compte_agit()
        d = db.lire("SELECT * FROM dossiers WHERE id=? AND compte=?", (int(id), compte))
        if not d:
            raise ValueError("dossier introuvable")
        sous = [r["id"] for r in db.lire("SELECT id FROM dossiers WHERE parent_id=?", (int(id),))]
        fiches = [r["id"] for r in db.lire("SELECT id FROM contacts WHERE dossier_id=? AND compte=?", (int(id), compte))]
        with db.transaction() as cx:
            cx.execute("UPDATE contacts SET dossier_id=0 WHERE dossier_id=? AND compte=?", (int(id), compte))
            cx.execute("UPDATE dossiers SET parent_id=0 WHERE parent_id=?", (int(id),))
            cx.execute("DELETE FROM dossiers WHERE id=?", (int(id),))
        return {"id": int(id), "compte": compte, "dossier": dict(d[0]), "sous_dossiers": sous, "fiches": fiches}

    def prouver_dossier_supprime(c, res):
        return not db.lire("SELECT 1 FROM dossiers WHERE id=?", (res["id"],)) and all(brute(i, res["compte"])["dossier_id"] == 0 for i in res["fiches"])

    def defaire_dossier_supprime(c, res):
        d = res["dossier"]
        with db.transaction() as cx:
            cx.execute("INSERT OR IGNORE INTO dossiers(id, compte, nom, parent_id, cree) VALUES (?,?,?,?,?)", (d["id"], d["compte"], d["nom"], d["parent_id"], d["cree"]))
            for s in res["sous_dossiers"]:
                cx.execute("UPDATE dossiers SET parent_id=? WHERE id=?", (d["id"], s))
            for f in res["fiches"]:
                cx.execute("UPDATE contacts SET dossier_id=? WHERE id=? AND compte=?", (d["id"], f, res["compte"]))

    # ------------------------------------------------------------------ rattachements
    def lier(c, id=0, kind="", ref="", role="autre", label="", auto=False):
        compte = compte_agit()
        f = exiger(id, compte)
        kind, role, ref = str(kind or "").strip().lower(), str(role or "autre").strip().lower(), str(ref or "").strip()
        if kind not in LIENS:
            raise ValueError("type inconnu (%s)" % ", ".join(LIENS))
        if role not in ROLES:
            raise ValueError("rôle inconnu (%s)" % ", ".join(ROLES))
        if not ref:
            raise ValueError("référence requise")
        if kind == "domain":
            ref = norm_domaine(ref)
        avant = db.lire("SELECT * FROM liens WHERE contact_id=? AND kind=? AND ref=?", (f["id"], kind, ref))
        if avant and auto:
            return {"id": f["id"], "compte": compte, "kind": kind, "ref": ref, "inchange": True, "avant": None}      # une déduction ne remplace jamais un lien posé à la main
        db.ecrire("INSERT OR REPLACE INTO liens(contact_id, kind, ref, role, label, auto, created_at) VALUES (?,?,?,?,?,?,?)", (f["id"], kind, ref, role, str(label or "")[:200], 1 if auto else 0, time.time()))
        return {"id": f["id"], "compte": compte, "kind": kind, "ref": ref, "role": role, "inchange": False, "avant": dict(avant[0]) if avant else None}

    def prouver_lien(c, res):
        return res["inchange"] or bool(db.lire("SELECT 1 FROM liens WHERE contact_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"])))

    def defaire_lien(c, res):
        if res["inchange"]:
            return
        db.ecrire("DELETE FROM liens WHERE contact_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))
        a = res["avant"]
        if a:
            db.ecrire("INSERT OR REPLACE INTO liens(contact_id, kind, ref, role, label, auto, created_at) VALUES (?,?,?,?,?,?,?)", (a["contact_id"], a["kind"], a["ref"], a["role"], a["label"], a["auto"], a["created_at"]))

    def delier(c, id=0, kind="", ref=""):
        compte = compte_agit()
        f = exiger(id, compte)
        kind = str(kind or "").strip().lower()
        ref = norm_domaine(ref) if kind == "domain" else str(ref or "").strip()
        avant = db.lire("SELECT * FROM liens WHERE contact_id=? AND kind=? AND ref=?", (f["id"], kind, ref))
        if not avant:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE contact_id=? AND kind=? AND ref=?", (f["id"], kind, ref))
        return {"id": f["id"], "compte": compte, "kind": kind, "ref": ref, "avant": dict(avant[0])}

    def prouver_delie(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE contact_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))

    def defaire_delie(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO liens(contact_id, kind, ref, role, label, auto, created_at) VALUES (?,?,?,?,?,?,?)", (a["contact_id"], a["kind"], a["ref"], a["role"], a["label"], a["auto"], a["created_at"]))

    # ------------------------------------------------------------------ fusion
    def fusion(compte, src, dst):
        """Absorbe `src` dans `dst`. Rend les deux instantanés d'avant (le retour remet tout)."""
        s, d = int(src), int(dst)
        if s == d:
            raise ValueError("une fiche ne se fusionne pas avec elle-même")
        a, b = instantane(s, compte), instantane(d, compte)
        fa, fb = a["fiche"], b["fiche"]
        locaux = {x[0].split("@")[0].lower() for x in b["emails"]}
        maj = {}
        for col in ("display_name", "company", "job_title", "phone", "mobile", "address", "website", "anniversaire", "vault_ref", "photo", "dossier_id"):
            vb, va = fb[col], fa[col]
            vide = (not vb) if isinstance(vb, int) else not str(vb or "").strip()
            if col == "display_name" and not vide:
                vide = str(vb).strip().lower() in locaux
            if vide and ((va) if isinstance(va, int) else str(va or "").strip()):
                maj[col] = va
        et = [t.strip() for t in str(fb["tags"]).split(",") if t.strip()]
        for t in [t.strip() for t in str(fa["tags"]).split(",") if t.strip()]:
            if t.lower() not in [x.lower() for x in et]:
                et.append(t)
        if ", ".join(et) != fb["tags"]:
            maj["tags"] = ", ".join(et)[:200]
        notes = "\n\n".join(x for x in [fb["notes"].strip(), fa["notes"].strip()] if x)
        if notes != fb["notes"]:
            maj["notes"] = notes[:4000]
        if fa["favorite"] and not fb["favorite"]:
            maj["favorite"] = 1
        with db.transaction() as cx:
            if maj:
                cx.execute("UPDATE contacts SET %s, updated_at=? WHERE id=?" % ", ".join("%s=?" % k for k in maj), list(maj.values()) + [time.time(), d])
            cx.execute("UPDATE OR IGNORE emails SET contact_id=?, is_primary=0 WHERE contact_id=?", (d, s))
            cx.execute("DELETE FROM emails WHERE contact_id=?", (s,))
            cx.execute("UPDATE OR IGNORE liens SET contact_id=? WHERE contact_id=?", (d, s))
            cx.execute("DELETE FROM liens WHERE contact_id=?", (s,))
            cx.execute("DELETE FROM pas_doublons WHERE a=? OR b=?", (s, s))
            cx.execute("UPDATE contacts SET supprime_at=?, fusion_vers=?, updated_at=? WHERE id=?", (time.time(), d, time.time(), s))
        return {"source": a, "destination": b}

    def fusionner(c, source=0, destination=0):
        compte = compte_agit()
        r = fusion(compte, source, destination)
        c.emettre("contact.fusionne", objet=("contact", str(destination)), donnees={"source": int(source), "destination": int(destination)})
        return {"compte": compte, "fusions": [r], "destination": int(destination), "source": int(source)}

    def prouver_fusion(c, res):
        for f in res["fusions"]:
            s, d = f["source"]["fiche"]["id"], f["destination"]["fiche"]["id"]
            if brute(s, res["compte"])["supprime_at"] is None:
                return False
            ad = {e["addr"] for e in db.lire("SELECT addr FROM emails WHERE contact_id=?", (d,))}
            if not {x[0] for x in f["source"]["emails"]} <= ad:
                return False
        return True

    def defaire_fusion(c, res):
        for f in reversed(res["fusions"]):
            remettre(res["compte"], f["destination"])
            remettre(res["compte"], f["source"])

    def fusionner_certaines(c, paires=None):
        compte = compte_agit()
        d = doublons_calcules(compte)
        certaines = (d["sur"] + d["jumelles"])[:200]
        if paires:
            voulues = {tuple(sorted((int(p["a"]), int(p["b"])))) for p in paires}
            certaines = [p for p in certaines if (p["a"], p["b"]) in voulues]
        fusions, deja = [], set()
        for p in certaines:
            if p["a"] in deja or p["b"] in deja:
                continue
            dst = p["garder"]
            src = p["b"] if dst == p["a"] else p["a"]
            fusions.append(fusion(compte, src, dst))
            deja.update((p["a"], p["b"]))
        if fusions:
            c.emettre("contact.fusionne", objet=("contact", "lot"), donnees={"n": len(fusions)})
        return {"compte": compte, "fusions": fusions, "n": len(fusions)}

    def pas_doublon(c, a=0, b=0, annuler=False):
        compte = compte_agit()
        x, y = sorted((int(a), int(b)))
        if x == y:
            raise ValueError("une fiche n'est pas son propre doublon")
        exiger(x, compte)
        exiger(y, compte)
        existait = bool(db.lire("SELECT 1 FROM pas_doublons WHERE compte=? AND a=? AND b=?", (compte, x, y)))
        if annuler:
            db.ecrire("DELETE FROM pas_doublons WHERE compte=? AND a=? AND b=?", (compte, x, y))
        else:
            db.ecrire("INSERT OR IGNORE INTO pas_doublons(compte, a, b, ts) VALUES (?,?,?,?)", (compte, x, y, time.time()))
        return {"compte": compte, "paire": [x, y], "ecartee": not annuler, "existait": existait}

    def prouver_paire(c, res):
        presente = bool(db.lire("SELECT 1 FROM pas_doublons WHERE compte=? AND a=? AND b=?", (res["compte"], res["paire"][0], res["paire"][1])))
        return presente == res["ecartee"]

    def defaire_paire(c, res):
        if res["existait"]:
            db.ecrire("INSERT OR IGNORE INTO pas_doublons(compte, a, b, ts) VALUES (?,?,?,?)", (res["compte"], res["paire"][0], res["paire"][1], time.time()))
        else:
            db.ecrire("DELETE FROM pas_doublons WHERE compte=? AND a=? AND b=?", (res["compte"], res["paire"][0], res["paire"][1]))

    # ------------------------------------------------------------------ importer
    def verser(compte, fiches, source, dossier_id=0):
        """La porte commune des imports : une adresse déjà connue complète la fiche (champs vides seulement), jamais de doublon."""
        if len(fiches) > IMPORT_MAX:
            raise ValueError("trop de fiches (%d au plus)" % IMPORT_MAX)
        crees, completees, deja, ignorees = [], [], 0, 0
        for f in fiches:
            f = dict(f)
            if not f.get("phone") and f.get("tel"):
                f["phone"] = f["tel"][0]
            if not f.get("mobile") and f.get("cell"):
                f["mobile"] = f["cell"][0]
            adrs = [a for a in valider_adresses_souple(f.get("emails"))]
            proprios = {proprietaire_adresse(compte, a) for a in adrs} - {None}
            if proprios:
                cid = sorted(proprios)[0]
                avant = instantane(cid, compte)
                manque = {k: str(f.get(k) or "")[:lg] for k, lg in CHAMPS if not str(avant["fiche"][k]).strip() and str(f.get(k) or "").strip()}
                nouvelles = [a for a in adrs if not proprietaire_adresse(compte, a)]
                if manque or nouvelles:
                    with db.transaction() as cx:
                        if manque:
                            cx.execute("UPDATE contacts SET %s, updated_at=? WHERE id=?" % ", ".join("%s=?" % k for k in manque), list(manque.values()) + [time.time(), cid])
                        for a in nouvelles:
                            cx.execute("INSERT OR IGNORE INTO emails(contact_id, compte, addr, is_primary) VALUES (?,?,?,0)", (cid, compte, a))
                    completees.append(avant)
                else:
                    deja += 1
                continue
            d = dict(f)
            d["emails"] = adrs
            d["dossier_id"] = dossier_id
            try:
                crees.append(creer_fiche(compte, d, source))
            except ValueError:
                ignorees += 1
        return {"compte": compte, "crees": crees, "completees": completees, "deja": deja, "ignorees": ignorees}

    def valider_adresses_souple(emails):
        sortie = []
        for a in emails or []:
            a = str(a or "").strip().lower()
            if EMAIL.match(a) and a not in sortie:
                sortie.append(a)
        return sortie

    def prouver_import(c, res):
        return all(brute(i, res["compte"]) is not None for i in res["crees"])

    def defaire_import(c, res):
        for i in res["crees"]:
            defaire_cree(c, {"id": i, "compte": res["compte"]})
        for snap in res["completees"]:
            remettre(res["compte"], snap)

    def vcard_importer(c, texte="", dossier_id=0):
        compte = compte_agit()
        if dossier_id and not db.lire("SELECT 1 FROM dossiers WHERE id=? AND compte=?", (int(dossier_id), compte)):
            raise ValueError("dossier introuvable")
        fiches = vcard_lire(texte, ctx.point)
        if not fiches:
            raise ValueError("aucune fiche reconnue dans ce fichier")
        r = verser(compte, fiches, "vcard", int(dossier_id or 0))
        c.emettre("contact.importe", objet=("contact", "lot"), donnees={"source": "vcard", "crees": len(r["crees"])})
        return r

    def csv_importer(c, contenu_b64="", appariement=None, dossier_id=0):
        compte = compte_agit()
        if dossier_id and not db.lire("SELECT 1 FROM dossiers WHERE id=? AND compte=?", (int(dossier_id), compte)):
            raise ValueError("dossier introuvable")
        d = csv_lire(base64.b64decode(contenu_b64 or "", validate=False))
        app = appariement if isinstance(appariement, dict) and appariement else csv_apparier(d["entetes"], ctx.point)
        if not app:
            raise ValueError("aucune colonne reconnue — appariez-les à la main avant d'importer")
        fiches = csv_fiches(d, app, ctx.point)
        if not fiches:
            raise ValueError("aucune ligne exploitable")
        r = verser(compte, fiches, "csv", int(dossier_id or 0))
        c.emettre("contact.importe", objet=("contact", "lot"), donnees={"source": "csv", "crees": len(r["crees"])})
        return r

    # ------------------------------------------------------------------ purger
    def purger_corbeille(c):
        compte = compte_agit()
        limite = time.time() - CORBEILLE_J * 86400
        vises = [r["id"] for r in db.lire("SELECT id FROM contacts WHERE compte=? AND supprime_at IS NOT NULL AND supprime_at<? LIMIT ?", (compte, limite, LOT_MAX))]
        snaps = [instantane(i, compte) for i in vises]
        with db.transaction() as cx:
            for i in vises:
                cx.execute("DELETE FROM emails WHERE contact_id=?", (i,))
                cx.execute("DELETE FROM liens WHERE contact_id=?", (i,))
                cx.execute("DELETE FROM contacts WHERE id=?", (i,))
        return {"compte": compte, "purgees": len(vises), "ids": vises, "copies": snaps}

    def prouver_purge(c, res):
        return not db.lire("SELECT 1 FROM contacts WHERE id IN (%s)" % ",".join("?" * len(res["ids"])), res["ids"]) if res["ids"] else True

    def defaire_purge(c, res):
        for snap in res["copies"]:
            remettre(res["compte"], snap)

    # ------------------------------------------------------------------ inscription
    c = ctx
    for cid, f in (("lister", lister), ("voir", voir), ("pour_adresse", pour_adresse), ("dossiers", dossiers), ("pour_cible", pour_cible), ("doublons", doublons),
                   ("vcard_exporter", vcard_exporter), ("csv_apercu", csv_apercu)):
        c.implementer(cid, f)
    c.implementer("creer", creer, prouver_cree, defaire_cree, simuler=lambda x, display_name="", **_: "créerait la fiche « %s »" % display_name)
    c.implementer("modifier", modifier, prouver_modifie, defaire_modifie, simuler=lambda x, id="", **_: "modifierait la fiche %s" % id)
    c.implementer("supprimer", supprimer, prouver_supprime, retour_lot, simuler=lambda x, ids=None, **_: "mettrait %s fiche(s) à la corbeille" % len(ids or []))
    c.implementer("restaurer", restaurer, prouver_restaure, retour_lot, simuler=lambda x, ids=None, **_: "sortirait %s fiche(s) de la corbeille" % len(ids or []))
    c.implementer("archiver", archiver, prouver_archive, retour_lot, simuler=lambda x, ids=None, **_: "archiverait %s fiche(s)" % len(ids or []))
    c.implementer("deplacer", deplacer, prouver_deplace, retour_lot, simuler=lambda x, ids=None, **_: "déplacerait %s fiche(s)" % len(ids or []))
    c.implementer("dossier_enregistrer", dossier_enregistrer, prouver_dossier, defaire_dossier, simuler=lambda x, nom="", **_: "enregistrerait le dossier « %s »" % nom)
    c.implementer("dossier_supprimer", dossier_supprimer, prouver_dossier_supprime, defaire_dossier_supprime, simuler=lambda x, id="", **_: "supprimerait le dossier %s sans toucher à ses fiches" % id)
    c.implementer("lier", lier, prouver_lien, defaire_lien, simuler=lambda x, id="", kind="", ref="", **_: "rattacherait la fiche %s à %s %s" % (id, kind, ref))
    c.implementer("delier", delier, prouver_delie, defaire_delie, simuler=lambda x, id="", kind="", ref="", **_: "détacherait la fiche %s de %s %s" % (id, kind, ref))
    c.implementer("fusionner", fusionner, prouver_fusion, defaire_fusion, simuler=lambda x, source="", destination="", **_: "fusionnerait la fiche %s dans la %s" % (source, destination))
    c.implementer("fusionner_certaines", fusionner_certaines, prouver_fusion, defaire_fusion, simuler=lambda x, **_: "fusionnerait les paires certaines (même adresse, jumelles d'import)")
    c.implementer("pas_doublon", pas_doublon, prouver_paire, defaire_paire, simuler=lambda x, a="", b="", **_: "retiendrait que %s et %s ne sont pas la même personne" % (a, b))
    c.implementer("vcard_importer", vcard_importer, prouver_import, defaire_import, simuler=lambda x, **_: "importerait un fichier vCard")
    c.implementer("csv_importer", csv_importer, prouver_import, defaire_import, simuler=lambda x, **_: "importerait un fichier CSV")
    c.implementer("purger_corbeille", purger_corbeille, prouver_purge, defaire_purge, simuler=lambda x, **_: "effacerait ce qui est à la corbeille depuis plus de trente jours")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : aplatir, norm_nom, initiales, norm_tel, norm_site, norm_domaine, remplissage, meilleure …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
