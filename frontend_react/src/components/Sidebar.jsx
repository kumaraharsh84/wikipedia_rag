export default function Sidebar({ username, history, settings, onSettingsChange, onHistoryClick, onSignIn, onSignOut, onNewSearch, open, onClose, activeView, onViewChange }) {
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div className="fixed inset-0 z-30 md:hidden" style={{ background: "rgba(0,0,0,0.6)" }} onClick={onClose} />
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed left-0 top-0 bottom-0 h-screen w-64 flex flex-col z-40 transition-transform duration-300
          ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
        style={{ background: "#0c0e14", borderRight: "1px solid rgba(16,185,129,0.15)", fontFamily: "Manrope, sans-serif" }}
      >
        <div className="flex flex-col p-6 gap-4 h-full">

          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center"
                 style={{ background: "rgba(16,185,129,0.2)", borderRadius: "0.75rem" }}>
              <span className="material-symbols-outlined" style={{ color: "#10b981", fontVariationSettings: "'FILL' 1" }}>library_books</span>
            </div>
            <div>
              <h1 className="font-extrabold tracking-tighter" style={{ fontSize: "1.5rem", color: "#10b981", letterSpacing: "-0.02em" }}>WikiQA</h1>
              <p className="uppercase tracking-widest font-label" style={{ fontSize: "0.6rem", color: "#64748b", letterSpacing: "0.12em" }}>Knowledge Hub</p>
            </div>
          </div>

          {/* New Search */}
          <button
            onClick={() => { onNewSearch(); onClose(); }}
            className="flex items-center justify-center gap-2 font-semibold transition-all hover:scale-[1.02] active:scale-95"
            style={{
              marginTop: "0.5rem",
              padding: "0.75rem 1rem",
              background: "rgba(16,185,129,0.1)",
              color: "#10b981",
              borderRadius: "9999px",
              border: "1px solid rgba(16,185,129,0.2)",
              fontSize: "0.875rem",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "rgba(16,185,129,0.2)"}
            onMouseLeave={e => e.currentTarget.style.background = "rgba(16,185,129,0.1)"}
          >
            <span className="material-symbols-outlined text-sm">add</span>
            New Search
          </button>

          {/* Nav */}
          <nav className="flex-1 py-2 space-y-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
            <div className="px-3 py-2 uppercase tracking-widest font-semibold"
                 style={{ fontSize: "0.625rem", color: "#64748b", letterSpacing: "0.12em" }}>
              Navigation
            </div>

            {[
              { view: "chat",    icon: "chat",      label: "Research"  },
              { view: "history", icon: "history",   label: "History"   },
              { view: "eval",    icon: "bar_chart", label: "Benchmark" },
              { view: "settings",icon: "settings",  label: "Settings"  },
            ].map(({ view, icon, label }) => {
              const active = activeView === view;
              return (
                <button
                  key={view}
                  onClick={() => { onViewChange(view); onClose(); }}
                  className="w-full flex items-center gap-3 px-3 py-3 transition-all"
                  style={{
                    borderRadius: "9999px",
                    color: active ? "#10b981" : "#aaaab3",
                    fontWeight: active ? "700" : "600",
                    background: active ? "#11131a" : "transparent",
                    borderRight: active ? "2px solid #10b981" : "none",
                    fontSize: "0.875rem",
                  }}
                  onMouseEnter={e => { if (!active) { e.currentTarget.style.color = "#10b981"; e.currentTarget.style.background = "#171921"; } }}
                  onMouseLeave={e => { if (!active) { e.currentTarget.style.color = "#aaaab3"; e.currentTarget.style.background = "transparent"; } }}
                >
                  <span className="material-symbols-outlined"
                        style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}>{icon}</span>
                  {label}
                </button>
              );
            })}

            {/* Recent archive */}
            <div className="pt-4">
              <div className="px-3 py-2 uppercase tracking-widest font-semibold"
                   style={{ fontSize: "0.625rem", color: "#64748b", letterSpacing: "0.12em" }}>
                Recent Archive
              </div>
              {history?.length ? (
                history.slice(0, 5).map((item, i) => (
                  <button
                    key={item.id ?? i}
                    onClick={() => { onHistoryClick(item.query); onClose(); }}
                    className="w-full text-left px-3 py-2 truncate transition-all"
                    style={{ fontSize: "0.75rem", color: "#aaaab3", borderRadius: "9999px" }}
                    onMouseEnter={e => { e.currentTarget.style.color = "#10b981"; e.currentTarget.style.background = "#171921"; }}
                    onMouseLeave={e => { e.currentTarget.style.color = "#aaaab3"; e.currentTarget.style.background = "transparent"; }}
                  >
                    {item.query}
                  </button>
                ))
              ) : (
                <p className="px-3 py-2 italic" style={{ fontSize: "0.75rem", color: "#64748b" }}>
                  No recent research...
                </p>
              )}
            </div>
          </nav>

          {/* Footer links */}
          <div className="pt-4 flex flex-col gap-1" style={{ borderTop: "1px solid rgba(16,185,129,0.1)" }}>
            {username ? (
              <div className="flex items-center gap-3 px-3 py-2" style={{ borderRadius: "9999px" }}>
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                     style={{ background: "rgba(16,185,129,0.15)" }}>
                  <span className="material-symbols-outlined text-base" style={{ color: "#10b981" }}>person</span>
                </div>
                <span className="text-sm font-semibold truncate flex-1" style={{ color: "#e2e2eb" }}>{username}</span>
                <button onClick={onSignOut} title="Sign out"
                  style={{ color: "#64748b" }}
                  onMouseEnter={e => e.currentTarget.style.color = "#ffb4ab"}
                  onMouseLeave={e => e.currentTarget.style.color = "#64748b"}>
                  <span className="material-symbols-outlined text-base">logout</span>
                </button>
              </div>
            ) : (
              <SideFooterBtn icon="account_circle" label="Sign In" onClick={onSignIn} />
            )}
            <SideFooterBtn icon="help"   label="Help"    />
            <SideFooterBtn icon="shield" label="Privacy" />
          </div>

        </div>
      </aside>
    </>
  );
}

