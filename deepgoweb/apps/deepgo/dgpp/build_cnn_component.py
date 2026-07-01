#!/usr/bin/env python3
"""DG++-Light `cnn` component — a CPU 1D-CNN over sequence (DeepGOCNN-style).

DeepGO-PlusPlus's strongest single components are GPU PLM heads. DG++-Light cannot
use them, so we *replace* the PLM signal with the canonical no-GPU sequence model:
a 1D convolutional network over the raw amino-acid sequence (the DeepGOPlus /
DeepGOCNN design), trainable and runnable **on CPU**. It complements the other
no-GPU channels (DIAMOND homology, FoldSeek structure, InterProScan domains,
STRING Net-KNN).

Architecture (compact, CPU-friendly):
  embed(21 AA + pad -> 16) -> parallel Conv1d (kernels 8/16/24/32, 128 filters
  each) -> global max-pool over length -> concat (512) -> dense 512 -> ReLU ->
  dropout -> linear to the GO vocabulary. BCEWithLogitsLoss with per-term
  frequency pos-weight (frequency weighting helped CAFA6 #4; IA-weighting hurt).

Targets are the pre-t0 `train_terms.tsv` labels, **propagated to GO ancestors**
(true-path); the output vocabulary is terms with propagated train frequency
>= --min-freq (keeps the head tractable on CPU). Predictions are written as
`protein<TAB>term<TAB>score`; the integrator re-propagates to ancestors (max), so
emitting vocabulary-term scores is sufficient.

Usage:
  python build_cnn_component.py \
      --train-fasta train.fasta --train-terms train_terms.tsv \
      --dag go-dag.tsv --test-fasta all_test.fasta --out cnn.tsv \
      --min-freq 50 --max-len 1000 --epochs 15 --batch 64 --threads 56
"""
from __future__ import annotations

import argparse
import gzip
import sys
import time
from collections import defaultdict

import numpy as np

AA = 'ACDEFGHIKLMNPQRSTVWY'
AA_IDX = {c: i + 1 for i, c in enumerate(AA)}  # 0 = pad/unknown
NS_OF_ROOT = {'GO:0003674': 'MF', 'GO:0008150': 'BP', 'GO:0005575': 'CC'}


def log(m):
    print(f'[{time.strftime("%H:%M:%S")}] {m}', file=sys.stderr, flush=True)


def opn(path):
    return gzip.open(path, 'rt') if path.endswith('.gz') else open(path)


def read_fasta(path):
    name, seq = None, []
    with opn(path) as fh:
        for line in fh:
            if line.startswith('>'):
                if name:
                    yield name, ''.join(seq)
                name = line[1:].split()[0].strip()
                seq = []
            else:
                seq.append(line.strip())
    if name:
        yield name, ''.join(seq)


def load_dag(path):
    anc = defaultdict(set)
    with open(path) as fh:
        for line in fh:
            if line.startswith('#'):
                continue
            c, _, a = line.rstrip('\n').partition('\t')
            if c and a:
                anc[c].add(a)
    for c in list(anc):
        anc[c].add(c)
    return anc


def encode(seq, max_len):
    x = np.zeros(max_len, dtype=np.int64)
    for i, c in enumerate(seq[:max_len]):
        x[i] = AA_IDX.get(c, 0)
    return x


