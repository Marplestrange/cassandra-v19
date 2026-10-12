-- Le jeton du robot est maintenant un réglage secret par compte, chiffré au repos : on efface ce que cette table pouvait en garder.
UPDATE liens SET jeton = '';
