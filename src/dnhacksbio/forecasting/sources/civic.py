"""Normalize historical CIViC TSVs without fetching present-day summaries.

Therapy groups are retained whole. Old releases do not distinguish combinations,
substitutes and sequential use; absent interaction metadata remains unknown.
"""
import csv
import hashlib
import json
import re
from pathlib import Path


def stable_id(namespace: str, *parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return f"{namespace}:{hashlib.sha256(payload.encode()).hexdigest()[:20]}"


def therapy_labels(drugs: str) -> list[str]:
    """Split groups, preserving commas inside parenthesized drug aliases."""
    labels, start, depth = [], 0, 0
    for index, char in enumerate(drugs):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            labels.append(drugs[start:index])
            start = index + 1
    labels.append(drugs[start:])
    return sorted({" ".join(label.split()) for label in labels if label.strip()}, key=str.casefold)


def therapy_members(drugs: str) -> tuple[str, ...]:
    return tuple(sorted({label.casefold() for label in therapy_labels(drugs)}))


def normalize_row(row: dict[str, str], available_at: str) -> dict:
    members = therapy_members(row.get("drugs", ""))
    source_type = row.get("source_type") or ("PubMed" if row.get("pubmed_id") else "Unknown")
    citation_id = row.get("citation_id") or row.get("pubmed_id") or ""
    evidence_id = f"civic:evidence:{row['evidence_id']}"
    source = f"civic:variant:{row['variant_id']}"
    target = stable_id("civic:therapy-group", members)
    match = re.search(r"\b(?:19|20)\d{2}\b", row.get("citation", ""))
    context = {
        "evidence_id": evidence_id,
        "gene": row.get("gene", ""), "variant": row.get("variant", ""),
        "disease": row.get("disease", ""), "disease_id": row.get("doid") or None,
        "therapies": list(members),
        "drug_interaction_type": row.get("drug_interaction_type") or None,
        "evidence_type": row.get("evidence_type", ""),
        "direction": row.get("evidence_direction", ""),
        "clinical_significance": row.get("clinical_significance", ""),
        "evidence_level": row.get("evidence_level", ""),
    }
    civic_url = row.get("evidence_civic_url") or f"https://civicdb.org/links/evidence_items/{row['evidence_id']}"
    text = row.get("evidence_statement", "")
    return {
        "source": source, "target": target,
        "variant_label": f"{row.get('gene', '')} {row.get('variant', '')}".strip(),
        "gene_id": f"civic:gene:{row.get('gene_id', '')}", "gene_label": row.get("gene", ""),
        "therapy_label": ", ".join(therapy_labels(row.get("drugs", ""))),
        "eligible": bool(members and row.get("variant_id") and row.get("gene_id")
                         and row.get("evidence_type", "").casefold() == "predictive"
                         and row.get("evidence_status", "").casefold() == "accepted"
                         and row.get("is_flagged", "false").casefold() != "true"),
        "context": context,
        "evidence": {
            "id": evidence_id, "title": row.get("citation") or f"CIViC evidence {row['evidence_id']}",
            "text": text,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{citation_id}/" if source_type.casefold() == "pubmed" and citation_id else civic_url,
            "available_at": available_at,
            "publication_year": int(match.group()) if match else None,
            "source_type": source_type, "citation_id": citation_id,
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(), "contexts": [context],
        },
    }


def load_release(path: str | Path, available_at: str) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {"evidence_id", "variant_id", "gene_id", "drugs", "evidence_type", "evidence_status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CIViC release missing columns: {sorted(missing)}")
        return [normalize_row(row, available_at) for row in reader]
