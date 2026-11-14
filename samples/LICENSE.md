# Vidéo d'exemple / Sample video

`vd_test.mp4` (2 min 30, 852×480) est un **extrait de film commercial, protégé par le droit d'auteur**.
Tous les droits appartiennent à leurs ayants droit. Il n'est **pas** placé sous licence libre.

- Il sert uniquement à **tester Wasf et à le présenter au jury du hackathon**, dans ce **dépôt privé**.
- **Ne pas le redistribuer** ni l'utiliser en dehors de ce cadre.
- **À retirer de tout l'historique git** (pas seulement du dernier commit) avant de rendre le dépôt public.
- Pour une démonstration publique, utilisez plutôt un film sous licence libre
  (`scripts/get_test_videos.sh` : films de la Blender Foundation, CC-BY).

## Fichiers de référence (DEMO MODE)

- `vd_test.script.json` : les 17 descriptions utilisées à la place de Gemini quand Wasf tourne sans clé
  d'API. Rédigées par Gemini puis **relues, corrigées et validées par un humain** dans l'éditeur, puis
  exportées avec `python scripts/export_reference.py <id_du_projet>`.
- `vd_test.transcript.json` : les dialogues transcrits par Whisper, utilisés à la place de Whisper sans
  modèle. Il s'agit du texte des dialogues du film : même statut que la vidéo (protégé, dépôt privé).

Le clip synthétique sous CC0 utilisé par les tests se trouve dans `backend/tests/fixtures/`.
