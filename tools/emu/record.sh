#!/bin/sh
# Screenshots and a video of PRIMO MI running in the headless emulator.
#   media/title.png     the opening screen
#   media/answers.png   after four questions
#   media/mi.mp4        the four questions being typed and answered, in real time
set -e
cd "$(dirname "$0")/../.."
PTP=${1:-MI.ptp}
mkdir -p media build/asm
FIFO=build/asm/video.fifo
rm -f $FIFO && mkfifo $FIFO
ffmpeg -loglevel error -y -f rawvideo -pix_fmt rgb24 -s 256x192 -r 50 -i $FIFO \
    -vf "scale=768:576:flags=neighbor" -r 50 -pix_fmt yuv420p -crf 20 media/mi.mp4 &
python3 - "$PTP" $FIFO <<'PY'
import os, subprocess, sys
sys.path.insert(0, "tools")
import primo
ptp, fifo = sys.argv[1:]
sc = ["wait 150"] + primo.keys("load") + ["press RETURN 4", "wait 1100"] + primo.keys("run") + \
     ["press RETURN 4", "wait 100", "shot media/title.png", "rec on", "wait 100", "speed 5 6"]
for q in ["hogyan törlöm a képernyőt?", "számolj el 25-ig", "ul error in 40", "rajzolj egy kört"]:
    for ch in q:                                    # a child's typing speed
        sc += [c[:-1] + "5" if c.startswith("press") else "wait 6" if c == "wait 3" else c
               for c in primo.keys(ch)]
    sc += ["press RETURN 5", "wait 200"]
sc += ["shot media/answers.png"]
subprocess.run([primo.EMU, "-ptp", ptp, "-scale", "3", "-video", fifo], input="\n".join(sc) + "\n", text=True)
PY
wait
rm -f $FIFO
ls -l media
