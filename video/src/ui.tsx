import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import {
  BookOpen,
  GitBranch,
  Network,
  Plus,
  ArrowUpRight,
  Search,
} from "lucide-react";
export { Button } from "../../frontend/src/components/ui/button";
export { Empty, Status } from "../../frontend/src/components/common";
export { BookOpen, GitBranch, Network, Plus, ArrowUpRight, Search };
export const C = {
  bg: "#151a1b",
  surface: "#1b2122",
  raised: "#252d2e",
  fg: "#edf0ea",
  muted: "#abb7b3",
  accent: "#a6cabb",
  amber: "#e4bb7f",
  red: "#e5a6a0",
};
export const tween = (f: number, a: number, b: number, x = 0, y = 1) =>
  interpolate(f, [a, b], [x, y], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });
export function Typed({
  text,
  start = 0,
  speed = 1.8,
}: {
  text: string;
  start?: number;
  speed?: number;
}) {
  const f = useCurrentFrame();
  const n = Math.max(0, Math.floor((f - start) / speed));
  return (
    <>
      {text.slice(0, n)}
      {n < text.length && <span className="typing-caret">│</span>}
    </>
  );
}
export function Shell({
  tab = "Library",
  project = "Pancreatic cancer",
  children,
}: {
  tab?: string;
  project?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="movie-app">
      <header className="movie-header">
        <div className="movie-brand">
          <svg width="29" height="31" viewBox="0 0 29 31" fill="none">
            <path
              d="M5 4v23M5 6h8c12 0 12 19 0 19H5M12 9v13M18 9v13"
              stroke="currentColor"
              strokeWidth="1.8"
            />
          </svg>
          <b>
            DN <span>Research</span>
          </b>
        </div>
        <div className="project-label">
          {project} <span>⌄</span>
        </div>
        <nav>
          {[
            [GitBranch, "Investigations"],
            [BookOpen, "Library"],
            [Network, "Knowledge"],
          ].map(([Icon, label]) => {
            const I = Icon as typeof BookOpen;
            return (
              <div
                key={String(label)}
                className={tab === label ? "active" : ""}
              >
                <I size={20} />
                {String(label)}
              </div>
            );
          })}
        </nav>
        <span className="header-help">?</span>
      </header>
      <div className="movie-content">{children}</div>
    </div>
  );
}
export function Frame({
  chapter,
  caption,
  children,
  detail = "Animated product walkthrough",
}: {
  chapter: string;
  caption: string;
  children: React.ReactNode;
  detail?: string;
}) {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill className="movie">
      <div className="movie-eyebrow">
        <span>DN RESEARCH / PRODUCT WALKTHROUGH</span>
        <span>{chapter}</span>
      </div>
      <div
        className="stage-window"
        style={{
          opacity: tween(f, 0, 13),
          translate: `0 ${tween(f, 0, 20, 12, 0)}px`,
        }}
      >
        {children}
      </div>
      <div className="movie-caption">{caption}</div>
      <div className="movie-footnote">{detail}</div>
    </AbsoluteFill>
  );
}
export type Waypoint = [number, number, number];
export function Cursor({
  points,
  clicks = [],
}: {
  points: Waypoint[];
  clicks?: number[];
}) {
  const f = useCurrentFrame();
  const times = points.map((p) => p[0]);
  const opt = {
    extrapolateLeft: "clamp" as const,
    extrapolateRight: "clamp" as const,
    easing: Easing.inOut(Easing.cubic),
  };
  const x = interpolate(
      f,
      times,
      points.map((p) => p[1]),
      opt,
    ),
    y = interpolate(
      f,
      times,
      points.map((p) => p[2]),
      opt,
    );
  const age = clicks.map((t) => f - t).find((a) => a >= 0 && a < 20);
  return (
    <div className="movie-cursor" style={{ left: x, top: y }}>
      {age !== undefined && (
        <div
          className="click-ring"
          style={{ opacity: 1 - age / 20, scale: 1 + age / 9 }}
        />
      )}
      <svg
        width="33"
        height="43"
        viewBox="0 0 33 43"
        style={{
          scale:
            age !== undefined ? 1 - 0.1 * Math.sin((age / 20) * Math.PI) : 1,
        }}
      >
        <path
          d="M3 2L28 25L17 26L24 38L18 41L11 29L3 36Z"
          fill="#fff"
          stroke="#121a17"
          strokeWidth="2"
        />
      </svg>
    </div>
  );
}
export function Heading({
  title,
  sub,
  action,
}: {
  title: string;
  sub: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="movie-heading">
      <div>
        <small>Research workspace / Library</small>
        <h1>{title}</h1>
        <p>{sub}</p>
      </div>
      {action}
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="movie-overlay">
      <div className="movie-modal">
        <div className="movie-modal-title">
          {title}
          <span>×</span>
        </div>
        <p>{description}</p>
        {children}
      </div>
    </div>
  );
}
export function Field({
  label,
  children,
  tall = false,
}: {
  label: string;
  children: React.ReactNode;
  tall?: boolean;
}) {
  return (
    <label className="movie-field">
      {label}
      <div className={tall ? "field-box tall" : "field-box"}>{children}</div>
    </label>
  );
}
