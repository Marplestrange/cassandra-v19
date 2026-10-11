"""Les droits : qui, parmi les COMPTES, peut utiliser quoi. Le modèle est celui de Dolibarr, resserré.

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

    def groupes_de(self, compte: str) -> list:
        return [r["groupe"] for r in self.base.lire("SELECT groupe FROM droit_membres WHERE compte=? ORDER BY groupe", (compte,))]

    def a(self, compte: str, droit: str) -> bool:
        return self.raison(compte, droit)["accord"]

    def raison(self, compte: str, droit: str) -> dict:
        """La décision ET son pourquoi : une réponse « non » doit pouvoir s'expliquer à celui qui la reçoit."""
        if not compte:
            return {"accord": True, "parce": "infrastructure (aucun compte)"}
        if self.est_admin(compte):
            return {"accord": True, "parce": "administrateur"}
        propre = self.base.lire("SELECT accord FROM droit_accords WHERE sujet_type='compte' AND sujet=? AND droit=?", (compte, droit))
        if propre:
            return {"accord": bool(propre[0]["accord"]), "parce": "accordé au compte" if propre[0]["accord"] else "refusé au compte"}
        groupes = self.groupes_de(compte)
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

    def detenus(self, compte: str) -> dict:
        """Tout ce qu'un compte détient parmi les droits que les modules branchés déclarent (de quoi filtrer un menu d'un seul coup)."""
        admin = bool(compte) and self.est_admin(compte)
        droits = sorted(k for k in self.connus if admin or self.a(compte, k)) if compte else sorted(self.connus)
        return {"compte": compte, "admin": admin, "groupes": self.groupes_de(compte) if compte else [], "droits": droits}

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
        r = self.base.lire("SELECT groupe, libelle FROM droit_groupes WHERE groupe=?", (groupe,))
        return r[0] if r else None

    def regler_groupe(self, groupe: str, libelle) -> None:
        """libelle None : supprime le groupe, ses membres et ses accords."""
        if not groupe or not str(groupe).strip():
            raise ValueError("groupe vide")
        with self.base.transaction() as c:
            if libelle is None:
                c.execute("DELETE FROM droit_accords WHERE sujet_type='groupe' AND sujet=?", (groupe,))
                c.execute("DELETE FROM droit_membres WHERE groupe=?", (groupe,))
                c.execute("DELETE FROM droit_groupes WHERE groupe=?", (groupe,))
            else:
                c.execute("INSERT INTO droit_groupes(groupe, libelle) VALUES(?,?) ON CONFLICT(groupe) DO UPDATE SET libelle=excluded.libelle",
                          (groupe, libelle))

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
            self.base.ecrire("DELETE FROM droit_admins WHERE compte=?", (compte,))

    def etat(self) -> dict:
        return {
            "admins": [r["compte"] for r in self.base.lire("SELECT compte FROM droit_admins ORDER BY compte")],
            "groupes": [dict(r, membres=[m["compte"] for m in self.base.lire("SELECT compte FROM droit_membres WHERE groupe=? ORDER BY compte", (r["groupe"],))])
                        for r in self.base.lire("SELECT groupe, libelle FROM droit_groupes ORDER BY groupe")],
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
