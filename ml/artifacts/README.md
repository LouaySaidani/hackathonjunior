# Modèle entraîné

`python ml/run_all.py` (ou `python ml/train.py`) écrit ici :

- `gap_scorer.joblib` : le modèle scikit-learn, chargé par Wasf au démarrage de chaque analyse ;
- `gap_scorer.json` : ses métadonnées (variables, seuil, scores de validation et de test), affichées dans l'application.

Sans ces fichiers, Wasf fonctionne comme avant : tous les silences reçoivent un brouillon.
