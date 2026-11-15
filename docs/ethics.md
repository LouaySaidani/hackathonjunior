# Éthique 360 : choix de conception

[← Retour au README](../README.md)

Wasf est conçu pour le hackathon OIF × JEI « IA Éthique 360 ». Chaque principe ci-dessous est **implémenté dans le
code** ; le fichier et le comportement correspondants sont indiqués.

## 1. Créateurs et métiers : l'IA assiste, l'humain décide

- **L'audiodescripteur·rice est l'auteur·e.** Une ligne ne devient `VALIDÉ PAR UN HUMAIN` que par un appel explicite
  `POST /descriptions/{id}/validate` avec un nom (`routes.py`). Aucun code ne valide automatiquement ; toute modification
  ultérieure repasse la ligne en `MODIFIÉ PAR UN HUMAIN`.
- **Seules les lignes validées sont exportées et vocalisées** (`service.export_project`, `synthesize_validated`).
- **Traçabilité** : chaque ligne garde son texte IA d'origine, le fournisseur et le modèle, la confiance, et un historique
  horodaté (création, modification, régénération, validation, rejet, voix).
- **Relecteur·rice·s aveugles rémunéré·e·s** (modèle de l'ATAA, Association des traducteurs et adaptateurs de l'audiovisuel) :
  la page *Retours testeurs* recueille la compréhension (1–5), la préférence de langue et le statut « rémunéré·e », avec consentement.

## 2. Droits

- Case de consentement **obligatoire** à l'import (refus HTTP 400 sinon).
- **Aucun entraînement** sur les films importés. L'option d'opt-in est décochée par défaut, enregistrée, et n'est utilisée par aucun code dans ce MVP.
- Le script d'audiodescription complet (`script_ayant_droit.json`, avec l'historique) est généré pour être **remis à l'ayant droit**.
- Le clip de test est synthétique et placé sous CC0 (`backend/tests/fixtures/LICENSE.md`).
- La vidéo d'exemple (`samples/les_ephemeres.mp4`) est un extrait du court métrage francophone « Les éphémères » (Nils Caneele, 2013), sous licence **CC BY-NC** : crédité, usage non commercial (`samples/LICENSE.md`). L'ancien extrait protégé a été retiré du dépôt ; il doit encore être retiré de l'historique git avant toute publication.

## 3. Données et vie privée

- **Pas de reconnaissance faciale.** Les personnages ne sont nommés qu'à partir de la distribution saisie par l'utilisateur
  (règle explicite dans le prompt système du VLM, `providers/vision.py`).
