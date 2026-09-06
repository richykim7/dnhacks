import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  FileText,
  Maximize2,
  Minimize2,
  Search,
} from "lucide-react";
import { useResource } from "@/lib/api";
import { human, id } from "@/lib/utils";
import { Button } from "./ui/button";
import { Disclosure, Empty, ErrorNotice, Loading } from "./common";

interface Paper {
  paper_id: string;
  source_ref: string;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  url: string | null;
  category: string | null;
  is_full_text: boolean;
  has_text: boolean;
  figure_count: number;
}
interface PaperDetail extends Paper {
  text: string | null;
  figures: { id: string; label: string; caption: string; url: string | null }[];
}
const availability = (p: Paper) =>
  p.has_text
    ? p.is_full_text
      ? "Full text"
      : "Abstract / excerpt"
    : "Metadata only";
const authors = (p: Paper) =>
  p.authors?.length ? p.authors.join(", ") : "Authors not recorded";
const sourceUrl = (p: Paper) => {
  if (p.doi) return `https://doi.org/${encodeURI(p.doi)}`;
  try {
    const url = new URL(p.url || "");
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
};

export function PaperBrowser({ project }: { project: string }) {
  const resource = useResource<{ papers: Paper[]; total: number }>(
    `/api/projects/${id(project)}/papers`,
  );
  const [query, setQuery] = useState("");
  const [text, setText] = useState("");
  const [year, setYear] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("newest");
  const [selected, setSelected] = useState<Paper | null>(null);
  const [expanded, setExpanded] = useState(false);
  const opener = useRef<HTMLButtonElement | null>(null);
  const papers = resource.data?.papers || [];
  const years = [
    ...new Set(papers.map((p) => p.year).filter((y): y is number => y != null)),
  ].sort((a, b) => b - a);
  const categories = [
    ...new Set(papers.map((p) => p.category).filter((c): c is string => !!c)),
  ].sort();
  const filtered = useMemo(
    () =>
      papers
        .filter((p) => {
          const needle = query.trim().toLowerCase();
          return (
            (!needle ||
              `${p.title} ${authors(p)} ${p.year || ""} ${p.doi || ""} ${p.source_ref}`
                .toLowerCase()
                .includes(needle)) &&
            (!year ||
              (year === "unknown"
                ? p.year == null
                : String(p.year) === year)) &&
            (!category || p.category === category) &&
            (!text ||
              (text === "full"
                ? p.has_text && p.is_full_text
                : text === "figures"
                  ? p.figure_count > 0
                  : text === "abstract"
                    ? p.has_text && !p.is_full_text
                    : !p.has_text))
          );
        })
        .sort((a, b) =>
          sort === "title"
            ? (a.title || a.source_ref).localeCompare(b.title || b.source_ref)
            : sort === "oldest"
              ? (a.year ?? 9999) - (b.year ?? 9999)
              : (b.year ?? 0) - (a.year ?? 0),
        ),
    [papers, query, year, category, text, sort],
  );
  const reset = () => {
    setQuery("");
    setText("");
    setYear("");
    setCategory("");
  };
  const close = () => {
    setSelected(null);
    setExpanded(false);
    requestAnimationFrame(() => opener.current?.focus());
  };
  return (
    <section
      className={`paper-browser ${selected ? "has-reader" : ""} ${expanded ? "reader-expanded" : ""}`}
      aria-label="Collection papers"
    >
      <div className="paper-browser-tools">
        <div className="paper-browser-title">
          <h2>Papers</h2>
          <span>Read, search and explore your collection</span>
        </div>
        <label className="search-field paper-search">
          <Search size={18} />
          <span className="sr-only">Search papers</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, author or DOI…"
          />
        </label>
        <div className="paper-filters">
          <label>
            Text availability
            <select value={text} onChange={(e) => setText(e.target.value)}>
              <option value="">All papers</option>
              <option value="full">Full text available</option>
              <option value="figures">With figures</option>
              <option value="abstract">Abstract / excerpt</option>
              <option value="metadata">Metadata only</option>
            </select>
          </label>
          <label>
            Publication year
            <select value={year} onChange={(e) => setYear(e.target.value)}>
              <option value="">All years</option>
              {years.map((y) => (
                <option key={y}>{y}</option>
              ))}
              {papers.some((p) => p.year == null) && (
                <option value="unknown">Year not recorded</option>
              )}
            </select>
          </label>
          {categories.length > 0 && (
            <label>
              Topic
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">All topics</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {human(c)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="paper-sort">
            Sort papers
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="title">Title A–Z</option>
            </select>
          </label>
        </div>
        {resource.data && (
          <div className="paper-results">
            <span role="status">
              {filtered.length} of {resource.data.total} papers
            </span>
            {query || year || text || category ? (
              <Button size="sm" variant="ghost" onClick={reset}>
                Clear filters
              </Button>
            ) : (
              <span>Select a paper to read</span>
            )}
          </div>
        )}
      </div>
      <ErrorNotice message={resource.error} retry={resource.refresh} />
      {resource.loading ? (
        <Loading label="Loading papers" />
      ) : (
        !resource.error &&
        resource.data && (
          <>
            {papers.length === 0 ? (
              <Empty title="No collected papers yet">
                Collection settings and imported documents are available in
                Manage collection. Papers appear here once collected.
              </Empty>
            ) : filtered.length === 0 ? (
              <Empty
                title="No papers match these filters"
                action={<Button onClick={reset}>Clear filters</Button>}
              >
                Try another title, author, year or text availability.
              </Empty>
            ) : null}
            <div className="paper-workspace">
              <div
                className="paper-list"
                aria-label="Papers"
                role="region"
                tabIndex={0}
              >
                {filtered.map((p, index) => (
                  <button
                    className={`paper-row ${selected?.paper_id === p.paper_id ? "selected" : ""}`}
                    key={p.paper_id}
                    aria-pressed={selected?.paper_id === p.paper_id}
                    onClick={(e) => {
                      opener.current = e.currentTarget;
                      setSelected(p);
                    }}
                  >
                    <span className="paper-row-index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="paper-row-body">
                      <strong>{p.title || "Untitled paper"}</strong>
                      <span className="paper-row-authors">{authors(p)}</span>
                      <span className="paper-row-meta">
                        <span>{p.year || "Year not recorded"}</span>
                        {p.category && <span>{human(p.category)}</span>}
                        <span
                          className={p.has_text ? "paper-text-available" : ""}
                        >
                          {p.has_text ? (
                            <BookOpen size={12} />
                          ) : (
                            <FileText size={12} />
                          )}
                          {availability(p)}
                        </span>
                        {p.figure_count > 0 && (
                          <span>{p.figure_count} figures</span>
                        )}
                      </span>
                    </span>
                    <ArrowUpRight className="paper-row-arrow" size={16} />
                  </button>
                ))}
              </div>
              {selected && (
                <PaperReader
                  key={selected.paper_id}
                  project={project}
                  paper={selected}
                  expanded={expanded}
                  onExpand={() => setExpanded(!expanded)}
                  onClose={close}
                />
              )}
            </div>
          </>
        )
      )}
    </section>
  );
}

function PaperReader({
  project,
  paper,
  expanded,
  onExpand,
  onClose,
}: {
  project: string;
  paper: Paper;
  expanded: boolean;
  onExpand: () => void;
  onClose: () => void;
}) {
  const detail = useResource<{ paper: PaperDetail }>(
    `/api/projects/${id(project)}/papers/${id(paper.paper_id)}`,
  );
  const reader = useRef<HTMLElement | null>(null);
  useEffect(() => {
    reader.current?.focus({ preventScroll: true });
  }, []);
  const p = detail.data?.paper || paper;
  const url = sourceUrl(p);
  return (
    <section
      ref={reader}
      tabIndex={-1}
      className="paper-reader"
      aria-label="Paper reader"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
    >
      <div className="paper-reader-toolbar">
        <Button variant="ghost" size="sm" onClick={onClose}>
          <ArrowLeft size={15} /> Back to papers
        </Button>
        <div className="paper-reader-actions">
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              scrollReaderTo(reader.current?.querySelector(".paper-figures"))
            }
          >
            Figures
          </Button>
          <Button
            className="paper-expand"
            variant="ghost"
            size="icon"
            aria-label={expanded ? "Show paper list" : "Expand reader"}
            onClick={onExpand}
          >
            {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </Button>
        </div>
      </div>
      <article className="paper-article">
        <div className="paper-reader-kicker">
          {p.year || "Year not recorded"} · {availability(p)}
        </div>
        <h2>{p.title || "Untitled paper"}</h2>
        <p className="paper-byline">{authors(p)}</p>
        {url && (
          <a
            className="paper-source-link"
            href={url}
            target="_blank"
            rel="noreferrer"
          >
            Open original source <ArrowUpRight size={14} />
          </a>
        )}
        <ErrorNotice message={detail.error} retry={detail.refresh} />
        {detail.loading ? (
          <Loading label="Opening paper" />
        ) : (
          detail.data && (
            <>
              <div className="paper-reading-note">
                {p.is_full_text && p.has_text
                  ? "Stored full text"
                  : "Stored paper record"}
                . Formatting follows the locally available extraction.
              </div>
              {detail.data.paper.text ? (
                <PaperText text={detail.data.paper.text} />
              ) : (
                <div className="notice">
                  Readable text is not stored for this paper.
                  {url
                    ? " Open the original source to read it."
                    : " No original source link is recorded."}
                </div>
              )}
              <section className="paper-figures" aria-label="Paper figures">
                <h3>Figures</h3>
                {detail.data.paper.figures?.length ? (
                  detail.data.paper.figures.map((figure, index) => (
                    <figure key={figure.id || index}>
                      {figure.url ? (
                        <StoredFigure
                          url={figure.url}
                          label={figure.label || `Figure ${index + 1}`}
                        />
                      ) : (
                        <p className="notice">
                          Figure image is not stored locally.
                        </p>
                      )}
                      <figcaption>
                        <strong>{figure.label || `Figure ${index + 1}`}</strong>
                        {figure.caption && <p>{figure.caption}</p>}
                      </figcaption>
                    </figure>
                  ))
                ) : (
                  <p className="muted">No figures are stored for this paper.</p>
                )}
              </section>
            </>
          )
        )}
      </article>
    </section>
  );
}
function StoredFigure({ url, label }: { url: string; label: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? (
    <p className="notice">{label}: image could not be loaded.</p>
  ) : (
    <img src={url} alt={label} loading="lazy" onError={() => setFailed(true)} />
  );
}

function PaperText({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/);
  const abstract = blocks.findIndex((block) =>
    /^(?:#{1,6}\s*)?Abstract\s*$/i.test(block.trim()),
  );
  const start = abstract > 0 ? abstract : 0;
  const heading = (block: string) => /^#{1,6}\s+(.+)$/.exec(block.trim());
  const sections = blocks
    .map((block, i) => ({
      label: heading(block)?.[1] || block.trim(),
      index: i,
    }))
    .filter(
      ({ label, index }) =>
        index >= start &&
        label.length < 100 &&
        /^(abstract|introduction|results|discussion|conclusion|materials|methods|references|acknowledg)/i.test(
          label,
        ),
    );
  const render = (block: string, i: number) =>
    heading(block) ? (
      <h3 id={`paper-section-${i}`} key={i}>
        {heading(block)![1]}
      </h3>
    ) : (
      <p id={`paper-section-${i}`} key={i}>
        {block}
      </p>
    );
  return (
    <div className="paper-fulltext">
      {sections.length > 0 && (
        <label className="paper-section-picker">
          Jump to section
          <select
            defaultValue=""
            onChange={(e) => {
              if (e.target.value)
                scrollReaderTo(document.getElementById(e.target.value));
            }}
          >
            <option value="">Choose a section</option>
            {sections.map((s) => (
              <option key={s.index} value={`paper-section-${s.index}`}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {start > 0 && (
        <Disclosure title="Publication details and author affiliations">
          {blocks.slice(0, start).map(render)}
        </Disclosure>
      )}
      {blocks.slice(start).map((block, i) => render(block, i + start))}
    </div>
  );
}

function scrollReaderTo(target: Element | null | undefined) {
  const pane = target?.closest(".paper-reader");
  if (target && pane)
    pane.scrollTo({
      top:
        pane.scrollTop +
        target.getBoundingClientRect().top -
        pane.getBoundingClientRect().top -
        70,
    });
}
