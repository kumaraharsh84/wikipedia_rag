export default function PassageCard({ passage, index }) {
  const score = typeof passage.score === "number" ? passage.score : null;
  const title = passage.source?.title ?? `Passage ${index + 1}`;
  const text = passage.passage ?? passage.text ?? "";

  // Colour-coded relevance tier
  const relevance = score === null ? null
    : score >= 0.70 ? { label: "High Relevance",   color: "#69f6b8", bg: "rgba(105,246,184,0.08)", border: "rgba(105,246,184,0.35)" }
    : score >= 0.40 ? { label: "Medium Relevance", color: "#ffb783", bg: "rgba(255,183,131,0.08)", border: "rgba(255,183,131,0.25)" }
    :                 { label: "Low Relevance",     color: "#aaaab3", bg: "rgba(170,170,179,0.06)", border: "rgba(170,170,179,0.18)" };

  return (
    <div
      className="rounded-xl p-4 space-y-3 transition-all duration-200"
      style={{
        background: "#0f1119",
        border: `1px solid ${relevance?.border ?? "rgba(70,72,79,0.3)"}`,
      }}
    >
      {/* Header row */}
      <div className="flex justify-between items-start gap-2">
        <h4 className="font-headline font-bold text-sm leading-snug" style={{ color: "#e5e4ed" }}>
          {title}
        </h4>
        {relevance && (
          <span
            className="font-label text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full flex-shrink-0"
            style={{ background: relevance.bg, color: relevance.color }}
          >
            {relevance.label}
          </span>
        )}
      </div>

      {/* Confidence bar */}
      {score !== null && (
        <div className="flex items-center gap-2">
          <span className="font-label text-[10px] uppercase tracking-widest" style={{ color: "#64748b" }}>
            Confidence
          </span>
          <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: "#1e1f26" }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, score * 100)}%`, background: relevance?.color ?? "#69f6b8" }}
            />
          </div>
          <span className="font-label text-[10px] font-bold w-8 text-right" style={{ color: relevance?.color ?? "#aaaab3" }}>
            {(score * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {/* Passage text */}
      <p className="text-sm leading-relaxed" style={{ color: "#aaaab3" }}>{text}</p>

      {/* Source link */}
      {passage.source?.url && (
        <a
          href={passage.source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs flex items-center gap-1 transition-colors"
          style={{ color: "rgba(105,246,184,0.45)" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#69f6b8")}
          onMouseLeave={e => (e.currentTarget.style.color = "rgba(105,246,184,0.45)")}
        >
          <span className="material-symbols-outlined text-xs">open_in_new</span>
          {passage.source.url.replace("https://en.wikipedia.org/wiki/", "Wikipedia: ")}
        </a>
      )}
    </div>
  );
}
