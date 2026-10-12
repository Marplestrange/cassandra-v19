#!/bin/sh
# La preuve que le module peut travailler : Python sait ouvrir une connexion TLS vérifiée.
python3 -c "import ssl; ssl.create_default_context()" || { echo "certificats : pas de contexte TLS" >&2; exit 3; }
echo "certificats : TLS disponible"
