#!/usr/bin/env bash
# Download short test extracts of Blender Foundation open movies (CC-BY) into videos_test/.
# Requires curl and ffmpeg. Usage: bash scripts/get_test_videos.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=videos_test
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"
UA="basira-test-videos/1.0 (educational accessibility project)"
W=https://upload.wikimedia.org/wikipedia/commons

# encode <source> <start> <duration> <name>: 480p H.264/AAC extract
encode() {
  if [ -s "$OUT/$4" ]; then echo "déjà présent : $4"; return; fi
  ffmpeg -nostdin -y -v error -ss "$2" -i "$1" -t "$3" -vf "scale=-2:480" \
    -c:v libx264 -preset veryfast -crf 26 -c:a aac -b:a 128k -ac 2 -movflags +faststart "$OUT/$4"
  echo "OK : $4"
}

# fetch <url> <file>: full download (Wikimedia throttles partial streaming)
fetch() { curl -sSL --fail --retry 3 --retry-delay 10 -A "$UA" -o "$TMP/$2" "$1"; }

# Tears of Steel (CC-BY 3.0): the server supports seeking, only the needed part is read
encode https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov 00:00:12 150 01_tears_of_steel_dialogue.mp4
# Spring (CC-BY 4.0), 82 MB
[ -s "$OUT/03_spring_sans_dialogue.mp4" ] || { fetch "$W/a/a5/Spring_-_Blender_Open_Movie.webm" spring.webm; \
  encode "$TMP/spring.webm" 00:00:50 150 03_spring_sans_dialogue.mp4; }
# Caminandes: Llama Drama (CC-BY 3.0), 31 MB
[ -s "$OUT/04_caminandes_llama_drama.mp4" ] || { fetch "$W/d/d0/Caminandes-_Llama_Drama_-_Short_Movie.ogv" caminandes.ogv; \
  encode "$TMP/caminandes.ogv" 0 95 04_caminandes_llama_drama.mp4; }
# Sintel trailer (CC-BY 3.0)
encode https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4 0 60 05_sintel_bande_annonce.mp4

cat > "$OUT/CREDITS.md" <<'EOF'
# Vidéos de test : crédits et licences

Extraits de films libres de la Blender Foundation, sous licence **Creative Commons Attribution (CC-BY)**.
Vous pouvez les utiliser, les modifier (y compris leur ajouter une audiodescription) et les montrer en public,
**à condition de citer l'œuvre et la Blender Foundation** (par exemple dans les crédits de la démo).

| Fichier | Œuvre | Licence | Intérêt pour le test |
|---|---|---|---|
| `01_tears_of_steel_dialogue.mp4` | *Tears of Steel* (2012), © Blender Foundation, mango.blender.org | CC-BY 3.0 | prises de vue réelles, dialogues et silences en alternance |
| `03_spring_sans_dialogue.mp4` | *Spring* (2019), © Blender Animation Studio | CC-BY 4.0 | aucun dialogue : test du découpage en créneaux de 10 s |
| `04_caminandes_llama_drama.mp4` | *Caminandes: Llama Drama* (2013), © Blender Foundation, caminandes.com | CC-BY 3.0 | court, comique, sans dialogue |
| `05_sintel_bande_annonce.mp4` | *Sintel* (bande-annonce, 2010), © Blender Foundation, durian.blender.org | CC-BY 3.0 | très court (1 min) : idéal pour un premier essai |

Extraits recadrés en 480p par `ffmpeg` pour le test de Basira. Sources : download.blender.org et Wikimedia Commons.
EOF
echo "Vidéos prêtes dans $OUT/ (crédits : $OUT/CREDITS.md)"
