# Modèles

Le registre des modèles de langage et la porte unique pour les faire parler (`completer`).

- Un modèle se déclare une fois : fournisseur, nom, adresse, clé **chiffrée** (liée à son modèle). La clé ne sort jamais : ni liste, ni journal, ni réponse.
- Deux portées : le modèle d'un **compte** (sa clé, lui seul s'en sert) et le modèle de l'**instance** (administrateur ; il sert les **rôles** — itare_citadelle, vision, relecteur, principal, second_avis… — et seulement les acteurs de la maison). Un compte n'utilise jamais la clé du serveur.
- `completer` : OpenAI-compatible ou Ollama natif (`think`, `num_ctx`) ; un raisonneur qui rend vide est rejoué une fois (budget ×3) ; une réponse tronquée est dite ; une panne est un résultat, pas une exception. Les échanges ne vont pas au journal ; les jetons sont comptés (`usage`).
- Ollama : modèles locaux, téléchargement en file tiré par un moteur (progression), suppression refusée si le modèle sert.
- Nouveau dans le noyau : `[permissions] secrets = true` → `ctx.chiffrer / ctx.dechiffrer`.

## Non porté
Migration des anciennes clés de config.json (la V19 repart d'une base vide), appel en flux (streaming) pour le chat, appels avec outils (ils viendront avec le module des agents).
