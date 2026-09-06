import { useEffect, useRef, useState, type FormEvent } from "react";
import { FilePlus2, Link, Upload } from "lucide-react";
import { post, request, useResource } from "@/lib/api";
import type { JsonRecord } from "@/lib/types";
import { human, id } from "@/lib/utils";
import { Button } from "./ui/button";
import { Disclosure, ErrorNotice, Modal } from "./common";

export interface MembershipResult {
  project_id: string;
  copied?: boolean;
  job?: JsonRecord;
  duplicates?: string[];
  removed?: string;
}
export function AddPapers({
  project,
  copiedOnEdit,
  onChanged,
}: {
  project: string;
  copiedOnEdit: boolean;
  onChanged: (result: MembershipResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("doi");
  const [dois, setDois] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const base = `/api/projects/${id(project)}/papers`;
      const result =
        mode === "doi"
          ? await post<MembershipResult>(`${base}/add`, {
              dois: dois
                .split(/[\n,]+/)
                .map((doi) => doi.trim())
                .filter(Boolean),
            })
          : await request<MembershipResult>(`${base}/upload`, {
              method: "POST",
              headers: { "X-Filename": encodeURIComponent(file!.name) },
              body: file!,
            });
      setOpen(false);
      setDois("");
      setFile(null);
      onChanged(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button
        className="add-papers-button"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
      >
        <FilePlus2 size={17} /> Add papers
      </Button>
      <Modal
        open={open}
        onOpenChange={(value) => {
          if (!busy) setOpen(value);
        }}
        title="Add papers to this collection"
        description="Add a DOI or upload a document. Only the papers you add will be processed."
      >
        <form onSubmit={submit} className="add-papers-form">
          <div
            className="paper-add-methods"
            role="group"
            aria-label="Add paper method"
          >
            <Button
              aria-pressed={mode === "doi"}
              onClick={() => {
                setMode("doi");
                setError("");
              }}
            >
              <Link size={16} /> From DOI
            </Button>
            <Button
              aria-pressed={mode === "upload"}
              onClick={() => {
                setMode("upload");
                setError("");
              }}
            >
              <Upload size={16} /> Upload document
            </Button>
          </div>
          {mode === "doi" ? (
            <label>
              Paper DOI
              <textarea
                aria-label="Paper DOI"
                rows={3}
                required
                value={dois}
                onChange={(e) => setDois(e.target.value)}
                placeholder="10.1038/…"
              />
              <small>
                Paste one DOI or DOI link per line. Papers already in this
                collection are skipped.
              </small>
            </label>
          ) : (
            <label className="paper-upload-field">
              Choose a document
              <input
                type="file"
                required
                accept=".pdf,.txt,.md,.xml,.nxml"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <small>
                PDF, text, Markdown or XML. Upload a copy you have permission to
                use.
              </small>
            </label>
          )}
          <div className="paper-processing-explainer">
            <strong>What happens next</strong>
            <p>
              Retrieve or convert the document and its available figures,
              extract evidence into this collection, then update its search
              index. Progress and any errors appear in Library.
            </p>
            <small>
              This starts model-based extraction using your configured account.
            </small>
          </div>
          {copiedOnEdit && (
            <p className="paper-edit-scope">
              Your changes will be saved in a separate collection, preserving
              the source collection and its investigations.
            </p>
          )}
          <ErrorNotice message={error} />
          <div className="dialog-actions">
            <Button disabled={busy} onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              disabled={busy || (mode === "doi" ? !dois.trim() : !file)}
            >
              {busy ? "Starting…" : "Add and process papers"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function RemovePaper({
  project,
  paper,
  copiedOnEdit,
  onClose,
  onChanged,
}: {
  project: string;
  paper: { paper_id: string; title: string } | null;
  copiedOnEdit: boolean;
  onClose: () => void;
  onChanged: (result: MembershipResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setError(""), [paper?.paper_id]);
  return (
    <Modal
      open={!!paper}
      onOpenChange={(value) => {
        if (!value && !busy) onClose();
      }}
      title="Remove paper from this collection?"
      description="This removes the paper and its contribution to this collection’s evidence and search index. Claims supported by other papers and original documents used elsewhere are preserved."
    >
      <p className="paper-remove-title">{paper?.title}</p>
      {copiedOnEdit && (
        <p className="paper-edit-scope">
          This change will be saved in a separate collection. The source
          collection and its investigations remain intact.
        </p>
      )}
      <ErrorNotice message={error} />
      <div className="dialog-actions">
        <Button disabled={busy} onClick={onClose}>
          Keep paper
        </Button>
        <Button
          variant="danger"
          disabled={busy}
          onClick={async () => {
            if (!paper) return;
            setBusy(true);
            setError("");
            try {
              const result = await post<MembershipResult>(
                `/api/projects/${id(project)}/papers/${id(paper.paper_id)}/remove`,
              );
              onClose();
              onChanged(result);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Removing…" : "Remove paper"}
        </Button>
      </div>
    </Modal>
  );
}

export function PaperProcessing({
  project,
  onCompleted,
}: {
  project: string;
  onCompleted: () => void;
}) {
  const jobs = useResource<{ jobs: JsonRecord[] }>(
    `/api/projects/${id(project)}/jobs`,
    2000,
  );
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState("");
  const completed = useRef(new Set<string>());
  const imports = (jobs.data?.jobs || []).filter(
    (job) =>
      job.kind === "membership" ||
      job.kind === "papers" ||
      job.kind === "ingest",
  );
  useEffect(() => {
    for (const job of imports) {
      if (job.status === "done" && !completed.current.has(job.id)) {
        completed.current.add(job.id);
        onCompleted();
      }
    }
  }, [jobs.data]);
  return (
    <div className="paper-processing-jobs">
      <ErrorNotice message={jobs.error || error} retry={jobs.refresh} />
      {imports.slice(0, 4).map((job) => (
        <div className={`paper-processing-job ${job.status}`} key={job.id}>
          <div>
            <strong>
              {job.status === "running"
                ? "Processing added papers"
                : job.status === "done"
                  ? "Papers processed"
                  : job.status === "failed"
                    ? "Paper processing needs attention"
                    : human(job.status)}
            </strong>
            <span>
              {job.error ||
                job.last_event?.msg ||
                job.message ||
                (job.status === "done"
                  ? "Collection evidence and search index are updated."
                  : "Progress is saved so completed stages can be reused.")}
            </span>
          </div>
          <Disclosure title="Processing details">
            <ProcessingDetails project={project} job={job.id} />
          </Disclosure>
          {(job.status === "failed" || job.status === "cancelled") && (
            <Button
              size="sm"
              disabled={!!retrying}
              onClick={async () => {
                setRetrying(job.id);
                setError("");
                try {
                  await post(
                    `/api/projects/${id(project)}/jobs/${id(job.id)}/retry`,
                  );
                  jobs.refresh();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setRetrying("");
                }
              }}
            >
              {retrying === job.id ? "Resuming…" : "Retry processing"}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
function ProcessingDetails({ project, job }: { project: string; job: string }) {
  const detail = useResource<{ job: JsonRecord; events: JsonRecord[] }>(
    `/api/projects/${id(project)}/jobs/${id(job)}`,
    2000,
  );
  return (
    <div className="paper-processing-events">
      <ErrorNotice message={detail.error} retry={detail.refresh} />
      {detail.data?.events?.map((event, index) => (
        <p key={index}>
          <strong>{human(event.stage)}</strong> {event.msg}
        </p>
      ))}
    </div>
  );
}
