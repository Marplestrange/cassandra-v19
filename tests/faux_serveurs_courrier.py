"""Un serveur IMAP et un serveur SMTP de poche, assez vrais pour que imaplib et smtplib leur parlent : de vrais sockets, de vraies commandes."""
import re
import socketserver
import threading
import time
from email import message_from_bytes


def message(de="alice@exemple.fr", objet="Bonjour", corps="Le texte", msgid=None, date=None, pj=False, html=None, a="bea@x.fr", extra=""):
    from email.utils import formatdate
    date = date or formatdate()
    msgid = msgid or "<%d.%d@exemple.fr>" % (int(time.time() * 1000) % 10 ** 9, abs(hash(objet + de)) % 10 ** 6)
    if pj:
        raw = ("From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nMessage-ID: %s\r\n%sMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=\"B\"\r\n\r\n--B\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n%s\r\n"
               "--B\r\nContent-Type: application/pdf; name=\"devis.pdf\"\r\nContent-Disposition: attachment; filename=\"devis.pdf\"\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n--B--\r\n") % (de, a, objet, date, msgid, extra, corps)
    elif html:
        raw = ("From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nMessage-ID: %s\r\n%sMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=\"C\"\r\n\r\n--C\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n%s\r\n"
               "--C\r\nContent-Type: text/html; charset=utf-8\r\n\r\n%s\r\n--C--\r\n") % (de, a, objet, date, msgid, extra, corps, html)
    else:
        raw = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nMessage-ID: %s\r\n%sContent-Type: text/plain; charset=utf-8\r\n\r\n%s\r\n" % (de, a, objet, date, msgid, extra, corps)
    return raw.encode("utf-8")


class Boite:
    """L'état d'une boîte : dossiers -> messages. Un message : {uid, flags, raw}."""

    def __init__(self, utilisateur="bea@x.fr", mdp="mdp-imap", move=True):
        self.utilisateur, self.mdp, self.move = utilisateur, mdp, move
        self.dossiers = {"INBOX": [], "Sent": [], "Drafts": [], "Trash": []}
        self.flags_dossier = {"Sent": "\\Sent", "Drafts": "\\Drafts", "Trash": "\\Trash"}
        self.suivant = {}
        self.verrou = threading.RLock()
        self.commandes = []
        self.coupures = 0                       # nombre de connexions à couper au prochain NOOP (session tombée)

    def ajouter(self, dossier, raw, flags=("\\Seen",)):
        with self.verrou:
            n = self.suivant.get(dossier, 1)
            self.suivant[dossier] = n + 1
            self.dossiers.setdefault(dossier, []).append({"uid": n, "flags": set(flags), "raw": raw})
            return n

    def uids(self, dossier):
        return [m["uid"] for m in self.dossiers.get(dossier, [])]


def nom_imap(n):
    return n.strip().strip('"').replace('\\"', '"').replace("\\\\", "\\")


