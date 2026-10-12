#!/bin/sh
# Certificats ne pose rien sur le système : il lit le port 443 et tient un registre dans sa base. Il n'exige que le module ssl de Python.
python3 -c "import ssl, socket" || { echo "certificats : le module ssl de Python manque" >&2; exit 3; }
echo "certificats : prêt (rien à installer)"
