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
# (interpro, cnn) -> frozen model JSON filename (shipped under dgpp/models/).
# Two variants share the same cascade math and assets; they differ ONLY in the cnn
# component — 'light' uses the original BCE-trained CNN, 'mcm' uses the hierarchy-aware
# CNN (C-HMCNN Max-Constraint Module over the GO is_a+part_of DAG; see gspa CASCADE.md).
# The no-cnn keys are identical between variants (nothing to retrain there).
MODEL_FILES = {
    'light': {
        (False, False): 'deepgo_plusplus_light_fast.json',       # diam + net_union (default)
        (False, True):  'deepgo_plusplus_light_fast_cnn.json',   # + CPU 1D-CNN (orphans)
        (True,  False): 'deepgo_plusplus_light_cpu.json',        # + InterProScan
        (True,  True):  'deepgo_plusplus_light_full.json',       # + both
    },
    'mcm': {
        (False, False): 'deepgo_plusplus_light_fast.json',           # no cnn -> same as light
        (False, True):  'deepgo_plusplus_light_fast_cnn_mcm.json',   # + hierarchy-aware CNN
        (True,  False): 'deepgo_plusplus_light_cpu.json',            # no cnn -> same as light
        (True,  True):  'deepgo_plusplus_light_full_mcm.json',       # + InterProScan + h.a. CNN
    },
}

# CNN weights per variant: bce vs the hierarchy-aware (MCM) head. Resolved from
# CNN_MODEL[_MCM] settings, else the ASSETS bundle, else the bundled models dir.
_CNN_FILE = {'light': 'cnn_model.pt', 'mcm': 'cnn_mcm.pt'}

_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')


def build_predictor(cfg, variant='light'):
    """Construct a warm :class:`DGppLight` from the ``DGPP_LIGHT`` settings dict.

    ``variant``: ``'light'`` (original) or ``'mcm'`` (hierarchy-aware CNN).

    ``cfg`` keys: ``ASSETS`` (dir with train_db.dmnd / train_net_index.tsv /
    train_terms.tsv / go-dag.tsv / go.obo), ``MODELS`` (override model dir),
    ``DIAMOND``, ``THREADS``, ``INTERPROSCAN`` (path to interproscan.sh; optional),
    ``CNN_MODEL`` / ``CNN_MODEL_MCM`` (path to the cnn weights .pt; optional).
    """
    assets = cfg['ASSETS']
    models_dir = cfg.get('MODELS') or _MODELS_DIR

    def asset(name):
        return os.path.join(assets, name)

    def resolve_cnn():
        key = 'CNN_MODEL_MCM' if variant == 'mcm' else 'CNN_MODEL'
        configured = cfg.get(key)
        if configured:
            return configured
        fn = _CNN_FILE[variant]
        in_assets = asset(fn)
        return in_assets if os.path.exists(in_assets) else os.path.join(models_dir, fn)

    files = MODEL_FILES.get(variant, MODEL_FILES['light'])
    models = {k: os.path.join(models_dir, f) for k, f in files.items()}

    # full cpu_lean serving (mcm variant): the flat integrator + the CPU aux components.
    # Each component stays off unless its asset is present, so the model degrades
    # gracefully (e.g. proteinfer only when DGPP_PROTEINFER_DIR + its docker image exist).
    cpu_lean = os.path.join(models_dir, 'cpu_lean_mcm.json') if variant == 'mcm' else None
    emb_store = cfg.get('EMB_STORE') or asset('train_esm2_35m.npz')
    return DGppLight(
        models=models,
        train_net_index=asset('train_net_index.tsv'),
        train_terms=asset('train_terms.tsv'),
        dag=asset('go-dag.tsv'),
        diamond_db=asset('train_db'),
        obo=asset('go.obo') if os.path.exists(asset('go.obo')) else None,
        diamond_bin=cfg.get('DIAMOND', 'diamond'),
        interproscan=cfg.get('INTERPROSCAN') or None,
        cnn_model=resolve_cnn(),
        threads=int(cfg.get('THREADS', 8)),
        emb_store=emb_store if os.path.exists(emb_store) else None,
        proteinfer_dir=cfg.get('PROTEINFER_DIR') or None,
        proteinfer_docker=cfg.get('PROTEINFER_DOCKER') or None,
        cpu_lean_model=cpu_lean,
    )
