"""Closed vocabularies: the menus the extractor chooses from. An identity key may contain only closed
vocabularies or resolved identifiers, never free text.
"""
from __future__ import annotations

import re

# --- relation classes -----------------------------------------------------------------------------
# A class exists to make the sign rule safe: two claims may only contradict on opposite sign if they measure
# the same dimension, or `precedes(+1)` would contradict `decreases(-1)`. Only signed classes are named;
# sign-0 predicates carry the empty class, and the conflicts among them are named directly in
# `OPPOSITE_PREDICATES`.
# The empty class, carried by every sign-0 predicate: no dimension asserted.
UNCLASSED = ""

# --- predicates -----------------------------------------------------------------------------------
# Direction lives in the canonical predicate itself, the way SIGNOR ships it (`up-regulates` and
# `down-regulates` are distinct terms), rather than in a separate polarity field that could disagree with
# the predicate. Synonyms collapse explicitly through `CANONICAL_PREDICATES`.
PREDICATES: dict[str, tuple[str, int]] = {
    # causal
    "increases": ("causal", +1), "decreases": ("causal", -1), "regulates": ("causal", 0),
    # dependency: "X needs Y" is not "X raises Y"
    "depends_on": (UNCLASSED, 0),
    # correlational: a correlation is not a causal claim whose direction was not recorded
    "associated_with": ("correlational", 0),
    "correlates_positively": ("correlational", +1),
    "correlates_inversely": ("correlational", -1),
    # physical
    "binds": (UNCLASSED, 0),
    "does_not_bind": (UNCLASSED, 0),     # a null physical result
    # spatial / genomic
    "enriched_at": (UNCLASSED, 0), "occupies": (UNCLASSED, 0), "co_occupies": (UNCLASSED, 0),
    "overlaps": (UNCLASSED, 0),
    "mutually_exclusive_with": (UNCLASSED, 0),  # co-exclusion in a cohort
    # Two events observed together in the same samples; distinct from `co_occupies`, which is two proteins
    # at one genomic site.
    "co_occurs_with": (UNCLASSED, 0),
    # temporal
    "precedes": ("temporal", +1), "delays": ("temporal", -1),
    # evolutionary
    "derives_from": (UNCLASSED, 0), "conserved_in": (UNCLASSED, 0),
    "present_in": (UNCLASSED, 0), "absent_in": (UNCLASSED, 0),
    # predictive: biomarker, never read as mechanism
    "predicts_worse": ("predictive", -1), "predicts_better": ("predictive", +1),
    "stratifies": ("predictive", 0),      # divides into groups without asserting which way
    "no_effect_on": (UNCLASSED, 0),
}

# When to reach for each predicate, kept beside the definitions so the prompt cannot drift from the table.
PREDICATE_WHEN: dict[str, str] = {
    "increases":      "X raises the object's amount/activity",
    "decreases":      "X lowers it",
    "regulates":      "X controls it but the paper does not say which way",
    "associated_with": "they go together; no direction claimed. A real choice, not a fallback",
    "correlates_positively": "more X, more Y; measured, in a population",
    "correlates_inversely":  "more X, less Y; measured, in a population",
    "depends_on":     "X needs Y to work (knock Y out and X fails)",
    "binds":          "physical interaction",
    "does_not_bind":  "tested for interaction and found none",
    "enriched_at":    "X is found concentrated at a place (a mark at a region)",
    "occupies":       "X sits at a specific site on DNA",
    "co_occupies":    "X and Y are at the same site on DNA",
    "overlaps":       "the two things share territory or scope",
    "co_occurs_with": "seen together in the same samples/patients (not the same DNA site)",
    "mutually_exclusive_with": "seen in the same cohort but never together",
    "precedes":       "X happens before Y",
    "delays":         "X makes Y happen later",
    "derives_from":   "X came from Y, by evolution, lineage or chemical conversion",
    "conserved_in":   "X is retained across the named species/lineage",
    "present_in":     "X is there, in a tissue, a species, a cohort, a tumour type. Use this for "
                      "'expressed in the spleen' and for 'mutated in 30% of tumours'",
    "absent_in":      "X is measurably not there",
    "predicts_worse": "X marks worse outcome. A biomarker, never read as cause",
    "predicts_better": "X marks better outcome",
    "stratifies":     "X splits patients into groups without saying which does better",
    "no_effect_on":   "tested and found nothing. Evidence, not absence of it",
}

