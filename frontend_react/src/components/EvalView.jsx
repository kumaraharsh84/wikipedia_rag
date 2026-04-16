import { useState } from "react";

const BASE = "/api";

function Bar({ value, max = 1, color = "#69f6b8" }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 rounded-full overflow-hidden" style={{ background: "#1e1f26", height: "8px" }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="font-label text-xs font-bold w-10 text-right" style={{ color }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

function MetricCard({ label, value, description, color }) {
  return (
    <div className="p-6 space-y-3 rounded-xl" style={{ background: "#11131a" }}>
      <div className="flex justify-between items-start">
        <div>
          <p className="font-label text-xs font-bold uppercase tracking-widest" style={{ color: "#aaaab3" }}>{label}</p>
          <p className="text-xs mt-1" style={{ color: "#64748b" }}>{description}</p>
        </div>
        <span className="font-headline font-extrabold text-2xl" style={{ color }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <Bar value={value} color={color} />
    </div>
  );
}

export default function EvalView() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runEval() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${BASE}/evaluate`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(e.message || "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-6 md:px-10 py-10 max-w-4xl mx-auto">

      {/* Header */}
      <div className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-2">
          <h2 className="font-headline font-extrabold tracking-tight" style={{ fontSize: "clamp(1.75rem,4vw,2.5rem)", color: "#e5e4ed" }}>
            System Benchmark
          </h2>
          <p style={{ color: "#aaaab3" }}>
            Precision@k, MRR, and latency across {result?.queries_run ?? 5} benchmark queries.
          </p>
        </div>
        <button
          onClick={runEval}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-full font-headline font-bold text-sm transition-all active:scale-95 disabled:opacity-50"
          style={{ background: "linear-gradient(to right, #69f6b8, #06b77f)", color: "#003923", boxShadow: "0 8px 20px rgba(105,246,184,0.2)" }}
        >
          <span className={`material-symbols-outlined text-lg ${loading ? "animate-spin" : ""}`}>
            {loading ? "progress_activity" : "play_arrow"}
          </span>
          {loading ? "Running…" : "Run Benchmark"}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl mb-6" style={{ background: "rgba(255,180,171,0.1)", border: "1px solid rgba(255,180,171,0.2)" }}>
          <span className="material-symbols-outlined" style={{ color: "#ffb4ab" }}>error</span>
          <p className="text-sm" style={{ color: "#ffb4ab" }}>{error}</p>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <div className="w-20 h-20 rounded-full flex items-center justify-center" style={{ background: "rgba(105,246,184,0.08)" }}>
            <span className="material-symbols-outlined text-4xl" style={{ color: "#69f6b8" }}>bar_chart</span>
          </div>
          <p style={{ color: "#aaaab3" }}>Click "Run Benchmark" to evaluate the RAG pipeline.</p>
          <p className="text-xs" style={{ color: "#464554" }}>Runs {5} queries — takes ~30s</p>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <span className="material-symbols-outlined text-5xl animate-spin" style={{ color: "#69f6b8" }}>progress_activity</span>
          <p style={{ color: "#aaaab3" }}>Evaluating pipeline quality…</p>
        </div>
      )}

      {result && (
        <div className="space-y-8">

          {/* Summary metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <MetricCard
              label="Precision@k"
              value={result.mean_precision_at_k}
              description="Fraction of top-k passages containing answer keywords"
              color="#69f6b8"
            />
            <MetricCard
              label="MRR@k"
              value={result.mean_mrr}
              description="Mean Reciprocal Rank — how high the first relevant passage ranks"
              color="#77e6ff"
            />
            {result.mean_faithfulness != null ? (
              <MetricCard
                label="Faithfulness"
                value={result.mean_faithfulness}
                description="LLM-as-judge: answer grounded in retrieved passages (not hallucinated)"
                color="#c084fc"
              />
            ) : (
              <div className="p-6 space-y-2 rounded-xl flex flex-col justify-center" style={{ background: "#11131a", border: "1px dashed rgba(70,69,84,0.5)" }}>
                <p className="font-label text-xs font-bold uppercase tracking-widest" style={{ color: "#aaaab3" }}>Faithfulness</p>
                <p className="text-xs" style={{ color: "#464554" }}>
                  LLM-as-judge scoring — set <code className="px-1 rounded" style={{ background: "#1e1f26" }}>GROQ_API_KEY</code> to enable
                </p>
              </div>
            )}
            <div className="p-6 space-y-3 rounded-xl" style={{ background: "#11131a" }}>
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-label text-xs font-bold uppercase tracking-widest" style={{ color: "#aaaab3" }}>Avg Latency</p>
                  <p className="text-xs mt-1" style={{ color: "#64748b" }}>End-to-end response time</p>
                </div>
                <span className="font-headline font-extrabold text-2xl" style={{ color: "#ffb783" }}>
                  {result.mean_latency_ms >= 1000
                    ? `${(result.mean_latency_ms / 1000).toFixed(1)}s`
                    : `${Math.round(result.mean_latency_ms)}ms`}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 rounded-full overflow-hidden" style={{ background: "#1e1f26", height: "8px" }}>
                  <div className="h-full rounded-full" style={{
                    width: `${Math.min(100, (result.mean_latency_ms / 5000) * 100)}%`,
                    background: "#ffb783"
                  }} />
                </div>
                <span className="font-label text-xs font-bold w-10 text-right" style={{ color: "#ffb783" }}>
                  {result.successful}/{result.queries_run}
                </span>
              </div>
            </div>
          </div>

          {/* Per-query breakdown */}
          <div className="rounded-xl overflow-hidden" style={{ background: "#11131a" }}>
            <div className="px-6 py-4" style={{ borderBottom: "1px solid rgba(70,72,79,0.3)" }}>
              <h3 className="font-headline font-bold" style={{ color: "#e5e4ed" }}>Per-Query Results</h3>
            </div>
            <div className="divide-y" style={{ borderColor: "rgba(70,72,79,0.2)" }}>
              {result.per_query.map((q, i) => (
                <div key={i} className="px-6 py-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm font-semibold flex-1" style={{ color: "#e5e4ed" }}>{q.query}</p>
                    {q.error ? (
                      <span className="font-label text-xs px-2 py-1 rounded-full flex-shrink-0" style={{ background: "rgba(255,180,171,0.1)", color: "#ffb4ab" }}>
                        Error
                      </span>
                    ) : (
                      <span className="font-label text-xs px-2 py-1 rounded-full flex-shrink-0" style={{ background: "rgba(105,246,184,0.1)", color: "#69f6b8" }}>
                        {q.latency_ms >= 1000 ? `${(q.latency_ms / 1000).toFixed(1)}s` : `${Math.round(q.latency_ms)}ms`}
                      </span>
                    )}
                  </div>
                  {!q.error && (
                    <div className={`grid gap-4 ${q.faithfulness != null ? "grid-cols-3" : "grid-cols-2"}`}>
                      <div>
                        <p className="font-label text-[10px] uppercase tracking-widest mb-1" style={{ color: "#64748b" }}>Precision@k</p>
                        <Bar value={q.precision_at_k} color="#69f6b8" />
                      </div>
                      <div>
                        <p className="font-label text-[10px] uppercase tracking-widest mb-1" style={{ color: "#64748b" }}>MRR</p>
                        <Bar value={q.mrr} color="#77e6ff" />
                      </div>
                      {q.faithfulness != null && (
                        <div>
                          <p className="font-label text-[10px] uppercase tracking-widest mb-1" style={{ color: "#64748b" }}>Faithfulness</p>
                          <Bar value={q.faithfulness} color="#c084fc" />
                        </div>
                      )}
                    </div>
                  )}
                  {q.error && <p className="text-xs" style={{ color: "#ffb4ab" }}>{q.error}</p>}
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <p className="text-center font-label text-xs uppercase tracking-widest" style={{ color: "#464554" }}>
            Evaluated on {result.queries_run} benchmark queries · k={result.k}
          </p>
        </div>
      )}
    </div>
  );
}
