import { useEffect, useState } from 'react'
import { Account } from './components/Account'
import { AdviceNotice } from './components/AdviceNotice'
import { DocumentLibrary } from './components/DocumentLibrary'
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
          <DocumentLibrary key={me.email} />
        ) : (
          <p className="empty">
            Sign in to upload a PDF, text, Markdown or Word file to your library.
          </p>
        )}
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
          Asking is not available yet. You will see each step of the search and the
          passages the answer quotes.
        </p>
      </section>
    </main>
  )
}

export default App
