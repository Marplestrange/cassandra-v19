# Tests d'interface (Playwright)

Un serveur de test **isolé** est lancé à chaque suite (`preparer_serveur.py`) : dossier de données neuf et jetable (`.donnees-test/`), compte d'essai créé dedans, port 9005. Rien ne touche à l'instance de développement.

    cd tests-ui
    npm install          # une fois
    npx playwright install chromium   # une fois
    npm test

Le compte d'essai (`UI_COMPTE`, `UI_MDP`) ne vaut que dans ce dossier jetable. `preparer_serveur.py` refuse de tourner contre le dossier de données réel.