# Surface form -> canonical predicate. This table is what collapses synonyms.
CANONICAL_PREDICATES: dict[str, str] = {
    "activates": "increases", "causes": "increases", "drives": "increases",
    # `licenses`, `maintains` and `confers` are ordinary positive regulation, usually shown by knockout;
    # the permissive-vs-instructive distinction lives in the experiment design, not the verb.
    "licenses": "increases", "maintains": "increases", "confers": "increases",
    "induces": "increases", "upregulates": "increases", "enhances": "increases",
    "promotes": "increases", "coactivates": "increases",
    "inhibits": "decreases", "represses": "decreases", "abolishes": "decreases",
    "protects_against": "decreases",
    "suppresses": "decreases", "blocks": "decreases", "downregulates": "decreases",
    "interacts_with": "binds", "recruits": "binds",
    "necessary_for": "depends_on", "required_for": "depends_on", "requires": "depends_on",
    "causes_no_change": "no_effect_on", "does_not_affect": "no_effect_on",
    "predicts": "stratifies",             # bare "predicts" states no direction; use predicts_worse/better
    "co_exclusive_with": "mutually_exclusive_with",
    "co_occurs": "co_occurs_with", "cooccurs_with": "co_occurs_with",
    "co_occurrent_with": "co_occurs_with", "co_mutated_with": "co_occurs_with",
}

# A predicate earns its place by distinguishing two claims that would otherwise merge.

# Claims that cannot both hold, for pairs whose conflict the sign cannot express. Opposite-signed predicates
# in the same relation class are caught by the sign rule and are not listed here.
OPPOSITE_PREDICATES: frozenset[frozenset[str]] = frozenset({
    frozenset({"present_in", "absent_in"}),
    frozenset({"binds", "does_not_bind"}),
    frozenset({"co_occurs_with", "mutually_exclusive_with"}),
})


def canonical_predicate(raw: str) -> str | None:
    """Surface predicate -> the canonical form that enters the identity key, or None to defer."""
    p = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    p = CANONICAL_PREDICATES.get(p, p)
    return p if p in PREDICATES else None


# Predicate -> the predicate it is a special case of: an `increases` claim is a refinement of a `regulates`
# claim on the same question. One level, never between siblings, and a parent sits in the same relation
# class as its children (asserted in the tests).
PREDICATE_PARENTS: dict[str, str] = {
    "increases": "regulates", "decreases": "regulates",
    "predicts_worse": "stratifies", "predicts_better": "stratifies",
    "correlates_positively": "associated_with", "correlates_inversely": "associated_with",
}


# --- object aspect --------------------------------------------------------------------------------
# Biolink's `object_aspect_qualifier` enum minus its directional values (see ASPECT_REWRITES). It answers
# "which property of the object changed"; processes and phenotypes are objects in their own right and carry
# no aspect. No value here may be an anti-quantity of the object: `degradation` fails because "GRB2
# increases EGFR degradation" means "GRB2 decreases EGFR".
OBJECT_ASPECTS: frozenset[str] = frozenset({
    "activity", "abundance", "expression", "synthesis",
    "localization", "transport", "molecular_interaction", "splicing", "mutation_rate",
    "phosphorylation", "methylation", "acetylation", "ubiquitination",
    "dna_binding", "chromatin_occupancy",
    # Three distinct measurements: thermal stability does not track cellular half-life proteome-wide, and
    # how firmly a protein folds and how much it moves come from different tools.
    "conformational_stability",   # the fold: ΔΔG, Tm, FoldX, thermostability
    "conformational_dynamics",    # flexibility: ΔΔSvib, ENCoM; `rigidity` is the anti-quantity, rewritten below
    "half_life",                  # turnover in cells: cycloheximide chase, ubiquitination, proteasome
                                  # inhibition; the only one that bears on abundance
})

