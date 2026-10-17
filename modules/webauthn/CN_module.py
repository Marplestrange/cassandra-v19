# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La clé de sécurité (WebAuthn), second facteur de connexion et entrée sans mot de passe
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : webauthn
# ZONE       : CN
# VERSION CN : 0.1.0  #3894b8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La clé de sécurité (WebAuthn), second facteur de connexion et entrée sans mot de passe.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3894b8 ▼▼▼
"""La clé de sécurité (WebAuthn), second facteur de connexion et entrée sans mot de passe.

Porté de la V18 (`wa_*`), avec ses leçons :
  - l'ORIGINE, le TYPE et le DÉFI de clientDataJSON comptent tous les trois : le type empêche de rejouer une inscription comme une connexion,
    le défi de rejouer tout court, l'origine fait de la clé une protection contre l'hameçonnage (ce qui la distingue d'un code à six chiffres) ;
  - le défi vit EN MÉMOIRE (cinq minutes) et se consomme à la lecture : sur disque il survivrait à un redémarrage, et un défi rejouable ne vaut rien ;
  - enregistrer une clé n'EXIGE rien : il faut pouvoir l'éprouver avant qu'elle devienne la condition d'entrée, sinon une clé qui ne fonctionne pas
    enferme dehors (c'est arrivé) ;
  - les codes de secours : huit, rendus en clair une seule fois, empreinte salée seule gardée, régénérer efface les précédents ;
  - la connexion SANS identifiant déduit le compte de la clé (jamais du userHandle envoyé par le navigateur) et exige la vérification de l'utilisateur
    (bit UV) : sans lui une clé volée dans un tiroir ouvrirait le compte, c'est lui qui fait de la passkey deux facteurs ;
  - un compteur qui recule signale une clé possiblement clonée ;
  - la clé publique ne sort jamais vers le navigateur ; deux algorithmes seulement, ES256 et RS256 (en accepter d'autres sans les avoir éprouvés serait
    dire oui à ce qu'on ne sait pas vérifier) ;
  - sans la bibliothèque « cryptography », on le DIT (le manque est côté serveur, pas côté clé).
Ajouts V19 : l'exigence refuse de retirer la dernière clé (verrou), l'origine doit être en https (sauf localhost), un second facteur défaillant refuse
l'entrée au lieu de l'ouvrir (noyau/CN_identite.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time

NB_SECOURS = 8
MAX_DEFIS = 2000
DEFIS = {}                      # défi (octets) -> (compte, expire, genre)
DISPONIBLE_ERREUR = ("La bibliothèque « cryptography » n'est pas installée sur le serveur : les clés de sécurité ne peuvent pas être vérifiées. "
                     "Installez-la (pip install cryptography), puis redémarrez Cassandra.")


def b64u(b):
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def b64u_lire(s):
    s = (s or "").strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def cbor(b, i=0):
    """Décode UNE valeur CBOR, rend (valeur, position suivante). Sous-ensemble étroit : entiers, octets, texte, tableaux, dictionnaires.
    Une étiquette ou un flottant lève : mieux vaut refuser que d'interpréter au hasard."""
    t = b[i] >> 5
    v = b[i] & 0x1F
    i += 1
    if v == 24:
        v = b[i]
        i += 1
    elif v == 25:
        v = int.from_bytes(b[i:i + 2], "big")
        i += 2
    elif v == 26:
        v = int.from_bytes(b[i:i + 4], "big")
        i += 4
    elif v == 27:
        v = int.from_bytes(b[i:i + 8], "big")
        i += 8
    elif v >= 28:
        raise ValueError("CBOR : longueur indéterminée non gérée")
    if t == 0:
        return v, i
    if t == 1:
        return -1 - v, i
    if t == 2:
        if i + v > len(b):
            raise ValueError("CBOR : octets tronqués")
        return b[i:i + v], i + v
    if t == 3:
        if i + v > len(b):
            raise ValueError("CBOR : texte tronqué")
        return b[i:i + v].decode("utf-8", "replace"), i + v
    if t == 4:
        sortie = []
        for _ in range(v):
            x, i = cbor(b, i)
            sortie.append(x)
        return sortie, i
    if t == 5:
        sortie = {}
        for _ in range(v):
            k, i = cbor(b, i)
            x, i = cbor(b, i)
            sortie[k] = x
        return sortie, i
    raise ValueError("CBOR : type %d non géré" % t)


