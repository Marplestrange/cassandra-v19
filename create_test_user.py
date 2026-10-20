import CN_main
import os
donnees = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees")
n = CN_main.Noyau(donnees)
res = n.identite.creer("root@x.fr", "Test!2026")
print("User created:", res)
n.droits.regler_admin("root@x.fr", True)
