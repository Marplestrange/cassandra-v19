# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #2d0018
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : l'usine des fiches (salles, artistes, revendeurs, formules, événements, billets, ...).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2d0018 ▼▼▼
"""Billetterie : l'usine des fiches (salles, artistes, revendeurs, formules, événements, billets, ...).

Chaque fiche a le MÊME cycle, et chaque écriture est réversible (la sûreté vient du retour arrière, jamais d'une permission) :
  sauver    crée ou modifie ; rend l'état d'avant ; prouve en relisant ; se défait en remettant l'état d'avant (ou en retirant la fiche neuve) ;
  supprimer refuse si la fiche est employée ailleurs ; se défait en remettant la fiche telle quelle, avec sa référence.
Une référence créée puis annulée, ou supprimée, reste au registre des retirés : elle n'est jamais donnée à une autre fiche.
"""
from __future__ import annotations

import inspect

from . import CN_identifiants as ids


def signer(fonction, *noms, premier="id", defaut_premier=0):
    """Donne à une capacité à `**d` une signature lisible (c, id, champ1=None, ...) : c'est elle que lisent la console et les outils d'Itare pour savoir quels arguments existent.
    L'appel réel reste `f(c, **args)` : un champ non donné n'est pas dans `args`, donc n'est pas touché (None = « non précisé »)."""
    P = inspect.Parameter
    ps = [P("c", P.POSITIONAL_OR_KEYWORD)]
    if premier:
        ps.append(P(premier, P.POSITIONAL_OR_KEYWORD, default=defaut_premier))
    ps += [P(n, P.POSITIONAL_OR_KEYWORD, default=None) for n in noms if n != premier]
    fonction.__signature__ = inspect.Signature(ps)
    return fonction


def _ligne(tx, table, ident):
    r = tx.execute("SELECT * FROM %s WHERE id = ?" % table, (int(ident),)).fetchone()
    return dict(r) if r else None


