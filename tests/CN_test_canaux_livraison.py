# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la livraison des notifications par les canaux
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #3a3dae
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la livraison des notifications par les canaux : du constat au message Telegram, avec le vrai noyau et un faux Telegram.
# MÉTHODE    : les vrais modules notifications, canaux et telegram ; l'heure est décalée pour franchir la grâce du démarrage et les heures calmes
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3a3dae ▼▼▼
"""Bancs de la livraison : un constat devient une notification, le moteur des canaux demande la politique du destinataire à notifications, et le robot Telegram de
CE destinataire la porte. Le vrai noyau, les vrais modules ; seul Telegram est faux (celui des bancs du module telegram). L'heure est décalée (jamais attendue)
pour franchir la grâce du démarrage, la fin des heures calmes et les retentes."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                                              # noqa: E402
from noyau.CN_bus import TOUT                                         # noqa: E402
from CN_test_telegram import FauxTelegram, JETON, JETON2, PUBLIC      # noqa: E402

CHEF, BEA, ZOE = "chef@exemple.test", "bea@exemple.test", "zoe@exemple.test"
VRAIE_HEURE = time.time
GRACE_S = 5 * 60


class Monde(unittest.TestCase):
    def setUp(self):
        self.tg = FauxTelegram()
        self.addCleanup(self.tg.arreter)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("notifications", "canaux", "telegram", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.addCleanup(self.n.arreter)
        self.n.etat_modules.poser("canaux", installe=True, par="banc")       # le module a un script d'installation
        for m in ("droits", "comptes", "notifications", "telegram", "canaux"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.reglages.poser("telegram.api", self.tg.url)
        self.n.reglages.poser("telegram.url_publique", PUBLIC)
        self.n.droits.regler_admin(CHEF, True)
        self.robot(BEA, JETON, "4242")
        self.robot(CHEF, JETON2, "777")
        self.avance = GRACE_S + 60                                          # par défaut, la grâce du démarrage est passée
        p = mock.patch("time.time", lambda: VRAIE_HEURE() + self.avance)
        p.start()
        self.addCleanup(p.stop)

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, capacite, compte=BEA, **args):
        r = self.ex(capacite, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def robot(self, compte, jeton, chat):
        """Un robot branché, dont le destinataire a été essayé pour de bon auprès de Telegram."""
        self.n.reglages.poser("telegram.jeton", jeton, compte)
        self.tg.demarres.add(chat)
        self.s("telegram.brancher", compte=compte)
        self.s("telegram.cible_poser", compte=compte, valeur=chat)

    def constat(self, compte=BEA, niveau="critique", site="exemple.test", source="sites"):
        """Ce que le noyau émet quand un détecteur ouvre un constat : notifications en fait une notification, adressée au compte du constat (ou aux administrateurs)."""
        return self.n.bus.emettre("constat.ouvert", source=source, acteur="sonde", objet=("site", site), compte=compte,
                                  donnees={"detecteur": "panne", "titre": "%s ne répond plus" % site, "detail": "trois mesures ratées de suite", "niveau": niveau})

    def ranges(self):
        """« noter » est asynchrone (une file, pour ne perdre aucune notification) : on attend qu'il ait rangé chacune de celles qui ont été émises."""
        attendu, fin = len(self.evts("notification.emise")), VRAIE_HEURE() + 15
        while VRAIE_HEURE() < fin:
            if next(m["executions"] for m in self.n.etat_moteurs() if m["cle"] == "canaux.noter") >= attendu:
                return
            time.sleep(0.02)
        self.fail("le moteur canaux.noter n'a pas rangé les notifications émises")

    def passe(self):
        self.ranges()
        r = self.n.lancer("canaux.livrer")
        self.assertEqual(r["statut"], "fait", r)                            # quoi qu'il arrive à Telegram, le moteur finit sa passe

    def recus(self, chat="4242"):
        return [texte for _, c, texte in self.tg.messages if c == chat]

    def file(self, compte=CHEF):
        return self.s("canaux.livraisons", compte=compte)["livraisons"]

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]


