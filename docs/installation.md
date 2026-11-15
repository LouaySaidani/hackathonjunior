# Installation, utilisation et configuration

[← Retour au README](../README.md)

## Installation

Wasf tourne sur votre propre ordinateur. La première installation prend 15 à 20 minutes et demande une connexion Internet.

### 1. Installer les outils (une seule fois)

| Outil | Version | Rôle | Vérification |
|---|---|---|---|
| **Git** | récente | récupérer le code | `git --version` |
| **Python** | **3.11** | serveur et pipeline d'IA | `py -3.11 --version` (Windows) ou `python3.11 --version` |
| **Node.js** | **22 ou plus** | construire l'interface web | `node --version` |
| **FFmpeg** | récente | audio, images clés, mixage | `ffmpeg -version` |
| espeak-ng | *facultatif* | voix de secours sans Internet | `espeak-ng --version` |

**Windows** (PowerShell) :

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.11
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Gyan.FFmpeg
```

Fermez puis rouvrez PowerShell pour qu'il trouve les nouveaux outils, et vérifiez-les avec les commandes de la dernière colonne.

Sous Linux ou macOS, suivez plutôt l'[installation rapide sous Linux et macOS](#installation-rapide-sous-linux-et-macos), plus bas : elle remplace les étapes 1 à 6.

### 2. Récupérer le code

```powershell
git clone https://github.com/LouaySaidani/hackathonjunior.git
cd hackathonjunior
```

> Le dépôt est privé : il faut avoir été invité sur GitHub.

### 3. Installer les dépendances Python

```powershell
py -3.11 -m venv .venv                                       # Linux/macOS : python3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip              # Linux/macOS : .venv/bin/python …
.venv\Scripts\python -m pip install -r backend\requirements.txt
```

### 4. Construire l'interface web

```powershell
cd frontend
npm ci
npm run build
cd ..
```

> Un avertissement `npm warn install-scripts … esbuild` peut s'afficher : il est sans conséquence.

### 5. Configurer (facultatif)

```powershell
copy .env.example .env                                       # Linux/macOS : cp .env.example .env
```

Sans clé, Wasf démarre en DEMO MODE, et une bannière le signale. La vidéo d'exemple reçoit alors des descriptions préparées à l'avance et relues par un humain. Pour obtenir de vraies descriptions, ouvrez `.env` et renseignez `GEMINI_API_KEY` (une [clé gratuite sur Google AI Studio](https://aistudio.google.com/apikey) suffit).

> La version gratuite de Gemini permet environ 20 requêtes par jour et par modèle. Wasf décrit 8 créneaux par requête, si bien qu'un extrait de 2 minutes coûte 2 requêtes. Quand le quota est épuisé, il passe tout seul à un modèle « lite ».

### 6. Lancer Wasf

```powershell
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --port 8000      # Linux/macOS : ../.venv/bin/python -m uvicorn …
```

Ouvrez <http://localhost:8000>. `Ctrl+C` dans le terminal arrête le serveur ; pour le relancer plus tard, il suffit de refaire l'étape 6.

### 7. Premier essai

**Tableau de bord → « Essayer le clip d'exemple » → Lancer l'analyse → Éditeur → Valider → Export.**

> À la première analyse, le modèle Whisper `small` (~460 Mo) est téléchargé une seule fois dans `models/`.

### Installation rapide sous Linux et macOS

Ce sont les mêmes étapes, raccourcies grâce au `Makefile` du dépôt :

```bash
# 1. Outils
#    Debian 12 / Ubuntu 22.04 : sudo apt install git python3.11 python3.11-venv ffmpeg espeak-ng
#    Ubuntu 24.04 (pas de Python 3.11 par défaut) : sudo add-apt-repository ppa:deadsnakes/ppa, puis la ligne ci-dessus
#    macOS (Homebrew) : brew install git python@3.11 node ffmpeg espeak-ng
#    Node.js 22 : le paquet apt « nodejs » est trop ancien, passez par https://nodejs.org ou nvm (nvm install 22)

# 2. Code
git clone https://github.com/LouaySaidani/hackathonjunior.git
cd hackathonjunior

# 3 et 4. Dépendances Python (dans .venv) et interface web
make install
make build

# 5. Configuration (facultatif, voir l'étape 5 ci-dessus)
cp .env.example .env

