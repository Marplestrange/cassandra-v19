<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : web — la porte du dehors -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : web -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : web — la porte du dehors -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=61c16f ▼▼▼ -->
# web — la porte du dehors

La seule porte des agents vers le dehors : `rechercher(requete, limite)` et `lire(url)`. Tout ce qui revient est une **donnée extérieure** (capacités marquées `externe`), jamais une consigne.

- `rechercher` interroge le moteur que l'administrateur configure (`web.moteur_url`, compatible SearXNG, JSON). Aucune adresse par défaut.
- `lire` rend `{url, titre, texte, lu_le, empreinte}` : texte seul, borné, jamais le HTML.
- Protection contre la forgerie de requête côté serveur : http et https seulement, adresses privées, de boucle locale, de lien local, 100.64.0.0/10 et multicast refusées (et leurs équivalents IPv6), vérifiées à chaque redirection (3 au plus) et sur l'adresse réellement connectée ; ports 80 et 443 ; 2 Mo ; texte, HTML, JSON.
- `web.hotes_bloques` refuse des sources. Le journal (`lectures_recentes`) garde adresse sans requête, taille et empreinte, jamais le contenu.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
