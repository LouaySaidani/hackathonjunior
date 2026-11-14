#!/usr/bin/env bash
# Regenerates backend/tests/fixtures/sample_medina.mp4, the synthetic CC0 clip used by the tests and the notebook.
# Requires espeak-ng and ffmpeg on the PATH.
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/backend/tests/fixtures"
TMP="$(mktemp -d)"
espeak-ng -v fr+f3 -s 150 -w "$TMP/l1.wav" 'Ahla bik ! Bienvenue à Sidi Bou Saïd.'
espeak-ng -v fr+m3 -s 150 -w "$TMP/l2.wav" 'Le café des Nattes est juste en haut de la rue.'
espeak-ng -v fr+f3 -s 150 -w "$TMP/l3.wav" 'Deux thés à la menthe, s il vous plaît.'
espeak-ng -v fr+m3 -s 150 -w "$TMP/l4.wav" 'Merci beaucoup. À demain, inchallah.'
B="drawbox=t=fill"
ffmpeg -y -v error \
 -f lavfi -i "color=c=0xEFE9DC:s=854x480:r=24:d=9" -f lavfi -i "color=c=0xC9853A:s=854x480:r=24:d=9" \
 -f lavfi -i "color=c=0x123A3A:s=854x480:r=24:d=9" -f lavfi -i "color=c=0x0B1A3A:s=854x480:r=24:d=9" \
 -i "$TMP/l1.wav" -i "$TMP/l2.wav" -i "$TMP/l3.wav" -i "$TMP/l4.wav" \
 -f lavfi -i "color=c=0xF3EEE6:s=42x165:r=24:d=9" \
 -filter_complex "\
[0:v]$B:x=357:y=110:w=140:h=320:color=0x1F5FA8,$B:x=372:y=125:w=110:h=290:color=0x2A6FBF,$B:x=390:y=170:w=8:h=8:color=0x101010,$B:x=456:y=170:w=8:h=8:color=0x101010,$B:x=390:y=260:w=8:h=8:color=0x101010,$B:x=456:y=260:w=8:h=8:color=0x101010,$B:x=390:y=350:w=8:h=8:color=0x101010,$B:x=456:y=350:w=8:h=8:color=0x101010,$B:x=600:y=150:w=90:h=90:color=0x1F5FA8,fade=t=out:st=8.4:d=0.6[a];\
[1:v]$B:x=0:y=380:w=854:h=100:color=0x8A5A2B,$B:x=0:y=0:w=854:h=60:color=0xF2B26B[bb];[bb][8:v]overlay=x='40+t*85':y=215,fade=t=in:st=0:d=0.6[b];\
[2:v]$B:x=397:y=40:w=60:h=40:color=0xF4C542,$B:x=280:y=300:w=300:h=24:color=0x6B3E1E,$B:x=410:y=324:w=30:h=120:color=0x6B3E1E,$B:x=360:y=262:w=26:h=38:color=0xD9F2E6:enable='gte(t,5)',$B:x=470:y=262:w=26:h=38:color=0xD9F2E6:enable='gte(t,5)',fade=t=out:st=8.2:d=0.8[c];\
[3:v]$B:x=120:y=60:w=4:h=4:color=white,$B:x=300:y=110:w=4:h=4:color=white,$B:x=520:y=50:w=4:h=4:color=white,$B:x=700:y=130:w=4:h=4:color=white,$B:x=780:y=40:w=4:h=4:color=white,$B:x=430:y=180:w=4:h=4:color=white,$B:x=0:y=360:w=854:h=120:color=0x05070D,$B:x=200:y=320:w=160:h=40:color=0x05070D,$B:x=560:y=300:w=120:h=60:color=0x05070D,fade=t=in:st=0:d=0.8[d];\
[a][b][c][d]concat=n=4:v=1:a=0,format=yuv420p[v];\
[4:a]adelay=3000:all=1[s1];[5:a]adelay=12000:all=1[s2];[6:a]adelay=21000:all=1[s3];[7:a]adelay=30000:all=1[s4];\
anullsrc=r=22050:cl=mono,atrim=0:36[sil];[sil][s1][s2][s3][s4]amix=inputs=5:duration=first:normalize=0,aresample=44100[aud]" \
 -map "[v]" -map "[aud]" -c:v libx264 -preset slow -crf 28 -c:a aac -b:a 64k -ac 1 -movflags +faststart -t 36 \
 "$OUT/sample_medina.mp4"
rm -rf "$TMP"
echo "OK -> $OUT/sample_medina.mp4"