# 6. Lancement, puis ouvrez http://localhost:8000
make backend
```

Vérifiez les versions avec `python3.11 --version`, `node --version` (22 ou plus) et `ffmpeg -version`.

### En cas de problème

| Message | Solution |
|---|---|
| `ffmpeg` ou `node` n'est pas reconnu | fermez et rouvrez le terminal après l'installation (étape 1) |
| « Frontend non construit » | refaites l'étape 4 |
| le port 8000 est déjà utilisé | lancez avec `--port 8001` et ouvrez <http://localhost:8001> |
| voix remplacée par un bip | pas d'Internet pour la voix edge-tts : installez espeak-ng (voix de secours) |
| `npm ci` échoue ou Vite refuse de démarrer | Node.js trop ancien : installez la version 22 ou plus |
| `python3.11: command not found` (Linux) | Python 3.11 n'est pas installé : voir l'[installation rapide](#installation-rapide-sous-linux-et-macos) |

## Utilisation

### Parcours complet : de la vidéo au film audiodécrit

1. **Nouveau projet** : importez la vidéo, cochez le consentement, choisissez la langue de description.
2. **Analyse → Lancer l'analyse** : silences, créneaux, scores ML et brouillons Gemini (de 30 s à 2 min).
3. **Éditeur** : indiquez votre nom, relisez chaque ligne et cliquez sur Valider. Au clavier, J et K passent d'une ligne à l'autre, V valide et X rejette. Une fois la relecture faite, « Tout valider » traite le reste d'un coup. Un brouillon non validé ne sera jamais lu à voix haute.
4. **Export → Générer les voix des lignes validées → Générer l'export**, puis téléchargez `film_audiodecrit.mp4`.

### Vidéos pour tester

```bash
bash scripts/get_test_videos.sh     # 4 extraits de films libres de la Blender Foundation (CC-BY) dans videos_test/
```

| Vidéo | Durée | Intérêt |
|---|---|---|
| `05_sintel_bande_annonce.mp4` | 52 s | premier essai, environ 1 requête Gemini |
| `04_caminandes_llama_drama.mp4` | 1 min 30 | animation comique sans dialogue |
| `01_tears_of_steel_dialogue.mp4` | 2 min 30 | prises de vue réelles, dialogues et silences (celle des captures) |
| `03_spring_sans_dialogue.mp4` | 2 min 30 | aucun dialogue : découpage en créneaux de 10 s |

Ces vidéos sont sous licence CC-BY : vous pouvez les montrer en public en citant l'œuvre et la Blender Foundation (les crédits sont dans `videos_test/CREDITS.md`). Pour comparer avec de vraies audiodescriptions humaines, prenez plutôt les 13 vidéos de test QuerYD que télécharge `python ml/run_all.py` (voir [ml/README.md](../ml/README.md)).

## Configuration

Toutes les variables sont documentées dans [`.env.example`](../.env.example).

| Variable | Défaut | Rôle |
|---|---|---|
| `ASR_PROVIDER` | `auto` | `whisper` · `demo` · `auto` (whisper, repli demo signalé) |
| `WHISPER_MODEL` | `small` | Taille faster-whisper **ou identifiant HF** d'un modèle CTranslate2 (ex. fine-tune tunisien) |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `cpu` / `int8` | `cuda` / `float16` sur carte graphique NVIDIA |
| `VLM_PROVIDER` | `auto` | `gemini` · `openai` · `demo` · `auto` (selon les clés présentes) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | — / `gemini-3.6-flash` | Fournisseur Gemini |
| `GEMINI_FALLBACK_MODELS` / `VLM_BATCH_SIZE` | `gemini-3.5-flash-lite,gemini-flash-lite-latest` / `8` | Modèles de secours quand le quota du jour est épuisé ; créneaux décrits par requête |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | — / OpenAI / `gpt-4o-mini` | Tout serveur compatible OpenAI |
| `TTS_PROVIDER` | `auto` | `edge` → `espeak` → `demo` |
| `TTS_VOICE_FR` / `_AR` | Denise / Reem (ar-TN) | Voix |
| `VAD_ENGINE` | `silero` | `silero` · `webrtc` |
| `MIN_GAP_SECONDS` / `GAP_PADDING_SECONDS` | `1.5` / `0.25` | Silences exploitables |
| `MAX_SLOT_SECONDS` | `10` | Longueur maximale d'un créneau (les longs silences sont découpés) ; `0` = pas de découpage |
| `CONFIDENCE_THRESHOLD` | `0.6` | En dessous : « À relire » |
| `DUCK_VOLUME` | `0.25` | Niveau de la bande originale pendant l'AD |
| `GAP_SELECTION` | `auto` | `auto` (modèle ML s'il est entraîné, sinon tous les silences) · `model` · `all` |
| `GAP_SCORE_THRESHOLD` / `GAP_MODEL_PATH` | `0` (seuil appris) / `ml/artifacts/gap_scorer.joblib` | Sélection ML des silences |
| `MAX_UPLOAD_MB`, `SEED_SAMPLE`, `DATA_DIR`, `MODELS_DIR` | `500`, `true`, `./data`, `./models` | Stockage |
| `SAMPLE_VIDEO` / `SAMPLE_TITLE` | `samples/les_ephemeres.mp4` / « Exemple — Les éphémères (extrait, CC BY-NC) » | Vidéo du projet d'exemple. Une vidéo locale peut aller dans `samples/local/` (ignoré par git). En DEMO MODE, une transcription et un script de référence sont utilisés s'ils sont fournis à côté de la vidéo (`<nom>.transcript.json`, `<nom>.script.json`) |

## Développement

Après l'installation ci-dessus :

```powershell
.venv\Scripts\python -m pip install -r backend\requirements-dev.txt     # outils de test et de lint
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000    # rechargement automatique du serveur
```

Pour modifier l'interface avec rechargement à chaud : `cd frontend` puis `npm run dev`, et ouvrez <http://localhost:5173> (les appels `/api` sont relayés vers le port 8000).

## Tests

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q     # 49 tests : silences/VAD réel, créneaux, ajustement, VTT/TTML/crédits, fournisseurs (HTTP simulé), quota Gemini, sélection ML, parcours API complet, migrations
..\.venv\Scripts\ruff check .            # lint
cd ..\frontend
npm run build
```

- Le notebook [`notebooks/pipeline_demo.ipynb`](../notebooks/pipeline_demo.ipynb) exécute le pipeline de bout en bout en DEMO MODE (vérifié en CI).
- Audit d'accessibilité Lighthouse : 100/100 sur le tableau de bord, le nouveau projet, l'analyse, l'éditeur, l'export et les retours.
