"""Bancs du module contacts : un vrai noyau, des comptes simulés, de vrais fichiers vCard et CSV."""
import base64
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau.bus import TOUT                 # noqa: E402

BEA, LEO = "bea@x.fr", "leo@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "contacts", mods / "contacts")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("contacts")["ok"])
        self.ctx = self.n.executeur.contextes["contacts"]
        self.e = self.n.executeur.executer

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("contacts." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def retour(self, cap, res):
        self.n.catalogue.get("contacts." + cap).defaire(self.ctx, res)

    def creer(self, nom="Alice Martin", emails=None, compte=BEA, **kw):
        return self.ok("creer", display_name=nom, emails=emails if emails is not None else [], compte=compte, **kw)["id"]

    def fiche(self, cid, compte=BEA):
        return self.ok("voir", id=cid, compte=compte)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def sql(self, requete, *args):
        return self.ctx.stockage.ecrire(requete, args)


class Fiches(Monde):
    def test_creer_prouve_et_defait(self):
        r = self.ex("creer", display_name="Alice Martin", emails=["Alice@Exemple.FR", "a2@exemple.fr"], phone="01 02 03 04 05", tags="client")
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(r["resultat"]["id"])
        self.assertEqual((f["emails"], f["addr"], f["phone"]), (["alice@exemple.fr", "a2@exemple.fr"], "alice@exemple.fr", "01 02 03 04 05"))
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.retour("creer", r["resultat"])
        self.assertEqual(self.ok("lister")["total"], 0)

    def test_un_nom_ou_une_adresse_et_le_nom_par_defaut(self):
        self.assertEqual(self.ex("creer", display_name="", emails=[])["statut"], "echec")
        cid = self.creer(nom="", emails=["jean.dupont@exemple.fr"])
        self.assertEqual(self.fiche(cid)["display_name"], "jean.dupont")

    def test_une_adresse_n_appartient_qu_a_une_fiche(self):
        self.creer(emails=["a@exemple.fr"])
        self.assertEqual(self.ex("creer", display_name="Autre", emails=["a@exemple.fr"])["statut"], "echec")
        self.assertEqual(self.ex("creer", display_name="Autre", emails=["pas-une-adresse"])["statut"], "echec")
        self.creer(nom="Autre", emails=["a@exemple.fr"], compte=LEO)          # un autre compte a son propre carnet

    def test_sans_compte_pas_de_carnet(self):
        for compte in ("", "cassandra", "operateur"):
            self.assertEqual(self.ex("creer", compte=compte, display_name="X")["statut"], "echec", compte)

    def test_modifier_est_un_patch_qui_ne_touche_pas_ce_qu_on_ne_dit_pas(self):
        cid = self.creer(emails=["a@exemple.fr"], phone="0102030405", company="Acme", notes="à rappeler")
        r = self.ex("modifier", id=cid, favorite=True)
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(cid)
        self.assertEqual((f["favorite"], f["emails"], f["phone"], f["company"], f["notes"]), (1, ["a@exemple.fr"], "0102030405", "Acme", "à rappeler"))
        self.ex("modifier", id=cid, company="")
        self.assertEqual(self.fiche(cid)["company"], "")                       # une chaîne vide efface
        self.assertEqual(self.fiche(cid)["phone"], "0102030405")

    def test_les_adresses_ne_sont_resynchronisees_que_si_elles_sont_fournies(self):
        cid = self.creer(emails=["a@exemple.fr", "b@exemple.fr"])
        self.ex("modifier", id=cid, emails=["c@exemple.fr"])
        self.assertEqual(self.fiche(cid)["emails"], ["c@exemple.fr"])
        autre = self.creer(nom="Autre", emails=["z@exemple.fr"])
        self.assertEqual(self.ex("modifier", id=cid, emails=["z@exemple.fr"])["statut"], "echec")        # pas volée
        self.assertEqual(self.fiche(autre)["emails"], ["z@exemple.fr"])

    def test_le_retour_d_une_modification_remet_la_fiche(self):
        cid = self.creer(emails=["a@exemple.fr"], phone="0102030405")
        r = self.ex("modifier", id=cid, phone="0999999999", emails=["b@exemple.fr"], favorite=True)
        self.retour("modifier", r["resultat"])
        f = self.fiche(cid)
        self.assertEqual((f["phone"], f["emails"], f["favorite"]), ("0102030405", ["a@exemple.fr"], 0))

    def test_les_champs_sont_bornes_et_la_photo_verifiee(self):
        cid = self.creer(nom="N" * 500, notes="x" * 9000)
        f = self.fiche(cid)
        self.assertEqual((len(f["display_name"]), len(f["notes"])), (120, 4000))
        self.ex("modifier", id=cid, photo="data:image/png;base64,AAAA")
        self.assertTrue(self.fiche(cid)["a_photo"])
        self.ex("modifier", id=cid, photo="http://pirate/x.png")
        self.assertFalse(self.fiche(cid)["a_photo"])                           # refusée, pas tronquée

    def test_chaque_compte_ne_voit_que_ses_fiches(self):
        cid = self.creer(emails=["a@exemple.fr"])
        for cap, args in (("voir", dict(id=cid)), ("modifier", dict(id=cid, company="x")), ("supprimer", dict(ids=[cid])), ("lier", dict(id=cid, kind="domain", ref="x.fr"))):
            self.assertEqual(self.ex(cap, compte=LEO, **args)["statut"], "echec", cap)
        self.assertEqual(self.ok("lister", compte=LEO)["total"], 0)
        self.assertEqual(self.ok("pour_adresse", compte=LEO, adresse="a@exemple.fr")["trouvee"], False)
        self.assertTrue(self.ok("pour_adresse", adresse="A@exemple.fr")["trouvee"])

    def test_recherche_favoris_tri(self):
        a = self.creer(nom="Zoé Zed", emails=["z@exemple.fr"], company="Acme")
        b = self.creer(nom="Alain Abel", phone="0612345678")
        self.ex("modifier", id=a, favorite=True)
        noms = [x["display_name"] for x in self.ok("lister")["contacts"]]
        self.assertEqual(noms, ["Zoé Zed", "Alain Abel"])                     # favoris d'abord
        self.assertEqual([x["id"] for x in self.ok("lister", query="acme")["contacts"]], [a])
        self.assertEqual([x["id"] for x in self.ok("lister", query="0612")["contacts"]], [b])
        self.assertEqual([x["id"] for x in self.ok("lister", favoris=True)["contacts"]], [a])


class CorbeilleArchiveDossiers(Monde):
    def test_la_corbeille_ne_detruit_rien_et_se_restaure(self):
        cid = self.creer(emails=["a@exemple.fr"])
        self.ok("lier", id=cid, kind="domain", ref="exemple.fr", role="client")
        r = self.ex("supprimer", ids=[cid])
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ok("lister")["total"], 0)
        self.assertEqual(self.ok("lister", vue="corbeille")["total"], 1)
        self.assertEqual(self.ok("voir", id=cid)["emails"], ["a@exemple.fr"])      # adresses et liens sont encore là
        self.assertEqual(len(self.ok("voir", id=cid)["links"]), 1)
        self.ok("restaurer", ids=[cid])
        self.assertEqual(self.ok("lister")["total"], 1)

    def test_les_retours_de_lot(self):
        a, b = self.creer(nom="A", emails=["a@x.fr"]), self.creer(nom="B", emails=["b@x.fr"])
        r = self.ex("supprimer", ids=[a, b])
        self.retour("supprimer", r["resultat"])
        self.assertEqual(self.ok("lister")["total"], 2)
        r = self.ex("archiver", ids=[a])
        self.assertEqual((self.ok("lister")["total"], self.ok("lister", vue="archive")["total"]), (1, 1))
        self.retour("archiver", r["resultat"])
        self.assertEqual(self.ok("lister")["total"], 2)

    def test_un_lot_est_borne_et_nettoye(self):
        a = self.creer(nom="A")
        r = self.ex("supprimer", ids=[a, a, "x", -3, 0])
        self.assertEqual(r["resultat"]["ids"], [a])
        self.assertEqual(self.ex("supprimer", ids=[])["statut"], "echec")
        self.assertEqual(self.ex("supprimer", ids=[99999])["statut"], "echec")

    def test_les_dossiers_comptent_les_fiches_vivantes_seulement(self):
        d = self.ok("dossier_enregistrer", nom="Clients")["id"]
        a, b, c = self.creer(nom="A"), self.creer(nom="B"), self.creer(nom="C")
        self.ok("deplacer", ids=[a, b, c], dossier_id=d)
        self.ok("supprimer", ids=[b])
        self.ok("archiver", ids=[c])
        ds = self.ok("dossiers")
        self.assertEqual(([x["n"] for x in ds["dossiers"]], ds["tout"], ds["archives"], ds["corbeille"]), ([1], 1, 1, 1))

    def test_deplacer_vers_un_dossier_inconnu_ou_d_autrui_est_refuse(self):
        d = self.ok("dossier_enregistrer", nom="Privé", compte=LEO)["id"]
        a = self.creer(nom="A")
        self.assertEqual(self.ex("deplacer", ids=[a], dossier_id=d)["statut"], "echec")
        self.assertEqual(self.ex("modifier", id=a, dossier_id=d)["statut"], "echec")
        self.assertEqual(self.ex("creer", display_name="X", dossier_id=d)["statut"], "echec")

    def test_un_seul_niveau_de_dossier_et_renommer(self):
        d = self.ok("dossier_enregistrer", nom="Clients")["id"]
        s = self.ok("dossier_enregistrer", nom="Paris", parent_id=d)["id"]
        self.assertEqual(self.ex("dossier_enregistrer", nom="Quartier", parent_id=s)["statut"], "echec")
        self.assertEqual(self.ex("dossier_enregistrer", nom="Boucle", id=d, parent_id=d)["statut"], "echec")
        r = self.ex("dossier_enregistrer", nom="Grands comptes", id=d)
        self.assertEqual(r["statut"], "faite", r)
        self.retour("dossier_enregistrer", r["resultat"])
        self.assertEqual([x["nom"] for x in self.ok("dossiers")["dossiers"] if x["id"] == d], ["Clients"])
        self.assertEqual(self.ex("dossier_enregistrer", nom="  ")["statut"], "echec")

    def test_supprimer_un_dossier_ne_supprime_pas_ses_fiches_et_se_defait(self):
        d = self.ok("dossier_enregistrer", nom="Clients")["id"]
        s = self.ok("dossier_enregistrer", nom="Paris", parent_id=d)["id"]
        a = self.creer(nom="A")
        self.ok("deplacer", ids=[a], dossier_id=d)
        r = self.ex("dossier_supprimer", id=d)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual((self.fiche(a)["dossier_id"], [x["parent_id"] for x in self.ok("dossiers")["dossiers"]]), (0, [0]))
        self.retour("dossier_supprimer", r["resultat"])
        self.assertEqual(self.fiche(a)["dossier_id"], d)
        self.assertEqual({x["id"]: x["parent_id"] for x in self.ok("dossiers")["dossiers"]}, {d: 0, s: d})

    def test_la_purge_n_efface_que_ce_qui_a_depasse_trente_jours_et_se_defait(self):
        vieux, recent = self.creer(nom="Vieux", emails=["v@x.fr"]), self.creer(nom="Récent", emails=["r@x.fr"])
        self.ok("lier", id=vieux, kind="domain", ref="x.fr")
        self.ok("supprimer", ids=[vieux, recent])
        self.sql("UPDATE contacts SET supprime_at = ? WHERE id = ?", time.time() - 40 * 86400, vieux)
        r = self.ex("purger_corbeille")
        self.assertEqual((r["statut"], r["resultat"]["purgees"]), ("faite", 1), r)
        self.assertEqual(self.ok("lister", vue="corbeille")["total"], 1)
        self.retour("purger_corbeille", r["resultat"])
        f = self.fiche(vieux)
        self.assertEqual((f["emails"], len(f["links"])), (["v@x.fr"], 1))
        self.assertEqual(self.ok("lister", vue="corbeille")["total"], 2)


