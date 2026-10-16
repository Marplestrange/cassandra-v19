"""La voix : ce qui est installé, le catalogue, et le choix par compte.

Porté de la V18 (`vx_*`), avec ses leçons :
  - on ne charge RIEN sur le chemin d'un écran : vérifier la présence d'un module coûte une importation,
    charger un modèle de plusieurs centaines de mégaoctets, non ;
  - la voix de chacun est PAR COMPTE : deux personnes n'entendent pas la même chose du même agent ;
  - une voix jugée « robotique » l'est souvent parce qu'elle parle trop vite pour ses moyens (le débit).

Différé proprement : l'écoute (faster-whisper), la parole (piper) et le téléchargement des voix — des modèles
lourds, par le courtier racine.
"""
from __future__ import annotations

CATALOGUE = [
    {"id": "fr_FR-gilles-low", "nom": "Gilles", "genre": "homme", "d": "grave et posée, un peu sourde"},
    {"id": "fr_FR-tom-medium", "nom": "Tom", "genre": "homme", "d": "claire et nette"},
    {"id": "fr_FR-siwis-medium", "nom": "Siwis", "genre": "femme", "d": "neutre, un peu scolaire"},
    {"id": "fr_FR-upmc-medium", "nom": "UPMC", "genre": "deux voix", "d": "Jessica (0) et Pierre (1)",
     "locuteurs": [["0", "Jessica"], ["1", "Pierre"]]},
    {"id": "fr_FR-siwis-low", "nom": "Siwis légère", "genre": "femme", "d": "la même, plus rapide et plus sourde"},
]


