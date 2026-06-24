# Celery 5 removed the bare `task` decorator; `shared_task` is the supported
# equivalent and keeps the `@task` usage below unchanged.
from celery import shared_task as task

import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
from deepgo.aminoacids import MAXLEN, to_onehot
from deepgo.utils import Ontology, NAMESPACES
import tensorflow as tf
from subprocess import Popen, PIPE
from deepgo.models import Release

releases = {}

# DeepGO-PlusPlus-Light: a warm CPU-only DGppLight per variant ('mcm' = hierarchy-aware
# CNN). Reused across requests like the DeepGOPlus model above; assets come from
# settings.DGPP_LIGHT (DIAMOND DB + train labels + go-dag + cnn weights).
dgpp_predictors = {}


@task
def predict_functions_dgpp(sequences, variant='mcm'):
    """DeepGO-PlusPlus-Light predictions, in the SAME output shape as
    ``predict_functions``: list[(annots {go_id->score}, sim_prots {prot->bitscore})],
    so the web view / serializer render path is unchanged."""
    global dgpp_predictors
    predictor = dgpp_predictors.get(variant)
    if predictor is None:
        from django.conf import settings
        from deepgo.dgpp import build_predictor
        predictor = build_predictor(settings.DGPP_LIGHT, variant=variant)
        dgpp_predictors[variant] = predictor
    fasta = ''.join('>%d\n%s\n' % (i, s) for i, s in enumerate(sequences))
    # full cpu_lean: every configured CPU component (diam, net, cnn, esm2_knn,
    # proteinfer) -> the cpu_lean integrator; also return the raw per-component preds.
    results, homologs, raw = predictor.predict_cpu_lean(
        fasta, min_score=0.01, topk=5, with_components=True)
    out, components = [], []
    for i in range(len(sequences)):
        key = str(i)
        annots = {p['term']: p['score'] for p in results.get(key, [])}
        sim = {h: b for h, b in homologs.get(key, [])}
        out.append((annots, sim))
        # per-protein, per-component top predictions for the result page
        per = {}
        for comp_name, comp_preds in raw.items():
            top = sorted(comp_preds.get(key, {}).items(), key=lambda x: -x[1])[:15]
            if top:
                label = predictor.COMP_LABELS.get(comp_name, comp_name)
                per[label] = [[g, predictor.names.get(g, ''), round(float(s), 4)] for g, s in top]
        components.append(per)
    return out, components


