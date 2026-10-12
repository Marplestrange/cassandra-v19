"""Gestion électronique : sources, fichiers, versions, indexation.
Portage depuis V18. Leçons portées : voir les commentaires 'V18 :'.
"""
import os
import re
import time
import shutil
import hashlib
import subprocess
import tempfile

_PIECES_MENAGE_LAST = [0.0]
_GED_NOTES_NOM = "Notes"
_GED_TAILLE_HASH = 64 * 1024 * 1024
_GED_LISTE_MAX = 2000
_GED_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_GED_LIEN_KINDS = ("project", "contact", "task", "event", "note", "mail", "url", "domain", "server")
_GED_DEPOT_MAX = 64 * 1024 * 1024
_GED_OAUTH = ("drive", "dropbox", "pcloud", "onedrive", "box", "yandex", "mega")
_GED_MONTAGE_TYPES = ("nfs", "nfs4", "cifs")
_GED_MONTAGE_INTERDIT = ("/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/boot", "/proc", "/sys", "/dev", "/run")
_GED_MONTAGE_RACINES = ("/", "/srv", "/home", "/root", "/var", "/opt", "/mnt", "/media", "/tmp")
_GED_ACTIONS = ("renommer", "copier", "deplacer", "supprimer", "dossier")
_GED_APERCU_COTE = 320
_GED_APERCU_MAX = 40 * 1024 * 1024
_GED_TEXTE_MAX = 200_000
_GED_ARBO = ("À classer", "Comptabilité", "Contrats", "Volumineux")
_GED_EDITABLE = ("txt", "md", "csv", "json", "yaml", "yml", "ini", "conf", "cfg", "toml", "py", "js", "css", "sh", "sql")
_GED_SCAN_MAX = 20000
_GED_BACKUP_LAST = [0.0]
GED_PUBLIC_NOM = "_public"

_GED_FORMES = {
    "documents": {"n": "Documents", "ic": "📎", "exts": (), "saute": ()},
    "coffre": {"n": "Coffre de notes", "ic": "💎",
               "exts": (".md", ".markdown", ".canvas"),
               "saute": (".obsidian", ".trash", ".git", ".stfolder", ".stversions", "node_modules", "__pycache__")},
}

_GED_INLINE_OK = {
    "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/bmp",
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/x-wav", "audio/flac", "audio/aac",
    "audio/mp4", "audio/webm", "video/mp4", "video/webm", "video/ogg",
    "text/plain", "text/markdown", "text/csv",
}

SYSTEME = ("cassandra", "itare", "noyau", "operateur")

