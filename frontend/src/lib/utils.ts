import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...values: ClassValue[]) => twMerge(clsx(values));
export const id = encodeURIComponent;
export const human = (value?: string | null) =>
  value
    ? value.replace(/_/g, " ").replace(/\b\w/, (c) => c.toUpperCase())
    : "Not recorded";
export const number = (value?: number | null) =>
  value == null || !Number.isFinite(value)
    ? "Not measured"
    : new Intl.NumberFormat("en", { maximumSignificantDigits: 4 }).format(
        value,
      );
export const date = (value?: number) =>
  value
    ? new Date(value * 1000).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Time not recorded";
export const duration = (value?: number) =>
  value == null
    ? ""
    : value < 60
      ? `${Math.round(value)}s`
      : `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
export const actionLabel = (action?: string) =>
  ({
    search_kg: "Searching evidence",
    neighbors: "Following relationships",
    subgraph: "Examining relationships",
    path: "Tracing a connection",
    recall: "Revisiting evidence",
    search_papers: "Finding papers",
    fetch_papers: "Retrieving papers",
    read_paper: "Reading a paper",
    find_datasets: "Finding datasets",
    search_skills: "Choosing an analysis",
    get_skill: "Preparing an analysis",
    run_experiments: "Running experiments",
    submit: "Submitting for verification",
    fork: "Exploring branches",
    reflect: "Evaluating a hypothesis",
    log: "Recording a finding",
    note: "Recording a note",
    done: "Finished",
  })[action || ""] || human(action);
export const stageLabel = (stage?: string) =>
  ({
    candidate: "Needs review",
    killed: "Not supported",
    reviewed: "Reviewed",
    verifying: "Verifying",
    submitted: "Awaiting verification",
    promising: "Has a result",
    open: "Exploring",
    invalid: "Invalid result",
    underpowered: "Insufficient data",
    refuted: "Not supported",
    inconclusive: "Inconclusive",
  })[stage || ""] || human(stage);
export function safeStorage(key: string, fallback: string) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}
export function saveStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Browsing still works without storage. */
  }
}
