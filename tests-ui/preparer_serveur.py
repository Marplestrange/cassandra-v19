"""Prépare un serveur de test ISOLÉ pour la suite Playwright, puis le lance.

Les tests d'interface écrivent (tâches, plans, réglages) et se connectent avec un compte d'essai : ils ne touchent donc JAMAIS aux données réelles.
Ce script crée un dossier de données neuf et jetable (tests-ui/.donnees-test), y inscrit le compte d'essai, puis remplace son processus par le serveur
(CN_main.py demarrer) à l'écoute sur le port d'essai.

    UI_COMPTE, UI_MDP   le compte d'essai et son mot de passe (valeurs d'essai, valables seulement dans ce dossier jetable)
    UI_PORT             le port d'écoute (9005 par défaut)

Refuse de tourner contre le dossier de données réel : un compte d'administrateur au mot de passe connu n'a rien à faire dans une vraie instance."""
import os
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
DONNEES = ICI / ".donnees-test"
COMPTE = os.environ.get("UI_COMPTE", "ui@exemple.test")
MDP = os.environ.get("UI_MDP", "Essai-UI-2026!")
PORT = os.environ.get("UI_PORT", "9005")


def main():
    if DONNEES.resolve() == (RACINE / "donnees").resolve() or os.environ.get("CASSANDRA_DONNEES"):
        sys.exit("refus : les tests d'interface ont leur propre dossier de données jetable (tests-ui/.donnees-test)")
    shutil.rmtree(DONNEES, ignore_errors=True)
    DONNEES.mkdir(parents=True)
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
    if os.name == "nt":                                  # execve y lance un enfant puis quitte : Playwright ne saurait plus l'arrêter (serveur orphelin sur le port)
        import subprocess
        sys.exit(subprocess.call([sys.executable, "CN_main.py", "demarrer"], env=env))
    os.execve(sys.executable, [sys.executable, "CN_main.py", "demarrer"], env)


if __name__ == "__main__":
    main()
