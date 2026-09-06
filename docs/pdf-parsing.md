# Structured document parsing

`dnhacksbio.litmap.document_parse.parse_document_bytes(data, format, output_dir=None)` returns
`text`, `markdown`, `figures`, `parser`, `parser_version`, `pages`, and `warnings`, plus
`figures_status`, `needs_ocr`, and `unreadable_pages`. XML/HTML also return `has_body`.
Install the `litmap` extra for PDF support. PDF parsing uses pinned PyMuPDF4LLM 1.28.2 and
serializes access to PyMuPDF across concurrent fetch threads.

PDF output preserves document layout in Markdown and saves rendered picture/formula regions,
including vector graphics, when an output directory is supplied. Each figure records its relative
filename, one-based page number, bounding box in PDF page coordinates, and region type.
Detected regions are not guaranteed to correspond one-to-one with numbered figures or panels.
Captions remain absent when the parser provides no reliable association; they are not fabricated.
The image filenames are content-derived and document-controlled paths cannot escape the parser's
scratch directory. Local corpus PDF ingestion saves pictures in `<document-stem>_assets/`.
Callers should retain the original PDF and source URL/license/hash alongside the result.

`figures_status` distinguishes `extracted`, `referenced`, `none`, and `not_extracted`.
Without an output directory, PDF picture metadata remains available but image bytes are not
persisted. Plain text and Markdown do not establish the absence of figures and report
`not_extracted`. XML/HTML figure metadata includes the source caption, label and graphic URL;
relative URLs remain unresolved and the downloader owns asset retrieval. No remote figure is
fetched by the parser. The figure manifest is separate from the text-only claim extractor:
saving an image does not mean its plotted measurements have been interpreted.

The JATS parser preserves paragraph/section boundaries, table rows and back-matter references.
HTML requires an identifiable article region and removes navigation/script/style content.
It does not treat a generic publisher landing page as an article. XML declared entities are
rejected. These structural parsers do not by themselves certify publication identity or completeness.

PDFs with textless pages, or image-dominated pages with only a short native header, report `needs_ocr` and their page numbers; completely textless PDFs
fail explicitly. This conservative flag can include legitimate figure-only pages and requires
inspection before accepting a paper as complete. Mixed scanned/native documents must not be
silently counted as complete. Optional `DNHACKS_PDF_OCR=1` uses a locally installed CPU
Tesseract backend and its language data. Missing OCR dependencies produce a warning and retain
the unreadable-page signal. No OCR model downloads are initiated. Local corpus ingestion
rejects PDFs still reporting unreadable pages.

The PDF packages carry the PyMuPDF AGPL/commercial licensing already present in this project;
this is not a permissively licensed replacement. The extension adds CPU layout dependencies,
including ONNX Runtime and PyMuPDF Layout. See the [official API](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html)
and [package license](https://pypi.org/project/pymupdf4llm/).
