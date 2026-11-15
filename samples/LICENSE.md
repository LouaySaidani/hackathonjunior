# Vidéo d'exemple

`les_ephemeres.mp4` (63 s, 1280×516, dialogues en français) est un **extrait du court métrage
« Les éphémères »** de **Nils Caneele** (Canada, 2013), diffusé par la plateforme de films libres
[HorsCiné](https://horscine.org/film/les-ephemeres/) sous licence
**[Creative Commons BY-NC](https://creativecommons.org/licenses/by-nc/4.0/deed.fr)** (attribution, pas d'usage
commercial).

## Modifications apportées

- Extrait de 2:28 à 3:31 du film (version 720p de HorsCiné).
- Image recadrée en haut et en bas pour retirer les bandes noires et les sous-titres anglais incrustés.
- Audiodescription en français ajoutée avec Wasf (les fichiers ci-dessous et les exports du projet).

## Conditions

- Citer le film et son auteur, comme ci-dessus, à chaque diffusion de l'extrait ou de sa version audiodécrite.
- **Usage non commercial uniquement** : démonstration, test, enseignement. L'extrait et sa version audiodécrite
  ne doivent jamais être vendus ni intégrés à une offre payante.
- Le code de Wasf reste sous Apache-2.0 : cette licence ne concerne que la vidéo et les fichiers qui en dérivent.

## Fichiers de référence (DEMO MODE)

- `les_ephemeres.script.json` : les descriptions utilisées à la place de Gemini quand Wasf tourne sans clé
  d'API. Rédigées par Gemini puis **relues et validées par un humain** dans l'éditeur, puis exportées avec
  `python scripts/export_reference.py <id_du_projet>`.
- `les_ephemeres.transcript.json` : les dialogues transcrits par Whisper, utilisés à la place de Whisper sans
  modèle (même licence que le film).

## Ancienne vidéo d'exemple

L'ancien extrait (`vd_test.mp4`, film commercial protégé par le droit d'auteur) a été retiré du dépôt le
15/11/2026. Il reste dans l'**historique git** : il faut l'en retirer avant de rendre le dépôt public.

Le clip synthétique sous CC0 utilisé par les tests se trouve dans `backend/tests/fixtures/`.