class Liens(Monde):
    def setUp(self):
        super().setUp()
        self.cid = self.creer(emails=["a@exemple.fr"])

    def test_lier_valide_normalise_et_se_defait(self):
        r = self.ex("lier", id=self.cid, kind="domain", ref="https://www.Exemple.fr/accueil", role="technique")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["ref"], "exemple.fr")
        for args in (dict(kind="inconnu", ref="x"), dict(kind="domain", ref="x.fr", role="roi"), dict(kind="domain", ref="")):
            self.assertEqual(self.ex("lier", id=self.cid, **args)["statut"], "echec", args)
        self.retour("lier", r["resultat"])
        self.assertEqual(self.fiche(self.cid)["links"], [])

    def test_une_deduction_ne_remplace_pas_un_lien_pose_a_la_main(self):
        self.ok("lier", id=self.cid, kind="project", ref="12", role="client", label="Refonte")
        r = self.ex("lier", id=self.cid, kind="project", ref="12", role="autre", auto=True)
        self.assertTrue(r["resultat"]["inchange"])
        l = self.fiche(self.cid)["links"][0]
        self.assertEqual((l["role"], l["label"], l["auto"]), ("client", "Refonte", 0))
        self.retour("lier", r["resultat"])
        self.assertEqual(len(self.fiche(self.cid)["links"]), 1)

    def test_remplacer_un_lien_se_defait_vers_l_ancien(self):
        self.ok("lier", id=self.cid, kind="server", ref="web1", role="technique")
        r = self.ex("lier", id=self.cid, kind="server", ref="web1", role="client")
        self.retour("lier", r["resultat"])
        self.assertEqual(self.fiche(self.cid)["links"][0]["role"], "technique")

    def test_delier_et_son_retour(self):
        self.ok("lier", id=self.cid, kind="domain", ref="exemple.fr")
        r = self.ex("delier", id=self.cid, kind="domain", ref="exemple.fr")
        self.assertEqual(self.fiche(self.cid)["links"], [])
        self.retour("delier", r["resultat"])
        self.assertEqual(len(self.fiche(self.cid)["links"]), 1)
        self.assertEqual(self.ex("delier", id=self.cid, kind="domain", ref="autre.fr")["statut"], "echec")

    def test_les_contacts_d_une_cible_par_ordre_de_role_et_sans_la_corbeille(self):
        b = self.creer(nom="Bruno", emails=["b@exemple.fr"])
        c = self.creer(nom="Chloé", emails=["c@exemple.fr"])
        self.ok("lier", id=self.cid, kind="domain", ref="exemple.fr", role="client")
        self.ok("lier", id=b, kind="domain", ref="exemple.fr", role="technique")
        self.ok("lier", id=c, kind="domain", ref="exemple.fr", role="facturation")
        self.ok("supprimer", ids=[c])
        r = self.ok("pour_cible", kind="domain", ref="www.exemple.fr")
        self.assertEqual([(x["display_name"], x["role"]) for x in r["contacts"]], [("Bruno", "technique"), ("Alice Martin", "client")])
        self.assertEqual(self.ok("pour_cible", kind="domain", ref="exemple.fr", compte=LEO)["contacts"], [])


