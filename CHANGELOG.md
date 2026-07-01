# DeepGOWeb Changelog

## v2.0.0 - DeepGOWeb v2

DeepGOWeb v2 adds the new DeepGO-PlusPlus-Light model, the DeepGO-GSPA genome-scale
workflow, containerized deployment, release archiving, and machine-readable exports.

### Added

- DeepGO-PlusPlus-Light protein prediction alongside legacy DeepGOPlus.
- Versioned release handling for both DeepGOPlus and DG++Light via `loadrelease`.
- CAFA-style metrics ingestion via `loadmetrics`; model performance belongs on the
  changelog/release page, not on every result page.
- DeepGO-GSPA genome-scale annotation tab:
  - genome/protein upload
  - optional GFF3 translation
  - per-contig genome-scale metrics
  - optional taxon consistency, completeness, coherence enforcement
  - provenance output
- Docker Compose deployment for web, worker, Redis, Postgres, Fuseki, and GSPA.
- GPU-enabled DG++Light worker path using CUDA PyTorch.
- Worker startup warmup for resident model state:
  - DG++Light CNN
  - ESM2 model
  - ESM2 hierarchy-aware head
  - ESM2 kNN embedding store
  - DG++Light train indexes and integrators
  - DeepGOPlus TensorFlow model
- RDF/Turtle download for protein predictions and genome-scale annotations.
- Downloadable example FASTA/GFF3 files; example buttons fill the form instead of
  auto-submitting jobs.
- Reproducible ProteInfer TF1.15 sidecar image (`docker/proteinfer.Dockerfile`).

### Changed

- DG++Light submissions are asynchronous and return immediately to a polling result page.
- DG++Light uses a default display threshold of `0.5`; DeepGOPlus remains `0.3`.
- Release-version fields are consistent between DeepGOPlus and DG++Light.
- DG++Light model/performance text was moved off result pages and into changelog/release metadata.
- Genome gene calling is restricted to explicit prokaryotic inputs (`Bacteria` or `Archaea`);
  eukaryotes and viruses require GFF3 or protein FASTA.
- Phage example identifiers are normalized to conventional `gp*` names instead of bare numbers.

### Fixed

- Cookie-law banner no longer calls a missing `Cookielaw` JavaScript object.
- Failed DG++Light jobs now show an error state instead of refreshing forever.

### Operational Notes

- The GPU worker runs as a single Celery `solo` process so the warmed CUDA model is kept
  resident in the same process that handles prediction tasks.
- ProteInfer remains isolated in a TF1.15 Docker sidecar launched per request. Keeping
  ProteInfer weights resident would require converting it into a long-lived sidecar API.
