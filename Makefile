# PRIMO MI: a neural network for the Microkey PRIMO A-64 that answers questions
# about the machine's BASIC.
#
#   make            MI.ptp, the tape, from z80/mi.asm and mi/     (needs z88dk, python3)
#   make emu        build the headless PrimGO driver              (needs go, git)
#   make check      run MI.ptp in the emulator: type questions on the PRIMO's keyboard
#                   and compare the answers with the Python reference
#   make kbcheck    try every BASIC example of the answers on the emulated PRIMO
#   make media      screenshots and a video of the emulated PRIMO (needs ffmpeg)
#
# Training (needs a GPU and a Python with PyTorch and transformers; TRAIN names it):
#   make data       download and prepare ordinary Hungarian sentences
#   make train      train the network, write build/mi.pt
#   make model      export it into mi/ and test it on the held-out questions

PY     = python3
TRAIN  = .venv/bin/python

all: MI.ptp

# the assembler's map and binary are needed by `make check`, so they are the real target
MI.ptp: build/asm/mi.map
build/asm/mi.map: z80/mi.asm $(wildcard mi/*) tools/build.sh tools/fixptp.py
	sh tools/build.sh mi MI.ptp

emu: build/primo-headless
build/primo-headless: tools/emu/headless.go tools/emu/setup.sh
	sh tools/emu/setup.sh

check: MI.ptp build/primo-headless
	$(PY) tools/check_helper.py --dir mi --ptp MI.ptp --questions 300

kbcheck: build/primo-headless
	$(PY) tools/kbcheck.py

media: MI.ptp build/primo-headless
	sh tools/emu/record.sh

data: data/work/stories.txt
data/work/stories.txt: train/prep.py train/translate.py tools/fetch.sh
	sh tools/fetch.sh
	$(TRAIN) train/translate.py --stories 30000
	$(PY) train/prep.py

train: data/work/stories.txt
	$(TRAIN) train/train_helper.py --name mi --buckets 1024 --dim 64

model:
	$(TRAIN) train/export_helper.py --name mi --out mi --check
	$(TRAIN) train/eval_helper.py --dir mi

clean:
	rm -rf build/asm MI.ptp

.PHONY: all emu check kbcheck media data train model clean