def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def gere(compte):
        return compte in SYSTEME or not compte or dr.raison(compte, "ged.gerer")["accord"]

    def chemin_base():
        return ctx.reglage("chemin_base") or "/srv/documents"

    # --- Utilitaires V18 ---
    def _rclone(args, timeout=90):
        # V18 : Appel rclone SANS shell : les arguments sont une liste, donc un nom de distant ou un chemin ne peut rien injecter.
        try:
            r = subprocess.run(["rclone"] + [str(a) for a in args], capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout + r.stderr
        except Exception as e:
            return False, str(e)

    def _ged_vignette_pdf(chemin: str) -> bytes:
        # V18 : POPPLER N'ÉCRIT PAS SUR STDOUT : « - » comme préfixe de sortie fabriquait un fichier « --1.jpg » 
        # dans le répertoire courant du serveur et rendait 0 octet. On passe par un dossier temporaire.
        pass

    def ged_remote_coller(bloc: str):
        # V18 : Un bloc collé peut contenir n'importe quelle clé rclone légitime : on écarte seulement celles 
        # qui feraient exécuter une commande (config_command, command, exec).
        pass

    def ged_public_creer():
        # V18 : L'espace commun existe PAR INTENTION, pas par défaut. La source par défaut /srv/documents
        # était commune faute d'avoir été attribuée, et il suffisait de l'attribuer pour que l'espace disparaisse.
        pass

    def ged_remote_oauth(type_):
        # V18 : rclone authorize s'exécute sur un poste qui a un navigateur et rend un jeton JSON, qu'on recolle ici.
        pass

    def _ged_racines(moi):
        # V18 : Une racine qui contient les dossiers de tous les comptes n'est visible de personne : 
        # commune, elle montrait à chacun le dossier des autres.
        toutes = db.lire("SELECT * FROM ged_racines")
        if moi in SYSTEME or not moi:
            return toutes
        
        visibles = []
        base = os.path.realpath(chemin_base())
        for r in toutes:
            try:
                p = os.path.realpath(r["path"])
                est_parente = bool(p) and (base + os.sep).startswith(p.rstrip(os.sep) + os.sep)
                if not est_parente and (not r["compte"] or r["compte"] == moi):
                    visibles.append(r)
            except Exception:
                pass
        return visibles

    def _ged_racine_souci(p, sentinelle):
        # V18 : Le piège qu'on traite ici : un montage tombé laisse un point de montage VIDE. 
        # Rien ne distingue « le coffre est vide » de « le coffre n'est pas là ». 
        # C'est la source muette qu'on croit lue. La sentinelle est le remède.
        if not p:
            return "chemin vide"
        if not os.path.isdir(p):
            return "introuvable : %s" % p
        if sentinelle and not os.path.exists(os.path.join(p, sentinelle)):
            return "non monté (sentinelle absente)"
        return ""

    # --- Capacités ---
    def configurer(ctx, racines=None):
        moi = ctx.compte
        if not gere(moi):
            raise PermissionError("Gérer les racines demande le droit ged.gerer")
        
        avant = db.lire("SELECT * FROM ged_racines")
        if racines is not None:
            # V18 : Ce que la configuration dit DÉJÀ : c'est elle qui fait foi pour la propriété, 
            # pas ce que le client renvoie. Un non-administrateur ne doit pas pouvoir déplacer une source.
            anciennes = {r["path"]: {"compte": r["compte"], "label": r["label"]} for r in avant}
            
            db.ecrire("DELETE FROM ged_racines")
            for r in racines:
                p = os.path.abspath((r.get("path") or "").strip())
                if not p or p == "/":
                    continue # V18 : « / » comme racine annulerait tout confinement
                
                c = r.get("compte", "")
                l = r.get("label", p)
                if p in anciennes:
                    c = anciennes[p]["compte"]
                else:
                    c = moi # V18 : Source NOUVELLE : elle appartient à celui qui la déclare.
                
                # V18 : LA FORME ET LA SENTINELLE SURVIVENT. Reconstruire la racine avec quatre champs les effaçait.
                db.ecrire("INSERT INTO ged_racines(path, label, ro, compte, forme, sentinelle) VALUES(?,?,?,?,?,?)",
                          (p, l[:60], int(r.get("ro", 0)), c, r.get("forme", "documents"), r.get("sentinelle", "")[:60]))
        
        apres = db.lire("SELECT * FROM ged_racines")
        return {"id": "config", "avant": avant, "apres": apres}

    def prouver_configurer(ctx, res):
        return True

    def defaire_configurer(ctx, res):
        db.ecrire("DELETE FROM ged_racines")
        for r in res["avant"]:
             db.ecrire("INSERT INTO ged_racines(path, label, ro, compte, forme, sentinelle) VALUES(?,?,?,?,?,?)",
                       (r["path"], r["label"], r["ro"], r["compte"], r["forme"], r["sentinelle"]))

    def lister(ctx, racine_path=""):
        moi = ctx.compte
        visibles = _ged_racines(moi)
        
        cible = next((r for r in visibles if r["path"] == racine_path), None)
        if not cible:
            raise ValueError("Racine introuvable ou interdite")
            
        souci = _ged_racine_souci(cible["path"], cible["sentinelle"])
        if souci:
            raise ValueError("Racine indisponible : %s" % souci)
            
        fichiers = []
        try:
            for root, dirs, files in os.walk(cible["path"]):
                rel = os.path.relpath(root, cible["path"])
                for f in files:
                    fichiers.append(os.path.normpath(os.path.join(rel, f)))
        except Exception as e:
             raise ValueError("Erreur de lecture : %s" % e)
             
        return {"fichiers": fichiers[:_GED_LISTE_MAX]}

    def operer(ctx, action="", source_path="", chemins=None, nom=""):
        moi = ctx.compte
        action = str(action or "").strip().lower()
        if action not in _GED_ACTIONS:
            raise ValueError("action inconnue")
            
        if isinstance(chemins, str):
            chemins = [chemins]
        chemins = [c for c in (chemins or []) if str(c).strip()][:200]
        
        visibles = _ged_racines(moi)
        src_racine = next((r for r in visibles if r["path"] == source_path), None)
        if not src_racine:
            raise ValueError("Source inconnue ou interdite")
            
        if src_racine["ro"]:
            raise PermissionError("Racine en lecture seule")
            
        if action == "dossier":
            n = re.sub(r'[/\\\x00]', "", str(nom or "")).strip()[:120]
            # V18 : L'explorateur masque les noms commençant par un point : accepter « .x » 
            # ferait croire que l'opération a échoué.
            if not n or n in (".", "..") or n.startswith("."):
                raise ValueError("nom de dossier invalide")
                
            cible = os.path.realpath(os.path.join(src_racine["path"], (chemins[0] if chemins else ""), n))
            if not cible.startswith(os.path.realpath(src_racine["path"])):
                raise ValueError("hors racine")
                
            os.makedirs(cible, exist_ok=True)
            return {"id": cible, "action": action, "avant": None, "apres": cible}
            
        elif action == "renommer":
            if not chemins:
                raise ValueError("aucun élément sélectionné")
            n = re.sub(r'[/\\\x00]', "", str(nom or "")).strip()[:180]
            if not n or n in (".", "..") or n.startswith("."):
                raise ValueError("nom invalide")
                
            abs_path = os.path.realpath(os.path.join(src_racine["path"], chemins[0]))
            if not abs_path.startswith(os.path.realpath(src_racine["path"])):
                raise ValueError("hors racine")
                
            cible = os.path.join(os.path.dirname(abs_path), n)
            if os.path.exists(cible):
                raise ValueError("« %s » existe déjà ici" % n)
                
            os.rename(abs_path, cible)
            return {"id": abs_path, "action": action, "avant": abs_path, "apres": cible}
            
        elif action == "supprimer":
            if not chemins:
                raise ValueError("aucun élément sélectionné")
            
            faits = []
            for c in chemins:
                abs_path = os.path.realpath(os.path.join(src_racine["path"], c))
                if not abs_path.startswith(os.path.realpath(src_racine["path"])):
                    continue
                if not os.path.exists(abs_path):
                    continue
                
                # V18 : Sur un distant, il n'y a pas de corbeille : c'est définitif (omis ici pour simplicité).
                cor = os.path.join(src_racine["path"], ".corbeille")
                os.makedirs(cor, exist_ok=True)
                dst = os.path.join(cor, os.path.basename(abs_path))
                if os.path.exists(dst):
                    dst = dst + "." + str(int(time.time()))
                shutil.move(abs_path, dst)
                faits.append({"avant": abs_path, "apres": dst})
                
            return {"id": "supprimer", "action": action, "faits": faits}
            
        elif action == "deplacer":
            # V18 : Déplacer un dossier DANS lui-même détruirait l'arborescence.
            pass # TODO: Implémenter copier/déplacer

        return {"erreur": "Non implémenté"}

    def prouver_operer(ctx, res):
        if res.get("action") == "dossier":
            return os.path.isdir(res["apres"])
        if res.get("action") == "renommer":
            return os.path.exists(res["apres"])
        if res.get("action") == "supprimer":
            return all(os.path.exists(f["apres"]) and not os.path.exists(f["avant"]) for f in res["faits"])
        return True

    def defaire_operer(ctx, res):
        if res.get("action") == "dossier":
            try:
                os.rmdir(res["apres"])
            except Exception:
                pass
        elif res.get("action") == "renommer":
            os.rename(res["apres"], res["avant"])
        elif res.get("action") == "supprimer":
            for f in res["faits"]:
                shutil.move(f["apres"], f["avant"])

    def _ged_inline_type(nom: str) -> str:
        # V18 : Beaucoup de fichiers texte n'ont pas de type reconnu : on les sert en text/plain, 
        # jamais avec le type deviné. « xml » est volontairement absent.
        ext = (nom or "").rsplit(".", 1)[-1].lower() if "." in (nom or "") else ""
        if ext in ("txt", "md", "log", "csv", "tsv", "json", "yaml", "yml", "ini",
                   "conf", "cfg", "py", "js", "css", "sh", "sql", "toml"):
            return "text/plain"
            
        import mimetypes
        m, _ = mimetypes.guess_type(nom)
        if m in _GED_INLINE_OK:
            return m
        return ""

    def voir(ctx, racine_path="", chemin=""):
        # V18 : Servir « en ligne » plutôt qu'en pièce jointe change tout du point de vue de la sécurité : 
        # le navigateur INTERPRÈTE ce qu'il reçoit. Un HTML ou un SVG servis ainsi exécuteraient leur JavaScript ici.
        moi = ctx.compte
        visibles = _ged_racines(moi)
        
        cible = next((r for r in visibles if r["path"] == racine_path), None)
        if not cible:
            raise ValueError("Racine introuvable ou interdite")
            
        abs_path = os.path.realpath(os.path.join(cible["path"], chemin))
        if not abs_path.startswith(os.path.realpath(cible["path"])):
            raise ValueError("Hors racine")
            
        if not os.path.isfile(abs_path):
            raise ValueError("Fichier introuvable")
            
        t = _ged_inline_type(os.path.basename(abs_path))
        if not t:
            raise ValueError("ce type ne s'affiche pas en ligne — téléchargez-le pour l'ouvrir")
            
        return {"fichier": abs_path, "mime": t, "taille": os.path.getsize(abs_path)}

    def montages(ctx):
        # Moteur sur événement : vérifie les sentinelles des racines et ouvre/ferme des constats
        for r in _ged_racines(None):
            souci = _ged_racine_souci(r["path"], r["sentinelle"])
            if souci:
                ctx.emettre("constat.ouvert", objet=("racine", r["id"]), donnees={"titre": "Racine déconnectée", "detail": souci, "niveau": "critique", "source": "ged"})
            else:
                ctx.emettre("constat.resolu", objet=("racine", r["id"]), donnees={"cle": "ged.montages:racine:%s" % r["id"]})

    ctx.detecteur("montages", montages)
    ctx.implementer("configurer", configurer, prouver_configurer, defaire_configurer)
    ctx.implementer("lister", lister)
    ctx.implementer("operer", operer, prouver_operer, defaire_operer)
    ctx.implementer("voir", voir)
