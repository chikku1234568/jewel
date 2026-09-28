import { AdviceNotice } from './components/AdviceNotice'

/**
 * Placeholder page. Nothing here talks to the backend yet: sign-in is inert and there is
 * no fake signed-in user. Regions, in order: advice sentence, sign-in, Documents, Graph, Ask.
 */
function App() {
  return (
    <main className="container">
      <header className="header">
        <h1>jewel</h1>
        <p className="subtitle">Your documents, as a knowledge graph you can explore and ask.</p>
      </header>

      <AdviceNotice />

      <section className="region" aria-labelledby="signin-title">
        <h2 id="signin-title">Sign in</h2>
        <button type="button" disabled title="Sign-in is not available yet">
          Sign in with Google
        </button>
        <p className="hint">Sign-in is not connected yet.</p>
      </section>

      <section className="region" aria-labelledby="documents-title">
        <h2 id="documents-title">Documents</h2>
        <p className="empty">
          Your library is empty. Upload a PDF, .txt or .md file to get started.
        </p>
      </section>

      <section className="region" aria-labelledby="graph-title">
        <h2 id="graph-title">Graph</h2>
        <p className="empty">
          Your graph appears here after a file is built: the people, places and ideas in
          your documents, linked by the sentences that connect them. Click a node to read the
          sentence it came from.
        </p>
      </section>

      <section className="region" aria-labelledby="ask-title">
        <h2 id="ask-title">Ask</h2>
        <textarea
          aria-label="Question"
          placeholder="Ask a question about your documents"
          disabled
          rows={3}
        />
        <p className="hint">
          Asking needs a saved xAI API key and at least one ready document. You will see
          each step of the search and the passages the answer quotes.
        </p>
      </section>
    </main>
  )
}

export default App
