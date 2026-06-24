"""Shared prediction dispatch for the web form and the REST API.

Both ``PredictionForm.save`` and ``PredictionGroupSerializer.save`` funnel through
:func:`run_predictions`, which

  * routes to the right warm Celery task based on the chosen model
    (``deepgoplus`` -> :func:`deepgo.tasks.predict_functions`,
     ``dgpp-light``  -> :func:`deepgo.tasks.predict_functions_dgpp`), and
  * caches per-(sequence, model) results in memcached, so a repeated sequence skips
    DIAMOND / the model entirely — a cheap latency win on top of DeepGOWeb's
    warm-worker design.

Output shape is identical for every model:
``list[(annots {go_id->score}, sim_prots {protein->bitscore})]``, one entry per input
sequence, in order — exactly what the existing ``save`` logic already expects.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache

from deepgo.tasks import predict_functions, predict_functions_dgpp

DGPP_LIGHT = 'dgpp-light'
DGPP_LIGHT_MCM = 'dgpp-light-mcm'
DEEPGOPLUS = 'deepgoplus'


def dgpp_enabled():
    """True iff DeepGO-PlusPlus-Light is switched on and its assets are present."""
    import os
    cfg = getattr(settings, 'DGPP_LIGHT', None)
    if not cfg or not cfg.get('ENABLED'):
        return False
    # The DIAMOND DB is the one indispensable asset; if it is missing the model
    # cannot run, so hide it rather than fail at request time.
    return os.path.exists(os.path.join(cfg['ASSETS'], 'train_db.dmnd'))


def dgpp_mcm_enabled():
    """True iff the hierarchy-aware (MCM) variant can run: the Light assets are present
    AND the MCM CNN weights resolve (the variant's whole point is the CNN component)."""
    import os
    if not dgpp_enabled():
        return False
    cfg = settings.DGPP_LIGHT
    candidates = [cfg.get('CNN_MODEL_MCM'),
                  os.path.join(cfg['ASSETS'], 'cnn_mcm.pt'),
                  os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'dgpp', 'models', 'cnn_mcm.pt')]
    return any(c and os.path.exists(c) for c in candidates)


def _cache_key(model_name, use_cnn, sequence):
    raw = '%s|%d|%s' % (model_name, int(bool(use_cnn)), sequence)
    return 'dgw:pred:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()


def run_predictions(sequences, model_name=DEEPGOPLUS, use_cnn=False):
    sequences = [s.strip() for s in sequences]
    n = len(sequences)
    ttl = getattr(settings, 'PREDICTION_CACHE_TTL', 0)

    results = [None] * n
    misses, miss_idx = [], []
    for i, seq in enumerate(sequences):
        cached = cache.get(_cache_key(model_name, use_cnn, seq)) if ttl else None
        if cached is not None:
            results[i] = cached
        else:
            misses.append(seq)
            miss_idx.append(i)

    if misses:
        if model_name == DGPP_LIGHT_MCM:
            # the hierarchy-aware variant IS the CNN component -> force cnn on
            preds = predict_functions_dgpp.delay(misses, True, 'mcm').get()
        elif model_name == DGPP_LIGHT:
            preds = predict_functions_dgpp.delay(misses, use_cnn, 'light').get()
        else:
            preds = predict_functions.delay(misses).get()
        for j, idx in enumerate(miss_idx):
            results[idx] = preds[j]
            if ttl:
                cache.set(_cache_key(model_name, use_cnn, sequences[idx]),
                          preds[j], ttl)

    return results