# --- mechanism: SIGNOR's second column --------------------------------
# SIGNOR ships direction and mechanism as two columns. A mechanism term must be a noun for a route that is
# true whichever way the claim goes: `proteolysis` passes, `stabilization` fails, which is why Biolink's
# `CausalMechanismQualifierEnum` is not adopted.
MECHANISMS: frozenset[str] = frozenset({
    "proteolysis",     # the object is removed: degraded, cleaved, turned over
})

# Aspect the paper's wording implies -> (aspect stored, mechanism, does the sign flip?). The keys are
# accepted as input but never stored. A word is rewritten only when its sign is opposite to the quantity's,
# i.e. more of the aspect means less of the object; near-synonyms (`stability` vs `abundance`) are not.
ASPECT_REWRITES: dict[str, tuple[str, str, bool]] = {
    "degradation": ("abundance", "proteolysis", True),
    "rigidity": ("conformational_dynamics", "", True),   # more rigid is less dynamic
}

# What the extractor is offered. The rewritten words stay on the menu so the sign flip is done in code.
ASPECT_INPUTS: frozenset[str] = OBJECT_ASPECTS | frozenset(ASPECT_REWRITES)

# Signed predicate -> its opposite within the same relation class, used for rewriting a claim;
# OPPOSITE_PREDICATES is for detecting a sign-0 conflict.
INVERTED_PREDICATES: dict[str, str] = {
    "increases": "decreases", "decreases": "increases",
    "correlates_positively": "correlates_inversely",
    "correlates_inversely": "correlates_positively",
    "predicts_worse": "predicts_better", "predicts_better": "predicts_worse",
    "precedes": "delays", "delays": "precedes",
}


def invert_predicate(p: str) -> str | None:
    """The sign-flipped twin of a canonical predicate, or None if it carries no sign to flip (a sign-0
    predicate moves across a rewrite unchanged)."""
    return INVERTED_PREDICATES.get(p)


# --- directional process terms ----------------------------
# `demote_regulation_term` catches `positive|negative regulation of X` by pattern; these two are sibling
# terms rather than "regulation of" strings, so they are demoted here onto their undirected parent with the
# sign moved into the predicate. The parent's label reads awkwardly under a claim; the identity is what
# matters.
DIRECTIONAL_PROCESSES: dict[str, tuple[str, str, bool]] = {
    # directional CURIE -> (undirected parent, parent label, does the sign FLIP?)
    "GO:0050821": ("GO:0031647", "regulation of protein stability", False),   # protein stabilization
    "GO:0031648": ("GO:0031647", "regulation of protein stability", True),    # protein destabilization
}

# --- entity state ---------------------------------------------------------------------------------
# One entity per resolved identifier, carrying state, which is part of the identity key: wild-type and
# mutant forms are different actors. `general` (the paper means the gene as a whole) and `unknown` (the paper
# is about some particular form and does not say which) are opposite situations, and only the first may take
# part in a general/specific link, following BioPAX L3's distinction between absent and unspecified
# features.
FUNCTIONAL_STATES: frozenset[str] = frozenset({
    "wild-type", "mutant", "null_loss", "overexpressed",
    "general",      # the paper means the gene/product as a whole; licenses a general/specific link
    "unknown",      # the paper did not say, or the form could not be told; blocks such a link
    "unspecified",  # alias for `unknown`; the default when the reader states nothing
})