class ManipulateurImap(socketserver.StreamRequestHandler):
    def ecrire(self, s):
        self.wfile.write(s if isinstance(s, bytes) else s.encode("utf-8"))
        self.wfile.flush()

    def handle(self):
        b = self.server.boite
        self.ecrire("* OK IMAP4rev1 pret\r\n")
        self.dossier, self.connecte = None, False
        while True:
            ligne = self.rfile.readline()
            if not ligne:
                return
            texte = ligne.decode("utf-8", "replace").rstrip("\r\n")
            m = re.match(r"^(\S+)\s+(\S+)\s*(.*)$", texte)
            if not m:
                continue
            tag, cmd, reste = m.group(1), m.group(2).upper(), m.group(3)
            with b.verrou:
                b.commandes.append((cmd + " " + reste)[:200])
            try:
                if cmd == "LOGOUT":
                    self.ecrire("* BYE\r\n%s OK fin\r\n" % tag)
                    return
                if not self.dispatch(b, tag, cmd, reste):
                    self.ecrire("%s BAD commande inconnue\r\n" % tag)
            except ConnectionError:
                return

    def dispatch(self, b, tag, cmd, reste):
        if cmd == "CAPABILITY":
            self.ecrire("* CAPABILITY IMAP4rev1 %s\r\n%s OK ok\r\n" % ("MOVE" if b.move else "", tag))
            return True
        if cmd == "LOGIN":
            args = re.findall(r'"((?:[^"\\]|\\.)*)"|(\S+)', reste)
            u, p = [a[0] or a[1] for a in args[:2]]
            if u == b.utilisateur and p == b.mdp:
                self.connecte = True
                self.ecrire("%s OK [CAPABILITY IMAP4rev1 %s] connecte\r\n" % (tag, "MOVE" if b.move else ""))
            else:
                self.ecrire("%s NO [AUTHENTICATIONFAILED] refuse\r\n" % tag)
            return True
        if not self.connecte:
            self.ecrire("%s NO non connecte\r\n" % tag)
            return True
        if cmd == "NOOP":
            with b.verrou:
                if b.coupures > 0:
                    b.coupures -= 1
                    self.connection.close()
                    raise ConnectionError()
            self.ecrire("%s OK noop\r\n" % tag)
            return True
        if cmd == "LIST":
            for nom in list(b.dossiers):
                f = b.flags_dossier.get(nom, "")
                brut = nom
                self.ecrire('* LIST (\\HasNoChildren %s) "/" "%s"\r\n' % (f, brut))
            self.ecrire("%s OK liste\r\n" % tag)
            return True
        if cmd == "STATUS":
            nom = nom_imap(reste.split("(")[0])
            if nom not in b.dossiers:
                self.ecrire("%s NO inconnu\r\n" % tag)
            else:
                ms = b.dossiers[nom]
                self.ecrire('* STATUS "%s" (MESSAGES %d UNSEEN %d)\r\n%s OK ok\r\n' % (nom, len(ms), sum(1 for x in ms if "\\Seen" not in x["flags"]), tag))
            return True
        if cmd in ("SELECT", "EXAMINE"):
            nom = nom_imap(reste)
            if nom not in b.dossiers:
                self.ecrire("%s NO [NONEXISTENT] inconnu\r\n" % tag)
            else:
                self.dossier = nom
                self.ecrire("* %d EXISTS\r\n* 0 RECENT\r\n%s OK [%s] ok\r\n" % (len(b.dossiers[nom]), tag, "READ-ONLY" if cmd == "EXAMINE" else "READ-WRITE"))
            return True
        if cmd == "CREATE":
            nom = nom_imap(reste)
            if nom in b.dossiers:
                self.ecrire("%s NO [ALREADYEXISTS] dossier existe deja\r\n" % tag)
            else:
                b.dossiers[nom] = []
                self.ecrire("%s OK cree\r\n" % tag)
            return True
        if cmd in ("SUBSCRIBE", "UNSUBSCRIBE"):
            self.ecrire("%s OK ok\r\n" % tag)
            return True
        if cmd == "DELETE":
            nom = nom_imap(reste)
            if nom in b.dossiers and not b.dossiers[nom]:
                del b.dossiers[nom]
                self.ecrire("%s OK supprime\r\n" % tag)
            else:
                self.ecrire("%s NO refuse\r\n" % tag)
            return True
        if cmd == "RENAME":
            a = re.findall(r'"((?:[^"\\]|\\.)*)"|(\S+)', reste)
            ancien, nouveau = a[0][0] or a[0][1], a[1][0] or a[1][1]
            if ancien in b.dossiers and nouveau not in b.dossiers:
                b.dossiers[nouveau] = b.dossiers.pop(ancien)
                self.ecrire("%s OK renomme\r\n" % tag)
            else:
                self.ecrire("%s NO refuse\r\n" % tag)
            return True
        if cmd == "EXPUNGE":
            with b.verrou:
                b.dossiers[self.dossier] = [x for x in b.dossiers[self.dossier] if "\\Deleted" not in x["flags"]]
            self.ecrire("%s OK expunge\r\n" % tag)
            return True
        if cmd == "APPEND":
            mm = re.match(r'^("(?:[^"\\]|\\.)*"|\S+)\s*(?:\(([^)]*)\))?\s*(?:"[^"]*")?\s*\{(\d+)\}$', reste)
            if not mm:
                self.ecrire("%s BAD append\r\n" % tag)
                return True
            nom, flags, n = nom_imap(mm.group(1)), (mm.group(2) or "").split(), int(mm.group(3))
            if nom not in b.dossiers:
                self.ecrire("%s NO [TRYCREATE] inconnu\r\n" % tag)
                return True
            self.ecrire("+ go\r\n")
            donnees = self.rfile.read(n)
            self.rfile.readline()
            b.ajouter(nom, donnees, flags)
            self.ecrire("%s OK ajoute\r\n" % tag)
            return True
        if cmd == "UID":
            return self.uid(b, tag, reste)
        return False

    def selection(self, b, jeu):
        voulus = set(int(x) for x in jeu.split(",") if x.isdigit())
        return [m for m in b.dossiers[self.dossier] if m["uid"] in voulus]

    def uid(self, b, tag, reste):
        sous, _, args = reste.partition(" ")
        sous = sous.upper()
        if self.dossier is None:
            self.ecrire("%s NO aucun dossier\r\n" % tag)
            return True
        ms = b.dossiers[self.dossier]
        if sous == "SEARCH":
            crit = args.upper()
            res = list(ms)
            if "UNSEEN" in crit:
                res = [m for m in res if "\\Seen" not in m["flags"]]
            h = re.search(r'HEADER MESSAGE-ID "?([^"]+)"?', args, re.I)
            if h:
                res = [m for m in res if h.group(1).strip().lower() in message_from_bytes(m["raw"]).get("Message-ID", "").lower()]
            q = re.search(r"OR OR FROM (.+?) SUBJECT", args, re.I)
            if q:
                mot = q.group(1).strip().strip('"').lower()
                res = [m for m in res if mot in m["raw"].decode("utf-8", "replace").lower()]
            self.ecrire("* SEARCH %s\r\n%s OK ok\r\n" % (" ".join(str(m["uid"]) for m in res), tag))
            return True
        if sous == "FETCH":
            jeu, _, items = args.partition(" ")
            for m in self.selection(b, jeu):
                raw = m["raw"]
                msg = message_from_bytes(raw)
                if "BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]" in items.upper() and "BODYSTRUCTURE" not in items.upper():
                    entete = ("Message-ID: %s\r\n\r\n" % msg.get("Message-ID", "")).encode()
                    self.ecrire(("* %d FETCH (UID %d BODY[HEADER.FIELDS (MESSAGE-ID)] {%d}\r\n" % (m["uid"], m["uid"], len(entete))).encode() + entete + b")\r\n")
                elif "BODY.PEEK[HEADER.FIELDS" in items.upper():
                    entete = b"".join(("%s: %s\r\n" % (k, v)).encode() for k, v in msg.items() if k.lower() in ("from", "to", "subject", "date", "message-id", "in-reply-to", "references")) + b"\r\n"
                    flags = " ".join(sorted(m["flags"]))
                    struct = '("APPLICATION" "PDF" ("NAME" "devis.pdf") NIL NIL "BASE64" 5)' if b"attachment" in raw.lower() else '("TEXT" "PLAIN" NIL NIL NIL "7BIT" 10 1)'
                    self.ecrire(("* %d FETCH (UID %d FLAGS (%s) RFC822.SIZE %d BODYSTRUCTURE %s BODY[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] {%d}\r\n" % (m["uid"], m["uid"], flags, len(raw), struct, len(entete))).encode()
                                + entete + b")\r\n")
                elif "BODY.PEEK[]" in items.upper() or "RFC822" in items.upper():
                    self.ecrire(("* %d FETCH (UID %d BODY[] {%d}\r\n" % (m["uid"], m["uid"], len(raw))).encode() + raw + b")\r\n")
                else:
                    self.ecrire("* %d FETCH (UID %d FLAGS (%s))\r\n" % (m["uid"], m["uid"], " ".join(sorted(m["flags"]))))
            self.ecrire("%s OK fetch\r\n" % tag)
            return True
        if sous == "STORE":
            jeu, op, fl = args.split(" ", 2)
            drap = set(fl.strip("()").split())
            for m in self.selection(b, jeu):
                if op.upper().startswith("+"):
                    m["flags"] |= drap
                else:
                    m["flags"] -= drap
            self.ecrire("%s OK store\r\n" % tag)
            return True
        if sous in ("COPY", "MOVE"):
            if sous == "MOVE" and not b.move:
                return False
            jeu, _, dest = args.partition(" ")
            dest = nom_imap(dest)
            if dest not in b.dossiers:
                self.ecrire("%s NO [TRYCREATE] inconnu\r\n" % tag)
                return True
            choisis = self.selection(b, jeu)
            for m in choisis:
                b.ajouter(dest, m["raw"], m["flags"] - {"\\Deleted"})
            if sous == "MOVE":
                with b.verrou:
                    b.dossiers[self.dossier] = [x for x in b.dossiers[self.dossier] if x not in choisis]
            self.ecrire("%s OK %s\r\n" % (tag, sous.lower()))
            return True
        return False


