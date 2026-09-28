import { useEffect, useState } from 'react'
import { Account } from './components/Account'
import { AdviceNotice } from './components/AdviceNotice'
import { DocumentLibrary } from './components/DocumentLibrary'
import {
  AgentPicker,
  EmbeddingPicker,
  ExtractionPicker,
  loadAgentChoice,
  loadEmbeddingChoice,
  loadExtractionChoice,
} from './components/EmbeddingPicker'
import { AskPanel, GraphPanel } from './components/GraphAsk'
import { getMe, logout, type Me } from './lib/api'

/** Reads and removes `?signin_error=...` left by a failed Google callback. */
function takeSignInError(): string | null {
  const url = new URL(window.location.href)
  const error = url.searchParams.get('signin_error')
  if (error) {
    url.searchParams.delete('signin_error')
    window.history.replaceState(null, '', url.toString())
  }
  return error
}

/**
 * Regions, in order: advice sentence, sign-in, Documents, Graph, Ask. Graph and Ask stay
 * empty and disabled until a later pass.
 */
function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [signingOut, setSigningOut] = useState(false)
  const [signInError] = useState(takeSignInError)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [graphKey, setGraphKey] = useState(0)
  const [embedding, setEmbedding] = useState(loadEmbeddingChoice)
  const [extraction, setExtraction] = useState(loadExtractionChoice)
  const [agent, setAgent] = useState(loadAgentChoice)

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setSessionError('Could not reach the jewel API.'))
      .finally(() => setLoading(false))
  }, [])

  async function onSignOut() {
    setSigningOut(true)
    try {
      await logout()
      setMe(null)
    } catch {
      setSessionError('Sign-out failed. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <main className="container">
      <header className="header">
        <h1>jewel</h1>
        <p className="subtitle">Your documents, as a knowledge graph you can explore and ask.</p>
      </header>

      <AdviceNotice />

      <section className="region" aria-labelledby="signin-title">
        <h2 id="signin-title">{me ? 'Account' : 'Sign in'}</h2>
        <Account
          me={me}
          loading={loading}
          signInError={signInError}
          onSignOut={() => void onSignOut()}
          signingOut={signingOut}
        />
        {sessionError ? (
          <p className="error" role="alert">
            {sessionError}
          </p>
        ) : null}
      </section>

      <section className="region" aria-labelledby="documents-title">
        <h2 id="documents-title">Documents</h2>
        {me ? (
          <>
            <ExtractionPicker value={extraction} onChange={setExtraction} />
            <EmbeddingPicker value={embedding} onChange={setEmbedding} />
            <DocumentLibrary
              key={me.email}
              embedding={embedding}
              extraction={extraction}
              onBuilt={() => setGraphKey((value) => value + 1)}
            />
          </>
        ) : (
          <p className="empty">
            Sign in to upload a PDF, text, Markdown or Word file to your library.
          </p>
        )}
      </section>

      <section className="region" aria-labelledby="graph-title">
        <h2 id="graph-title">Graph</h2>
        {me ? (
          <GraphPanel refreshKey={graphKey} />
        ) : (
          <p className="empty">Sign in to see your graph.</p>
        )}
      </section>

      <section className="region" aria-labelledby="ask-title">
        <h2 id="ask-title">Ask</h2>
        {me ? (
          <>
            <AgentPicker value={agent} onChange={setAgent} />
            <AskPanel embedding={embedding} agent={agent} />
          </>
        ) : (
          <p className="empty">Sign in to ask a question.</p>
        )}
      </section>
    </main>
  )
}

export default App