# --- isoform vs construct ----------------------------------------------
# An isoform (isoform-alpha, AR-V7) is a kind of the protein and inherits its biology; a lab construct
# (DBD, CTD, AF-2, Δ283-595, "full-length") is a piece of it, and a property of a part is not a property of
# the whole. The split is deterministic so stored rows land in the right field on load, and it is rule-based
# rather than a lookup table so it stays field-neutral. Unrecognised values stay isoforms, which is the safe
# default: a mislabelled isoform can only link claims about the same protein.
_REGION_TERMS: frozenset[str] = frozenset({
    # structural regions named by abbreviation, generic across protein biology
    "dbd", "ctd", "ntd", "tad", "lbd", "ctr", "ntr", "prd", "od", "sam", "nls", "nes",
    "af-1", "af1", "af-2", "af2", "dna-binding domain", "transactivation domain",
    "c-terminal domain", "n-terminal domain", "c-terminal region", "n-terminal region",
    "oligomerization domain", "oligomerisation domain", "proline-rich domain",
    "ligand-binding domain", "kinase domain", "full-length", "full length",
})
_CONSTRUCT_WORDS: tuple[str, ...] = ("delet", "lacking", "truncat", "fragment", "construct",
                                     "residues", "-only", " only", "mutantless")
# `deltaN-M` names a removed range (a construct); `deltaN` names an isoform by the residue it starts at.
_DELETION_RANGE = re.compile(r"^(delta|Δ|d)\s*\d+\s*[-–]\s*\d+$", re.I)


def classify_form(value: str) -> tuple[str, str]:
    """An isoform-slot string -> ('isoform' | 'construct', normalised value)."""
    v = (value or "").strip()
    if not v:
        return "isoform", ""
    low = v.lower()
    if low in _REGION_TERMS or _DELETION_RANGE.match(low) or any(w in low for w in _CONSTRUCT_WORDS):
        return "construct", low
    return "isoform", low

# --- clinical endpoints ---------------------------------------------------------------------------
# Objects for `predictive` claims only. In a causal claim survival is how something was measured and lives
# on the evidence; in a predictive claim the endpoint is what is claimed about. `poor prognosis` normalises
# to `overall_survival` at polarity -1.
CLINICAL_ENDPOINTS: frozenset[str] = frozenset({
    "overall_survival", "progression_free_survival", "disease_free_survival",
    "recurrence_free_survival", "biochemical_recurrence", "metastasis_free_survival",
    "response_to_therapy", "disease_stage", "tumour_grade",
    "time_to_progression", "objective_response_rate", "complete_remission",
    "relapse", "event_free_survival",
})

