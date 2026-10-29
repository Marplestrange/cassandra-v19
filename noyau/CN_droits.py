# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les droits
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #7764f1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les droits : qui, parmi les COMPTES, peut utiliser quoi.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7764f1 ▼▼▼
"""Les droits : qui, parmi les COMPTES, peut utiliser quoi.

  - un module DÉCLARE ses droits dans son manifeste ([[droits]]) ; ils s'appellent « module.droit » ;
  - on les attribue à un compte, ou à un groupe dont le compte est membre ;
  - un administrateur détient tous les droits ;
  - un droit « défaut » est accordé d'office à tout compte ;
  - la vérification a lieu à UN endroit, l'exécuteur : une capacité qui porte un `droit` ne s'exécute pour un compte que s'il le détient.

Le point qui compte : quand Itare ou Cassandra agissent AU NOM d'un compte, ils n'ont pas plus de droits que lui (le « délégué abusé »).
Sans compte (infrastructure, agents seuls), aucun droit n'est demandé : les agents sont souverains, c'est le palier de la capacité qui les borne.

Ordre de résolution, du plus fort au plus faible :
  administrateur  >  accord/refus propre au compte  >  refus d'un groupe  >  accord d'un groupe  >  défaut du droit  >  non.
"""
from __future__ import annotations

import threading

SUJETS = ("compte", "groupe")
VALEURS = {"accorde": 1, "refuse": 0}


