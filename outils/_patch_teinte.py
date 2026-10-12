"""Patch d'appoint (jetable) : drapeaux `externe` / `sortant` des capacités ; paliers de la plomberie de la mémoire."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def sub(p, old, new, tous=False):
    chemin = RACINE / p
    s = chemin.read_bytes().decode("utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    assert old in s, (p, old[:70])
    s = s.replace(old, new) if tous else s.replace(old, new, 1)
    chemin.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


sub("noyau/manifeste.py", '''    masque: tuple = ()         # noms d'arguments et de résultats qui ne vont JAMAIS au journal (mot de passe, jeton de session...)
''', '''    masque: tuple = ()         # noms d'arguments et de résultats qui ne vont JAMAIS au journal (mot de passe, jeton de session...)
    externe: bool = False      # ce qu'elle lit vient de l'EXTÉRIEUR (un message reçu, une page web) : du texte étranger entre dans le tour, et l'agent ne le tient pas pour des instructions
    sortant: bool = False      # ce qu'elle fait SORT de la maison (un message envoyé, un lien public) : après une lecture externe dans le même tour, elle ne part pas toute seule
''')
sub("noyau/manifeste.py", '''        droit=_qualifier(m["id"], c.get("droit")), masque=tuple(c.get("masque", ())),
    ) for c''', '''        droit=_qualifier(m["id"], c.get("droit")), masque=tuple(c.get("masque", ())), externe=bool(c.get("externe", False)), sortant=bool(c.get("sortant", False)),
    ) for c''')
# la plomberie de la mémoire s'exécute d'emblée (auto) : un tour de chat ne s'arrête pas pour une écriture de service
g = RACINE / "outils/_gen_memoire.py"
s = g.read_bytes().decode("utf-8")
for cid in ("tour_commencer", "apres_echange", "doutes_depuis_reponse"):
    i = s.index('W("%s"' % cid)
    j = s.index("P3, Q5", i)
    s = s[:j] + 'P2A, Q5' + s[j + len("P3, Q5"):]
s = s.replace('P2 = ["raconter", "auto"]\n', 'P2 = ["raconter", "auto"]\nP2A = ["auto", "raconter"]            # la plomberie d\'un tour de chat s\'exécute d\'emblée\n', 1)
g.write_bytes(s.encode("utf-8"))
print("ok")
