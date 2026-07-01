# Running DeepGOWeb v2 with Docker

One `docker compose up` brings up the full site — the Django web app, the Celery
prediction worker (both model stacks), the SPARQL endpoint, Redis and Postgres —
and **downloads every model/data asset on first start**. No assets are baked into
the images; they are pulled from the public mirror at `bio2vec.net`.

```bash
cp .env.example .env        # set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, ...
docker compose build
docker compose up           # first start downloads ~2 GB of assets into volumes
# site:   http://localhost:8000
# sparql: http://localhost:3330/ds/query   (also proxied at /ds/query by the site)
```

## What gets downloaded (`docker/download_assets.sh`)

| asset | into | source |
|---|---|---|
| **DG++Light bundle** (`train_db.dmnd`, `train_net_index.tsv`, `train_terms.tsv`, `go-dag.tsv`, `go.obo`, `train_esm2_35m.npz`, `esm2_35m_mcm.pt`, `cnn_mcm.pt`) | `assets` volume → `/opt/dgpp_assets` | `bio2vec.net/data/deepgoweb/dgpp_assets/` |
| **legacy DeepGOPlus release** (`go.obo`, `terms.pkl`, `train_data.pkl`, `model.h5`) | `release_data` volume → `/opt-data/extracted/<ver>/` | `bio2vec.net/data/deepgo/extracted/<ver>/` |
| **ESM2-35M weights** | image torch-hub cache (worker startup warmup) | HuggingFace via `fair-esm` |

The download is idempotent (existing files are skipped). After the first run set
`DOWNLOAD_ASSETS=0` to skip the check.

## Services

- **web** — gunicorn `deepgoweb.wsgi`; runs `migrate` on start. Serves the site, REST
  API (`/deepgo/api/...`) and proxies `/ds/query` to Fuseki.
- **worker** — `celery -A deepgoweb worker`. Runs predictions: legacy DeepGOPlus
  (TensorFlow `model.h5`) and DG++Light (`diamond` + torch + fair-esm). The v2
  deployment uses a single `solo` worker process by default so CUDA model weights
  are loaded once and kept resident in the same process that serves prediction jobs.
- **fuseki** — embedded Jena Fuseki (`sparql/Dockerfile`); stateless, proxies the
  `dg:predict` / `dg:components` / `dg:deepgo` property functions to `web`.
- **gspa** — the **Genome** tab's engine (DeepGO-GSPA): the JVM `gspa-cli` behind a
  FastAPI endpoint, built from the sibling `gspa` repo (`build.context: ../gspa`,
  `service/Dockerfile`). It shares the DG++Light `assets` volume (reuses
  `train_db.dmnd` / `go.obo` / ...). The worker POSTs an uploaded genome+GFF3 to it;
  it runs CDS translation → DG++Light → **per-contig** genome-scale metrics →
  optional SAT taxon-consistency / completeness / coherence enforcement → provenance,
  and returns the parsed tables. CPU-only. Tune with `GSPA_SERVICE_URL` (worker → service),
  `GSPA_PORT`, `GSPA_THREADS`, `GSPA_SERVICE_TIMEOUT`.
- **db** — Postgres; **redis** — Celery broker.

## Configuration (env)

`DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (0/1), `DJANGO_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`,
`DEEPGO_RELEASE` (legacy release to fetch, default `1.0.18`), `DGPP_THREADS`,
`WEB_PORT`, `FUSEKI_PORT`, `DATA_BASE` (asset mirror base, default
`https://bio2vec.net/data`). The site reads them via `deepgoweb/settings/docker.py`.

DG++Light/GPU worker controls:

- `DGPP_DEVICE=cuda` enables the CUDA path.
- `DGPP_WARMUP=1` loads resident model state at worker startup.
- `DGPP_VARIANT=mcm` selects the hierarchy-aware DG++Light variant.
- `CELERY_POOL=solo`, `CELERY_CONCURRENCY=1` are fixed in `docker-compose.yml`
  for the v2 GPU deployment to avoid duplicating CUDA model state across forked
  worker processes.

## Release Archive and Update Procedure

DeepGOWeb v2 separates code releases from model/data releases. Model releases are
archived as immutable directories and registered in the database.

### DeepGOPlus Release

```bash
docker compose exec web python manage.py loadrelease 1.0.18 \
  --predictor deepgoplus \
  --data-root /opt-data/extracted/1.0.18
```

The DeepGOPlus release directory must contain the archived files used by the legacy
predictor, including `go.obo`, `terms.pkl`, `train_data.pkl`, `model.h5`, and
release metadata when available.

### DeepGO-PlusPlus-Light Release

Archive each DG++Light model/data bundle under its own versioned directory, for
example:

```text
/opt/dgpp_assets/v2.0-light/
  train_db.dmnd
  train_net_index.tsv
  train_terms.tsv
  go-dag.tsv
  go.obo
  train_esm2_35m.npz
  esm2_35m_mcm.pt
  cnn_mcm.pt
  RELEASE.html
```

Then register it:

```bash
docker compose exec web python manage.py loadrelease v2.0-light \
  --predictor dgpp-light \
  --data-root /opt/dgpp_assets/v2.0-light
```

`loadrelease` is idempotent: rerunning it updates the existing `Release` row for
that version. The web form exposes DG++Light only when a `dgpp-light` release exists.

### CAFA Metrics

Performance metrics are computed offline and archived as JSON. Ingest them into the
registered release with:

```bash
docker compose exec web python manage.py loadmetrics v2.0-light /path/to/metrics.json
```

Metrics are displayed on the changelog/release page. They should not be hard-coded
on result pages.

### Deploying a Code Update

```bash
git pull
docker compose build web worker gspa fuseki
docker compose up -d
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py check
```

For a GPU worker, verify CUDA and warmup:

```bash
docker exec deepgoweb-worker-1 python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
docker logs deepgoweb-worker-1 | grep 'warmup complete'
```

### First Boot

Create an admin user when needed:

```bash
docker compose exec web python manage.py createsuperuser
```
