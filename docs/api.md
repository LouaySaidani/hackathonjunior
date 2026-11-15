# API REST

URL de base : `http://localhost:8000`. Documentation OpenAPI interactive : **`/docs`**. Les corps de requête et de
réponse sont en JSON, sauf mention contraire. Les erreurs renvoient `{"detail": "<message en français>"}`.

## Système

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/health` | `{"status":"ok","version","demo_mode"}` : l'interface vérifie ainsi que le serveur répond |
| GET | `/api/system` | Fournisseurs actifs, DEMO MODE, seuils, langues acceptées (jamais de secrets) |
| GET | `/api/stats` | Compteurs du tableau de bord |

## Projets

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/projects` | Liste avec le nombre de lignes par état, `needs_review`, `active_job` |
| POST | `/api/projects` | **multipart** : `file` (mp4/mov/mkv), `title`, `language` (langue de description : `fr`/`ar`/`aeb`, sinon 422), `dialogue_language` (langue parlée dans le film, simple indication pour Whisper : `auto` par défaut, l'interface propose `ar`/`fr`/`en`), `cast` (JSON `[{name, description}]`), `consent` (**doit valoir true**, sinon 400), `training_opt_in` (false par défaut). 415 si le type est refusé ou la vidéo illisible, 413 si elle est trop lourde |
| POST | `/api/projects/sample` | Crée un projet à partir de la vidéo d'exemple (`SAMPLE_VIDEO`, par défaut `samples/les_ephemeres.mp4`) |
| GET | `/api/projects/{id}` | Projet complet : transcription, zones de parole, créneaux (avec score ML), images clés, descriptions |
| PATCH | `/api/projects/{id}` | `title`, `language`, `validator_name`, `cast`, `training_opt_in` |
| DELETE | `/api/projects/{id}` | Supprime le projet et ses fichiers |
| POST | `/api/projects/{id}/analyze` | Lance l'analyse (audio → VAD → ASR → silences → créneaux → score ML → scènes → images clés → brouillons). 202 + tâche. 409 si une tâche est en cours, ou si des lignes ont été validées, modifiées ou écrites par un humain (elles seraient effacées) : passer `?force=true` après une confirmation explicite |
| GET | `/api/jobs/{job_id}` | `status` (`queued`/`running`/`done`/`error`), `progress` de 0 à 1, `step`, `message`, `result` |

## Descriptions (humain dans la boucle)

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/api/gaps/{id}/draft` | « Rédiger ici » : brouillon IA dans un créneau, y compris un créneau que le modèle ML n'a pas retenu. 201 + description. 409 si une tâche est en cours ou si le créneau a déjà une ligne non rejetée, 429 si le quota du VLM est épuisé, 502 si la rédaction échoue |
| POST | `/api/projects/{id}/descriptions` | Ligne manuelle `{start, end, text, language, author}` → `origin=human`, `status=edited`. 422 si elle chevauche un dialogue |
| PATCH | `/api/descriptions/{id}` | `{text?, start?, end?, language?, editor}`. Toute modification → `status=edited`, retire la validation, recalcule les indicateurs. Un texte plus long (ou une langue plus lente) allonge la ligne dans le silence libre quand `end` n'est pas fourni. 422 si chevauchement avec un dialogue |
| DELETE | `/api/descriptions/{id}` | Supprime la ligne |
| POST | `/api/descriptions/{id}/validate` | `{validator}` **obligatoire**. Renseigne `validated`, `validated_by`, `validated_at`. Une ligne `too_long` est d'abord allongée dans le silence libre qui suit ; si elle ne tient toujours pas, 422 avec le nombre maximal de mots |
| POST | `/api/projects/{id}/validate-all` | `{validator}` **obligatoire**. Valide d'un coup toutes les lignes `ai_draft` / `edited` (historique : « validation groupée »). Les lignes rejetées ne sont pas touchées ; les lignes `too_long` restent bloquées et sont renvoyées dans `blocked`. → `{validated, blocked[]}` |
| POST | `/api/descriptions/{id}/reject` | `{by, reason}` |
| POST | `/api/descriptions/{id}/reopen` | Sort une ligne de l'état `rejected` |
| POST | `/api/descriptions/{id}/regenerate` | `{hint?, language?}` : nouveau brouillon IA pour le même créneau, la ligne repasse à `ai_draft` |
| POST | `/api/descriptions/{id}/tts` | Synthèse vocale (**lignes validées uniquement**, sinon 409). Renvoie des `warnings` (accélération, qualité de l'arabe…) |
| DELETE | `/api/descriptions/{id}/voice` | Supprime la voix générée (elle peut être générée à nouveau) |

Objet description : `id, start, end, text, language, origin (ai|human), status (ai_draft|edited|validated|rejected),
confidence, needs_review, flags[] (low_confidence, uncertain, trimmed_to_fit, too_long, demo), provider, model,
ai_original_text, validated_by, validated_at, history[], audio_url, audio_source (tts|demo_tone),
audio_duration, audio_voice, estimated_seconds`.

## Voix et export

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/api/projects/{id}/tts` | Tâche : voix pour toutes les lignes validées qui n'en ont pas encore |
| POST | `/api/projects/{id}/export` | Tâche : produit `film_audiodecrit.mp4` (mixage AD + piste originale), `ad_track.wav/.mp3`, `description.vtt`, `description.ttml`, `credits.txt`, `script_ayant_droit.json`, `export_complet.zip`. **Lignes validées uniquement** ; 409 s'il n'y en a aucune |
| GET | `/api/projects/{id}/export` | Liste des fichiers générés |
| GET | `/api/projects/{id}/export/{name}` | Télécharge un fichier |
| GET | `/api/files/{path}` | Médias du projet (vidéo avec HTTP Range, images clés, voix), limités à `DATA_DIR/projects/` (la base de données n'est jamais servie) |

## Retours des testeurs aveugles et malvoyants

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/api/feedback` | `{project_id?, tester_alias?, comprehension 1–5, preferred_language (msa|darija|fr|no_preference), comment?, consent (doit valoir true), paid_tester}` |
| GET | `/api/feedback?project_id=` | Liste des retours |
| GET | `/api/feedback/summary?project_id=` | Nombre de retours, compréhension moyenne, préférences de langue, histogramme |
