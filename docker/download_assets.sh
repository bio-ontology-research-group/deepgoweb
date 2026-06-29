#!/usr/bin/env bash
# Download every model + data asset DeepGOWeb needs to run *fully* — the
# DG++Light (dgpp) bundle and one legacy DeepGOPlus release — from the public
# mirror at bio2vec.net. Idempotent: each asset is skipped if already present.
#
# Run at container start (entrypoint) or once into a named volume:
#   DGPP_ASSETS=/opt/dgpp_assets RELEASE_DATA_ROOT=/opt-data/extracted \
#   DEEPGO_RELEASE=1.0.18 docker/download_assets.sh
#
# Env:
#   DATA_BASE        base URL of the mirror   (default https://bio2vec.net/data)
#   DGPP_ASSETS      where the DG++Light bundle lands (default /opt/dgpp_assets)
#   RELEASE_DATA_ROOT  parent of the legacy release dirs (default /opt-data/extracted)
#   DEEPGO_RELEASE   legacy DeepGOPlus release to fetch (default 1.0.18; '' to skip)
#   SKIP_DGPP=1      skip the DG++Light bundle
set -euo pipefail

DATA_BASE="${DATA_BASE:-https://bio2vec.net/data}"
DGPP_ASSETS="${DGPP_ASSETS:-/opt/dgpp_assets}"
RELEASE_DATA_ROOT="${RELEASE_DATA_ROOT:-/opt-data/extracted}"
DEEPGO_RELEASE="${DEEPGO_RELEASE:-1.0.18}"

log(){ echo "[download_assets] $*"; }
fetch(){ # url dest
  local url="$1" dest="$2"
  if [ -s "$dest" ]; then log "have $(basename "$dest")"; return 0; fi
  log "GET $url"
  # PID-unique temp so concurrent runs (web + worker share the volume) never
  # collide on a single .part file; only publish if nobody beat us to it.
  local part="$dest.$$.part"
  curl -fL --retry 5 --retry-delay 5 -o "$part" "$url"
  if [ -s "$dest" ]; then rm -f "$part"; else mv "$part" "$dest"; fi
}

# Serialize concurrent runs across the shared asset volumes: web and worker both
# run this at boot, so without a lock they race (corrupt .part / crash on mv).
# flock makes the second waiter skip everything (files already present).
mkdir -p "$DGPP_ASSETS" "$RELEASE_DATA_ROOT"
exec 9>"$DGPP_ASSETS/.download.lock"
flock 9

# --- 1. DG++Light (dgpp) bundle: the strictly-CPU multi-evidence predictor ---
# Files resolved by deepgoweb/apps/deepgo/dgpp/__init__.py:build_predictor().
if [ "${SKIP_DGPP:-0}" != "1" ]; then
  mkdir -p "$DGPP_ASSETS"
  DGPP_FILES=(
    train_db.dmnd          # DIAMOND BLAST-KNN database (pre-t0 train proteins)
    train_net_index.tsv    # precomputed STRING Net-KNN votes for the homology bridge
    train_terms.tsv        # pre-t0 GO labels
    go-dag.tsv             # is_a + part_of DAG (propagation)
    go.obo                 # ontology (obsolete-term resolution + namespaces)
    train_esm2_35m.npz     # pre-t0 ESM2-35M embedding store (kNN)
    esm2_35m_mcm.pt        # ESM2-35M hierarchy-aware (C-HMCNN/MCM) head
    cnn_mcm.pt             # hierarchy-aware 1D-CNN (orphan coverage)
  )
  log "DG++Light bundle -> $DGPP_ASSETS"
  for f in "${DGPP_FILES[@]}"; do
    fetch "$DATA_BASE/deepgoweb/dgpp_assets/$f" "$DGPP_ASSETS/$f"
  done
fi

# --- 2. Legacy DeepGOPlus release (TensorFlow CNN) ---
# Already public under bio2vec.net/data/deepgo/extracted/<ver>/ ; a Release row in
# the DB points its data_root at $RELEASE_DATA_ROOT/<ver>.
if [ -n "$DEEPGO_RELEASE" ]; then
  REL_DIR="$RELEASE_DATA_ROOT/$DEEPGO_RELEASE"
  mkdir -p "$REL_DIR"
  log "DeepGOPlus release $DEEPGO_RELEASE -> $REL_DIR"
  for f in go.obo terms.pkl train_data.pkl model.h5; do
    fetch "$DATA_BASE/deepgo/extracted/$DEEPGO_RELEASE/$f" "$REL_DIR/$f"
  done
fi

log "all assets ready."
