"""Patch d'appoint (jetable) : marque les capacités qui lisent de l'extérieur (externe) ou qui font sortir quelque chose (sortant)."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MARQUES = {"courrier": {"lister": "externe", "lire": "externe", "piece": "externe", "envoyer": "sortant"},
           "telegram": {"envoyer": "sortant"},
           "notes": {"partage_creer": "sortant"}}
for mod, caps in MARQUES.items():
    chemin = RACINE / "modules" / mod / "CN_manifeste.toml"
    s = chemin.read_bytes().decode("utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for cid, drapeau in caps.items():
        motif = '[[capacites]]\nid = "%s"\n' % cid
        assert motif in s, (mod, cid)
        i = s.index(motif)
        j = s.find("\n\n", i)
        j = len(s) if j < 0 else j
        bloc = s[i:j]
        if drapeau + " = true" not in bloc:
            s = s[:j] + "\n" + drapeau + " = true" + s[j:]
    chemin.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print("ok")
