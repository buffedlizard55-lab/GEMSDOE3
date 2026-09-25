# Data placement

Run `bash scripts/download_competition_data.sh` then `python scripts/prepare_data.py` from the repository root in the installed Python environment. The downloader restores the three supplied raster files from the pinned upstream GitHub data bridge; size and SHA-256 are checked before atomic placement. Large raster files and caches are ignored by Git.

The original official data tab requires DrivenData login/enrollment. These bytes originate from the user-supplied Dropbox mirrors and match the inherited bridge inventory. Matching that inventory is **not an independent checksum from DrivenData**. The sample's values contradict the official all-zero example description; only its grid and finite-data mask are used.

Canonical files: `training_features.tif`, `labels.tif`, `sample_submission.tif`. The original DEM index is preserved at `legacy/data/dem_links.json`. No 1 m DEM is used by the current model. Never train on the sample's values or claim the mirrored files were freshly fetched from the authenticated official endpoint.
