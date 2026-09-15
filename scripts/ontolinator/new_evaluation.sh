#!/usr/bin/env bash
# Evaluate the newly trained checkpoint. Any failed command aborts publication.
set -Eeuo pipefail

python diamond_data.py -df data/train_data.pkl -o data/train_data.fa
python diamond_data.py -df data/test_data.pkl -o data/test_data.fa

diamond makedb --in data/train_data.fa -d data/train_data
diamond blastp -d data/train_data.dmnd --more-sensitive -t /tmp \
    -q data/test_data.fa --outfmt 6 qseqid sseqid bitscore \
    -o data/test_diamond.res

python find_alphas.py -o mf
python find_alphas.py -o bp
python find_alphas.py -o cc

mkdir -p results
python evaluate_deepgoplus.py -o mf > results/deepgoplus_mf.txt
python evaluate_deepgoplus.py -o bp > results/deepgoplus_bp.txt
python evaluate_deepgoplus.py -o cc > results/deepgoplus_cc.txt
