# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'évolution : cibler, évaluer, mettre en ombre, monter par paliers, revisiter
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #ea4569
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : reçoit des variantes d'un moteur de recherche, ne retient que celles que l'évaluateur prouve, les met en service sans risque et vérifie le gain plus tard.
# MÉTHODE    : le moteur ne propose que du texte ; ici tout est déterministe : évaluation, pièges, écriture de l'EC, ombre, paliers, retour, chaîne d'empreintes, tombes.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ea4569 ▼▼▼
"""L'évolution (docs/CN_EVOLUTION.md) : le côté NEXUS. Le moteur de recherche (Orfan, ou un autre par le contrat d'adaptateur) ne fait que PROPOSER du texte ;
tout ce qui décide est ici, en code déterministe :

  proposer   : des candidats -> évaluation (équivalence par paliers, gain mesuré sur le réservé) -> évaluateur éprouvé (pièges) -> écriture de l'EC -> OMBRE ;
  tick       : l'ombre est sans écart -> 10 % -> 50 % -> 100 % du trafic, chaque palier gardé tant qu'aucune faute ne survient ;
  visiter    : un mois après, le gain est-il resté ? sinon l'EC est retirée et devient une TOMBE ;
  retour     : un aiguillage, jamais une restauration ;
  chaîne     : chaque événement est scellé dans une chaîne d'empreintes ; une rupture se voit (verifier_chaine).

Le moteur ne touche jamais le disque ni le noyau : il rend des textes. Une variante qui ne passe pas tous les contrôles n'est jamais écrite.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import sqlite3
import time
from pathlib import Path

SEUILS = {"gain_min_pct": 5.0,          # un gain en dessous n'en est pas un (le bruit de mesure)
          "pieges_min": 0.85,           # part des variantes fausses que le corpus doit attraper avant qu'on lui fasse confiance
          "ombre_appels": 200,          # appels comparés en ombre, sans un écart, avant le premier palier
          "paliers": (10, 50, 100),     # la part du trafic, étape par étape
          "appels_par_palier": 200,     # appels réels sur un palier avant le suivant
          "visite_jours": 30,           # le gain est revérifié après ce délai de service complet
          "gain_confirme": 0.5}         # à la visite, le gain doit valoir au moins cette part du gain annoncé

SCHEMA = """
CREATE TABLE IF NOT EXISTS pieces(id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT NOT NULL, num INTEGER NOT NULL, fichier TEXT NOT NULL, empreinte TEXT NOT NULL, ast TEXT NOT NULL,
  etat TEXT NOT NULL, gain_annonce REAL, evaluation TEXT, cree REAL NOT NULL, etape REAL NOT NULL, appels_etape INTEGER NOT NULL DEFAULT 0, mise_en_service REAL,
  visite TEXT, UNIQUE(gid, num));
CREATE TABLE IF NOT EXISTS tombes(gid TEXT NOT NULL, ast TEXT NOT NULL, raison TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY(gid, ast));
CREATE TABLE IF NOT EXISTS chaine(seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, gid TEXT NOT NULL, verbe TEXT NOT NULL, details TEXT NOT NULL,
  previous_hash TEXT NOT NULL, hash TEXT NOT NULL UNIQUE);
"""
ETATS_VIVANTS = ("ombre", "palier_10", "palier_50", "en_service")


def empreinte_ast(texte: str) -> str:
    """L'identité SÉMANTIQUE d'un texte : l'arbre syntaxique, sans commentaires ni mise en forme. Deux variantes qui ne diffèrent que par la mise en page sont la même."""
    return hashlib.sha256(ast.dump(ast.parse(texte)).encode("utf-8")).hexdigest()[:16]


def _empreinte_borne(texte: str) -> str:
    return hashlib.sha256("\n".join(l.rstrip() for l in texte.splitlines()).encode("utf-8")).hexdigest()[:6]


