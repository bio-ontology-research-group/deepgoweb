# DeepGOWeb v2

DeepGOWeb v2 is the web interface for protein function prediction and genome-scale
annotation from the BORG group.

It serves:

- **DeepGOPlus**: the original CNN + DIAMOND protein-function predictor.
- **DeepGO-PlusPlus-Light**: a multi-evidence ensemble using DIAMOND, STRING-Net,
  hierarchy-aware CNN, ESM2-kNN, an ESM2 hierarchy-aware head, and ProteInfer.
- **DeepGO-GSPA**: genome-scale annotation and quality assessment over predicted
  protein functions, with optional taxon consistency, completeness, coherence and
  provenance output.

The deployed v2 stack is containerized with Docker Compose and includes the web app,
Celery worker, Postgres, Redis, Fuseki/SPARQL, and the GSPA annotation service.

See:

- [CHANGELOG.md](CHANGELOG.md) for the v2 release notes.
- [docker/README.md](docker/README.md) for deployment, model archive, and update
  procedures.

## Development

For local Django-only development:

```bash
python manage.py runserver
celery -A deepgoweb worker -l info
```

For the full v2 application, use Docker Compose:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```