class Doublons(Monde):
    def mettre(self, cid, **champs):
        self.ex("modifier", id=cid, **champs)

    def niveaux(self):
        return {k: v for k, v in self.ok("doublons")["paires"].items() if v}

    def vieillir(self, *ids):
        """Des fiches saisies à des moments différents : sinon nom + numéro identiques les feraient passer pour des jumelles d'import."""
        for i, cid in enumerate(ids):
            self.sql("UPDATE contacts SET created_at = created_at - ? WHERE id = ?", 7200 * (i + 1), cid)

    def test_nom_plus_telephone_est_probable_et_le_numero_se_compare_par_ses_neuf_derniers_chiffres(self):
        a = self.creer(nom="Julie Danet", phone="06 88 41 22 09")
        b = self.creer(nom="Paul Autre", mobile="+33 6 88 41 22 09")
        b2 = self.creer(nom="Julie  Danet", mobile="0033688412209")
        self.vieillir(a, b, b2)
        n = self.niveaux()
        self.assertEqual({(p["a"], p["b"]) for p in n["probable"]}, {(a, b2)})            # même nom, même numéro écrit de trois façons
        self.assertEqual({(p["a"], p["b"]) for p in n["piege"]}, {(a, b), (b, b2)})       # même numéro, noms différents

    def test_les_niveaux(self):
        a = self.creer(nom="Julie Danet", phone="0688412209", company="Acme SARL")
        b = self.creer(nom="Julie Danet", company="ACME")
        c = self.creer(nom="Paul Autre", phone="0688412209")
        d = self.creer(nom="Julie Danet")
        n = self.niveaux()
        self.assertEqual(sorted(n), ["piege", "possible", "probable"])
        self.assertEqual(n["piege"][0]["motif"], "même numéro, noms différents : famille, pro ou numéro recyclé")
        self.assertEqual({(p["a"], p["b"]) for p in n["probable"]}, {(a, b)})            # nom + société (la forme juridique ne compte pas)
        self.assertEqual({(p["a"], p["b"]) for p in n["possible"]}, {(a, d), (b, d)})     # nom seul

    def test_les_initiales_se_reconnaissent_mais_pas_deux_personnes_qui_partagent_une_initiale(self):
        a = self.creer(nom="Julie Danet", phone="0688412209")
        b = self.creer(nom="J. Danet", phone="0688412209")
        c = self.creer(nom="Jean Dupont", phone="0688412209")
        self.vieillir(a, b, c)
        n = self.niveaux()
        self.assertEqual({(p["a"], p["b"]) for p in n["probable"]}, {(a, b)})            # initiales développées + numéro
        self.assertEqual({(p["a"], p["b"]) for p in n["piege"]}, {(a, c), (b, c)})        # « Jean Dupont » n'a que l'initiale en commun
        self.assertIn("initiales", n["probable"][0]["signaux"][0] + n["probable"][0]["signaux"][1])

    def test_un_nom_d_emojis_garde_sa_signature(self):
        self.creer(nom="🚫🚫🚫")
        self.creer(nom="🚫🚫🚫")
        self.creer(nom="⭐⭐")
        self.assertEqual(len(self.niveaux()["possible"]), 1)

    def test_les_jumelles_d_import_se_distinguent_du_probable(self):
        a = self.creer(nom="Julie Danet", phone="0688412209", source="csv")
        b = self.creer(nom="Julie Danet", phone="0688412209", source="csv")
        self.assertEqual(list(self.niveaux()), ["jumelles"])
        self.sql("UPDATE contacts SET created_at = created_at - 3600 WHERE id = ?", b)
        self.assertEqual(list(self.niveaux()), ["probable"])

    def test_pas_la_meme_personne_est_retenu_et_se_defait(self):
        a, b = self.creer(nom="Julie Danet"), self.creer(nom="Julie Danet")
        r = self.ex("pas_doublon", a=b, b=a)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.niveaux(), {})
        self.retour("pas_doublon", r["resultat"])
        self.assertEqual(list(self.niveaux()), ["possible"])
        self.assertEqual(self.ex("pas_doublon", a=a, b=a)["statut"], "echec")
        self.assertEqual(self.ex("pas_doublon", compte=LEO, a=a, b=b)["statut"], "echec")

    def test_la_corbeille_et_l_archive_ne_comptent_pas(self):
        a, b = self.creer(nom="Julie Danet"), self.creer(nom="Julie Danet")
        self.ok("supprimer", ids=[b])
        self.assertEqual(self.niveaux(), {})


