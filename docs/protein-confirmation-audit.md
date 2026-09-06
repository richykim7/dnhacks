# Protein confirmation-source audit

The goal is still the original confirmation release, including80% power at the
declared effect0.4, valid null behavior, eligible independent groups and independent
processing/sampling/privacy reviews. [Continuous calibration](protein-model-power.md)
now exceeds the modeled power target at192 pairs, but patient counts are not generated
by simulation and the modeled witness is not automatically a biological confirmation.

## Primary-source findings

| Source | What is actually available | Grade-pair limit and unresolved issue |
|---|---|---|
| Korea, PDC000248 |150 measured patients,143 strict ductal cases|25 pairs before treatment/coverage; processed data use across-sample normalization|
| APGI, PXD059074 |115 unique tumor patients; embedded annotations resolve97 ductal cases|35 G3 and60 G1/G2;2 undifferentiated/unknown excluded:35 clinical pairs before assay/review gates|
|2026 spatial proteome atlas|47 unique pancreatic-cancer patients among1,015 cancer patients|At most23 pairs arithmetically; no grade, ductal subtype or prior-treatment fields|
|ProCan public cohort1, PXD056810|20 ductal samples mapped to15 reported patient identifiers in the richer CSV|At most7 pairs using those identifiers; grade and prior-treatment metadata still unavailable|

These are ceilings, not approved confirmation counts. Even summing the four optimistic
ceilings gives90 pairs, below the currently tested192-pair successful modeled budget.
This sum does not assert cross-study independence, compatible assays or legal pooling.
CPTAC and Fudan are already exposed development/benchmark data and are not added.
The audit does not claim that no other suitable source exists.

### APGI

The [primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12548992/) reports
surgery without neoadjuvant treatment and125 collected patients, reduced to115 after
QC. Main Table1 contains aggregate grade and histology categories; those marginals
cannot supply an exact patient-level intersection. Four undifferentiated cases are
not silently mapped to G3. The publication's additional clinical Supplementary Table1
is also aggregate. [PRIDE's deposited file list](https://www.ebi.ac.uk/pride/ws/archive/v2/projects/PXD059074/files/all)
contains1,368 files, including raw runs, a spectral library and protein_matrix.csv;
no separately named clinical or SDRF crosswalk appears in that listing. **That listing
was insufficient to conclude that individual metadata were unavailable.** A subsequent
bounded header check found embedded clinical annotations in protein_matrix.csv.

The metadata-only extraction hashes patient identifiers and discards protein values
and dates. The deposited matrix has176 rows:115 unique tumor patients and61 normal
specimens, representing125 patient identifiers overall. Grade/histology annotations
are consistent within patients. The strict ductal tumor intersection has60
well/moderately differentiated cases,35 poorly differentiated cases and2
undifferentiated/unknown cases. Thus35 clinical grade pairs are verified within this
deposit; assay compatibility, independent processing and release reviews remain
unverified. The source's File_QC_check value is Processing, which is not treated as
a QC-pass declaration. Raw runs and normal specimens are not additional tumor donors.
The full source byte SHA256 is
`dac5565def740adfd647afac3e059723df4cd548833c3b4c37267fbc67ac673a`.

The stated processing uses survival-blocked preparation batches, DIA-NN peptide
filtering and MaxLFQ protein quantification. Conditional processing and selection
assumptions require review before native replay. The clinical supplement SHA256 is
`d885ff264e2e9e6b531cc6265222efc03873d5741eda33b258724cbdb4d255fb`.

### 2026 atlas

The [primary study](https://www.nature.com/articles/s41586-026-10660-y) and its
Supplementary Table1 identify47 pancreatic patients. They are labeled only
pancreatic carcinoma. The patient sheet contains age, sex, tissue/cancer labels,
anatomical classification, library type and center; it does not contain grade or
treatment. The sample sheet identifies technical replicates and instrument/batch
information, which must not be mistaken for extra donors. Metadata SHA256:
`72725bb4c52f69f6b74e5ca1bbc56ce89859b138902b3c79cca1fde8558afe64`.

### ProCan

The [primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12409279/) separates a
public cohort from larger cohorts retained behind participating institutions'
firewalls. Its public processed workbook has1,260 rows and four annotation columns:
SampleID, Cancer type, Tissue type and Cancer subtype. Auditing those four columns
finds20 ductal,7 neuroendocrine and25 normal pancreatic sample IDs. The repository's
documented richer training format is not supplied in that workbook. However, the
separately deposited E0008_P10_onlyVCB_protein_averaged_log2_transformed.csv contains
74 metadata columns before the protein columns. Its subject_collaborator_patient_id
field maps20 ductal sample rows to15 reported patient identifiers. No dedicated grade
or prior-treatment field is present, and scanning those metadata columns found no
explicit grade/differentiation terms in the ductal cases. The CSV contains non-UTF8
bytes and was decoded as Windows-1252, with raw byte hashes retained. Cross-study
identity equivalence is not established by this within-deposit mapping.
Protein values were not retained or analyzed for these annotation audits. Private
cohort counts cannot be represented as acquired or accessible patient data.

## Concrete metadata request ready for study teams

APGI patient/grade/histology mapping is now resolved from deposited annotations;
request only unresolved processing, cross-study identity and QC-selection details
if they cannot be established from its methods. For ProCan, request differentiation
grade, prior-treatment and primary-versus-metastatic status for the mapped patients,
plus the approved access route for larger pancreatic cohorts. For the atlas, request grade,
ductal histology and prior-treatment status for the published pancreatic PatientIDs.
For each source, request normalization/reference dependencies and whether usable
per-sample measurements can be reconstructed without fitting across future donors.
Do not request names, dates of birth, addresses or medical-record numbers.

These requests have not been sent. External correspondence needs explicit authorization
and an available delivery channel; neither is provided by a source-download permission.
Independent review of the actual sampling/processing contract and deployment privacy
also remains outstanding. Improving modeled power cannot supply those approvals.

## Reproduce the count audit

```sh
uv run --with openpyxl python scripts/audit_protein_apgi.py --article data/raw/protein/apgi/article.xml --atlas data/raw/protein/atlas2026/metadata.xlsx --embedded-clinical data/raw/protein/apgi/embedded-clinical.json --output new-audit.json
uv run pytest tests/test_protein_apgi.py
```

Use `--fetch-embedded` instead of `--embedded-clinical PATH` to stream the original
published CSV, compute its byte hash and project the clinical fields in memory.
The100-MiB source budget is enforced; protein columns and clinical dates are not
retained. Both routes produce the same aggregate clinical intersection.

Article XML was obtained through Europe PMC's public full-text API. Clinical
supplements and repository manifests, with receipts, remain in ignored
`data/raw/protein/apgi/`, `atlas2026/`, `procan/` and `korea/`. The parser records
`clinical_grade_pairs` separately from still-unverified confirmation eligibility.
`clinical_projection` extracts only PatientID, Grade, Histology and T_or_N from a
CSV stream, replacing patient IDs with namespaced hashes before retaining rows.