def disponible():
    try:
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
        return True
    except Exception:
        return False


def cle_publique(cose):
    """(genre, clé) à partir d'une clé COSE, ou None."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
        alg = cose.get(3)
        if alg == -7 and cose.get(1) == 2:
            return ("es256", ec.EllipticCurvePublicNumbers(int.from_bytes(cose[-2], "big"), int.from_bytes(cose[-3], "big"), ec.SECP256R1()).public_key())
        if alg == -257 and cose.get(1) == 3:
            return ("rs256", rsa.RSAPublicNumbers(int.from_bytes(cose[-2], "big"), int.from_bytes(cose[-1], "big")).public_key())
    except Exception:
        pass
    return None


def verifier_signature(cose, donnees, signature):
    k = cle_publique(cose)
    if not k:
        return False
    genre, pub = k
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding
        if genre == "es256":
            pub.verify(signature, donnees, ec.ECDSA(hashes.SHA256()))
        else:
            pub.verify(signature, donnees, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def authdata(b):
    """rpIdHash(32) | flags(1) | compteur(4) | [données de la clé attestée]."""
    if len(b) < 37:
        raise ValueError("authenticatorData trop court")
    d = {"rp": b[:32], "flags": b[32], "compteur": int.from_bytes(b[33:37], "big")}
    if b[32] & 0x40:                      # bit AT : la clé publique suit
        if len(b) < 55:
            raise ValueError("données de clé tronquées")
        n = int.from_bytes(b[53:55], "big")
        d["cred_id"] = b[55:55 + n]
        d["cose"], _ = cbor(b, 55 + n)
    return d


def cose_en_json(cose):
    return json.dumps({str(k): (b64u(v) if isinstance(v, bytes) else v) for k, v in cose.items()})


def cose_relire(txt):
    return {int(k): (b64u_lire(v) if isinstance(v, str) else v) for k, v in json.loads(txt).items()}


def brancher(ctx):
    db = ctx.stockage
    idt = ctx.identite()

    def rp():
        r = str(ctx.reglage("rp_id", "") or "").strip().lower()
        if not r:
            raise ValueError("le domaine des clés n'est pas réglé (réglage webauthn.rp_id) : une clé est liée à un domaine")
        return r

    def exiger_disponible():
        if not disponible():
            raise ValueError(DISPONIBLE_ERREUR)

    def ttl():
        try:
            return int(ctx.reglage("ttl_defi_s", 300) or 300)
        except (TypeError, ValueError):
            return 300

    def compte_qui_agit():
        c = ctx.compte
        if not c or c in ("cassandra", "itare", "noyau", "operateur"):
            raise ValueError("une clé de sécurité est celle d'un compte : aucun compte n'agit")
        return c

    # ------------------------------------------------------------------ défis
    def defi_nouveau(compte, genre):
        maintenant = time.time()
        for k in [k for k, v in DEFIS.items() if v[1] < maintenant]:
            DEFIS.pop(k, None)
        if len(DEFIS) >= MAX_DEFIS:
            raise ValueError("trop de défis en cours : réessayez dans un instant")
        d = secrets.token_bytes(32)
        DEFIS[d] = (compte, maintenant + ttl(), genre)
        return b64u(d)

    def defi_consommer(defi_b64, genre):
        """Rend le compte associé et RETIRE le défi : un défi qui resservirait laisserait rejouer une signature déjà capturée."""
        try:
            d = b64u_lire(defi_b64)
        except Exception:
            return None
        v = DEFIS.pop(d, None)
        if not v or v[1] < time.time() or v[2] != genre:
            return None
        return v[0]

    def client_data_ok(brut, genre, defi_attendu):
        d = json.loads(brut.decode("utf-8"))
        if d.get("type") != genre:
            raise ValueError("type inattendu : %s" % d.get("type"))
        if d.get("challenge") != defi_attendu:
            raise ValueError("défi non concordant")
        origine = str(d.get("origin") or "")
        schema, _, reste = origine.partition("://")
        hote = reste.split("/")[0].split(":")[0]
        if hote != rp():
            raise ValueError("origine inattendue : %s" % origine)
        if schema != "https" and hote != "localhost":
            raise ValueError("origine non sécurisée : %s" % origine)
        return d

    # ------------------------------------------------------------------ clés et codes
    def cles_de(compte):
        return db.lire("SELECT cred_id, libelle, cree, dernier FROM cles WHERE compte=? ORDER BY id", (compte,))

    def actif(compte):
        return bool(db.lire("SELECT 1 FROM cles WHERE compte=? LIMIT 1", (compte,)))

    def exigee(compte):
        r = db.lire("SELECT exigee FROM exigences WHERE compte=?", (compte,))
        return bool(r and r[0]["exigee"]) and actif(compte)

    def secours_restants(compte):
        return db.lire("SELECT COUNT(*) n FROM secours WHERE compte=? AND utilise IS NULL", (compte,))[0]["n"]

    def secours_creer(compte):
        codes = ["-".join(secrets.token_hex(2) for _ in range(3)) for _ in range(NB_SECOURS)]
        with db.transaction() as c:
            c.execute("DELETE FROM secours WHERE compte=?", (compte,))
            for code in codes:
                c.execute("INSERT INTO secours(compte, empreinte) VALUES (?,?)", (compte, idt.hacher(code)))
        return codes

    def secours_instantane(compte):
        return [(r["empreinte"], r["utilise"]) for r in db.lire("SELECT empreinte, utilise FROM secours WHERE compte=? ORDER BY id", (compte,))]

    def secours_remettre(compte, instantane):
        with db.transaction() as c:
            c.execute("DELETE FROM secours WHERE compte=?", (compte,))
            for emp, util in instantane:
                c.execute("INSERT INTO secours(compte, empreinte, utilise) VALUES (?,?,?)", (compte, emp, util))

    def secours_consommer(compte, code):
        """Un code ne sert qu'une fois : on le marque AVANT de rendre la main, deux requêtes simultanées ne passent pas avec le même."""
        code = (code or "").strip()
        if not code:
            return False
        for r in db.lire("SELECT id, empreinte FROM secours WHERE compte=? AND utilise IS NULL", (compte,)):
            if idt.secret_ok(code, r["empreinte"]):
                with db.transaction() as c:
                    return c.execute("UPDATE secours SET utilise=? WHERE id=? AND utilise IS NULL", (time.time(), r["id"])).rowcount > 0
        return False

    # ------------------------------------------------------------------ vérification d'une signature de connexion
    def assertion(compte, cred_id, client_data, auth_data, signature, defi, uv_requis):
        ligne = db.lire("SELECT cose, compteur FROM cles WHERE compte=? AND cred_id=?", (compte, cred_id))
        if not ligne:
            return {"ok": False, "error": "Clé inconnue pour ce compte"}
        try:
            cd = b64u_lire(client_data)
            client_data_ok(cd, "webauthn.get", defi)
            ab = b64u_lire(auth_data)
            ad = authdata(ab)
        except Exception as ex:
            return {"ok": False, "error": "Réponse illisible : %s" % ex}
        if ad["rp"] != hashlib.sha256(rp().encode()).digest():
            return {"ok": False, "error": "Domaine inattendu"}
        if not (ad["flags"] & 0x01):
            return {"ok": False, "error": "Clé non présentée"}
        if uv_requis and not (ad["flags"] & 0x04):
            return {"ok": False, "error": "Sans code PIN ni empreinte, la clé seule ne suffit pas à se connecter — utilisez votre mot de passe."}
        try:
            sig = b64u_lire(signature)
        except Exception:
            return {"ok": False, "error": "Signature illisible"}
        if not verifier_signature(cose_relire(ligne[0]["cose"]), ab + hashlib.sha256(cd).digest(), sig):
            return {"ok": False, "error": "Signature invalide"}
        ancien = int(ligne[0]["compteur"] or 0)
        if ad["compteur"] and ancien and ad["compteur"] <= ancien:
            return {"ok": False, "error": "Compteur en recul — clé possiblement clonée"}
        db.ecrire("UPDATE cles SET compteur=?, dernier=? WHERE compte=? AND cred_id=?", (ad["compteur"], time.time(), compte, cred_id))
        return {"ok": True}

    # ------------------------------------------------------------------ le second facteur branché sur la connexion
    class Facteur:
        def exige(self, compte):
            return exigee(compte)

        def invite(self, compte):
            return {"defi": defi_nouveau(compte, "entrer"), "ids": [r["cred_id"] for r in db.lire("SELECT cred_id FROM cles WHERE compte=?", (compte,))],
                    "rp_id": rp(), "secours": secours_restants(compte) > 0}

        def verifier(self, compte, preuve, ip=""):
            if preuve.get("secours"):
                if secours_consommer(compte, str(preuve["secours"])):
                    ctx.emettre("cle_de_securite.secours_utilise", objet=("compte", compte), donnees={"restants": secours_restants(compte)})
                    return {"ok": True}
                ctx.emettre("cle_de_securite.refusee", objet=("compte", compte), donnees={"ip": ip, "par": "secours"})
                return {"ok": False, "error": "Code de secours invalide ou déjà utilisé"}
            if defi_consommer(str(preuve.get("defi") or ""), "entrer") != compte:
                return {"ok": False, "error": "Défi expiré — recommencez"}
            r = assertion(compte, str(preuve.get("cred_id") or ""), str(preuve.get("client_data") or ""), str(preuve.get("auth_data") or ""),
                          str(preuve.get("signature") or ""), str(preuve.get("defi") or ""), uv_requis=False)
            if not r["ok"]:
                ctx.emettre("cle_de_securite.refusee", objet=("compte", compte), donnees={"ip": ip, "raison": r["error"]})
            return r

    # ------------------------------------------------------------------ lectures
    def etat(c):
        compte = compte_qui_agit()
        return {"disponible": disponible(), "erreur": "" if disponible() else DISPONIBLE_ERREUR, "rp_id": str(ctx.reglage("rp_id", "") or ""),
                "cles": [{"id": r["cred_id"][-8:], "libelle": r["libelle"] or "Clé sans nom", "cree": r["cree"], "dernier": r["dernier"]} for r in cles_de(compte)],
                "exigee": exigee(compte), "secours_restants": secours_restants(compte)}

    def defi_creer(c):
        compte = compte_qui_agit()
        exiger_disponible()
        return {"defi": defi_nouveau(compte, "creer"), "rp_id": rp(), "compte": compte, "exclure": [r["cred_id"] for r in cles_de(compte)]}

    # ------------------------------------------------------------------ gestes
    def enregistrer(c, defi="", client_data="", attestation="", libelle=""):
        compte = compte_qui_agit()
        exiger_disponible()
        if defi_consommer(str(defi), "creer") != compte:
            raise ValueError("Défi expiré — recommencez")
        try:
            cd = b64u_lire(client_data)
            client_data_ok(cd, "webauthn.create", str(defi))
            att, _ = cbor(b64u_lire(attestation))
            ad = authdata(att["authData"])
        except Exception as ex:
            raise ValueError("Clé illisible : %s" % ex)
        if ad["rp"] != hashlib.sha256(rp().encode()).digest():
            raise ValueError("La clé a été créée pour un autre domaine")
        if not (ad["flags"] & 0x01):
            raise ValueError("Clé non présentée (touchez-la)")
        if "cose" not in ad:
            raise ValueError("La clé n'a pas transmis sa clé publique")
        if not cle_publique(ad["cose"]):
            raise ValueError("Algorithme non pris en charge (ES256 ou RS256)")
        cred = b64u(ad["cred_id"])
        if db.lire("SELECT 1 FROM cles WHERE cred_id=?", (cred,)):
            raise ValueError("Cette clé est déjà enregistrée")
        nom = (libelle or "").strip()[:40] or "Clé de sécurité"
        db.ecrire("INSERT INTO cles(compte, cred_id, cose, compteur, libelle, cree) VALUES (?,?,?,?,?,?)", (compte, cred, cose_en_json(ad["cose"]), ad["compteur"], nom, time.time()))
        c.poser("cle_de_securite", cred[-8:] + ":" + compte, nom, etat="active", donnees={"compte": compte})
        c.emettre("cle_de_securite.enregistree", objet=("compte", compte), donnees={"cle": cred[-8:], "libelle": nom})
        return {"compte": compte, "cred_id": cred, "id": cred[-8:], "libelle": nom, "cles": len(cles_de(compte))}

    def prouver_enregistree(c, res):
        return bool(db.lire("SELECT 1 FROM cles WHERE cred_id=? AND compte=?", (res["cred_id"], res["compte"])))

    def defaire_enregistree(c, res):
        db.ecrire("DELETE FROM cles WHERE cred_id=? AND compte=?", (res["cred_id"], res["compte"]))
        c.retirer("cle_de_securite", res["id"] + ":" + res["compte"])

    def supprimer(c, court=""):
        compte = compte_qui_agit()
        court = str(court or "").strip()
        ligne = db.lire("SELECT * FROM cles WHERE compte=? AND substr(cred_id, -8)=?", (compte, court)) if len(court) == 8 else []
        if not ligne:
            raise ValueError("clé inconnue")
        if exigee(compte) and len(cles_de(compte)) <= 1:
            raise ValueError("c'est la dernière clé et elle est exigée pour entrer : cessez d'abord de l'exiger (sinon vous seriez enfermé dehors)")
        db.ecrire("DELETE FROM cles WHERE id=?", (ligne[0]["id"],))
        c.retirer("cle_de_securite", court + ":" + compte)
        c.emettre("cle_de_securite.retiree", objet=("compte", compte), donnees={"cle": court})
        return {"compte": compte, "court": court, "ligne": {k: ligne[0][k] for k in ("compte", "cred_id", "cose", "compteur", "libelle", "cree", "dernier")}}

    def prouver_supprimee(c, res):
        return not db.lire("SELECT 1 FROM cles WHERE cred_id=?", (res["ligne"]["cred_id"],))

    def defaire_supprimee(c, res):
        x = res["ligne"]
        db.ecrire("INSERT OR IGNORE INTO cles(compte, cred_id, cose, compteur, libelle, cree, dernier) VALUES (?,?,?,?,?,?,?)",
                  (x["compte"], x["cred_id"], x["cose"], x["compteur"], x["libelle"], x["cree"], x["dernier"]))

    def exiger(c, exiger=True):
        compte = compte_qui_agit()
        exiger = bool(exiger)
        if exiger and not actif(compte):
            raise ValueError("Enregistrez d'abord une clé, et vérifiez qu'elle fonctionne, avant de l'exiger.")
        ligne = db.lire("SELECT exigee FROM exigences WHERE compte=?", (compte,))
        avant = {"exigee": bool(ligne and ligne[0]["exigee"]), "avant_codes": secours_instantane(compte)}
        db.ecrire("INSERT INTO exigences(compte, exigee) VALUES (?,?) ON CONFLICT(compte) DO UPDATE SET exigee=excluded.exigee", (compte, 1 if exiger else 0))
        res = {"compte": compte, "exigee": exiger, "avant": avant["exigee"], "avant_codes": avant["avant_codes"]}
        if exiger and not avant["exigee"]:
            res["secours"] = secours_creer(compte)         # c'est LE moment où ils deviennent nécessaires, et le seul où on est sûr qu'on les regarde
        c.emettre("cle_de_securite.exigee", objet=("compte", compte), donnees={"exigee": exiger})
        return res

    def prouver_exigee(c, res):
        return exigee(res["compte"]) == res["exigee"]

    def defaire_exigee(c, res):
        db.ecrire("INSERT INTO exigences(compte, exigee) VALUES (?,?) ON CONFLICT(compte) DO UPDATE SET exigee=excluded.exigee", (res["compte"], 1 if res["avant"] else 0))
        secours_remettre(res["compte"], [tuple(x) for x in res["avant_codes"]])

    def secours_regenerer(c):
        compte = compte_qui_agit()
        if not actif(compte):
            raise ValueError("aucune clé : les codes de secours n'ont de sens qu'avec une clé")
        avant = secours_instantane(compte)
        return {"compte": compte, "secours": secours_creer(compte), "avant_codes": avant}

    def prouver_regeneres(c, res):
        return secours_restants(res["compte"]) == NB_SECOURS

    def defaire_regeneres(c, res):
        secours_remettre(res["compte"], [tuple(x) for x in res["avant_codes"]])

    # ------------------------------------------------------------------ entrer avec une clé d'accès (public)
    def passkey_defi(c):
        try:
            exiger_disponible()
            return {"ok": True, "defi": defi_nouveau("*", "passkey"), "rp_id": rp()}
        except ValueError as ex:
            return {"ok": False, "erreur": str(ex)}

    def passkey_ouvrir(c, defi="", cred_id="", client_data="", auth_data="", signature="", ip=""):
        """Rend le compte et le jeton de session : la passerelle en fait un cookie.
        Un refus est un RÉSULTAT ({ok: false}), jamais une exception : l'apprentissage des paliers compte les échecs d'une capacité, et des
        signatures fausses envoyées par n'importe qui feraient redescendre ce palier, c'est-à-dire couper l'entrée par clé d'accès à tous."""
        try:
            exiger_disponible()
            if defi_consommer(str(defi), "passkey") != "*":
                return {"ok": False, "erreur": "Défi expiré — recommencez"}
            ligne = db.lire("SELECT compte FROM cles WHERE cred_id=?", (str(cred_id),))
            if not ligne:
                return {"ok": False, "erreur": "Clé inconnue"}
            compte = ligne[0]["compte"]
            attente = idt.bloque(compte, ip)
            if attente:
                return {"ok": False, "erreur": "Trop d'essais : réessayez dans %d s" % attente, "limite": True}
            r = assertion(compte, str(cred_id), str(client_data), str(auth_data), str(signature), str(defi), uv_requis=True)
        except ValueError as ex:
            return {"ok": False, "erreur": str(ex)}
        if not r["ok"]:
            idt._echec(compte, ip)
            c.emettre("cle_de_securite.refusee", objet=("compte", compte), donnees={"ip": ip, "raison": r["error"], "par": "passkey"})
            return {"ok": False, "erreur": r["error"]}
        s = idt.ouvrir_sans_mdp(compte, ip, "clé d'accès")
        if not s.get("ok"):
            return {"ok": False, "erreur": s.get("error", "session impossible")}
        c.emettre("cle_de_securite.passkey", objet=("compte", compte), donnees={"ip": ip, "par": "passkey"})
        return {"ok": True, "ouvre_session": True, "compte": compte, "jeton": s["jeton"], "id": s["id"]}

    def prouver_passkey(c, res):
        return (not res.get("ok")) or idt.valider(res["jeton"]).get("ok", False)

    def defaire_passkey(c, res):
        if res.get("ok"):
            idt.fermer(res["jeton"])

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.second_facteur(Facteur())
    for cid, f in (("etat", etat), ("defi_creer", defi_creer), ("passkey_defi", passkey_defi)):
        c.implementer(cid, f)
    c.implementer("enregistrer", enregistrer, prouver_enregistree, defaire_enregistree, simuler=lambda x, libelle="", **_: "enregistrerait la clé « %s »" % (libelle or "Clé de sécurité"))
    c.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee, simuler=lambda x, court="", **_: "retirerait la clé %s" % court)
    c.implementer("exiger", exiger, prouver_exigee, defaire_exigee, simuler=lambda x, exiger=True, **_: ("exigerait" if exiger else "n'exigerait plus") + " la clé pour entrer")
    c.implementer("secours_regenerer", secours_regenerer, prouver_regeneres, defaire_regeneres, simuler=lambda x, **_: "remplacerait les codes de secours par huit nouveaux")
    c.implementer("passkey_ouvrir", passkey_ouvrir, prouver_passkey, defaire_passkey, simuler=lambda x, **_: "ouvrirait une session avec la clé d'accès")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : b64u, b64u_lire, cbor, disponible, cle_publique, verifier_signature, authdata, cose_en_json …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
