# Versioned DeepGOPlus update scripts

These are the fail-fast training/update scripts and receiver installer used by
the legacy DeepGOWeb release pipeline. Hostnames, account names, paths, and
accelerator settings belong in host-local configuration files, not in Git.

On the training host, put `update.py`, `update.sh`, and `new_evaluation.sh` in
the model-build project. Copy `update.env.example` to `metadata/update.env`,
edit it for that host, and restrict it to the service account (`chmod 600`).
On the receiving host, put `take_data_ontolinator` and its private configuration
side by side; use `take_data_ontolinator.env.example` as the template. Do not
commit either real configuration file.

`update.sh` uses a lock so only one update runs at a time. `update.py` keeps a
recoverable copy of release metadata until a checked server publication
succeeds. A failed run exits nonzero; the next invocation restores metadata
from an interrupted run before retrying. The receiver stages and validates the
archive, publishes the checkpoint directory atomically, and registers it in
Django. Full training/publication still requires an end-to-end test on a future
release; syntax checks alone do not exercise the model build.
