# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'analyse de sécurité
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #ee8aa3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'analyse de sécurité : des relevés bruts (ss, iptables -S, sshd -T, fail2ban) -> exposition, pare-feu, accès, verdict. Chaque banc rejoue une situation réelle de la V18 : une règle finale REJECT, un port ouvert par adresse, une ma
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ee8aa3 ▼▼▼
"""Bancs de l'analyse de sécurité : des relevés bruts (ss, iptables -S, sshd -T, fail2ban) -> exposition, pare-feu, accès, verdict.
Chaque banc rejoue une situation réelle de la V18 : une règle finale REJECT, un port ouvert par adresse, une machine derrière une box."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from modules.securite import CN_analyse as an   # noqa: E402

PARE_FEU_FERME = """-P INPUT DROP
-P FORWARD DROP
-P OUTPUT ACCEPT
-A INPUT -i lo -j ACCEPT
-A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
-A INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT
-A INPUT -s 192.168.1.0/24 -p tcp -m tcp --dport 3306 -j ACCEPT
-A INPUT -s 100.64.1.5/32 -p tcp -m tcp --dport 9090 -j ACCEPT
"""
PARE_FEU_OUVERT = """-P INPUT ACCEPT
-P FORWARD ACCEPT
-P OUTPUT ACCEPT
"""
PARE_FEU_REJECT_FINAL = """-P INPUT ACCEPT
-A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
-A INPUT -j REJECT --reject-with icmp-port-unreachable
"""


def ecoute(proto, adr, port, proc, pid=1):
    return {"proto": proto, "adresse": adr, "port": port, "processus": proc, "pid": pid, "unite": ""}


def releves(**kw):
    base = {"ecoutes": [], "ip_addr": "2: eth0    inet 198.51.100.9/32 scope global eth0\n", "iptables": PARE_FEU_FERME, "ip6tables": None, "iptables_docker": None, "nft": None,
            "sshd": {"passwordauthentication": "no", "permitrootlogin": "prohibit-password", "x11forwarding": "no", "port": "22"}, "echecs_ssh_7j": 3,
            "comptes": {"shells": ["root"], "sudo": []}, "cles_ssh": {"root": 1}, "fail2ban": {"present": True, "actif": True, "jails": {"sshd": "Total failed: 9\nCurrently banned: 2\nTotal banned: 5\nBanned IP list: 1.2.3.4 5.6.7.8"}},
            "maj": {"apt": True, "a_mettre_a_jour": 4, "securite": 0, "auto_installe": True, "auto_conf": 'APT::Periodic::Unattended-Upgrade "1";', "unites_en_echec": []},
            "outils": {"lynis": False, "trivy": False, "clamav": False, "crowdsec": False}, "cage": "active", "hote": "amizo"}
    base.update(kw)
    return base


class Portee(unittest.TestCase):
    def test_les_anneaux(self):
        self.assertEqual(an.portee("127.0.0.1"), "machine")
        self.assertEqual(an.portee("[::1]"), "machine")
        self.assertEqual(an.portee("100.64.0.10"), "tailscale")
        self.assertEqual(an.portee("192.168.1.199"), "reseau")
        self.assertEqual(an.portee("198.51.100.9"), "public")
        self.assertEqual(an.portee("0.0.0.0"), "tout")
        self.assertEqual(an.portee("*"), "tout")


class Adresses(unittest.TestCase):
    def test_publique_donc_pas_de_box(self):
        m = an.adresses_machine("2: eth0    inet 198.51.100.9/32 scope global eth0\n1: lo inet 127.0.0.1/8 scope host lo\n")
        self.assertEqual(m["public_v4"], ["198.51.100.9"])

    def test_derriere_une_box(self):
        m = an.adresses_machine("2: enp3s0    inet 192.168.1.199/24 brd 192.168.1.255 scope global enp3s0\n3: tailscale0    inet 100.64.0.10/32 scope global tailscale0\n")
        self.assertEqual(m["public_v4"], [])
        self.assertEqual(m["ips_locales"], ["192.168.1.199"])
        self.assertEqual(m["reseaux_locaux"], ["192.168.1.0/24"])        # Tailscale n'est pas un réseau local


class PareFeu(unittest.TestCase):
    def test_une_politique_drop_filtre(self):
        fw = an.parefeu({"iptables": PARE_FEU_FERME})
        self.assertTrue(fw["filtre"])
        self.assertEqual(fw["politique"], "DROP")

    def test_une_politique_accept_sans_regle_ne_filtre_pas(self):
        self.assertFalse(an.parefeu({"iptables": PARE_FEU_OUVERT})["filtre"])

    def test_une_regle_finale_reject_filtre_autant_qu_un_drop(self):
        fw = an.parefeu({"iptables": PARE_FEU_REJECT_FINAL})
        self.assertTrue(fw["filtre"])              # les options de la cible (--reject-with) ne font pas de la règle une règle conditionnelle

    def test_qui_peut_joindre_un_port(self):
        v4 = an.parefeu({"iptables": PARE_FEU_FERME})["noyau"]["v4"]
        self.assertEqual(an.pf_admis(v4, 22, "tcp"), "tous")
        self.assertEqual(an.pf_admis(v4, 443, "tcp"), "tous")
        self.assertEqual(an.pf_admis(v4, 3306, "tcp"), "reseau")             # une plage locale entière
        self.assertEqual(an.pf_admis(v4, 9090, "tcp"), "parc")               # une adresse unique
        self.assertEqual(an.pf_admis(v4, 6379, "tcp"), "")                   # personne
        self.assertEqual(an.pf_admis(v4, 22, "udp"), "")

    def test_sans_filtre_tout_est_admis(self):
        self.assertEqual(an.pf_admis(an.parefeu({"iptables": PARE_FEU_OUVERT})["noyau"]["v4"], 3306, "tcp"), "tous")

    def test_un_pare_feu_illisible_est_dit_illisible(self):
        fw = an.parefeu({"iptables": None, "nft": None})
        self.assertFalse(fw["noyau"]["lu"])

    def test_nftables_en_repli(self):
        fw = an.parefeu({"iptables": None, "nft": "table inet filter {\n chain input {\n type filter hook input priority 0; policy drop;\n }\n}"})
        self.assertTrue(fw["filtre"])
        self.assertEqual(fw["outil"], "nftables")

    def test_docker_publie_a_cote_du_pare_feu(self):
        d = an.docker_publies("-A DOCKER ! -i docker0 -p tcp -m tcp --dport 8080 -j DNAT --to-destination 172.17.0.2:80\n-A DOCKER -d 127.0.0.1/32 ! -i docker0 -p tcp -m tcp --dport 5432 -j DNAT --to-destination 172.17.0.3:5432")
        self.assertEqual([(x["port"], x["portee"]) for x in d], [(8080, "tout"), (5432, "machine")])


FW_PANNEAU = """-P INPUT DROP
-N fastpanel_rules
-A INPUT -i lo -j ACCEPT
-A INPUT -j fastpanel_rules
-A fastpanel_rules -p tcp -m tcp --dport 443 -j ACCEPT
"""


LYNIS = {"installe": True, "convient": True, "resultat": {"score": 62, "avertissements": [{"id": "X"}], "suggestions_n": 31}}
TRIVY = {"installe": True, "convient": True, "resultat": {"images": [{"image": "a", "critiques": 2, "corrigeables": 1}, {"image": "b", "critiques": 0, "corrigeables": 0}]}}


class Outils(unittest.TestCase):
    def sortie(self, **etat):
        return an.outils(releves(outils_etat=etat))

    def test_un_outil_absent_est_dit_non_installe(self):
        o = an.outils(releves())["lynis"]
        self.assertEqual((o["niveau"], o["dit"]), ("", "non installé"))

    def test_une_machine_qui_ne_s_y_prete_pas_dit_pourquoi(self):
        o = self.sortie(clamav={"installe": False, "convient": False, "pourquoi": "1024 Mo de mémoire : le démon l'écraserait"})["clamav"]
        self.assertIn("1024 Mo", o["dit"])

    def test_installe_sans_resultat_est_premier_passage_a_venir_pas_ok(self):
        o = self.sortie(lynis={"installe": True, "convient": True, "resultat": None})["lynis"]
        self.assertEqual(o["niveau"], "pas_encore")

    def test_lynis_avertissements_a_regarder(self):
        o = self.sortie(lynis=LYNIS)["lynis"]
        self.assertEqual(o["niveau"], "regarder")
        self.assertIn("score 62/100", o["dit"])
        self.assertIn("31 conseils", o["dit"])

    def test_trivy_compte_les_critiques_de_toutes_les_images(self):
        o = self.sortie(trivy=TRIVY)["trivy"]
        self.assertEqual(o["niveau"], "regarder")
        self.assertIn("2 images · 2 failles critiques · 1 déjà corrigée", o["dit"])

    def test_un_fichier_infecte_est_une_panne_et_le_dit_en_majuscules(self):
        o = self.sortie(clamav={"installe": True, "convient": True, "resultat": {"infectes": [{"fichier": "/tmp/x", "menace": "Eicar"}]}})["clamav"]
        self.assertEqual((o["niveau"], o["dit"]), ("panne", "1 FICHIER INFECTÉ"))

    def test_clamav_propre(self):
        o = self.sortie(clamav={"installe": True, "convient": True, "resultat": {"infectes": [], "analyses": 1200, "signatures": "2026-10-16 09:00"}})["clamav"]
        self.assertEqual(o["niveau"], "ok")
        self.assertIn("1200 fichiers analysés · aucune menace", o["dit"])

    def test_crowdsec_arrete_est_une_panne(self):
        o = self.sortie(crowdsec={"installe": True, "convient": True, "resultat": {"moteur": True, "videur": False}})["crowdsec"]
        self.assertEqual(o["niveau"], "panne")
        self.assertIn("videur ARRÊTÉ", o["dit"])

    def test_crowdsec_en_marche(self):
        o = self.sortie(crowdsec={"installe": True, "convient": True, "resultat": {"moteur": True, "videur": True, "decisions_locales": 3, "liste_communautaire": 9000, "alertes_24h": 1}})["crowdsec"]
        self.assertEqual(o["niveau"], "ok")
        self.assertIn("3 adresses bannies ici", o["dit"])

    def test_un_outil_en_panne_fait_le_verdict_de_la_machine(self):
        d = an.etat(releves(ecoutes=[ecoute("tcp", "0.0.0.0", 22, "sshd")], outils_etat={"clamav": {"installe": True, "convient": True, "resultat": {"infectes": [{"fichier": "f", "menace": "m"}]}}}), "t")
        self.assertEqual(d["verdict"]["niveau"], "panne")
        self.assertEqual(d["verdict"]["titre"], "Un outil de sécurité a trouvé un problème.")
        self.assertIn("ClamAV : 1 FICHIER INFECTÉ", d["verdict"]["sous"])

    def test_sans_programme_des_outils_seule_la_presence_se_lit(self):
        o = an.outils(releves(outils={"lynis": True, "trivy": False, "clamav": False, "crowdsec": False}))
        self.assertTrue(o["lynis"]["installe"])
        self.assertEqual(o["lynis"]["niveau"], "pas_encore")


class AccordPanneau(unittest.TestCase):
    def test_sans_panneau_la_source_est_le_systeme(self):
        self.assertEqual(an.parefeu({"iptables": FW_PANNEAU})["source"], "systeme")

    def test_ce_que_le_panneau_declare_est_applique(self):
        fw = an.parefeu({"iptables": FW_PANNEAU}, {"ok": True, "regles": [{"nom": "Web", "ports": "443", "proto": "TCP"}], "politique": "DROP", "essais": []})
        self.assertEqual(fw["source"], "fastpanel")
        self.assertTrue(fw["noyau"]["accord"]["accord"])

    def test_une_regle_du_panneau_que_le_noyau_n_applique_pas_est_nommee(self):
        fw = an.parefeu({"iptables": FW_PANNEAU}, {"ok": True, "regles": [{"nom": "Web", "ports": "443", "proto": "TCP"}, {"nom": "Appli", "ports": "8080", "proto": "TCP"}], "politique": "DROP"})
        a = fw["noyau"]["accord"]
        self.assertFalse(a["accord"])
        self.assertEqual(a["manquantes"], ["Appli"])

    def test_une_politique_du_panneau_que_le_noyau_ne_porte_pas(self):
        a = an.parefeu({"iptables": PARE_FEU_OUVERT}, {"ok": True, "regles": [], "politique": "DROP"})["noyau"]["accord"]
        self.assertFalse(a["politique_ok"])

    def test_un_panneau_injoignable_est_dit_et_le_noyau_reste_la_verite(self):
        fw = an.parefeu({"iptables": PARE_FEU_FERME}, {"ok": False, "erreur": "panneau injoignable"})
        self.assertEqual(fw["source"], "systeme")
        self.assertFalse(fw["api_ok"])
        self.assertTrue(fw["filtre"])

    def test_les_essais_en_cours_remontent_a_l_ecran(self):
        d = an.etat(releves(), "t", panneau={"ok": True, "regles": [], "politique": "ACCEPT", "essais": [{"jeton": "ab12", "quoi": "règle posée : X", "fin": 1, "reste": 90}]})
        self.assertEqual(d["parefeu_essais"], [{"jeton": "ab12", "quoi": "règle posée : X", "reste": 90}])
        self.assertEqual([f for f in d["verdict"]["familles"] if f["page"] == "parefeu"][0]["dit"].split(" · ")[0], "FastPanel")


class Exposition(unittest.TestCase):
    def expo(self, ecoutes, iptables=PARE_FEU_FERME, ip_addr=None):
        m = releves(ecoutes=ecoutes, iptables=iptables)
        if ip_addr:
            m["ip_addr"] = ip_addr
        machine = an.adresses_machine(m["ip_addr"])
        return an.exposition(ecoutes, machine, an.parefeu(m))

    def test_un_service_local_n_est_pas_expose(self):
        e = self.expo([ecoute("tcp", "127.0.0.1", 3306, "mysqld")])[0]
        self.assertFalse(e["reseau"])
        self.assertEqual(e["internet"], "non")

    def test_mysql_ouvert_au_reseau_est_sensible_et_propose_son_geste(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 3306, "mysqld")])[0]
        self.assertTrue(e["reseau"] and e["sensible"])
        self.assertEqual(e["geste"], "mysql_local")

    def test_le_pare_feu_ferme_ce_que_l_ecoute_ouvre(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 6379, "redis-server")])[0]
        self.assertFalse(e["reseau"])                            # le port écoute partout, le pare-feu n'admet personne
        self.assertFalse(e["parc"])

    def test_un_port_reserve_au_parc(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 9090, "prometheus")])[0]
        self.assertFalse(e["reseau"])
        self.assertTrue(e["parc"])

    def test_public_sans_filtre_est_joignable_d_internet(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 80, "nginx")], iptables=PARE_FEU_OUVERT)[0]
        self.assertEqual(e["internet"], "oui")

    def test_derriere_une_box_on_ne_sait_pas(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 80, "nginx")], ip_addr="2: enp3s0    inet 192.168.1.199/24 scope global enp3s0\n")[0]
        self.assertEqual(e["internet"], "box")                   # dit « selon la box », n'affirme ni oui ni non

    def test_les_clients_dhcp_et_ntp_ne_sont_pas_des_services(self):
        self.assertEqual(self.expo([ecoute("udp", "0.0.0.0", 68, "dhclient")]), [])

    def test_cassandra_porte_son_nom(self):
        self.assertEqual(self.expo([ecoute("tcp", "127.0.0.1", 9000, "python3")])[0]["nom"], "Cassandra")

    def test_les_sensibles_ouverts_passent_en_tete(self):
        e = self.expo([ecoute("tcp", "0.0.0.0", 22, "sshd"), ecoute("tcp", "0.0.0.0", 3306, "mysqld")])
        self.assertEqual(e[0]["nom"], "MySQL")


class Verdict(unittest.TestCase):
    def test_rien_d_ouvert_est_stable(self):
        d = an.etat(releves(ecoutes=[ecoute("tcp", "0.0.0.0", 80, "nginx"), ecoute("tcp", "0.0.0.0", 22, "sshd")]), "t")
        self.assertEqual(d["verdict"]["niveau"], "stable")

    def test_un_service_sensible_public_est_une_panne(self):
        d = an.etat(releves(ecoutes=[ecoute("tcp", "0.0.0.0", 3306, "mysqld")], iptables=PARE_FEU_OUVERT), "t")
        self.assertEqual(d["verdict"]["niveau"], "panne")
        self.assertIn("MySQL", d["verdict"]["titre"])

    def test_un_serveur_web_public_n_est_pas_un_probleme(self):
        d = an.etat(releves(ecoutes=[ecoute("tcp", "0.0.0.0", 80, "nginx")], iptables=PARE_FEU_OUVERT), "t")
        self.assertNotEqual(d["verdict"]["chiffres"][0]["niveau"], "panne")

    def test_les_mots_de_passe_ssh_se_disent(self):
        m = releves(ecoutes=[ecoute("tcp", "0.0.0.0", 22, "sshd")])
        m["sshd"]["passwordauthentication"] = "yes"
        d = an.etat(m, "t")
        self.assertIn("mots de passe", d["verdict"]["sous"])
        self.assertEqual([f for f in d["verdict"]["familles"] if f["page"] == "acces"][0]["niveau"], "regarder")

    def test_un_relevé_qui_manque_n_est_jamais_stable(self):
        d = an.etat(releves(ecoutes=None), "t")
        self.assertEqual(d["verdict"]["niveau"], "inconnu")
        self.assertIn("services à l'écoute", d["verdict"]["sous"])

    def test_un_pare_feu_illisible_n_est_pas_dit_ouvert(self):
        d = an.etat(releves(ecoutes=[], iptables=None, nft=None), "t")
        fam = [f for f in d["verdict"]["familles"] if f["page"] == "parefeu"][0]
        self.assertEqual(fam["niveau"], "regarder")
        self.assertIn("impossible", fam["dit"])

    def test_un_confinement_en_cours_se_voit_dans_les_defenses(self):
        d = an.etat(releves(), "t", confinement={"ok": True, "actif": True, "niveau": 2})
        f = [x for x in d["verdict"]["familles"] if x["page"] == "defenses"][0]
        self.assertEqual(f["niveau"], "regarder")
        self.assertIn("Cassandra confinée", f["dit"])
        self.assertIn("Cassandra libre", [x for x in an.etat(releves(), "t")["verdict"]["familles"] if x["page"] == "defenses"][0]["dit"])

    def test_fail2ban_se_lit(self):
        f = an.fail2ban(releves())
        self.assertTrue(f["actif"])
        self.assertEqual(f["jails"][0]["bannies"], 2)
        self.assertEqual(f["jails"][0]["ips"], ["1.2.3.4", "5.6.7.8"])

    def test_les_correctifs_automatiques(self):
        self.assertTrue(an.maj(releves())["auto_actif"])
        m = releves()
        m["maj"]["auto_conf"] = 'APT::Periodic::Unattended-Upgrade "0";'
        self.assertFalse(an.maj(m)["auto_actif"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : ecoute, releves, Portee, Adresses, PareFeu, Outils, AccordPanneau, Exposition …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