class Evolution:
    def __init__(self, points, rejeu, evaluateur, chemin_base, horloge=time.time, seuils: dict | None = None):
        self.points, self.rejeu, self.evaluateur, self._horloge = points, rejeu, evaluateur, horloge
        self.seuils = dict(SEUILS, **(seuils or {}))
        self.chemin = Path(chemin_base)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._pieges: dict = {}                               # le score des pièges d'un point, calculé une fois par état du corpus
        with self._con() as c:
            c.executescript(SCHEMA)

    @contextlib.contextmanager
    def _con(self):
        c = sqlite3.connect(str(self.chemin), timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # ── la chaîne : une rupture se voit ──────────────────────────────────
    def _noter(self, c, gid: str, verbe: str, details: dict) -> str:
        ts = self._horloge()
        dernier = c.execute("SELECT hash FROM chaine ORDER BY seq DESC LIMIT 1").fetchone()
        prev = dernier["hash"] if dernier else "0" * 64
        corps = json.dumps(details, ensure_ascii=False, sort_keys=True)
        h = hashlib.sha256(("%s|%r|%s|%s|%s" % (prev, ts, gid, verbe, corps)).encode("utf-8")).hexdigest()
        c.execute("INSERT INTO chaine(ts,gid,verbe,details,previous_hash,hash) VALUES(?,?,?,?,?,?)", (ts, gid, verbe, corps, prev, h))
        return h

    def verifier_chaine(self) -> dict:
        """Rejoue la chaîne : la première maille dont l'empreinte ne se recalcule pas est une rupture (docs/CN_EVOLUTION.md : rupture = tout s'arrête)."""
        with self._con() as c:
            prev = "0" * 64
            for r in c.execute("SELECT * FROM chaine ORDER BY seq"):
                h = hashlib.sha256(("%s|%r|%s|%s|%s" % (prev, r["ts"], r["gid"], r["verbe"], r["details"])).encode("utf-8")).hexdigest()
                if r["previous_hash"] != prev or r["hash"] != h:
                    return {"ok": False, "rupture_a": r["seq"], "mailles": r["seq"]}
                prev = h
            n = c.execute("SELECT COUNT(*) FROM chaine").fetchone()[0]
        return {"ok": True, "mailles": n}

    def chaine(self, gid: str | None = None, limite: int = 50) -> list:
        with self._con() as c:
            if gid:
                lignes = c.execute("SELECT seq,ts,gid,verbe,details FROM chaine WHERE gid=? ORDER BY seq DESC LIMIT ?", (gid, limite)).fetchall()
            else:
                lignes = c.execute("SELECT seq,ts,gid,verbe,details FROM chaine ORDER BY seq DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r, details=json.loads(r["details"])) for r in lignes]

    # ── cibler ───────────────────────────────────────────────────────────
    def cibles(self) -> list:
        """Les points classés par ce que l'optimisation rapporterait : appels réels × durée moyenne. Sans mesure, un point est dit MUET (rangé en dernier) : jamais « zéro »."""
        out = []
        for gid in self.points.points():
            s = self.rejeu.stats(gid)
            muet = s["duree_moyenne_ms"] is None
            out.append({"point": gid, "appels": s["appels"], "duree_moyenne_ms": s["duree_moyenne_ms"], "corpus": s["distincts"], "muet": muet,
                        "valeur_ms": None if muet else round(s["appels"] * s["duree_moyenne_ms"], 1)})
        return sorted(out, key=lambda x: (x["muet"], -(x["valeur_ms"] or 0)))

    def tombes(self, gid: str) -> set:
        with self._con() as c:
            return {r["ast"] for r in c.execute("SELECT ast FROM tombes WHERE gid=?", (gid,))}

    def _tomber(self, c, gid: str, ast_h: str, raison: str):
        c.execute("INSERT OR REPLACE INTO tombes(gid,ast,raison,ts) VALUES(?,?,?,?)", (gid, ast_h, raison, self._horloge()))

    # ── proposer ─────────────────────────────────────────────────────────
    def proposer(self, module: str, point: str, moteur, budget: int = 5) -> dict:
        """Demande des variantes au moteur, ne retient que la meilleure PROUVÉE, l'écrit au format universel et la met en OMBRE. Rien n'est jamais servi à ce stade."""
        ref = self.points.reference(module, point)
        gid = ref["gid"]
        source = ref["fichier"].read_text(encoding="utf-8")
        visibles = self.rejeu.corpus(gid, "visible")
        contexte = {"point": gid, "source_reference": source, "contrat": ref["contrat"], "fonction": ref["fonction"], "appelable": ref["appelable"],
                    "entrees": [c["entree"] for c in visibles[:60]],           # le générateur ne voit QUE la partition visible
                    "tombes": sorted(self.tombes(gid)), "budget": int(budget), "seuils": dict(self.seuils)}
        try:
            candidats = list(moteur.proposer(contexte))[:int(budget)]
        except Exception as e:
            return {"ok": False, "raison": "le moteur a échoué : %s : %s" % (type(e).__name__, e), "essais": [], "piece": None}
        reference_ast = empreinte_ast(source)
        tombes = self.tombes(gid)
        essais, meilleur = [], None
        for cand in candidats:
            texte = cand if isinstance(cand, str) else str(cand.get("texte", ""))
            hypothese = "" if isinstance(cand, str) else str(cand.get("hypothese", ""))
            try:
                h = empreinte_ast(texte)
            except SyntaxError:
                essais.append({"ast": None, "verdict": "illisible", "gain_pct": None})
                continue
            if h == reference_ast or h in tombes:
                essais.append({"ast": h, "verdict": "deja_vue" if h in tombes else "identique", "gain_pct": None})
                continue
            r = self.evaluateur.evaluer(module, point, texte)
            essais.append({"ast": h, "verdict": r["verdict"], "gain_pct": r["gain_pct"], "gain_tient": r["gain_tient"], "divergence": r["divergence"]})
            if r["verdict"] in ("divergente", "erreur", "impure", "illisible"):
                with self._con() as c:
                    self._tomber(c, gid, h, "%s : %s" % (r["verdict"], r.get("erreur") or r.get("divergence")))
                continue
            if r["verdict"] != "equivalente":
                continue                                                      # corpus trop étroit : on ne promeut pas sur un jeu mince (le motif est rendu plus bas)
            bruit = r.get("bruit_pct") or 0
            if (r["gain_pct"] or 0) < self.seuils["gain_min_pct"] or r["gain_pct"] <= 2 * bruit or r["gain_tient"] is False:
                with self._con() as c:
                    self._tomber(c, gid, h, "gain insuffisant, dans le bruit de mesure (%s %%) ou qui ne tient pas hors du vu : %s %%" % (round(bruit, 1), r["gain_pct"]))
                continue
            if meilleur is None or r["gain_pct"] > meilleur["eval"]["gain_pct"]:
                meilleur = {"texte": texte, "ast": h, "eval": r, "hypothese": hypothese}
        if meilleur is None:
            etroit = any(e["verdict"] == "corpus_trop_etroit" for e in essais)
            return {"ok": False, "raison": "corpus trop étroit : aucune promotion sur un jeu mince" if etroit else "aucune variante prouvée et plus rapide", "essais": essais, "piece": None}
        # l'évaluateur est évalué avant qu'on lui fasse confiance
        cle = (gid, self.rejeu.stats(gid)["distincts"])
        if cle not in self._pieges:
            self._pieges[cle] = self.evaluateur.pieges(module, point)
        p = self._pieges[cle]
        if p["score"] is None or p["score"] < self.seuils["pieges_min"]:
            return {"ok": False, "raison": "corpus trop faible pour juger : %s %% des variantes fausses seulement sont attrapées (seuil %s %%)" % (round(100 * (p["score"] or 0)), round(100 * self.seuils["pieges_min"])),
                    "essais": essais, "piece": None, "pieges": p}
        piece = self._ecrire(module, point, ref, meilleur)
        return {"ok": True, "raison": "", "essais": essais, "piece": piece, "pieges": {"score": p["score"], "mutants": p["mutants"]}}

    def _ecrire(self, module: str, point: str, ref: dict, meilleur: dict) -> dict:
        gid = ref["gid"]
        stock = self.points.stock
        if stock is None:
            raise ValueError("aucun stock d'EC : rien à écrire")
        with self._con() as c:
            num = (c.execute("SELECT COALESCE(MAX(num),0) FROM pieces WHERE gid=?", (gid,)).fetchone()[0]) + 1
        dossier = Path(stock) / module / point
        dossier.mkdir(parents=True, exist_ok=True)
        nom = "EC_%s__EC%d.py" % (point.replace(".", "_"), num)
        h = _empreinte_borne(meilleur["texte"])
        contrat = ref["version_contrat"]
        lignes = ["# " + "═" * 78, "# TITRE      : %s : variante EC%d (générée par l'évolution)" % (point, num), "# LICENCE    : AGPL-3.0", "# AUTEUR     : Atek Drisse",
                  "# GIT        : github.com/Marplestrange", "# MAIL       : marplestrange@cassandra.center", "# MODULE     : " + module, "# ZONE       : EC", "# RUNTIME    : python",
                  "# VERSION CN : néant", "# VERSION EC : EC%d  #%s" % (num, h), "# HÔTE CN    : façade de %s · %s @%s" % (module, point, contrat),
                  "# NEXUS VISÉ : %s (contrat %s)" % (module, contrat), "# CONTRAT PROUVÉ : @%s" % contrat,
                  "# RÔLE       : variante prouvée équivalente à la référence sur le corpus de rejeu, gain annoncé %s %%." % meilleur["eval"]["gain_pct"],
                  "# MÉTHODE    : %s" % (meilleur["hypothese"] or "variante proposée par le moteur de recherche, jugée par l'évaluateur du noyau."), "# " + "═" * 78,
                  "# ▼▼▼ BORNE EC point=%s contrat=@%s version=EC%d empreinte=%s ▼▼▼" % (point, contrat, num, h)]
        pied = ["# ▲▲▲ FIN BORNE EC ▲▲▲", "", "# ═══ EXPLICATIF CN / EC " + "═" * 55,
                "# EC : variante EC%d du point %s ; remplaçable, retirable en un geste (routage), jamais détruite." % (num, point),
                "# CN : appelée par la façade du module par ctx.point, sous le contrat et le disjoncteur du noyau."]
        texte = "\n".join(lignes + meilleur["texte"].rstrip("\n").split("\n") + pied) + "\n"
        (dossier / nom).write_text(texte, encoding="utf-8", newline="\n")
        (dossier / "ACTIVE").write_text(nom, encoding="utf-8")
        self.points.router(module, point, "ombre")
        now = self._horloge()
        etat = self.points.etat(module, point)
        with self._con() as c:
            c.execute("INSERT INTO pieces(gid,num,fichier,empreinte,ast,etat,gain_annonce,evaluation,cree,etape,appels_etape) VALUES(?,?,?,?,?,'ombre',?,?,?,?,?)",
                      (gid, num, nom, h, meilleur["ast"], meilleur["eval"]["gain_pct"], json.dumps({k: v for k, v in meilleur["eval"].items() if k != "fautes"}, default=str), now, now, etat["appels"]))
            self._noter(c, gid, "proposee", {"ec": "EC%d" % num, "ast": meilleur["ast"], "gain_pct": meilleur["eval"]["gain_pct"], "empreinte": h})
            self._noter(c, gid, "ombre", {"ec": "EC%d" % num})
        return {"gid": gid, "ec": "EC%d" % num, "num": num, "fichier": nom, "gain_annonce_pct": meilleur["eval"]["gain_pct"], "etat": "ombre"}

    # ── la mise en service par paliers ───────────────────────────────────
    def pieces(self, gid: str | None = None, etats=None) -> list:
        with self._con() as c:
            q, a = "SELECT * FROM pieces", []
            cond = []
            if gid:
                cond.append("gid=?")
                a.append(gid)
            if etats:
                cond.append("etat IN (%s)" % ",".join("?" * len(etats)))
                a += list(etats)
            if cond:
                q += " WHERE " + " AND ".join(cond)
            return [dict(r) for r in c.execute(q + " ORDER BY id", a)]

    def tick(self) -> list:
        """Fait avancer chaque pièce vivante d'un cran si, et seulement si, ses preuves le permettent. Rend ce qui s'est passé."""
        faits = []
        for p in self.pieces(etats=ETATS_VIVANTS):
            module, point = p["gid"].split(".", 1)
            etat = self.points.etat(module, point)
            if etat["suspendue"]:
                faits.append(self._retirer(p, "suspendue par le disjoncteur : %s" % etat["suspendue"]["raison"]))
                continue
            if p["etat"] == "ombre":
                o = etat["ombre"] or {"appels": 0, "ecarts": 0, "erreurs": 0}
                if o["appels"] >= self.seuils["ombre_appels"] and o["ecarts"] == 0 and o["erreurs"] == 0:
                    faits.append(self._palier(p, module, point, self.seuils["paliers"][0], etat))
            elif p["etat"].startswith("palier_"):
                part = int(p["etat"].split("_")[1])
                if etat["appels"] - p["appels_etape"] >= self.seuils["appels_par_palier"]:
                    suivants = [x for x in self.seuils["paliers"] if x > part]
                    if suivants:
                        faits.append(self._palier(p, module, point, suivants[0], etat))
        return faits

    def _palier(self, p: dict, module: str, point: str, part: int, etat: dict) -> dict:
        self.points.router(module, point, "service", part)
        nouveau = "en_service" if part >= 100 else "palier_%d" % part
        now = self._horloge()
        with self._con() as c:
            c.execute("UPDATE pieces SET etat=?, etape=?, appels_etape=?, mise_en_service=CASE WHEN ?='en_service' THEN ? ELSE mise_en_service END WHERE id=?",
                      (nouveau, now, etat["appels"], nouveau, now, p["id"]))
            self._noter(c, p["gid"], nouveau, {"ec": "EC%d" % p["num"], "part": part})
        return {"point": p["gid"], "ec": "EC%d" % p["num"], "etat": nouveau, "part": part}

    def _retirer(self, p: dict, raison: str, tombe: bool = True) -> dict:
        module, point = p["gid"].split(".", 1)
        try:
            self.points.router(module, point, "arret")
        except ValueError:
            pass
        with self._con() as c:
            c.execute("UPDATE pieces SET etat='retiree' WHERE id=?", (p["id"],))
            if tombe:
                self._tomber(c, p["gid"], p["ast"], raison)
            self._noter(c, p["gid"], "retiree", {"ec": "EC%d" % p["num"], "raison": raison})
        return {"point": p["gid"], "ec": "EC%d" % p["num"], "etat": "retiree", "raison": raison}

    def retour(self, gid: str, raison: str = "retour demandé") -> list:
        """Le retour instantané : un aiguillage vers la référence ; l'EC reste dans le stock et sa tombe est gardée avec la raison."""
        return [self._retirer(p, raison) for p in self.pieces(gid, ETATS_VIVANTS)]

    # ── la visite : le gain est-il resté ? ───────────────────────────────
    def visiter(self, piece_id: int | None = None) -> list:
        """Pour chaque pièce en service depuis assez longtemps, rejoue l'EC contre la référence sur le corpus d'AUJOURD'HUI. Un gain qui n'est pas resté la retire."""
        now = self._horloge()
        sortie = []
        for p in self.pieces(etats=("en_service",)):
            if piece_id is not None and p["id"] != piece_id:
                continue
            if p["visite"] or now - (p["mise_en_service"] or now) < self.seuils["visite_jours"] * 86400:
                continue
            module, point = p["gid"].split(".", 1)
            fichier = Path(self.points.stock) / module / point / p["fichier"]
            bloc = self._corps_ec(fichier.read_text(encoding="utf-8"))
            r = self.evaluateur.evaluer(module, point, bloc)
            tenu = r["verdict"] == "equivalente" and (r["gain_pct"] or 0) >= self.seuils["gain_confirme"] * (p["gain_annonce"] or 0)
            verdict = {"tenu": bool(tenu), "gain_annonce_pct": p["gain_annonce"], "gain_mesure_pct": r["gain_pct"], "verdict": r["verdict"]}
            with self._con() as c:
                c.execute("UPDATE pieces SET visite=? WHERE id=?", (json.dumps(verdict), p["id"]))
                self._noter(c, p["gid"], "visite", dict(verdict, ec="EC%d" % p["num"]))
            if not tenu:
                verdict["retrait"] = self._retirer(p, "visite : annoncé %s %%, mesuré %s %% (%s)" % (p["gain_annonce"], r["gain_pct"], r["verdict"]))
            sortie.append(dict(verdict, point=p["gid"], ec="EC%d" % p["num"]))
        return sortie

    @staticmethod
    def _corps_ec(texte: str) -> str:
        """Le code d'une EC, sans son en-tête : ce qui est entre les marqueurs de borne."""
        out, dedans = [], False
        for l in texte.splitlines():
            s = l.strip()
            if s.startswith("# ▼▼▼ BORNE EC"):
                dedans = True
                continue
            if s.startswith("# ▲▲▲ FIN BORNE EC"):
                break
            if dedans:
                out.append(l)
        return "\n".join(out) + "\n"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Evolution (cibles, proposer, tick, visiter, retour, chaîne). C'est lui qui décide ; le moteur de recherche ne fait que proposer du texte.
# EC : néant. L'orchestration d'une évolution ne s'évolue pas (docs/CN_NEXUS.md §4 : mécanismes de l'évolution).
# LIEN : noyau/CN_evaluateur.py (le juge), noyau/CN_rejeu.py (le corpus), noyau/CN_points.py (ombre, routage, disjoncteur), orfan/CN_orfan.py (un moteur de recherche).
