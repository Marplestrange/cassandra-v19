<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : dns — domaines et DNS -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : dns -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.2.1  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : dns — domaines et DNS -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.2.1 empreinte=bf8cf0 ▼▼▼ -->
# dns — domaines et DNS

Porté de la V18 (`_dns_*`, `_detect_dns`, `_aut_dns_corriger`, `_dom_expiration`). Plus de `dig` : un client DNS en Python pur (UDP, puis TCP si tronqué).

- Zones suivies = domaines du panneau (module fastpanel, s'il est là) + réglage `dns.domaines`.
- Relève toutes les heures auprès du serveur de noms faisant foi ; la première relève devient la référence (versionnée, rien n'est écrasé).
- Un nom qu'on n'a pas pu lire est **inconnu** : ni dérive, ni conformité (en V18 un résolveur qui flanchait faisait une fausse dérive).
- Dérive = constat. Adresse publique changée (deux services d'accord) = constat avec correction proposée (`corriger_enregistrement`, palier réglé par l'administrateur : « raconter » par défaut).
- Correction : un A existant, d'une zone suivie, non proxifié, vers l'adresse publique actuelle, jamais un nom réservé (`dns.ne_pas_toucher`) ni un nom de courrier (sauf `dns.courrier_libre`) ; prouvée sur le serveur de noms, défaisable (ancienne valeur, référence précédente).
- Expiration des domaines par RDAP (une lecture par domaine et par jour, seuil `dns.expire_jours`).

## À savoir
- Les listes de noms réservés sont des **réglages vides par défaut** (en V18, une valeur propre à une installation était écrite dans le code).
- Le jeton Cloudflare est un réglage secret (le coffre chiffré n'est pas encore porté).
- Preuve faite contre un faux DNS (UDP et TCP réels en local) et un faux Cloudflare ; pas contre un vrai Cloudflare.

## Non porté
- `_dns_txt` / `_cf_*` (résolution TXT et noms Cloudflare de la V18 utilisés par le courrier) : avec le module courrier.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