class Fusion(Monde):
    def setUp(self):
        super().setUp()
        self.a = self.creer(nom="a1", emails=["a1@x.fr"], company="Acme", tags="vip", notes="note A", favorite=True)
        self.b = self.creer(nom="Julie Danet", emails=["julie@x.fr"], phone="0102030405", tags="client, vip", notes="note B")
        self.ok("lier", id=self.a, kind="project", ref="7", role="client")
        self.ok("lier", id=self.b, kind="project", ref="7", role="technique")
        self.ok("lier", id=self.a, kind="domain", ref="x.fr")

    def test_la_fusion_garde_tout_et_laisse_la_source_a_la_corbeille(self):
        r = self.ex("fusionner", source=self.a, destination=self.b)
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(self.b)
        self.assertEqual(sorted(f["emails"]), ["a1@x.fr", "julie@x.fr"])
        self.assertEqual((f["display_name"], f["company"], f["phone"], f["favorite"]), ("Julie Danet", "Acme", "0102030405", 1))
        self.assertEqual(f["tags"], "client, vip")                              # étiquettes réunies sans doublon
        self.assertEqual(f["notes"], "note B\n\nnote A")
        self.assertEqual({(l["kind"], l["ref"], l["role"]) for l in f["links"]}, {("project", "7", "technique"), ("domain", "x.fr", "autre")})
        s = self.fiche(self.a)
        self.assertEqual((s["fusion_vers"], s["supprime_at"] is not None, s["emails"]), (self.b, True, []))

    def test_le_nom_de_la_destination_tiré_de_l_adresse_cede_la_place_au_vrai_nom(self):
        c = self.creer(nom="julie", emails=["julie@y.fr"])
        self.ok("fusionner", source=self.b, destination=c)
        self.assertEqual(self.fiche(c)["display_name"], "Julie Danet")

    def test_le_retour_remet_les_deux_fiches_telles_qu_elles_etaient(self):
        avant_a, avant_b = self.fiche(self.a), self.fiche(self.b)
        r = self.ex("fusionner", source=self.a, destination=self.b)
        self.retour("fusionner", r["resultat"])
        self.assertEqual(self.fiche(self.a), avant_a)
        self.assertEqual(self.fiche(self.b), avant_b)

    def test_fusionner_avec_soi_ou_une_fiche_d_autrui_est_refuse(self):
        self.assertEqual(self.ex("fusionner", source=self.a, destination=self.a)["statut"], "echec")
        autre = self.creer(nom="X", compte=LEO)
        self.assertEqual(self.ex("fusionner", source=self.a, destination=autre)["statut"], "echec")

    def test_la_fusion_en_lot_ne_prend_que_le_certain(self):
        j1 = self.creer(nom="Marc Lenoir", phone="0611223344", source="csv")
        j2 = self.creer(nom="Marc Lenoir", phone="0611223344", source="csv")
        p1 = self.creer(nom="Lola Petit", phone="0655443322", source="manuel")
        self.ex("modifier", id=p1, company="Zeta")
        p2 = self.creer(nom="Lola Petit", phone="0655443322", source="manuel")
        self.sql("UPDATE contacts SET created_at = created_at - 7200 WHERE id = ?", p2)
        r = self.ex("fusionner_certaines")
        self.assertEqual((r["statut"], r["resultat"]["n"]), ("faite", 1), r)
        vivantes = {x["id"] for x in self.ok("lister")["contacts"]}
        self.assertTrue({p1, p2} <= vivantes)                                      # le probable n'est pas touché
        self.assertEqual(len(vivantes & {j1, j2}), 1)
        self.retour("fusionner_certaines", r["resultat"])
        self.assertTrue({j1, j2} <= {x["id"] for x in self.ok("lister")["contacts"]})


