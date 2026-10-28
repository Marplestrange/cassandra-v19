# ══════════════════════════════════════════════════════════════════
# TITRE      : L'assistant de création d'un module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #702f70
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'assistant de création d'un module : un squelette valide, qui se charge, s'active et répond, que l'auteur n'a plus qu'à faire grandir.
# MÉTHODE    : écrit un dossier (manifeste, code, mode d'emploi) puis le recharge avec le chargeur du noyau : un squelette que le noyau refuserait n'est jamais rendu
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=702f70 ▼▼▼
"""Un module neuf, prêt à greffer : `python CN_main.py module nouveau mon_module --nom "Mon module"`.

Le squelette déclare une capacité de lecture (`etat`), un réglage (`message`), son importance et ce qui s'arrête sans lui ; son code se branche et répond. Rien n'est écrit
dans le dépôt du noyau : le dossier est créé où on le demande. Ensuite : `paquet construire` (avec une clé privée) en fait une archive `.cmod` que la page App Store sait installer.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import CN_manifeste as mf

_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

MANIFESTE = '''[module]
id = "{id}"
nom = "{nom}"
version = "0.1.0"
noyau_min = "0.1.0"
description = "{description}"
confiance = "local"
section = "{famille}"
importance = "{importance}"
sans = "{sans}"
# Dépendances : un identifiant, ou une plage de version. Exemples :
#   requiert = ["droits", "dns >=0.2, <1"]
# Un nom de service rendu par un autre module (fournit = ["courrier"]) se requiert de la même façon.
requiert = []
# conflits = ["un_autre_module"]      # refusé à l'activation si celui-là est actif
# suggere = ["un_module_utile"]       # facultatif : il sert sans être requis
# fournit = ["mon_service"]           # un nom de service que d'autres modules peuvent requérir

[[reglages]]
id = "message"
libelle = "Le message que ce module répond"
defaut = "Bonjour depuis {nom}"

[[droits]]
id = "utiliser"
libelle = "Utiliser le module d'essai"
defaut = true

[[capacites]]
id = "etat"
libelle = "L'état de ce module : son message et sa version"
risque = "lecture"

[permissions]
# Ce que le module DEMANDE, dit avant l'installation (la Logithèque le montre). Il n'est pas encore cloisonné : n'écrivez que ce qui est vrai.
# reseau = ["api.exemple.org"]
# ecritures = ["/var/lib/mon_module"]
'''

CODE = '''"""{nom} : un module greffé. `brancher(ctx)` est appelé à l'activation ; il déclare ce que le manifeste annonce."""


def brancher(ctx):
    def etat(ctx):
        return {{"message": ctx.reglage("message", "Bonjour"), "version": ctx.manifeste.version}}

    ctx.implementer("etat", etat)
'''

LISEZ_MOI = '''# {nom}

Un module de Cassandra, créé par `python CN_main.py module nouveau`.

- `CN_manifeste.toml` : ce que le module est (importance, ce qui s'arrête sans lui, dépendances versionnées, réglages, capacités, permissions demandées).
- `CN_module.py` : `brancher(ctx)` y relie les capacités déclarées.

Pour l'essayer : déposez le dossier dans le dossier des extensions (`donnees/extensions`), activez-le dans la Logithèque.
Pour le distribuer : `python CN_main.py paquet construire {id} --cle editeur.pem` fabrique `{id}.cmod` (signé) que la Logithèque (Boutique) examine et installe.
'''


def creer(dest, mid: str, nom: str = "", famille: str = "autres", importance: str = "optionnel", description: str = "") -> Path:
    """Crée `dest`/`mid` et rend son chemin. Refuse un identifiant mal écrit, un dossier existant, ou un squelette que le chargeur du noyau n'accepterait pas."""
    if not _ID.match(mid or ""):
        raise ValueError("identifiant invalide : lettres minuscules, chiffres et _ (2 à 41 caractères, commence par une lettre)")
    if importance not in mf.IMPORTANCES:
        raise ValueError("importance : %s" % " ou ".join(mf.IMPORTANCES))
    nom = (nom or mid.replace("_", " ").capitalize()).replace('"', "'")
    dossier = Path(dest) / mid
    if dossier.exists():
        raise ValueError("« %s » existe déjà" % dossier)
    valeurs = {"id": mid, "nom": nom, "famille": re.sub(r"[^a-z0-9_]", "", famille.lower()) or "autres", "importance": importance,
               "description": (description or "Un module de %s." % nom).replace('"', "'"), "sans": "Plus rien de ce que fait %s." % nom}
    dossier.mkdir(parents=True)
    (dossier / "CN_manifeste.toml").write_text(MANIFESTE.format(**valeurs), encoding="utf-8")
    (dossier / "CN_module.py").write_text(CODE.format(**valeurs), encoding="utf-8")
    (dossier / "CN_LISEZ-MOI.md").write_text(LISEZ_MOI.format(**valeurs), encoding="utf-8")
    try:
        m = mf.charger(dossier / "CN_manifeste.toml")
        if m.id != mid:
            raise ValueError("l'identifiant ne se relit pas")
    except Exception:
        import shutil
        shutil.rmtree(dossier, ignore_errors=True)                  # un squelette que le noyau refuserait ne reste pas
        raise
    return dossier
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : creer (le squelette d'un module), MANIFESTE, CODE, LISEZ_MOI.
# EC : néant.
# LIEN : CN_main.py (la commande `module nouveau`), noyau/CN_manifeste.py (ce que le squelette doit respecter), tests/CN_test_nouveau.py.
