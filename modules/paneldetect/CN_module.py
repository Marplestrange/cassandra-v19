# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Panel Detect
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : paneldetect
# ZONE       : CN
# VERSION CN : 0.2.1  #b4cac3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Panel Detect : quel panneau d'hébergement pilote cette machine, et par quel module de Cassandra.
# MÉTHODE    : des signatures de fichiers, sans rien lancer ; le module d'un panneau porte son identifiant et déclare ses routes par « <module>.routes », chacune vérifiée contre son manifeste ; les lectures sont relayées pour le compte qui demande, les gestes jamais.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.1 empreinte=b4cac3 ▼▼▼
"""Panel Detect : quel panneau d'hébergement pilote cette machine, et par quel module de Cassandra.

Le panneau s'installe AVANT Cassandra ; Cassandra n'en installe jamais. Ce module :
  - reconnaît le panneau présent par des signatures de fichiers (dossiers, commandes), sans rien lancer ni rien lire de privé ;
  - trouve le module qui le pilote : un module de la famille « hebergement » qui porte le même identifiant que le panneau
    (« fastpanel » pilote FastPanel) et déclare ses routes par sa capacité de lecture « <module>.routes » ;
  - rend ces routes : pour chaque fonction de l'hébergement (sites, bases, courrier, certificats…), la capacité qui la sert,
    et si c'est une lecture ou un geste (lu dans le manifeste du module, jamais supposé) ;
  - relaie les LECTURES (« paneldetect.lire », la même réponse que la capacité du panneau, pour le compte qui demande) ;
    un GESTE ne passe pas par lui : l'écran appelle la capacité que « paneldetect.etat » lui donne, au nom de la personne, avec sa confirmation.
Deux panneaux à la fois, ou un panneau sans module : il le dit (détecteurs) et ne choisit rien.
"""
from __future__ import annotations

import os
import shutil
import time

# Les signatures cherchées : un panneau est présent si l'un de ses chemins existe ou si l'une de ses commandes est dans le PATH.
# Elles viennent des dossiers de recherche du 12-11-2026 (docs/CN_maquette-hebergement.html) ; un panneau sans module y est quand même reconnu.
SIGNATURES = (
    ("fastpanel", "FastPanel", ("/usr/local/fastpanel2",), ("mogwai",)),
    ("hestia", "HestiaCP", ("/usr/local/hestia",), ()),
    ("cloudpanel", "CloudPanel", ("/home/clp/htdocs/app",), ("clpctl",)),
    ("cyberpanel", "CyberPanel", ("/usr/local/CyberCP",), ()),
    ("aapanel", "aaPanel", ("/www/server/panel",), ()),
    ("virtualmin", "Virtualmin", ("/etc/webmin/virtual-server",), ("virtualmin",)),
    ("ispconfig", "ISPConfig", ("/usr/local/ispconfig",), ()),
    ("froxlor", "Froxlor", ("/var/www/froxlor/lib/Froxlor/Froxlor.php", "/var/www/html/froxlor/lib/Froxlor/Froxlor.php"), ("froxlor-cli",)),
    ("plesk", "Plesk", ("/usr/local/psa",), ("plesk",)),
    ("cpanel", "cPanel", ("/usr/local/cpanel",), ()),
)
NOMS = {s[0]: s[1] for s in SIGNATURES}
# Les fonctions de l'hébergement, dans l'ordre où l'écran les montre, et les modules de Cassandra qui les demandent.
FONCTIONS = (
    ("sites", "La liste des sites", "Sites, Zones DNS, Certificats, NetBird, Panorama"),
    ("php", "Le PHP des sites", "Sites"),
    ("bases", "Les bases de données", "Bases de données, Sites"),
    ("base_creer", "Créer une base", "Bases de données"),
    ("base_supprimer", "Supprimer une base", "Bases de données"),
    ("courrier", "Les boîtes e-mail", "Gestion e-mail, Sites"),
    ("ftp", "Les comptes FTP", "Sécurité › Accès"),
    ("comptes", "Les comptes du panneau", "Sécurité › Accès, Comptes"),
    ("comptes_cles", "Les clés SSH d'un compte du panneau", "Sécurité › Accès"),
    ("avatar", "Le portrait d'un compte du panneau", "Comptes"),
    ("certificats", "Les certificats du panneau", "Certificats"),
    ("ssl_renouveler", "Émettre ou renouveler un certificat", "Certificats"),
    ("zones", "Les zones DNS servies par la machine", "Zones DNS, NetBird"),
    ("dns_enregistrer", "Ajouter un enregistrement DNS", "Zones DNS"),
    ("copies", "Les copies de sauvegarde", "Sauvegardes"),
    ("plans", "Les plans de sauvegarde", "Sauvegardes"),
    ("copies_du_plan", "Les copies d'un plan de sauvegarde", "Sauvegardes, Sites"),
    ("copie_restaurer", "Restaurer une copie", "Sauvegardes"),
    ("analyses", "Les analyses antivirus", "Sécurité › Outils, Sites"),
    ("parefeu", "Le pare-feu du panneau", "Sécurité"),
    ("parefeu_regle_poser", "Poser une règle du pare-feu du panneau", "Sécurité"),
    ("parefeu_regle_retirer", "Retirer une règle du pare-feu du panneau", "Sécurité"),
    ("parefeu_politique", "Changer la politique du pare-feu du panneau", "Sécurité"),
    ("parefeu_trancher", "Garder ou annuler une règle posée à l'essai", "Sécurité"),
    ("services", "Les services de l'hébergement", "Panorama, La machine"),
    ("audit", "L'audit : certificats, PHP, copies", "Sites, Panorama"),
    ("adresse", "L'adresse web du panneau (pour ouvrir phpMyAdmin)", "Bases de données"),
)
FONCTIONS_IDS = tuple(f[0] for f in FONCTIONS)
DUREE_ROUTES_S = 30


