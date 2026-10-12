# certificats — veille des certificats TLS

Porté de la V18 (`_ssl_probe`, `ssl_quota_state`, `_cert_days`). Le module pilote d'origine n'était qu'un manifeste ; il est maintenant réel.

- Sonde horaire du certificat réellement servi (port 443) pour les hôtes du panneau + `certificats.hotes`. États : valide, proche (seuil réglable, 21 j), échu, **inconnu** (jamais « sans certificat » sur une simple impossibilité de lire).
- Registre des émissions Let's Encrypt (5 par semaine et par domaine enregistré), alimenté par les événements `fastpanel.certificat_renouvele` lus dans le journal du bus (curseur : un événement ne compte qu'une fois ; le module ne dépend pas de la présence de fastpanel).
- Constats avec le quota restant ; critique sous 7 jours ou échu.
- Le **renouvellement** n'est plus ici : il passe par le panneau (`fastpanel.ssl_renouveler`, avec preuve par la date d'émission).

## Non porté
- Calendrier des échéances (`_ssl_calendar_items`) : avec le module agenda. Renouvellement par certbot (sous-processus) : le panneau suffit ; un module certbot viendra si un serveur n'en a pas.