class Livrer(Monde):
    def test_une_panne_critique_part_sur_le_telegram_du_proprietaire(self):
        self.constat()
        self.assertEqual(self.recus(), [])                                  # l'événement range, il n'envoie pas : c'est le moteur périodique qui porte
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertIn("Critique — exemple.test ne répond plus", self.recus()[0])
        self.assertIn("trois mesures ratées de suite", self.recus()[0])
        self.assertEqual(self.recus("777"), [])                             # adressée à Béa : l'administrateur n'en reçoit pas la copie
        dem = [e for e in self.evts("capacite.demandee") if e["objet_id"] == "telegram.prevenir"]
        self.assertEqual([(e["compte"], e["acteur"]) for e in dem], [("noyau", "cassandra")])       # un acte ordinaire, journalisé, au nom du compte système
        self.assertEqual([(x["compte"], x["canal"], x["etat"]) for x in self.file()], [(BEA, "telegram", "livree")])
        self.assertEqual(len(self.evts("livraison.faite")), 1)

    def test_un_constat_sans_compte_part_chez_les_administrateurs(self):
        self.constat(compte="")
        self.passe()
        self.assertEqual(len(self.recus("777")), 1)
        self.assertEqual(self.recus(), [])

    def test_une_notification_qui_se_repete_ne_sonne_qu_une_fois(self):
        self.constat()
        self.passe()
        self.constat()                                                      # la même panne revue : la notification compte, elle n'est pas réémise
        self.passe()
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertEqual(self.s("notifications.lister")["notifications"][0]["n"], 2)

    def test_le_niveau_decide_et_l_escalade_se_dit(self):
        a = {"titre": "Disque bientôt plein", "source": "disque", "cle": "disque:plein", "dest": [BEA]}
        self.s("notifications.emettre", niveau="avoir", **a)
        self.passe()
        self.assertEqual(self.recus(), [])                                  # la politique par défaut ne met pas Telegram sur « à voir »
        self.assertEqual(self.file(), [])
        self.s("notifications.emettre", niveau="critique", **a)             # la même, devenue critique
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertIn("Critique — Disque bientôt plein", self.recus()[0])

    def test_la_politique_de_chacun_est_la_sienne(self):
        self.s("notifications.prefs", calmes=False)
        self.s("notifications.politique_ecrire", niveau="avoir", canaux=["telegram"])
        self.s("notifications.politique_ecrire", compte=CHEF, niveau="critique", canaux=[])     # le chef ne veut que la cloche
        self.s("notifications.emettre", compte=CHEF, titre="Un mot", source="essai_banc", niveau="avoir", dest=[BEA, CHEF])
        self.constat(compte="")
        self.passe()
        self.assertEqual(len(self.recus()), 1)                              # Béa a mis Telegram sur « à voir »
        self.assertEqual(self.recus("777"), [])                             # le chef ne reçoit ni l'une (défaut) ni l'autre (son choix)

    def test_un_compte_sans_robot_ne_casse_rien(self):
        self.constat(compte=ZOE)
        self.constat(compte=BEA, site="autre.exemple.test")
        self.passe()
        self.assertEqual(len(self.recus()), 1)                              # celle de Béa part quand même
        zoe = [x for x in self.file() if x["compte"] == ZOE][0]
        self.assertEqual(zoe["etat"], "tue")
        self.assertIn("robot", zoe["motif"])


