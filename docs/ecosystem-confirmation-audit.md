# Cellular confirmation donor-access audit

**Route cancelled, 2026-09-06.** The user deprecated this research plan for insufficient accessible independent eligible donors. Preserve all models, data, results and audits; no further research or autonomous resumption is authorized.

The biological power gate remains unmet. Direct malignant/CAF development models now project more than 80% power at 60 simulated donors, but those simulations resample only eight development donors. The current 18-donor design still has near-zero power. This audit checks whether another independent, eligible cohort supplies the missing budget; it does not count cells, assay records, tumor sections or previously exposed training donors as new confirmation donors.

## Remaining original-source leads

| Source | What is actually available or reported | Confirmation issue |
| --- | --- | --- |
| [GSE292095](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE292095), Stanford NFAT study | Six original PDAC patients, each with GEX and ATAC records; 12 records total. Original public GEX H5 files exist. | Multiome RNA is not automatically interchangeable with the registered snRNA assay. GEO characteristics do not provide treatment status. Six is an upper bound, not six verified eligible donors. |
| [GSE278689](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE278689), neural-invasion study | Eight tumor snRNA specimens, with 32,005 public metadata cell rows. The parent project’s 25 patients span modalities and tissue types. All eight have at least 32 author-labelled Ductal and CAF cells. | No treatment field in released cell metadata or sample characteristics; Ductal is not a verified malignant label. Neural-invasion sampling and cross-source identities require review. Public processed matrix files exist but were not opened in this audit. |
| [GSE290274](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE290274) | PDX-derived primary/metastatic cell lines and KLF5 perturbation experiments, including replicate GEX/ATAC records. | These are not independent primary-tumor patients with paired malignant/CAF compartments. Adds zero eligible donors to this design. |
| [WashU HTAN study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9470535/) | The broad study reports 31 patients across modalities; snRNA validation specifically used two cases, HT288P1 and HT412P1. | The 31-patient headline is not 31 snRNA donors. Treatment and original count/annotation access for the two cases need specimen-level verification. |
| [Perineural-niche preprint](https://www.biorxiv.org/content/10.64898/2026.08.05.743048v2.full) | Reports 11 snRNA samples selected in the context of perineural invasion. | The available data statement says snRNA data will be deposited at dbGaP and accessions supplied. This is not a currently verified accessible cohort. |
| [Wuhan snRNA study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13187969/) | Three original patients with paired tumor/peritumoral tissue; MobiDrop library chemistry. The 48-patient validation concerns qPCR. | Neither six paired tissue specimens nor 48 qPCR patients establish a larger compatible snRNA cohort. |
| [ctPANDA / OEP00006497](https://doi.org/10.1016/j.ccell.2026.05.012) | Published study reports 152 PDAC snRNA patients. Earlier public NODE metadata identified raw and related processed files as Restricted. | No approved access has been established for this task. The 2026-09-06 public metadata recheck returned HTTP 403; it did not demonstrate a change in access. Treatment eligibility, unique donors and paired-compartment coverage also require verification. |

This is an audit of identified leads, not a claim that no other dataset exists. Large integrated atlases are source-discovery aids, not automatically additional independent cohorts. Their underlying donor releases must be deduplicated against existing development data and reserved confirmation sources.

## Evidence and access boundary

Original GEO SOFT family metadata for GSE292095, GSE290274 and GSE278689 was obtained from the official public FTP archive. The GSE278689 cell metadata contains only the columns `tissue`, `patients` and `all_celltype` (plus row identifiers); it provides no neoadjuvant-treatment column. Its eight original sample identifiers agree with the eight patient labels in cell metadata. These files and the per-patient cell-type count audit are retained locally under `data/interim/ecosystems/confirmation-audit/`. No candidate expression matrix was opened, no restricted file was requested and no Hwang confirmation matrix was opened.

The WashU paper distinguishes its broad scRNA cohort from the two snRNA validation cases. The perineural-niche preprint’s data statement is prospective, so its 11 specimens cannot be treated as data already delivered to this project. The original GSE290274 metadata explicitly identifies patient-derived xenograft cell lines and perturbations.

## Unresolved requirements at cancellation

Confirmation would have required an approved, sufficiently large independent untreated-primary-PDAC cohort with the registered assay, original measured counts, canonical donor identities and malignant/CAF coverage. Approximately 60 usable donors is the current development-based planning target, not a guarantee of 80% biological power. The final model/alternative and eligibility rules must be frozen before independent numerical evaluation. The observed model-selection instability, biological uncertainty and the remaining confounding/missingness controls also remain unresolved.

Reusing the exposed development donors, treating multiple modalities as new people, opening reserved data to tune a model, weakening the 80% threshold, or simply running more epochs would not establish this gate. Training and source-audit milestones are complete, but the full goal is not. The user cancelled further pursuit; this audit does not authorize reopening the route.

Related results: [direct count-model training and all power comparisons](ecosystem-cna-training.md), [CNA source preparation and initial transfer failure](ecosystem-cna.md), and [original plan](../plans/evalue-tool-council/PLAN-cellular-ecosystems.md). This milestone changes documentation only; source counts, links and consistency were reviewed, with no code-test rerun required.
