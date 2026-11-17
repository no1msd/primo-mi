#!/bin/sh
# Fetch PrimGO (https://github.com/no1msd/primgo, MIT) and build the headless driver around
# its emulation core.  PrimGO's module is not go-gettable, so the driver is built inside it.
set -e
cd "$(dirname "$0")/../.."
PIN=8f132ab1a2cf59967f510f5de4663b5a22528ed3
if [ ! -d third_party/primgo/.git ]; then
    mkdir -p third_party
    git clone -q https://github.com/no1msd/primgo.git third_party/primgo
fi
git -C third_party/primgo checkout -q "$PIN"
mkdir -p third_party/primgo/cmd/headless build
cp tools/emu/headless.go third_party/primgo/cmd/headless/main.go
(cd third_party/primgo && go build -o ../../build/primo-headless ./cmd/headless)
echo "built build/primo-headless"
