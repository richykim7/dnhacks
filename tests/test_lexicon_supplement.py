from dnhacksbio.litmap.lexicon_supplement import SUPPLEMENT, supplement_lookup


def test_owner_gate_prevents_category_correction_by_alias():
    assert supplement_lookup("ROS", ("GO",)) is None
    assert supplement_lookup("ROS", ("CHEBI",))["curie"] == "CHEBI:26523"
    assert supplement_lookup("ERK1/2", ("HGNC",)) is None
    assert supplement_lookup("ERK1/2", ("FPLX",))["curie"] == "FPLX:ERK"
    assert supplement_lookup("ROS", ()) is None


def test_population_subtypes_remain_distinct_and_are_not_cl_ids():
    hits = [supplement_lookup(name, ("LOCALCELL",)) for name in ("CAF", "iCAF", "myCAF", "apCAF")]
    assert len({h["curie"] for h in hits}) == 4
    assert all(h["curie"].startswith("LOCALCELL:") for h in hits)
    assert supplement_lookup("iCAF", ("CL",)) is None
    assert supplement_lookup("myofibroblast", ("LOCALCELL",)) is None


def test_pathological_numerical_outcome_is_not_normal_duplication():
    amplification = supplement_lookup("centrosome amplification", ("LOCALPHENO",))
    clustering = supplement_lookup("centrosome clustering", ("LOCALPHENO",))
    assert amplification["curie"] != clustering["curie"]
    assert supplement_lookup("centrosome duplication") is None
    assert supplement_lookup("centrosome amplification", ("GO",)) is None


def test_spelling_normalization_preserves_chemical_specificity():
    assert supplement_lookup(" N–acetyl  cysteine ", ("CHEBI",))["curie"] == "CHEBI:28939"
    assert supplement_lookup("N-acetyl-D-cysteine", ("CHEBI",)) is None


def test_reviewed_records_carry_definitions_and_primary_provenance():
    assert len({term.curie for term in SUPPLEMENT}) == len(SUPPLEMENT)
    for term in SUPPLEMENT:
        assert term.definition and term.sources and term.coverage_note
        assert all(url.startswith("https://") for url in term.sources)
        assert supplement_lookup(term.label, (term.curie.partition(":")[0],))["curie"] == term.curie


def test_reagents_do_not_collapse_into_related_drug_or_inhibitor_class():
    assert supplement_lookup("imidazole ketone erastin", ("LOCALREAGENT",))["curie"] == "LOCALREAGENT:imidazole_ketone_erastin"
    assert supplement_lookup("erastin", ("LOCALREAGENT",)) is None
    assert supplement_lookup("pantothenate kinase inhibitor", ("LOCALREAGENT",)) is None
    assert supplement_lookup("PANKi", ("LOCALREAGENT",)) is None
    assert supplement_lookup("Calbiochem 537983", ("LOCALREAGENT",))["curie"] == "LOCALREAGENT:panki_537983"
    assert supplement_lookup("cyst(e)inase", ("HGNC",)) is None


def test_abnormal_and_assay_outcomes_are_not_general_processes():
    assert supplement_lookup("chromosome segregation", ("LOCALPHENO",)) is None
    assert supplement_lookup("fibrosis", ("LOCALPHENO",)) is None
    assert supplement_lookup("stemness", ("LOCALPHENO",)) is None
    assert supplement_lookup("proliferation", ("LOCALPHENO",)) is None


def test_residual_outcomes_preserve_lesion_and_genomic_meaning():
    assert supplement_lookup("DNA damage", ("MESH",))["curie"] == "MESH:D004249"
    assert supplement_lookup("DNA damage", ("GO",)) is None
    assert supplement_lookup("DNA damage response", ("MESH",)) is None
    assert supplement_lookup("tumour cell invasion", ("MESH",))["curie"] == "MESH:D009361"
    assert supplement_lookup("whole genome duplication", ("LOCALPHENO",))["curie"] == "LOCALPHENO:whole_genome_duplication"
    assert supplement_lookup("DNA replication", ("LOCALPHENO",)) is None
    assert supplement_lookup("tumor heterogeneity", ("LOCALPHENO",)) is None
    assert supplement_lookup("angiogenesis", ("LOCALPHENO",)) is None


def test_disease_subtype_keeps_grade_without_fake_mondo_equivalence():
    hit = supplement_lookup("HGSOC", ("LOCALDISEASE",))
    assert hit["curie"] == "LOCALDISEASE:hgsoc"
    assert hit["kind"] == "disease"
    assert "NCIT:C105555" in hit["provenance"]["coverage_note"]
    assert supplement_lookup("HGSOC", ("MONDO",)) is None
    assert supplement_lookup("ovarian serous adenocarcinoma", ("LOCALDISEASE",)) is None
    assert supplement_lookup("ovarian cancer cell lines", ("CVCL",)) is None
