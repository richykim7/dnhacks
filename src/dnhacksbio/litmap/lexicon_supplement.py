"""Versioned, reviewed vocabulary gaps, separate from downloaded owner lexicons.

External identifiers retain their ontology meaning. LOCAL identifiers are explicitly
our controlled concepts, not claimed additions to GO or CL. Definitions describe
measured phenomena/populations, never a paper's causal finding. A repair must select
the corresponding category; this table does not silently override its owner.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

VERSION = "2026-09-06.3"


@dataclass(frozen=True)
class SupplementTerm:
    curie: str
    label: str
    kind: str
    aliases: tuple[str, ...]
    definition: str
    sources: tuple[str, ...]
    coverage_note: str


def _ols(ontology: str, query: str) -> str:
    from urllib.parse import urlencode
    return "https://www.ebi.ac.uk/ols4/api/search?" + urlencode(
        {"ontology": ontology, "q": query, "rows": 40})


_CAF = "https://doi.org/10.1158/2159-8290.CD-19-0094"
_CA = "https://doi.org/10.1016/j.devcel.2018.10.026"
_CLUSTER = "https://doi.org/10.26508/lsa.202201470"
_OVARY = "https://doi.org/10.1038/s41467-023-41840-3"
_FPLX = "https://github.com/sorgerlab/famplex/blob/master/entities.csv"

SUPPLEMENT = (
    SupplementTerm("LOCALDISEASE:hgsoc", "high-grade serous ovarian carcinoma", "disease",
                   ("HGSOC", "high grade serous ovarian cancer", "ovarian high grade serous adenocarcinoma"),
                   "The high-grade serous ovarian carcinoma subtype, retaining its high-grade histological identity; "
                   "not interchangeable with all ovarian serous adenocarcinomas.",
                   (_OVARY, _ols("mondo", "ovarian high grade serous adenocarcinoma"),
                    _ols("ncit", "ovarian high grade serous adenocarcinoma")),
                   "Exact subtype verified as NCIT:C105555; absent from live MONDO owner search. MONDO:0005211 is broader."),
    SupplementTerm("MESH:D004249", "DNA Damage", "process", (),
                   "Lesions that change DNA from its intact structure; distinct from the cellular response to DNA damage.",
                   ("https://id.nlm.nih.gov/mesh/D004249.html", _ols("mesh", "DNA Damage")),
                   "Verified MeSH descriptor, tree G05.200; GO response-to-damage terms are not the lesions themselves."),
    SupplementTerm("MESH:D009361", "Neoplasm Invasiveness", "pathological_process",
                   ("tumour cell invasion", "tumor cell invasion", "tumor invasion", "tumour invasion"),
                   "Capacity of neoplastic cells to infiltrate surrounding tissue.",
                   ("https://id.nlm.nih.gov/mesh/D009361.html", _ols("mesh", "Neoplasm Invasiveness")),
                   "Verified MeSH descriptor; aliases explicitly retain neoplastic context."),
    SupplementTerm("LOCALPHENO:genome_subclonality", "genome subclonality", "process",
                   ("genomic subclonality",),
                   "The fraction of genomic segments with copy-number states present in only a subset of tumor cells, "
                   "as estimated from absolute copy-number fits in the source study; not all tumor heterogeneity.",
                   (_OVARY, _ols("go", "genome subclonality"), _ols("ncit", "Subclonal Genome to Total Tumor Tissue Genome Ratio Measurement")),
                   "No matching GO term; NCIT:C206455 independently describes the corresponding genomic-fraction measurement."),
    SupplementTerm("LOCALPHENO:whole_genome_duplication", "whole-genome duplication", "process",
                   ("whole genome duplication", "whole-genome doubling", "whole genome doubling", "WGD"),
                   "Acquisition of an additional complete genomic complement in a cell lineage, distinct from "
                   "normal S-phase DNA replication or duplication of an individual genomic segment.",
                   (_OVARY, _ols("go", "whole genome duplication"), _ols("mesh", "whole genome duplication")),
                   "No matching GO or MeSH term in live owner searches on 2026-09-06."),
    SupplementTerm("LOCALPHENO:vascular_perfusion", "vascular perfusion", "process", (),
                   "Delivery of circulating blood through a tissue's vascular bed, including intratumoral blood supply "
                   "in the source; not vessel density or angiogenesis itself.",
                   (_CAF, _ols("go", "vascular perfusion"), _ols("mesh", "vascular perfusion")),
                   "No equivalent term in GO or MeSH searches; blood circulation is broader than the tissue perfusion phenotype."),
    SupplementTerm("LOCALREAGENT:cw069", "CW069", "entity", ("CW-069",),
                   "The experimental small-molecule reagent CW069, an allosteric HSET/KIFC1 inhibitor; "
                   "the study identifies the purchased reagent as Selleckchem S7336.",
                   (_CLUSTER, _OVARY, _ols("chebi", "CW069")),
                   "No matching ChEBI term under CW069 or CW-069 in live search on 2026-09-06."),
    SupplementTerm("LOCALREAGENT:imidazole_ketone_erastin", "imidazole ketone erastin", "entity", ("IKE",),
                   "The named imidazole ketone erastin experimental compound, distinct from erastin itself.",
                   ("https://doi.org/10.1126/science.aaw9872", "https://doi.org/10.1016/j.chembiol.2019.01.008",
                    _ols("chebi", "imidazole ketone erastin")),
                   "No matching ChEBI term in live search on 2026-09-06."),
    SupplementTerm("LOCALREAGENT:cyst_e_inase", "cyst(e)inase", "entity", (),
                   "The engineered cysteine/cystine-degrading enzyme preparation named cyst(e)inase in the source, "
                   "not a generic gene or an arbitrary cysteine-metabolizing enzyme.",
                   ("https://doi.org/10.1126/science.aaw9872", _ols("chebi", "cyst(e)inase")),
                   "No matching ChEBI term in live search on 2026-09-06; engineered reagent requires its own identity."),
    SupplementTerm("LOCALREAGENT:panki_537983", "PANKi (Calbiochem 537983)", "entity",
                   ("Calbiochem 537983", "PANKi (CAS 902614-04-4)", "902614-04-4"),
                   "The specific pantothenate kinase inhibitor reagent Calbiochem 537983, CAS 902614-04-4. "
                   "Bare PANKi or generic pantothenate kinase inhibitor requires source confirmation before choosing this identity.",
                   ("https://doi.org/10.1126/science.aaw9872",
                    "https://www.caymanchem.com/product/31002/pantothenate-kinase-inhibitor",
                    _ols("chebi", "902614-04-4")),
                   "No ChEBI term for the specific reagent in live search; CHEBI:77194 describes an inhibitor class, not this compound."),
    SupplementTerm("LOCALPHENO:chromosome_missegregation", "chromosome missegregation", "process",
                   ("chromosome mis-segregation", "chromosomal missegregation"),
                   "Erroneous partitioning of chromosomes during division, distinct from normal chromosome segregation.",
                   (_OVARY, _CA, _ols("go", "chromosome missegregation")),
                   "No matching GO term in live owner search on 2026-09-06."),
    SupplementTerm("LOCALPHENO:colony_formation", "colony formation", "process",
                   ("clonogenic growth",),
                   "Formation of countable colonies from plated cells in a clonogenic culture assay; "
                   "not a direct synonym for proliferation or in-vivo tumor initiation.",
                   ("https://doi.org/10.1158/1078-0432.CCR-15-3115", _ols("go", "colony formation")),
                   "GO hits describe unrelated cooperative development or imported cell types, not the measured culture outcome."),
    SupplementTerm("LOCALPHENO:tumorsphere_formation", "tumorsphere formation", "process",
                   ("tumor sphere formation", "tumour sphere formation", "tumoursphere formation"),
                   "Formation of multicellular tumor-cell spheres under the source's sphere-culture conditions; "
                   "not proof of stem-cell identity or in-vivo tumor initiation.",
                   ("https://doi.org/10.1158/1078-0432.CCR-15-3115", _ols("go", "tumor sphere formation")),
                   "No matching GO term in live owner search on 2026-09-06."),
    SupplementTerm("LOCALPHENO:desmoplasia", "desmoplasia", "process", ("desmoplastic reaction",),
                   "Connective-tissue stromal reaction associated with neoplasia, including the collagen-rich reaction "
                   "measured by staining in the source; not all fibrosis.",
                   ("https://doi.org/10.1158/1078-0432.CCR-15-3115", _ols("mesh", "desmoplasia"),
                    _ols("mpath", "desmoplasia")),
                   "Absent from MeSH owner search; independently described by MPATH:581."),
    SupplementTerm("GO:0042613", "MHC class II protein complex", "entity",
                   ("MHC class II", "MHCII", "MHC II"),
                   "Transmembrane complex containing an MHC class II alpha chain and beta chain, with or without bound antigen.",
                   (_ols("go", "MHC class II protein complex"),),
                   "Verified GO cellular component; not a FamPlex family or a single gene."),
    SupplementTerm("LOCALPHENO:mitochondrial_respiration", "mitochondrial respiration", "process",
                   ("mitochondrial oxygen consumption",),
                   "Mitochondrial oxygen consumption measured as a cellular respiratory phenotype; "
                   "not respiratory-chain complex assembly or ATP production specifically.",
                   ("https://doi.org/10.1038/nature19084", _ols("go", "mitochondrial respiration")),
                   "GO search did not yield an equivalent term; source measures mitochondrial oxygen consumption."),
    SupplementTerm("CHEBI:26523", "reactive oxygen species", "entity", ("ROS",),
                   "Reactive oxygen-derived molecules or ions.",
                   (_ols("chebi", "reactive oxygen species"),), "Verified owner term; common abbreviation."),
    SupplementTerm("CHEBI:28939", "N-acetyl-L-cysteine", "entity",
                   ("N-acetyl cysteine", "N-acetylcysteine", "NAC", "acetylcysteine"),
                   "The N-acetylated derivative of L-cysteine.",
                   (_ols("chebi", "N-acetyl-L-cysteine"),), "Verified owner term; spelling variants."),
    SupplementTerm("FPLX:ERK", "ERK", "entity", ("ERK1/2", "ERK1 and ERK2"),
                   "ERK protein family, retaining the family rather than choosing MAPK3 alone.",
                   (_FPLX, _CA), "Verified FamPlex family."),
    SupplementTerm("FPLX:NADPH_oxidase", "NADPH oxidase", "entity", ("NADPH oxidases",),
                   "NADPH oxidase family, retaining family identity rather than choosing NOX1 alone.",
                   (_FPLX, _CA), "Verified FamPlex family."),
    SupplementTerm("LOCALPHENO:centrosome_amplification", "centrosome amplification", "process",
                   ("supernumerary centrosomes", "extra centrosomes", "increased centrosome number"),
                   "Presence of more centrosomes than the normal complement for the cell-cycle stage; "
                   "this records the numerical phenotype, not ordinary centrosome duplication.",
                   (_CA, _OVARY, _ols("go", "centrosome amplification")),
                   "No matching GO term found in live owner search on 2026-09-06."),
    SupplementTerm("LOCALPHENO:centrosome_clustering", "centrosome clustering", "process",
                   ("clustering of supernumerary centrosomes",),
                   "Coalescence of supernumerary centrosomes into spindle poles, permitting pseudo-bipolar division.",
                   (_CLUSTER, _ols("go", "centrosome clustering")),
                   "No matching GO term found in live owner search on 2026-09-06."),
    SupplementTerm("LOCALPHENO:multipolar_spindle_formation", "multipolar spindle formation", "process",
                   ("formation of multipolar spindles",),
                   "Formation of a mitotic spindle with more than two poles.",
                   (_CLUSTER, _ols("go", "multipolar spindle")),
                   "No matching GO term found in live owner search on 2026-09-06."),
    SupplementTerm("LOCALPHENO:micronucleus_formation", "micronucleus formation", "process",
                   ("micronuclei formation", "formation of micronuclei"),
                   "Formation of small extranuclear DNA-containing bodies scored separately from the main nucleus.",
                   (_OVARY, _ols("go", "micronucleus formation")),
                   "No matching GO term found in live owner search on 2026-09-06; not equivalent to chromosome segregation."),
    SupplementTerm("LOCALCELL:caf", "cancer-associated fibroblast", "cell_type",
                   ("cancer-associated fibroblasts", "CAF", "CAFs", "tumor-associated fibroblast", "tumour-associated fibroblast"),
                   "Fibroblast population associated with cancerous tissue; no specific CAF subtype is implied.",
                   (_CAF, _ols("cl", "cancer associated fibroblast"), _ols("ncit", "Cancer-Associated Fibroblast")),
                   "Absent from CL owner search; broader concept independently represented by NCIT:C168534."),
    SupplementTerm("LOCALCELL:icaf", "inflammatory cancer-associated fibroblast", "cell_type",
                   ("iCAF", "iCAFs", "inflammatory CAF", "inflammatory CAFs", "inflammatory cancer-associated fibroblasts"),
                   "Cancer-associated fibroblast population with an inflammatory cytokine/chemokine program, "
                   "distinguished from myofibroblastic and antigen-presenting CAF populations in the source study.",
                   (_CAF, _ols("cl", "inflammatory fibroblast")), "No matching subtype in live CL search on 2026-09-06."),
    SupplementTerm("LOCALCELL:mycaf", "myofibroblastic cancer-associated fibroblast", "cell_type",
                   ("myCAF", "myCAFs", "myofibroblastic CAF", "myofibroblastic CAFs", "myofibroblastic cancer-associated fibroblasts"),
                   "Cancer-associated fibroblast population with a myofibroblastic program and elevated alpha-SMA "
                   "in the source study; not equivalent to all myofibroblasts.",
                   (_CAF, _ols("cl", "myofibroblastic fibroblast")), "No matching subtype in live CL search on 2026-09-06."),
    SupplementTerm("LOCALCELL:apcaf", "antigen-presenting cancer-associated fibroblast", "cell_type",
                   ("apCAF", "apCAFs", "antigen-presenting CAF", "antigen-presenting CAFs", "antigen-presenting cancer-associated fibroblasts"),
                   "Cancer-associated fibroblast population with an MHC class II antigen-presentation program; "
                   "distinct from circulating fibrocytes and other CAF populations.",
                   (_CAF, _ols("cl", "antigen presenting fibroblast"), _ols("ncit", "Antigen-Presenting Cancer-Associated Fibroblast")),
                   "Absent from CL owner search; independently represented by NCIT:C187401."),
)


def normalize(text: str) -> str:
    """Only Unicode, hyphen/space and case normalization; no semantic stemming."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"[\s\-‐‑‒–—]+", " ", text).strip()


def supplement_lookup(text: str, namespaces: tuple[str, ...] | None = None) -> dict | None:
    """Return an unambiguous reviewed exact alias, respecting the requested owner."""
    allowed = {ns.upper() for ns in namespaces} if namespaces is not None else None
    key = normalize(text)
    matches = [term for term in SUPPLEMENT
               if (allowed is None or term.curie.partition(":")[0].upper() in allowed)
               and key in {normalize(term.label), *(normalize(a) for a in term.aliases)}]
    if len(matches) != 1:
        return None
    term = matches[0]
    return {"curie": term.curie, "label": term.label, "kind": term.kind,
            "db": term.curie.partition(":")[0], "score": 1.0, "matched": text,
            "match": "label" if key == normalize(term.label) else "synonym",
            "provenance": {"version": VERSION, "definition": term.definition,
                           "sources": list(term.sources), "coverage_note": term.coverage_note}}
