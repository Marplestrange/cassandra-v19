"""Le paquet des bancs : un réglage RÉSERVÉ AUX TESTS, posé ici et nulle part ailleurs.

En service, le hachage des mots de passe coûte scrypt n=2**17 (~0,5 s, 128 Mo) ; c'est voulu, et aucune variable d'environnement ni aucun réglage ne permet
de l'abaisser. Les bancs, eux, créent des centaines de comptes : ce paquet remplace, DANS LE PROCESSUS DE TEST SEULEMENT, le coût par n=2**10. Le code de
production ne lit rien de ceci : c'est le banc qui va modifier le dictionnaire du module, jamais l'inverse.

Un banc qui doit exercer les vrais paramètres (ceux du fichier de production, relevés AVANT le remplacement) les rétablit le temps d'un test :
    from tests import parametres_de_production
    @parametres_de_production()
    def test_...(self): ...
"""
import sys
from pathlib import Path
from unittest import mock

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from noyau import CN_identite as _identite                    # noqa: E402

SCRYPT_PRODUCTION = dict(_identite._SCRYPT)                    # relevé AVANT le remplacement : la valeur réelle du fichier de production
SCRYPT_BANC = dict(_identite._SCRYPT, n=2 ** 10)               # n=2**10 : ~100 fois moins cher, assez pour exercer le format et la vérification

_identite._SCRYPT.update(SCRYPT_BANC)


def parametres_de_production():
    """Un décorateur (ou gestionnaire de contexte) qui rétablit, le temps d'un test, les paramètres scrypt de production."""
    return mock.patch.dict(_identite._SCRYPT, SCRYPT_PRODUCTION)
