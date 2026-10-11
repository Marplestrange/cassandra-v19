"""Dictée et synthèse vocale.
V18 port : Logique 1:1, les réglages sont désormais stockés dans le contexte du module (voix_prefs / voix_machine) pour garantir le cloisonnement par compte V19.
"""

import json
import re
import time
import logging

_VX_AUDIO_MAX = 20 * 1024 * 1024
_VX_TEXTE_MAX = 4000
_VX_MODELE = "small"
_VX_MODELES = [
    ("tiny", "le plus rapide, et le moins fiable — dépannage seulement"),
    ("base", "rapide, se trompe souvent sur les noms propres"),
    ("small", "le bon compromis : nettement meilleur, ~2× plus lent"),
    ("medium", "très bon, ~5× plus lent que « small » — machine confortable"),
]
_VX_LEXIQUE = ("Conversation avec Itare, l'agent d'administration système. "
               "Vocabulaire : serveur, Cassandra, Itare, panneau, nginx, "
               "SSL, certificat, cron, sauvegarde, Telegram, coffre-fort, "
               "base de données, redémarrer, journal, domaine, vhost.")
_VX_CATALOGUE = [
    {"id": "fr_FR-gilles-low", "nom": "Gilles", "genre": "homme", "d": "grave et posée, un peu sourde", "dossier": "gilles/low"},
    {"id": "fr_FR-tom-medium", "nom": "Tom", "genre": "homme", "d": "claire et nette", "dossier": "tom/medium"},
    {"id": "fr_FR-siwis-medium", "nom": "Siwis", "genre": "femme", "d": "neutre, un peu scolaire", "dossier": "siwis/medium"},
    {"id": "fr_FR-upmc-medium", "nom": "UPMC", "genre": "deux voix", "d": "Jessica (0) et Pierre (1)", "dossier": "upmc/medium", "locuteurs": [["0", "Jessica"], ["1", "Pierre"]]},
    {"id": "fr_FR-mls-medium", "nom": "MLS", "genre": "beaucoup", "d": "des dizaines de lecteurs, qualite tres inegale — a essayer", "dossier": "mls/medium", "locuteurs": [[str(i), "voix %d" % i] for i in range(0, 12)]},
    {"id": "fr_FR-siwis-low", "nom": "Siwis legere", "genre": "femme", "d": "la meme, plus rapide et plus sourde", "dossier": "siwis/low"},
]
_VX_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR"
_VX_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\u2190-\u2BFF\uFE0F\u200D\u2022\u25A0-\u25FF]")

_VX_MOTEUR = {}
_VX_CACHE = {}
_VX_CACHE_MAX = 40

def _vx_cache_poser(cle, wav):
    # V18 : "Un cache sans borne est une fuite : quarante lectures de quelques secondes tiennent en mémoire, quatre mille non."
    try:
        _VX_CACHE[cle] = wav
        while len(_VX_CACHE) > _VX_CACHE_MAX:
            _VX_CACHE.pop(next(iter(_VX_CACHE)))
    except Exception:
        pass

def _vx_cache_cle(texte, voix, loc, deb):
    # V18 : "Oublier l'un des paramètres du cache (texte, voix, locuteur, débit) servirait l'ancien son après un changement de réglage."
    import hashlib
    return hashlib.sha1(("%s|%s|%s|%s" % (texte, voix, loc, deb)).encode("utf-8")).hexdigest()

