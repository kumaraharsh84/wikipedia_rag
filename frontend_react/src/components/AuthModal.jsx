import { useState } from "react";

export default function AuthModal({ onClose, onAuth }) {
  const [tab, setTab]         = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]   = useState(false);
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await onAuth(tab, username.trim(), password);
      onClose();
    } catch (err) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    /* Full-screen backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
         style={{ background: "rgba(12,14,20,0.55)", backdropFilter: "blur(20px)" }}
         onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>

      {/* Decorative background blobs (same as stitch) */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full"
             style={{ background: "rgba(105,246,184,0.12)", filter: "blur(120px)" }} />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full"
             style={{ background: "rgba(255,183,131,0.07)", filter: "blur(120px)" }} />
      </div>

      {/* Modal card */}
      <div className="relative z-10 w-full max-w-[480px] flex flex-col overflow-hidden shadow-2xl"
           style={{ background: "#191b22", borderRadius: "1rem" }}>

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 transition-colors"
          style={{ color: "#908fa0" }}
          onMouseEnter={e => e.currentTarget.style.color = "#e2e2eb"}
          onMouseLeave={e => e.currentTarget.style.color = "#908fa0"}
        >
          <span className="material-symbols-outlined">close</span>
        </button>

        {/* Decorative shield corner */}
        <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none select-none">
          <span className="material-symbols-outlined text-6xl" style={{ color: "#69f6b8" }}>security</span>
        </div>

        {/* Header / Branding */}
        <div className="px-8 pt-10 pb-6 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 mb-6"
               style={{ background: "#282a30", borderRadius: "0.75rem" }}>
            <span className="material-symbols-outlined text-4xl" style={{ color: "#10b981", fontVariationSettings: "'FILL' 1" }}>
              auto_stories
            </span>
          </div>
          <h2 className="font-headline font-bold tracking-tight" style={{ fontSize: "1.875rem", color: "#e2e2eb" }}>WikiQA</h2>
          <p className="font-label text-xs tracking-widest uppercase mt-1" style={{ color: "#908fa0", letterSpacing: "0.12em" }}>
            Intelligence Redefined
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex px-8" style={{ borderBottom: "1px solid rgba(70,69,84,0.2)" }}>
          {["login", "register"].map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError(""); }}
              className="flex-1 py-4 text-sm font-semibold tracking-wide transition-colors capitalize"
              style={{
                color: tab === t ? "#10b981" : "#c7c4d7",
                borderBottom: tab === t ? "2px solid #10b981" : "2px solid transparent",
              }}
            >
              {t === "login" ? "Login" : "Register"}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-8 space-y-6">

          {/* Archive ID / Username */}
          <div className="space-y-2">
            <label className="font-label text-xs font-bold tracking-widest uppercase px-1"
                   style={{ color: "#908fa0", letterSpacing: "0.1em" }}>
              Archive ID / Username
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <span className="material-symbols-outlined text-xl transition-colors"
                      style={{ color: "var(--icon-col, #908fa0)" }}>fingerprint</span>
              </div>
              <input
                required
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. archivist_01"
                className="w-full border-none outline-none font-body transition-all"
                style={{
                  background: "#33343b",
                  borderRadius: "0.75rem",
                  padding: "1rem 1rem 1rem 3rem",
                  color: "#e2e2eb",
                  fontSize: "0.9375rem",
                }}
                onFocus={e => e.currentTarget.style.boxShadow = "0 0 0 2px rgba(16,185,129,0.3)"}
                onBlur={e => e.currentTarget.style.boxShadow = "none"}
              />
            </div>
          </div>

          {/* Secret Key / Password */}
          <div className="space-y-2">
            <div className="flex justify-between items-center px-1">
              <label className="font-label text-xs font-bold tracking-widest uppercase"
                     style={{ color: "#908fa0", letterSpacing: "0.1em" }}>
                Secret Key
              </label>
              <span className="font-label text-[10px] font-bold uppercase tracking-tight cursor-pointer"
                    style={{ color: "#10b981" }}>
                Recover Access
              </span>
            </div>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <span className="material-symbols-outlined text-xl" style={{ color: "#908fa0" }}>key</span>
              </div>
              <input
                required
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full border-none outline-none font-body transition-all"
                style={{
                  background: "#33343b",
                  borderRadius: "0.75rem",
                  padding: "1rem 3rem 1rem 3rem",
                  color: "#e2e2eb",
                  fontSize: "0.9375rem",
                }}
                onFocus={e => e.currentTarget.style.boxShadow = "0 0 0 2px rgba(16,185,129,0.3)"}
                onBlur={e => e.currentTarget.style.boxShadow = "none"}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center transition-colors"
                style={{ color: "#908fa0" }}
              >
                <span className="material-symbols-outlined text-xl">
                  {showPw ? "visibility" : "visibility_off"}
                </span>
              </button>
            </div>
          </div>

          {/* Remember me */}
          <div className="flex items-center gap-3 px-1">
            <input
              type="checkbox"
              id="remember"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="w-5 h-5 cursor-pointer"
              style={{ borderRadius: "0.375rem", accentColor: "#10b981" }}
            />
            <label htmlFor="remember" className="text-sm cursor-pointer select-none"
                   style={{ color: "#c7c4d7" }}>
              Maintain terminal session
            </label>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm flex items-center gap-2 px-1" style={{ color: "#ffb4ab" }}>
              <span className="material-symbols-outlined text-base">error</span>
              {error}
            </p>
          )}

          {/* Sign In button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 font-headline font-bold text-lg transition-all active:scale-[0.98] disabled:opacity-60"
              style={{
                background: "linear-gradient(to right, #10b981, #059669)",
                borderRadius: "0.75rem",
                padding: "1rem",
                color: "#003924",
                boxShadow: "0 8px 30px rgba(16,185,129,0.15)",
              }}
            >
              {loading ? (
                <span className="font-label text-base">Processing…</span>
              ) : (
                <>
                  <span>{tab === "login" ? "Sign In" : "Create Archive"}</span>
                  <span className="material-symbols-outlined text-xl">arrow_forward</span>
                </>
              )}
            </button>
          </div>

          {/* Federated access divider */}
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full" style={{ borderTop: "1px solid rgba(70,69,84,0.15)" }} />
            </div>
            <div className="relative flex justify-center">
              <span className="px-4 font-label text-[10px] uppercase tracking-widest"
                    style={{ background: "#191b22", color: "#908fa0", letterSpacing: "0.15em" }}>
                Federated Access
              </span>
            </div>
          </div>

          {/* Google + GitHub */}
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              className="flex items-center justify-center gap-3 py-3 transition-colors group"
              style={{ background: "#282a30", borderRadius: "0.75rem" }}
              onMouseEnter={e => e.currentTarget.style.background = "#373940"}
              onMouseLeave={e => e.currentTarget.style.background = "#282a30"}
            >
              <span className="material-symbols-outlined text-lg" style={{ color: "#908fa0" }}>language</span>
              <span className="text-xs font-semibold tracking-wide" style={{ color: "#e2e2eb" }}>Google</span>
            </button>
            <button
              type="button"
              className="flex items-center justify-center gap-3 py-3 transition-colors"
              style={{ background: "#282a30", borderRadius: "0.75rem" }}
              onMouseEnter={e => e.currentTarget.style.background = "#373940"}
              onMouseLeave={e => e.currentTarget.style.background = "#282a30"}
            >
              <span className="material-symbols-outlined text-lg" style={{ color: "#908fa0" }}>terminal</span>
              <span className="text-xs font-semibold tracking-wide" style={{ color: "#e2e2eb" }}>GitHub</span>
            </button>
          </div>
        </form>

        {/* Footer */}
        <div className="px-8 pb-8 text-center" style={{ background: "rgba(12,14,20,0.4)" }}>
          <p className="text-xs leading-relaxed" style={{ color: "#908fa0" }}>
            By entering the archive, you agree to our{" "}
            <a href="#" className="underline transition-colors"
               style={{ color: "#c7c4d7", textDecorationColor: "rgba(16,185,129,0.4)" }}>
              Protocol Standards
            </a>{" "}
            and{" "}
            <span style={{ color: "#c7c4d7" }}>Data Sovereignty</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
