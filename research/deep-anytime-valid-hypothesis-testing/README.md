# Deep anytime-valid hypothesis testing

Teodora Pandeva, Patrick Forré, Aaditya Ramdas, and Shubhanshu Shekhar.
Proceedings of AISTATS 2024, PMLR 238:622–630.

- [Full text](paper.txt): all 22 PDF pages, including references and appendices.
- [Published PDF](paper.pdf): authoritative equations, algorithms, tables, and figures.
- [Publication and citation](https://proceedings.mlr.press/v238/pandeva24a.html).
- [PDF source](https://proceedings.mlr.press/v238/pandeva24a/pandeva24a.pdf).

Copyright 2024 the authors. Distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
as specified by the [PMLR publication agreement](https://proceedings.mlr.press/pmlr-license-agreement.html).
The PDF is unchanged. The text is a mechanical extraction with page markers and joined hyphenated
line endings; this reading guide is repository commentary, not part of the paper.

## Reading guide for agents

Search `paper.txt` for these headings; page numbers below are one-based PDF page numbers.

| Topic | Location |
| --- | --- |
| Independent two-sample setup and swap symmetry | Example 2.1, page 2 |
| Assumptions and oracle construction | Section 4.1, page 4 |
| Product batch score and learning objective | Equations (5)–(6), page 5 |
| Score first, update model afterward | Algorithm 1, page 6 |
| Consistency assumptions | Proposition 4.3, page 5 |
| Proofs | Section 10, pages 14–16 |
| Validation-batch training and transformed payoff | Section 11.1, page 18 |
| Architectures and experimental settings | Section 11, pages 18–22 |

The text preserves PDF content-stream reading order so two-column prose is not interleaved by
horizontal position. Mathematical subscripts, fractions, tables, and plot labels may still appear on
separate lines. Unmapped control characters are marked `�`. Figure graphics are in the PDF.
Consult the PDF before implementing an equation or
interpreting a chart; the text is a navigation and reading aid, not a lossless mathematical source.

For convenience, the main algorithm's equations in agent-readable notation are:

```text
payoff_theta(z) = g_theta(T1(z)) - g_theta(T2(z))
S_t = product_{z in B_t} [1 + payoff_{theta_(t-1)}(z)]
W_0 = 1
W_t = W_(t-1) * S_t
theta_t maximizes sum_{l=1}^t sum_{z in B_l} log(1 + payoff_theta(z))
```

Section 11.1 uses `sigma(g_theta(T1(z)) - g_theta(T2(z)))`, with an odd, bounded,
monotone function `sigma`. The repository plan specializes to independent two-sample observations
and chooses a clipped `tanh`. Its two unscored initialization batches follow the experimental
training description; Algorithm 1 itself describes scoring from the initial model.

Null validity and consistency are distinct: predictable bounded fair payoffs establish null
control; the paper's power-one result additionally assumes learning progress. A frozen lossy
encoder can erase a difference, so that result cannot automatically be promised for every
expression-space alternative.

## Provenance and regeneration

Downloaded 2026-09-05 from the PDF source above. PDF SHA-256:

```text
380eaa88d788f2f5758cbb085a09ada1cfa875a4884b378e4c14611d307f005b
```

Extracted with PyMuPDF 1.28.0 using `page.get_text("text", sort=False,
flags=pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_DEHYPHENATE)` for every page in order.
Each page has a `PDF PAGE NN / 22` marker. A short bibliographic header precedes the extraction.
No pages or appendix sections were intentionally omitted and no generated prose replaces paper text.
