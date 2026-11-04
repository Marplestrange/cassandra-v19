# ══════════════════════════════════════════════
# TITRE      : L'hôte de processus d'un moteur de recherche
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #8c5801
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait tourner un moteur de recherche d'Évolution (Orfan, ou un moteur externe derrière le même contrat) dans un processus à part, sans clé, sans réseau, avec un relais pour parler à un modèle.
# MÉTHODE    : une ligne JSON par message sur l'entrée et la sortie standard ; le moteur ne voit jamais un jeton : il demande un modèle au serveur, qui compte et plafonne.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8c5801 ▼▼▼
"""Le protocole de processus d'un moteur de recherche (docs/CN_EVOLUTION.md, « moteurs »).

Lancé par noyau/CN_moteurs.py : `python -I CN_moteur_hote.py <chemin de CN_orfan.py> <choix> <mémoire en octets>`.

  choix : deterministe | modele | les_deux (Orfan) · evolutif | frugal (orfan/CN_evolutif.py, CN_frugal.py) · adaptateur:<module> (un moteur externe, son module expose proposer(contexte, modele))

  serveur -> moteur  {"op":"proposer","contexte":{…}}
  moteur  -> serveur {"op":"modele","prompt":"…","role":"executant"|"strategie"}     (le relais : le serveur choisit le modèle, compte, plafonne)
  serveur -> moteur  {"ok":true,"texte":"…"} | {"ok":false,"erreur":"…"}
  moteur  -> serveur {"op":"partiel","candidats":[…]}      (facultatif : ce qui est déjà prouvé ; si le délai tombe avant le résultat, le serveur rend le dernier partiel au lieu de tout perdre)
  moteur  -> serveur {"op":"resultat","candidats":[{"texte":…,"hypothese":…}, …]} | {"op":"erreur","erreur":"…"}

Le moteur ne propose JAMAIS de mise en service : il rend du texte, le juge du noyau décide.
"""
import importlib.util
import io
import json
import os
import sys


def _limiter(octets, externe=False):
    """POSIX seulement : mémoire, aucun cœur, descripteurs comptés. Un moteur de la maison n'écrit aucun fichier et ne lance rien ; un moteur EXTERNE écrit dans son dossier privé (64 Mo au plus) et a
    besoin de fils et de processus (le bac, lui, le coupe du réseau et du reste du serveur : RLIMIT_NPROC compte les processus de l'utilisateur, pas ceux du bac)."""
    try:
        import resource
    except Exception:
        return
    plafonds = [("RLIMIT_AS", octets * (4 if externe else 1)), ("RLIMIT_CORE", 0), ("RLIMIT_FSIZE", 64 * 1024 * 1024 if externe else 0), ("RLIMIT_NOFILE", 256 if externe else 32)]
    if not externe:
        plafonds.append(("RLIMIT_NPROC", 0))
    for nom, valeur in plafonds:
        try:
            resource.setrlimit(getattr(resource, nom), (valeur, valeur))
        except Exception:
            pass


class _RelaisHTTP:
    """Un serveur compatible « OpenAI » (POST /v1/chat/completions) sur 127.0.0.1, DANS la cage : les moteurs externes (OpenEvolve, ShinkaEvolve, GEPA…) parlent ce dialecte, jamais à l'extérieur.
    Chaque requête devient une demande de modèle au serveur de Cassandra, par le canal du relais : un seul appel à la fois (le canal est une ligne)."""

    def __init__(self, modele):
        import http.server
        import threading
        verrou = threading.Lock()

        class Gestionnaire(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                try:
                    corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8"))
                    messages = corps.get("messages") or []
                    prompt = "\n\n".join(("%s :\n%s" % (m.get("role", "user"), m.get("content", ""))) if len(messages) > 1 else str(m.get("content", "")) for m in messages)
                    with verrou:
                        texte = modele(prompt, "strategie" if corps.get("model") == "strategie" else "executant")
                    rep = {"id": "relais", "object": "chat.completion", "model": corps.get("model", "relais"), "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": texte}}],
                           "usage": {"prompt_tokens": max(1, len(prompt) // 4), "completion_tokens": max(1, len(texte) // 4), "total_tokens": max(1, (len(prompt) + len(texte)) // 4)}}
                    code = 200
                except Exception as e:
                    rep, code = {"error": {"message": str(e)[:300], "type": "relais"}}, 502
                octets = json.dumps(rep).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(octets)))
                self.end_headers()
                self.wfile.write(octets)

        self.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self.url = "http://127.0.0.1:%d/v1" % self.serveur.server_address[1]
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()


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

    def modele(prompt, role="executant"):
        dire({"op": "modele", "prompt": str(prompt), "role": role})
        ligne = entree.readline()
        if not ligne:
            raise RuntimeError("le serveur a fermé le relais")
        rep = json.loads(ligne.decode("utf-8"))
        if not rep.get("ok"):
            raise RuntimeError(rep.get("erreur") or "le relais a refusé")
        return rep.get("texte") or ""

    dossier = os.path.dirname(os.path.abspath(chemin))
    externe = False

    def frere(nom, fichier):
        sp = importlib.util.spec_from_file_location(nom, os.path.join(dossier, fichier))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    if choix == "modele":
        moteur = orfan.MoteurModele(modele)
    elif choix == "les_deux":
        moteur = orfan.MoteurComposite(orfan.MoteurDeterministe(), orfan.MoteurModele(modele))
    elif choix == "evolutif":
        moteur = frere("orfan_evolutif", "CN_evolutif.py").MoteurEvolutif(orfan, modele)
    elif choix == "frugal":
        moteur = frere("orfan_frugal", "CN_frugal.py").MoteurFrugal(orfan, modele)
    elif choix.startswith("adaptateur:"):                        # un moteur externe : un module de son environnement, `proposer(contexte, modele) -> candidats`
        sys.path.insert(0, os.path.join(dossier, "adaptateurs"))
        adaptateur = importlib.import_module(choix.split(":", 1)[1])
        externe = True
        relais = _RelaisHTTP(modele)                                 # un « serveur OpenAI » dans la cage, sur la boucle locale : le moteur n'a que lui pour parler à un modèle
        modele.url, modele.cle, modele.nom = relais.url, "relais-sans-cle", "relais"

        class _Externe:
            def proposer(self, contexte):
                return adaptateur.proposer(contexte, modele)
        moteur = _Externe()
    else:
        moteur = orfan.MoteurDeterministe()
    _limiter(memoire, externe)                                    # les plafonds viennent APRÈS les imports : charger un moteur peut vouloir plus de mémoire que travailler

    moteur.emettre = lambda candidats: dire({"op": "partiel", "candidats": [c for c in candidats if isinstance(c, dict)]})        # un moteur qui le veut dit au fur et à mesure ce qu'il a déjà prouvé

    for ligne in iter(entree.readline, b""):
        try:
            msg = json.loads(ligne.decode("utf-8"))
            if msg.get("op") != "proposer":
                dire({"op": "erreur", "erreur": "opération inconnue"})
                continue
            candidats = [c if isinstance(c, dict) else {"texte": str(c)} for c in moteur.proposer(msg["contexte"])]
            dire({"op": "resultat", "candidats": candidats, "memoire": list(getattr(moteur, "fiches", None) or [])})        # ce que le moteur a appris : le serveur le nettoie et le garde sur le disque
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