- Stockage local (`./data`), secrets uniquement côté serveur (variables d'environnement).
- Seules quelques images clés (1 à 3 par silence) quittent la machine si un VLM distant est configuré. L'audio n'est jamais envoyé
  au VLM.
- Jeux de données ouverts de parole tunisienne pour un futur fine-tuning (non utilisés à l'exécution). Licences à vérifier à la source avant tout usage :

| Jeu de données | Contenu | Licence |
|---|---|---|
| LinTO Tunisian Arabic (linagora) | Parole en arabe tunisien | Voir la fiche Hugging Face (licence indiquée par l'éditeur) |
| TunSwitch | Parole tunisienne avec alternance arabe/français | Voir la publication et le dépôt d'origine |
| TARIC | Corpus de parole en arabe tunisien (domaine ferroviaire) | Voir la publication d'origine |
| TEDxTN | Conférences TEDx en tunisien, transcrites | Voir la fiche du jeu de données |

## 4. Cultures et langues

- Audiodescription en **français, arabe standard (فصحى) et darija tunisienne (تونسي)**.
- Rendu **RTL** de l'arabe dans l'interface (`dir="rtl"`, `lang`), dans le WebVTT (balise `<lang>` et RLM) et dans le TTML (`tts:direction="rtl"`).
- Le prompt demande des termes culturels exacts (*sefsari*, *chéchia*, *médina*) **seulement s'ils sont visibles**.
- **Le choix entre arabe standard et darija revient aux usagers aveugles** : on le mesure dans les retours et on en rend compte, on ne l'impose pas.
- Voix darija : la synthèse est signalée comme approximative. La voix est toujours générée par la synthèse vocale : l'humain intervient sur le **texte** (écriture, correction, validation), pas sur l'enregistrement.

## 5. Transparence

- Trois états visibles (icône et texte, jamais la couleur seule) : `BROUILLON IA` → `MODIFIÉ PAR UN HUMAIN` → `VALIDÉ PAR UN HUMAIN`.
- Les lignes peu fiables sont marquées **« À relire »** (confiance < 0,6, éléments incertains, texte trop long).
- Mentions dans les exports : `NOTE` VTT, `ttm:desc` / `ttm:agent` TTML, métadonnées MP4, `credits.txt` :
  « audiodescription assistée par IA, validée par <nom> ».
- **DEMO MODE** affiché en bannière et dans tous les exports dès qu'un fournisseur simulé est utilisé.

## 6. Planète

- On ne traite que les silences et quelques images clés, pas chaque image du film.
- Modèles petits et quantifiés (Whisper `small` en int8), **CPU par défaut**, téléchargés une seule fois puis mis en cache dans `./models`.

## 7. Limites honnêtes et modèle économique

- En Tunisie, aucune obligation légale ne finance l'audiodescription. Pistes de financement possibles : festivals (JCC…),
  chaînes publiques (Al Wataniya), subventions OIF, UE ou ambassades, mécénat.
- Nous ne citons **aucune statistique** sur le nombre de personnes aveugles en Tunisie : nous n'avons pas de source vérifiée.
- La qualité de l'ASR sur la darija avec un Whisper générique est limitée ; d'où le fine-tuning prévu sur les jeux de données ci-dessus.

## 8. Plan de validation

### Technique (automatisée)

Les tests (`backend/tests/`) vérifient le calcul des silences avec un vrai VAD, l'ajustement des textes à la durée, la validité du WebVTT et du TTML (y compris de droite à gauche), la règle « pas de reconnaissance faciale » dans le prompt, et le parcours complet de l'API : seules les lignes validées sont exportées. La CI (`.github/workflows/ci.yml`) lance ruff, pytest, le notebook et le build de l'interface.

### Accessibilité

- axe-core / Lighthouse (score visé ≥ 95) sur chaque page.
- Parcours au clavier seul : Tab, raccourcis J/K/V/X/P/Alt+S, lien d'évitement, focus visible.
- Tests avec NVDA (Windows) et TalkBack (Android) par un·e testeur·rice aveugle.

### Qualité de l'audiodescription (humaine)

Protocole proposé pour un pilote de 3 extraits tunisiens (avec l'accord des ayants droit) :

1. **Audiodescripteur·rice professionnel·le** : corrige les brouillons. Mesures : temps passé par minute de film,
   part des brouillons validés sans modification, modifiés ou rejetés (visible dans l'historique de chaque ligne).
2. **Panel de relecteur·rice·s aveugles ou malvoyant·e·s, rémunéré·e·s** : chaque extrait est écouté en trois versions
   (français, arabe standard, darija), dans un ordre aléatoire.
   - Compréhension 1–5 et questions factuelles sur l'intrigue
   - Préférence de langue (arabe standard / darija / français / sans préférence), **rapportée telle quelle**
   - Commentaires libres (formulaire « Retours testeurs »)
3. **Critères de réussite** fixés avec le panel avant le test (pas de chiffre inventé ici).

### Éthique et conformité

- Revue des consentements et droits avant chaque traitement.
- Vérification qu'aucune ligne n'est exportée sans validation (test automatisé + revue de `script_ayant_droit.json`).
- Vérification de l'absence de noms de personnes réelles non fournis dans la distribution.

## Licences

| Élément | Licence |
|---|---|
| Code de Wasf | Apache-2.0 ([LICENSE](../LICENSE)) |
| Vidéo d'exemple `samples/les_ephemeres.mp4` et son script de référence | Extrait de « Les éphémères », Nils Caneele (2013), **CC BY-NC** : usage non commercial, attribution obligatoire ([samples/LICENSE.md](../samples/LICENSE.md)) |
| Clip de test synthétique, transcription et script de référence | CC0 1.0 ([backend/tests/fixtures/LICENSE.md](../backend/tests/fixtures/LICENSE.md)) |
| faster-whisper / CTranslate2 | MIT ; poids Whisper d'OpenAI sous MIT |
| Silero VAD | MIT |
| scikit-learn | BSD-3-Clause |
| QuerYD / YouDescribe (horaires et textes des descriptions, pour l'entraînement) | Données de recherche ; vidéos YouTube téléchargées localement par `ml/download.py`, **jamais redistribuées** (`ml/data/` est exclu du dépôt) |
| FFmpeg | LGPL/GPL (binaire système, non redistribué dans le dépôt) |
| espeak-ng | GPL-3.0 (installé séparément, facultatif) |
| edge-tts | Bibliothèque sous LGPL-3.0 ; service vocal de Microsoft soumis à ses conditions |
| Gemini / modèles OpenAI-compatibles | Conditions de chaque fournisseur ; non utilisés en DEMO MODE |
| LinTO, TunSwitch, TARIC, TEDxTN (prévus pour le fine-tuning, non inclus) | Voir la licence de chaque jeu de données à sa source |