def _vx_mots(texte):
    import unicodedata
    t = unicodedata.normalize("NFD", (texte or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [m for m in re.split(r"[^a-z0-9]+", t) if m]

def _vx_est_echo(texte, dit):
    # V18 : "Sa propre voix ne lui revient pas : l'annulation d'écho laisse un résidu. Le reconnaître aux MOTS car on sait ce qu'elle a dit."
    mots = _vx_mots(texte)
    # V18 : "Trop court pour trancher... (3 mots mini)"
    if len(mots) < 4:
        return False
    ref = " ".join(_vx_mots(dit))
    if not ref:
        return False
    vus = total = 0
    for i in range(len(mots) - 2):
        total += 1
        if " ".join(mots[i:i + 3]) in ref:
            vus += 1
    # V18 : "TROIS QUARTS, ET PAS LA MOITIÉ. À la moitié, une vraie question qui reprend ses termes passait pour un écho."
    return total > 0 and (vus / float(total)) >= 0.75

def _vx_prononcable(texte):
    # V18 : "Les emojis et la mise en forme (code, liens, astérisques, tables) sont retirés avant lecture, car ils ne se lisent pas à l'oreille et font croire à une panne."
    t = texte or ""
    t = re.sub(r"```[\s\S]*?```", " (bloc de code) ", t)
    t = re.sub(r"`([^`\n]*)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", " un lien ", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s{0,3}>\s?", "", t, flags=re.M)
    t = re.sub(r"^\s{0,3}[-*+]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*\|.*$", "", t, flags=re.M)
    t = re.sub(r"^\s*[-:| ]{4,}\s*$", "", t, flags=re.M)
    t = re.sub(r"[*_~]{1,3}", "", t)
    t = _VX_EMOJI.sub(" ", t)
    t = re.sub(r"[#`|<>{}\\^]+", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _vx_pourquoi(e):
    # V18 : "La trace complete au journal, ce qui revient a l ecran est court par necessite."
    t = ("%s %s" % (type(e).__name__, e)).lower()
    if "connect" in t or "timed out" in t or "resolve" in t or "ssl" in t:
        return "Le modèle n'a pas pu être téléchargé : le serveur n'atteint pas huggingface.co. C'est le PREMIER usage qui le télécharge ; ensuite il est en cache."
    if "no module named 'av'" in t or "libav" in t or "pyav" in t:
        return "Le décodeur audio manque : « pip install av » dans le même environnement que faster-whisper."
    if "ctranslate2" in t or "cudnn" in t or "cublas" in t or "libc" in t:
        return "Le moteur de calcul refuse de démarrer sur cette machine (ctranslate2) : %s" % str(e)[:120]
    # V18 : "Piper module : les paramètres doivent être posés AVANT d'attendre le premier morceau, sinon la fermeture lève 'channels not specified'"
    if "channels not specified" in t or "sampwidth not specified" in t or "sampling rate not specified" in t:
        return "Le moteur de lecture n'a rien produit : le fichier son s'est refermé sans avoir reçu la moindre image. Vérifiez que la voix choisie a bien ses DEUX fichiers (.onnx et .onnx.json) et qu'espeak-ng est installé."
    if "no such file" in t or "invalid data" in t or "format" in t:
        return "L'enregistrement n'a pas pu être décodé : le navigateur a produit un format que le moteur ne lit pas."
    return ""

def brancher(ctx):
    db = ctx.stockage

    def _machine_get():
        r = db.lire("SELECT modele, lexique FROM voix_machine WHERE id=1")
        return r[0] if r else {"modele": _VX_MODELE, "lexique": _VX_LEXIQUE}

    def _pref_get(compte):
        r = db.lire("SELECT * FROM voix_prefs WHERE compte=?", (compte,))
        if r:
            return dict(r[0], _existe=True)
        return {"compte": compte, "voix_nom": "", "voix_locuteur": "", "voix_debit": "1.0", "voix_mode": 0, "voix_auto": 1, "_existe": False}

    def _voix_chemin(dossier, nom):
        import os
        if nom:
            c = os.path.join(dossier, nom + ".onnx")
            if os.path.isfile(c):
                return c
        try:
            for f in sorted(os.listdir(dossier)):
                if f.endswith(".onnx"):
                    return os.path.join(dossier, f)
        except Exception:
            pass
        return ""

    def _charger(taille):
        # V18 : "Le modèle d'écoute, chargé UNE fois pour la vie du processus."
        if _VX_MOTEUR.get("m") is not None:
            return _VX_MOTEUR["m"], ""
        try:
            # V18 : "importer faster_whisper/piper coûte du temps/mémoire, ne le faire qu'au besoin (pas au niveau global)."
            from faster_whisper import WhisperModel
        except Exception:
            return None, "Le moteur d'écoute n'est pas installé sur le serveur : pip install faster-whisper"
        try:
            _VX_MOTEUR["m"] = WhisperModel(taille, device="cpu", compute_type="int8")
            return _VX_MOTEUR["m"], ""
        except Exception as e:
            logging.exception("[VOIX] ouverture du modele")
            return None, (_vx_pourquoi(e) or ("Le moteur d'écoute n'a pas pu s'ouvrir : %s" % str(e)[:160]))

    def dispo(ctx):
        import shutil
        ecoute, parle, quoi = False, False, []
        try:
            import faster_whisper
            ecoute = True
        except Exception:
            quoi.append("la DICTÉE demande « pip install faster-whisper » (quelques centaines de Mo au premier usage, puis rien)")
        try:
            import piper
            parle = True
        except Exception:
            if shutil.which("piper"):
                parle = True
            else:
                quoi.append("la LECTURE demande « pip install piper-tts » et une voix française (fr_FR-siwis-medium) posée dans %s" % (ctx.reglage("dossier_voix") or ""))
        machine = _machine_get()
        return {"ok": True, "ecoute": ecoute, "parle": parle, "modele": machine["modele"], "quoi": quoi}

    def reglages(ctx):
        import os
        dossier = ctx.reglage("dossier_voix") or "/tmp"
        posees = []
        try:
            for f in sorted(os.listdir(dossier)):
                if not f.endswith(".onnx"): continue
                ref = f[:-5]
                fiche = next((c for c in _VX_CATALOGUE if c["id"] == ref), None)
                posees.append({"id": ref, "nom": (fiche or {}).get("nom", ref), "genre": (fiche or {}).get("genre", ""), "d": (fiche or {}).get("d", ""), "locuteurs": (fiche or {}).get("locuteurs") or []})
        except Exception:
            pass
        machine = _machine_get()
        prefs = _pref_get(ctx.compte) if ctx.compte else {"voix_nom": "", "voix_locuteur": "", "voix_debit": "1.0", "voix_mode": 0, "voix_auto": 1}
        return {
            "ok": True, "posees": posees, "modele": machine["modele"],
            "modeles": [{"id": m, "d": d} for m, d in _VX_MODELES],
            "lexique": machine["lexique"],
            "catalogue": [dict(c, pose=any(p["id"] == c["id"] for p in posees)) for c in _VX_CATALOGUE],
            "choix": prefs["voix_nom"], "locuteur": prefs["voix_locuteur"],
            "debit": prefs["voix_debit"], "mode": bool(prefs["voix_mode"]),
            "auto": bool(prefs["voix_auto"]), "dossier": dossier
        }

    def choisir(ctx, nom="", locuteur="", debit="", mode=None, auto=None):
        compte = ctx.compte
        if not compte:
            raise ValueError("compte manquant")
        avant = _pref_get(compte)
        
        _nom = nom.strip() if nom is not None else ""
        if not _nom:
            # V18 : "BASCULER LE MODE DEPUIS LE CHAT n'envoie pas de voix : sans ce garde-fou le nom vide écraserait le choix"
            _nom = avant["voix_nom"]
            
        if _nom:
            import os
            dossier = ctx.reglage("dossier_voix") or "/tmp"
            if not os.path.isfile(os.path.join(dossier, _nom + ".onnx")):
                raise ValueError("Cette voix n'est pas posée sur le serveur : téléchargez-la d'abord.")
                
        _loc = str(locuteur) if locuteur else (avant["voix_locuteur"] if not nom else "")
        _d = avant["voix_debit"]
        # V18 : "LE DÉBIT... Si manquant dans choisir, on ne l'écrase pas avec 1.0 (comme pour les contacts)."
        if str(debit or "").strip():
            try: f = float(str(debit).replace(",", "."))
            except ValueError: f = 1.0
            _d = "%.2f" % min(1.8, max(0.6, f))
            
        _m = 1 if mode else 0 if mode is not None else avant["voix_mode"]
        _a = 1 if auto else 0 if auto is not None else avant["voix_auto"]
        
        db.ecrire("INSERT INTO voix_prefs (compte, voix_nom, voix_locuteur, voix_debit, voix_mode, voix_auto) "
                  "VALUES (?,?,?,?,?,?) ON CONFLICT(compte) DO UPDATE SET "
                  "voix_nom=excluded.voix_nom, voix_locuteur=excluded.voix_locuteur, "
                  "voix_debit=excluded.voix_debit, voix_mode=excluded.voix_mode, voix_auto=excluded.voix_auto",
                  (compte, _nom, _loc, _d, _m, _a))
        return {"id": compte, "avant": avant, "apres": _pref_get(compte)}

    def prouver_choisir(ctx, res):
        return _pref_get(res["id"]) == res["apres"]

    def defaire_choisir(ctx, res):
        a = res["avant"]
        if a.get("_existe"):
            db.ecrire("UPDATE voix_prefs SET voix_nom=?, voix_locuteur=?, voix_debit=?, voix_mode=?, voix_auto=? WHERE compte=?",
                      (a["voix_nom"], a["voix_locuteur"], a["voix_debit"], a["voix_mode"], a["voix_auto"], a["compte"]))
        else:
            db.ecrire("DELETE FROM voix_prefs WHERE compte=?", (a["compte"],))

    def machine_regler(ctx, modele="", lexique=None):
        _modele = modele.strip() if modele else ""
        if _modele and _modele not in [m for m, _ in _VX_MODELES]:
            raise ValueError("taille de modèle inconnue")
        avant = _machine_get()
        nouveau_modele = _modele if _modele else avant["modele"]
        nouveau_lexique = str(lexique)[:800] if lexique is not None else avant["lexique"]
        
        db.ecrire("UPDATE voix_machine SET modele=?, lexique=? WHERE id=1", (nouveau_modele, nouveau_lexique))
        # V18 : "LE MOTEUR EST OUBLIÉ : il est chargé une fois pour la vie du processus, et sans cette ligne le nouveau modèle n'aurait d'effet qu'au prochain redémarrage"
        _VX_MOTEUR["m"] = None
        logging.info("[VOIX] modele d'ecoute -> %s", nouveau_modele)
        return {"id": 1, "avant": avant, "apres": _machine_get()}

    def prouver_machine_regler(ctx, res):
        return _machine_get() == res["apres"]

    def defaire_machine_regler(ctx, res):
        a = res["avant"]
        db.ecrire("UPDATE voix_machine SET modele=?, lexique=? WHERE id=1", (a["modele"], a["lexique"]))
        _VX_MOTEUR["m"] = None

    def telecharger(ctx, ref=""):
        import os
        import urllib.request
        fiche = next((c for c in _VX_CATALOGUE if c["id"] == (ref or "")), None)
        if not fiche:
            raise ValueError("voix inconnue")
        dossier = ctx.reglage("dossier_voix")
        if not dossier:
            raise ValueError("dossier_voix non configuré")
        os.makedirs(dossier, exist_ok=True)
        base_url = "%s/%s/%s" % (_VX_HF, fiche["dossier"], fiche["id"])
        fichiers = []
        # V18 : "Téléchargement depuis HF : seulement celles du catalogue pour éviter une écriture arbitraire."
        for suffixe in (".onnx", ".onnx.json"):
            cible = os.path.join(dossier, fiche["id"] + suffixe)
            try:
                with urllib.request.urlopen(base_url + suffixe, timeout=120) as rep:
                    data = rep.read()
                if not data:
                    raise ValueError("réponse vide pour " + suffixe)
                with open(cible, "wb") as f:
                    f.write(data)
                fichiers.append(cible)
            except Exception as e:
                logging.exception("[VOIX] téléchargement de %s", fiche["id"])
                raise ValueError("Téléchargement refusé (%s) : le serveur atteint-il huggingface.co ?" % str(e)[:110])
        logging.info("[VOIX] voix posée : %s", fiche["id"])
        return {"id": fiche["id"], "avant": None, "apres": True, "fichiers": fichiers}

    def prouver_telecharger(ctx, res):
        import os
        return all(os.path.isfile(f) for f in res["fichiers"])

    def defaire_telecharger(ctx, res):
        import os
        for f in res["fichiers"]:
            if os.path.isfile(f):
                try: os.unlink(f)
                except Exception: pass

    def ecouter(ctx, octets="", langue="fr", dit=""):
        import os
        import tempfile
        if isinstance(octets, str):
            import base64
            try: b_octets = base64.b64decode(octets)
            except Exception: b_octets = octets.encode("utf-8")
        else:
            b_octets = octets
        if not b_octets:
            raise ValueError("aucun son reçu")
        # V18 : "_VX_AUDIO_MAX à 20Mo pour ne pas exploser la RAM."
        if len(b_octets) > _VX_AUDIO_MAX:
            raise ValueError("Enregistrement trop long (%d Mo) : au-delà de %d Mo il n'est pas traité ici." % (len(b_octets) // (1024 * 1024), _VX_AUDIO_MAX // (1024 * 1024)))
        
        machine = _machine_get()
        modele, err = _charger(machine["modele"])
        if err:
            raise ValueError(err)
            
        chemin = ""
        try:
            fd, chemin = tempfile.mkstemp(suffix=".webm", prefix="vx_")
            with os.fdopen(fd, "wb") as f:
                f.write(b_octets)
            # V18 : "initial_prompt donne au modèle l'orthographe des noms propres... (lexique)."
            # V18 : "condition_on_previous_text=False car sur un flux indépendant, une erreur se répète et amplifie."
            segments, info = modele.transcribe(
                chemin, language=(langue or "fr"), vad_filter=True,
                initial_prompt=(machine["lexique"] or None),
                condition_on_previous_text=False
            )
            texte = " ".join((s.text or "").strip() for s in segments).strip()
            # V18 : "Sa propre voix ne lui revient pas : l'annulation d'écho laisse un résidu. Le reconnaître aux MOTS..."
            if dit and _vx_est_echo(texte, dit):
                return {"ok": True, "texte": "", "echo": True, "duree": round(float(getattr(info, "duration", 0) or 0), 1)}
            return {"ok": True, "texte": texte, "duree": round(float(getattr(info, "duration", 0) or 0), 1)}
        except Exception as e:
            logging.exception("[VOIX] écoute")
            raise ValueError(_vx_pourquoi(e) or ("Écoute impossible : %s" % str(e)[:160]))
        finally:
            # V18 : "L'audio (fichier webm temporaire) est effacé quoi qu'il arrive (donnée personnelle laissée en clair)."
            if chemin:
                try: os.unlink(chemin)
                except Exception: pass

    def parler(ctx, texte=""):
        import os
        import io
        import shutil
        import subprocess
        import base64
        
        _brut = (texte or "").strip()
        texte_propre = _vx_prononcable(_brut)[:_VX_TEXTE_MAX]
        if not texte_propre:
            raise ValueError("rien à lire" if not _brut else "ce passage ne contient que de la mise en forme : rien à prononcer")
            
        dossier = ctx.reglage("dossier_voix")
        prefs = _pref_get(ctx.compte) if ctx.compte else {"voix_nom": "", "voix_locuteur": "", "voix_debit": "1.0"}
        
        voix = _voix_chemin(dossier, prefs.get("voix_nom"))
        if not voix:
            raise ValueError("Aucune voix installée sur le serveur. Posez un fichier .onnx (et son .json) dans %s" % dossier)
            
        _loc = prefs.get("voix_locuteur")
        _deb = prefs.get("voix_debit")
        
        _cle = _vx_cache_cle(texte_propre, voix, _loc, _deb)
        if _cle in _VX_CACHE:
            return {"ok": True, "wav_b64": base64.b64encode(_VX_CACHE[_cle]).decode("ascii")}
            
        exe = shutil.which("piper")
        if exe:
            try:
                _cmd = [exe, "--model", voix, "--output_file", "-"]
                # V18 : "Piper sans numéro de locuteur rend toujours le premier."
                if _loc not in ("", None): _cmd += ["--speaker", str(_loc)]
                # V18 : "Le débit au-dessus de 1 ralentit."
                if _deb not in ("", None): _cmd += ["--length_scale", str(_deb)]
                p = subprocess.run(_cmd, input=texte_propre.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if p.returncode == 0 and p.stdout:
                    _vx_cache_poser(_cle, p.stdout)
                    return {"ok": True, "wav_b64": base64.b64encode(p.stdout).decode("ascii")}
                raise ValueError("Piper a refusé : %s" % (p.stderr or b"").decode("utf-8", "replace")[:160])
            except Exception as e:
                logging.exception("[VOIX] lecture (binaire)")
                raise ValueError("Lecture impossible (binaire) : %s" % str(e)[:160])
                
        try:
            from piper import PiperVoice
            import wave
            v = PiperVoice.load(voix)
            tampon = io.BytesIO()
            w = wave.open(tampon, "wb")
            
            # V18 : "La fréquence (sample_rate) vient du fichier .json, sinon la voix est jouée trop vite ou trop lentement."
            _sr = 0
            try:
                with open(voix + ".json", encoding="utf-8") as _fj:
                    _sr = int((json.load(_fj).get("audio") or {}).get("sample_rate") or 0)
            except Exception: pass
            if not _sr:
                try: _sr = int(getattr(getattr(v, "config", None), "sample_rate", 0) or 0)
                except Exception: pass
            _sr = _sr or 22050
            
            # V18 : "Piper module : les paramètres doivent être posés AVANT d'attendre le premier morceau..."
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(_sr)
            try:
                # V18 : "Piper a changé de nom (synthesize_wav vs synthesize), on essaie les deux pour la compatibilité ascendante."
                if hasattr(v, "synthesize_wav"):
                    v.synthesize_wav(texte_propre, w)
                else:
                    try: _sortie = v.synthesize(texte_propre)
                    except TypeError: _sortie = v.synthesize(texte_propre, w)
                    if _sortie is not None:
                        for _m in _sortie: w.writeframes(getattr(_m, "audio_int16_bytes", _m))
            finally:
                try: w.close()
                except Exception: pass
                
            _wav = tampon.getvalue()
            # V18 : "Un WAV vide (<= 44 octets) n'est pas une réussite (navigateur silencieux). Il faut rendre la taille du texte dans l'erreur."
            if len(_wav) <= 44:
                raise ValueError("Le moteur n'a produit aucun son : %d caractères envoyés à la voix « %s », zéro image rendue. Soit la voix est incomplète, soit ce texte-là n'a rien de prononçable." % (len(texte_propre), os.path.basename(voix)))
            _vx_cache_poser(_cle, _wav)
            return {"ok": True, "wav_b64": base64.b64encode(_wav).decode("ascii")}
        except Exception as e:
            logging.exception("[VOIX] lecture (module)")
            raise ValueError(_vx_pourquoi(e) or ("Lecture impossible : %s" % str(e)[:160]))

    ctx.implementer("dispo", dispo)
    ctx.implementer("reglages", reglages)
    ctx.implementer("ecouter", ecouter)
    ctx.implementer("parler", parler)
    ctx.implementer("choisir", choisir, prouver_choisir, defaire_choisir)
    ctx.implementer("machine_regler", machine_regler, prouver_machine_regler, defaire_machine_regler)
    ctx.implementer("telecharger", telecharger, prouver_telecharger, defaire_telecharger)