class Droits:
    def __init__(self, base):
        self.base = base
        self.connus = {}              # « module.droit » -> Droit déclaré par un module branché
        self.delegant = lambda compte: ""   # compte -> le compte qui l'a invité (un agent invité n'a que ce que son invitant a)
        self.verrou = lambda compte: ""   # compte -> pourquoi on ne peut pas lui retirer l'administration ("" : rien ne s'y oppose)
        self._verrou = threading.Lock()

    # ---- ce que les modules déclarent ----
    def declarer(self, manifeste) -> None:
        with self._verrou:
            for d in manifeste.droits:
                self.connus["%s.%s" % (manifeste.id, d.id)] = (manifeste.id, d)

    def oublier(self, module: str) -> None:
        """Un module débranché n'offre plus ses droits ; les accords déjà donnés sont gardés (il peut revenir)."""
        with self._verrou:
            for cle in [k for k, (m, _) in self.connus.items() if m == module]:
                del self.connus[cle]

    def catalogue(self) -> list:
        with self._verrou:
            return [{"droit": k, "module": m, "libelle": d.libelle, "defaut": d.defaut, "sensible": d.sensible}
                    for k, (m, d) in sorted(self.connus.items())]

    # ---- la décision ----
    def est_admin(self, compte: str) -> bool:
        return bool(self.base.lire("SELECT 1 FROM droit_admins WHERE compte=?", (compte,)))

    def groupes_de(self, compte: str, societe: str = "") -> list:
        """Les groupes qui comptent pour une décision : ceux sans société (valables partout) et, si on agit dans une société, ceux attachés à celle-là.
        Une « fonction » (groupe attaché à la société B) ne donne jamais rien hors de B."""
        lignes = self.base.lire("SELECT m.groupe, p.societe FROM droit_membres m LEFT JOIN droit_groupe_portee p ON p.groupe=m.groupe WHERE m.compte=? ORDER BY m.groupe", (compte,))
        return [r["groupe"] for r in lignes if not r["societe"] or r["societe"] == societe]

    def tous_groupes_de(self, compte: str) -> list:
        """Tous les groupes d'un compte, avec leur société le cas échéant : [{"groupe", "societe"}]."""
        return [{"groupe": r["groupe"], "societe": r["societe"] or ""} for r in self.base.lire(
            "SELECT m.groupe, p.societe FROM droit_membres m LEFT JOIN droit_groupe_portee p ON p.groupe=m.groupe WHERE m.compte=? ORDER BY m.groupe", (compte,))]

    def portee_du_groupe(self, groupe: str) -> str:
        r = self.base.lire("SELECT societe FROM droit_groupe_portee WHERE groupe=?", (groupe,))
        return r[0]["societe"] if r else ""

    def attacher_groupe(self, groupe: str, societe: str) -> None:
        """Attache un groupe à une société (vide : le rend valable partout)."""
        if not self.groupe(groupe):
            raise ValueError("groupe inconnu : %s" % groupe)
        if not societe:
            self.base.ecrire("DELETE FROM droit_groupe_portee WHERE groupe=?", (groupe,))
            return
        if not self.base.lire("SELECT 1 FROM societes WHERE id=?", (societe,)):
            raise ValueError("société inconnue : %s" % societe)
        self.base.ecrire("INSERT INTO droit_groupe_portee(groupe, societe) VALUES(?,?) ON CONFLICT(groupe) DO UPDATE SET societe=excluded.societe", (groupe, societe))

    def societes_de(self, compte: str) -> list:
        """Les sociétés où ce compte peut agir : la sienne (obligatoire), puis celles où il a une fonction. Un superadministrateur peut agir dans toutes."""
        if not compte:
            return []
        r = self.base.lire("SELECT societe, superadmin FROM comptes WHERE compte=?", (compte,))
        if r and r[0]["superadmin"]:
            return [x["id"] for x in self.base.lire("SELECT id FROM societes WHERE archivee=0 ORDER BY principale DESC, id")]
        ids = [r[0]["societe"] if r and r[0]["societe"] else "1"]
        for x in self.base.lire("SELECT DISTINCT p.societe FROM droit_membres m JOIN droit_groupe_portee p ON p.groupe=m.groupe JOIN societes s ON s.id=p.societe "
                                "WHERE m.compte=? AND s.archivee=0 ORDER BY p.societe", (compte,)):
            if x["societe"] not in ids:
                ids.append(x["societe"])
        return ids

    def a(self, compte: str, droit: str, societe: str = "") -> bool:
        return self.raison(compte, droit, societe)["accord"]

    def raison(self, compte: str, droit: str, societe: str = "", _profondeur: int = 0) -> dict:
        """La décision ET son pourquoi : une réponse « non » doit pouvoir s'expliquer à celui qui la reçoit."""
        if not compte:
            return {"accord": True, "parce": "infrastructure (aucun compte)"}
        if self.est_admin(compte):
            return {"accord": True, "parce": "administrateur"}
        propre = self.base.lire("SELECT accord FROM droit_accords WHERE sujet_type='compte' AND sujet=? AND droit=?", (compte, droit))
        if propre:
            return {"accord": bool(propre[0]["accord"]), "parce": "accordé au compte" if propre[0]["accord"] else "refusé au compte"}
        if compte.startswith("agent:") and _profondeur < 5:
            # Un agent INVITÉ n'a jamais plus que celui qui l'a invité (V18 : « la seule borne d'un invité est le statut du compte qui l'invite »).
            # En direct : baisser les droits de l'invitant baisse ceux de ses invités, et l'invité d'un administrateur a tout.
            par = self.delegant(compte)
            if par and par != compte:
                r = self.raison(par, droit, societe, _profondeur + 1)
                return {"accord": r["accord"], "parce": "agent invité par %s : %s" % (par, r["parce"])}
            return {"accord": False, "parce": "agent invité sans invitant connu"}
        groupes = self.groupes_de(compte, societe)
        if groupes:
            marques = ",".join("?" * len(groupes))
            lignes = self.base.lire("SELECT sujet, accord FROM droit_accords WHERE sujet_type='groupe' AND droit=? AND sujet IN (%s)" % marques,
                                    (droit, *groupes))
            refus = [r["sujet"] for r in lignes if not r["accord"]]
            if refus:
                return {"accord": False, "parce": "refusé par le groupe %s" % refus[0]}
            octroi = [r["sujet"] for r in lignes if r["accord"]]
            if octroi:
                return {"accord": True, "parce": "accordé par le groupe %s" % octroi[0]}
        connu = self.connus.get(droit)
        if connu and connu[1].defaut:
            return {"accord": True, "parce": "accordé à tous par défaut"}
        return {"accord": False, "parce": "non attribué" if connu else "droit inconnu"}

    def decisions_de(self, compte: str, societe: str = "", _profondeur: int = 0) -> dict:
        """Toutes les décisions d'un compte pour tous les droits connus, en quatre lectures au lieu d'une par droit. Même ordre et mêmes motifs que `raison` :
        {droit: {"accord": bool, "parce": str, "propre": 'accorde' | 'refuse' | None}}."""
        with self._verrou:
            connus = dict(self.connus)
        if not compte:
            return {k: {"accord": True, "parce": "infrastructure (aucun compte)", "propre": None} for k in connus}
        propres = {r["droit"]: ("accorde" if r["accord"] else "refuse")
                   for r in self.base.lire("SELECT droit, accord FROM droit_accords WHERE sujet_type='compte' AND sujet=?", (compte,))}
        if self.est_admin(compte):
            return {k: {"accord": True, "parce": "administrateur", "propre": propres.get(k)} for k in connus}
        base = None
        if compte.startswith("agent:") and _profondeur < 5:
            par = self.delegant(compte)
            base = self.decisions_de(par, societe, _profondeur + 1) if par and par != compte else {}
            invitant = par
        groupes = self.groupes_de(compte, societe)
        lignes = []
        if groupes and base is None:
            marques = ",".join("?" * len(groupes))
            lignes = self.base.lire("SELECT sujet, accord, droit FROM droit_accords WHERE sujet_type='groupe' AND sujet IN (%s)" % marques, tuple(groupes))
        refus, octroi = {}, {}
        for r in lignes:
            (octroi if r["accord"] else refus).setdefault(r["droit"], r["sujet"])
        out = {}
        for k, (_, d) in connus.items():
            p = propres.get(k)
            if p == "accorde":
                out[k] = {"accord": True, "parce": "accordé au compte", "propre": p}
            elif p == "refuse":
                out[k] = {"accord": False, "parce": "refusé au compte", "propre": p}
            elif base is not None:
                if base:
                    out[k] = {"accord": base[k]["accord"], "parce": "agent invité par %s : %s" % (invitant, base[k]["parce"]), "propre": None}
                else:
                    out[k] = {"accord": False, "parce": "agent invité sans invitant connu", "propre": None}
            elif k in refus:
                out[k] = {"accord": False, "parce": "refusé par le groupe %s" % refus[k], "propre": None}
            elif k in octroi:
                out[k] = {"accord": True, "parce": "accordé par le groupe %s" % octroi[k], "propre": None}
            elif d.defaut:
                out[k] = {"accord": True, "parce": "accordé à tous par défaut", "propre": None}
            else:
                out[k] = {"accord": False, "parce": "non attribué", "propre": None}
        return out

    def detenus(self, compte: str, societe: str = "") -> dict:
        """Tout ce qu'un compte détient parmi les droits que les modules branchés déclarent (de quoi filtrer un menu d'un seul coup)."""
        admin = bool(compte) and self.est_admin(compte)
        droits = sorted(k for k, v in self.decisions_de(compte, societe).items() if v["accord"]) if compte else sorted(self.connus)
        return {"compte": compte, "admin": admin, "groupes": self.groupes_de(compte, societe) if compte else [], "droits": droits, "societe": societe}

    # ---- les écritures (appelées par le module des droits, qui les rend réversibles) ----
    def accord(self, sujet_type: str, sujet: str, droit: str):
        """'accorde' | 'refuse' | None (hérite)."""
        r = self.base.lire("SELECT accord FROM droit_accords WHERE sujet_type=? AND sujet=? AND droit=?", (sujet_type, sujet, droit))
        return None if not r else ("accorde" if r[0]["accord"] else "refuse")

    def regler(self, sujet_type: str, sujet: str, droit: str, valeur) -> None:
        """valeur : 'accorde' | 'refuse' | None / 'herite' (retire l'entrée)."""
        if sujet_type not in SUJETS:
            raise ValueError("sujet : compte | groupe")
        if not sujet or not str(sujet).strip():
            raise ValueError("sujet vide")
        if sujet_type == "groupe" and not self.groupe(sujet):
            raise ValueError("groupe inconnu : %s" % sujet)
        if droit not in self.connus:
            raise ValueError("droit inconnu (aucun module actif ne le déclare) : %s" % droit)
        if valeur in (None, "herite"):
            self.base.ecrire("DELETE FROM droit_accords WHERE sujet_type=? AND sujet=? AND droit=?", (sujet_type, sujet, droit))
            return
        if valeur not in VALEURS:
            raise ValueError("valeur : accorde | refuse | herite")
        self.base.ecrire("INSERT INTO droit_accords(sujet_type, sujet, droit, accord) VALUES(?,?,?,?) "
                         "ON CONFLICT(sujet_type, sujet, droit) DO UPDATE SET accord=excluded.accord", (sujet_type, sujet, droit, VALEURS[valeur]))

    def groupe(self, groupe: str):
        r = self.base.lire("SELECT groupe, libelle, description FROM droit_groupes WHERE groupe=?", (groupe,))
        return r[0] if r else None

    def regler_groupe(self, groupe: str, libelle, description=None) -> None:
        """libelle None : supprime le groupe, ses membres et ses accords. `description` None : on garde l'ancienne."""
        if not groupe or not str(groupe).strip():
            raise ValueError("groupe vide")
        with self.base.transaction() as c:
            if libelle is None:
                c.execute("DELETE FROM droit_accords WHERE sujet_type='groupe' AND sujet=?", (groupe,))
                c.execute("DELETE FROM droit_membres WHERE groupe=?", (groupe,))
                c.execute("DELETE FROM droit_groupe_portee WHERE groupe=?", (groupe,))
                c.execute("DELETE FROM droit_groupes WHERE groupe=?", (groupe,))
            else:
                if description is None:
                    c.execute("INSERT INTO droit_groupes(groupe, libelle) VALUES(?,?) ON CONFLICT(groupe) DO UPDATE SET libelle=excluded.libelle",
                              (groupe, libelle))
                else:
                    c.execute("INSERT INTO droit_groupes(groupe, libelle, description) VALUES(?,?,?) ON CONFLICT(groupe) DO UPDATE SET libelle=excluded.libelle, description=excluded.description",
                              (groupe, libelle, str(description).strip()))

    def membre(self, compte: str, groupe: str) -> bool:
        return bool(self.base.lire("SELECT 1 FROM droit_membres WHERE compte=? AND groupe=?", (compte, groupe)))

    def regler_membre(self, compte: str, groupe: str, present: bool) -> None:
        if not compte or not str(compte).strip():
            raise ValueError("compte vide")
        if present:
            if not self.groupe(groupe):
                raise ValueError("groupe inconnu : %s" % groupe)
            self.base.ecrire("INSERT OR IGNORE INTO droit_membres(compte, groupe) VALUES(?,?)", (compte, groupe))
        else:
            self.base.ecrire("DELETE FROM droit_membres WHERE compte=? AND groupe=?", (compte, groupe))

    def regler_admin(self, compte: str, admin: bool) -> None:
        if not compte or not str(compte).strip():
            raise ValueError("compte vide")
        if admin:
            self.base.ecrire("INSERT OR IGNORE INTO droit_admins(compte) VALUES(?)", (compte,))
        else:
            raison = self.verrou(compte)
            if raison:
                raise ValueError(raison)
            if self.dernier_admin_humain(compte):
                raise ValueError("« %s » est le dernier administrateur : nommez-en un autre d'abord" % compte)
            self.base.ecrire("DELETE FROM droit_admins WHERE compte=?", (compte,))

    def dernier_admin_humain(self, compte: str) -> bool:
        """Ce compte est-il le DERNIER administrateur humain actif ? Les comptes de l'infrastructure (cassandra, noyau, opérateur) et les agents ne comptent pas :
        ils ne se connectent pas. Un administrateur sans ligne de compte (un droit réglé sans compte) n'est pas concerné."""
        r = self.base.lire("SELECT type, desactive FROM comptes WHERE compte=?", (compte,))
        if not r or r[0]["type"] != "humain" or r[0]["desactive"] or not self.est_admin(compte):
            return False
        return self.base.lire("SELECT COUNT(*) AS n FROM droit_admins a JOIN comptes c ON c.compte=a.compte WHERE c.type='humain' AND c.desactive=0")[0]["n"] <= 1

    def etat(self) -> dict:
        return {
            "admins": [r["compte"] for r in self.base.lire("SELECT compte FROM droit_admins ORDER BY compte")],
            "groupes": [dict(r, membres=[m["compte"] for m in self.base.lire("SELECT compte FROM droit_membres WHERE groupe=? ORDER BY compte", (r["groupe"],))])
                        for r in self.base.lire("SELECT g.groupe, g.libelle, g.description, COALESCE(p.societe, '') AS societe FROM droit_groupes g "
                                                "LEFT JOIN droit_groupe_portee p ON p.groupe=g.groupe ORDER BY g.groupe")],
            "accords": self.base.lire("SELECT sujet_type, sujet, droit, accord FROM droit_accords ORDER BY sujet_type, sujet, droit"),
        }

    def amorcer(self, compte: str) -> bool:
        """Une seule fois dans la vie de l'installation : le premier administrateur (fastuser, comme FastPanel).
        Si on le retire ensuite, il ne revient pas tout seul : c'est un choix de l'administrateur."""
        if self.base.lire("SELECT 1 FROM etat_noyau WHERE cle='droits_amorces'"):
            return False
        with self.base.transaction() as c:
            c.execute("INSERT OR IGNORE INTO droit_admins(compte) VALUES(?)", (compte,))
            c.execute("INSERT OR REPLACE INTO etat_noyau(cle, valeur) VALUES('droits_amorces', ?)", (compte,))
        return True
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Droits
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