class Retenir(Monde):
    def test_la_grace_du_demarrage_retient_puis_laisse_partir(self):
        self.avance = 0
        self.constat()
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertIn("grâce", self.file()[0]["motif"])
        self.avance = GRACE_S + 60
        self.passe()
        self.assertEqual(len(self.recus()), 1)

    def test_une_panne_resolue_pendant_la_grace_ne_part_pas(self):
        self.avance = 0
        ev = self.constat()
        self.passe()
        self.n.bus.emettre("constat.resolu", source="sites", acteur="sonde", cause=ev, compte=BEA, donnees={"cle": "sites.panne:site:exemple.test"})
        self.avance = GRACE_S + 60
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertEqual(self.file()[0]["etat"], "tue")

    def test_les_heures_calmes_retiennent_tout_sauf_une_critique(self):
        ici = time.localtime(time.time())
        heure = lambda d: "%02d:%02d" % (((ici.tm_hour + d) % 24), ici.tm_min)
        self.s("notifications.prefs", calmes=True, calme_debut=heure(-1), calme_fin=heure(1))
        self.s("notifications.politique_ecrire", niveau="avoir", canaux=["telegram"])
        self.s("notifications.emettre", titre="Certificat à renouveler", source="certificats", niveau="avoir", dest=[BEA])
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertIn("heures calmes", self.file()[0]["motif"])
        self.constat()                                                      # une critique, elle, réveille
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertIn("Critique", self.recus()[0])
        self.avance += 3600 + 120                                           # les heures calmes sont finies
        self.passe()
        self.assertEqual(len(self.recus()), 2)
        self.assertIn("À voir — Certificat à renouveler", self.recus()[1])

    def test_ce_qui_a_ete_lu_dans_la_cloche_pendant_les_heures_calmes_ne_part_plus(self):
        ici = time.localtime(time.time())
        heure = lambda d: "%02d:%02d" % (((ici.tm_hour + d) % 24), ici.tm_min)
        self.s("notifications.prefs", calmes=True, calme_debut=heure(-1), calme_fin=heure(1))
        self.s("notifications.politique_ecrire", niveau="avoir", canaux=["telegram"])
        nid = self.s("notifications.emettre", titre="Certificat à renouveler", source="certificats", niveau="avoir", dest=[BEA])["id"]
        self.passe()
        self.s("notifications.vu", id=nid)
        self.avance += 3600 + 120
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertIn("déjà lue", self.file()[0]["motif"])

    def test_une_sourdine_fait_taire_la_source_pour_celui_qui_l_a_posee(self):
        self.s("notifications.sourdine", portee="source", cible="sites", heures=2)
        self.constat()
        self.constat(compte=CHEF, site="autre.exemple.test")
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertEqual(len(self.recus("777")), 1)                         # la sourdine de Béa ne fait taire personne d'autre
        bea = [x for x in self.file() if x["compte"] == BEA][0]
        self.assertEqual((bea["etat"], bea["motif"]), ("tue", "sourdine posée par le compte"))
        self.assertEqual(len(self.s("notifications.lister")["notifications"]), 1)       # la cloche, elle, a reçu

    def test_le_frein_des_envois_retient_puis_laisse_partir(self):
        self.n.freiner("envois", True, "banc")
        self.constat()
        self.passe()
        self.assertEqual(self.recus(), [])
        self.assertEqual([e for e in self.evts("capacite.demandee") if e["objet_id"] == "telegram.prevenir"], [])     # rien n'a même été tenté
        etat = self.s("canaux.livraisons", compte=CHEF)
        self.assertEqual((etat["frein"], etat["attente"]), ("envois", 1))                                              # et cela se voit
        self.n.freiner("envois", False, "banc")
        self.passe()
        self.assertEqual(len(self.recus()), 1)

    def test_le_gel_de_l_autonomie_retient_aussi(self):
        self.n.freiner("gel", True, "banc")
        self.constat()
        self.passe()
        self.assertEqual(self.recus(), [])
        etat = self.s("canaux.livraisons", compte=CHEF)
        self.assertEqual((etat["frein"], etat["attente"]), ("gel", 1))
        self.n.freiner("gel", False, "banc")
        self.passe()
        self.assertEqual(len(self.recus()), 1)


class Echouer(Monde):
    def test_un_refus_de_telegram_se_retente_puis_se_dit_sans_rien_casser(self):
        self.tg.refus_envoi = True
        self.constat()
        self.passe()
        l = self.file()[0]
        self.assertEqual((l["etat"], l["tentatives"]), ("attente", 1))
        self.assertIn("blocked", l["motif"])
        self.passe()                                                        # trop tôt : la retente attend une minute
        self.assertEqual(self.file()[0]["tentatives"], 1)
        self.avance += 61
        self.passe()
        self.avance += 301
        self.passe()
        l = self.file()[0]
        self.assertEqual((l["etat"], l["tentatives"]), ("echec", 3))
        self.assertEqual(len(self.evts("livraison.echouee")), 1)
        self.assertEqual(self.s("canaux.livraisons", compte=CHEF)["echecs"], 1)
        self.tg.refus_envoi = False
        self.avance += 3600
        self.passe()
        self.assertEqual(self.recus(), [])                                  # un échec dit ne repart pas tout seul
        self.assertEqual(self.n.catalogue.savoir("telegram.prevenir")["palier"], "auto")     # un refus est un résultat : il ne fait pas redescendre le palier
        self.assertEqual(len(self.s("notifications.lister")["notifications"]), 1)            # et la cloche a reçu

    def test_un_refus_passager_part_a_la_retente(self):
        self.tg.refus_envoi = True
        self.constat()
        self.passe()
        self.tg.refus_envoi = False
        self.avance += 61
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertEqual(self.file()[0]["etat"], "livree")


