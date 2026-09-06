import { lazy, Suspense, useEffect, useState } from "react";
const InhibitorLink=lazy(()=>import('./components/InhibitorLink'));
import {
  BookOpen,
  ChevronDown,
  GitBranch,
  Moon,
  Network,
  Plus,
  Sun,
  CircleHelp,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useResource } from "./lib/api";
import type { Project } from "./lib/types";
import { safeStorage, saveStorage } from "./lib/utils";
import { Investigation } from "./components/Investigation";
import { Library, LaunchInvestigation } from "./components/Library";
import { Knowledge } from "./components/Knowledge";
import { ResearchProcess } from "./components/ResearchProcess";
import { Button } from "./components/ui/button";
import { ErrorNotice } from "./components/common";
type View = "investigations" | "library" | "knowledge";
function readRoute() {
  const [path, run = ""] = window.location.hash.slice(1).split("/");
  const map: Record<string, View> = {
    runs: "investigations",
    tree: "investigations",
    workflow: "investigations",
    graph: "knowledge",
    evidence: "knowledge",
    review: "knowledge",
    corpus: "library",
    projects: "library",
    new: "library",
  };
  return {
    view: (["investigations", "library", "knowledge"].includes(path)
      ? path
      : map[path] || "investigations") as View,
    run: decodeURIComponent(run),
  };
}
export default function App() {
  if(new URLSearchParams(location.search).get('sceneTool')==='inhibitor')return <Suspense fallback={<p>Opening experiment…</p>}><InhibitorLink/></Suspense>;
  return <Workspace/>;
}
function Workspace() {
  const [route, setRoute] = useState(readRoute);
  const [navigationCollapsed, setNavigationCollapsed] = useState(() => safeStorage("dn-navigation-collapsed", "false") === "true");
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
    {
      view: "investigations" as const,
      label: "Investigations",
      icon: GitBranch,
    },
    { view: "library" as const, label: "Library", icon: BookOpen },
    { view: "knowledge" as const, label: "Knowledge", icon: Network },
  ];
  return (
    <div className={`app-shell ${navigationCollapsed ? "navigation-collapsed" : "navigation-expanded"}`}>
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
        <Button
          variant="ghost"
          size="icon"
          className="navigation-toggle"
          aria-label={navigationCollapsed ? "Expand main navigation" : "Collapse main navigation"}
          aria-expanded={!navigationCollapsed}
          aria-controls="main-navigation"
          onClick={() => setNavigationCollapsed(value => {
            saveStorage("dn-navigation-collapsed", String(!value));
            return !value;
          })}
        >
          {navigationCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </Button>
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
            Active collection
          </label>
          <select
            id="project-picker"
            value={project}
            onChange={(e) => chooseProject(e.target.value)}
          >
            <option value="">All collections</option>
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
        <nav id="main-navigation" className="navigation" aria-label="Main navigation" hidden={navigationCollapsed}>
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
          <Button variant="ghost" className="new-research" onClick={start} disabled={!active?.has_kg} title={active?.has_kg ? "Ask a question of this collection" : "Select a populated collection to start an investigation"}>
            <Plus size={19} />
            <span>New investigation</span>
          </Button>
          <span className="nav-footer">DNHacks 2026</span>
        </nav>
        <main id="workspace" className={`workspace-${route.view}`} tabIndex={-1}>
          <ErrorNotice message={projects.error} retry={projects.refresh} />
          {project && !active && projects.data && (
            <div className="notice">
              This collection is unavailable. Select another collection or All
              collections.
            </div>
          )}
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
            />
          )}{" "}
          {route.view === "knowledge" && (
            <Knowledge key={project} project={project} />
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
