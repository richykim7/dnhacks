import { useEffect, useState, type FormEvent } from "react";
import { PaperBrowser } from "./PaperBrowser";
import "../library.css";
import {
  ArrowUpRight,
  BookOpen,
  FileText,
  Plus,
  Send,
  Upload,
} from "lucide-react";
import { post, request, useResource } from "@/lib/api";
import type { JsonRecord, Project } from "@/lib/types";
import { date, human, id, number } from "@/lib/utils";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import {
  Disclosure,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  Status,
} from "./common";

export function Library({
  project,
  projects,
  onProject,
  onRefresh,
}: {
  project: string;
  projects: Project[];
  onProject: (id: string) => void;
  onRefresh: () => void;
}) {
  const rec = useResource<Project>(
    project ? `/api/projects/${id(project)}` : null,
  );
  const stats = useResource<JsonRecord>(
    project ? `/api/projects/${id(project)}/kg` : null,
    10000,
  );
  const [tab, setTab] = useState("collection");
  const [managing, setManaging] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmBuild, setConfirmBuild] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [purge, setPurge] = useState(false);
  const refresh = () => {
    rec.refresh();
    stats.refresh();
    onRefresh();
  };
  async function build(dry = false) {
    setBusy(true);
    setError("");
    try {
      await post(`/api/projects/${id(project)}/build`, { dry });
      setConfirmBuild(false);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page library-page">
      <header className="page-heading">
        <div>
          <div className="breadcrumb">Research workspace / Library</div>
          <h1>{rec.data?.name || "Your research library"}</h1>
          <p>Browse the papers behind your research.</p>
        </div>
        <div className="library-heading-actions">
          {project && (
            <Button
              aria-expanded={managing}
              onClick={() => setManaging(!managing)}
            >
              {managing ? "Back to papers" : "Manage collection"}
            </Button>
          )}
          {(project || projects.length > 0) && (
            <Button variant="ghost" onClick={() => setCreating(true)}>
              <Plus size={16} /> New collection
            </Button>
          )}
        </div>
      </header>
      <CreateProject
        open={creating}
        onOpenChange={setCreating}
        onCreated={(p) => {
          onRefresh();
          onProject(p.id);
        }}
      />
      {!project ? (
        <>
          <div className="project-table">
            {projects.map((p) => (
              <button key={p.id} onClick={() => onProject(p.id)}>
                <BookOpen size={22} />
                <span>
                  <strong>{p.name}</strong>
                  <small>
                    {p.adopted ? "Imported collection" : human(p.status)}
                  </small>
                </span>
                <span>
                  {p.n_claims == null
                    ? "Not yet measured"
                    : `${number(p.n_claims)} claims`}
                </span>
                <ArrowUpRight size={17} />
              </button>
            ))}
          </div>
          {!projects.length && (
            <Empty
              title="Create your first collection"
              action={
                <Button variant="default" onClick={() => setCreating(true)}>
                  Create a literature collection <Plus size={16} />
                </Button>
              }
            >
              Define a topic, collect its literature, and turn the evidence into
              an investigation.
            </Empty>
          )}
        </>
      ) : rec.loading ? (
        <Loading />
      ) : (
        <>
          <ErrorNotice message={rec.error || error} retry={rec.refresh} />
          {rec.data && (
            <>
              <div className="library-summary">
                <span>
                  {rec.data.adopted
                    ? "Imported · read-only"
                    : human(rec.data.status)}
                </span>
                {stats.data?.exists && !stats.data?.error && (
                  <span>
                    {number(stats.data.papers.n)} papers ·{" "}
                    {number(stats.data.claims.n)} literature claims
                  </span>
                )}
                <p>
                  {rec.data.description ||
                    rec.data.spec.scope ||
                    "Your collected literature"}
                </p>
              </div>
              {!managing && (
                <PaperBrowser
                  key={project}
                  project={project}
                />
              )}
              {managing && (
                <>
                  {rec.data.built?.stale && (
                    <div className="notice">
                      The collection settings have changed since the last build.
                      Rebuild to include those changes in future investigations.
                    </div>
                  )}
                  <AnimatedTabs
                    label="Library sections"
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "collection", label: "Collection settings" },
                      { value: "documents", label: "Import documents" },
                      { value: "assistant", label: "Research assistant" },
                      { value: "history", label: "Builds & runs" },
                    ]}
                  />
                  <div className="library-content">
                    {tab === "collection" && (
                      <>
                        <SpecEditor
                          key={`${project}-${JSON.stringify(rec.data.spec)}`}
                          project={rec.data}
                          onSaved={refresh}
                        />
                        {!rec.data.adopted && (
                          <div className="build-actions">
                            <div>
                              <h3>Build the collection</h3>
                              <p>
                                Preview matching papers, or collect and extract
                                evidence for research.
                              </p>
                            </div>
                            <Button
                              disabled={busy}
                              onClick={() => void build(true)}
                            >
                              Preview papers
                            </Button>
                            <Button
                              variant="default"
                              onClick={() => setConfirmBuild(true)}
                            >
                              Build collection
                            </Button>
                          </div>
                        )}
                        {rec.data.built && (
                          <Disclosure title="Last build provenance">
                            <pre>{JSON.stringify(rec.data.built, null, 2)}</pre>
                          </Disclosure>
                        )}
                        {!rec.data.adopted && (
                          <div className="danger-zone">
                            <Button
                              variant="ghost"
                              onClick={() => setConfirmDelete(true)}
                            >
                              Delete project…
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                    {tab === "documents" && (
                      <Documents
                        project={project}
                        readOnly={rec.data.adopted}
                      />
                    )}
                    {tab === "assistant" && (
                      <Assistant project={rec.data} onApplied={refresh} />
                    )}
                    {tab === "history" && <JobHistory project={project} />}
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}
      <Modal
        open={confirmBuild}
        onOpenChange={setConfirmBuild}
        title="Build this literature collection?"
        description="This starts literature retrieval and model-based evidence extraction. It can take several minutes and uses your configured model account."
      >
        <ErrorNotice message={error} />
        <div className="dialog-actions">
          <Button onClick={() => setConfirmBuild(false)}>Keep editing</Button>
          <Button
            variant="default"
            disabled={busy}
            onClick={() => void build()}
          >
            {busy ? "Starting…" : "Start build"}
          </Button>
        </div>
      </Modal>
      <Modal
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this project?"
        description="Deleting removes the project record. You can choose whether to also permanently remove its generated files."
      >
        <label className="check-label">
          <input
            type="checkbox"
            checked={purge}
            onChange={(e) => setPurge(e.target.checked)}
          />
          Also permanently delete its documents, jobs and graph
        </label>
        <ErrorNotice message={error} />
        <div className="dialog-actions">
          <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button
            variant="danger"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await post(`/api/projects/${id(project)}/delete`, { purge });
                setConfirmDelete(false);
                onProject("");
                onRefresh();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Delete project
          </Button>
        </div>
      </Modal>
    </div>
  );
}

export function CreateProject({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (p: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const p = await post<Project>("/api/projects", {
        name,
        description,
        spec: { scope: description, theme: description },
      });
      onCreated(p);
      onOpenChange(false);
      setName("");
      setDescription("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Create a literature collection"
      description="Start with a topic. You can refine the literature search and add documents next."
    >
      <form onSubmit={submit}>
        <label>
          Collection name
          <input
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Ion-channel mechanisms"
          />
        </label>
        <label>
          What does this collection cover?
          <textarea
            required
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the biology, targets, or evidence you want to explore."
          />
        </label>
        <ErrorNotice message={error} />
        <div className="dialog-actions">
          <Button type="submit" variant="default" disabled={busy}>
            {busy ? "Creating…" : "Create collection"}
            <ArrowUpRight size={15} />
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function SpecEditor({
  project: p,
  onSaved,
}: {
  project: Project;
  onSaved: () => void;
}) {
  const [spec, setSpec] = useState<JsonRecord>(p.spec || {});
  const [name, setName] = useState(p.name);
  const [description, setDescription] = useState(p.description || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const set = (key: string, value: unknown) => {
    setSpec((s) => ({ ...s, [key]: value }));
    setSaved(false);
  };
  const list = (key: string, label: string, hint: string) =>
    key !== "queries" ? (
      <CollectionChips
        label={label}
        hint={hint}
        disabled={p.adopted}
        values={Array.isArray(spec[key]) ? spec[key] : []}
        onChange={(values) => set(key, values)}
      />
    ) : (
      <label>
        {label}
        <textarea
          rows={3}
          disabled={p.adopted}
          value={
            Array.isArray(spec[key]) ? spec[key].join("\n") : spec[key] || ""
          }
          onChange={(e) => set(key, e.target.value.split("\n"))}
        />
        <small>{hint}</small>
      </label>
    );
  return (
    <form
      className="spec-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await post(`/api/projects/${id(p.id)}`, { name, description, spec });
          setSaved(true);
          onSaved();
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="form-section">
        <div>
          <h2>Define the collection</h2>
          <p>
            These settings choose the literature. Your research question is set
            separately for each investigation.
          </p>
        </div>
        <div>
          <label>
            Name
            <input
              disabled={p.adopted}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>
          <label>
            Description
            <textarea
              disabled={p.adopted}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </label>
          <Disclosure title="Scope and relevance criteria">
            <label>
              Scope
              <textarea
                disabled={p.adopted}
                value={spec.scope || ""}
                onChange={(e) => set("scope", e.target.value)}
                rows={3}
              />
            </label>
            <label>
              Relevance criteria
              <textarea
                disabled={p.adopted}
                value={spec.theme || ""}
                onChange={(e) => set("theme", e.target.value)}
                rows={3}
              />
              <small>What makes a paper useful to this project?</small>
            </label>
          </Disclosure>
        </div>
      </div>
      <div className="form-section">
        <div>
          <h2>Find the literature</h2>
          <p>
            Search Europe PMC and optionally anchor the collection with specific
            papers.
          </p>
        </div>
        <div>
          {list(
            "queries",
            "Literature searches",
            "One Europe PMC query per line. Required before building.",
          )}
          {list(
            "seed_dois",
            "Anchor papers",
            "One DOI per line; these papers are explicitly included.",
          )}
          <div className="field-pair">
            <label>
              Maximum papers
              <input
                type="number"
                min={5}
                max={2000}
                disabled={p.adopted}
                value={spec.n_papers || 120}
                onChange={(e) => set("n_papers", Number(e.target.value))}
              />
            </label>
            <label>
              Text availability
              <select
                disabled={p.adopted}
                value={spec.full_text_only ? "full" : "any"}
                onChange={(e) =>
                  set("full_text_only", e.target.value === "full")
                }
              >
                <option value="any">Include abstracts</option>
                <option value="full">Full text only</option>
              </select>
            </label>
          </div>
          <Disclosure title="Publication window and exclusions">
            <div className="field-pair">
              {["year_min", "year_max"].map((k, i) => (
                <label key={k}>
                  {i === 0 ? "From year" : "Through year"}
                  <input
                    type="number"
                    disabled={p.adopted}
                    value={spec[k] ?? ""}
                    onChange={(e) =>
                      set(k, e.target.value ? Number(e.target.value) : null)
                    }
                  />
                </label>
              ))}
            </div>
            {list(
              "exclude_terms",
              "Excluded terms",
              "Papers matching these terms are left out.",
            )}
            <label>
              Parallel retrieval tasks
              <input
                type="number"
                min={1}
                max={40}
                disabled={p.adopted}
                value={spec.concurrency || 8}
                onChange={(e) => set("concurrency", Number(e.target.value))}
              />
            </label>
          </Disclosure>
        </div>
      </div>
      <ErrorNotice message={error} />
      {!p.adopted && (
        <div className="form-save">
          <span role="status">{saved ? "Settings saved" : ""}</span>
          <Button type="submit" disabled={busy} variant="default">
            {busy ? "Saving…" : "Save settings"}
          </Button>
        </div>
      )}
    </form>
  );
}

function Documents({
  project,
  readOnly,
}: {
  project: string;
  readOnly: boolean;
}) {
  const docs = useResource<{ attachments: JsonRecord[] }>(
    `/api/projects/${id(project)}/attachments`,
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [remove, setRemove] = useState<JsonRecord | null>(null);
  async function upload(files: FileList | null) {
    if (!files) return;
    setBusy(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        await request(`/api/projects/${id(project)}/attachments`, {
          method: "POST",
          headers: { "X-Filename": encodeURIComponent(file.name) },
          body: file,
        });
      }
      docs.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h2>Source documents</h2>
      <p className="muted">
        Add papers and notes to inform the collection and research assistant.
      </p>
      {!readOnly && (
        <label className="upload-zone">
          <Upload size={23} />
          <strong>
            {busy ? "Uploading documents…" : "Choose documents to upload"}
          </strong>
          <span>PDF, text, Markdown or XML · up to 40 MiB each</span>
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.xml"
            disabled={busy}
            onChange={(e) => void upload(e.target.files)}
          />
        </label>
      )}
      <ErrorNotice message={error || docs.error} />
      {docs.loading && <Loading />}
      {docs.data?.attachments.map((d) => (
        <div className="document-row" key={d.id}>
          <FileText size={20} />
          <span>
            <strong>{d.filename || d.name}</strong>
            <small>
              {d.n_chars != null
                ? `${number(d.n_chars)} characters extracted`
                : "Uploaded document"}
            </small>
          </span>
          {!readOnly && (
            <Button variant="ghost" size="sm" onClick={() => setRemove(d)}>
              Remove
            </Button>
          )}
        </div>
      ))}
      {!docs.loading && !docs.data?.attachments.length && (
        <p className="muted">No documents added yet.</p>
      )}
      <Modal
        open={!!remove}
        onOpenChange={() => setRemove(null)}
        title="Remove this document?"
        description={
          remove?.filename ||
          "This removes the uploaded document from the project."
        }
      >
        <Button
          variant="danger"
          onClick={async () => {
            try {
              await post(
                `/api/projects/${id(project)}/attachments/${id(remove!.id)}/delete`,
              );
              setRemove(null);
              docs.refresh();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Remove document
        </Button>
      </Modal>
    </>
  );
}

function Assistant({
  project,
  onApplied,
}: {
  project: Project;
  onApplied: () => void;
}) {
  const [messages, setMessages] = useState<JsonRecord[]>(project.chat || []);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="assistant">
      <h2>Refine your research collection</h2>
      <p className="muted">
        Discuss the scope and literature searches. Proposed settings are only
        changed when you apply them.
      </p>
      <div className="chat-log">
        {messages.map((m, i) => (
          <article className={`chat-message ${m.role}`} key={i}>
            <span>{m.role === "assistant" ? "Research assistant" : "You"}</span>
            <p>{m.content}</p>
            {m.patch && (
              <Disclosure title="Proposed collection changes">
                <pre>{JSON.stringify(m.patch, null, 2)}</pre>
                <Button
                  disabled={busy || project.adopted}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await post(`/api/projects/${id(project.id)}/chat/apply`, {
                        patch: m.patch,
                      });
                      onApplied();
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Apply these settings
                </Button>
              </Disclosure>
            )}
          </article>
        ))}
      </div>
      <ErrorNotice message={error} />
      <form
        className="chat-compose"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const res = await post<JsonRecord>(
              `/api/projects/${id(project.id)}/chat`,
              { message },
            );
            setMessages(res.chat);
            setMessage("");
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="sr-only" htmlFor="assistant-message">
          Message the research assistant
        </label>
        <textarea
          id="assistant-message"
          required
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Help me focus this collection on…"
        />
        <Button type="submit" variant="default" disabled={busy}>
          {busy ? "Thinking…" : "Send"}
          <Send size={15} />
        </Button>
      </form>
    </div>
  );
}

export function JobHistory({ project }: { project: string }) {
  const jobs = useResource<{ jobs: JsonRecord[] }>(
    `/api/projects/${id(project)}/jobs`,
    3000,
  );
  const [selected, setSelected] = useState("");
  const detail = useResource<JsonRecord>(
    selected ? `/api/projects/${id(project)}/jobs/${id(selected)}` : null,
    3000,
  );
  const log = useResource<{ log: string }>(
    selected ? `/api/projects/${id(project)}/jobs/${id(selected)}/log` : null,
    5000,
  );
  const [error, setError] = useState("");
  return (
    <>
      <h2>Builds & runs</h2>
      <ErrorNotice message={jobs.error || detail.error || error} />
      {jobs.data?.jobs.map((j) => (
        <button
          className="job-row"
          key={j.id}
          onClick={() => setSelected(j.id)}
        >
          <span>
            <strong>
              {j.kind === "run"
                ? j.goal || "Research investigation"
                : j.dry
                  ? "Literature preview"
                  : "Collection build"}
            </strong>
            <small>{date(j.started)}</small>
          </span>
          <Status
            label={human(j.status)}
            tone={
              j.status === "running"
                ? "live"
                : j.status === "failed"
                  ? "negative"
                  : "neutral"
            }
          />
          <ArrowUpRight size={15} />
        </button>
      ))}
      {jobs.data?.jobs.length === 0 && (
        <p className="muted">No builds or runs started for this project.</p>
      )}
      {detail.data && (
        <section className="job-detail">
          <div className="section-heading">
            <h3>Progress</h3>
            {detail.data.job.status === "running" && (
              <Button
                variant="danger"
                size="sm"
                onClick={async () => {
                  try {
                    await post(
                      `/api/projects/${id(project)}/jobs/${id(selected)}/cancel`,
                    );
                    jobs.refresh();
                    detail.refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Stop job
              </Button>
            )}
          </div>
          {detail.data.job.error && (
            <ErrorNotice message={detail.data.job.error} />
          )}
          <div className="job-events">
            {detail.data.events?.map((e: JsonRecord, i: number) => (
              <p key={i}>
                <span>{human(e.stage)}</span> {e.msg}
              </p>
            ))}
          </div>
          <Disclosure title="Process log">
            <ErrorNotice message={log.error} />
            <pre>{log.data?.log || "No log output yet."}</pre>
          </Disclosure>
        </section>
      )}
    </>
  );
}

export function LaunchInvestigation({
  open,
  onOpenChange,
  project,
  onStarted,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  project: Project | undefined;
  onStarted: (run: string) => void;
}) {
  const [goal, setGoal] = useState("");
  const [steps, setSteps] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setError(""), [open]);
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Start an investigation"
      description={`Ask a question of ${project?.name || "your literature collection"}. This starts the research engine using your configured model account.`}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!project) return;
          setBusy(true);
          setError("");
          try {
            const result = await post<JsonRecord>(
              `/api/projects/${id(project.id)}/run`,
              { goal, steps },
            );
            onStarted(result.run_id);
            onOpenChange(false);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Research question
          <textarea
            rows={5}
            minLength={12}
            maxLength={4000}
            required
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="What would you like to understand or test?"
          />
        </label>
        <Disclosure title="Research budget">
          <label>
            Maximum steps
            <input
              type="number"
              min={1}
              max={200}
              value={steps}
              onChange={(e) => setSteps(Number(e.target.value))}
            />
            <small>
              Bounds the number of research actions. Longer investigations can
              use more model compute.
            </small>
          </label>
        </Disclosure>
        <ErrorNotice message={error} />
        <div className="dialog-actions">
          <Button type="submit" variant="default" disabled={busy || !project}>
            {busy ? "Starting…" : "Start research"}
            <ArrowUpRight size={15} />
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function CollectionChips({
  label,
  hint,
  values,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  values: string[];
  disabled: boolean;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const value = draft.trim();
    if (value && !values.includes(value))
      onChange([...values.filter(Boolean), value]);
    setDraft("");
  };
  return (
    <div className="collection-chip-field">
      <label>
        {label}
        {!disabled && (
          <div className="collection-chip-input">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={
                label === "Anchor papers" ? "Add a DOI" : "Add an excluded term"
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add();
                }
              }}
            />
            <Button
              type="button"
              size="sm"
              disabled={!draft.trim()}
              onClick={add}
            >
              Add
            </Button>
          </div>
        )}
      </label>
      <div className="collection-chips">
        {values.filter(Boolean).map((value, i) => (
          <span key={`${value}-${i}`}>
            {value}
            {!disabled && (
              <button
                type="button"
                aria-label={`Remove ${value}`}
                onClick={() =>
                  onChange(values.filter((_, index) => index !== i))
                }
              >
                ×
              </button>
            )}
          </span>
        ))}
        {!values.filter(Boolean).length && <small>None added</small>}
      </div>
      <small>{hint}</small>
    </div>
  );
}
