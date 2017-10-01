from collections import deque
import pandas as pd
from keras import backend as K
from constants import (
    BIOLOGICAL_PROCESS,
    MOLECULAR_FUNCTION,
    CELLULAR_COMPONENT,
    MAXLEN,
    AACIDS)


def is_ok(seq):
    if len(seq) > MAXLEN:
        return False
    for c in seq:
        if c not in AACIDS:
            return False
    return True


def get_gene_ontology(filename='go.obo'):
    # Reading Gene Ontology from OBO Formatted file
    go = dict()
    obj = None
    with open('data/' + filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line == '[Term]':
                if obj is not None:
                    go[obj['id']] = obj
                obj = dict()
                obj['is_a'] = list()
                obj['part_of'] = list()
                obj['regulates'] = list()
                obj['is_obsolete'] = False
                continue
            elif line == '[Typedef]':
                obj = None
            else:
                if obj is None:
                    continue
                l = line.split(": ")
                if l[0] == 'id':
                    obj['id'] = l[1]
                elif l[0] == 'is_a':
                    obj['is_a'].append(l[1].split(' ! ')[0])
                elif l[0] == 'is_obsolete' and l[1] == 'true':
                    obj['is_obsolete'] = True
                elif l[0] == 'name':
                    obj['name'] = l[1]
    if obj is not None:
        go[obj['id']] = obj
    for go_id in go.keys():
        if go[go_id]['is_obsolete']:
            del go[go_id]
    for go_id, val in go.iteritems():
        if 'children' not in val:
            val['children'] = set()
        for g_id in val['is_a']:
            if g_id in go:
                if 'children' not in go[g_id]:
                    go[g_id]['children'] = set()
                go[g_id]['children'].add(go_id)
    # Rooting
    go['root'] = dict()
    go['root']['is_a'] = []
    go['root']['children'] = [
        BIOLOGICAL_PROCESS, MOLECULAR_FUNCTION, CELLULAR_COMPONENT]
    go[BIOLOGICAL_PROCESS]['is_a'] = ['root']
    go[MOLECULAR_FUNCTION]['is_a'] = ['root']
    go[CELLULAR_COMPONENT]['is_a'] = ['root']

    return go


def get_anchestors(go, go_id):
    go_set = set()
    q = deque()
    q.append(go_id)
    while(len(q) > 0):
        g_id = q.popleft()
        go_set.add(g_id)
        for parent_id in go[g_id]['is_a']:
            if parent_id in go:
                q.append(parent_id)
    return go_set


def get_parents(go, go_id):
    go_set = set()
    for parent_id in go[go_id]['is_a']:
        if parent_id in go:
            go_set.add(parent_id)
    return go_set


def get_go_set(go, go_id):
    go_set = set()
    q = deque()
    q.append(go_id)
    while len(q) > 0:
        g_id = q.popleft()
        go_set.add(g_id)
        for ch_id in go[g_id]['children']:
            q.append(ch_id)
    return go_set


def load_model_weights(model, filepath):
    ''' Name-based weight loading
    Layers that have no matching name are skipped.
    '''
    if hasattr(model, 'flattened_layers'):
        # Support for legacy Sequential/Merge behavior.
        flattened_layers = model.flattened_layers
    else:
        flattened_layers = model.layers

    df = pd.read_pickle(filepath)

    # Reverse index of layer name to list of layers with name.
    index = {}
    for layer in flattened_layers:
        if layer.name:
            index[layer.name] = layer

    # We batch weight value assignments in a single backend call
    # which provides a speedup in TensorFlow.
    weight_value_tuples = []
    for row in df.iterrows():
        row = row[1]
        name = row['layer_names']
        weight_values = row['weight_values']
        if name in index:
            symbolic_weights = index[name].weights
            if len(weight_values) != len(symbolic_weights):
                raise Exception('Layer named "' + layer.name +
                                '") expects ' + str(len(symbolic_weights)) +
                                ' weight(s), but the saved weights' +
                                ' have ' + str(len(weight_values)) +
                                ' element(s).')
            # Set values.
            for i in range(len(weight_values)):
                weight_value_tuples.append(
                    (symbolic_weights[i], weight_values[i]))
    K.batch_set_value(weight_value_tuples)


go = get_gene_ontology()


def filter_specific(gos):
    go_set = set(gos)
    for go_id in gos:
        anchestors = get_anchestors(go, go_id)
        anchestors.discard(go_id)
        go_set -= anchestors
    return list(go_set)


def read_fasta(lines):
    seqs = list()
    info = list()
    seq = ''
    inf = ''
    for line in lines:
        line = line.strip()
        if line.startswith('>'):
            if seq != '':
                seqs.append(seq)
                info.append(inf)
                seq = ''
            inf = line[1:]
        else:
            seq += line
    seqs.append(seq)
    info.append(inf)
    return info, seqs