def presents(racine: str = "/", qui=shutil.which) -> list:
    """Les panneaux dont une signature est sur la machine : [{id, nom, preuves}]. `racine` et `qui` servent aux bancs (une machine fictive)."""
    sortie = []
    for pid, nom, chemins, commandes in SIGNATURES:
        preuves = ["dossier " + c for c in chemins if os.path.exists(os.path.join(racine, c.lstrip("/")))]
        preuves += ["commande " + c for c in commandes if qui(c)]
        if preuves:
            sortie.append({"id": pid, "nom": nom, "preuves": preuves})
    return sortie


def brancher(ctx):
    def modules_panneau(c) -> dict:
        """Les modules branchés de la famille « hebergement » (sauf celui-ci), par identifiant, avec la nature de chacune de leurs capacités."""
        sortie = {}
        for m in c.manifestes_actifs(toutes=True):
            if getattr(m, "famille", "") == "hebergement" and m.id != "paneldetect":
                sortie[m.id] = {"nom": m.nom, "version": m.version, "risques": {k.id: k.risque for k in m.capacites}}
        return sortie

    def routes_de(c, mid: str, mod: dict) -> dict:
        """Les routes que déclare le module d'un panneau, vérifiées une à une contre son manifeste : une capacité absente n'est pas une route."""
        r = c.executer_lecture(mid + ".routes")
        brut = (r or {}).get("routes") if isinstance(r, dict) else None
        sortie = {}
        for fonction, cap in (brut or {}).items():
            if fonction not in FONCTIONS_IDS or not isinstance(cap, str) or "." not in cap:
                continue
            m, nom = cap.split(".", 1)
            if m != mid or nom not in mod["risques"]:
                continue
            sortie[fonction] = {"capacite": cap, "nature": "lecture" if mod["risques"][nom] == "lecture" else "geste"}
        return sortie

    def etat(c):
        trouves = presents()
        mods = modules_panneau(c)
        panneaux = []
        for p in trouves:
            mod = mods.get(p["id"])
            panneaux.append(dict(p, module=({"id": p["id"], "nom": mod["nom"], "version": mod["version"]} if mod else None)))
        pilotes = [p for p in panneaux if p["module"]]
        # Un seul panneau piloté : il sert les routes. Deux panneaux : aucun ne les sert tant que l'administrateur n'a rien tranché (rien n'est choisi à sa place).
        pilote = pilotes[0] if len(panneaux) == 1 and pilotes else None
        routes = routes_de(c, pilote["id"], mods[pilote["id"]]) if pilote else {}
        return {
            "panneaux": panneaux,
            "pilote": pilote["id"] if pilote else "",
            "nom": pilote["nom"] if pilote else (panneaux[0]["nom"] if len(panneaux) == 1 else ""),
            "situation": ("aucun" if not panneaux else "deux" if len(panneaux) > 1 else "pilote" if pilote else "sans_module"),
            "routes": [{"fonction": f, "libelle": lib, "demandee_par": par, **(routes.get(f) or {"capacite": "", "nature": ""})} for f, lib, par in FONCTIONS],
            "modules": sorted(mods),
            "signatures": [{"id": s[0], "nom": s[1], "chemins": list(s[2]), "commandes": list(s[3]), "module": s[0] in mods} for s in SIGNATURES],
        }

    def lire(c, fonction: str = "", **args):
        """La lecture d'une fonction par le module du panneau détecté : la réponse de sa capacité, telle quelle (None si rien ne la sert)."""
        if fonction not in FONCTIONS_IDS:
            raise ValueError("fonction inconnue : « %s » (connues : %s)" % (fonction, ", ".join(FONCTIONS_IDS)))
        e = etat(c)
        r = next((x for x in e["routes"] if x["fonction"] == fonction), None)
        if not r or not r["capacite"]:
            return None                                             # aucun panneau piloté ne sert cette fonction : l'appelant fait sans
        if r["nature"] != "lecture":
            raise ValueError("« %s » est un geste : il s'appelle directement (%s), au nom de la personne, jamais relayé" % (fonction, r["capacite"]))
        return c.executer_lecture(r["capacite"], **args)

    cache = {"ts": 0.0, "routes": None}

    def route(c, fonction: str = "", **args):
        """La capacité qui sert une fonction de l'hébergement, pour que l'appelant l'appelle LUI-MÊME : {capacite, nature} (capacite vide : aucun panneau piloté ne la sert).
        Aucun droit ici : ce sont des noms, pas des données ; la lecture qui suit garde le droit du panneau, pour le même compte qu'avant. Les routes se gardent 30 s :
        la sonde de Sites en lit six par tour."""
        if fonction not in FONCTIONS_IDS:
            raise ValueError("fonction inconnue : « %s » (connues : %s)" % (fonction, ", ".join(FONCTIONS_IDS)))
        signature = tuple(sorted(p["id"] for p in presents()))                      # un panneau qui apparaît ou disparaît vide le cache tout de suite
        if cache["routes"] is None or cache.get("signature") != signature or time.time() - cache["ts"] > DUREE_ROUTES_S:
            vues = etat(c)["routes"]
            cache["routes"], cache["ts"], cache["signature"] = ({x["fonction"]: x for x in vues if x["capacite"]} or None), time.time(), signature
        r = (cache["routes"] or {}).get(fonction)
        return {"capacite": r["capacite"], "nature": r["nature"]} if r else {"capacite": "", "nature": ""}

    def det_deux(c):
        p = presents()
        if len(p) < 2:
            return []
        noms = " et ".join(x["nom"] for x in p)
        return [{"objet": ("panneau", "deux"), "niveau": "avoir", "titre": "Deux panneaux d'hébergement sur la machine : %s" % noms,
                 "detail": "Ils écrivent tous deux la configuration du serveur web et de PHP : l'un peut défaire l'autre. Aucun n'est piloté tant qu'un seul ne reste."}]

    def det_sans_module(c):
        p = presents()
        if len(p) != 1:
            return []
        mods = modules_panneau(c)
        if p[0]["id"] in mods:
            return []
        return [{"objet": ("panneau", p[0]["id"]), "niveau": "info", "titre": "%s est installé, sans module de Cassandra pour le piloter" % p[0]["nom"],
                 "detail": "Cassandra lit la machine telle quelle et n'agit pas à la place du panneau. Preuves : %s." % ", ".join(p[0]["preuves"])}]

    ctx.implementer("etat", etat)
    ctx.implementer("lire", lire)
    ctx.implementer("route", route)
    ctx.detecteur("deux_panneaux", det_deux)
    ctx.detecteur("panneau_sans_module", det_sans_module)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : presents, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/fastpanel/CN_module.py (ROUTES) ; tests/CN_test_paneldetect.py ; interface/CN_paneldetect-ecran.js
