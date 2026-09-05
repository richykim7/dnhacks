"""The claim atom: the typed model every extracted assertion must satisfy before it can enter the graph.

An identity key may contain only closed vocabularies or resolved identifiers, never free text, so that two
papers asserting the same thing land on one row. Two levels of identity: `abstract_key` (subject, object,
aspect) is the question being asked; `claim_key` adds relation class, predicate and entity states and names
one distinct assertion. Four objects: Paper -> Experiment -> Evidence -> Claim, with the Experiment shared
across the claims it grounds.
"""
from __future__ import annotations

import hashlib
import re

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from dnhacksbio.litmap.attribution import ATTRIBUTIONS, PRIOR, UNCLEAR
from dnhacksbio.litmap.vocab import (
    ASPECT_REWRITES, CLINICAL_ENDPOINTS, CONTEXT_PROVENANCE, CONTEXT_SLOTS, DIRECTIONAL_PROCESSES,
    EXPERIMENTAL_PHENOTYPES,
    DOC_TYPES, EVIDENCE_TYPES, FUNCTIONAL_STATES, INHERITANCE_ALLOWED, MECHANISMS, OBJECT_ASPECTS,
    PREDICATES, STUDY_TYPES, VETO_SLOTS, canonical_predicate, classify_form,
    invert_predicate,
)

_CURIE = re.compile(r"^[A-Za-z][A-Za-z0-9._]*:[A-Za-z0-9][A-Za-z0-9._\-]*$")


class DeferralError(ValueError):
    """Raised when a claim cannot be built under the schema rules. Callers catch it and write a
    `Deferral`; nothing is coerced, dropped or guessed."""


class _Model(BaseModel):
    """Base that surfaces one exception type (`DeferralError`) to callers, unwrapping pydantic's
    ValidationError at construction."""

    def __init__(self, **data):
        try:
            super().__init__(**data)
        except ValidationError as e:
            raise DeferralError(str(e)) from e


# ---------------------------------------------------------------------------------------------------
# Entities ---------------------------------------------------------------------------------------------------
class EntityState(_Model):
    """A mutant form is a different actor from the wild-type form."""
    functional: str = "unknown"     # the safe default: unknown blocks refinement, general licenses it
    variant: str = ""      # HGVS when the paper names one, e.g. "p.Leu858Arg"
    isoform: str = ""      # a real isoform, a kind of the protein, e.g. "isoform-alpha", "beta", "v7"
    # A lab construct: a piece of the protein, or the intact protein named to contrast with a piece ("dbd",
    # "delta283-595", "full-length"). A part is not a kind, so it never licenses a refinement link.
    protein_construct: str = ""

    @model_validator(mode="before")
    @classmethod
    def _split_isoform_from_construct(cls, data):
        """Route a construct out of the isoform slot at construction, via `vocab.classify_form`, so stored
        rows land in the right field on load."""
        if not isinstance(data, dict) or data.get("protein_construct"):
            return data
        kind, value = classify_form(str(data.get("isoform") or ""))
        if kind == "construct":
            data = {**data, "isoform": "", "protein_construct": value}
        return data

    @field_validator("functional")
    @classmethod
    def _known_state(cls, v: str) -> str:
        v = (v or "unknown").strip().lower()
        if v == "unspecified":
            v = "unknown"            # the ambiguous word is never stored
        if v not in FUNCTIONAL_STATES:
            raise DeferralError(f"unknown functional state {v!r}; allowed: {sorted(FUNCTIONAL_STATES)}")
        return v

    def key(self) -> str:
        """`variant`, `isoform` and `construct` are normalised and included: an L858R claim is not an T790M
        claim, and an isolated kinase domain is not the full protein."""
        return (f"{self.functional}/{self.variant.strip().lower()}/{self.isoform.strip().lower()}"
                f"/{self.protein_construct.strip().lower()}")

    def is_specified(self) -> bool:
        """Does this state pin the actor down to a particular form?"""
        return self.functional not in ("unspecified", "unknown", "general") or bool(
            self.variant or self.isoform or self.protein_construct)

    def is_general(self) -> bool:
        """Is this an explicit claim about the gene as a whole? Only a `general` state may be the broad
        side of a refinement link; an unidentified actor cannot be."""
        return self.functional == "general" and not (
            self.variant or self.isoform or self.protein_construct)


