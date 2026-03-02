/**
 * AppShell — STEP 1 scaffold.
 * Full implementation in STEP 4 (layout, topbar, sidebar, panels).
 * STEP 6: Chat view. STEP 7: Pipeline canvas. STEP 8: Right panel.
 *
 * CRITICAL RULES (do not break in future steps):
 * - ChatInput must ALWAYS be visible — never unmount it.
 * - PipelineCanvas uses visibility:hidden (not unmount) when switching to chat.
 * - This component is the root layout — all routes render inside it.
 */
export default function AppShell() {
  return (
    <div className="flex flex-col h-screen bg-drs-bg text-drs-text font-sans">
      {/* Topbar — STEP 4 */}
      <header className="h-12 flex-shrink-0 border-b border-drs-border bg-drs-s1 flex items-center px-5 gap-4">
        <span className="text-drs-accent font-semibold tracking-wide">◈ DRS</span>
        <span className="ml-auto text-drs-faint text-xs font-mono">STEP 1 scaffold</span>
      </header>

      {/* Main content — STEP 4, 6, 7, 8 */}
      <div className="flex flex-1 overflow-hidden">
        {/* Document Sidebar — STEP 4 */}
        <aside className="w-[260px] flex-shrink-0 border-r border-drs-border bg-drs-s1 flex flex-col">
          <div className="p-4 border-b border-drs-border">
            <button className="w-full text-left text-sm text-drs-muted hover:text-drs-text transition-colors">
              + Nuovo documento
            </button>
          </div>
          <div className="flex-1 p-4 text-drs-faint text-xs font-mono">
            DocumentSidebar — STEP 4
          </div>
        </aside>

        {/* Main area — Chat (STEP 6) / Pipeline (STEP 7) */}
        <main className="flex-1 flex items-center justify-center overflow-hidden">
          <div className="text-center animate-fade-in">
            <div className="text-5xl text-drs-accent mb-3">◈</div>
            <div className="text-2xl font-light text-drs-text mb-1">DRS</div>
            <div className="text-drs-muted text-sm">Deep Research System</div>
            <div className="mt-6 text-drs-faint text-xs font-mono">
              STEP 1 scaffolding — Chat in STEP 6, Pipeline in STEP 7
            </div>
          </div>
        </main>

        {/* Right Panel — STEP 8 */}
        <aside className="w-[320px] flex-shrink-0 border-l border-drs-border bg-drs-s1 flex flex-col">
          <div className="p-4 border-b border-drs-border">
            <span className="text-drs-faint text-xs font-mono">Right Panel — STEP 8</span>
          </div>
        </aside>
      </div>

      {/* Chat Input — ALWAYS VISIBLE (STEP 4 full impl, placeholder here) */}
      <footer className="h-20 flex-shrink-0 border-t border-drs-border bg-drs-s1 flex items-center px-4 gap-3">
        <span className="text-drs-faint text-xs font-mono w-32 flex-shrink-0">
          [model selector]
        </span>
        <input
          type="text"
          placeholder="Scrivi a DRS..."
          className="
            flex-1 bg-drs-s3 border border-drs-border rounded-lg px-4 py-2.5
            text-drs-text placeholder:text-drs-faint text-sm
            focus:outline-none focus:border-drs-border-bright
            transition-colors
          "
        />
        <button
          className="
            px-4 py-2.5 bg-drs-accent text-white rounded-lg text-sm font-medium
            hover:opacity-90 transition-opacity flex-shrink-0
          "
        >
          ↑
        </button>
      </footer>
    </div>
  )
}
