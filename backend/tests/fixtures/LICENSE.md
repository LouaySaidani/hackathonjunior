# Licence du clip de test / Test clip licence

`sample_medina.mp4` (36 s, 854×480) sert aux tests automatiques et au notebook de démonstration.
Il est **entièrement synthétique** et a été créé pour ce dépôt :

- **Image** : formes géométriques générées avec les filtres `color`, `drawbox`, `overlay` et `fade` de FFmpeg
  (porte bleue, ruelle ocre avec une silhouette, intérieur avec lampe et deux verres, ciel nocturne).
  Aucune image tierce, aucun visage, aucune personne réelle.
- **Dialogues** : quatre répliques en français synthétisées avec **eSpeak NG** (voix `fr+f3` / `fr+m3`).
  eSpeak NG est sous licence GPL-3.0 ; l'audio qu'il produit n'est pas couvert par cette licence.
- `sample_medina.transcript.json` : transcription de référence (utilisée uniquement par le fournisseur ASR `demo`).
- `sample_medina.script.json` : script d'audiodescription de référence utilisé par le fournisseur VLM `demo`
  (DEMO MODE) : ce n'est **pas** une sortie de modèle d'IA.

Le clip, la transcription et le script sont placés dans le **domaine public (CC0 1.0)**
<https://creativecommons.org/publicdomain/zero/1.0/>.

Recette de régénération : voir `scripts/make_sample.sh`.
