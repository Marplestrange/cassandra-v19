"""Bancs du module dns : le client DNS (vrai UDP et TCP local), puis le module dans un vrai noyau avec un DNS, un panneau et un Cloudflare simulés."""
import json
import shutil
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import importlib.util                      # noqa: E402
import main as moteur                      # noqa: E402
from noyau.bus import TOUT                 # noqa: E402


def charger():
    spec = importlib.util.spec_from_file_location("dns_mod", RACINE / "modules" / "dns" / "module.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def nom_dns(nom):
    return b"".join(bytes([len(p)]) + p.encode() for p in nom.strip(".").split(".")) + b"\x00"


def reponse(requete, rr, rcode=0, tronque=False):
    """Une réponse DNS minimale : la question recopiée, puis des enregistrements (type, rdata) dont le nom est un POINTEUR vers la question (compression)."""
    ident = struct.unpack(">H", requete[:2])[0]
    flags = 0x8180 | rcode | (0x0200 if tronque else 0)
    q = requete[12:]
    corps = b"".join(b"\xc0\x0c" + struct.pack(">HHIH", t, 1, 60, len(d)) + d for t, d in rr)
    return struct.pack(">HHHHHH", ident, flags, 1, len(rr), 0, 0) + q + corps


class ServeurDns:
    """Un serveur DNS UDP+TCP sur un port local : table {(nom, type): [rdata]}."""

    def __init__(self, table, tronque_udp=False):
        self.table, self.tronque_udp, self.rcode = table, tronque_udp, 0
        # le même numéro de port en UDP et en TCP : on essaie jusqu'à en trouver un libre des deux côtés (sous Linux, le port UDP choisi peut être pris en TCP)
        for _ in range(50):
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.bind(("127.0.0.1", 0))
            self.port = self.udp.getsockname()[1]
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.tcp.bind(("127.0.0.1", self.port))
                break
            except OSError:
                self.udp.close()
                self.tcp.close()
        else:
            raise OSError("aucun port libre en UDP et en TCP")
        self.tcp.listen(5)
        self.actif = True
        threading.Thread(target=self.boucle_udp, daemon=True).start()
        threading.Thread(target=self.boucle_tcp, daemon=True).start()

    def lire_question(self, req):
        i, parts = 12, []
        while req[i]:
            parts.append(req[i + 1:i + 1 + req[i]].decode())
            i += 1 + req[i]
        t = struct.unpack(">H", req[i + 1:i + 3])[0]
        return ".".join(parts), t

    def repondre(self, req, tronque=False):
        nom, t = self.lire_question(req)
        return reponse(req, self.table.get((nom, t), []) if not tronque else [], rcode=self.rcode, tronque=tronque)

    def boucle_udp(self):
        self.udp.settimeout(0.2)
        while self.actif:
            try:
                req, adr = self.udp.recvfrom(512)
            except OSError:
                continue
            self.udp.sendto(self.repondre(req, tronque=self.tronque_udp), adr)

    def boucle_tcp(self):
        self.tcp.settimeout(0.2)
        while self.actif:
            try:
                c, _ = self.tcp.accept()
            except OSError:
                continue
            n = struct.unpack(">H", c.recv(2))[0]
            req = c.recv(n)
            r = self.repondre(req)
            c.sendall(struct.pack(">H", len(r)) + r)
            c.close()

    def arreter(self):
        self.actif = False
        time.sleep(0.3)
        self.udp.close()
        self.tcp.close()


A = lambda ip: (1, socket.inet_aton(ip))
TXT = lambda *morceaux: (16, b"".join(bytes([len(m)]) + m.encode() for m in morceaux))
MX = lambda pref, h: (15, struct.pack(">H", pref) + nom_dns(h))
NS = lambda h: (2, nom_dns(h))
CAA = lambda flag, tag, val: (257, bytes([flag, len(tag)]) + tag.encode() + val.encode())


class ClientDns(unittest.TestCase):
    def setUp(self):
        self.m = charger()
        self.srv = None

    def serveur(self, table, **kw):
        self.srv = ServeurDns(table, **kw)
        self.addCleanup(self.srv.arreter)
        self.m.PORT_DNS = self.srv.port

    def test_a_ns_mx_txt_caa_decodes_et_tries(self):
        self.serveur({("e.fr", 1): [A("192.0.2.9"), A("192.0.2.1")], ("e.fr", 15): [MX(10, "mx.e.fr")], ("e.fr", 16): [TXT("v=spf1 ", "include:x.fr ~all")],
                      ("e.fr", 2): [NS("NS1.E.fr")], ("e.fr", 257): [CAA(0, "issue", "letsencrypt.org")]})
        q = lambda t: self.m.interroger("e.fr", t, "127.0.0.1")
        self.assertEqual(q("A"), ["192.0.2.1", "192.0.2.9"])
        self.assertEqual(q("MX"), ["10 mx.e.fr"])
        self.assertEqual(q("TXT"), ["v=spf1 include:x.fr ~all"])        # les morceaux d'un TXT sont recollés
        self.assertEqual(q("NS"), ["ns1.e.fr"])
        self.assertEqual(q("CAA"), ['0 issue "letsencrypt.org"'])

    def test_absent_n_est_pas_inconnu(self):
        self.serveur({})
        self.assertEqual(self.m.interroger("vide.e.fr", "A", "127.0.0.1"), [])           # le serveur dit : rien
        self.srv.rcode = 2
        self.assertIsNone(self.m.interroger("vide.e.fr", "A", "127.0.0.1"))                # SERVFAIL : on ne sait pas
        self.srv.rcode = 3
        self.assertEqual(self.m.interroger("vide.e.fr", "A", "127.0.0.1"), [])             # NXDOMAIN : absent

    def test_un_serveur_muet_ou_un_nom_invalide_rendent_inconnu(self):
        self.m.PORT_DNS = 9
        self.assertIsNone(self.m.interroger("e.fr", "A", "127.0.0.1", delai=0.5))
        self.assertIsNone(self.m.interroger("pas un nom", "A", "127.0.0.1"))
        self.assertIsNone(self.m.interroger("e.fr", "SRV", "127.0.0.1"))
        self.assertIsNone(self.m.interroger("e.fr", "A", ""))

    def test_une_reponse_tronquee_repart_en_tcp(self):
        self.serveur({("e.fr", 1): [A("192.0.2.1")]}, tronque_udp=True)
        self.assertEqual(self.m.interroger("e.fr", "A", "127.0.0.1"), ["192.0.2.1"])

    def test_une_reponse_d_un_autre_identifiant_est_refusee(self):
        ident, req = self.m.construire("e.fr", "A")
        r = reponse(req, [A("192.0.2.1")])
        with self.assertRaises(ValueError):
            self.m.analyser(r, (ident + 1) % 65536)

    def test_une_boucle_de_compression_est_refusee(self):
        b = bytes(12) + b"\xc0\x0c"
        with self.assertRaises(ValueError):
            self.m.lire_nom(b, 12)

    def test_normalisations(self):
        self.assertEqual(self.m.normaliser("A", "104.21.5.5"), "<cloudflare>")
        self.assertEqual(self.m.normaliser("A", "192.0.2.1"), "192.0.2.1")
        self.assertEqual(self.m.normaliser("MX", "10 MX.E.fr"), "10 mx.e.fr")
        self.assertEqual([self.m.dom_enregistre(x) for x in ("app.exemple.org", "x.co.uk", "a.b.exemple.fr", "fr", "")], ["exemple.org", "x.co.uk", "exemple.fr", "", ""])


class FauxCloudflare:
    def __init__(self, dns):
        self.dns, self.proxied, self.appels = dns, False, []
        faux = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def rep(self, corps, code=200):
                d = json.dumps(corps).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d)))
                self.end_headers()
                self.wfile.write(d)

            def do_GET(self):
                faux.appels.append(("GET", self.path, self.headers.get("Authorization")))
                if self.headers.get("Authorization") != "Bearer jeton-cf":
                    return self.rep({"success": False, "errors": [{"message": "Invalid token"}]}, 403)
                if self.path.startswith("/zones?name="):
                    return self.rep({"success": True, "result": [{"id": "z1"}] if self.path.endswith("exemple.fr") else []})
                if "dns_records" in self.path:
                    nom = self.path.split("name=")[1]
                    ip = faux.dns.get((nom, 1))
                    return self.rep({"success": True, "result": [{"id": "r-" + nom, "content": socket.inet_ntoa(ip[0][1]), "ttl": 120, "proxied": faux.proxied}] if ip else []})
                self.rep({"success": False, "errors": []}, 404)

            def do_PUT(self):
                n = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(n).decode())
                faux.appels.append(("PUT", self.path, corps))
                faux.dns[(corps["name"], 1)] = [A(corps["content"])]
                self.rep({"success": True, "result": {"id": "x"}})

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.serveur.daemon_threads = True
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.serveur.server_address[1]

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()


