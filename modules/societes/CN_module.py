# ═══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sociétés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : societes
# ZONE       : CN
# VERSION CN : 0.1.0  #9fba12
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les sociétés de l'instance et la fiche de chacune ; les fonctions (groupes attachés à une société).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ═══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9fba12 ▼▼▼
"""Le module Sociétés : la fiche de chaque société et ses fonctions.

Tout compte appartient à une société (le noyau le garantit) ; la société principale existe toujours. Seul le superadministrateur crée, archive et
administre l'ensemble des sociétés ; l'administrateur d'une société ne gère que la sienne. Une « fonction » est un groupe de droits attaché à
une société : ses niveaux (aucun, voir, modifier, gérer) par domaine ne valent que dans cette société.
"""
from __future__ import annotations

import copy
import datetime
import json
import re
import time

DOMAINES = ("fiche", "etablissements", "horaires", "pieces", "banque", "conformite", "habillage", "equipe")
NIVEAUX = ("voir", "modifier", "gerer")
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

# ── les rubriques de la fiche : quel domaine de droits les couvre, quels champs, quel niveau pour les écrire ──
def _t(n):
    return ("txt", n)


RUBRIQUES = {
    "identite": {"domaine": "fiche", "ecrire": "modifier", "champs": {"forme": _t(40), "siren": ("siren",), "ape": _t(10), "capital": _t(40), "creation": ("date",), "nom": ("nom",)}},
    "siege": {"domaine": "fiche", "ecrire": "modifier", "champs": {"adresse": _t(200), "cp": _t(12), "ville": _t(80), "pays": _t(60), "tel": ("tel",), "email": ("email",), "web": ("url",)}},
    "regional": {"domaine": "fiche", "ecrire": "modifier", "champs": {"devise": ("choix", ("", "EUR", "CHF", "CAD", "USD", "GBP")), "langue": _t(30), "fuseau": ("fuseau",)}},
    "presence": {"domaine": "fiche", "ecrire": "modifier", "champs": {"linkedin": _t(200), "instagram": _t(200), "facebook": _t(200), "youtube": _t(200), "whatsapp": _t(200)}},
    "etablissements": {"domaine": "etablissements", "ecrire": "modifier", "champs": {"items": ("liste", {"id": _t(40), "nom": _t(120), "siege": ("bool",), "adresse": _t(240), "siret": ("siret",), "horaires_propres": ("bool",)}, 200)}},
    "horaires": {"domaine": "horaires", "ecrire": "modifier", "champs": {"jours": ("jours",), "feries": ("bool",), "exceptions": ("liste", {"d": ("date",), "l": _t(160)}, 200)}},
    "pieces": {"domaine": "pieces", "ecrire": "modifier", "champs": {"items": ("liste", {"id": _t(40), "nom": _t(160), "exp": ("date",), "lien": _t(300)}, 200)}},
    "banque": {"domaine": "banque", "ecrire": "gerer", "champs": {"iban": ("iban",), "bic": ("bic",), "banque": _t(120), "pref_devis": _t(20), "pref_facture": _t(20), "tva_taux": ("taux",), "exo_deb": ("md",), "exo_fin": ("md",)}},
    "conformite": {"domaine": "conformite", "ecrire": "modifier", "champs": {"mentions": ("bool",), "rgpd": ("bool",), "dpo": ("bool",), "cgv": ("bool",), "cookies": ("bool",)}},
    "habillage": {"domaine": "habillage", "ecrire": "modifier", "champs": {"accent": ("hex",), "entete": ("choix", ("classique", "sobre", "bandeau")), "signature": ("choix", ("complete", "courte"))}},
    "roles": {"domaine": "equipe", "ecrire": "gerer", "champs": {"titulaire": ("compte",), "legal": ("compte",), "dpo": ("compte",), "facturation": ("compte",), "securite": ("compte",)}},
}

DEFAUTS = {
    "identite": {"forme": "", "siren": "", "ape": "", "capital": "", "creation": "", "nom": ""},
    "siege": {"adresse": "", "cp": "", "ville": "", "pays": "", "tel": "", "email": "", "web": ""},
    "regional": {"devise": "", "langue": "", "fuseau": ""},
    "presence": {"linkedin": "", "instagram": "", "facebook": "", "youtube": "", "whatsapp": ""},
    "etablissements": {"items": []},
    "horaires": {"jours": [{"o": i < 5, "a": "09:00", "f": "18:00"} for i in range(7)], "feries": True, "exceptions": []},
    "pieces": {"items": []},
    "banque": {"iban": "", "bic": "", "banque": "", "pref_devis": "", "pref_facture": "", "tva_taux": "", "exo_deb": "01-01", "exo_fin": "12-31"},
    "conformite": {"mentions": False, "rgpd": False, "dpo": False, "cgv": False, "cookies": False},
    "habillage": {"accent": "#0b7c74", "entete": "classique", "signature": "complete"},
    "roles": {"titulaire": "", "legal": "", "dpo": "", "facturation": "", "securite": ""},
}

# les fonctions que toute société reçoit : niveaux (0 aucun, 1 voir, 2 modifier, 3 gérer) par domaine, dans l'ordre de DOMAINES
FONCTIONS = (
    ("titulaire", "Titulaire", "Propriétaire de l'espace de la société. Une seule personne.", (3, 3, 3, 3, 3, 3, 3, 3)),
    ("admin", "Administrateur", "Gère la société au quotidien et nomme les fonctions inférieures.", (3, 3, 3, 3, 2, 3, 3, 3)),
    ("gestion", "Gestionnaire", "Fait vivre les lieux, les horaires, les pièces et l'image.", (2, 3, 3, 2, 0, 1, 2, 1)),
    ("compta", "Comptable", "Facturation et pièces ; coffre limité aux collections qu'on lui ouvre.", (1, 1, 0, 2, 3, 1, 0, 0)),
    ("conformite", "Conformité", "Registre, pièces légales, mentions.", (1, 0, 0, 3, 0, 3, 0, 0)),
    ("membre", "Membre", "Consulte la fiche et les horaires.", (1, 1, 1, 0, 0, 0, 0, 0)),
    ("invite", "Invité", "Lecture de la fiche seulement (prestataire, stagiaire).", (1, 0, 0, 0, 0, 0, 0, 0)),
)
RE_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