class Entite:
    def __init__(self, db, id_, table, type_ref, libelle, champs, preparer, dependances=None, apres=None, defaire_apres=None, tombes=(), champ_libelle="nom"):
        self.db, self.id, self.table, self.type_ref, self.libelle = db, id_, table, type_ref, libelle
        self.champs = tuple(champs)            # les noms que la capacité d'écriture annonce (lisibles par la console et par Itare)
        self.preparer = preparer              # (tx, donnees, avant) -> {colonne: valeur}, ou ValueError
        self.dependances = dependances or (lambda tx, ligne: [])
        self.apres = apres                    # (tx, avant, apres) -> effets (dict JSON) ou None
        self.defaire_apres = defaire_apres    # (tx, effets) -> None
        self.tombes = tuple(tombes)           # ((type, colonne), ...) : d'autres identifiants à ne jamais réutiliser (le code d'un revendeur)
        self.champ_libelle = champ_libelle

    # ---- lectures ----
    def lister(self, c, q="", limite=500):
        sql, p = "SELECT * FROM %s" % self.table, ()
        if q:
            sql += " WHERE %s LIKE ? OR ref LIKE ?" % self.champ_libelle
            p = ("%" + str(q) + "%", "%" + str(q) + "%")
        return self.db.lire(sql + " ORDER BY id LIMIT ?", p + (max(1, min(int(limite or 500), 2000)),))

    def lire(self, c, id=0):
        r = self.db.lire("SELECT * FROM %s WHERE id = ?" % self.table, (int(id),))
        if not r:
            raise ValueError("%s introuvable" % self.libelle)
        return r[0]

    # ---- sauver ----
    def sauver(self, c, **d):
        with self.db.transaction() as tx:
            avant = None
            if d.get("id"):
                avant = _ligne(tx, self.table, d["id"])
                if not avant:
                    raise ValueError("%s introuvable" % self.libelle)
            vals = dict(self.preparer(tx, d, avant))
            if avant:
                if vals:
                    tx.execute("UPDATE %s SET %s WHERE id = ?" % (self.table, ", ".join("%s = ?" % k for k in vals)), tuple(vals.values()) + (avant["id"],))
                ident = avant["id"]
            else:
                vals["ref"] = ids.nouvelle_ref(tx, self.type_ref)
                ident = tx.execute("INSERT INTO %s (%s) VALUES (%s)" % (self.table, ", ".join(vals), ", ".join("?" * len(vals))), tuple(vals.values())).lastrowid
            apres = _ligne(tx, self.table, ident)
            effets = self.apres(tx, avant, apres) if self.apres else None
            apres = _ligne(tx, self.table, ident)
        return {"id": ident, "ref": apres["ref"], "cree": avant is None, "avant": avant, "attendu": apres, "effets": effets or {}}

    def prouver_sauver(self, c, res):
        return self.db.lire("SELECT * FROM %s WHERE id = ?" % self.table, (res["id"],)) == [res["attendu"]]

    def defaire_sauver(self, c, res):
        with self.db.transaction() as tx:
            if self.defaire_apres and res.get("effets"):
                self.defaire_apres(tx, res["effets"])
            if res["avant"] is None:
                cour = _ligne(tx, self.table, res["id"])
                tx.execute("DELETE FROM %s WHERE id = ?" % self.table, (res["id"],))
                if cour:
                    ids.retirer(tx, self.type_ref, cour["ref"], cour.get(self.champ_libelle, ""), "créée puis annulée")
                    for t, col in self.tombes:
                        if cour.get(col):
                            ids.retirer(tx, t, cour[col], cour.get(self.champ_libelle, ""), "créée puis annulée")
            else:
                a = res["avant"]
                cols = [k for k in a if k != "id"]
                tx.execute("UPDATE %s SET %s WHERE id = ?" % (self.table, ", ".join("%s = ?" % k for k in cols)), tuple(a[k] for k in cols) + (a["id"],))

    # ---- supprimer ----
    def supprimer(self, c, id=0):
        with self.db.transaction() as tx:
            ligne = _ligne(tx, self.table, id)
            if not ligne:
                raise ValueError("%s introuvable" % self.libelle)
            raisons = self.dependances(tx, ligne)
            if raisons:
                raise ValueError("« %s » est employé(e) : %s" % (ligne.get(self.champ_libelle, ligne["ref"]), " ; ".join(raisons)))
            tx.execute("DELETE FROM %s WHERE id = ?" % self.table, (ligne["id"],))
            ids.retirer(tx, self.type_ref, ligne["ref"], ligne.get(self.champ_libelle, ""), "supprimée")
            for t, col in self.tombes:
                if ligne.get(col):
                    ids.retirer(tx, t, ligne[col], ligne.get(self.champ_libelle, ""), "supprimée")
        return {"id": ligne["id"], "avant": ligne}

    def prouver_supprimer(self, c, res):
        return not self.db.lire("SELECT 1 FROM %s WHERE id = ?" % self.table, (res["id"],))

    def defaire_supprimer(self, c, res):
        a = res["avant"]
        with self.db.transaction() as tx:
            tx.execute("INSERT INTO %s (%s) VALUES (%s)" % (self.table, ", ".join(a), ", ".join("?" * len(a))), tuple(a.values()))
            ids.restaurer(tx, self.type_ref, a["ref"])
            for t, col in self.tombes:
                if a.get(col):
                    ids.restaurer(tx, t, a[col])

    # ---- branchement ----
    def brancher(self, ctx, pluriel=None):
        """Inscrit les capacités `<id>s` (liste), `<id>` (une fiche), `<id>_save`, `<id>_delete`."""
        p = pluriel or self.id + "s"
        def liste(c, q="", limite=500):
            return {p: self.lister(c, q, limite)}

        def une(c, id=0):
            return {self.id: self.lire(c, id)}

        def sauve(c, **d):
            return self.sauver(c, **d)

        def supprime(c, id=0):
            return self.supprimer(c, id)

        ctx.implementer(p, liste)
        ctx.implementer(self.id, une)
        ctx.implementer(self.id + "_save", signer(sauve, *self.champs), self.prouver_sauver, self.defaire_sauver,
                        simuler=lambda x, **d: "enregistrerait %s « %s »" % (self.libelle, d.get(self.champ_libelle, d.get("id", "?"))))
        ctx.implementer(self.id + "_delete", supprime, self.prouver_supprimer, self.defaire_supprimer,
                        simuler=lambda x, id=0, **_: "supprimerait %s %s" % (self.libelle, id))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : signer, _ligne, Entite
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