def build_cnn(vocab_size):
    """The DeepGOCNN-style network (defined at module scope so a saved model can
    be reconstructed for apply-without-retrain)."""
    import torch.nn as nn

    class CNN(nn.Module):
        def __init__(self, vocab_size):
            super().__init__()
            self.emb = nn.Embedding(len(AA) + 1, 16, padding_idx=0)
            self.convs = nn.ModuleList([
                nn.Conv1d(16, 128, k, padding=k // 2) for k in (8, 16, 24, 32)
            ])
            self.fc1 = nn.Linear(128 * 4, 512)
            self.drop = nn.Dropout(0.3)
            self.out = nn.Linear(512, vocab_size)

        def forward(self, x):
            import torch
            e = self.emb(x).transpose(1, 2)          # B, 16, L
            pooled = [torch.relu(c(e)).max(dim=2).values for c in self.convs]
            h = torch.cat(pooled, dim=1)             # B, 512
            h = self.drop(torch.relu(self.fc1(h)))
            return self.out(h)                       # logits

    return CNN(vocab_size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train-fasta', help='required unless --load-model')
    ap.add_argument('--train-terms', help='required unless --load-model')
    ap.add_argument('--dag', help='required for training (label propagation)')
    ap.add_argument('--test-fasta', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--min-freq', type=int, default=50)
    ap.add_argument('--max-len', type=int, default=1000)
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--batch', type=int, default=64)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--threads', type=int, default=0)
    ap.add_argument('--min-score', type=float, default=0.01)
    ap.add_argument('--val-frac', type=float, default=0.02)
    ap.add_argument('--patience', type=int, default=4,
                    help='early-stop after N epochs without val improvement (0 = off)')
    ap.add_argument('--save-model', help='save trained weights + vocab to this .pt')
    ap.add_argument('--load-model', help='skip training; load .pt and predict only')
    args = ap.parse_args()

    import torch
    if args.threads:
        torch.set_num_threads(args.threads)
    log(f'torch {torch.__version__}  threads={torch.get_num_threads()}')

    # --- apply-only path: load a saved model and predict, no training ---
    if args.load_model:
        ckpt = torch.load(args.load_model, map_location='cpu', weights_only=False)
        vocab = ckpt['vocab']
        max_len = ckpt['max_len']
        model = build_cnn(len(vocab))
        model.load_state_dict(ckpt['state_dict'])
        model.eval()
        log(f'loaded model {args.load_model}  vocab={len(vocab):,} max_len={max_len}')
        predict(model, vocab, max_len, args.test_fasta, args.out, args.min_score, torch)
        return

    anc = load_dag(args.dag)

    # train labels, propagated to ancestors
    log('loading + propagating train labels ...')
    prot_terms = defaultdict(set)
    with open(args.train_terms) as fh:
        first = fh.readline().split('\t')
        if first and first[0].strip().lower() not in ('entryid', 'protein', 'accession'):
            fh.seek(0)
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) < 2:
                continue
            prot_terms[p[0]].update(anc.get(p[1], (p[1],)))

    freq = defaultdict(int)
    for ts in prot_terms.values():
        for t in ts:
            freq[t] += 1
    vocab = sorted([t for t, c in freq.items() if c >= args.min_freq
                    and t not in NS_OF_ROOT])
    tidx = {t: i for i, t in enumerate(vocab)}
    log(f'vocab terms (freq>={args.min_freq}): {len(vocab):,}')

    # training tensors (only proteins with a sequence AND >=1 vocab term)
    log('encoding train sequences ...')
    Xtr, Ytr_rows, Ytr_cols = [], [], []
    r = 0
    seqs = {n: s for n, s in read_fasta(args.train_fasta)}
    for p, ts in prot_terms.items():
        s = seqs.get(p)
        if not s:
            continue
        cols = [tidx[t] for t in ts if t in tidx]
        if not cols:
            continue
        Xtr.append(encode(s, args.max_len))
        for c in cols:
            Ytr_rows.append(r); Ytr_cols.append(c)
        r += 1
    Xtr = np.asarray(Xtr, dtype=np.int64)
    log(f'train proteins with seq+labels: {Xtr.shape[0]:,}')
    n = Xtr.shape[0]
    V = len(vocab)
    Y = np.zeros((n, V), dtype=np.float32)
    Y[np.asarray(Ytr_rows), np.asarray(Ytr_cols)] = 1.0

    # per-term frequency pos-weight (clipped); frequency weighting (not IA)
    pos = Y.sum(0)
    pos_weight = np.clip((n - pos) / np.maximum(pos, 1.0), 1.0, 50.0).astype(np.float32)

    # split a tiny validation set
    rng = np.random.RandomState(0)
    perm = rng.permutation(n)
    nval = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:nval], perm[nval:]

    import torch.nn as nn
    dev = torch.device('cpu')
    model = build_cnn(V).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.from_numpy(pos_weight).to(dev))
    Xt = torch.from_numpy(Xtr)
    Yt = torch.from_numpy(Y)

    log(f'training: n={len(tr_idx):,} val={len(val_idx):,} V={V} epochs={args.epochs}')
    import copy
    best_val = float('inf')
    best_state = copy.deepcopy(model.state_dict())
    best_ep = 0
    bad = 0
    for ep in range(args.epochs):
        model.train()
        rng.shuffle(tr_idx)
        tot = 0.0
        for i in range(0, len(tr_idx), args.batch):
            b = tr_idx[i:i + args.batch]
            xb = Xt[b].to(dev); yb = Yt[b].to(dev)
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward(); opt.step()
            tot += float(loss.detach()) * len(b)
        model.eval()
        with torch.no_grad():
            vlogit = model(Xt[val_idx].to(dev))
            vloss = float(lossf(vlogit, Yt[val_idx].to(dev)))
        flag = ''
        if vloss < best_val - 1e-4:
            best_val, best_ep = vloss, ep + 1
            best_state = copy.deepcopy(model.state_dict())
            bad = 0
            flag = ' *best*'
        else:
            bad += 1
        log(f'  epoch {ep+1}/{args.epochs}  train_loss={tot/len(tr_idx):.4f}  val_loss={vloss:.4f}{flag}')
        if args.patience and bad >= args.patience:
            log(f'  early stop (no val improvement for {args.patience} epochs)')
            break

    # predict the test set with the BEST-validation checkpoint (avoid overfit-at-end)
    log(f'restoring best-val model (epoch {best_ep}, val_loss={best_val:.4f})')
    model.load_state_dict(best_state)

    if args.save_model:
        torch.save({'state_dict': model.state_dict(), 'vocab': vocab,
                    'max_len': args.max_len}, args.save_model)
        log(f'saved model -> {args.save_model}')

    predict(model, vocab, args.max_len, args.test_fasta, args.out, args.min_score, torch)


def predict(model, vocab, max_len, test_fasta, out_path, min_score, torch, device='cpu'):
    """Score a FASTA with a (trained or loaded) CNN -> protein<TAB>term<TAB>score."""
    model.to(device)
    model.eval()
    test = list(read_fasta(test_fasta))
    nw = 0
    opn_out = gzip.open(out_path, 'wt') if out_path.endswith('.gz') else open(out_path, 'w')
    with opn_out as out, torch.no_grad():
        for i in range(0, len(test), 256):
            chunk = test[i:i + 256]
            xb = torch.from_numpy(np.stack([encode(s, max_len) for _, s in chunk])).to(device)
            probs = torch.sigmoid(model(xb)).cpu().numpy()
            for (pname, _), row in zip(chunk, probs):
                for c in np.where(row >= min_score)[0]:
                    out.write(f'{pname}\t{vocab[c]}\t{row[c]:.4f}\n')
                    nw += 1
    log(f'wrote {nw:,} predictions -> {out_path}')


if __name__ == '__main__':
    main()
