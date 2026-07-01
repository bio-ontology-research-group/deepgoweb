# DeepGOWeb — Django site + Celery prediction worker in one image.
# Carries BOTH model stacks the site serves:
#   * legacy DeepGOPlus  -> tensorflow-cpu (model.h5)
#   * DG++Light (dgpp)   -> torch + fair-esm + the `diamond` binary
# Large data/model assets are NOT baked in; they are pulled at container start by
# docker/download_assets.sh from bio2vec.net (see docker/README.md).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=deepgoweb.settings.docker \
    TORCH_HOME=/opt/torch \
    DGPP_ASSETS=/opt/dgpp_assets \
    RELEASE_DATA_ROOT=/opt-data/extracted/

# --- system deps: curl (asset download), diamond (BLAST-KNN), libgomp (torch/tf) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# DIAMOND static binary (matches the version used to build train_db.dmnd)
ARG DIAMOND_VERSION=2.1.11
RUN curl -fL "https://github.com/bbuchfink/diamond/releases/download/v${DIAMOND_VERSION}/diamond-linux64.tar.gz" \
      | tar -xz -C /usr/local/bin diamond \
    && diamond --version

WORKDIR /app

# --- python deps in three layers for cache friendliness ---
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
# DG++Light extras: torch + fair-esm (imported lazily by dgpp/predict.py).
# Build with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu128
# for GPU inference in the Celery worker.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG TORCH_SPEC=torch==2.2.2
RUN pip install --index-url "${TORCH_INDEX}" "${TORCH_SPEC}" \
    && pip install "fair-esm==2.0.0"
# WSGI server for the `web` role (entrypoint runs `gunicorn`) + WhiteNoise so that
# gunicorn serves the collected static files directly (no nginx in this deploy).
# Separate layer so it doesn't bust the heavy requirements/torch layers above.
RUN pip install "gunicorn==23.0.0" "whitenoise==6.8.2"

# Docker CLI (client only) so the Celery worker can launch the isolated TF1.15
# ProteInfer container (DGPP_PROTEINFER_DOCKER) against the host daemon via the
# mounted /var/run/docker.sock. ProteInfer needs legacy TF1.15 (tensorflow.contrib)
# so it cannot share this image's TF2.15, and it is CPU-only. Placed after the
# heavy pip layers so it doesn't bust their cache.
ARG DOCKER_CLI_VERSION=27.3.1
RUN curl -fL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
      | tar -xz -C /usr/local/bin --strip-components=1 docker/docker \
    && docker --version

# --- app code ---
COPY . /app

# collectstatic needs no DB; give it throwaway env so the build never touches a service
RUN DJANGO_SECRET_KEY=build POSTGRES_HOST=localhost \
    python manage.py collectstatic --noinput || true

RUN chmod +x docker/entrypoint.sh docker/download_assets.sh
EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
# default: the web server. The worker overrides this in docker-compose.yml.
CMD ["web"]