class ServeurImap(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, boite):
        super().__init__(("127.0.0.1", 0), ManipulateurImap)
        self.boite = boite
        self.port = self.server_address[1]
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def arreter(self):
        self.shutdown()
        self.server_close()


class ManipulateurSmtp(socketserver.StreamRequestHandler):
    def ecrire(self, s):
        self.wfile.write(s.encode())
        self.wfile.flush()

    def handle(self):
        s = self.server
        self.ecrire("220 faux-smtp pret\r\n")
        auth, expediteur, rcpt = False, "", []
        while True:
            ligne = self.rfile.readline()
            if not ligne:
                return
            t = ligne.decode("utf-8", "replace").rstrip("\r\n")
            cmd = t.split(" ", 1)[0].upper()
            if cmd == "EHLO":
                self.ecrire("250-faux-smtp\r\n250-AUTH PLAIN LOGIN\r\n250 8BITMIME\r\n")
            elif cmd == "HELO":
                self.ecrire("250 faux-smtp\r\n")
            elif cmd == "AUTH":
                parts = t.split()
                import base64
                if parts[1].upper() == "PLAIN":
                    u, p = base64.b64decode(parts[2]).decode().split("\0")[1:3]
                else:
                    self.ecrire("334 VXNlcm5hbWU6\r\n")
                    u = base64.b64decode(self.rfile.readline().strip()).decode()
                    self.ecrire("334 UGFzc3dvcmQ6\r\n")
                    p = base64.b64decode(self.rfile.readline().strip()).decode()
                if (u, p) == (s.utilisateur, s.mdp):
                    auth = True
                    self.ecrire("235 ok\r\n")
                else:
                    self.ecrire("535 refuse\r\n")
            elif cmd == "MAIL":
                if not auth:
                    self.ecrire("530 authentification requise\r\n")
                    continue
                if s.refuser_expediteur and s.refuser_expediteur not in t.lower():
                    self.ecrire("553 From address does not match your authenticated SMTP account\r\n")
                    continue
                expediteur, rcpt = re.search(r"<([^>]*)>", t).group(1), []
                self.ecrire("250 ok\r\n")
            elif cmd == "RCPT":
                rcpt.append(re.search(r"<([^>]*)>", t).group(1))
                self.ecrire("250 ok\r\n")
            elif cmd == "DATA":
                self.ecrire("354 envoyez\r\n")
                lignes = []
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b""):
                        break
                    lignes.append(l[1:] if l.startswith(b"..") else l)
                s.recus.append({"de": expediteur, "a": rcpt, "raw": b"".join(lignes)})
                self.ecrire("250 accepte\r\n")
            elif cmd == "RSET":
                self.ecrire("250 ok\r\n")
            elif cmd == "NOOP":
                self.ecrire("250 ok\r\n")
            elif cmd == "QUIT":
                self.ecrire("221 au revoir\r\n")
                return
            else:
                self.ecrire("502 non gere\r\n")


class ServeurSmtp(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, utilisateur="bea@x.fr", mdp="mdp-smtp"):
        super().__init__(("127.0.0.1", 0), ManipulateurSmtp)
        self.utilisateur, self.mdp, self.recus, self.refuser_expediteur = utilisateur, mdp, [], ""
        self.port = self.server_address[1]
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def arreter(self):
        self.shutdown()
        self.server_close()