class EntityRef(_Model):
    """A resolved entity. `curie` is an identifier, never a label. `kind` decides what the entity may be
    used as: an `entity` may carry state and take an object aspect; a `process` is the object and takes no
    aspect; an `endpoint` is legal only as the object of a `predictive` claim.
    """
    curie: str
    label: str = ""
    kind: str = "entity"
    state: EntityState = Field(default_factory=EntityState)
    feature_type: str = ""      # SO CURIE, set when this ref is a genomic feature or a generic
                                # feature mention qualifying a gene ("EGFR introns")
    feature_tier: str = ""      # how the identity was anchored; see vocab.FEATURE_TIERS

    @field_validator("curie")
    @classmethod
    def _resolved(cls, v: str) -> str:
        v = (v or "").strip()
        if not _CURIE.match(v):
            raise DeferralError(
                f"unresolved entity {v!r}: identity keys admit only resolved identifiers. "
                "Route to the deferral queue as a Lead.")
        return v

    def key(self) -> str:
        """`feature_type` is in the key, including on the generic form: a property of the introns is not a
        property of the gene."""
        f = f".{self.feature_type}" if self.feature_type else ""
        return f"{self.curie}{f}[{self.state.key()}]"

    @classmethod
    def feature(cls, parent_curie: str, so_type: str, designator: str = "",
                tier: str = "designator", label: str = "") -> EntityRef:
        """A sub-genic feature, identified by the composite key FEATURE:<parent gene>.<SO type>.<designator>.

        A feature earns its own node only when the paper identifies a particular one ("EGFR intron 1"). A
        generic mention ("EGFR intronic sequences") returns the parent gene carrying the SO term as a
        qualifier, which is Biolink's convention; use `tier='generic'`. `tier` records how the identity was
        anchored (coordinates, accession, or the paper's own designator) and is not part of the key, so two
        papers naming the same intron by number merge.
        """
        from dnhacksbio.litmap.vocab import FEATURE_TIERS
        if tier not in FEATURE_TIERS:
            raise DeferralError(f"unknown feature tier {tier!r}; allowed: {list(FEATURE_TIERS)}")
        if not _CURIE.match(parent_curie or ""):
            raise DeferralError(f"genomic feature needs a resolved parent gene, got {parent_curie!r}")
        if not _CURIE.match(so_type or ""):
            raise DeferralError(f"genomic feature needs an SO type CURIE, got {so_type!r}")
        if tier == "generic" or not designator:
            return cls(curie=parent_curie, label=label or parent_curie, kind="entity",
                       feature_type=so_type, feature_tier="generic")
        slug = re.sub(r"[^a-z0-9]+", "-", designator.strip().lower()).strip("-")
        if not slug:
            raise DeferralError(f"feature designator {designator!r} slugs to nothing")
        composite = f"{parent_curie}.{so_type}.{slug}".replace(":", "-")
        return cls(curie=f"FEATURE:{composite}", label=label or f"{parent_curie} {so_type} {designator}",
                   kind="feature", feature_type=so_type, feature_tier=tier)

    @classmethod
    def endpoint(cls, name: str) -> EntityRef:
        n = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
        if n in EXPERIMENTAL_PHENOTYPES:
            # a phenotype, not an endpoint: it may be caused as well as predicted, so it is exempt from the
            # predictive-only rule
            return cls(curie=f"PHENOTYPE:{n}", label=n, kind="phenotype")
        if n not in CLINICAL_ENDPOINTS:
            raise DeferralError(f"unknown clinical endpoint {n!r} (note: 'poor prognosis' is not an "
                                "endpoint; it normalises to overall_survival at polarity -1)")
        return cls(curie=f"ENDPOINT:{n}", label=n, kind="endpoint")