def luhn(n: str) -> bool:
    if not re.fullmatch(r"\d{9}", n):
        return False
    s = 0
    for i, ch in enumerate(reversed(n)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return s % 10 == 0


def iban_valide(iban: str) -> bool:
    z = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", z):
        return False
    r = z[4:] + z[:4]
    return int("".join(str(int(c, 36)) for c in r)) % 97 == 1


def masquer_iban(iban: str) -> str:
    z = (iban or "").replace(" ", "")
    return "" if not z else z[:4] + " " + "•••• " * max(0, (len(z) - 8) // 4) + z[-4:]


def _valider(spec, v, nom):
    """Rend la valeur propre, ou lève ValueError(« champ : pourquoi »)."""
    k = spec[0]
    if k == "txt":
        s = str(v if v is not None else "").strip()
        if len(s) > spec[1]:
            raise ValueError("%s : %d caractères au plus" % (nom, spec[1]))
        return s
    if k == "bool":
        return bool(v)
    if k == "choix":
        s = str(v or "")
        if s not in spec[1]:
            raise ValueError("%s : %s" % (nom, " | ".join(x or "vide" for x in spec[1])))
        return s
    s = str(v if v is not None else "").strip()
    if k == "nom":
        if not s or len(s) > 120:
            raise ValueError("nom : de 1 à 120 caractères")
        return s
    if k == "siren":
        z = s.replace(" ", "")
        if z and not luhn(z):
            raise ValueError("siren : 9 chiffres, clé de contrôle valide")
        return z
    if k == "siret":
        z = s.replace(" ", "")
        if z and not re.fullmatch(r"\d{14}", z):
            raise ValueError("%s : 14 chiffres" % nom)
        return z
    if k == "date":
        if s:
            try:
                datetime.date.fromisoformat(s)
            except ValueError:
                raise ValueError("%s : une date AAAA-MM-JJ" % nom)
        return s
    if k == "email":
        if s and not RE_EMAIL.match(s):
            raise ValueError("%s : une adresse e-mail" % nom)
        return s
    if k == "url":
        if s and not re.match(r"^https?://[^\s]{3,}$", s):
            raise ValueError("%s : une adresse http(s)" % nom)
        return s
    if k == "tel":
        if s and not re.fullmatch(r"[0-9+()\-. ]{4,30}", s):
            raise ValueError("%s : un numéro de téléphone" % nom)
        return s
    if k == "hex":
        if s and not re.fullmatch(r"#[0-9a-fA-F]{6}", s):
            raise ValueError("%s : une couleur #rrggbb" % nom)
        return s.lower()
    if k == "fuseau":
        if s and not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_+\-0-9]+", s):
            raise ValueError("%s : un fuseau comme Europe/Paris" % nom)
        return s
    if k == "iban":
        if s and not iban_valide(s):
            raise ValueError("iban : clé de contrôle invalide")
        z = s.replace(" ", "").upper()
        return " ".join(z[i:i + 4] for i in range(0, len(z), 4))
    if k == "bic":
        if s and not re.fullmatch(r"[A-Za-z]{6}[A-Za-z0-9]{2}([A-Za-z0-9]{3})?", s):
            raise ValueError("bic : 8 ou 11 caractères")
        return s.upper()
    if k == "md":
        if s and not re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", s):
            raise ValueError("%s : mois-jour, comme 12-31" % nom)
        return s
    if k == "taux":
        if s and not re.fullmatch(r"\d{1,2}([.,]\d{1,3})?", s):
            raise ValueError("%s : un taux en %%" % nom)
        return s.replace(",", ".")
    if k == "compte":
        s = s.lower()
        if s and not RE_EMAIL.match(s):
            raise ValueError("%s : l'identifiant d'un compte" % nom)
        return s
    raise ValueError("%s : type inconnu" % nom)


def valider_champs(champs, valeurs):
    """Valide un dictionnaire de valeurs pour une rubrique ; rend le dictionnaire propre (seulement les champs fournis)."""
    if not isinstance(valeurs, dict):
        raise ValueError("valeurs : un objet")
    inconnus = [k for k in valeurs if k not in champs]
    if inconnus:
        raise ValueError("champ inconnu : %s" % ", ".join(sorted(inconnus)))
    out = {}
    for k, v in valeurs.items():
        spec = champs[k]
        if spec[0] == "liste":
            if not isinstance(v, list) or len(v) > spec[2]:
                raise ValueError("%s : une liste de %d éléments au plus" % (k, spec[2]))
            out[k] = [valider_champs(spec[1], dict(it)) if isinstance(it, dict) else (_ for _ in ()).throw(ValueError("%s : des objets" % k)) for it in v]
            for it in out[k]:                                  # un élément complet : les champs absents prennent leur valeur vide
                for ck, cs in spec[1].items():
                    it.setdefault(ck, False if cs[0] == "bool" else "")
        elif spec[0] == "jours":
            if not isinstance(v, list) or len(v) != 7:
                raise ValueError("jours : sept jours, du lundi au dimanche")
            jours = []
            for i, j in enumerate(v):
                if not isinstance(j, dict):
                    raise ValueError("jours : des objets")
                a, f = str(j.get("a", "09:00")), str(j.get("f", "18:00"))
                for h in (a, f):
                    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h):
                        raise ValueError("%s : une heure HH:MM" % JOURS[i])
                if bool(j.get("o")) and a >= f:
                    raise ValueError("%s : l'ouverture précède la fermeture" % JOURS[i])
                jours.append({"o": bool(j.get("o")), "a": a, "f": f})
            out[k] = jours
        else:
            out[k] = _valider(spec, v, k)
    return out


