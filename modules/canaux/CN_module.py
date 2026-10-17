# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les canaux Telegram
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : canaux
# ZONE       : CN
# VERSION CN : 0.1.0  #48d683
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les canaux Telegram : l'état et le miroir.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=48d683 ▼▼▼
"""Les canaux Telegram : l'état et le miroir.

Porté de la V18 (`tg_miroir_*`), avec sa leçon :
  - le miroir est ÉTEINT PAR DÉFAUT, et c'est délibéré : relier Telegram pour recevoir des alertes n'est pas
    consentir à y voir surgir ses conversations — deux usages du même canal, et confondre les deux enverrait
    chez un tiers ce que personne n'y a mis.

Différé proprement : la connexion MTProto/Telethon et la session (qui ne vit QUE dans le coffre, jamais dans
la base), l'envoi et la réception.
"""
from __future__ import annotations


def brancher(ctx):
    db = ctx.stockage

    def _miroir(compte):
        r = db.lire("SELECT miroir FROM canal_prefs WHERE compte=?", (compte,))
        return bool(r[0]["miroir"]) if r else False

    def connecter(c, session="", api_id="", api_hash=""):
        if not session:
            raise ValueError("session requise (elle vit dans le coffre)")
        if not api_id or not api_hash:
            raise ValueError("api_id et api_hash requis")
        r = ctx.racine("connecter", [str(api_id), str(api_hash)], stdin=session, delai=120)
        if not r.get("ok"):
            raise ValueError(r.get("erreur") or "connexion impossible")
        return {"identifiant": (r.get("sortie") or "").strip()}

    def etat(c):
        compte = (ctx.compte or "").strip().lower()
        return {"client": False, "connecte": False, "miroir": _miroir(compte),
                "detail": "le client Telegram (Telethon) n'est pas encore branché"}

    def miroir(c):
        compte = (ctx.compte or "").strip().lower()
        return {"miroir": _miroir(compte)}

    def miroir_ecrire(c, actif=False):
        compte = (ctx.compte or "").strip().lower()
        if not compte:
            raise ValueError("aucun compte n'agit")
        avant = _miroir(compte)
        db.ecrire("INSERT INTO canal_prefs (compte, miroir) VALUES (?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET miroir=excluded.miroir",
                  (compte, 1 if actif else 0))
        return {"compte": compte, "avant": avant, "apres": bool(actif)}

    def prouver_miroir(c, res):
        r = db.lire("SELECT miroir FROM canal_prefs WHERE compte=?", (res["compte"],))
        return bool(r[0]["miroir"]) == res["apres"]

    def defaire_miroir(c, res):
        db.ecrire("INSERT INTO canal_prefs (compte, miroir) VALUES (?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET miroir=excluded.miroir",
                  (res["compte"], 1 if res["avant"] else 0))

    for cid, f in (("etat", etat), ("miroir", miroir), ("connecter", connecter)):
        ctx.implementer(cid, f)
    ctx.implementer("miroir_ecrire", miroir_ecrire, prouver_miroir, defaire_miroir,
                    simuler=lambda x, actif=False, **_: "allumerait le miroir Telegram" if actif else "éteindrait le miroir Telegram")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
