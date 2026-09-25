# Exact executed training source

These files preserve the model/data/metric/export code read for the released run. `provenance/model-source.json` recomputes their combined fingerprint and binds it to `docs/data/experiment.json`.

The source is stored here for provenance, not as a second runnable package in this directory. To reproduce this exact version in a separate working directory, place these `.py` files under its `gems3/` package and `config.json` at `configs/riftline.json`, together with the root package initializer, the preserved `legacy/` proxy/bridge metadata and the pinned data. Run the documented Python 3.11 CPU commands. `evidence/environment-installed.txt` records the installed environment.

The active package may receive additional input-validation and cache-invalidation guards without retroactively rewriting the fingerprint of a completed model run. Changes that alter numeric operators, sampling, targets or selection require a new experiment and measured adoption. The current released candidate’s exact pixels are preserved and independently verifiable even when a training backend is not bitwise reproducible across environments.

For the original candidate, the selected contextual confidence field was bit-identical across two local executions; the raw-feature control was not. That dated record does not certify unrelated later model runs. See `evidence/repeatability.json` for that unresolved irregularity. No hidden-label score or universal deterministic-training guarantee is implied.