# --- categories: what a claim's subject or object is ----------------------------------------------
# One table: the prompt menu is rendered from it and the owner lookup reads the same rows, so no category
# can be assigned that no owner answers for. The category is a routing hint from the reader, who has the
# paper. What a node is still comes from its identifier (`kind_from_curie`); a mislabelled category costs a deferral, never a mistyped
# node. Exactly one owner answers for each category (`repeat` lists two prefixes because Dfam issues two id
# shapes). Terms only a non-owner carries defer, which is visible and recoverable.
CATEGORIES: dict[str, dict] = {
    # category -> owner, the namespaces that may answer for it, the resolver path, and the prompt gloss
    "gene": {"owner": "HGNC", "ns": ("HGNC",), "path": "entity",
             "when": "a gene or the protein it encodes: BRCA1, EGFR, ATM"},
    # Non-human genes have their own category and owner; the dedicated path refuses anything
    # human-resolvable and requires an organism context (grounding.nonhuman_gene_lookup).
    "non_human_gene": {"owner": "NCBI Gene", "ns": ("NCBIGene",), "path": "nonhuman_gene",
                       "when": "only a non-human organism's own gene, under its species-specific "
                               "name: unc-54, lin-12, Notch, hedgehog. Never a human gene, and never "
                               "a rodent ortholog written like the human symbol (Gene1 → gene). "
                               "Needs the organism in context"},
    "chemical": {"owner": "ChEBI", "ns": ("CHEBI",), "path": "entity",
                 "when": "a drug, small molecule or metabolite: olaparib, tamoxifen, estradiol"},
    "family": {"owner": "FamPlex", "ns": ("FPLX",), "path": "entity",
               "when": "a protein family or complex, not one gene: AKT, NF-kappaB, mTORC1"},
    "process": {"owner": "GO", "ns": ("GO",), "path": "process",
                "when": "an ordinary biological process: apoptosis, proliferation, DNA repair, EMT"},
    "pathological_process": {"owner": "MeSH", "ns": ("MESH",), "path": "process",
                             "when": "a disease process: tumorigenesis, carcinogenesis, metastasis"},
    "disease": {"owner": "MONDO", "ns": ("MONDO",), "path": "entity",
                "when": "a named disease: breast cancer, Li-Fraumeni syndrome"},
    # Phenotypes take the entity path (`obesity` is an HP lookup), with HP alone as owner.
    "phenotype": {"owner": "HP", "ns": ("HP",), "path": "entity",
                  "when": "an organism-level trait: obesity, insulin resistance, azoospermia"},
    "mark": {"owner": "SO", "ns": ("SO",), "path": "entity",
             "when": "a chromatin or DNA mark: H3K27ac, H3K9me3, methylated cytosine"},
    "repeat": {"owner": "Dfam", "ns": ("DFAM", "DFAMCLASS"), "path": "entity",
               "when": "a repeat family or transposable element: Alu, LINE-1, HERV-K, LTR12C"},
    "feature": {"owner": "ours", "ns": ("FEATURE",), "path": "entity",
                "when": "a named part of a gene: BRCA1 intron 1, the EGFR promoter"},
    "anatomy": {"owner": "UBERON", "ns": ("UBERON",), "path": "entity",
                "when": "a tissue or organ: liver, mammary gland"},
    "cell_type": {"owner": "CL", "ns": ("CL",), "path": "entity",
                  "when": "a cell type: hepatocyte, germinal centre B cell"},
    "cell_line": {"owner": "Cellosaurus", "ns": ("CVCL",), "path": "entity",
                  "when": "a named cell line: MCF-7, LNCaP"},
    "organism": {"owner": "NCBITaxon", "ns": ("NCBITaxon",), "path": "entity",
                 "when": "a species: mouse, C. elegans"},
    "endpoint": {"owner": "ours", "ns": (), "path": "endpoint",
                 "when": "a clinical endpoint or experimental phenotype -- see the closed lists below"},
}

# Derived, so they cannot drift from the table above.
CATEGORY_PATH: dict[str, str] = {k: v["path"] for k, v in CATEGORIES.items()}
CATEGORY_NS: dict[str, tuple] = {k: v["ns"] for k, v in CATEGORIES.items()}

EXPERIMENTAL_PHENOTYPES: frozenset[str] = frozenset({
    "treatment_resistance", "tumour_burden",
})

# --- evidence / study / provenance ----------------------------------------------------------------
# What kind of study produced this evidence. A different kind of study is different evidence on the same
# edge; only a different kind of relation needs a different edge.
STUDY_TYPES: frozenset[str] = frozenset({
    "molecular_experiment", "genomic_assay", "cohort_association", "clinical_trial",
    "animal_experiment", "evolutionary_comparison", "computational_analysis",
    "review_statement",          # a restatement; carries no experiment
    "unspecified",
})

# ECO-shaped evidence type: separates what the authors said from what was done.
EVIDENCE_TYPES: frozenset[str] = frozenset({
    "experimental_own",           # the authors' own experimental result
    "author_statement_prior",     # authors asserting someone else's finding
    "computational_inference",
    "curator_inference",
    "unspecified",
})

