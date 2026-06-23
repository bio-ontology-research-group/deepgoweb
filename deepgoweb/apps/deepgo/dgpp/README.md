# DeepGO-PlusPlus-Light in DeepGOWeb

This package embeds **DeepGO-PlusPlus-Light** as an optional prediction model
alongside the original DeepGOPlus. Users pick the model on the prediction form
(and via the REST API / SPARQL endpoint, which funnel through the same task).

## What it is

DeepGO-PlusPlus-Light modernises the classic DeepGOPlus recipe (1D-CNN + DIAMOND)
for the **novel-protein** case, with **no GPU**:

- **`diam`** — DIAMOND BLAST-KNN: bit-score-weighted vote of each homolog's pre-t0
  GO labels.
- **`net_union`** — a homology-bridged STRING Net-KNN. Each homolog's *precomputed*
  STRING-neighbour label vector is voted; **no STRING files are read per request**,
  so it predicts functions for proteins that are not in STRING at all.
- Components are propagated to GO ancestors (max) and combined by a frozen per-aspect
  logistic integrator — the same math as the offline GSPA `run_deepgo_plusplus` sidecar.

Optional, opt-in extras (each hidden unless configured):

- **CNN** (`use_cnn`) — a CPU 1D-CNN that gives a sequence signal for *orphan* proteins
  with no homolog (where `diam`/`net` are blind). Needs PyTorch (CPU) + a `cnn_model.pt`.
- **InterProScan** (`interpro`) — adds domain GO terms; heavy, not bundled.

The code is **vendored** from the GSPA `deepgo-plusplus` project (rev `ffb10d6`,
`deepgo-plusplus/service/predict.py` + `pipeline/{apply_net_bridge,build_cnn_component}.py`).
The only change is import wiring and an extra `predict_full` method that also returns
the top DIAMOND homologs for the "similar proteins" table.

## How it is wired (fast, like DeepGOPlus)

`deepgo.tasks.predict_functions_dgpp` warm-loads one `DGppLight` into a **module
global** the first time it runs, so the DIAMOND DB and the ~205 MB precomputed bridge
index stay resident in the Celery worker and are reused across requests — exactly how
DeepGOPlus keeps its Keras model warm. Repeated `(sequence, model)` pairs additionally
hit a memcached layer (`deepgo.runner`), skipping DIAMOND entirely.

The task returns the **same shape** as `predict_functions`
(`list[(annots, sim_prots)]`), so the web view, REST serializer, and SPARQL endpoint
need no changes.

## Enabling it on a deployment

The small integrator JSONs live here in `models/`. The large data assets are **not**
committed — build them once (they are the same assets the GSPA service uses):

```bash
# from the gspa deepgo-plusplus/ checkout:
service/make_assets.sh /path/to/deepgoweb/data/dgpp \
    train.fasta train_net_index.tsv train_terms.tsv go-dag.tsv go.obo \
    [cnn_model.pt]   # optional, enables use_cnn
```

This produces, under `data/dgpp/`: `train_db.dmnd`, `train_net_index.tsv`,
`train_terms.tsv`, `go-dag.tsv`, `go.obo` (+ optional `cnn_model.pt`).

Configuration (`settings.DGPP_LIGHT`, all overridable by env var):

| key / env | default | meaning |
|---|---|---|
| `DGPP_ENABLED` | `1` | master switch; the model is also auto-hidden if `train_db.dmnd` is absent |
| `DGPP_ASSETS` | `<repo>/data/dgpp` | the asset bundle above |
| `DGPP_DIAMOND` | `diamond` | DIAMOND binary (already required by DeepGOPlus) |
| `DGPP_THREADS` | `8` | DIAMOND threads |
| `DGPP_CNN_MODEL` | `<assets>/cnn_model.pt` | weights to enable `use_cnn` (needs `torch`, CPU) |
| `DGPP_INTERPROSCAN` | — | path to `interproscan.sh` to enable the InterPro component |
| `PREDICTION_CACHE_TTL` | `86400` | seconds to cache predictions in memcached; 0 disables |

When disabled or unbuilt, the model is removed from the form choices and the API
rejects `model_name=dgpp-light` — DeepGOPlus is completely unaffected. The default
(fast) path needs only the `diamond` binary and the Python standard library — no
numpy, no torch.
