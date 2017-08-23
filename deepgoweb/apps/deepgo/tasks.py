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

    # hashes = list()
    # for seq in sequences:
    #     hashes.append(md5.md5(seq).hexdigest())
    # prots = Protein.objects.filter(sequence_md5__in=hashes)
    
    p = Popen(['blastp', '-db', 'data/embeddings.fa',
               '-max_target_seqs', '1', '-num_threads', '128',
               '-outfmt', '6 qseqid sseqid'], stdin=PIPE, stdout=PIPE)
    for i in xrange(n):
        p.stdin.write('>' + str(i) + '\n' + sequences[i] + '\n')
    p.stdin.close()

    prot_ids = {}
    if p.wait() == 0:
        for line in p.stdout:
            it = line.strip().split('\t')
            prot_ids[it[1]] = int(it[0])
    prots = embed_df[embed_df['accessions'].isin(prot_ids.keys())]
    for i, row in prots.iterrows():
        embeds[prot_ids[row['accessions']], :] = row['embeddings']
        
    for i in xrange(len(sequences)):
        seq = sequences[i]
        for j in xrange(len(seq) - gram_len + 1):
            data[i, j] = vocab[seq[j: (j + gram_len)]]
    return [data, embeds]


def predict(data, model, functions, threshold):
    batch_size = 1
    n = data[0].shape[0]
    result = list()
    for i in xrange(n):
        result.append(list())
    predictions = model.predict(
        data, batch_size=batch_size)
    for i in xrange(n):
        pred = (predictions[i] >= threshold).astype('int32')
        for j in xrange(len(functions)):
            if pred[j] == 1:
                result[i].append(functions[j])
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
        result = predict(data, model, functions)
        print result


@task
def predict_functions(sequences, threshold=0.3):
    if not models:
        init_models()
    data = get_data(sequences)
    result = list()
    for i in range(len(models)):
        model, functions = models[i]
        print 'Running predictions for model %s' % funcs[i]
        result += predict(data, model, functions, threshold)
    return result
