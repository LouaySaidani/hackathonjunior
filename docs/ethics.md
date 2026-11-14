# Éthique 360 — choix de conception

Basira est conçu pour le hackathon OIF × JEI « IA Éthique 360 ». Chaque principe ci-dessous est **implémenté dans le
code** ; le fichier et le comportement correspondants sont indiqués.

## 1. Créateurs et métiers : l'IA assiste, l'humain décide

- **L'audiodescripteur·rice est l'auteur·e.** Une ligne ne devient `HUMAN VALIDATED` que par un appel explicite
  `POST /descriptions/{id}/validate` avec un nom (`routes.py`). Aucun code ne valide automatiquement ; toute modification
  ultérieure repasse la ligne en `EDITED BY HUMAN`.
- **Seules les lignes validées sont exportées et vocalisées** (`service.export_project`, `synthesize_validated`).
- **Traçabilité** : chaque ligne garde son texte IA d'origine, le fournisseur et le modèle, la confiance, et un historique
  horodaté (création, modification, régénération, validation, rejet, voix).
- **Relecteur·rice·s aveugles rémunéré·e·s** (modèle de l'ATAA, Association des traducteurs et adaptateurs de l'audiovisuel) :
  la page *Retours testeurs* recueille la compréhension (1–5), la préférence de langue et le statut « rémunéré·e », avec consentement.

## 2. Droits

- Case de consentement **obligatoire** à l'import (refus HTTP 400 sinon).
- **Aucun entraînement** sur les films importés. L'option d'opt-in est décochée par défaut, enregistrée, et n'est utilisée par aucun code dans ce MVP.
- Le script d'audiodescription complet (`script_ayant_droit.json`, avec l'historique) est généré pour être **remis à l'ayant droit**.
- Le clip d'exemple est synthétique et placé sous CC0 (`samples/LICENSE.md`). Aucun film protégé n'est téléchargé.

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

- Audiodescription en **français, arabe standard (فصحى) et darija tunisienne (تونسي)**, plus l'anglais.
- Rendu **RTL** de l'arabe dans l'interface (`dir="rtl"`, `lang`), dans le WebVTT (balise `<lang>` et RLM) et dans le TTML (`tts:direction="rtl"`).
- Le prompt demande des termes culturels exacts (*sefsari*, *chéchia*, *médina*) **seulement s'ils sont visibles**.
- **Le choix entre arabe standard et darija revient aux usagers aveugles** : on le mesure dans les retours et on en rend compte, on ne l'impose pas.
- Voix darija : la synthèse est signalée comme approximative. L'outil propose l'**enregistrement d'une voix humaine** (par ligne ou en piste complète).

## 5. Transparence

- Trois états visibles (icône et texte, jamais la couleur seule) : `BROUILLON IA` → `MODIFIÉ PAR UN HUMAIN` → `VALIDÉ PAR UN HUMAIN`.
- Les lignes peu fiables sont marquées **« À relire »** (confiance < 0,6, éléments incertains, texte trop long).
- Mentions dans les exports : `NOTE` VTT, `ttm:desc` / `ttm:agent` TTML, métadonnées MP4, `credits.txt` :
  « audiodescription assistée par IA, validée par <nom> ».
- **DEMO MODE** affiché en bannière et dans tous les exports dès qu'un fournisseur simulé est utilisé.

## 6. Planète

- On ne traite que les silences et quelques images clés, pas chaque image du film.
- Modèles petits et quantifiés (Whisper `small` en int8), **CPU par défaut**, téléchargés une seule fois puis mis en cache (volume `/models`).

## 7. Limites honnêtes et modèle économique

- En Tunisie, aucune obligation légale ne finance l'audiodescription. Pistes de financement possibles : festivals (JCC…),
  chaînes publiques (Al Wataniya), subventions OIF, UE ou ambassades, mécénat.
- Nous ne citons **aucune statistique** sur le nombre de personnes aveugles en Tunisie : nous n'avons pas de source vérifiée.
- La qualité de l'ASR sur la darija avec un Whisper générique est limitée ; d'où le fine-tuning prévu sur les jeux de données ci-dessus.
