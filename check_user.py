import CN_main
import os
donnees = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees")
n = CN_main.Noyau(donnees)
print("Exists:", n.identite.existe("root@x.fr"))
