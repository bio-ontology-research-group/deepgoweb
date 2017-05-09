from celery import task

import numpy as np
import pandas as pd
from keras.models import load_model
from deepgo.constants import MAXLEN
import tensorflow as tf

models = list()
devs = [('cc', '/gpu:1'), ('mf', '/gpu:1'), ('bp', '/gpu:1')]
ngram_df = pd.read_pickle('data/models/ngrams.pkl')
vocab = {}
for key, gram in enumerate(ngram_df['ngrams']):
    vocab[gram] = key + 1
gram_len = len(ngram_df['ngrams'][0])
print('Gram length:', gram_len)
print('Vocabulary size:', len(vocab))


def get_data(sequences):
    n = len(sequences)
    data = np.zeros((n, 1000), dtype='int32')
    for i in xrange(len(sequences)):
        seq = sequences[i]
        for j in xrange(len(seq) - gram_len + 1):
            data[i, j] = vocab[seq[j: (j + gram_len)]]
    return data


def predict(data, model, functions):
    batch_size = 1
    n = data.shape[0]
    result = list()
    for i in xrange(n):
        result.append(list())
    predictions = model.predict(
        data, batch_size=batch_size)
    for i in xrange(n):
        rpred = predictions[i]
        pred = np.round(rpred)
        for j in xrange(len(functions)):
            if pred[j] == 1:
                result[i].append(functions[j])
    return result


def init_models(conf=None, **kwargs):
    global models
    sequences = ['MKKVLVINGPNLNLLGIREKNIYGSVSYEDVLKSISRKAQELGFEVEFFQSNHEGEIIDKIHRAYFEKVDAIIINPGAYTHYSYAIHDAIKAVNIPTIEVHISNIHAREEFRHKSVIAPACTGQISGFGIKSYIIALYALKEILD']
    print 'Init'
    data = get_data(sequences)
    for onto, dev in devs:
        model = load_model('data/models/model_seq_%s.h5' % onto)
        model.compile(
            optimizer='rmsprop',
            loss='binary_crossentropy',
            metrics=['accuracy'])
        df = pd.read_pickle('data/models/%s.pkl' % onto)
        functions = df['functions']
        models.append((model, functions))
        print 'Model %s initialized. Running first predictions' % onto
        result = predict(data, model, functions)
        print result


@task
def predict_functions(sequences):
    if not models:
        # with tf.device('/gpu:1'):
        init_models()
    data = get_data(sequences)
    result = list()
    for i in range(len(models)):
        model, functions = models[i]
        print 'Running predictions for model %s' % devs[i][0]
        result += predict(data, model, functions)
    return result
