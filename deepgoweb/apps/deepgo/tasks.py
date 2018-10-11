from celery import task

import numpy as np
import pandas as pd
from keras.models import load_model
from deepgo.constants import MAXLEN
from deepgo.models import Protein
import tensorflow as tf
import md5
from subprocess import Popen, PIPE

models = list()
funcs = ['cc', 'mf', 'bp']


def get_data(sequences):
    n = len(sequences)
    data = np.zeros((n, 1000), dtype=np.float32)
    embeds = np.zeros((n, 256), dtype=np.float32)
    
    p = Popen(['diamond', 'blastp', '-d', 'data/embeddings',
               '--max-target-seqs', '1',
               '--outfmt', '6', 'qseqid', 'sseqid'], stdin=PIPE, stdout=PIPE)
    
    for i in xrange(n):
        p.stdin.write('>' + str(i) + '\n' + sequences[i] + '\n')
    p.stdin.close()

    prot_ids = {}
    if p.wait() == 0:
        for line in p.stdout:
            it = line.strip().split('\t')
            prot_ids[int(it[0])] = it[1]
    prots = embed_df[embed_df['accessions'].isin(set(prot_ids.values()))]

    embeds_dict = {}
    for i, row in prots.iterrows():
        embeds_dict[row['accessions']] = row['embeddings']

    for i, prot_id in prot_ids.iteritems():
        embeds[i, :] = embeds_dict[prot_id]
    
    
    for i in xrange(len(sequences)):
        seq = sequences[i]
        for j in xrange(len(seq) - gram_len + 1):
            data[i, j] = vocab[seq[j: (j + gram_len)]]
    return [data, embeds]


def predict(data, model, functions, func):
    batch_size = 1
    n = data[0].shape[0]
    result = list()
    for i in xrange(n):
        result.append(list())
    predictions = model.predict(
        data, batch_size=batch_size)
    predictions = predictions.round(3)
    for i in xrange(n):
        pred = (predictions[i] > 0).astype('int32')
        for j in xrange(len(functions)):
            if pred[j] == 1:
                result[i].append(
                    func + '_' + functions[j] + '_' + str(predictions[i, j]))
    return result


def init_models(conf=None, **kwargs):
    print('Init')
    global models
    ngram_df = pd.read_pickle('data/models/ngrams.pkl')
    global embed_df
    embed_df = pd.read_pickle('data/graph_new_embeddings.pkl')
    global vocab
    vocab = {}
    global gram_len
    for key, gram in enumerate(ngram_df['ngrams']):
        vocab[gram] = key + 1
        gram_len = len(ngram_df['ngrams'][0])
    print('Gram length:', gram_len)
    print('Vocabulary size:', len(vocab))
    sequences = ['MKKVLVINGPNLNLLGIREKNIYGSVSYEDVLKSISRKAQELGFEVEFFQSNHEGEIIDKIHRAYFEKVDAIIINPGAYTHYSYAIHDAIKAVNIPTIEVHISNIHAREEFRHKSVIAPACTGQISGFGIKSYIIALYALKEILD']
    data = get_data(sequences)
    for onto in funcs:
        model = load_model('data/models/model_%s.h5' % onto)
        df = pd.read_pickle('data/models/%s.pkl' % onto)
        functions = df['functions']
        models.append((model, functions))
        print 'Model %s initialized. Running first predictions' % onto
        result = predict(data, model, functions, onto)
        print result


@task
def predict_functions(sequences):
    if not models:
        init_models()
    data = get_data(sequences)
    result = list()
    for i in range(len(models)):
        model, functions = models[i]
        print 'Running predictions for model %s' % funcs[i]
        result += predict(data, model, functions, funcs[i])
    return result
