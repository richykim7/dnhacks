import { useEffect, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  GitBranch,
  Moon,
  Network,
  Plus,
  Sun,
  CircleHelp,
  Telescope,
} from "lucide-react";
import { useResource } from "./lib/api";
import type { Project } from "./lib/types";
import { safeStorage, saveStorage } from "./lib/utils";
import { Investigation } from "./components/Investigation";
import { Library, LaunchInvestigation } from "./components/Library";
import { Evidence } from "./components/Evidence";
import { Forecasting } from "./components/Forecasting";
import { ResearchProcess } from "./components/ResearchProcess";
import { Button } from "./components/ui/button";
import { ErrorNotice } from "./components/common";
type View = "forecast" | "investigations" | "library" | "evidence";
function readRoute() {
  const [path, run = ""] = window.location.hash.slice(1).split("/");
  const map: Record<string, View> = {
    runs: "investigations",
    tree: "investigations",
    workflow: "investigations",
    graph: "evidence",
    review: "evidence",
    corpus: "library",
    projects: "library",
    new: "library",
  };
  return {
    view: (["forecast", "investigations", "library", "evidence"].includes(path)
      ? path
      : map[path] || "investigations") as View,
    run: decodeURIComponent(run),
  };
}
export default function App() {
  const [route, setRoute] = useState(readRoute);
  const [theme, setTheme] = useState(() => safeStorage("dn-theme", "dark"));
  const [project, setProject] = useState(
    () =>
      new URLSearchParams(location.search).get("project") ||
      safeStorage("dn-project", ""),
  );
  const [launch, setLaunch] = useState(false);
  const [lastRun, setLastRun] = useState(() =>
    safeStorage(`dn-last-run-${project}`, ""),
  );
  useEffect(() => {
    if (route.view === "investigations" && route.run) {
      setLastRun(route.run);
      saveStorage(`dn-last-run-${project}`, route.run);
    }
  }, [route]);
  const [processOpen, setProcessOpen] = useState(false);
  const projects = useResource<{ projects: Project[] }>("/api/projects", 15000);
  useEffect(() => {
    const fn = () => setRoute(readRoute());
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle("dark", theme === "dark");
    saveStorage("dn-theme", theme);
  }, [theme]);
  const go = (view: View, run = "") => {
    location.hash = `${view}${run ? `/${encodeURIComponent(run)}` : ""}`;
  };
  const chooseProject = (value: string) => {
    setProject(value);
    setLastRun(safeStorage(`dn-last-run-${value}`, ""));
    saveStorage("dn-project", value);
    const url = new URL(location.href);
    value
      ? url.searchParams.set("project", value)
      : url.searchParams.delete("project");
    history.replaceState(null, "", url);
    go(route.view);
  };
  const active = projects.data?.projects.find((p) => p.id === project);
  const start = () => {
    if (active?.has_kg) setLaunch(true);
    else go("library");
  };
  const nav = [
    { view: "forecast" as const, label: "Forecast", icon: Telescope },
    {
      view: "investigations" as const,
      label: "Investigations",
      icon: GitBranch,
    },
    { view: "library" as const, label: "Library", icon: BookOpen },
    { view: "evidence" as const, label: "Evidence", icon: Network },
  ];
  return (
    <div className="app-shell">
      <a
        href="#workspace"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("workspace")?.focus();
        }}
      >
        Skip to workspace
      </a>
      <header className="app-header">
        <a
          className="brand"
          href="#investigations"
          aria-label="DN Research workspace"
        >
          <svg
            width="29"
            height="31"
            viewBox="0 0 29 31"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M5 4v23M5 6h8c12 0 12 19 0 19H5M12 9v13M18 9v13"
              stroke="currentColor"
              strokeWidth="1.8"
            />
          </svg>
          <span>
            DN<span className="brand-sub">Research</span>
          </span>
        </a>
        <div className="header-divider" />
        <div className="project-picker">
          <label className="sr-only" htmlFor="project-picker">
            Active project
          </label>
          <select
            id="project-picker"
            value={project}
            onChange={(e) => chooseProject(e.target.value)}
          >
            <option value="">All projects</option>
            {projects.data?.projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
            {project && !active && (
              <option value={project}>Project unavailable</option>
            )}
          </select>
          <ChevronDown size={14} />
        </div>
        <div className="header-spacer" />
        <span className="workspace-label">Biological discovery workspace</span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="How research works"
          onClick={() => setProcessOpen(true)}
        >
          <CircleHelp size={17} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={
            theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
          }
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </Button>
      </header>
      <div className="app-body">
        <nav className="navigation" aria-label="Main navigation">
          {nav.map((n) => (
            <a
              key={n.view}
              href={`#${n.view}${n.view === "investigations" && lastRun ? `/${encodeURIComponent(lastRun)}` : ""}`}
              className={route.view === n.view ? "active" : ""}
              aria-current={route.view === n.view ? "page" : undefined}
            >
              <n.icon size={19} strokeWidth={1.6} />
              <span>{n.label}</span>
            </a>
          ))}
          <div className="nav-spacer" />
          <Button variant="ghost" className="new-research" onClick={start}>
            <Plus size={19} />
            <span>New research</span>
          </Button>
          <span className="nav-footer">DNHacks 2026</span>
        </nav>
        <main id="workspace" tabIndex={-1}>
          <ErrorNotice message={projects.error} retry={projects.refresh} />
          {project && !active && projects.data && (
            <div className="notice">
              This project is unavailable. Select another project or All
              projects.
            </div>
          )}
          {route.view === "forecast" && <Forecasting />}
          {route.view === "investigations" && (
            <Investigation
              project={project}
              requestedRun={route.run}
              onRun={(r) => go("investigations", r)}
              onNew={start}
            />
          )}{" "}
          {route.view === "library" && (
            <Library
              key={project}
              project={project}
              projects={projects.data?.projects || []}
              onProject={chooseProject}
              onRefresh={projects.refresh}
              onInvestigate={() => setLaunch(true)}
            />
          )}{" "}
          {route.view === "evidence" && (
            <Evidence key={project} project={project} />
          )}{" "}
        </main>
      </div>
      <ResearchProcess open={processOpen} onOpenChange={setProcessOpen} />
      <LaunchInvestigation
        open={launch}
        onOpenChange={setLaunch}
        project={active}
        onStarted={(r) => go("investigations", r)}
      />
    </div>
  );
}
