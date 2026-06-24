#!/usr/bin/env python3
"""DeepGO-PlusPlus-Light inference core — CPU-only, no GPU, no STRING scan.

Vendored into DeepGOWeb from the GSPA `deepgo-plusplus` project (gspa rev ffb10d6,
`deepgo-plusplus/service/predict.py`).  It is self-contained: the default (fast)
path needs only the `diamond` binary plus the stdlib — no numpy, no torch — so it
embeds cleanly in the warm Celery worker (see ``deepgo.tasks.predict_functions_dgpp``).

A single DIAMOND search of the query against the pre-t0 train DB powers both
components of the strictly-no-GPU model:

  * `diam`      — BLAST-KNN: vote each homolog's pre-t0 GO labels (bit-score weighted).
  * `net_union` — homology-bridged Net-KNN: vote each homolog's *precomputed* STRING-
                  neighbour label vector (`train_net_index.tsv`). No STRING files are
                  read at request time (see apply_net_bridge.py) — ~ms.

Optionally (`interpro=True`) it shells out to InterProScan, and (`cnn=True`) it runs a
saved CPU 1D-CNN for orphan proteins with no homolog.  Components are propagated to GO
ancestors (max) and combined by the frozen per-aspect logistic integrator — the *same*
math as the offline `run_deepgo_plusplus` sidecar.

The only change from the GSPA copy is import wiring (sibling modules in this package
instead of ``../pipeline``) and the extra ``predict_full`` method, which returns the
top DIAMOND homologs alongside the predictions so DeepGOWeb can show the "similar
proteins" table without a second DIAMOND run.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from apply_net_bridge import load_train_net, bridge  # noqa: E402

NS_OF_ROOT = {'GO:0003674': 'MF', 'GO:0008150': 'BP', 'GO:0005575': 'CC'}


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


def aspect_of_terms(anc):
    out = {}
    for t, ancestors in anc.items():
        for root, ns in NS_OF_ROOT.items():
            if root in ancestors:
                out[t] = ns
                break
    return out


def load_grouped(path, has_header=True):
    """protein -> set(term) from a 2+ column TSV (e.g. train_terms.tsv)."""
    out = defaultdict(set)
    with open(path) as fh:
        if has_header:
            next(fh, None)
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2:
                out[p[0]].add(p[1])
    return out


def load_obo_names(path):
    names = {}
    if not path or not os.path.exists(path):
        return names
    cur = None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line == '[Term]':
                cur = None
            elif line.startswith('id: GO:'):
                cur = line[4:].strip()
            elif line.startswith('name:') and cur:
                names[cur] = line[6:].strip()
    return names


def read_fasta(text):
    name, seq = None, []
    for line in text.splitlines():
        if line.startswith('>'):
            if name:
                yield name, ''.join(seq)
            name = line[1:].split()[0].strip()
            seq = []
        else:
            seq.append(line.strip())
    if name:
        yield name, ''.join(seq)


class DGppLight:
    def __init__(self, *, models, train_net_index, train_terms,
                 dag, diamond_db, obo=None, diamond_bin='diamond',
                 interproscan=None, cnn_model=None, threads=8):
        """models: dict {(interpro: bool, cnn: bool) -> path to frozen JSON}.
        Only the combinations whose model file exists are served."""
        import json
        self.anc = load_dag(dag)
        self.aspect_of = aspect_of_terms(self.anc)
        self.train_net = load_train_net(train_net_index)
        self.train_terms = load_grouped(train_terms)
        self.models = {k: json.load(open(p)) for k, p in models.items()
                       if p and os.path.exists(p)}
        self.names = load_obo_names(obo)
        self.diamond_db = diamond_db
        self.diamond_bin = diamond_bin
        self.interproscan = interproscan
        self.cnn_model = cnn_model if cnn_model and os.path.exists(cnn_model) else None
        self.threads = threads

    # ---- components (all from one DIAMOND search) ----
    def _diamond(self, fasta_path):
        out = fasta_path + '.m8'
        subprocess.run([self.diamond_bin, 'blastp', '-d', self.diamond_db,
                        '-q', fasta_path, '-o', out, '--outfmt', '6',
                        'qseqid', 'sseqid', 'bitscore', 'pident',
                        '--very-sensitive', '-k', '25', '--evalue', '1e-3',
                        '-p', str(self.threads), '--quiet'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hom = defaultdict(list)
        with open(out) as fh:
            for line in fh:
                c = line.rstrip('\n').split('\t')
                if len(c) >= 3 and c[1] != c[0]:
                    try:
                        hom[c[0]].append((c[1], float(c[2])))
                    except ValueError:
                        pass
        os.unlink(out)
        return hom

    def _diam_component(self, hom, topk=5, min_score=0.01):
        """BLAST-KNN: bit-score-weighted vote of homolog GO labels."""
        comp = {}
        for q, hs in hom.items():
            hs = sorted(hs, key=lambda x: -x[1])[:topk]
            if not hs:
                continue
            mx = hs[0][1]
            vote = defaultdict(float)
            for h, b in hs:
                w = b / mx
                for t in self.train_terms.get(h, ()):
                    vote[t] += w
            if not vote:
                continue
            vmx = max(vote.values())
            comp[q] = {t: v / vmx for t, v in vote.items() if v / vmx >= min_score}
        return comp

    def _net_component(self, hom, topk=5, min_score=0.01):
        comp = defaultdict(dict)
        for q, t, s in bridge(self.train_net, hom, topk, min_score):
            comp[q][t] = s
        return comp

    def _interpro_component(self, fasta_path):
        """Optional: InterProScan --goterms -> per-protein GO set (score 1.0)."""
        if not self.interproscan:
            raise RuntimeError('interpro=true but no InterProScan configured')
        out = fasta_path + '.ipr.tsv'
        subprocess.run([self.interproscan, '-i', fasta_path, '-f', 'tsv',
                        '--goterms', '-o', out, '-cpu', str(self.threads)],
                       check=True)
        comp = defaultdict(dict)
        with open(out) as fh:
            for line in fh:
                col = line.rstrip('\n').split('\t')
                if len(col) > 13 and col[13].startswith('GO:'):
                    for go in col[13].replace('|', '(').split('('):
                        go = go.strip()
                        if go.startswith('GO:'):
                            comp[col[0]][go] = 1.0
        os.unlink(out)
        return comp

    def _cnn_component(self, fasta_path, min_score=0.01):
        """Optional: the CPU 1D-CNN (build_cnn_component) loaded from saved weights.
        Provides sequence-based predictions for orphan proteins with no homolog."""
        if not self.cnn_model:
            raise RuntimeError('cnn=true but no CNN weights configured (DGPP_CNN_MODEL)')
        import torch  # heavy; imported only when the CNN path is used
        import build_cnn_component as bcc
        ckpt = torch.load(self.cnn_model, map_location='cpu', weights_only=False)
        vocab, max_len = ckpt['vocab'], ckpt['max_len']
        model = bcc.build_cnn(len(vocab))
        model.load_state_dict(ckpt['state_dict'])
        model.eval()
        out = fasta_path + '.cnn.tsv'
        bcc.predict(model, vocab, max_len, fasta_path, out, min_score, torch)
        comp = defaultdict(dict)
        with open(out) as fh:
            for line in fh:
                p = line.rstrip('\n').split('\t')
                if len(p) >= 3:
                    comp[p[0]][p[1]] = float(p[2])
        os.unlink(out)
        return comp

    def _propagate(self, comp):
        """protein -> {term -> score} propagated to ancestors (max)."""
        out = {}
        for q, terms in comp.items():
            d = {}
            for t, s in terms.items():
                for a in self.anc.get(t, (t,)):
                    if a in self.aspect_of and s > d.get(a, -1.0):
                        d[a] = s
            out[q] = d
        return out

    def _apply(self, model, comps, min_score):
        """Mirror run_deepgo_plusplus: per-aspect sigmoid(b + Σ coef·(x-mean)/scale)."""
        components = model['components']
        aspect_models = model['aspects']
        proteins = set().union(*[set(c) for c in comps.values()]) if comps else set()
        results = {}
        for q in proteins:
            preds = []
            for aspect, am in aspect_models.items():
                coef, mean, scale, b = am['coef'], am['mean'], am['scale'], am['intercept']
                cand = set()
                for c in components:
                    for t in comps.get(c, {}).get(q, ()):
                        if self.aspect_of.get(t) == aspect:
                            cand.add(t)
                for t in cand:
                    if t in NS_OF_ROOT:        # drop the always-true aspect roots
                        continue
                    z = b
                    for i, c in enumerate(components):
                        x = comps.get(c, {}).get(q, {}).get(t, 0.0)
                        sc = scale[i] if scale[i] else 1.0
                        z += coef[i] * (x - mean[i]) / sc
                    s = 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))
                    if s >= min_score:
                        preds.append({'term': t, 'name': self.names.get(t, ''),
                                      'aspect': aspect, 'score': round(s, 4)})
            preds.sort(key=lambda p: -p['score'])
            results[q] = preds
        return results

    def available(self):
        """Sorted list of served (interpro, cnn) combinations."""
        return sorted(self.models)

    def predict_full(self, fasta_text, *, interpro=False, cnn=False, topk=5, min_score=0.1):
        """Like ``predict`` but also returns the top DIAMOND homologs per query so the
        caller can render a "similar proteins" table without a second DIAMOND run.

        Returns ``(results, homologs)`` where ``results`` maps protein -> list of
        ``{term, name, aspect, score}`` and ``homologs`` maps protein -> list of
        ``(homolog_id, bitscore)`` (best first, truncated to ``topk``)."""
        key = (interpro, cnn)
        if key not in self.models:
            raise RuntimeError(f'no model for interpro={interpro}, cnn={cnn} '
                               f'(available: {self.available()})')
        model = self.models[key]
        with tempfile.NamedTemporaryFile('w', suffix='.faa', delete=False) as fh:
            fh.write(fasta_text)
            path = fh.name
        try:
            hom = self._diamond(path)
            comps = {'diam': self._propagate(self._diam_component(hom, topk)),
                     'net_union': self._propagate(self._net_component(hom, topk))}
            if interpro:
                comps['interpro'] = self._propagate(self._interpro_component(path))
            if cnn:
                comps['cnn'] = self._propagate(self._cnn_component(path))
            results = self._apply(model, comps, min_score)
            homologs = {q: sorted(hs, key=lambda x: -x[1])[:topk]
                        for q, hs in hom.items()}
            return results, homologs
        finally:
            os.unlink(path)

    def predict(self, fasta_text, *, interpro=False, cnn=False, topk=5, min_score=0.1):
        return self.predict_full(fasta_text, interpro=interpro, cnn=cnn,
                                 topk=topk, min_score=min_score)[0]
