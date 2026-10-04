import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AdviceNotice } from '../components/AdviceNotice'
import { getMe, SIGN_IN_URL } from '../lib/api'

const SIGN_IN_ERRORS: Record<string, string> = {
  google_denied: 'Google sign-in was cancelled.',
  missing_code: 'Google did not return a sign-in code. Please try again.',
  invalid_state: 'That sign-in link expired. Please try again.',
  token_invalid: 'Google sign-in could not be verified. Please try again.',
  not_allowed: 'This Google account is not on the jewel sign-in list.',
}

type SessionCheck = 'checking' | 'signed-out' | 'unreachable'

/**
 * Reads `?signin_error=...` left by a failed Google callback once, then removes it from
 * the address bar (through the router, so its location stays in step).
 */
function useSignInError(): string | null {
  const location = useLocation()
  const navigate = useNavigate()
  const [error] = useState(() => new URLSearchParams(location.search).get('signin_error'))

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    if (!params.has('signin_error')) return
    params.delete('signin_error')
    const search = params.toString()
    navigate(
      { pathname: location.pathname, search: search ? `?${search}` : '', hash: location.hash },
      { replace: true },
    )
  }, [location, navigate])

  return error
}

/** `/`: the signed-out first screen. A visitor with a live session goes straight to `/app`. */
export function Landing() {
  const navigate = useNavigate()
  const signInError = useSignInError()
  const [check, setCheck] = useState<SessionCheck>('checking')

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((me) => {
        if (cancelled) return
        if (me) navigate('/app', { replace: true })
        else setCheck('signed-out')
      })
      .catch(() => {
        if (!cancelled) setCheck('unreachable')
      })
    // Do not keep a slow API from hiding the page.
    const timer = window.setTimeout(() => {
      if (!cancelled) setCheck((value) => (value === 'checking' ? 'signed-out' : value))
    }, 1500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [navigate])

  useEffect(() => {
    document.title = 'jewel: your documents as a knowledge graph'
  }, [])

  return (
    <div className="landing" data-ready={check !== 'checking'}>
      <header className="landing-bar shell">
        <span className="wordmark">jewel</span>
      </header>

      <main className="shell landing-main">
        <section className="hero" aria-labelledby="hero-title">
          <h1 id="hero-title" className="hero-title">
            Your documents become a knowledge graph you can ask questions about.
          </h1>
          <AdviceNotice />
          <div className="hero-actions">
            <a className="button button-primary button-large" href={SIGN_IN_URL}>
              Sign in with Google
            </a>
          </div>
          {signInError ? (
            <p className="error" role="alert">
              {SIGN_IN_ERRORS[signInError] ?? 'Sign-in failed. Please try again.'}
            </p>
          ) : null}
          {check === 'unreachable' ? (
            <p className="error" role="alert">
              Could not reach the jewel API. Sign-in will not work until it is running.
            </p>
          ) : null}
        </section>

        <section className="steps" aria-labelledby="steps-title">
          <h2 id="steps-title" className="section-label">
            How it works
          </h2>
          <ol className="step-list">
            <li className="step">
              <span className="step-number" aria-hidden="true">
                1
              </span>
              <h3>Upload files</h3>
              <p>
                Add more than one file. PDF, Word, PowerPoint, Excel, HTML, text, and Markdown
                are accepted. A question can cross-reference a name that appears in more than one
                of them. A PDF can be at most 20 pages and 20 MB.
              </p>
            </li>
            <li className="step">
              <span className="step-number" aria-hidden="true">
                2
              </span>
              <h3>Build the graph</h3>
              <p>
                jewel reads each file and records the people, places and ideas in it, how they
                connect, and the sentence that says so.
              </p>
            </li>
            <li className="step">
              <span className="step-number" aria-hidden="true">
                3
              </span>
              <h3>Ask a question</h3>
              <p>
                One agent searches your graph, shows each step it took, and answers with quotes from
                your files.
              </p>
            </li>
          </ol>
        </section>
      </main>

      <footer className="shell landing-foot">
        <span className="wordmark wordmark-small">jewel</span>
        <span>Your files, your graph.</span>
      </footer>
    </div>
  )
}
