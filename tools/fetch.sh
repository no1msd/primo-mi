#!/bin/sh
# Download the sources of the ordinary Hungarian sentences, from which the network
# learns what is not a question about BASIC:
#   the Hungarian sentences of Tatoeba (CC BY 2.0 FR, 6 MB)
#   the validation file of TinyStories V2 (27 630 English stories written by GPT-4 in a
#   small child's vocabulary, 22 MB, CDLA-Sharing-1.0); train/translate.py turns them
#   into Hungarian
set -e
cd "$(dirname "$0")/.."
mkdir -p data/raw
[ -f data/raw/hun_sentences.tsv.bz2 ] || curl -L -o data/raw/hun_sentences.tsv.bz2 \
    https://downloads.tatoeba.org/exports/per_language/hun/hun_sentences.tsv.bz2
[ -f data/raw/TinyStoriesV2-GPT4-valid.txt ] || curl -L -o data/raw/TinyStoriesV2-GPT4-valid.txt \
    https://huggingface.co/datasets/roneneldan/TinyStories/resolve/main/TinyStoriesV2-GPT4-valid.txt
ls -l data/raw/hun_sentences.tsv.bz2 data/raw/TinyStoriesV2-GPT4-valid.txt