class Portes(Monde):
    def test_prevenir_n_est_ouverte_qu_au_moteur_des_canaux(self):
        a = {"compte": BEA, "texte": "bonjour"}
        self.assertEqual(self.ex("telegram.prevenir", **a)["statut"], "refuse")                                # un humain : la capacité ne le nomme pas
        self.assertEqual(self.ex("telegram.prevenir", acteur="itare", **a)["statut"], "refuse")
        r = self.ex("telegram.prevenir", acteur="cassandra", **a)                                                # Cassandra au nom de Béa : un résultat, pas un envoi
        self.assertEqual((r["statut"], r["resultat"]["ok"], r["resultat"]["cause"]), ("faite", False, "reserve"))
        r = self.n.executeur.executer("telegram.prevenir", "cassandra", a, compte="noyau", appelant="sites")     # un autre moteur, sous le même compte système
        self.assertEqual((r["resultat"]["ok"], r["resultat"]["cause"]), (False, "reserve"))
        self.assertEqual(self.recus(), [])
        self.assertEqual(self.n.catalogue.savoir("telegram.prevenir")["palier"], "auto")                         # un appel d'ailleurs ne fait pas redescendre le palier

    def test_envoyer_garde_son_palier(self):
        self.constat()
        self.passe()
        self.assertEqual(self.n.catalogue.savoir("telegram.envoyer")["palier"], "raconter")
        r = self.ex("telegram.envoyer", acteur="cassandra", texte="bonjour")
        self.assertEqual(r["statut"], "racontee")                           # Cassandra raconte toujours avant d'écrire sur Telegram
        self.assertEqual(len(self.recus()), 1)                              # seule la notification est partie

    def test_un_compte_ne_lit_pas_la_politique_d_un_autre(self):
        nid = self.s("notifications.emettre", compte=CHEF, titre="Un mot", source="essai_banc", niveau="critique", dest=[BEA])["id"]
        self.assertEqual(self.ex("notifications.livraison", compte=CHEF, id=nid)["statut"], "refuse")                        # un humain, même administrateur
        self.assertEqual(self.ex("notifications.livraison", compte=CHEF, acteur="cassandra", id=nid)["statut"], "echec")     # Cassandra au nom d'un compte
        r = self.ex("notifications.livraison", compte="", acteur="cassandra", id=nid)                                        # un moteur : aucun compte n'agit
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual([(d["compte"], d["canaux"]) for d in r["resultat"]["destinataires"]], [(BEA, ["mail", "telegram"])])

    def test_la_politique_dit_ce_qui_porte_vraiment(self):
        p = self.s("notifications.politique")["canaux"]
        self.assertTrue(p["telegram"]["declare"])
        self.assertIn("Telegram porte vos notifications", p["portes"])
        self.assertIn("le courriel et le webhook n'envoient pas encore", p["portes"])
        self.assertFalse(p["mail"]["declare"])
        z = self.s("notifications.politique", compte=ZOE)["canaux"]
        self.assertFalse(z["telegram"]["declare"])
        self.assertIn("aucun robot", z["portes"])

    def test_l_essai_de_telegram_passe_par_le_vrai_chemin(self):
        ici = time.localtime(time.time())
        heure = lambda d: "%02d:%02d" % (((ici.tm_hour + d) % 24), ici.tm_min)
        self.s("notifications.prefs", calmes=True, calme_debut=heure(-1), calme_fin=heure(1))       # un essai ne regarde pas les heures calmes : on vient de le demander
        r = self.s("notifications.essai", canal="telegram")
        self.assertTrue(r["ok"])
        self.assertFalse(self.s("notifications.politique")["canaux"]["essais"]["telegram"]["ok"])   # confié, pas encore arrivé : on ne le prétend pas
        self.passe()
        self.assertEqual(len(self.recus()), 1)
        self.assertIn("Essai", self.recus()[0])
        self.assertTrue(self.s("notifications.politique")["canaux"]["essais"]["telegram"]["ok"])
        z = self.s("notifications.essai", compte=ZOE, canal="telegram")
        self.assertFalse(z["ok"])
        self.assertIn("aucun robot", z["detail"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Livrer, Retenir, Echouer, Portes
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
