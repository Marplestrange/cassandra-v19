# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le travailleur d'une EC
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #da8928
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le travailleur d'une EC : un processus à part, sans rien du serveur, qui charge UNE EC et répond à des lignes JSON.
# MÉTHODE    : un processus lancé en mode isolé (-I), environnement vidé, mémoire plafonnée (POSIX), stdout détourné ; il relit la cage de CN_points (pureté, builtins restreints) et répond à des lignes JSON ; le serveur le tue au délai.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=da8928 ▼▼▼
"""Le travailleur d'une EC : un processus à part, sans rien du serveur, qui charge UNE EC et répond à des lignes JSON.

Lancé par noyau/CN_points.py avec `python -I CN_ec_worker.py <CN_points.py> <mémoire en octets>`. Il ne partage avec le serveur ni mémoire, ni clés, ni descripteurs :
une EC qui boucle, qui dévore la mémoire ou qui s'échappe de sa cage ne touche que ce processus, que le serveur tue au délai.

Protocole (une ligne JSON par message, ASCII) :
  {"op":"charger","texte":…,"fonction":…}                 -> {"ok":true} | {"ok":false,"erreur":…}
  {"op":"appeler","entree":…}                              -> {"ok":true,"sortie":…} | {"ok":false,"erreur":…}
  {"op":"chrono","ref":…,"cand":…,"fonction":…,"entrees":[…],"passes":n} -> {"ok":true,"t":[[ref,cand,ref2] par entrée]}   (le chronométrage à froid, DANS ce processus)
"""
import importlib.util
import io
import json
import os
import sys
import time
import types


def _limiter(octets):
    try:
        import resource                                          # POSIX seulement : sous Windows le délai tient seul la garde
        resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    except Exception:
        pass


def _points(chemin):
    spec = importlib.util.spec_from_file_location("cn_points_cage", chemin)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cn_points_cage"] = mod
    spec.loader.exec_module(mod)
    return mod


def _charger(P, texte, fonction):
    fautes = P.analyser_purete(texte)
    if fautes:
        raise ValueError("impure : " + " ; ".join(fautes[:3]))
    mod = types.ModuleType("cassandra_ec")
    P.executer_ec(texte, "<candidat>", mod.__dict__)
    return getattr(mod, fonction)


def _chrono(P, msg):
    passes = max(1, int(msg.get("passes", 1)))
    entrees = msg["entrees"]
    meilleur = {}
    for p in range(passes):
        ref_a, ref_b = _charger(P, msg["ref"], msg["fonction"]), _charger(P, msg["ref"], msg["fonction"])
        cand = _charger(P, msg["cand"], msg["fonction"])
        appelants = [("ref", ref_a), ("cand", cand), ("ref2", ref_b)]
        for i, entree in enumerate(entrees):
            k = (p + i) % 3
            for nom, f in appelants[k:] + appelants[:k]:
                e = P._copie(entree)
                t0 = time.perf_counter_ns()
                f(e)
                d = (time.perf_counter_ns() - t0) / 1e6
                cle = (i, nom)
                if cle not in meilleur or d < meilleur[cle]:
                    meilleur[cle] = d
    return [[meilleur[(i, "ref")], meilleur[(i, "cand")], meilleur[(i, "ref2")]] for i in range(len(entrees))]


def main():
    chemin_points, memoire = sys.argv[1], int(sys.argv[2])
    entree = sys.stdin.buffer
    sortie = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 1)                  # rien de ce que l'EC ou une bibliothèque écrirait ne corrompt le canal
    sys.stdin = io.StringIO("")                                   # une bibliothèque qui lit « l'entrée standard » (shlex.shlex(None)) trouve une entrée vide, jamais le canal du serveur
    sys.stdout = sys.stderr = io.StringIO()
    _limiter(memoire)
    P = _points(chemin_points)
    f = None

    def repondre(obj):
        sortie.write((json.dumps(obj) + "\n").encode("ascii"))

    for ligne in iter(entree.readline, b""):
        try:
            msg = json.loads(ligne.decode("utf-8"))
            op = msg.get("op")
            if op == "charger":
                f = _charger(P, msg["texte"], msg["fonction"])
                repondre({"ok": True})
            elif op == "appeler":
                repondre({"ok": True, "sortie": P._copie(f(P._copie(msg["entree"])))})
            elif op == "chrono":
                repondre({"ok": True, "t": _chrono(P, msg)})
            else:
                repondre({"ok": False, "erreur": "opération inconnue"})
        except BaseException as e:                                # une faute de l'EC (jusqu'à un dépassement de mémoire) se dit, elle ne tue pas le travailleur
            try:
                repondre({"ok": False, "erreur": "%s : %s" % (type(e).__name__, str(e)[:300])})
            except Exception:
                return


if __name__ == "__main__":
    main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _limiter, _points, _charger, _chrono, main
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : noyau/CN_points.py (_Travailleur, HoteProcessus, CandidatIsole : qui le lance et le tue), noyau/CN_evaluateur.py (le chronométrage à froid y a lieu), tests/CN_test_evolution_audit.py.
