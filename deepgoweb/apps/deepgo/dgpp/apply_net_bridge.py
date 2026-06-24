#!/usr/bin/env python3
"""Fast homology-bridged Net-KNN at inference — index lookup, no STRING read.

`build_net_bridge.py` reads the whole 6.1 GB STRING corpus per run (~45 min) — fine
for an offline benchmark, hopeless for a webservice. The fix exploits that the
bridge is separable:

    net_bridge(q) = Σ_h  homology_weight(q,h) · net(h)

where `net(h)` (train protein h's STRING-neighbour label vote) is **fixed and
pre-t0**. So precompute `net(h)` for every train STRING node ONCE
(`build_net_component.py --queries <train nodes>` → `train_net_index.tsv`), then at
query time the bridge is just: DIAMOND `q → h` + a dict lookup of the precomputed
vote. No STRING files touched per request → milliseconds instead of minutes.

For a webservice the query is a novel sequence (not a STRING node), so the bridge
is the only — and correct — way to get a `net` signal; the hold-out benchmark shows
it recovers ~100 % of direct STRING (`RESULTS.md`).

Inputs:
  --train-net   train_net_index.tsv  (homolog_accession\\tterm\\tscore) — precomputed
  --diamond     m8 of queries vs the train DB: qseqid sseqid bitscore [pident]
Output: protein\\tterm\\tscore  (per-protein max-normalised), identical in form to
the `net`/`net_union` component so it drops straight into the integrator.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict


def log(m):
    print(f'[{time.strftime("%H:%M:%S")}] {m}', file=sys.stderr, flush=True)


def load_train_net(path):
    """homolog accession -> list[(term, score)] (the precomputed neighbour vote)."""
    idx = defaultdict(list)
    with open(path) as fh:
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 3:
                try:
                    idx[p[0]].append((p[1], float(p[2])))
                except ValueError:
                    pass
    return idx


def load_diamond(path, want=None):
    """query -> list[(homolog, bitscore)]."""
    hom = defaultdict(list)
    with open(path) as fh:
        for line in fh:
            c = line.rstrip('\n').split('\t')
            if len(c) < 3 or c[1] == c[0]:
                continue
            if want is not None and c[1] not in want:
                continue
            try:
                hom[c[0]].append((c[1], float(c[2])))
            except ValueError:
                pass
    return hom


def bridge(train_net, diamond_hom, topk_homologs=5, min_score=0.01):
    """Yield (protein, term, score) rows for the homology-bridged net component."""
    for q, hs in diamond_hom.items():
        hs = sorted(hs, key=lambda x: -x[1])
        # only homologs we have a precomputed vote for
        hs = [(h, b) for h, b in hs if h in train_net][:topk_homologs]
        if not hs:
            continue
        mx_b = hs[0][1]
        vote = defaultdict(float)
        for h, b in hs:
            w = b / mx_b                      # homology weight, best = 1
            for term, s in train_net[h]:
                vote[term] += w * s
        if not vote:
            continue
        mx = max(vote.values())
        for term, v in vote.items():
            sc = v / mx
            if sc >= min_score:
                yield q, term, sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-net', required=True)
    ap.add_argument('--diamond', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--topk-homologs', type=int, default=5)
    ap.add_argument('--min-score', type=float, default=0.01)
    args = ap.parse_args()

    t0 = time.time()
    train_net = load_train_net(args.train_net)
    log(f'train_net index: {len(train_net):,} homolog nodes ({time.time()-t0:.0f}s)')
    diamond_hom = load_diamond(args.diamond, want=set(train_net))
    log(f'queries with a precomputed homolog: {len(diamond_hom):,}')

    n = 0
    with open(args.out, 'w') as out:
        for q, term, sc in bridge(train_net, diamond_hom,
                                  args.topk_homologs, args.min_score):
            out.write(f'{q}\t{term}\t{sc:.4f}\n')
            n += 1
    log(f'done: {n:,} rows -> {args.out}  ({time.time()-t0:.0f}s total)')


if __name__ == '__main__':
    main()