class Echanges(Monde):
    def test_vcard_aller_retour_avec_virgules_accents_et_lignes_longues(self):
        cid = self.creer(nom="Hélène Dupont-Müller", emails=["h@exemple.fr", "h2@exemple.fr"], phone="01 02 03 04 05", mobile="06 07 08 09 10", company="Acme, Fils; Cie",
                         job_title="Directrice", address="12 rue de la Paix, 75002 Paris", website="https://exemple.fr", tags="vip,client", notes="Ligne 1\nLigne 2 " + "mot " * 60)
        v = self.ok("vcard_exporter")
        self.assertEqual(v["fiches"], 1)
        self.assertTrue(all(len(l.encode()) <= 75 for l in v["vcard"].split("\r\n")))
        r = self.ex("vcard_importer", compte=LEO, texte=v["vcard"])
        self.assertEqual(r["statut"], "faite", r)
        f = self.ok("lister", compte=LEO)["contacts"][0]
        o = self.fiche(cid)
        for k in ("display_name", "company", "job_title", "phone", "mobile", "website", "tags", "notes", "emails"):
            self.assertEqual(f[k], o[k], k)

    def test_importer_complete_sans_dupliquer_et_se_defait(self):
        cid = self.creer(nom="Alice", emails=["a@x.fr"])
        texte = "BEGIN:VCARD\nVERSION:3.0\nFN:Alice Martin\nEMAIL:a@x.fr\nTEL;TYPE=CELL:0611223344\nORG:Acme\nEND:VCARD\nBEGIN:VCARD\nFN:Bob\nEMAIL:b@x.fr\nEND:VCARD\nBEGIN:VCARD\nFN:Sans adresse\nEND:VCARD\n"
        r = self.ex("vcard_importer", texte=texte)
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual((len(res["crees"]), len(res["completees"])), (2, 1))
        f = self.fiche(cid)
        self.assertEqual((f["display_name"], f["mobile"], f["company"]), ("Alice", "0611223344", "Acme"))     # champs vides complétés, le nom existant gardé
        self.assertEqual(self.ok("lister")["total"], 3)
        self.retour("vcard_importer", res)
        self.assertEqual(self.ok("lister")["total"], 1)
        self.assertEqual((self.fiche(cid)["mobile"], self.fiche(cid)["company"]), ("", ""))

    def test_un_fichier_sans_fiche_est_refuse(self):
        self.assertEqual(self.ex("vcard_importer", texte="rien")["statut"], "echec")

    def csv(self, texte, enc="utf-8"):
        return base64.b64encode(texte.encode(enc)).decode()

    def test_apercu_csv_dit_ce_qu_il_a_compris_avant_d_ecrire(self):
        b = self.csv("Prénom;Nom;E-mail;Téléphone;Société\nLéa;Durand;lea@x.fr;0102030405;Acme\nPaul;Petit;paul@x.fr;;Zed\n", "cp1252")
        a = self.ok("csv_apercu", contenu_b64=b)
        self.assertEqual((a["encodage"], a["separateur"], a["lignes"], a["utilisable"]), ("cp1252", ";", 2, True))
        self.assertEqual(sorted(a["reconnus"]), ["_nom", "_prenom", "company", "emails", "phone"])
        self.assertEqual(self.ok("lister")["total"], 0)

    def test_import_csv_assemble_prenom_et_nom_et_decoupe_les_adresses(self):
        b = self.csv("First Name,Last Name,Email,Mobile\nLéa,Durand,\"lea@x.fr; lea2@x.fr\",0611223344\n,,seul@x.fr,\n")
        r = self.ex("csv_importer", contenu_b64=b)
        self.assertEqual(r["statut"], "faite", r)
        noms = {x["display_name"]: x for x in self.ok("lister")["contacts"]}
        self.assertEqual(noms["Léa Durand"]["emails"], ["lea@x.fr", "lea2@x.fr"])
        self.assertEqual(noms["seul"]["emails"], ["seul@x.fr"])
        self.retour("csv_importer", r["resultat"])
        self.assertEqual(self.ok("lister")["total"], 0)

    def test_csv_vide_inconnu_ou_trop_gros(self):
        self.assertEqual(self.ex("csv_apercu", contenu_b64="")["statut"], "echec")
        self.assertEqual(self.ex("csv_apercu", contenu_b64=self.csv("a\n"))["statut"], "echec")
        r = self.ex("csv_importer", contenu_b64=self.csv("machin;truc\n1;2\n"))
        self.assertEqual(r["statut"], "echec")
        self.assertIn("aucune colonne", json.dumps(r, ensure_ascii=False))

    def test_l_appariement_manuel_l_emporte(self):
        b = self.csv("colA;colB\nZoé;zoe@x.fr\n")
        r = self.ex("csv_importer", contenu_b64=b, appariement={"0": "display_name", "1": "emails"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ok("lister")["contacts"][0]["emails"], ["zoe@x.fr"])


class VueModele(Monde):
    def setUp(self):
        super().setUp()
        self.cid = self.creer(nom="Alice", emails=["a@x.fr"], phone="0102030405", address="1 rue X", notes="rappeler avant 10 h", company="Acme")

    def vu(self, acteur):
        return self.e("contacts.voir", acteur, {"id": self.cid}, compte=BEA)["resultat"]

    def test_un_humain_voit_tout(self):
        v = self.vu("humain")
        self.assertEqual((v["emails"], v["phone"], v["notes"]), (["a@x.fr"], "0102030405", "rappeler avant 10 h"))

    def test_un_modele_voit_la_presence_des_coordonnees_pas_leur_valeur(self):
        for qui in ("itare", "cassandra"):
            v = self.vu(qui)
            for k in ("emails", "addr", "phone", "mobile", "address"):
                self.assertNotIn(k, v, (qui, k))
            self.assertEqual((v["has_email"], v["has_phone"], v["has_address"], v["redacted"], v["company"]), (True, True, True, True, "Acme"))
            self.assertEqual(v["notes"], "rappeler avant 10 h")                # le contexte accompagne, par défaut

    def test_les_notes_peuvent_rester_au_serveur(self):
        self.n.reglages.poser("contacts.notes_au_modele", False)
        v = self.vu("itare")
        self.assertNotIn("notes", v)
        self.assertTrue(v["has_notes"])

    def test_la_vue_complete_est_un_choix_de_l_administrateur(self):
        self.n.reglages.poser("contacts.vue_modele", "complete")
        v = self.vu("itare")
        self.assertEqual(v["emails"], ["a@x.fr"])

    def test_la_liste_expurge_aussi_et_ne_porte_pas_la_photo(self):
        self.ex("modifier", id=self.cid, photo="data:image/png;base64,AAAA")
        l = self.e("contacts.lister", "itare", {}, compte=BEA)["resultat"]["contacts"][0]
        self.assertNotIn("emails", l)
        self.assertNotIn("photo", l)


if __name__ == "__main__":
    unittest.main()
