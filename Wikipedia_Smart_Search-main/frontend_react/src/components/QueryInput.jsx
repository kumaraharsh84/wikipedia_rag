import { useState, useRef } from "react";

const MAX = 300;

export default function QueryInput({ onSubmit, loading, onAbort }) {
  const [text, setText] = useState("");
  const inputRef = useRef(null);

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const q = text.trim();
    if (!q || loading || q.length > MAX) return;
    onSubmit(q);
    setText("");
  }

  return (
    <div className="absolute bottom-0 left-0 w-full p-6 bg-gradient-to-t from-surface via-surface to-transparent z-20">
      <div className="max-w-3xl mx-auto relative group">
        {/* Focus glow */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/20 to-primary/10 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500 pointer-events-none" />

        {/* Input container */}
        <div className="relative flex items-center rounded-2xl p-2 pl-6 pr-3 shadow-2xl"
             style={{ background: "rgba(51,52,59,0.6)", backdropFilter: "blur(24px)" }}>
          <input
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX))}
            onKeyDown={handleKey}
            placeholder="Ask the archivist anything..."
            disabled={loading}
            className="flex-1 bg-transparent border-none outline-none font-body py-4"
            style={{
              color: "#e2e2eb",
              fontSize: "1.125rem",
            }}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="p-2 transition-colors"
              style={{ color: "#908fa0" }}
              onMouseEnter={e => e.currentTarget.style.color = "#69f6b8"}
              onMouseLeave={e => e.currentTarget.style.color = "#908fa0"}
            >
              <span className="material-symbols-outlined">attach_file</span>
            </button>
            {loading ? (
              <button
                onClick={onAbort}
                title="Stop generating"
                className="flex items-center justify-center transition-all active:scale-95"
                style={{
                  width: "3rem", height: "3rem", borderRadius: "0.75rem",
                  background: "rgba(255,180,171,0.15)", color: "#ffb4ab", flexShrink: 0,
                  border: "1px solid rgba(255,180,171,0.3)",
                }}
              >
                <span className="material-symbols-outlined text-xl">stop</span>
              </button>
            ) : (
              <button
                onClick={submit}
                disabled={!text.trim() || text.length > MAX}
                className="flex items-center justify-center transition-all hover:shadow-lg active:scale-100 disabled:opacity-40"
                style={{
                  width: "3rem", height: "3rem", borderRadius: "0.75rem",
                  background: "#69f6b8", color: "#003923", flexShrink: 0,
                }}
                onMouseEnter={e => { e.currentTarget.style.boxShadow = "0 8px 20px rgba(105,246,184,0.2)"; }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = "none"; }}
              >
                <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="text-center mt-4 uppercase tracking-[0.2em] font-label"
         style={{ fontSize: "0.625rem", color: "#464554" }}>
        Verified by Wikipedia Archives &amp; Global Intelligence Network
      </p>
    </div>
  );
}
