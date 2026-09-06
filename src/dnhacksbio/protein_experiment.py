"""Fail-closed registration seam for protein-group-native-v1.

A receipt queue cannot substitute for the shared canonical donor/segment ledger or
an enforced private deployment. No configurable boolean can enable this method.
"""
from .experiment_transport import QueueStore

METHOD = "protein-group-native-v1"
BLOCKERS = (
    "shared native kernel and canonical investigation-level donor/segment ledger",
    "independent sampling/preprocessing and untouched-cohort review",
    "audited external G1/G2 versus G3 metadata and at least 48 independent pairs",
    "deployment-enforced confirmation privacy",
    "measured resource, 10000-stream null diagnostics and minimum-effect power >= 80%",
)


class EvidenceUnavailable(ValueError):
    pass


def availability():
    return {"method": METHOD, "status": "unavailable", "blockers": list(BLOCKERS)}


class Store(QueueStore):
    """Reuse transport type while refusing all registrations and submissions."""

    def configure(self, *args, **kwargs):
        raise EvidenceUnavailable("Protein native evidence has not passed release gates")

    def validate_payload(self, payload):
        raise EvidenceUnavailable("Protein native evidence is unavailable")

    def _score_one(self, receipt):
        raise EvidenceUnavailable("Protein native scoring is unavailable")
