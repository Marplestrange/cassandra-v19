"""Serveur d'essai DURABLE pour regarder l'interface à la main : mêmes comptes et mêmes réglages que preparer_serveur.py, mais le dossier de données (tests-ui/.donnees-dev) n'est jamais effacé, donc une session ouverte survit à un redémarrage.

    python tests-ui/serveur_dev.py        écoute sur 127.0.0.1:9005 (UI_PORT pour en changer)
"""
import os
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
DONNEES = ICI / ".donnees-dev"
COMPTE = os.environ.get("UI_COMPTE", "ui@exemple.test")
MDP = os.environ.get("UI_MDP", "Essai-UI-2026!")
PORT = os.environ.get("UI_PORT", "9005")


def main():
    if DONNEES.resolve() == (RACINE / "donnees").resolve() or os.environ.get("CASSANDRA_DONNEES"):
        sys.exit("refus : ce serveur a son propre dossier de données (tests-ui/.donnees-dev)")
    neuf = not DONNEES.exists()
    DONNEES.mkdir(parents=True, exist_ok=True)
    if neuf:
        sys.path.insert(0, str(RACINE))
        import CN_main as moteur
        n = moteur.Noyau(DONNEES)
        n.brancher(annoncer=False)
        r = n.identite.creer(COMPTE, MDP)
        if isinstance(r, dict) and r.get("ok") is False:
            sys.exit("le compte d'essai n'a pas pu être créé : %s" % r)
        n.droits.regler_admin(COMPTE, True)
        n.arreter()
    env = dict(os.environ, CASSANDRA_DONNEES=str(DONNEES), CASSANDRA_ECOUTE="127.0.0.1:" + PORT)
    os.chdir(RACINE)
    sys.exit(subprocess.call([sys.executable, "CN_main.py", "demarrer"], env=env))


if __name__ == "__main__":
    main()
