import { useState, useEffect, useRef } from "react";
import { askStream, fetchHistory, login, register } from "./api";
import ChatMessage from "./components/ChatMessage";
import QueryInput from "./components/QueryInput";
import Sidebar, { SettingsPanel } from "./components/Sidebar";
import AuthModal from "./components/AuthModal";
import HistoryView from "./components/HistoryView";
import EvalView from "./components/EvalView";

const LS_TOKEN = "wikiqa_token";
const LS_USER  = "wikiqa_username";

const SAMPLES = [
  { icon: "science",          label: "What is the Fermi paradox?",      sub: "Explore the contradiction between the lack of evidence of extraterrestrial life." },
  { icon: "psychology",       label: "Explain quantum entanglement",     sub: "Understand how particles remain connected even over vast distances." },
  { icon: "account_balance",  label: "History of the Roman Empire",      sub: "Trace the rise and fall of one of history's most powerful civilizations." },
  { icon: "flare",            label: "How do black holes form?",         sub: "Discover the cosmic life cycle of massive stars ending in singularity." },
];

export default function App() {
  /* Auth */
  const [token, setToken]         = useState(() => localStorage.getItem(LS_TOKEN) || "");
  const [username, setUsername]   = useState(() => localStorage.getItem(LS_USER)  || "");
  const [showAuth, setShowAuth]   = useState(false);

  /* Chat */
  const [messages, setMessages]   = useState([]);
  const [loading, setLoading]     = useState(false);
  const abortRef                  = useRef(null);

  /* Navigation */
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeView, setActiveView]   = useState("chat"); // chat | history | settings

  /* History */
  const [history, setHistory]           = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  /* Settings */
  const [settings, setSettings] = useState({ top_k: 5, num_articles: 2, rerank: true });

  /* Scroll anchor */
  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* Load history */
  useEffect(() => {
    if (!token) { setHistory([]); return; }
    setHistoryLoading(true);
    fetchHistory(token)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  }, [token]);

  /* ── Handlers ── */
  async function handleAuth(mode, uname, pw) {
    const fn = mode === "login" ? login : register;
    const data = await fn(uname, pw);
    setToken(data.access_token);
    setUsername(data.username);
    localStorage.setItem(LS_TOKEN, data.access_token);
    localStorage.setItem(LS_USER, data.username);
  }

  function handleSignOut() {
    setToken(""); setUsername("");
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
    setHistory([]);
  }

  function handleAbort() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setMessages((prev) => prev.filter((m) => m.role !== "streaming"));
  }

  async function handleSubmit(query) {
    setActiveView("chat");

    // Build conversation history from existing completed messages
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const msgId = Date.now();
    setMessages((prev) => [...prev, { role: "streaming", id: msgId, content: "", status: "" }]);

    try {
      for await (const chunk of askStream(query, {
        top_k: settings.top_k,
        num_articles: settings.num_articles,
        rerank: settings.rerank,
        token,
        history,
        signal: controller.signal,
      })) {
        if (chunk.type === "status") {
          setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, status: chunk.content } : m));
        } else if (chunk.type === "token") {
          setMessages((prev) => prev.map((m) =>
            m.id === msgId ? { ...m, content: m.content + chunk.content, status: "" } : m
          ));
        } else if (chunk.type === "done") {
          setMessages((prev) => prev.map((m) =>
            m.id === msgId ? {
              role: "assistant",
              content: chunk.answer,
              passages: chunk.passages,
              sources: chunk.sources,
              related_topics: chunk.related_topics,
              latency_ms: chunk.latency_ms,
              cached: chunk.cached,
            } : m
          ));
          if (token) fetchHistory(token).then(setHistory).catch((e) => console.warn("History refresh failed:", e));
        } else if (chunk.type === "error") {
          setMessages((prev) =>
            prev.filter((m) => m.id !== msgId).concat({ role: "error", content: chunk.content })
          );
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setMessages((prev) =>
          prev.filter((m) => m.id !== msgId).concat({ role: "error", content: err.message || "Something went wrong." })
        );
      }
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }

  function handleNewSearch() {
    setMessages([]);
    setActiveView("chat");
  }

  /* ── Render ── */
  return (
    <div className="flex h-screen bg-background text-on-surface overflow-hidden">

      {/* Sidebar */}
      <Sidebar
        username={username}
        history={history}
        settings={settings}
        onSettingsChange={(k, v) => setSettings((p) => ({ ...p, [k]: v }))}
        onHistoryClick={(q) => { handleSubmit(q); setSidebarOpen(false); }}
        onSignIn={() => setShowAuth(true)}
        onSignOut={handleSignOut}
        onNewSearch={handleNewSearch}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeView={activeView}
        onViewChange={setActiveView}
      />

      {/* Main stage */}
      <div className="flex flex-col flex-1 min-w-0 md:ml-64">

        {/* Mobile top bar */}
        <header className="fixed top-0 right-0 left-0 md:left-64 h-16 z-20 bg-background/80 backdrop-blur-xl border-b border-primary/10 flex items-center justify-between px-6 md:hidden">
          <div className="flex items-center gap-2">
            <button onClick={() => setSidebarOpen(true)} className="text-primary">
              <span className="material-symbols-outlined">menu</span>
            </button>
            <h1 className="text-xl font-extrabold text-primary font-headline">WikiQA</h1>
          </div>
          <button onClick={() => username ? null : setShowAuth(true)} className="text-primary">
            <span className="material-symbols-outlined">account_circle</span>
          </button>
        </header>

        {/* Content area */}
        {activeView === "settings" ? (
          <div className="flex-1 overflow-y-auto pt-16 md:pt-0">
            <SettingsPanel settings={settings} onChange={(k, v) => setSettings((p) => ({ ...p, [k]: v }))} />
          </div>
        ) : activeView === "eval" ? (
          <div className="flex-1 overflow-y-auto pt-16 md:pt-0">
            <EvalView />
          </div>
        ) : activeView === "history" ? (
          <div className="flex-1 overflow-y-auto pt-16 md:pt-0">
            <HistoryView
              history={history}
              loading={historyLoading}
              username={username}
              onQueryClick={(q) => { handleSubmit(q); setActiveView("chat"); }}
              onSignIn={() => setShowAuth(true)}
              onNewSearch={() => { handleNewSearch(); }}
            />
          </div>
        ) : (
          /* Chat view */
          <div className="flex-1 relative overflow-hidden">
            {/* Background decoration */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-20 z-0">
              <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/10 blur-[120px] rounded-full" />
              <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-tertiary/5 blur-[120px] rounded-full" />
            </div>

            {/* Chat scroll area */}
            <div className="h-full overflow-y-auto px-4 md:px-6 pt-20 md:pt-12 pb-48 relative z-10">
              {messages.length === 0 && !loading ? (
                <EmptyState onSample={handleSubmit} />
              ) : (
                <div className="max-w-3xl mx-auto space-y-10">
                  {messages.map((msg, i) => (
                    <ChatMessage key={i} msg={msg} onTopicClick={handleSubmit} />
                  ))}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            {/* Pinned input */}
            <QueryInput onSubmit={handleSubmit} loading={loading} onAbort={handleAbort} />
          </div>
        )}
      </div>

      {/* Auth modal */}
      {showAuth && (
        <AuthModal
          onClose={() => setShowAuth(false)}
          onAuth={handleAuth}
        />
      )}
    </div>
  );
}

function EmptyState({ onSample }) {
  return (
    <div className="max-w-3xl w-full mx-auto flex flex-col items-center text-center space-y-10 pt-8 md:pt-14 px-4">

        {/* Archive Ready badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 font-label text-xs tracking-wider uppercase"
             style={{ background: "#1e1f26", borderRadius: "9999px", color: "#10b981", border: "1px solid rgba(16,185,129,0.15)" }}>
          <span className="material-symbols-outlined text-sm">auto_awesome</span>
          Archive Ready
        </div>

        {/* Hero headline */}
        <h2 className="font-headline font-extrabold tracking-tighter leading-tight"
            style={{ fontSize: "clamp(2.2rem, 5vw, 3.5rem)", letterSpacing: "-0.02em", color: "#e2e2eb" }}>
          What would you like to <br />
          <span style={{
            background: "linear-gradient(to right, #10b981, #69f6b8)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            research today?
          </span>
        </h2>

        {/* Sample question cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
          {SAMPLES.map((s) => (
            <button
              key={s.label}
              onClick={() => onSample(s.label)}
              className="group flex flex-col items-start text-left transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
              style={{
                background: "#11131a",
                borderRadius: "1.25rem",
                padding: "1.5rem",
                border: "1px solid rgba(70,69,84,0.2)",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "#1a1c24"; e.currentTarget.style.borderColor = "rgba(105,246,184,0.15)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "#11131a"; e.currentTarget.style.borderColor = "rgba(70,69,84,0.2)"; }}
            >
              <span className="material-symbols-outlined mb-3 transition-opacity opacity-60 group-hover:opacity-100"
                    style={{ color: "#10b981" }}>{s.icon}</span>
              <span className="font-headline font-bold text-base" style={{ color: "#e2e2eb" }}>{s.label}</span>
              <span className="text-sm mt-1.5 leading-relaxed text-left" style={{ color: "#aaaab3" }}>{s.sub}</span>
            </button>
          ))}
        </div>
    </div>
  );
}