def brancher(ctx):
    db = ctx.stockage

    def _pref(compte):
        r = db.lire("SELECT * FROM voix_prefs WHERE compte=?", (compte,))
        return dict(r[0]) if r else None

    def ecouter(c, audio_b64="", langue="fr"):
        if not audio_b64:
            raise ValueError("aucun son reçu")
        import base64
        import os
        import tempfile
        try:
            octets = base64.b64decode(audio_b64, validate=False)
        except Exception:
            raise ValueError("audio illisible")
        if not octets:
            raise ValueError("audio vide")
        fd, chemin = tempfile.mkstemp(suffix=".webm", prefix="vx_")
        with os.fdopen(fd, "wb") as f:
            f.write(octets)
        try:
            r = ctx.racine("ecouter", [chemin, langue or "fr"], delai=300)
            if not r.get("ok"):
                raise ValueError(r.get("erreur") or "écoute impossible")
            return {"texte": (r.get("sortie") or "").strip()}
        finally:
            try:
                os.unlink(chemin)
            except Exception:
                pass

    def parler(c, texte="", voix="", locuteur="", debit=""):
        if not texte or not voix:
            raise ValueError("texte et voix requis")
        import os
        import tempfile
        fd, sortie = tempfile.mkstemp(suffix=".wav", prefix="vx_")
        os.close(fd)
        try:
            r = ctx.racine("parler", [texte, voix, sortie, locuteur or "", debit or ""], delai=300)
            if not r.get("ok"):
                raise ValueError(r.get("erreur") or "parole impossible")
            return {"chemin": sortie}
        except Exception:
            try:
                os.unlink(sortie)
            except Exception:
                pass
            raise

    def telecharger(c, voix_id=""):
        if not voix_id:
            raise ValueError("voix requise")
        r = ctx.racine("telecharger", [voix_id], delai=600)
        if not r.get("ok"):
            raise ValueError(r.get("erreur") or "téléchargement impossible")
        return {"voix_id": voix_id}

    def prouver_parler(c, res):
        import os
        return os.path.isfile(res["chemin"])

    def defaire_parler(c, res):
        import os
        try:
            os.unlink(res["chemin"])
        except Exception:
            pass

    def prouver_telecharger(c, res):
        import os
        return os.path.isdir("/usr/libexec/cassandra/voix/voix/%s" % res["voix_id"])

    def defaire_telecharger(c, res):
        import shutil
        shutil.rmtree("/usr/libexec/cassandra/voix/voix/%s" % res["voix_id"], ignore_errors=True)

    def dispo(c):
        import shutil
        ecoute, parle, quoi = False, False, []
        try:
            import faster_whisper  # noqa: F401
            ecoute = True
        except Exception:
            quoi.append("la DICTÉE demande « pip install faster-whisper »")
        try:
            import piper  # noqa: F401
            parle = True
        except Exception:
            if shutil.which("piper"):
                parle = True
            else:
                quoi.append("la LECTURE demande « pip install piper-tts » et une voix française posée")
        return {"ecoute": ecoute, "parle": parle, "quoi": quoi}

    def catalogue(c):
        return {"catalogue": CATALOGUE}

    def reglages(c):
        compte = (ctx.compte or "").strip().lower()
        p = _pref(compte) or {"voix_nom": "", "voix_locuteur": "", "voix_auto": 1, "voix_debit": "", "voix_mode": 0}
        return {"reglages": p, "catalogue": CATALOGUE}

    def choisir(c, voix_nom="", voix_locuteur="", voix_auto=None, voix_debit="", voix_mode=None):
        compte = (ctx.compte or "").strip().lower()
        if not compte:
            raise ValueError("aucun compte n'agit")
        avant = _pref(compte)
        if voix_nom and not any(v["id"] == voix_nom for v in CATALOGUE):
            raise ValueError("voix inconnue")
        actuel = avant or {"voix_nom": "", "voix_locuteur": "", "voix_auto": 1, "voix_debit": "", "voix_mode": 0}
        nouveau = {
            "voix_nom": str(voix_nom or "").strip()[:60],
            "voix_locuteur": str(voix_locuteur or "").strip()[:20],
            "voix_auto": (1 if voix_auto else 0) if voix_auto is not None else actuel.get("voix_auto", 1),
            "voix_debit": str(voix_debit or "").strip()[:20],
            "voix_mode": int(voix_mode) if voix_mode is not None else actuel.get("voix_mode", 0),
        }
        db.ecrire("INSERT INTO voix_prefs (compte, voix_nom, voix_locuteur, voix_auto, voix_debit, voix_mode) VALUES (?,?,?,?,?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET voix_nom=excluded.voix_nom, voix_locuteur=excluded.voix_locuteur, "
                  "voix_auto=excluded.voix_auto, voix_debit=excluded.voix_debit, voix_mode=excluded.voix_mode",
                  (compte, nouveau["voix_nom"], nouveau["voix_locuteur"], nouveau["voix_auto"], nouveau["voix_debit"], nouveau["voix_mode"]))
        return {"compte": compte, "avant": avant, "apres": nouveau}

    def prouver_choisir(c, res):
        p = _pref(res["compte"])
        return bool(p) and all(p.get(k) == v for k, v in (res.get("apres") or {}).items())

    def defaire_choisir(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM voix_prefs WHERE compte=?", (res["compte"],))
        else:
            a = res["avant"]
            db.ecrire("INSERT INTO voix_prefs (compte, voix_nom, voix_locuteur, voix_auto, voix_debit, voix_mode) VALUES (?,?,?,?,?,?) "
                      "ON CONFLICT(compte) DO UPDATE SET voix_nom=excluded.voix_nom, voix_locuteur=excluded.voix_locuteur, "
                      "voix_auto=excluded.voix_auto, voix_debit=excluded.voix_debit, voix_mode=excluded.voix_mode",
                      (res["compte"], a["voix_nom"], a["voix_locuteur"], a["voix_auto"], a["voix_debit"], a["voix_mode"]))

    for cid, f in (("dispo", dispo), ("catalogue", catalogue), ("reglages", reglages), ("ecouter", ecouter)):
        ctx.implementer(cid, f)
    ctx.implementer("parler", parler, prouver_parler, defaire_parler,
                    simuler=lambda x, texte="", **_: "synthétiserait « %s »" % str(texte)[:60])
    ctx.implementer("telecharger", telecharger, prouver_telecharger, defaire_telecharger,
                    simuler=lambda x, voix_id="", **_: "téléchargerait la voix « %s »" % voix_id)
    ctx.implementer("choisir", choisir, prouver_choisir, defaire_choisir,
                    simuler=lambda x, voix_nom="", **_: "choisirait la voix « %s »" % voix_nom)
