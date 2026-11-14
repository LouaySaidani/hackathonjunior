# Plan de validation

## 1. Validation technique (automatisée)

| Contrôle | Où | Critère |
|---|---|---|
| Calcul des silences | `tests/test_vad.py` | Silences ≥ seuil, marge appliquée, jamais de chevauchement avec la parole. VAD réel (Silero et webrtcvad) sur le clip d'exemple |
| Ajustement à la durée | `tests/test_fit_export.py` | Texte raccourci ou signalé `too_long` |
| WebVTT / TTML | `tests/test_fit_export.py` | VTT valide, `-->` échappé, RTL ; TTML est du XML valide avec `tts:direction="rtl"` |
| Fournisseurs | `tests/test_providers.py` | Demo honnête (faible confiance hors clip d'exemple) ; forme des requêtes Gemini et OpenAI-compatibles (mock HTTP) ; règle « pas de reconnaissance faciale » présente dans le prompt |
| Parcours complet | `tests/test_api.py` | Import avec consentement → analyse → modification, régénération, validation, rejet → validation groupée (`test_validate_all`) → voix TTS → export des 8 fichiers ; seules les lignes validées sont exportées |
| CI | `.github/workflows/ci.yml` | ruff, pytest, build frontend, notebook |

## 2. Validation de l'accessibilité

- axe-core / Lighthouse (score visé ≥ 95) sur chaque page.
- Parcours au clavier seul : Tab, raccourcis J/K/V/X/P/Alt+S, lien d'évitement, focus visible.
- Tests avec NVDA (Windows) et TalkBack (Android) par un·e testeur·rice aveugle.

## 3. Validation de la qualité d'audiodescription (humaine)

Protocole proposé pour un pilote de 3 extraits tunisiens (avec l'accord des ayants droit) :

1. **Audiodescripteur·rice professionnel·le** : corrige les brouillons. Mesures : temps passé par minute de film,
   part des brouillons validés sans modification, modifiés ou rejetés (visible dans l'historique de chaque ligne).
2. **Panel de relecteur·rice·s aveugles ou malvoyant·e·s, rémunéré·e·s** : chaque extrait est écouté en trois versions
   (français, arabe standard, darija), dans un ordre aléatoire.
   - Compréhension 1–5 et questions factuelles sur l'intrigue
   - Préférence de langue (arabe standard / darija / français / sans préférence), **rapportée telle quelle**
   - Commentaires libres (formulaire « Retours testeurs »)
3. **Critères de réussite** fixés avec le panel avant le test (pas de chiffre inventé ici).

## 4. Éthique et conformité

- Revue des consentements et droits avant chaque traitement.
- Vérification qu'aucune ligne n'est exportée sans validation (test automatisé + revue de `script_ayant_droit.json`).
- Vérification de l'absence de noms de personnes réelles non fournis dans la distribution.
