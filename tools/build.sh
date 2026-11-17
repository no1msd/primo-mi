#!/bin/sh
# Assemble the PRIMO program around the exported network and wrap it as a tape image.
#   tools/build.sh [<network directory> [<output.ptp>]]
# Intermediate files (mi.bin, mi.map) go to build/asm.
set -e
cd "$(dirname "$0")/.."
MODEL=${1:-mi}
OUT=${2:-MI.ptp}
W=build/asm
mkdir -p $W
z88dk-z80asm -b -m -I$MODEL -o$W/mi.bin z80/mi.asm
sym() { grep -i "^$1 " $W/mi.map | sed 's/.*= *\$\([0-9A-Fa-f]*\).*/\1/'; }
END=$(sym image_end)
LIMIT=$(sym WORK)        # first address the running program uses for itself
echo "image: $(stat -c %s $W/mi.bin) bytes, \$4400-\$$END (limit \$$LIMIT)"
[ $((0x$END)) -le $((0x$LIMIT)) ] || { echo "image too large"; exit 1; }
z88dk-appmake +primo -b $W/mi.bin -o $W/raw.ptp -t ptp -n MI >/dev/null
python3 -I tools/fixptp.py $W/raw.ptp "$OUT"
echo "wrote $OUT ($(stat -c %s "$OUT") bytes)"
