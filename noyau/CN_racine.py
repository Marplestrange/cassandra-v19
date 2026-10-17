"""La racine : ce qu'un module demande au courtier (root) quand le noyau, sans privilège, ne peut pas le faire lui-même.

La règle qui rend cela sûr : le noyau ne dit jamais QUOI exécuter, seulement quelle commande NOMMÉE d'un module, avec quels arguments.
La commande est un petit programme que le script d'INSTALLATION du module (celui que l'administrateur a lancé en root, en connaissance de cause) a posé
dans /usr/libexec/cassandra/<module>/<commande>, qui appartient à root et que le noyau ne peut pas modifier. Le courtier (exploitation/CN_courtier.py) ne lance
que cela, sans shell, avec les arguments en simples chaînes ; chaque programme valide ses propres arguments (c'est lui qui sait ce qu'il peut casser).
Le résultat revient par un fichier que le courtier écrit et que le noyau relit.

Un module qui n'a pas posé son programme obtient « commande absente » : aucune installation silencieuse, aucune élévation par une mise à jour du noyau.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time

RE_NOM = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
ARGS_MAX = 40
ARG_TAILLE_MAX = 4096
STDIN_MAX = 65536
DELAI_MAX = 300


def valider(module: str, commande: str, args, stdin, delai):
    """Une demande bien formée, ou ValueError. Pure : le courtier refait EXACTEMENT ce contrôle de son côté."""
    if not RE_NOM.match(str(module)) or not RE_NOM.match(str(commande)):
        raise ValueError("nom de module ou de commande illisible")
    if not isinstance(args, (list, tuple)) or len(args) > ARGS_MAX:
        raise ValueError("au plus %d arguments" % ARGS_MAX)
    propres = []
    for a in args:
        a = str(a)
        if "\x00" in a or len(a) > ARG_TAILLE_MAX:
            raise ValueError("argument illisible (octet nul, ou plus de %d signes)" % ARG_TAILLE_MAX)
        propres.append(a)
    if stdin is not None:
        stdin = str(stdin)
        if len(stdin) > STDIN_MAX:
            raise ValueError("entrée standard trop longue (%d signes au plus)" % STDIN_MAX)
    d = 30 if delai is None else int(delai)
    if not 1 <= d <= DELAI_MAX:
        raise ValueError("délai entre 1 et %d secondes" % DELAI_MAX)
    return propres, stdin, d


class Racine:
    def __init__(self, dossier):
        self.dossier = dossier                      # le dossier des demandes au courtier ; les résultats sont dans <dossier>/resultats
        self.pause = 0.2                            # l'attente entre deux relectures du résultat (un banc la raccourcit)

    def demander(self, module: str, commande: str, args=(), stdin=None, delai: int = 30) -> dict:
        """Dépose la demande et attend le résultat. -> {ok, code, sortie, erreur} ; jamais d'exception pour un échec de la commande ou du courtier."""
        args, stdin, delai = valider(module, commande, args, stdin, delai)
        if not self.dossier:
            return {"ok": False, "code": None, "sortie": "", "erreur": "pas de courtier sur cette installation"}
        os.makedirs(os.path.join(self.dossier, "resultats"), exist_ok=True)
        ident = "%d-%s" % (int(time.time()), secrets.token_hex(6))
        tmp = os.path.join(self.dossier, "racine-%s.tmp" % ident)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"action": "racine", "id": ident, "module": module, "commande": commande, "args": args, "stdin": stdin, "delai": delai}, f)
        os.replace(tmp, os.path.join(self.dossier, "racine-%s.json" % ident))
        resultat = os.path.join(self.dossier, "resultats", ident + ".json")
        fin = time.time() + delai + 15              # le délai de la commande, plus de quoi réveiller le courtier
        while time.time() < fin:
            if os.path.exists(resultat):
                try:
                    with open(resultat, encoding="utf-8") as f:
                        r = json.load(f)
                except (OSError, ValueError):
                    time.sleep(self.pause)
                    continue
                try:
                    os.unlink(resultat)
                except OSError:
                    pass
                return {"ok": bool(r.get("ok")), "code": r.get("code"), "sortie": str(r.get("sortie") or ""), "erreur": str(r.get("erreur") or "")}
            time.sleep(self.pause)
        return {"ok": False, "code": None, "sortie": "", "erreur": "le courtier n'a pas répondu (est-il actif ? systemctl status cassandra-courtier.path)"}
