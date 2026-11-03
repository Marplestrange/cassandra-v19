# ══════════════════════════════════════════════
# TITRE      : L'hôte de processus d'un moteur de recherche
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait tourner un moteur de recherche d'Évolution (Orfan, ou un moteur externe derrière le même contrat) dans un processus à part, sans clé, sans réseau, avec un relais pour parler à un modèle.
# MÉTHODE    : une ligne JSON par message sur l'entrée et la sortie standard ; le moteur ne voit jamais un jeton : il demande un modèle au serveur, qui compte et plafonne.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
"""Le protocole de processus d'un moteur de recherche (docs/CN_EVOLUTION.md, « moteurs »).

Lancé par noyau/CN_moteurs.py : `python -I CN_moteur_hote.py <chemin de CN_orfan.py> <choix> <mémoire en octets>`.

  serveur -> moteur  {"op":"proposer","contexte":{…}}
  moteur  -> serveur {"op":"modele","prompt":"…","role":"executant"|"strategie"}     (le relais : le serveur choisit le modèle, compte, plafonne)
  serveur -> moteur  {"ok":true,"texte":"…"} | {"ok":false,"erreur":"…"}
  moteur  -> serveur {"op":"resultat","candidats":[{"texte":…,"hypothese":…}, …]} | {"op":"erreur","erreur":"…"}

Le moteur ne propose JAMAIS de mise en service : il rend du texte, le juge du noyau décide.
"""
import importlib.util
import io
import json
import os
import sys


def _limiter(octets):
    """POSIX seulement : mémoire, aucun cœur, aucun fichier écrit, peu de descripteurs, aucun nouveau processus."""
    try:
        import resource
    except Exception:
        return
    for nom, valeur in (("RLIMIT_AS", octets), ("RLIMIT_CORE", 0), ("RLIMIT_FSIZE", 0), ("RLIMIT_NOFILE", 32), ("RLIMIT_NPROC", 0)):
        try:
            resource.setrlimit(getattr(resource, nom), (valeur, valeur))
        except Exception:
            pass


def main():
    sys.dont_write_bytecode = True
    chemin, choix, memoire = sys.argv[1], sys.argv[2], int(sys.argv[3])
    entree = sys.stdin.buffer
    sortie = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 1)                  # rien de ce que le moteur écrirait ne corrompt le canal
    sys.stdin = io.StringIO("")
    sys.stdout = sys.stderr = io.StringIO()
    try:
        import signal
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    except Exception:
        pass

    def dire(obj):
        sortie.write((json.dumps(obj) + "\n").encode("ascii"))

    spec = importlib.util.spec_from_file_location("orfan_moteur", chemin)
    orfan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(orfan)                                # chargé AVANT les plafonds : l'import peut vouloir plus de mémoire que le travail
    _limiter(memoire)

    def modele(prompt, role="executant"):
        dire({"op": "modele", "prompt": str(prompt), "role": role})
        ligne = entree.readline()
        if not ligne:
            raise RuntimeError("le serveur a fermé le relais")
        rep = json.loads(ligne.decode("utf-8"))
        if not rep.get("ok"):
            raise RuntimeError(rep.get("erreur") or "le relais a refusé")
        return rep.get("texte") or ""

    if choix == "modele":
        moteur = orfan.MoteurModele(modele)
    elif choix == "les_deux":
        moteur = orfan.MoteurComposite(orfan.MoteurDeterministe(), orfan.MoteurModele(modele))
    else:
        moteur = orfan.MoteurDeterministe()

    for ligne in iter(entree.readline, b""):
        try:
            msg = json.loads(ligne.decode("utf-8"))
            if msg.get("op") != "proposer":
                dire({"op": "erreur", "erreur": "opération inconnue"})
                continue
            dire({"op": "resultat", "candidats": [c if isinstance(c, dict) else {"texte": str(c)} for c in moteur.proposer(msg["contexte"])]})
        except BaseException as e:                                # une faute du moteur se dit, elle ne tue pas le processus
            try:
                dire({"op": "erreur", "erreur": "%s : %s" % (type(e).__name__, str(e)[:300])})
            except Exception:
                return


if __name__ == "__main__":
    main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (le moteur de recherche est l'objet de l'évolution ; lui-même n'est pas évolué).
# CN : le seul pont entre un moteur et Cassandra : tout le reste passe par le contrat `proposer(contexte)`.
# LIEN : noyau/CN_moteurs.py (l'hôte côté serveur), orfan/CN_orfan.py (le moteur natif).
