from celery import task
from celery.signals import worker_init

import numpy as np
import pandas as pd
from keras.models import Model, model_from_json
from keras.preprocessing import sequence
from deepgo.constants import (
    AAINDEX, MAXLEN)
# import tensorflow as tf

models = list()
devs = [('cc', '/gpu:0'), ('mf', '/gpu:0'), ('bp', '/gpu:1')]
# devs = [('bp', '/gpu:0')]


def get_data(sequences):
    n = len(sequences)
    data = np.zeros((n, MAXLEN), dtype='float32')
    for i in range(n):
        for j in range(len(sequences[i])):
            data[i, j] = AAINDEX[sequences[i][j]]
    return data


def predict(data, model, functions):
    batch_size = 1
    n = data.shape[0]
    result = list()
    for i in range(n):
        result.append(list())
    predictions = model.predict(
        data, batch_size=batch_size)
    for i in range(len(functions)):
        rpred = predictions[i].flatten()
        pred = np.round(rpred)
        for j in range(n):
            if pred[j] == 1:
                result[j].append(functions[i])
    return result


def init_models(conf=None, **kwargs):
    global models
    sequences = ['MKKVLVINGPNLNLLGIREKNIYGSVSYEDVLKSISRKAQELGFEVEFFQSNHEGEIIDKIHRAYFEKVDAIIINPGAYTHYSYAIHDAIKAVNIPTIEVHISNIHAREEFRHKSVIAPACTGQISGFGIKSYIIALYALKEILD']
    print 'Init'
    data = get_data(sequences)
    for onto, dev in devs:
        with open('models/%s/model.json' % onto, 'r') as f:
            json_string = next(f)
        # with tf.device(dev):
        model = model_from_json(json_string)
        model.compile(
            optimizer='rmsprop',
            loss='binary_crossentropy',
            metrics=['accuracy'])
        model.load_weights('models/%s/weights.hdf5' % onto)
        df = pd.read_pickle('models/%s/functions.pkl' % onto)
        functions = df['functions']
        models.append((model, functions))
        print 'Model %s initialized. Running first predictions' % onto
        result = predict(data, model, functions)
        print result


@task
def predict_functions(sequences):
    if not models:
        init_models()
    data = get_data(sequences)
    result = list()
    for i in range(len(models)):
        model, functions = models[i]
        print 'Running predictions for model %s' % devs[i][0]
        result += predict(data, model, functions)
    return result