class Module(unittest.TestCase):
    ANCIENNE, NOUVELLE = "192.0.2.10", "198.51.100.7"

    def setUp(self):
        self.m = charger()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "dns", mods / "dns")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("dns")["ok"])
        self.ctx = self.n.executeur.contextes["dns"]
        g = self.n.catalogue.get("dns.etat").faire.__globals__
        self.g = g
        self.table = {("exemple.fr", 2): [NS("ns1.exemple.fr")], ("ns1.exemple.fr", 1): [A("203.0.113.53")],
                      ("exemple.fr", 1): [A(self.ANCIENNE)], ("www.exemple.fr", 1): [A(self.ANCIENNE)], ("app.exemple.fr", 1): [A(self.ANCIENNE)],
                      ("exemple.fr", 15): [MX(10, "mx.exemple.fr")], ("exemple.fr", 16): [TXT("v=spf1 -all")], ("mail.exemple.fr", 1): [A(self.ANCIENNE)]}
        self.inconnus = set()
        self.ip = self.ANCIENNE
        self.exp = None

        def interroger(nom, typ, serveur, delai=4.0):
            if (nom, typ) in self.inconnus:
                return None
            return self.valeurs(nom, typ)
        g["interroger"] = interroger
        g["ip_publique"] = lambda: self.ip
        g["expiration_rdap"] = lambda dom: self.exp
        g["resolveurs_systeme"] = lambda: ["203.0.113.1"]
        g["ATTENTE_PREUVE_S"], g["PAS_PREUVE_S"] = 1, 0.1
        self.panneau = [{"domaine": "app.exemple.fr"}, {"domaine": "www.exemple.fr"}]
        self.ctx.executer_lecture = lambda cap, **a: self.panneau
        self.cf = FauxCloudflare(self.table)
        self.addCleanup(self.cf.arreter)
        self.n.reglages.poser("dns.api_cloudflare", self.cf.url)
        self.n.reglages.poser("dns.jeton_cloudflare", "jeton-cf")
        self.n.reglages.poser("dns.ne_pas_toucher", "reserve.exemple.fr")
        self.e = self.n.executeur.executer

    def valeurs(self, nom, typ):
        m = self.m
        out = []
        for t, d in self.table.get((nom, m.TYPES[typ]), []):
            if typ == "A":
                out.append(socket.inet_ntoa(d))
            elif typ == "NS":
                out.append(m.lire_nom(d, 0)[0].lower())
            elif typ == "MX":
                out.append("%d %s" % (struct.unpack(">H", d[:2])[0], m.lire_nom(d, 2)[0].lower()))
            elif typ == "TXT":
                out.append(d[1:].decode())
        return sorted(out)

    def releve(self):
        self.n.lancer("dns.releve")

    def ex(self, cap, acteur="humain", **args):
        return self.e("dns." + cap, acteur, args, compte="")

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def constats(self):
        self.n.tick()
        return [e["donnees"]["titre"] for e in self.evts("constat.ouvert")]

    def test_la_premiere_releve_devient_la_reference_sans_alerte(self):
        self.releve()
        ref = self.ex("reference", domaine="exemple.fr")["resultat"]
        self.assertEqual(ref["version"], 1)
        self.assertEqual(ref["contenu"]["exemple.fr|A"], [self.ANCIENNE])
        self.assertEqual(self.constats(), [])

    def test_les_zones_suivies_viennent_du_panneau_et_du_reglage(self):
        self.n.reglages.poser("dns.domaines", "autre.org, exemple.fr")
        self.assertEqual([z["domaine"] for z in self.ex("etat")["resultat"]["zones"]], ["autre.org", "exemple.fr"])

    def test_une_zone_non_suivie_est_refusee(self):
        self.assertEqual(self.ex("relever_zone", domaine="inconnu.org")["statut"], "echec")

    def test_une_derive_est_signalee_une_fois_et_acceptee_comme_nouvelle_version(self):
        self.releve()
        self.table[("exemple.fr", 16)] = [TXT("v=spf1 +all")]
        self.releve()
        self.releve()
        self.assertEqual(len(self.evts("dns.derive")), 1)
        titres = self.constats()
        self.assertEqual(len(titres), 1)
        self.assertIn("exemple.fr (TXT) a changé", titres[0])
        r = self.e("dns.accepter_reference", "humain", {"domaine": "exemple.fr"}, compte="")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("reference", domaine="exemple.fr")["resultat"]["version"], 2)
        self.assertEqual(len(self.ex("reference", domaine="exemple.fr", historique=True)["resultat"]["versions"]), 2)
        self.n.tick(time.time() + 4000)
        self.assertEqual(len([e for e in self.evts("constat.resolu")]), 1)

    def test_le_retour_d_une_acceptation_remet_la_version_precedente(self):
        self.releve()
        self.table[("exemple.fr", 16)] = [TXT("v=spf1 +all")]
        r = self.ex("accepter_reference", domaine="exemple.fr")
        self.n.catalogue.get("dns.accepter_reference").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ex("reference", domaine="exemple.fr")["resultat"]["version"], 1)

    def test_un_nom_illisible_n_est_ni_une_derive_ni_une_conformite(self):
        self.releve()
        self.inconnus.add(("exemple.fr", "TXT"))
        self.releve()
        self.assertEqual(self.constats(), [])
        self.assertEqual(self.evts("dns.derive"), [])
        self.assertEqual(self.n.registre.lire("domaine", "exemple.fr", portee=TOUT)["donnees"]["inconnus"], 1)

    def test_un_enregistrement_disparu_est_une_derive(self):
        self.releve()
        del self.table[("www.exemple.fr", 1)]
        self.releve()
        self.assertTrue(any("www.exemple.fr (A)" in t for t in self.constats()))

    def test_le_changement_d_adresse_publique_propose_la_correction_et_le_palier_la_borne(self):
        self.releve()
        self.ip = self.NOUVELLE
        self.releve()
        self.n.tick()
        ouverts = [e["donnees"]["titre"] for e in self.evts("constat.ouvert")]
        self.assertTrue(any("app.exemple.fr pointe encore sur l'ancienne adresse" in t for t in ouverts), ouverts)
        self.assertEqual(self.table[("app.exemple.fr", 1)], [A(self.ANCIENNE)])           # palier « raconter » : rien n'est écrit
        self.assertTrue(any(e["donnees"].get("palier") == "raconter" for e in self.evts("capacite.racontee")))

    def test_cassandra_au_palier_auto_corrige_prouve_sur_le_serveur_de_noms(self):
        self.releve()
        self.ip = self.NOUVELLE
        self.releve()
        self.n.catalogue.regler_palier("dns.corriger_enregistrement", "auto")
        self.n.tick()
        self.assertEqual(self.table[("app.exemple.fr", 1)], [A(self.NOUVELLE)])
        self.assertEqual(self.table[("www.exemple.fr", 1)], [A(self.NOUVELLE)])
        self.assertEqual(self.ex("etat")["resultat"]["ip_reference"], self.NOUVELLE)
        self.assertGreaterEqual(len(self.evts("capacite.prouvee")), 2)
        self.assertEqual(self.table[("exemple.fr", 1)], [A(self.NOUVELLE)])
        self.assertEqual(self.table[("mail.exemple.fr", 1)], [A(self.ANCIENNE)])             # le courrier n'est jamais touché
        self.assertEqual(len(self.evts("dns.corrige")), 3)

    def test_la_correction_refuse_ce_qui_n_est_pas_a_ce_serveur(self):
        self.releve()
        self.ip = self.NOUVELLE
        refus = {"exemple.fr_AAAA": dict(nom="app.exemple.fr", type="AAAA", valeur=self.NOUVELLE), "zone": dict(nom="a.autre.org", type="A", valeur=self.NOUVELLE),
                 "reserve": dict(nom="reserve.exemple.fr", type="A", valeur=self.NOUVELLE), "courrier": dict(nom="mail.exemple.fr", type="A", valeur=self.NOUVELLE),
                 "dmarc": dict(nom="_dmarc.exemple.fr", type="A", valeur=self.NOUVELLE), "autre_ip": dict(nom="app.exemple.fr", type="A", valeur="203.0.113.99"),
                 "illisible": dict(nom="app.exemple.fr", type="A", valeur="pas-une-ip"), "ipv6": dict(nom="app.exemple.fr", type="A", valeur="2001:db8::1")}
        for nom, args in refus.items():
            self.assertEqual(self.ex("corriger_enregistrement", **args)["statut"], "echec", nom)
        self.assertEqual([a for a in self.cf.appels if a[0] == "PUT"], [])

    def test_un_enregistrement_proxifie_ou_absent_ne_se_corrige_pas(self):
        self.releve()
        self.ip = self.NOUVELLE
        self.cf.proxied = True
        self.assertEqual(self.ex("corriger_enregistrement", nom="app.exemple.fr", type="A", valeur=self.NOUVELLE)["statut"], "echec")
        self.cf.proxied = False
        self.assertEqual(self.ex("corriger_enregistrement", nom="nouveau.exemple.fr", type="A", valeur=self.NOUVELLE)["statut"], "echec")
        self.assertEqual([a for a in self.cf.appels if a[0] == "PUT"], [])

    def test_une_ecriture_que_le_serveur_de_noms_ne_rend_pas_est_defaite(self):
        self.releve()
        self.ip = self.NOUVELLE
        # le serveur de noms ne reflète pas l'écriture (propagation qui n'arrive pas) : l'API ne met plus à jour la table
        sauvegarde = dict(self.cf.dns)
        class Gele(dict):
            def __setitem__(s, k, v):
                if k[1] != 1 or k[0] != "app.exemple.fr":
                    super().__setitem__(k, v)
        gele = Gele(self.table)
        self.table = gele
        self.cf.dns = gele
        r = self.ex("corriger_enregistrement", nom="app.exemple.fr", type="A", valeur=self.NOUVELLE)
        self.assertEqual(r["statut"], "annulee", r)
        puts = [a for a in self.cf.appels if a[0] == "PUT"]
        self.assertEqual([p[2]["content"] for p in puts], [self.NOUVELLE, self.ANCIENNE])        # écrit, puis remis

    def test_sans_jeton_cloudflare_le_constat_dit_quoi_faire_sans_proposer_d_acte(self):
        self.n.reglages.poser("dns.jeton_cloudflare", "")
        self.releve()
        self.ip = self.NOUVELLE
        self.releve()
        self.n.catalogue.regler_palier("dns.corriger_enregistrement", "auto")
        self.n.tick()
        self.assertTrue(any("jeton Cloudflare" in e["donnees"].get("detail", "") for e in self.evts("constat.ouvert")))
        self.assertEqual([a for a in self.cf.appels if a[0] == "PUT"], [])

    def test_le_jeton_n_apparait_pas_au_journal(self):
        self.releve()
        self.ip = self.NOUVELLE
        self.ex("corriger_enregistrement", nom="app.exemple.fr", type="A", valeur=self.NOUVELLE)
        self.assertNotIn("jeton-cf", json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str))

    def test_le_retour_d_une_correction_remet_l_ancienne_adresse_et_la_reference(self):
        self.releve()
        self.ip = self.NOUVELLE
        r = self.ex("corriger_enregistrement", nom="app.exemple.fr", type="A", valeur=self.NOUVELLE)
        self.assertEqual(r["statut"], "faite", r)
        self.n.catalogue.get("dns.corriger_enregistrement").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.table[("app.exemple.fr", 1)], [A(self.ANCIENNE)])
        self.assertEqual(self.ex("etat")["resultat"]["ip_reference"], self.ANCIENNE)

    def test_l_adresse_publique_inconnue_ne_declenche_rien(self):
        self.ip = ""
        self.releve()
        self.assertEqual(self.ex("etat")["resultat"]["ip_publique"], None)
        self.assertEqual(self.constats(), [])

    def test_expiration_d_un_domaine(self):
        from datetime import datetime, timedelta
        self.exp = datetime.utcnow() + timedelta(days=10)
        self.releve()
        self.assertEqual(len(self.evts("domaine.proche_expiration")), 1)
        t = self.constats()
        self.assertTrue(any("exemple.fr expire dans" in x for x in t), t)
        self.assertEqual(self.ex("etat")["resultat"]["zones"][0]["expiration"], self.exp.strftime("%Y-%m-%d"))

    def test_un_domaine_loin_de_son_terme_ne_dit_rien(self):
        from datetime import datetime, timedelta
        self.exp = datetime.utcnow() + timedelta(days=400)
        self.releve()
        self.assertEqual(self.evts("domaine.proche_expiration"), [])


if __name__ == "__main__":
    unittest.main()
