# Running DeepGOWeb with Docker

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
| **ESM2-35M weights** | image torch-hub cache (first inference) | HuggingFace via `fair-esm` |

The download is idempotent (existing files are skipped). After the first run set
`DOWNLOAD_ASSETS=0` to skip the check.

## Services

- **web** — gunicorn `deepgoweb.wsgi`; runs `migrate` on start. Serves the site, REST
  API (`/deepgo/api/...`) and proxies `/ds/query` to Fuseki.
- **worker** — `celery -A deepgoweb worker`. Runs predictions: legacy DeepGOPlus
  (TensorFlow `model.h5`) and DG++Light (`diamond` + torch + fair-esm).
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

## After first boot

Create an admin user and a `Release` row (Admin → Releases) whose **data_root** points
at `/opt-data/extracted/<ver>` so the legacy predictor is selectable:

```bash
docker compose exec web python manage.py createsuperuser
```

The DG++Light predictor is enabled automatically when its assets are present
(`DGPP_ENABLED=1`, the default).
