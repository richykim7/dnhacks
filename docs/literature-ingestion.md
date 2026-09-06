# Literature retrieval and readable source artifacts

The project builder searches Europe PMC using each configured query and OpenAlex using the plain
project theme. OpenAlex's query language does not accept Europe PMC field names, so the builder does
not forward fielded queries to that service. Seed DOIs are looked up in both services. Each discovery
channel is bounded to 180 results; a shortfall means broaden or split discovery queries, not that the
field contains no more papers. The capture-recapture estimate describes discovered records, not
full-text availability, and the channels are correlated.

DOIs are normalized (including DOI URL prefixes), and records sharing DOI, PMID, PMCID or OpenAlex ID
are merged before ranking. Metadata and available OA locations are combined. Publication dates are
retained when supplied; existing inclusive publication-year filters still apply. No first-publication
or temporal-holdout policy is inferred from these dates.

## Full-text selection

For a corpus that must contain at least 100 readable papers, set `n_papers` to 100 or higher and
`full_text_only` to true. The builder fetches candidates in relevance order, prioritizing seed DOIs,
then replaces unavailable or rejected sources with lower-ranked candidates. It enforces the requested
minimum **before paid extraction**. If discovery is exhausted, the build fails with the achieved count
and retains its retrieval artifacts. Abstracts never satisfy this minimum. Identical downloaded
content and resolved identifier aliases cannot inflate the accepted count. An uploaded copy with the
same DOI as a fetched paper is skipped.

Setting `full_text_only` to false permits explicitly labeled abstract-only documents; this setting
must not be used for a full-text-only corpus. Uploads are handled separately and do not reduce the
minimum requested number of retrieved full texts.

Retrieval tries Europe PMC XML, PMC efetch XML and PMC article HTML, followed by all OA PDF locations
and then OA landing pages found through OpenAlex and Unpaywall. A failed PDF location does not stop
other locations from being attempted. OA landing pages also expose up to five explicit
`citation_pdf_url` or `application/pdf` links; these are followed without crawling the site. Downloads have finite streaming limits (40 MiB per response;
100 MiB for PMC figure packages), request timeouts and at most three attempts on transient network,
429 or server errors. Attempts record status and parser failures without recording API credentials.

A full-text flag requires at least 1,500 readable characters and title-token agreement. XML must
contain an actual article body exceeding 800 characters; PDF/HTML must contain at least two distinct
recognized section headings. Documents flagged as needing OCR or having unreadable pages are rejected.
These conservative checks reject abstract-only records and many landing pages, but are not proof that
every visual, equation or supplement was recovered. Short letters and unusual section headings may
need a separately inspected source.

## Source retention and reuse

Before parsing, each downloaded source is saved in
`data/projects/<project>/retrieval/<hash-of-canonical-id>/`. The directory holds content-addressed raw
files, parsed `.txt` and `.md`, per-source asset directories, and `retrieval.json` containing source
URL, available license, hashes, parser/version, figure metadata and route outcomes. Rejected downloaded
sources are retained too. The parent `attempts.json` records partial build progress before extraction.

Successful cached text is reused only when its raw hash, parsed text, title and all referenced figure
files still validate. Missing or unresolved figures trigger retrieval again, allowing repair rather
than freezing a failed asset lookup permanently. Failed documents are retried on a later build. The
final `paper_list.json` is rewritten with the actual refilled selection and source provenance;
dry runs mark their list as proposed. The source metadata and final parsed text are also stored with the knowledge graph; publication dates and
asset provenance remain in the corpus manifest and retrieval sidecars.

For JATS figures with relative graphic IDs, the retriever first requests the Europe PMC
`supplementaryFiles` ZIP (which includes inline images), then tries the NCBI PMC OA package for
unresolved assets. It reads matching image members without extracting archive paths or links. Each image is content-addressed and associated
with its original figure label/caption and archive member. Recognized absolute image URLs are also
fetched. Image status distinguishes extracted, partial and referenced/unavailable assets; metadata-only
figure references must not be presented as extracted images. Markdown links point to retained assets
relative to the saved Markdown file.

## Service settings

`OPENALEX_API_KEY` is optional and read only from the process environment. `LITERATURE_CONTACT_EMAIL`
sets the contact email used for service identification and Unpaywall. Supply a real service contact
for Unpaywall; the default placeholder is not a working contact. Credentials are not read from local
configuration files. OpenAlex/Unpaywall failures degrade discovery or trigger alternate retrieval
routes and are reported, rather than being treated as evidence that a paper has no full text.

API references: [OpenAlex search](https://help.openalex.org/api/searching/),
[OpenAlex pagination](https://help.openalex.org/api/paging/),
[OpenAlex data and locations](https://help.openalex.org/data/).
