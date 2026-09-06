import { useEffect, useState } from "react";
type Metrics = {
  conditions: Record<
    string,
    {
      simulation_replicates: number;
      uncensored_replicates: number;
      mean_bipolar_dwell_s: number;
      replicate_sd_s: number | null;
      final_pole_count_distribution: Record<string, number>;
    }
  >;
  runs: {
    condition: string;
    seed: number;
    time_to_bipolar_s: number | null;
    right_censored: boolean;
    observation_end_s: number;
    final_pole_count: number;
  }[];
  analysis_plan: { threshold_um: number; dwell_s: number };
  threshold_sensitivity: unknown;
};
export default function SpindleMetrics({ url }: { url: string }) {
  const [metrics, setMetrics] = useState<Metrics>(),
    [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    setMetrics(undefined);
    setError("");
    fetch(url, { signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("Ensemble metrics unavailable at this event");
        const m = await r.json();
        if (!m.conditions || !Array.isArray(m.runs) || !m.analysis_plan)
          throw Error("Invalid spindle metrics");
        if (!abort.signal.aborted) setMetrics(m);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [url]);
  if (error) return <p role="alert">{error}</p>;
  if (!metrics) return <p role="status">Loading numerical ensemble…</p>;
  return (
    <section className="spindle-metrics" aria-label="Spindle ensemble metrics">
      <h4>Numerical ensemble</h4>
      <p>
        Exactly two distance-connected clusters; threshold{" "}
        {metrics.analysis_plan.threshold_um} µm; required dwell{" "}
        {metrics.analysis_plan.dwell_s} s. Simulation seeds measure numerical
        variation, not biological uncertainty.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Condition</th>
              <th>Seeds</th>
              <th>Final pole counts</th>
              <th>Mean bipolar dwell</th>
              <th>Across-seed SD</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.conditions).map(([name, c]) => (
              <tr key={name}>
                <th>{name}</th>
                <td>{c.simulation_replicates}</td>
                <td>
                  {Object.entries(c.final_pole_count_distribution)
                    .map(([p, n]) => `${p} poles: ${n}`)
                    .join("; ")}
                </td>
                <td>{c.mean_bipolar_dwell_s.toFixed(3)} s</td>
                <td>
                  {c.replicate_sd_s == null
                    ? "Unavailable (one seed)"
                    : `${c.replicate_sd_s.toFixed(3)} s`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>All trajectories and censoring</summary>
        <ul>
          {metrics.runs.map((r) => (
            <li key={`${r.condition}-${r.seed}`}>
              {r.condition} · seed {r.seed}:{" "}
              {r.right_censored
                ? `no qualifying onset observed by ${r.observation_end_s} s (right-censored)`
                : `qualifying bipolar onset ${r.time_to_bipolar_s} s`}
              ; final pole count {r.final_pole_count}.
            </li>
          ))}
        </ul>
      </details>
      <details>
        <summary>Threshold sensitivity</summary>
        <pre>{JSON.stringify(metrics.threshold_sensitivity, null, 2)}</pre>
      </details>
    </section>
  );
}