def brancher(ctx):
    db = ctx.stockage
    d = ctx.droits()
    idt = ctx.identite()

    def _aujourdhui():
        return datetime.date.today()

    # ── qui peut quoi, dans quelle société ──────────────────────────────────
    def _superadmin(compte):
        return bool(compte) and idt.est_superadmin(compte)

    def _exiger_super():
        if ctx.compte and not _superadmin(ctx.compte):
            raise ValueError("réservé au superadministrateur : seul lui administre l'ensemble des sociétés")

    def _cible(societe):
        """La société visée : celle de l'acte, ou une autre à laquelle ce compte a accès. Un refus ne dit pas si elle existe."""
        soc = str(societe or "").strip() or ctx.societe or "1"
        compte = ctx.compte
        if compte and soc not in d.societes_de(compte):
            raise ValueError("cette société n'est pas la vôtre")
        s = idt.societe(soc)
        if not s or s["archivee"]:
            raise ValueError("cette société n'est pas la vôtre")
        return soc

    def _niveau(compte, domaine, societe):
        """0 aucun, 1 voir, 2 modifier, 3 gérer : le plus haut droit de ce domaine que détient ce compte dans cette société."""
        if not compte:
            return 3
        n = 0
        for i, nv in enumerate(NIVEAUX, 1):
            if d.a(compte, "societes.%s_%s" % (domaine, nv), societe):
                n = i
        return n

    def _exiger(domaine, niveau, societe):
        need = NIVEAUX.index(niveau) + 1
        if _niveau(ctx.compte, domaine, societe) < need:
            raise ValueError("droit manquant : %s sur « %s » dans cette société" % (niveau, domaine))

    # ── stockage de la fiche ────────────────────────────────────────────────
    def _lire_rub(soc, rub):
        r = db.lire("SELECT donnees FROM fiche WHERE societe=? AND rubrique=?", (soc, rub))
        out = copy.deepcopy(DEFAUTS[rub])
        if r:
            out.update(json.loads(r[0]["donnees"]))
        if rub == "identite":
            s = idt.societe(soc)
            out["nom"] = s["nom"] if s else ""
        return out

    def _ecrire_rub(soc, rub, data):
        data = {k: v for k, v in data.items() if not (rub == "identite" and k == "nom")}
        db.ecrire("INSERT INTO fiche (societe, rubrique, donnees, maj) VALUES (?,?,?,?) "
                  "ON CONFLICT(societe, rubrique) DO UPDATE SET donnees=excluded.donnees, maj=excluded.maj", (soc, rub, json.dumps(data, ensure_ascii=False), time.time()))

    def _poser_nom(soc, nom):
        r = idt.societe_renommer(soc, nom)
        if not r["ok"]:
            raise ValueError(r["error"])

    def _decrire(rub, data):
        """Une copie pour l'historique : l'IBAN n'y est jamais en clair."""
        c = copy.deepcopy(data)
        if rub == "banque":
            c["iban"] = masquer_iban(c.get("iban", ""))
        return json.dumps(c, ensure_ascii=False)

    def _histoire(soc, rub, resume, avant, apres):
        db.ecrire("INSERT INTO historique (societe, ts, qui, rubrique, resume, avant, apres) VALUES (?,?,?,?,?,?,?)",
                  (soc, time.time(), ctx.compte or "", rub, resume, _decrire(rub, avant) if avant is not None else "", _decrire(rub, apres) if apres is not None else ""))

    def _emettre(type, soc, donnees):
        try:
            ctx.emettre(type, objet=("societe", soc), donnees=dict(donnees, societe=soc))
        except Exception:
            pass

    # ── lectures ────────────────────────────────────────────────────────────
    def lister(c):
        compte = ctx.compte
        ids = d.societes_de(compte) if compte else [s["id"] for s in idt.societes()]
        sup = _superadmin(compte)
        out = []
        for s in idt.societes(tout=sup):
            if s["id"] in ids or (sup and not compte):
                out.append({"id": s["id"], "nom": s["nom"], "principale": bool(s["principale"]), "archivee": bool(s["archivee"]), "ici": s["id"] == (ctx.societe or "1"),
                            "domicile": bool(compte) and s["id"] == idt.societe_de(compte)})
        return {"societes": out, "multi": bool(ctx.reglage("multi")), "superadmin": sup, "societe": ctx.societe or "1"}

    def vue_consolidee(c):
        """Toutes les sociétés d'un coup, pour le superadministrateur : utilisateurs, modules ouverts, partages, demandes de module en attente."""
        _exiger_super()
        manifs = ctx.manifestes_actifs(toutes=True)
        attente = {r["societe"]: r["n"] for r in db.lire("SELECT societe, COUNT(*) AS n FROM demandes_module WHERE etat='demandee' GROUP BY societe")}
        out = []
        for s in idt.societes(tout=True):
            p = idt.partages(s["id"])
            out.append({"id": s["id"], "nom": s["nom"], "principale": bool(s["principale"]), "archivee": bool(s["archivee"]),
                        "utilisateurs": idt.nombre_utilisateurs(s["id"]),
                        "modules": sum(1 for m in manifs if idt.module_ouvert(s["id"], m.id, m.importance, m.essentiel, m.instance)),
                        "partages_donnes": len([x for x in p["sortants"] if x["actif"]]), "partages_recus": len(p["entrants"]),
                        "demandes": attente.get(s["id"], 0)})
        return {"societes": out, "modules_installes": len(manifs)}

    def lire(c, societe=""):
        soc = _cible(societe)
        s = idt.societe(soc)
        compte = ctx.compte
        sup = _superadmin(compte)
        return {"societe": s["id"], "nom": s["nom"], "principale": bool(s["principale"]), "archivee": bool(s["archivee"]),
                "comptes": len(idt.comptes_de_societe(soc)) if sup or _niveau(compte, "equipe", soc) >= 1 else None}

    def _acces(soc):
        return {dm: _niveau(ctx.compte, dm, soc) for dm in DOMAINES}

    def fiche_lire(c, societe=""):
        soc = _cible(societe)
        acces = _acces(soc)
        out = {}
        for rub, spec in RUBRIQUES.items():
            if acces[spec["domaine"]] >= 1:
                data = _lire_rub(soc, rub)
                if rub == "banque":
                    data["iban"] = masquer_iban(data.get("iban", ""))
                out[rub] = data
        return {"societe": soc, "rubriques": out, "acces": acces}

    def carte(c, societe=""):
        """Ce que les modules lisent pour nommer la société (en-têtes, signatures, mentions) : jamais de banque, jamais de responsables."""
        soc = str(societe or "").strip() or ctx.societe or "1"
        if ctx.compte and soc not in d.societes_de(ctx.compte):
            raise ValueError("cette société n'est pas la vôtre")
        i, sg, rg, hb = _lire_rub(soc, "identite"), _lire_rub(soc, "siege"), _lire_rub(soc, "regional"), _lire_rub(soc, "habillage")
        return {"societe": soc, "nom": i["nom"], "forme": i["forme"], "siren": i["siren"], "capital": i["capital"], "adresse": sg["adresse"], "cp": sg["cp"], "ville": sg["ville"],
                "pays": sg["pays"], "email": sg["email"], "tel": sg["tel"], "web": sg["web"], "devise": rg["devise"], "langue": rg["langue"], "fuseau": rg["fuseau"], "accent": hb["accent"],
                "entete": hb["entete"], "signature": hb["signature"]}

    def iban_voir(c, societe=""):
        soc = _cible(societe)
        _exiger("banque", "gerer", soc)
        b = _lire_rub(soc, "banque")
        _histoire(soc, "banque", "a affiché l'IBAN", None, None)
        return {"societe": soc, "iban": b.get("iban", "")}

    def historique(c, societe="", limite=50):
        soc = _cible(societe)
        acces = _acces(soc)
        n = max(1, min(int(limite or 50), 500))
        rows = db.lire("SELECT id, ts, qui, rubrique, resume FROM historique WHERE societe=? ORDER BY id DESC LIMIT ?", (soc, n))
        return {"societe": soc, "historique": [r for r in rows if r["rubrique"] == "" or acces.get(RUBRIQUES.get(r["rubrique"], {"domaine": "fiche"})["domaine"], 0) >= 1]}

    def echeances(c, societe=""):
        soc = _cible(societe)
        acces = _acces(soc)
        if acces["pieces"] < 1:
            raise ValueError("droit manquant : voir « pieces » dans cette société")
        auj = _aujourdhui()
        out = []
        for p in _lire_rub(soc, "pieces")["items"]:
            if p.get("exp"):
                out.append({"nom": p["nom"], "date": p["exp"], "jours": (datetime.date.fromisoformat(p["exp"]) - auj).days, "genre": "piece"})
        if acces["banque"] >= 1:
            fin = _lire_rub(soc, "banque").get("exo_fin") or "12-31"
            m, j = int(fin[:2]), int(fin[3:])
            try:
                dt = datetime.date(auj.year, m, j)
                if dt < auj:
                    dt = datetime.date(auj.year + 1, m, j)
                out.append({"nom": "Clôture de l'exercice", "date": dt.isoformat(), "jours": (dt - auj).days, "genre": "exercice"})
            except ValueError:
                pass
        return {"societe": soc, "echeances": sorted(out, key=lambda e: e["jours"])}

    # ── écritures de la fiche ───────────────────────────────────────────────
    def fiche_regler(c, societe="", rubrique="", valeurs=None):
        soc = _cible(societe)
        spec = RUBRIQUES.get(rubrique)
        if not spec:
            raise ValueError("rubrique : %s" % " | ".join(RUBRIQUES))
        _exiger(spec["domaine"], spec["ecrire"], soc)
        propres = valider_champs(spec["champs"], valeurs if valeurs is not None else {})
        if not propres:
            raise ValueError("rien à changer")
        avant = _lire_rub(soc, rubrique)
        apres = dict(avant)
        apres.update(propres)
        if rubrique == "etablissements":
            if sum(1 for e in apres["items"] if e.get("siege")) > 1:
                raise ValueError("etablissements : un seul siège")
        if rubrique == "roles":
            for k, v in propres.items():
                if v and idt.societe_de(v) != soc and soc not in d.societes_de(v):
                    raise ValueError("%s : ce compte n'a aucun lien avec cette société" % k)
        if rubrique == "identite" and "nom" in propres:
            _poser_nom(soc, propres["nom"])
        _ecrire_rub(soc, rubrique, apres)
        _histoire(soc, rubrique, "a modifié %s" % ", ".join(sorted(propres)), avant, apres)
        _emettre("societe.modifiee", soc, {"rubrique": rubrique, "champs": sorted(propres)})
        return {"societe": soc, "rubrique": rubrique, "avant": avant, "apres": apres}

    def prouver_regler(c, res):
        return _lire_rub(res["societe"], res["rubrique"]) == res["apres"]

    def defaire_regler(c, res):
        if res["rubrique"] == "identite" and res["avant"].get("nom") != res["apres"].get("nom"):
            _poser_nom(res["societe"], res["avant"]["nom"])
        _ecrire_rub(res["societe"], res["rubrique"], res["avant"])
        _histoire(res["societe"], res["rubrique"], "a défait la modification", res["apres"], res["avant"])

    # ── les modules de chaque société : le superadministrateur seul décide ──
    def modules(c, societe=""):
        """Les modules de l'instance et, pour cette société, s'ils sont ouverts. Les modules vitaux le sont partout."""
        soc = _cible(societe)
        out = []
        for m in sorted(ctx.manifestes_actifs(toutes=True), key=lambda m: m.id):
            vital = (m.importance == "vital" or bool(m.essentiel)) and not m.instance
            out.append({"id": m.id, "nom": m.nom, "importance": m.importance or "optionnel", "vital": vital, "instance": bool(m.instance), "ouvert": idt.module_ouvert(soc, m.id, m.importance, m.essentiel, m.instance),
                        "choisi": m.id in idt.modules_de_societe(soc)})
        return {"societe": soc, "modules": out, "peut_regler": _superadmin(ctx.compte) or not ctx.compte or _niveau(ctx.compte, "equipe", soc) >= 3}

    def partages(c, societe=""):
        """Ce que la société partage avec d'autres, et ce que d'autres partagent avec elle."""
        soc = _cible(societe)
        _exiger("equipe", "voir", soc)
        p = idt.partages(soc)
        noms = {x["id"]: x["nom"] for x in idt.societes()}
        for k in ("sortants", "entrants"):
            for x in p[k]:
                x["nom_source"] = noms.get(x["source"], x["source"])
                x["nom_destinataire"] = noms.get(x["destinataire"], x["destinataire"])
        return dict(p, societe=soc, peut_decider=_superadmin(ctx.compte) or not ctx.compte)

    def partager(c, source="", destinataire="", type="utilisateurs", mode="tous", elements=None, actif=True):
        _exiger_super()
        src = str(source or "").strip()
        dst = str(destinataire or "").strip()
        typ = str(type or "utilisateurs")
        avant = next((x for x in idt.partages(src)["sortants"] if x["destinataire"] == dst and x["type"] == typ), None)
        r = idt.partage_regler(src, dst, typ, str(mode or "tous"), elements or [], bool(actif), ctx.compte or "")
        r["avant"] = avant
        _histoire(src, "partages", "partage ses %s avec « %s » (%s)" % (r["type"], dst, "tous" if r["mode"] == "tous" else "%d choisi(s)" % len(r["elements"])), None, None)
        _emettre("societe.modifiee", src, {"rubrique": "partages", "destinataire": dst, "type": r["type"], "mode": r["mode"]})
        return r

    def partage_retirer(c, source="", destinataire="", type="utilisateurs"):
        _exiger_super()
        src = str(source or "").strip()
        dst = str(destinataire or "").strip()
        typ = str(type or "utilisateurs")
        avant = next((x for x in idt.partages(src)["sortants"] if x["destinataire"] == dst and x["type"] == typ), None)
        if not idt.partage_retirer(src, dst, typ):
            raise ValueError("ce partage n'existe pas")
        _histoire(src, "partages", "ne partage plus ses %s avec « %s »" % (type, dst), None, None)
        _emettre("societe.modifiee", src, {"rubrique": "partages", "destinataire": dst, "type": type, "retire": True})
        return {"source": src, "destinataire": dst, "type": typ, "avant": avant}

    def _remettre_partage(res):
        a = res.get("avant")
        if a:
            idt.partage_regler(a["source"], a["destinataire"], a["type"], a["mode"], a["elements"], a["actif"], ctx.compte or "")
        else:
            idt.partage_retirer(res["source"], res["destinataire"], res["type"])

    def prouver_partager(c, res):
        return any(x["destinataire"] == res["destinataire"] and x["type"] == res["type"] and x["mode"] == res["mode"] for x in idt.partages(res["source"])["sortants"])

    def prouver_partage_retirer(c, res):
        return not any(x["destinataire"] == res["destinataire"] and x["type"] == res["type"] for x in idt.partages(res["source"])["sortants"])

    def defaire_partager(c, res):
        _remettre_partage(res)

    def defaire_partage_retirer(c, res):
        _remettre_partage(res)

    def partageables(c, societe=""):
        """Les utilisateurs d'autres sociétés qu'on peut ranger dans une fonction de cette société, avec celle qu'ils y ont déjà."""
        soc = _cible(societe)
        _exiger("equipe", "gerer", soc)
        _initialiser_fonctions(soc)
        gids = {g["id"]: g["id"].split(".", 1)[-1] for g in _fonctions_de(soc)}
        out = []
        for u in idt.utilisateurs_partages(soc):
            fct = next((gids[g] for g in gids if d.membre(u["compte"], g)), "")
            out.append(dict(u, fonction=fct))
        return {"societe": soc, "utilisateurs": out}

    # ── les demandes de module : une société secondaire n'installe rien sur l'instance, elle demande ; la principale examine, installe, attribue ──
    def _demande(did):
        r = db.lire("SELECT * FROM demandes_module WHERE id=?", (int(did),))
        if not r:
            raise ValueError("demande introuvable")
        return dict(r[0])

    def module_demander(c, societe="", nom="", motif="", source=""):
        soc = _cible(societe)
        _exiger("equipe", "gerer", soc)
        n, m, s = str(nom or "").strip()[:120], str(motif or "").strip()[:1000], str(source or "").strip()[:300]
        if not n:
            raise ValueError("quel module ? Un nom au moins")
        if not m:
            raise ValueError("dites à quoi il servira : la société principale décide sur ce motif")
        cur = db.ecrire("INSERT INTO demandes_module(societe, demandeur, ts, nom, motif, source) VALUES(?,?,?,?,?,?)", (soc, ctx.compte or "", time.time(), n, m, s))
        did = cur if isinstance(cur, int) else db.lire("SELECT max(id) AS i FROM demandes_module")[0]["i"]
        _histoire(soc, "", "a demandé le module « %s »" % n, None, None)
        _emettre("societe.modifiee", soc, {"rubrique": "demandes", "demande": did, "nom": n})
        return {"id": did, "societe": soc, "nom": n}

    def prouver_demander(c, res):
        return bool(db.lire("SELECT 1 FROM demandes_module WHERE id=? AND etat='demandee'", (res["id"],)))

    def defaire_demander(c, res):
        db.ecrire("DELETE FROM demandes_module WHERE id=? AND etat='demandee'", (res["id"],))

    def module_demandes(c, societe="", toutes=False):
        """Les demandes d'une société ; la société principale (superadministrateur) les voit toutes avec `toutes`."""
        if toutes:
            _exiger_super()
            rows = db.lire("SELECT * FROM demandes_module ORDER BY (etat='demandee') DESC, id DESC LIMIT 200")
        else:
            soc = _cible(societe)
            _exiger("equipe", "voir", soc)
            rows = db.lire("SELECT * FROM demandes_module WHERE societe=? ORDER BY id DESC LIMIT 100", (soc,))
        noms = {x["id"]: x["nom"] for x in idt.societes(True)}
        return {"demandes": [dict(r, nom_societe=noms.get(r["societe"], r["societe"])) for r in rows], "peut_decider": _superadmin(ctx.compte) or not ctx.compte}

    def module_demande_decider(c, id=0, decision="", module="", reponse="", exclusif=True):
        _exiger_super()
        d_ = _demande(id)
        if d_["etat"] != "demandee":
            raise ValueError("cette demande est déjà traitée")
        decision = str(decision or "").strip()
        if decision not in ("accepter", "refuser"):
            raise ValueError("décision : accepter ou refuser")
        mod = ""
        if decision == "accepter":
            mod = str(module or "").strip()
            m = next((x for x in ctx.manifestes_actifs(toutes=True) if x.id == mod), None)
            if m is None:
                raise ValueError("ce module n'est pas installé et actif : installez-le d'abord par la logithèque (examen et consentement), puis attribuez-le")
            if m.instance:
                raise ValueError("un module d'instance n'existe que dans la société principale")
            if m.importance == "vital" or m.essentiel:
                raise ValueError("un module vital est déjà ouvert dans toutes les sociétés")
            idt.module_regler(d_["societe"], mod, True)
            if exclusif and d_["societe"] != "1" and mod not in idt.modules_de_societe("1"):
                idt.module_regler("1", mod, False)                  # installé pour eux : la société principale ne l'a pas d'office
        db.ecrire("UPDATE demandes_module SET etat=?, module=?, decide_par=?, decide_ts=?, reponse=? WHERE id=?",
                  ("acceptee" if decision == "accepter" else "refusee", mod, ctx.compte or "", time.time(), str(reponse or "").strip()[:500], int(id)))
        _histoire(d_["societe"], "", "demande du module « %s » %s%s" % (d_["nom"], "acceptée" if decision == "accepter" else "refusée", (" : " + mod) if mod else ""), None, None)
        _emettre("societe.modifiee", d_["societe"], {"rubrique": "demandes", "demande": int(id), "decision": decision, "module": mod})
        return {"id": int(id), "societe": d_["societe"], "etat": "acceptee" if decision == "accepter" else "refusee", "module": mod, "avant": d_}

    def prouver_decider(c, res):
        return _demande(res["id"])["etat"] == res["etat"]

    def defaire_decider(c, res):
        a = res["avant"]
        if res.get("module"):
            idt.module_regler(a["societe"], res["module"], None)
        db.ecrire("UPDATE demandes_module SET etat='demandee', module='', decide_par='', decide_ts=0, reponse='' WHERE id=?", (res["id"],))

    # ── le profil d'une personne dans une société ──
    def _lier(soc, compte):
        if idt.societe_de(compte) != soc and soc not in d.societes_de(compte):
            raise ValueError("ce compte n'a aucun lien avec cette société")

    def _profil(soc, compte):
        r = db.lire("SELECT nom, fonction, tel, email FROM profils WHERE societe=? AND compte=?", (soc, compte))
        return dict(r[0]) if r else {"nom": "", "fonction": "", "tel": "", "email": ""}

    def _cible_profil(societe, utilisateur):
        soc = _cible(societe)
        cible = str(utilisateur or "").strip().lower() or ctx.compte or ""
        if not cible:
            raise ValueError("de quel compte ?")
        if cible != ctx.compte and not _superadmin(ctx.compte):
            _exiger("equipe", "gerer", soc)            # le profil d'un autre : l'administrateur de la société
        _lier(soc, cible)
        return soc, cible

    def profil_lire(c, societe="", utilisateur=""):
        soc, cible = _cible_profil(societe, utilisateur)
        return dict(_profil(soc, cible), societe=soc, compte=cible)

    def profil_regler(c, societe="", utilisateur="", nom=None, fonction=None, tel=None, email=None):
        soc, cible = _cible_profil(societe, utilisateur)
        avant = _profil(soc, cible)
        neuf = dict(avant)
        for k, v, lim in (("nom", nom, 120), ("fonction", fonction, 120), ("tel", tel, 40), ("email", email, 190)):
            if v is not None:
                neuf[k] = str(v).strip()[:lim]
        if neuf["email"] and not RE_EMAIL.match(neuf["email"]):
            raise ValueError("email : adresse invalide")
        db.ecrire("INSERT INTO profils(societe, compte, nom, fonction, tel, email, maj) VALUES(?,?,?,?,?,?,?) ON CONFLICT(societe, compte) DO UPDATE SET nom=excluded.nom, fonction=excluded.fonction, tel=excluded.tel, email=excluded.email, maj=excluded.maj",
                  (soc, cible, neuf["nom"], neuf["fonction"], neuf["tel"], neuf["email"], time.time()))
        _histoire(soc, "", "a modifié le profil de %s dans la société" % cible, None, None)
        return {"societe": soc, "compte": cible, "avant": avant, "apres": neuf}

    def prouver_profil(c, res):
        return _profil(res["societe"], res["compte"]) == res["apres"]

    def defaire_profil(c, res):
        a = res["avant"]
        db.ecrire("INSERT INTO profils(societe, compte, nom, fonction, tel, email, maj) VALUES(?,?,?,?,?,?,?) ON CONFLICT(societe, compte) DO UPDATE SET nom=excluded.nom, fonction=excluded.fonction, tel=excluded.tel, email=excluded.email, maj=excluded.maj",
                  (res["societe"], res["compte"], a["nom"], a["fonction"], a["tel"], a["email"], time.time()))

    # ── les modèles d'une société (son habillage et les préfixes de ses devis et factures), recopiés par une autre : jamais la banque ──
    def _recopier_modeles(dest, source):
        avant = {"habillage": _lire_rub(dest, "habillage"), "banque": _lire_rub(dest, "banque")}
        _ecrire_rub(dest, "habillage", _lire_rub(source, "habillage"))
        ban = _lire_rub(dest, "banque")
        src = _lire_rub(source, "banque")
        ban["pref_devis"], ban["pref_facture"] = src.get("pref_devis", ""), src.get("pref_facture", "")
        _ecrire_rub(dest, "banque", ban)
        return avant

    def modeles_recopier(c, societe="", depuis=""):
        soc = _cible(societe)
        _exiger("habillage", "modifier", soc)
        src = str(depuis or "").strip()
        s = idt.societe(src)
        if not s or s["archivee"] or src == soc:
            raise ValueError("société à recopier inconnue")
        if not _superadmin(ctx.compte) and ctx.compte and not idt.partage_actif(src, soc, "modeles"):
            raise ValueError("cette société ne partage pas ses modèles avec la vôtre : seul le superadministrateur décide d'un partage")
        avant = _recopier_modeles(soc, src)
        _histoire(soc, "habillage", "a recopié les modèles de « %s »" % s["nom"], None, None)
        _emettre("societe.modifiee", soc, {"rubrique": "habillage", "depuis": src})
        return {"societe": soc, "depuis": src, "avant": avant, "apres": _lire_rub(soc, "habillage")}

    def prouver_modeles(c, res):
        return _lire_rub(res["societe"], "habillage") == res["apres"]

    def defaire_modeles(c, res):
        _ecrire_rub(res["societe"], "habillage", res["avant"]["habillage"])
        _ecrire_rub(res["societe"], "banque", res["avant"]["banque"])

    def module_regler(c, societe="", module="", ouvert=True):
        soc = _cible(societe)
        if ctx.compte and not _superadmin(ctx.compte):
            _exiger("equipe", "gerer", soc)          # l'administrateur d'une société choisit les modules de SA société, parmi ceux de l'instance qui ne sont pas la base
        m = next((x for x in ctx.manifestes_actifs(toutes=True) if x.id == module), None)
        if m is None:
            raise ValueError("module inconnu ou pas actif dans l'instance")
        if m.instance:
            raise ValueError("un module d'instance n'existe que dans la société principale : elle seule décide du comportement de l'application")
        if m.importance == "vital" or m.essentiel:
            raise ValueError("un module vital est ouvert dans toutes les sociétés")
        avant = idt.modules_de_societe(soc).get(module)
        idt.module_regler(soc, module, bool(ouvert))
        _histoire(soc, "", "a %s le module %s" % ("ouvert" if ouvert else "fermé", module), None, None)
        _emettre("societe.modifiee", soc, {"rubrique": "modules", "module": module, "ouvert": bool(ouvert)})
        return {"societe": soc, "module": module, "avant": avant, "apres": bool(ouvert)}

    def prouver_module_regler(c, res):
        return idt.modules_de_societe(res["societe"]).get(res["module"]) == res["apres"]

    def defaire_module_regler(c, res):
        idt.module_regler(res["societe"], res["module"], res["avant"])

    # ── les sociétés elles-mêmes : le superadministrateur seul ──────────────
    def creer(c, nom="", identifiant="", administrateur="", modules_de="", modeles_de=""):
        _exiger_super()
        if not ctx.reglage("multi"):
            raise ValueError("une seule société dans cette instance : installez le module Multi-sociétés pour en ajouter")
        r = idt.societe_creer(nom, identifiant)
        if not r["ok"]:
            raise ValueError(r["error"])
        adm = str(administrateur or ctx.compte or "").strip().lower()
        if modules_de:
            for mid, ouvert in idt.modules_de_societe(str(modules_de)).items():
                idt.module_regler(r["societe"], mid, ouvert)
            if str(modules_de) == "1":                                  # la principale ouvre par défaut tout ce qui n'a pas été choisi : on le recopie aussi
                for m in ctx.manifestes_actifs(toutes=True):
                    if not (m.importance == "vital" or m.essentiel or m.instance) and m.id not in idt.modules_de_societe("1"):
                        idt.module_regler(r["societe"], m.id, True)
        if modeles_de and idt.societe(str(modeles_de)):                  # une société « modèle » : habillage et préfixes de la société choisie
            _recopier_modeles(r["societe"], str(modeles_de))
        _initialiser_fonctions(r["societe"])
        _histoire(r["societe"], "", "société créée", None, None)
        _emettre("societe.creee", r["societe"], {"nom": r["nom"], "administrateur": adm})
        return {"societe": r["societe"], "nom": r["nom"], "administrateur": adm}

    def prouver_creer(c, res):
        s = idt.societe(res["societe"])
        return bool(s) and not s["archivee"]

    def defaire_creer(c, res):
        for g, _, _, _ in FONCTIONS:
            gid = _gid(res["societe"], g)
            if d.groupe(gid):
                d.regler_groupe(gid, None)
        idt.societe_retirer(res["societe"])

    def renommer(c, societe="", nom=""):
        soc = _cible(societe)
        _exiger("fiche", "modifier", soc)
        avant = idt.societe(soc)["nom"]
        _poser_nom(soc, nom)
        _histoire(soc, "identite", "a renommé la société", {"nom": avant}, {"nom": nom})
        _emettre("societe.modifiee", soc, {"rubrique": "identite", "champs": ["nom"]})
        return {"societe": soc, "avant": avant, "apres": str(nom).strip()}

    def prouver_renommer(c, res):
        return idt.societe(res["societe"])["nom"] == res["apres"]

    def defaire_renommer(c, res):
        _poser_nom(res["societe"], res["avant"])

    def archiver(c, societe=""):
        _exiger_super()
        soc = str(societe or "").strip()
        r = idt.societe_archiver(soc, True)
        if not r["ok"]:
            raise ValueError(r["error"])
        _emettre("societe.archivee", soc, {})
        return {"societe": soc}

    def prouver_archiver(c, res):
        return bool(idt.societe(res["societe"])["archivee"])

    def defaire_archiver(c, res):
        idt.societe_archiver(res["societe"], False)

    def rouvrir(c, societe=""):
        _exiger_super()
        soc = str(societe or "").strip()
        r = idt.societe_archiver(soc, False)
        if not r["ok"]:
            raise ValueError(r["error"])
        return {"societe": soc}

    def prouver_rouvrir(c, res):
        return not idt.societe(res["societe"])["archivee"]

    def defaire_rouvrir(c, res):
        idt.societe_archiver(res["societe"], True)

    def historique_defaire(c, societe="", id=0):
        """Remet une rubrique comme elle était avant la modification de l'historique (jamais la banque : l'IBAN n'y est pas en clair)."""
        soc = _cible(societe)
        r = db.lire("SELECT * FROM historique WHERE id=? AND societe=?", (int(id or 0), soc))
        if not r or not r[0]["rubrique"] or not r[0]["avant"]:
            raise ValueError("cette ligne de l'historique ne se défait pas")
        h = r[0]
        spec = RUBRIQUES.get(h["rubrique"])
        if not spec or h["rubrique"] == "banque":
            raise ValueError("cette ligne de l'historique ne se défait pas : la banque se corrige à la main")
        avant = json.loads(h["avant"])
        if h["rubrique"] == "roles" and ("niveau" in avant or "fonction" in avant):
            raise ValueError("cette ligne de l'historique ne se défait pas : changez la fonction à la main")
        _exiger(spec["domaine"], spec["ecrire"], soc)
        courant = _lire_rub(soc, h["rubrique"])
        if h["rubrique"] == "identite" and avant.get("nom") and avant["nom"] != courant.get("nom"):
            _poser_nom(soc, avant["nom"])
        _ecrire_rub(soc, h["rubrique"], avant)
        _histoire(soc, h["rubrique"], "a défait : %s" % h["resume"], courant, avant)
        return {"societe": soc, "rubrique": h["rubrique"], "avant": courant, "apres": avant}

    def membres(c, societe=""):
        soc = _cible(societe)
        _exiger("equipe", "voir", soc)
        fonc = {m: f["fonction"] for f in _fonctions_de(soc) for m in f["membres"]}
        noms = {x for x in (set(idt.comptes_de_societe(soc)) | set(fonc)) if idt.est_utilisateur(x)}      # des personnes : ni les agents ni le noyau
        out = []
        for cpt in sorted(noms):
            try:
                nom = (idt.lire(cpt) or {}).get("display_name") or ""
            except Exception:
                nom = ""
            out.append({"compte": cpt, "nom": nom, "fonction": fonc.get(cpt, ""), "domicile": idt.societe_de(cpt) == soc})
        return {"societe": soc, "membres": out}

    # ── les fonctions : des groupes attachés à la société ───────────────────
    def _gid(soc, fonction):
        return "s%s.%s" % (soc, fonction)

    def _initialiser_fonctions(soc):
        """Les sept fonctions de départ, idempotent : on ne touche jamais à une fonction déjà réglée."""
        for fid, lib, desc, niveaux in FONCTIONS:
            gid = _gid(soc, fid)
            if d.groupe(gid):
                continue
            d.regler_groupe(gid, lib, desc)
            d.attacher_groupe(gid, soc)
            _appliquer_niveaux(gid, niveaux)
        _garantir_gestion(soc)

    GERENT_LES_UTILISATEURS = ("titulaire", "admin")        # ces fonctions gèrent les utilisateurs de la société (droit « comptes.gerer », valable dans la société seulement)

    def _appliquer_niveaux(gid, niveaux):
        for dm, n in zip(DOMAINES, niveaux):
            _regler_domaine(gid, dm, n)

    ECRIVENT_LE_CARNET = ("titulaire", "admin", "gestion")      # le carnet de la société : ces fonctions y écrivent (droit « contacts.societe_ecrire », valable dans la société seulement)

    def _garantir_gestion(soc):
        for f in ECRIVENT_LE_CARNET:
            gid = _gid(soc, f)
            if d.groupe(gid) and "contacts.societe_ecrire" in d.connus and d.accord("groupe", gid, "contacts.societe_ecrire") is None:
                d.regler("groupe", gid, "contacts.societe_ecrire", "accorde")
        for f in GERENT_LES_UTILISATEURS:
            gid = _gid(soc, f)
            if d.groupe(gid) and "comptes.gerer" in d.connus and d.accord("groupe", gid, "comptes.gerer") is None:
                d.regler("groupe", gid, "comptes.gerer", "accorde")

    def _regler_domaine(gid, dm, n):
        for i, nv in enumerate(NIVEAUX, 1):
            d.regler("groupe", gid, "societes.%s_%s" % (dm, nv), "accorde" if n >= i else None)

    def _niveaux_du_groupe(gid):
        out = {}
        for dm in DOMAINES:
            n = 0
            for i, nv in enumerate(NIVEAUX, 1):
                if d.accord("groupe", gid, "societes.%s_%s" % (dm, nv)) == "accorde":
                    n = i
            out[dm] = n
        return out

    def _fonctions_de(soc):
        _initialiser_fonctions(soc)
        etat = d.etat()
        membres = {g["groupe"]: g["membres"] for g in etat["groupes"]}
        out = []
        prefixe = "s%s." % soc
        for g in etat["groupes"]:
            if g["groupe"].startswith(prefixe) and d.portee_du_groupe(g["groupe"]) == soc:
                gid = g["groupe"]
                out.append({"id": gid, "fonction": gid[len(prefixe):], "nom": g["libelle"], "description": g.get("description") or "",
                            "niveaux": _niveaux_du_groupe(gid), "membres": sorted(membres.get(gid, [])), "fixe": gid == _gid(soc, "titulaire")})
        order = {f[0]: i for i, f in enumerate(FONCTIONS)}
        return sorted(out, key=lambda f: (order.get(f["fonction"], 99), f["nom"]))

    def fonctions(c, societe=""):
        soc = _cible(societe)
        _exiger("equipe", "voir", soc)
        return {"societe": soc, "fonctions": _fonctions_de(soc), "domaines": list(DOMAINES)}

    def _plafond(soc, domaine, niveau):
        """Personne n'accorde plus qu'il n'a : le niveau demandé ne dépasse pas celui qu'on détient soi-même sur ce domaine."""
        if ctx.compte and not _superadmin(ctx.compte) and niveau > _niveau(ctx.compte, domaine, soc):
            raise ValueError("on n'accorde pas plus que ce qu'on a : vous n'avez pas le niveau %d sur « %s »" % (niveau, domaine))

    def fonction_regler(c, societe="", fonction="", domaine="", niveau=0):
        soc = _cible(societe)
        _exiger("equipe", "gerer", soc)
        if domaine not in DOMAINES:
            raise ValueError("domaine : %s" % " | ".join(DOMAINES))
        n = int(niveau)
        if n < 0 or n > 3:
            raise ValueError("niveau : 0 (aucun) à 3 (gérer)")
        gid = _gid(soc, fonction)
        if not d.groupe(gid) or d.portee_du_groupe(gid) != soc:
            raise ValueError("fonction inconnue dans cette société")
        if fonction == "titulaire":
            raise ValueError("la fonction de titulaire est fixe")
        _plafond(soc, domaine, n)
        avant = _niveaux_du_groupe(gid)[domaine]
        _regler_domaine(gid, domaine, n)
        _histoire(soc, "roles", "a réglé « %s » : %s → %d" % (fonction, domaine, n), {"niveau": avant}, {"niveau": n})
        return {"societe": soc, "fonction": fonction, "domaine": domaine, "avant": avant, "apres": n}

    def prouver_fonction_regler(c, res):
        return _niveaux_du_groupe(_gid(res["societe"], res["fonction"]))[res["domaine"]] == res["apres"]

    def defaire_fonction_regler(c, res):
        _regler_domaine(_gid(res["societe"], res["fonction"]), res["domaine"], res["avant"])

    def fonction_creer(c, societe="", nom="", partir_de="membre"):
        soc = _cible(societe)
        _exiger("equipe", "gerer", soc)
        nom = str(nom or "").strip()
        if not nom or len(nom) > 80:
            raise ValueError("nom de la fonction : de 1 à 80 caractères")
        fid = re.sub(r"[^a-z0-9]+", "-", nom.lower().encode("ascii", "ignore").decode()).strip("-")[:30] or "fonction"
        _initialiser_fonctions(soc)
        base = _gid(soc, partir_de)
        if not d.groupe(base):
            raise ValueError("fonction de départ inconnue")
        n, gid = 2, _gid(soc, fid)
        while d.groupe(gid):
            gid = _gid(soc, "%s-%d" % (fid, n))
            n += 1
        niveaux = _niveaux_du_groupe(base)
        for dm, nv in niveaux.items():
            _plafond(soc, dm, nv)                                 # on ne crée pas une fonction plus puissante que soi
        d.regler_groupe(gid, nom, "Fonction créée pour cette société.")
        d.attacher_groupe(gid, soc)
        _appliquer_niveaux(gid, [niveaux[dm] for dm in DOMAINES])
        _histoire(soc, "roles", "a créé la fonction « %s »" % nom, None, None)
        return {"societe": soc, "fonction": gid[len("s%s." % soc):], "nom": nom}

    def prouver_fonction_creer(c, res):
        return bool(d.groupe(_gid(res["societe"], res["fonction"])))

    def defaire_fonction_creer(c, res):
        d.regler_groupe(_gid(res["societe"], res["fonction"]), None)

    def affecter(c, societe="", utilisateur="", fonction=""):
        soc = _cible(societe)
        _exiger("equipe", "gerer", soc)
        cible = str(utilisateur or "").strip().lower()
        if not idt.existe(cible):
            raise ValueError("compte inconnu")
        if idt.societe_de(cible) != soc and not _superadmin(ctx.compte) and ctx.compte and not idt.utilisateur_partage(cible, soc):
            raise ValueError("cet utilisateur n'est pas de cette société ni partagé avec elle : seul le superadministrateur décide d'un partage")
        _initialiser_fonctions(soc)
        gids = [f["id"] for f in _fonctions_de(soc)]
        avant = next((g for g in gids if d.membre(cible, g)), "")
        nouveau = _gid(soc, fonction) if fonction else ""
        if nouveau and nouveau not in gids:
            raise ValueError("fonction inconnue dans cette société")
        if nouveau:
            for dm, nv in _niveaux_du_groupe(nouveau).items():
                _plafond(soc, dm, nv)                             # on ne donne pas une fonction plus puissante que la sienne
        tit = _gid(soc, "titulaire")
        if avant == tit and nouveau != tit:
            if len([m for m in _fonctions_de(soc)[0]["membres"] if m != cible]) < 1:
                raise ValueError("la société garde un titulaire : désignez d'abord le suivant")
        if nouveau == tit:                                        # un seul titulaire : l'ancien devient administrateur
            for m in list(_fonctions_de(soc)[0]["membres"]):
                if m != cible:
                    d.regler_membre(m, tit, False)
                    d.regler_membre(m, _gid(soc, "admin"), True)
        for g in gids:
            if g != nouveau and d.membre(cible, g):
                d.regler_membre(cible, g, False)
        if nouveau:
            d.regler_membre(cible, nouveau, True)
        _histoire(soc, "roles", "a donné la fonction « %s » à %s" % (fonction or "aucune", cible), {"fonction": avant}, {"fonction": nouveau})
        _emettre("societe.modifiee", soc, {"rubrique": "roles", "compte": cible, "fonction": nouveau})
        return {"societe": soc, "compte": cible, "avant": avant, "apres": nouveau}

    def prouver_affecter(c, res):
        return (d.membre(res["compte"], res["apres"]) if res["apres"] else True) and (not res["avant"] or res["avant"] == res["apres"] or not d.membre(res["compte"], res["avant"]))

    def defaire_affecter(c, res):
        if res["apres"]:
            d.regler_membre(res["compte"], res["apres"], False)
        if res["avant"]:
            d.regler_membre(res["compte"], res["avant"], True)

    for cid, f in (("lister", lister), ("lire", lire), ("fiche_lire", fiche_lire), ("carte", carte), ("iban_voir", iban_voir), ("historique", historique),
                   ("echeances", echeances), ("fonctions", fonctions)):
        ctx.implementer(cid, f)
    ctx.implementer("membres", membres)
    ctx.implementer("modules", modules)
    ctx.implementer("partages", partages)
    ctx.implementer("partager", partager, prouver_partager, defaire_partager)
    ctx.implementer("partage_retirer", partage_retirer, prouver_partage_retirer, defaire_partage_retirer)
    ctx.implementer("partageables", partageables)
    ctx.implementer("module_regler", module_regler, prouver_module_regler, defaire_module_regler)
    ctx.implementer("module_demander", module_demander, prouver_demander, defaire_demander)
    ctx.implementer("vue_consolidee", vue_consolidee)
    ctx.implementer("profil_lire", profil_lire)
    ctx.implementer("profil_regler", profil_regler, prouver_profil, defaire_profil)
    ctx.implementer("modeles_recopier", modeles_recopier, prouver_modeles, defaire_modeles)
    ctx.implementer("module_demandes", module_demandes)
    ctx.implementer("module_demande_decider", module_demande_decider, prouver_decider, defaire_decider)
    ctx.implementer("fiche_regler", fiche_regler, prouver_regler, defaire_regler)
    ctx.implementer("historique_defaire", historique_defaire, prouver_regler, defaire_regler)
    ctx.implementer("creer", creer, prouver_creer, defaire_creer)
    ctx.implementer("renommer", renommer, prouver_renommer, defaire_renommer)
    ctx.implementer("archiver", archiver, prouver_archiver, defaire_archiver)
    ctx.implementer("rouvrir", rouvrir, prouver_rouvrir, defaire_rouvrir)
    ctx.implementer("fonction_regler", fonction_regler, prouver_fonction_regler, defaire_fonction_regler)
    ctx.implementer("fonction_creer", fonction_creer, prouver_fonction_creer, defaire_fonction_creer)
    ctx.implementer("affecter", affecter, prouver_affecter, defaire_affecter)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
