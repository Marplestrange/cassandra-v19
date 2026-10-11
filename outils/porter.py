#!/usr/bin/env python3
"""porter.py : fait écrire un BROUILLON de module V19 par le Claude d'Orion (quotas gratuits), à partir du code de la V18 et du guide docs/PORTER.md.

    python outils/porter.py <id> --domaine "ce que fait le module en une phrase" --fonctions "f1, f2, C3" [--lignes 59000-59500] [--famille securite]

Rien n'est écrit sur Orion (lecture seule) : le brouillon revient par la sortie standard, est découpé dans `.porte/<id>/` (hors dépôt), et c'est MOI qui le relis,
le corrige, le teste et le range dans `modules/`. Un brouillon n'est jamais déployé tel quel.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
V18_SUR_ORION = "/root/cassandra-v18/cassandra.py"
MARQUE = re.compile(r"^=== FICHIER : (\S+) ===$", re.M)


def lire(p):
    return (RACINE / p).read_text(encoding="utf-8")


def exemple_de_bancs():
    t = lire("tests/test_noyau.py")
    i = t.index("VEILLE_NOTIF_TOML = ")
    j = t.index("    def test_le_cloisonnement_un_compte_ne_voit_que_ce_qui_le_vise(self):")
    return t[i:j]


def prompt(a):
    return f"""Tu portes un module de la V18 de Cassandra vers la V19. Le code V18 est dans {V18_SUR_ORION} (fichier unique de ~154 000 lignes ; lis UNIQUEMENT ce qui concerne ce module).

MODULE À PORTER : « {a.id} » — {a.domaine}
Fonctions et constantes de la V18 qui lui appartiennent (cherche-les par leur nom ; lis aussi leurs commentaires, ce sont des LEÇONS de bogues déjà payés) :
{a.fonctions}
{('Zone de lignes de la V18 où elles se trouvent (indicatif, le fichier a pu bouger) : ' + a.lignes) if a.lignes else ''}
Famille du menu des modules : « {a.famille} ».

=== GUIDE DE PORTAGE (à suivre à la lettre) ===
{lire('docs/PORTER.md')}

=== MODÈLE À IMITER : un module complet déjà porté (manifeste, code, migration) ===
--- modules/notifications/manifeste.toml ---
{lire('modules/notifications/manifeste.toml')}
--- modules/notifications/module.py ---
{lire('modules/notifications/module.py')}
--- modules/notifications/migrations/001_init.sql ---
{lire('modules/notifications/migrations/001_init.sql')}

=== MODÈLE DE BANCS (extrait de tests/test_noyau.py ; ton fichier sera tests/test_{a.id}.py, qui fait `import test_noyau as base` pour réutiliser MDP, ecrire_module, RACINE, moteur, TOUT...) ===
{exemple_de_bancs()}

=== TA TÂCHE ===
1. Lis dans la V18 les fonctions listées (et ce qu'elles appellent de proche en proche UNIQUEMENT si c'est nécessaire pour comprendre la règle).
2. Écris le module V19 complet en suivant le guide : manifeste, module.py, migrations (état final des tables, sans les ALTER historiques), bancs.
3. Pour tout ce que le module appelait chez un autre module de la V18 (courriel, notifications, coffre, etc.), n'importe rien : émets un événement ou un constat, ou laisse un `# TODO(<module>) : ...` explicite.
4. Cite en commentaire, dans module.py, les LEÇONS de la V18 que tu as portées (« V18 : ... ») et celles que tu n'as pas pu porter.
5. Ne porte pas l'interface. Pas de threads. Pas de chemins ni d'hôtes en dur : des réglages.

FORMAT DE SORTIE — strictement, rien avant, rien après, pas de ``` autour des fichiers :
=== FICHIER : modules/{a.id}/manifeste.toml ===
<contenu>
=== FICHIER : modules/{a.id}/module.py ===
<contenu>
=== FICHIER : modules/{a.id}/migrations/001_init.sql ===
<contenu>
=== FICHIER : tests/test_{a.id}.py ===
<contenu>
=== FICHIER : NOTES.md ===
<ce que tu n'as pas pu porter ou pas compris, les hypothèses, les TODO inter-modules, en 25 lignes maximum>
Lecture seule : tu ne modifies rien. Ne fais PAS de plan : ta réponse EST le résultat, en un seul message, dans le format ci-dessus.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--domaine", default="")
    ap.add_argument("--fonctions", default="")
    ap.add_argument("--lignes", default="")
    ap.add_argument("--famille", default="gestion")
    ap.add_argument("--modele", default="cc-sonnet")
    ap.add_argument("--delai", type=int, default=1500)
    a = ap.parse_args()
    if not a.fonctions:                        # la carte du découpage (docs/decoupe/) donne les symboles du module et son rôle
        import json
        sm = json.loads((RACINE / "docs/decoupe/sym_mod.json").read_text(encoding="utf-8"))
        dm = json.loads((RACINE / "docs/decoupe/data_decoupe2.json").read_text(encoding="utf-8"))["modules"]
        mine = sorted((x for x in sm if x["mod"] == a.id), key=lambda x: x["a"])
        if not mine:
            sys.exit("module inconnu dans la carte : %s" % a.id)
        a.fonctions = ", ".join(x["name"] for x in mine)
        a.lignes = a.lignes or "; ".join("%d-%d" % (x["a"], x["b"]) for x in mine[:0]) or "voir les noms (le fichier a pu bouger)"
        a.domaine = a.domaine or next((m["role"] for m in dm if m["id"] == a.id), a.id)
        a.famille = a.famille if a.famille != "gestion" else {"canaux": "communication", "coffre": "securite", "planifie": "travail"}.get(a.id, "gestion")
    sortie = RACINE / ".porte" / a.id
    sortie.mkdir(parents=True, exist_ok=True)
    cmd = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", "root@orion",
           "cd /root/cassandra-v18 && ANTHROPIC_DEFAULT_HAIKU_MODEL=cc-haiku ANTHROPIC_DEFAULT_SONNET_MODEL=cc-sonnet ANTHROPIC_DEFAULT_OPUS_MODEL=cc-opus "
           "timeout %d claude -p --model %s --allowedTools \"Read Grep Glob\" --disallowedTools \"Write Edit Bash NotebookEdit\" --max-turns 40 2>/dev/null" % (a.delai, a.modele)]
    r = subprocess.run(cmd, input=prompt(a), capture_output=True, text=True, encoding="utf-8")
    (sortie / "brut.txt").write_text(r.stdout, encoding="utf-8")
    parts = MARQUE.split(r.stdout)
    n = 0
    for k in range(1, len(parts) - 1, 2):
        chemin = parts[k]
        if ".." in chemin or chemin.startswith("/"):
            continue
        cible = sortie / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes((parts[k + 1].strip(chr(10)) + chr(10)).encode('utf-8'))
        n += 1
    print("%d fichier(s) dans %s (sortie brute : %d octets, code %s)" % (n, sortie, len(r.stdout), r.returncode))
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
