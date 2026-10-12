# Agenda

Événements (récurrence, alarme, liens vivants, journal), rappels, import/export iCalendar, lecture CalDAV, et la vue temporelle unique (`calendrier`) : événements, tâches datées, rappels, jalons des projets.

- À la personne : l'administrateur ne voit pas l'agenda des autres.
- Une série est gardée en une ligne (RRULE) et développée à la lecture sur la plage demandée ; non gérées : BYMONTHDAY, BYSETPOS, BYMONTH, BYDAY hors hebdomadaire, EXDATE. Un import avec une règle non gérée garde l'événement de base et le dit.
- CalDAV : réglages `caldav_url`, `caldav_identifiant`, `caldav_mot_de_passe` (secret) par compte ; lecture seule ; une panne laisse l'agenda local.
- Rappels échus et alarmes d'événements sont des constats (détecteurs), résolus seuls.
- La préparation d'un événement : l'écran crée la tâche (`taches.creer`, `source="événement"`) puis la lie (`lien_ajouter kind=tache`).

## Non porté
Échéances de certificats et crons projetés dans la vue (modules concernés pas encore à ce niveau), écriture CalDAV (retirée en V18 aussi).
