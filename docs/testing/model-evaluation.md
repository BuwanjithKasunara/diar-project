# Model evaluation and dataset record

Evaluated on 2026-10-11 (Asia/Colombo), Python 3.12.10 in a fresh environment.
The [JSON record](model-evaluation.json) includes dataset SHA-256, package versions,
seed, class counts, split indices, confusion matrix and per-class metrics.

From the repository root, create a virtual environment and install
`backend/requirements-lock.txt`; then from `backend` run:

```text
python train_ml_model.py
python train_ml_model.py --output evaluation-local.json
```

Evaluation alone does not replace the runtime artifact. `--save-model` additionally
trains on the full deduplicated dataset and writes the local ignored joblib file.
Re-evaluation changes the timestamp; numerical results should match with the pinned
environment and input hash. Small platform differences may affect floating values.

The repository CSV has 75 nonempty labelled rows: 15 each for AI Engineer,
Data Scientist, Entrepreneur, Researcher and Software Engineer. The original
collection method, source, author consent and dataset licence are unknown; no
dataset-specific provenance or licence evidence was found in this checkout.
Do not describe these rows as verified real resumes or a representative sample.

Normalization lowercases text and collapses whitespace. Exact duplicates are
removed before evaluation; conflicting labels for identical normalized text stop
evaluation. This run found zero duplicates and zero conflicts. A stratified
80/20 holdout uses seed 42: 60 training rows and 15 test rows, with no exact text
overlap. Train/test character similarity at 0.9 found zero near-duplicate pairs.
That screen cannot rule out shared templates, semantic duplicates or shared authors.

Five shuffled stratified folds use seed 42. TF-IDF is fitted inside each fold,
avoiding vocabulary fitting on test rows. The holdout accuracy was 100%; mean
five-fold accuracy was 98.67%. These are in-dataset results on a small sample,
not evidence of real-profile accuracy, probability calibration or a defensible
abstention threshold. No performance minimum is enforced in CI.

The model uses TF-IDF unigrams/bigrams, English stop words, 4,000 maximum features,
sublinear TF and logistic regression (C=1.5, maximum 1,000 iterations, seed 42).
The runtime continues to train from the CSV if its local model is missing. Load,
training or inference failures return unavailable ML while retaining rule analysis.
