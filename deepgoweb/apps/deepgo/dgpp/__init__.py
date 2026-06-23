"""DeepGO-PlusPlus-Light: a strictly-CPU GO predictor embedded in DeepGOWeb.

Vendored from the GSPA ``deepgo-plusplus`` project (gspa rev ffb10d6).  The model
modernises the classic DeepGOPlus recipe (DIAMOND BLAST-KNN + CNN) by replacing the
CNN with a homology-bridged STRING Net-KNN, so it predicts functions for proteins that
are not in STRING at all — the realistic novel-protein case — using only the `diamond`
binary (no GPU).  See ``deepgo.tasks.predict_functions_dgpp`` for how it is wired into
the warm Celery worker, mirroring how DeepGOPlus is served.
"""
import os

from .predict import DGppLight

# (interpro, cnn) -> frozen model JSON filename (shipped under dgpp/models/).
# Only the combinations whose file exists *and* whose extra tool/asset is configured
# are actually served (DGppLight filters missing model files; tasks.py gates cnn/interpro).
MODEL_FILES = {
    (False, False): 'deepgo_plusplus_light_fast.json',       # diam + net_union (default)
    (False, True):  'deepgo_plusplus_light_fast_cnn.json',   # + CPU 1D-CNN (orphans)
    (True,  False): 'deepgo_plusplus_light_cpu.json',        # + InterProScan
    (True,  True):  'deepgo_plusplus_light_full.json',       # + both
}

_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')


def build_predictor(cfg):
    """Construct a warm :class:`DGppLight` from the ``DGPP_LIGHT`` settings dict.

    ``cfg`` keys: ``ASSETS`` (dir with train_db.dmnd / train_net_index.tsv /
    train_terms.tsv / go-dag.tsv / go.obo), ``MODELS`` (override model dir),
    ``DIAMOND``, ``THREADS``, ``INTERPROSCAN`` (path to interproscan.sh; optional),
    ``CNN_MODEL`` (path to cnn_model.pt; optional).
    """
    assets = cfg['ASSETS']
    models_dir = cfg.get('MODELS') or _MODELS_DIR

    def asset(name):
        return os.path.join(assets, name)

    models = {k: os.path.join(models_dir, f) for k, f in MODEL_FILES.items()}
    return DGppLight(
        models=models,
        train_net_index=asset('train_net_index.tsv'),
        train_terms=asset('train_terms.tsv'),
        dag=asset('go-dag.tsv'),
        diamond_db=asset('train_db'),
        obo=asset('go.obo') if os.path.exists(asset('go.obo')) else None,
        diamond_bin=cfg.get('DIAMOND', 'diamond'),
        interproscan=cfg.get('INTERPROSCAN') or None,
        cnn_model=cfg.get('CNN_MODEL') or asset('cnn_model.pt'),
        threads=int(cfg.get('THREADS', 8)),
    )
