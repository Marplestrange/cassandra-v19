<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Notes -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : notes -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Notes -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=db0095 ▼▼▼ -->
# Notes

Le carnet d'un compte : numéros stables (`N-0007`, jamais réattribués), renvois `[[N-0007]]` / `[[projet:12]]` avec rétro-liens, dossiers (deux niveaux), étiquettes, projet, état, relecture, cases à cocher liées aux tâches, versions, corbeille, fusion, note du jour, liens de partage, export, archive, import.

- **À la personne** : l'administrateur ne voit pas les notes des autres.
- **Rien ne se perd** : chaque écriture de texte laisse la version d'avant (20 au plus) ; supprimer = corbeille ; vider la corbeille garde une copie dans le résultat de l'acte, donc se défait ; chaque geste a sa preuve et son retour.
- **Partage** : jeton tiré au sort, échéance (30 jours), mot de passe facultatif (scrypt salé, comparaison à temps constant, 8 essais faux par 10 minutes), retrait immédiat. Route publique `/api/public/notes.partage_servir`.
- **Cases ↔ tâches** : les notes ne créent pas de tâche elles-mêmes (le noyau ne laisse pas un module écrire dans un autre) ; l'agent ou l'écran crée la tâche (`taches.creer`, `source="note"`) puis lie la case (`case_lier`). `cases_etat` montre les désaccords, `cases_reprendre` reporte l'état des tâches dans la note.

## Non porté
- Le stockage en fichiers `.md` dans Documents/Notes (V18) : ici la base fait foi ; `exporter`, `archive` et `importer` gardent l'échange avec Obsidian.
- Les natures de renvoi hors notes/projets/tâches sont acceptées mais pas vérifiées (jamais déclarées « mortes »).
- Notes « vivantes » (requête), post-it, `ca_memos_*` (reprise de l'ancien écran), dossier public.
- Rappels liés aux cases (le module des rappels n'existe pas encore).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