@task
def predict_functions(release_pk, sequences):
    global releases
    # Load GO and read list of all terms
    if release_pk not in releases:
        rel = Release.objects.get(pk=release_pk)
        if len(releases) == 2: # Remove older version from dictionary
            r_id = min(releases.keys())
            del releases[r_id]
        data_root = rel.data_root
        releases[release_pk] = {}
        releases[release_pk]['rel'] = rel
        releases[release_pk]['go'] = Ontology(f'{data_root}/go.obo', with_rels=True)
        terms_df = pd.read_pickle(f'{data_root}/terms.pkl')
        releases[release_pk]['terms'] = terms_df['terms'].values.flatten()

        # Read known experimental annotations
        releases[release_pk]['annotations'] = {}
        df = pd.read_pickle(f'{data_root}/train_data.pkl')
        annots_col = 'prop_annotations'
        # if annots_col not in df:
            # annots_col = 'annotations'
        for row in df.itertuples():
            releases[release_pk]['annotations'][row.proteins] = set(getattr(row, annots_col))

        # Load CNN model
        releases[release_pk]['model'] = load_model(f'{data_root}/model.h5')

    rel = releases[release_pk]['rel']
    data_root = rel.data_root
    go = releases[release_pk]['go']
    terms = releases[release_pk]['terms']
    annotations = releases[release_pk]['annotations']
    model = releases[release_pk]['model']

    alphas = {NAMESPACES["mf"]: rel.alpha_mf, NAMESPACES["bp"]: rel.alpha_bp, NAMESPACES["cc"]: rel.alpha_cc}
    
    p = Popen(['diamond', 'blastp', '-d', f'{data_root}/train_data', '--more-sensitive',
               '--outfmt', '6', 'qseqid', 'sseqid', 'bitscore'], stdin=PIPE, stdout=PIPE)
    
    for i in range(len(sequences)):
        p.stdin.write(bytes('>' + str(i) + '\n' + sequences[i] + '\n', encoding='utf8'))
    p.stdin.close()

    diamond_preds = {}
    mapping = {}
    if p.wait() == 0:
        for line in p.stdout:
            it = line.decode('utf8').strip().split()
            prot_id = int(it[0])
            if prot_id not in mapping:
                mapping[prot_id] = {}
            mapping[prot_id][it[1]] = float(it[2])
    for prot_id, sim_prots in mapping.items():
        annots = {}
        allgos = set()
        total_score = 0.0
        for p_id, score in sim_prots.items():
            allgos |= annotations[p_id]
            total_score += score
        allgos = list(sorted(allgos))
        sim = np.zeros(len(allgos), dtype=np.float32)
        for j, go_id in enumerate(allgos):
            s = 0.0
            for p_id, score in sim_prots.items():
                if go_id in annotations[p_id]:
                    s += score
            sim[j] = s / total_score
        for go_id, score in zip(allgos, sim):
            annots[go_id] = score
        diamond_preds[prot_id] = annots
    
    
    results = []
    deep_preds = {}
    ids, data = get_data(sequences)
    batch_size = 32
    preds = model.predict(data, batch_size=batch_size)
    assert preds.shape[1] == len(terms)
    for i, prot_id in enumerate(ids):
        if prot_id not in deep_preds:
            deep_preds[prot_id] = {}
        for l in range(len(terms)):
            if preds[i, l] >= 0.01: # Filter out very low scores
                if terms[l] not in deep_preds[prot_id]:
                    deep_preds[prot_id][terms[l]] = preds[i, l]
                else:
                    deep_preds[prot_id][terms[l]] = max(
                        deep_preds[prot_id][terms[l]], preds[i, l])
    # Combine diamond preds and deepgo
    for prot_id in range(len(sequences)):
        annots = {}
        sim_prots = {}
        if prot_id in mapping:
            sim_prots = mapping[prot_id]
        if prot_id in diamond_preds:
            for go_id, score in diamond_preds[prot_id].items():
                annots[go_id] = score * alphas[go.get_namespace(go_id)]
                # annots[go_id] = score * 0.5
        for go_id, score in deep_preds[prot_id].items():
            if go_id in annots:
                annots[go_id] += (1 - alphas[go.get_namespace(go_id)]) * score
                # annots[go_id] += 0.5 * score
            else:
                annots[go_id] = (1 - alphas[go.get_namespace(go_id)]) * score
                # annots[go_id] = 0.5 * score
        # Propagate scores with ontology structure
        gos = list(annots.keys())
        for go_id in gos:
            for g_id in go.get_anchestors(go_id):
                if g_id in annots:
                    annots[g_id] = max(annots[g_id], annots[go_id])
                else:
                    annots[g_id] = annots[go_id]

        results.append((annots, sim_prots))
        
    return results

def get_data(sequences):
    pred_seqs = []
    ids = []
    for i, seq in enumerate(sequences):
        if len(seq) > MAXLEN:
            st = 0
            while st < len(seq):
                pred_seqs.append(seq[st: st + MAXLEN])
                ids.append(i)
                st += MAXLEN - 128
        else:
            pred_seqs.append(seq)
            ids.append(i)
    n = len(pred_seqs)
    data = np.zeros((n, MAXLEN, 21), dtype=np.float32)
    
    for i in range(n):
        seq = pred_seqs[i]
        data[i, :, :] = to_onehot(seq)
    return ids, data