# How a context slot's value was obtained.
CONTEXT_PROVENANCE: frozenset[str] = frozenset({
    "stated",        # the claim's own passage says it; store the quote
    "inherited",     # methods/figure legend says it, propagated down; store that quote and its scope
    "unspecified",   # not determinable from the paper; not a failure and not a universal claim
})

# Inheritance is disabled for reviews: a restatement has no experimental system of its own.
DOC_TYPES: frozenset[str] = frozenset({
    "primary_research", "review", "preprint", "case_report", "clinical_trial_report",
    "methods_paper", "editorial", "unspecified",
})
INHERITANCE_ALLOWED: frozenset[str] = frozenset({
    "primary_research", "preprint", "clinical_trial_report", "methods_paper",
})

# --- context slots --------------------------------------------------------------------------------
# Each slot declares its own type, so the resolver only needs an id in a slot-appropriate namespace.
# Keys: `ontology` = preferred namespace(s), best first; `closed` = a closed value set instead of an
# ontology; `veto` = a mismatch disqualifies a context comparison outright; `map` = an explicit surface ->
# identifier table, tried before any similarity lookup.
CONTEXT_SLOTS: dict[str, dict] = {
    # Organism is a veto slot, so it resolves deterministically through an explicit table, never by
    # similarity score, with NCBITaxon as the only owner.
    "organism":     {"ontology": ["NCBITaxon"], "veto": True, "map": {
        "human": "NCBITaxon:9606", "humans": "NCBITaxon:9606", "homo sapiens": "NCBITaxon:9606",
        "patient": "NCBITaxon:9606", "patients": "NCBITaxon:9606",
        "mouse": "NCBITaxon:10090", "mice": "NCBITaxon:10090", "murine": "NCBITaxon:10090",
        "mus musculus": "NCBITaxon:10090",
        "rat": "NCBITaxon:10116", "rats": "NCBITaxon:10116", "rattus norvegicus": "NCBITaxon:10116",
        "zebrafish": "NCBITaxon:7955", "danio rerio": "NCBITaxon:7955",
        "drosophila": "NCBITaxon:7227", "fly": "NCBITaxon:7227", "flies": "NCBITaxon:7227",
        "c. elegans": "NCBITaxon:6239", "caenorhabditis elegans": "NCBITaxon:6239",
        "worm": "NCBITaxon:6239",
        "yeast": "NCBITaxon:4932", "saccharomyces cerevisiae": "NCBITaxon:4932",
        "xenopus": "NCBITaxon:8355", "chicken": "NCBITaxon:9031",
        "xenopus laevis": "NCBITaxon:8355", "xenopus tropicalis": "NCBITaxon:8364",
        "drosophila melanogaster": "NCBITaxon:7227", "gallus gallus": "NCBITaxon:9031",
        "macaca mulatta": "NCBITaxon:9544", "sus scrofa": "NCBITaxon:9823",
        "oryctolagus cuniculus": "NCBITaxon:9986", "bos taurus": "NCBITaxon:9913",
        "canis lupus familiaris": "NCBITaxon:9615", "danio rerio": "NCBITaxon:7955",
        "macaque": "NCBITaxon:9544", "rhesus macaque": "NCBITaxon:9544",
        "dog": "NCBITaxon:9615", "pig": "NCBITaxon:9823", "rabbit": "NCBITaxon:9986",
    }},
    "tissue":       {"ontology": ["UBERON"],            "veto": False},
    "cell_type":    {"ontology": ["CL"],                "veto": False},
    "cell_line":    {"ontology": ["CVCL"],              "veto": False},
    "disease":      {"ontology": ["MONDO"],             "veto": False},
    "sex":          {"closed": frozenset({"male", "female", "both", "unspecified"}), "veto": False},
    # Named for the question, not for one of its answers.
    "system":       {"closed": frozenset({"in_vivo", "in_vitro", "ex_vivo", "in_silico",
                                          "unspecified"}), "veto": False},
    "perturbation": {"closed": frozenset({"knockout", "knockdown", "overexpression", "mutation",
                                          "small_molecule", "antibody", "ligand", "irradiation",
                                          "starvation", "none", "unspecified"}), "veto": False},
    "dose":         {"closed": frozenset({"physiological", "supraphysiological", "sub_physiological",
                                          "unspecified"}), "veto": False},
    "timepoint":    {"closed": frozenset({"acute", "sustained", "chronic", "unspecified"}),
                     "veto": False},
    # Assay is a closed family menu, not an ontology lookup: the question is what kind of measurement it
    # was. `keywords` maps a paper's phrasing onto a family by substring; longest key wins.
    "assay":        {"closed": frozenset({
                        "western_blot", "qpcr", "rt_pcr", "reporter_assay", "emsa", "chip", "chip_seq",
                        "rna_seq", "sequencing", "two_hybrid", "co_ip", "pulldown", "flow_cytometry",
                        "microscopy", "viability_assay", "proliferation_assay", "colony_formation",
                        "xenograft", "mass_spectrometry", "microarray", "elisa", "crispr_screen",
                        "computational_prediction", "structural", "unspecified"}),
                     "keywords": {
                        "western": "western_blot", "immunoblot": "western_blot",
                        "qrt-pcr": "qpcr", "rt-qpcr": "qpcr", "real-time pcr": "qpcr",
                        "real-time rt-pcr": "qpcr", "quantitative pcr": "qpcr", "taqman": "qpcr",
                        "rt-pcr": "rt_pcr", "northern": "rt_pcr",
                        "luciferase": "reporter_assay", "reporter": "reporter_assay",
                        "cat assay": "reporter_assay", "beta-galactosidase": "reporter_assay",
                        "gel mobility shift": "emsa", "gel shift": "emsa", "emsa": "emsa",
                        "electrophoretic mobility": "emsa", "footprint": "emsa",
                        "chip-seq": "chip_seq", "chip seq": "chip_seq", "cut&run": "chip_seq",
                        "cut and run": "chip_seq", "atac": "chip_seq",
                        "chip": "chip", "chromatin immunoprecipitation": "chip",
                        "rna-seq": "rna_seq", "rna seq": "rna_seq", "transcriptom": "rna_seq",
                        "sequencing": "sequencing", "sanger": "sequencing", "exome": "sequencing",
                        "two-hybrid": "two_hybrid", "two hybrid": "two_hybrid",
                        "co-immunoprecipitation": "co_ip", "coimmunoprecipitation": "co_ip",
                        "immunoprecipitation": "co_ip", "co-ip": "co_ip",
                        "pull-down": "pulldown", "pulldown": "pulldown",
                        "flow cytometry": "flow_cytometry", "facs": "flow_cytometry",
                        "annexin": "flow_cytometry", "propidium iodide": "flow_cytometry",
                        "immunofluorescence": "microscopy", "immunohistochem": "microscopy",
                        "confocal": "microscopy", "microscopy": "microscopy", "staining": "microscopy",
                        "celltiter": "viability_assay", "mtt": "viability_assay",
                        "viability": "viability_assay", "apoptosis assay": "viability_assay",
                        "brdu": "proliferation_assay", "edu": "proliferation_assay",
                        "proliferation assay": "proliferation_assay",
                        "colony formation": "colony_formation", "soft agar": "colony_formation",
                        "xenograft": "xenograft", "tumour growth": "xenograft",
                        "mass spec": "mass_spectrometry", "lc-ms": "mass_spectrometry",
                        "proteomic": "mass_spectrometry",
                        "microarray": "microarray", "elisa": "elisa",
                        "crispr screen": "crispr_screen", "shrna screen": "crispr_screen",
                        "foldx": "computational_prediction", "ddg": "computational_prediction",
                        "ddmut": "computational_prediction", "prediction": "computational_prediction",
                        "molecular dynamics": "computational_prediction",
                        "in silico": "computational_prediction", "docking": "computational_prediction",
                        "crystal": "structural", "cryo-em": "structural", "nmr": "structural",
                        "pdb": "structural"},
                     "veto": False},
}
VETO_SLOTS: frozenset[str] = frozenset(k for k, v in CONTEXT_SLOTS.items() if v.get("veto"))