# ---------------------------------------------------------------------------------------------------
# Context ---------------------------------------------------------------------------------------------------
class ContextValue(_Model):
    """One context slot, with how it was obtained. Most papers state the system once in the Methods and
    then write 'EGFR activated GRB2' for the rest of the paper, so provenance matters."""
    value: str                      # a CURIE, or a member of the slot's closed set
    label: str = ""
    provenance: str = "stated"
    quote: str = ""                 # the passage this came from (required for stated/inherited)
    inherited_from: str = ""        # e.g. "methods"; only when provenance == 'inherited'

    @field_validator("provenance")
    @classmethod
    def _known_prov(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in CONTEXT_PROVENANCE:
            raise DeferralError(f"unknown context provenance {v!r}")
        return v


class Context(_Model):
    """A bundle of typed slots. An absent slot means the paper did not say, which is not a claim of
    universality."""
    slots: dict[str, ContextValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_slots(self):
        for name, cv in self.slots.items():
            spec = CONTEXT_SLOTS.get(name)
            if spec is None:
                raise DeferralError(f"unknown context slot {name!r}; allowed: {sorted(CONTEXT_SLOTS)}")
            closed = spec.get("closed")
            if closed is not None:
                if cv.value not in closed:
                    raise DeferralError(f"slot {name!r} takes a closed value; got {cv.value!r}")
            elif not _CURIE.match(cv.value):
                raise DeferralError(
                    f"slot {name!r} needs a resolved identifier in {spec['ontology']}; got {cv.value!r}")
        return self

    def specified(self) -> dict[str, str]:
        """Only slots the paper pinned down. Unspecified slots are absent, never 'any'."""
        return {k: v.value for k, v in sorted(self.slots.items())
                if v.provenance != "unspecified" and v.value}

    def scope_key(self) -> str:
        """The context part of claim identity, built from specified slots only."""
        return ";".join(f"{k}={v}" for k, v in self.specified().items())


# ---------------------------------------------------------------------------------------------------
# The claim
# ---------------------------------------------------------------------------------------------------
class ClaimSpine(_Model):
    """The machine-comparable core: every component is a resolved identifier, a closed vocabulary term or
    an integer, never free text."""
    subject: EntityRef
    predicate: str
    object: EntityRef
    object_aspect: str = ""          # "" when the object is a process/endpoint (it has no properties)

    # The source's own encoding before `_direction_lives_in_one_place` normalised it. These are outside the
    # key and are carried down onto the evidence rows by `Claim`, since they are facts about one source's
    # wording; two sources can reach one claim by different routes.
    aspect_said: str = ""            # e.g. "degradation" when the stored aspect is "abundance"
    mechanism_term: str = ""         # the direction-free route implied by that word (vocab.MECHANISMS)
    object_said: str = ""            # the directional process CURIE, when one was demoted to its parent
    predicate_said: str = ""         # the predicate before the flip; set only when a flip happened
    # `relation_class` and `polarity` are derived from the predicate, not stored beside it, so they cannot
    # disagree with it. Context is not part of the key: what splits an edge is the result (increases,
    # decreases, no_effect_on), and "same result, different setting" is corroboration, not conflict.

    @model_validator(mode="before")
    @classmethod
    def _direction_lives_in_one_place(cls, data):
        """Keep direction in one place, at construction.

        Some aspect words carry direction inside themselves (`degradation`), and some GO process terms do
        the same as sibling CURIEs (`protein stabilization` / `protein destabilization`), so the same finding
        could sit at two identity keys. Each is rewritten onto the direction-free quantity with the sign
        moved into the predicate. This runs before field validation, so `degradation` is accepted as input
        and never stored. The flip is a property of the word, never a per-claim judgement, and the source's
        wording is kept on `aspect_said`/`predicate_said` so any flip stays auditable against the quote.
        """
        if not isinstance(data, dict):
            return data
        d = dict(data)
        flip = False

        raw = str(d.get("object_aspect") or "").strip().lower().replace(" ", "_").replace("-", "_")
        rule = ASPECT_REWRITES.get(raw)
        if rule:
            aspect, mech, flip_aspect = rule
            d["object_aspect"] = aspect
            d["aspect_said"] = d.get("aspect_said") or raw
            d["mechanism_term"] = d.get("mechanism_term") or mech
            flip ^= flip_aspect

        obj = d.get("object")
        curie = obj.get("curie") if isinstance(obj, dict) else getattr(obj, "curie", "")
        demote = DIRECTIONAL_PROCESSES.get(curie or "")
        if demote:
            parent, label, flip_obj = demote
            fields = {"curie": parent, "label": label}
            d["object"] = {**obj, **fields} if isinstance(obj, dict) else obj.model_copy(update=fields)
            d["object_said"] = d.get("object_said") or curie
            flip ^= flip_obj

        if flip:
            # Canonicalise first: the surface word may be `induces`, and only `increases` has a twin.
            said = str(d.get("predicate") or "")
            p = canonical_predicate(said)
            if p is not None:
                # A sign-0 predicate (`regulates`, `no_effect_on`) has no sign to flip and moves across
                # unchanged.
                flipped = invert_predicate(p)
                if flipped:
                    d["predicate"] = flipped
                    d["predicate_said"] = d.get("predicate_said") or said
        return d

    @field_validator("mechanism_term")
    @classmethod
    def _known_mechanism(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v and v not in MECHANISMS:
            raise DeferralError(f"unknown mechanism {v!r}; allowed: {sorted(MECHANISMS)}")
        return v

    @field_validator("predicate")
    @classmethod
    def _known_predicate(cls, v: str) -> str:
        p = canonical_predicate(v)
        if p is None:
            raise DeferralError(f"unknown predicate {v!r}; deferred rather than coerced")
        return p

    @field_validator("object_aspect")
    @classmethod
    def _known_aspect(cls, v: str) -> str:
        v = (v or "").strip().lower().replace(" ", "_").replace("-", "_")
        if v and v not in OBJECT_ASPECTS:
            extra = (" (that word carries direction and is rewritten onto a quantity before this "
                     "check runs)"
                     if v in ASPECT_REWRITES else "")
            raise DeferralError(
                f"unknown object aspect {v!r}{extra}; allowed: {sorted(OBJECT_ASPECTS)}")
        return v

    @property
    def relation_class(self) -> str:
        """What kind of statement this is, read off the canonical predicate."""
        return PREDICATES[self.predicate][0]

    @property
    def polarity(self) -> int:
        """The direction, read off the canonical predicate."""
        return PREDICATES[self.predicate][1]

    @model_validator(mode="after")
    def _coherent(self):
        # A process or an endpoint is the object and takes no aspect. `pathological_process` is a process
        # with a separate owner, and every process rule applies to it.
        if self.object.kind in ("process", "pathological_process", "endpoint") and self.object_aspect:
            raise DeferralError(
                f"object kind {self.object.kind!r} takes no aspect (got {self.object_aspect!r}): "
                "a process is the object, not a property of anything.")
        # A tissue or cell type is a setting, not a molecule, so it takes no aspect. An anatomy object with
        # no aspect stays legal ("EGFR loss increases metastasis to liver").
        if self.object.kind in ("anatomy", "cell_type") and self.object_aspect:
            raise DeferralError(
                f"object {self.object.label!r} is a {self.object.kind}, which cannot have "
                f"{self.object_aspect!r}; a tissue is the setting a thing was measured in. Re-encode as "
                f"{self.subject.label!r} [{self.object_aspect}] with "
                f"context.{'tissue' if self.object.kind == 'anatomy' else 'cell_type'}="
                f"{self.object.label!r}.")
        if self.relation_class == "predictive" and self.object.kind not in ("endpoint", "phenotype"):
            raise DeferralError("a `predictive` claim's object must be a clinical endpoint or a "
                                "phenotype")
        if self.object.kind == "endpoint" and self.relation_class != "predictive":
            raise DeferralError("a clinical endpoint is an object only for `predictive` claims; in a "
                                "causal claim the endpoint is an outcome measure on the evidence")
        return self

    # --- identity -------------------------------------------------------------------------------
    def abstract_key(self) -> str:
        """The question: does subject affect this property of object? Context-free, polarity-free,
        state-free. The level at which prior claims are found and contradictions detected."""
        return "|".join([self.subject.curie, self.object.curie, self.object_aspect])

    def claim_key(self) -> str:
        """One distinct assertion: subject, object, aspect, relation class, canonical predicate and entity
        states. The canonical predicate carries direction (`represses`, `inhibits` and `abolishes` all
        canonicalise to `decreases` first), so polarity is not in the key. Context is not in the key; entity
        state is, because mutant and wild-type forms are different actors.
        """
        return "|".join([self.subject.key(), self.object.key(), self.object_aspect,
                         self.relation_class, self.predicate])

    def claim_id(self) -> str:
        return hashlib.sha256(self.claim_key().encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------------------------------
# Experiment / Evidence
# ---------------------------------------------------------------------------------------------------
class Experiment(_Model):
    """What was done, shared across every claim it grounds. Quotable-or-null: a quantitative value is
    stored only if it appears verbatim in `quote`; otherwise it goes to the deferral queue."""
    experiment_id: str
    source_ref: int
    unit: str = ""                 # e.g. "HeLa cells"
    intervention: str = ""
    control: str = ""
    readout: str = ""
    assay: str = ""
    timepoint: str = ""
    n: int | None = None
    effect: str = ""               # verbatim, e.g. "-1.4 log2FC"
    uncertainty: str = ""          # verbatim, e.g. "95% CI 1.2-2.7"
    statistic: str = ""
    quote: str = ""

    @model_validator(mode="after")
    def _quotable_or_null(self):
        q = (self.quote or "")
        for field in ("effect", "uncertainty", "statistic"):
            val = getattr(self, field)
            if val and val not in q:
                raise DeferralError(
                    f"experiment {field}={val!r} does not appear verbatim in the stored quote "
                    "(quotable-or-null); defer the number rather than storing it unchecked")
        if self.n is not None and str(self.n) not in q:
            raise DeferralError(f"experiment n={self.n} does not appear verbatim in the stored quote")
        return self


class Evidence(_Model):
    """The attestation: this source, in these exact words, asserts this claim. A null `experiment_id` is
    the difference between a finding and a retelling."""
    claim_id: str
    source_ref: int
    source_label: str = ""
    experiment_id: str | None = None
    quote: str
    section: str = ""
    predicate_said: str = ""     # the surface predicate this source used, before canonicalisation
    # `aspect_said` is what the paper's wording implied ("degradation" where the claim is stored on
    # `abundance`) and `mechanism_term` the direction-free route that word names. They live on the evidence
    # because two sources can reach one claim by different routes.
    aspect_said: str = ""
    mechanism_term: str = ""
    evidence_type: str = "unspecified"
    study_type: str = "unspecified"
    context: Context = Field(default_factory=Context)

    # `quantifier`: how much of the subject set this source's claim covers; blank means "not a group claim"
    # and is never read as `all`. Outside the identity key, consulted only when deciding whether two
    # opposite-signed claims conflict. `certainty`: how strongly the source asserted it, an input to the
    # computed confidence. `attribution`: whose finding it is, from `attribution.classify`.
    quantifier: str = ""
    certainty: str = "demonstrated"
    certainty_basis: list[str] = Field(default_factory=list)
    certainty_agreed: bool | None = None

    attribution: str = UNCLEAR                            # own | prior | unclear
    attribution_basis: list[str] = Field(default_factory=list)   # which signals fired
    attribution_agreed: bool | None = None                # True/False/None = agreed/disagreed/never asked

    # What this evidence leans on: `cites` holds identities (DOI:/PMID:/AY:/SRC:), `cite_markers` the
    # verbatim markers. Two evidence rows sharing a `cites` entry are echoes of one source.
    cites: list[str] = Field(default_factory=list)
    cite_markers: list[str] = Field(default_factory=list)

    extractor: str = "unspecified"
    extractor_conf: float = Field(default=0.5, ge=0.0, le=1.0)
    prompt_version: str = ""

    @field_validator("mechanism_term")
    @classmethod
    def _known_mechanism(cls, v: str) -> str:
        """Closed here as well as on the spine."""
        v = (v or "").strip().lower()
        if v and v not in MECHANISMS:
            raise DeferralError(f"unknown mechanism {v!r}; allowed: {sorted(MECHANISMS)}")
        return v

    @field_validator("quantifier")
    @classmethod
    def _known_quantifier(cls, v: str) -> str:
        from dnhacksbio.litmap.vocab import QUANTIFIERS
        v = (v or "").strip().lower()
        if v and v not in QUANTIFIERS:
            raise DeferralError(f"unknown quantifier {v!r}; allowed: {sorted(QUANTIFIERS)} or blank")
        return v

    @field_validator("certainty")
    @classmethod
    def _known_certainty(cls, v: str) -> str:
        from dnhacksbio.litmap.vocab import CERTAINTY
        if v not in CERTAINTY:
            raise DeferralError(f"unknown certainty {v!r}; allowed: {sorted(CERTAINTY)}")
        return v

    @field_validator("attribution")
    @classmethod
    def _known_attr(cls, v: str) -> str:
        if v not in ATTRIBUTIONS:
            raise DeferralError(f"unknown attribution {v!r}; allowed: {sorted(ATTRIBUTIONS)}")
        return v

    @model_validator(mode="after")
    def _echo_has_no_experiment(self):
        """A restatement cannot carry an experiment: the authors did not run one."""
        if self.attribution == PRIOR and self.experiment_id:
            raise DeferralError(
                f"evidence attributed to PRIOR work carries experiment {self.experiment_id!r}; a paper "
                "restating someone else's result has no experiment of its own")
        return self

    @field_validator("evidence_type")
    @classmethod
    def _known_ev(cls, v: str) -> str:
        if v not in EVIDENCE_TYPES:
            raise DeferralError(f"unknown evidence type {v!r}")
        return v

    @field_validator("study_type")
    @classmethod
    def _known_study(cls, v: str) -> str:
        if v not in STUDY_TYPES:
            raise DeferralError(f"unknown study type {v!r}")
        return v

    @model_validator(mode="after")
    def _review_has_no_experiment(self):
        if self.study_type == "review_statement" and self.experiment_id:
            raise DeferralError("a review_statement carries no experiment of its own")
        return self


class Claim(_Model):
    """One distinct assertion + its accumulated evidence."""
    spine: ClaimSpine
    mechanism: str = ""             # free text; never in the key
    status: str = "extracted"
    novelty_class: str = "unassessed"
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _carry_rewrite_down(self):
        """Move the spine's rewrite record onto the evidence rows, where it is persisted. An evidence row
        that already carries its own values is left alone."""
        for ev in self.evidence:
            if self.spine.aspect_said and not ev.aspect_said:
                ev.aspect_said = self.spine.aspect_said
            if self.spine.mechanism_term and not ev.mechanism_term:
                ev.mechanism_term = self.spine.mechanism_term
            # The flipped-away word must reach the evidence row, or the graph falls back to the claim's
            # predicate, which after a flip is the opposite of what this source wrote.
            if self.spine.predicate_said and not ev.predicate_said:
                ev.predicate_said = self.spine.predicate_said
        return self

    @property
    def claim_id(self) -> str:
        return self.spine.claim_id()


class Deferral(_Model):
    """Something the pass could not decide. Neither guessed nor dropped."""
    source_ref: int
    reason: str
    raw: dict = Field(default_factory=dict)
    candidates: list[str] = Field(default_factory=list)
    quote: str = ""
    extractor: str = "unspecified"
    prompt_version: str = ""


# ---------------------------------------------------------------------------------------------------
# Helpers used by the extractor / integration passes
# ---------------------------------------------------------------------------------------------------
def inheritance_allowed(doc_type: str) -> bool:
    """Context inheritance is off for reviews: a restatement has no experimental system of its own, so
    propagating the paper's framing would attach a context the original experiment never had.
    """
    if doc_type not in DOC_TYPES:
        raise DeferralError(f"unknown doc_type {doc_type!r}")
    return doc_type in INHERITANCE_ALLOWED


