"""La sécurité : les gestes, le journal, les audits.

Porté de la V18 (`securite_*`, `_sec_gestes`), avec ses leçons :
  - un geste de sécurité laisse une trace AVANT d'agir : qui, quoi, cible, résultat, et le retour arrière possible ;
  - l'administrateur administre, il ne voit pas le contenu des autres comptes (cloisonnement) ;
  - un audit dit le modèle qui l'a produit.

Différé proprement : l'état de la machine (ports, SSH, nginx), l'exécution des gestes (Lynis/Trivy/ClamAV/CrowdSec
par le courtier racine) et le pare-feu (par l'API FastPanel) — voir les notes de conception du courtier.
"""
from __future__ import annotations

GESTES = [
    {"id": "bannir-ou-debannir-une-adresse", "nom": "Bannir ou débannir une adresse", "rev": "oui",
     "garde": "exclut maison, tailnet, confiance"},
    {"id": "fermer-ou-rouvrir-un-chemin", "nom": "Fermer ou rouvrir un chemin", "rev": "oui",
     "garde": "refus sur « / » ou si des humains y passent"},
    {"id": "poser-ou-retirer-une-regle-de-pare-feu", "nom": "Poser ou retirer une règle de pare-feu", "rev": "oui",
     "garde": "à l'essai, retour automatique"},
    {"id": "fermer-une-session-ssh", "nom": "Fermer une session SSH", "rev": "non", "garde": "identifiant valide"},
    {"id": "revoquer-une-cle-ou-une-session-inutilisee", "nom": "Révoquer une clé ou une session inutilisée", "rev": "oui",
     "garde": "inactive depuis 90 jours"},
    {"id": "faire-tourner-une-cle-ssh", "nom": "Faire tourner une clé SSH", "rev": "part", "garde": "ancienne clé valide 24 h"},
    {"id": "remplacer-un-mot-de-passe-de-service", "nom": "Remplacer un mot de passe de service", "rev": "part",
     "garde": "écrit dans le coffre avant usage"},
    {"id": "refermer-ce-qui-n-aurait-pas-du-etre-ouvert", "nom": "Refermer ce qui n'aurait pas dû être ouvert", "rev": "oui",
     "garde": "pare-feu à l'essai"},
    {"id": "lancer-clamav-lynis-trivy", "nom": "Lancer ClamAV, Lynis, Trivy", "rev": "oui", "garde": "outils en liste blanche"},
]


def brancher(ctx):
    db = ctx.stockage

    def gestes(c):
        return {"gestes": GESTES}

    def journal(c, limite=120):
        return {"journal": db.lire("SELECT * FROM securite_journal ORDER BY id DESC LIMIT ?",
                                   (max(1, min(int(limite or 120), 500)),))}

    def audits(c, id=0):
        if int(id or 0):
            r = db.lire("SELECT * FROM securite_audits WHERE id=?", (int(id),))
            return {"audit": r[0] if r else None}
        return {"audits": db.lire("SELECT id, ts, modele, titre FROM securite_audits ORDER BY id DESC LIMIT 100")}

    def noter(c, geste="", cible="", detail="", ok=True, resultat="", defaire=""):
        if not str(geste or "").strip():
            raise ValueError("geste requis")
        rid = db.ecrire("INSERT INTO securite_journal (qui, geste, cible, detail, ok, resultat, defaire) VALUES (?,?,?,?,?,?,?)",
                        ((ctx.compte or "").strip()[:80], str(geste)[:120], str(cible or "")[:120],
                         str(detail or "")[:400], 1 if ok else 0, str(resultat or "")[:400], str(defaire or "")[:2000]))
        return {"id": rid}

    def prouver_noter(c, res):
        return bool(db.lire("SELECT 1 FROM securite_journal WHERE id=?", (res["id"],)))

    def defaire_noter(c, res):
        db.ecrire("DELETE FROM securite_journal WHERE id=?", (res["id"],))

    def audit_poser(c, modele="", titre="", corps=""):
        if not str(titre or "").strip():
            raise ValueError("titre requis")
        rid = db.ecrire("INSERT INTO securite_audits (modele, titre, corps) VALUES (?,?,?)",
                        (str(modele or "")[:80], str(titre)[:200], str(corps or "")[:40000]))
        return {"id": rid}

    def prouver_audit(c, res):
        return bool(db.lire("SELECT 1 FROM securite_audits WHERE id=?", (res["id"],)))

    def defaire_audit(c, res):
        db.ecrire("DELETE FROM securite_audits WHERE id=?", (res["id"],))

    for cid, f in (("gestes", gestes), ("journal", journal), ("audits", audits)):
        ctx.implementer(cid, f)
    ctx.implementer("noter", noter, prouver_noter, defaire_noter,
                    simuler=lambda x, geste="", **_: "inscrirait le geste « %s » au journal de sécurité" % geste)
    ctx.implementer("audit_poser", audit_poser, prouver_audit, defaire_audit,
                    simuler=lambda x, titre="", **_: "poserait l'audit « %s »" % titre)
