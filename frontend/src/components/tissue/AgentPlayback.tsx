import { useEffect, useRef, useState } from "react";
import type { View } from "./types";
export type SceneAction = {
  sequence: number;
  payload: {
    artifact_sha256: string;
    recipe_sha256: string;
    view: View;
    note: string;
    actor: string;
  };
};
export default function AgentPlayback({
  actions,
  view,
  apply,
}: {
  actions: SceneAction[];
  view: View;
  apply: (v: View) => void;
}) {
  const [index, setIndex] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [replay, setReplay] = useState(false);
  const user = useRef(view);
  const action = actions[Math.min(index, actions.length - 1)];
  useEffect(() => {
    if (!replay || !action) return;
    apply(action.payload.view);
  }, [replay, index, action?.payload.recipe_sha256]);
  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      if (index >= actions.length - 1) setPlaying(false);
      else setIndex((i) => i + 1);
    }, 1500 / speed);
    return () => clearTimeout(timer);
  }, [playing, index, speed, actions.length]);
  if (!actions.length)
    return (
      <p className="tissue-history-empty">
        No recorded agent scene actions at this investigation cursor.
      </p>
    );
  return (
    <section
      className="tissue-agent-playback"
      aria-label="Recorded agent scene actions"
    >
      <button
        onClick={() => {
          if (!replay) {
            user.current = view;
            setReplay(true);
          } else {
            setPlaying(false);
            setReplay(false);
            apply(user.current);
          }
        }}
      >
        {replay ? "Return to my view" : "Watch agent actions"}
      </button>
      {replay && (
        <>
          <button onClick={() => setPlaying((p) => !p)}>
            {playing ? "Pause agent replay" : "Play agent replay"}
          </button>
          <input
            aria-label="Agent action timeline"
            type="range"
            min={0}
            max={actions.length - 1}
            value={index}
            onChange={(e) => {
              setPlaying(false);
              setIndex(+e.target.value);
            }}
          />
          <label>
            Playback speed
            <select
              aria-label="Agent playback speed"
              value={speed}
              onChange={(e) => setSpeed(+e.target.value)}
            >
              {[0.5, 1, 2, 4].map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
          <span>
            Action {index + 1}/{actions.length}: {action?.payload.note}
          </span>
          <small>
            Recorded camera and scene actions · simulation time is shown
            separately below. Local exploration never changes this history.
          </small>
        </>
      )}
    </section>
  );
}