# --- how strongly did the authors assert it? --------------------------
# Hedged claims are kept and labelled rather than deferred; a prediction stored indistinguishably from a
# measurement cannot be told apart afterwards. `certainty` is what the source claimed, one input to the
# confidence the system computes, and is not itself a confidence.
CERTAINTY: dict[str, float] = {
    "demonstrated":  1.00,   # the authors show it
    "suggested":     0.60,   # data are consistent with it; the authors hedge ("suggests", "may")
    "predicted":     0.35,
    "hypothesized":  0.20,   # proposed, untested
}

# --- how much of the subject set does the claim cover? ----------------
# "Most exon-19 mutations are destabilizing" and "two exon-19 variants are stabilizing" are both true of one
# group and must not be stored as a contradiction. The quantifier is optional (absent means "not a group
# claim") and absent is never read as `all`. It says what would falsify the claim, not how confident it
# is, and it is not in the identity key, so a paper that says "most" and one that says nothing still
# merge; it is consulted only when deciding whether two opposite-signed claims conflict.
QUANTIFIERS: frozenset[str] = frozenset({"all", "most", "some"})

# A universal is refuted by one counterexample, so `all` vs anything opposite is a real conflict; `most` vs
# `some` is not.
def quantifiers_conflict(a: str, b: str) -> bool:
    """Do two opposite-signed claims still disagree, given how much of the set each covers?"""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return True
    if a == "some" and b == "some":
        return False                   # "some do" and "some don't" are both true of most real sets
    if {a, b} == {"most", "some"}:
        return False                   # the exception does not refute the tendency
    return True                        # `all` against anything opposite is a genuine counterexample