function SideFooterBtn({ icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2 transition-all"
      style={{ borderRadius: "9999px", color: "#aaaab3", fontSize: "0.875rem" }}
      onMouseEnter={e => { e.currentTarget.style.color = "#10b981"; e.currentTarget.style.background = "#171921"; }}
      onMouseLeave={e => { e.currentTarget.style.color = "#aaaab3"; e.currentTarget.style.background = "transparent"; }}
    >
      <span className="material-symbols-outlined text-lg">{icon}</span>
      {label}
    </button>
  );
}

export function SettingsPanel({ settings, onChange }) {
  return (
    <div className="p-6 space-y-6 max-w-xl mx-auto pt-10">
      <h2 className="font-headline font-bold text-xl" style={{ color: "#e2e2eb" }}>Search Settings</h2>

      {[
        { key: "top_k", label: "Passages (top_k)", min: 1, max: 10 },
        { key: "num_articles", label: "Articles to Fetch", min: 1, max: 5 },
      ].map(({ key, label, min, max }) => (
        <div key={key} className="p-5 space-y-3" style={{ background: "#11131a", borderRadius: "1rem" }}>
          <div className="flex justify-between items-center">
            <label className="font-label text-xs font-bold uppercase tracking-widest" style={{ color: "#aaaab3" }}>{label}</label>
            <span className="font-label text-sm font-bold" style={{ color: "#10b981" }}>{settings[key]}</span>
          </div>
          <input type="range" min={min} max={max} step={1} value={settings[key]}
            onChange={e => onChange(key, Number(e.target.value))}
            className="w-full" style={{ accentColor: "#10b981" }} />
          <div className="flex justify-between text-xs" style={{ color: "#64748b" }}>
            <span>{min}</span><span>{max}</span>
          </div>
        </div>
      ))}

      <div className="p-5 flex items-center justify-between" style={{ background: "#11131a", borderRadius: "1rem" }}>
        <div>
          <p className="font-label text-xs font-bold uppercase tracking-widest" style={{ color: "#aaaab3" }}>Cross-encoder Rerank</p>
          <p className="text-xs mt-1" style={{ color: "#64748b" }}>Higher accuracy, slightly slower</p>
        </div>
        <button onClick={() => onChange("rerank", !settings.rerank)}
          className="relative w-12 h-6 rounded-full transition-colors"
          style={{ background: settings.rerank ? "#10b981" : "#33343b" }}>
          <span className={`absolute top-1 w-4 h-4 rounded-full transition-transform ${settings.rerank ? "translate-x-7" : "translate-x-1"}`}
                style={{ background: settings.rerank ? "#003924" : "#aaaab3" }} />
        </button>
      </div>

      <p className="text-xs pt-2" style={{ color: "#64748b" }}>Settings apply to the next query.</p>
    </div>
  );
}
