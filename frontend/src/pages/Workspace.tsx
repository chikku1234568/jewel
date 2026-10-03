import { useEffect, useState } from 'react'
import { Link, Navigate, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { AdviceNotice } from '../components/AdviceNotice'
import { DocumentLibrary } from '../components/DocumentLibrary'
import {
  AgentPicker,
  EmbeddingPicker,
  ExtractionPicker,
  loadAgentChoice,
  loadEmbeddingChoice,
  loadExtractionChoice,
} from '../components/EmbeddingPicker'
import { AskPanel, GraphPanel } from '../components/GraphAsk'
import { getMe, logout, type Me } from '../lib/api'

type Area = 'documents' | 'graph' | 'ask'

const AREA_TITLES: Record<Area, string> = {
  documents: 'Documents',
  graph: 'Graph',
  ask: 'Ask',
}

function areaFor(pathname: string): Area | null {
  const rest = pathname.replace(/^\/app\/?/, '').replace(/\/$/, '')
  if (rest === '') return 'documents'
  if (rest === 'graph' || rest === 'ask') return rest
  return null
}

/**
 * `/app`: the signed-in workspace. A top bar with the Google name, email and Sign out, and
 * three areas: Documents (`/app`), Graph (`/app/graph`) and Ask (`/app/ask`). All three stay
 * mounted so a running build keeps polling and an answer stays put while you switch.
 * Without a session (or if `GET /me` fails) the person is sent back to `/`.
 */
export function Workspace() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [me, setMe] = useState<Me | null>(null)
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [graphKey, setGraphKey] = useState(0)
  const [askKey, setAskKey] = useState(0)
  const [embedding, setEmbedding] = useState(loadEmbeddingChoice)
  const [extraction, setExtraction] = useState(loadExtractionChoice)
  const [agent, setAgent] = useState(loadAgentChoice)
  const area = areaFor(pathname)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((user) => {
        if (cancelled) return
        if (user) setMe(user)
        else navigate('/', { replace: true })
      })
      .catch(() => {
        if (!cancelled) navigate('/', { replace: true })
      })
    return () => {
      cancelled = true
    }
  }, [navigate])

  useEffect(() => {
    if (area) document.title = `${AREA_TITLES[area]} · jewel`
  }, [area])

  async function onSignOut() {
    setSigningOut(true)
    setSignOutError(null)
    try {
      await logout()
      navigate('/', { replace: true })
    } catch {
      setSignOutError('Sign-out failed. Please try again.')
      setSigningOut(false)
    }
  }

  if (area === null) return <Navigate to="/app" replace />

  if (!me) {
    return (
      <div className="boot" role="status">
        <span className="wordmark">jewel</span>
        <span className="hint">Opening your library…</span>
      </div>
    )
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'area-link active' : 'area-link'

  return (
    <div className="workspace">
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link to="/app" className="wordmark">
            jewel
          </Link>
          <nav className="areas" aria-label="Workspace">
            <NavLink to="/app" end className={navClass}>
              Documents
            </NavLink>
            <NavLink
              to="/app/graph"
              className={navClass}
              onClick={() => setGraphKey((value) => value + 1)}
            >
              Graph
            </NavLink>
            <NavLink to="/app/ask" className={navClass}>
              Ask
            </NavLink>
          </nav>
          <div className="who">
            <div className="who-text">
              <span className="who-name">{me.name || me.email}</span>
              {me.name ? <span className="who-email">{me.email}</span> : null}
            </div>
            <button
              type="button"
              className="button button-quiet"
              onClick={() => void onSignOut()}
              disabled={signingOut}
            >
              {signingOut ? 'Signing out…' : 'Sign out'}
            </button>
          </div>
        </div>
        {signOutError ? (
          <p className="shell error topbar-error" role="alert">
            {signOutError}
          </p>
        ) : null}
      </header>

      <main className={area === 'graph' ? 'shell shell-wide workspace-main' : 'shell workspace-main'}>
        <section className="area" aria-labelledby="documents-title" hidden={area !== 'documents'}>
          <div className="area-head">
            <h1 id="documents-title">Documents</h1>
            <p className="lede">
              Upload a file, then build it into your graph. Each build uses the models under Build
              settings.
            </p>
          </div>
          <div className="area-grid">
            <div className="area-main">
              <DocumentLibrary
                key={me.email}
                embedding={embedding}
                extraction={extraction}
                onBuilt={() => setGraphKey((value) => value + 1)}
                onCleared={() => setAskKey((value) => value + 1)}
              />
            </div>
            <aside className="area-side" aria-labelledby="build-settings-title">
              <h2 id="build-settings-title" className="side-title">
                Build settings
              </h2>
              <ExtractionPicker value={extraction} onChange={setExtraction} />
              <EmbeddingPicker value={embedding} onChange={setEmbedding} />
            </aside>
          </div>
        </section>

        <section className="area" aria-labelledby="graph-title" hidden={area !== 'graph'}>
          <div className="area-head">
            <h1 id="graph-title">Graph</h1>
            <p className="lede">
              One file at a time: the names found in it and the statements that connect them.
              Click a name to see only its edges, or a line to read the sentence it comes from.
              You can remove a statement from the list on the right.
            </p>
          </div>
          <GraphPanel refreshKey={graphKey} />
        </section>

        <section className="area" aria-labelledby="ask-title" hidden={area !== 'ask'}>
          <div className="area-head">
            <h1 id="ask-title">Ask</h1>
            <p className="lede">
              Ask one question at a time. The agent searches your graph, shows each step, then
              answers with quotes from your files.
            </p>
          </div>
          <div className="area-grid">
            <div className="area-main">
              <AskPanel key={askKey} embedding={embedding} agent={agent} />
            </div>
            <aside className="area-side" aria-labelledby="answer-settings-title">
              <h2 id="answer-settings-title" className="side-title">
                Answer settings
              </h2>
              <AgentPicker value={agent} onChange={setAgent} />
              <p className="hint side-note">
                Search uses the embedding model from Build settings:{' '}
                <code>{embedding.model || 'not set'}</code>. It must match the model your graph was
                built with.
              </p>
            </aside>
          </div>
        </section>
      </main>

      <footer className="shell workspace-foot">
        <AdviceNotice />
      </footer>
    </div>
  )
}