# --- genomic features -----------------------------------------------------------------
# Sub-genic features exist in neither HGNC nor GO. Surface word -> SO CURIE; keys are lowercase and
# singular. SO has no term for `super_enhancer`, `Alu_element`, `estrogen_response_element` or
# factor-specific binding sites, so those ground as the generic type with the specific name in the
# designator.
SO_FEATURE_TYPES: dict[str, str] = {
    "intron": "SO:0000188", "exon": "SO:0000147",
    "promoter": "SO:0000167", "enhancer": "SO:0000165",
    "silencer": "SO:0000625", "insulator": "SO:0000627",
    "5' utr": "SO:0000204", "5'utr": "SO:0000204", "five prime utr": "SO:0000204",
    "3' utr": "SO:0000205", "3'utr": "SO:0000205", "three prime utr": "SO:0000205",
    "cpg island": "SO:0000307",
    "binding site": "SO:0000235", "tf binding site": "SO:0000235",
    "transcription factor binding site": "SO:0000235",
    "response element": "SO:0002205", "androgen response element": "SO:0001853",
    "estrogen response element": "SO:0002205",   # SO has no ERE term; "estrogen" goes in the designator
    "sine element": "SO:0000206", "alu": "SO:0000206", "alu element": "SO:0000206",
    "splice site": "SO:0000162", "polyadenylation signal": "SO:0000551",
    "locus control region": "SO:0000037", "transcription start site": "SO:0000315",
    "tss": "SO:0000315", "regulatory region": "SO:0005836",
    "cis-regulatory element": "SO:0005836", "regulatory element": "SO:0005836",
    "origin of replication": "SO:0000296",
}

# How a feature's identity was anchored, strongest first; recorded on the node so a coordinate-anchored
# merge is visibly better evidence than a prose-anchored one.
FEATURE_TIERS: tuple[str, ...] = ("coordinates", "accession", "designator", "generic")

