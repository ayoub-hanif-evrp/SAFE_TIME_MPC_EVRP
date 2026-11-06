# Gate 3B — Dataset provenance

Raw archives are gitignored under `data/raw/`. Manifests and this note are tracked.

## EVRP-TW-D (primary candidate)

| Field | Value |
| --- | --- |
| Landing | https://zenodo.org/records/18529191 |
| DOI | https://doi.org/10.5281/zenodo.18529191 |
| Metadata version | **v1.1** (Geo-AC-v1.1 / NA-US-20) |
| Archive filename | `EVRP-TW-D-B-v1.0.tar.gz` |
| Version discrepancy | Record metadata says **v1.1**; the sole published file is still named **v1.0**. We treat metadata version as the scientific release label and record the archive filename verbatim. |
| License | CC-BY-4.0 |
| Published MD5 | `7cc5ddd617dff8792b167f45ab7e4ed3` |
| Size | 527,733,122 bytes (match) |
| Local SHA-256 | `02da7522652daf3a1a00211a84e984f714002b3e200cf2f860b5a66376bc9fcb` |
| MD5 verified | yes |
| Contents (metadata claim) | `source_data` geospatial layers; `eval_standard_20` territories |
| Contents (actual archive) | `dataset/{anchored,unanchored}/Cus_*` Solomon+pickle; `dist_fun=2-norm`; **no** road-edge files |
| Character | Semi-synthetic generator EVRPTW; metadata oversells road networks vs the tarball |

## LaDe (operational demand)

| Field | Value |
| --- | --- |
| Site | https://cainiaoai.github.io/LaDe-website/ |
| Code | https://github.com/wenhaomin/LaDe |
| Distribution | https://huggingface.co/datasets/Cainiao-AI/LaDe |
| Subset acquired | `delivery/delivery_jl.csv` (Jilin; manageable size) |
| Bytes | 4,736,342 |
| MD5 | `1a28b45d6aa4a9ec8cf196ee4ab3f73a` |
| SHA-256 | `12e2cf4664dd5b4475d39dddee8872f5a03b3082f08f0eece7f103baee6c6e73` |
| Rows | 31,415 (+ header) |
| Columns | order_id, region_id, city, courier_id, lng, lat, aoi_*, accept_time, accept_gps_*, delivery_time, delivery_gps_*, ds |
| License | Research use per HF card / authors’ terms (not EV) |
| Caveats | Couriers are **not** electric vehicles. `delivery_time` / `delivery_gps_time` are outcomes — **not** available to an online controller at decision time. Use accept/release-side fields only for online information. |

## Amazon Last Mile Routing Challenge

| Field | Value |
| --- | --- |
| Registry | https://registry.opendata.aws/amazon-last-mile-challenges/ |
| Access | `s3://amazon-last-mile-challenges` unsigned (`--no-sign-request`) |
| License | CC BY-NC 4.0 |
| Sample acquired | `License.txt`, `Readme.txt`, training `readme.md`, `route_data` 5 MiB prefix, `package_data` 2 MiB prefix |
| Full eval travel times | ~843 MB (not bulk-downloaded) |
| Caveats | ICE last-mile routes; windows and travel-time matrices are real operational structure, not EV energy. |

## ESOGU-ML5EV (light cargo EV energy)

| Field | Value |
| --- | --- |
| DOI | https://doi.org/10.5281/zenodo.14912892 |
| Archive | `snmbzkrt87/ESOGU-ML5EV-v1.0.0.zip` |
| License | Apache-2.0 |
| Published MD5 | `25fee94466835e59043edeb708e44ed2` |
| Local MD5 | `25fee94466835e59043edeb708e44ed2` (match) |
| Local SHA-256 | `599d0f37d991b4d86f54c6e55137edbcebe691cdb0a893ce675442dd08adc8f9` |
| Bytes | 726,065 |
| Files | 35 cleaned CSVs; SOC, speeds, torque, charging flags on an L5 urban cargo EV |
| Role | Energy plausibility / consumption calibration — **not** Amazon or LaDe vehicle traces |

## Schneider E-VRPTW

Retained as small mathematical reference only (see Part 1 `DATA_PROVENANCE.md`). Not the flagship Gate 3B application.
