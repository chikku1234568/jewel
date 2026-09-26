import { NotForClinicalUseBanner } from './components/NotForClinicalUseBanner'

/**
 * Placeholder shell. Step 1 is structure + architecture only.
 *
 * Planned panels (see docs/architecture.md):
 *   1. Ingest: paste text / upload PDF -> episodes
 *   2. Progress: the five visible steps
 *   3. Chat: graph answer vs. naive-RAG baseline, side by side
 *   4. Graph view: temporal KG with the closed PRESCRIBED_DOSE edge
 */
const PLANNED_STEPS = [
  'Parse orders',
  'Ingest labs',
  'Evaluate the rule',
  'Invalidate the dose',
  'State what is still active',
] as const

function App() {
  return (
    <>
      <NotForClinicalUseBanner />
      <main className="container">
        <h1>jewel</h1>
        <p className="subtitle">Pharmacotherapy regimen lab alert (showcase)</p>
        <p>
          Status: <em>step 1, repository structure and architecture proposal</em>.
          No functionality yet.
        </p>
        <section>
          <h2>Planned progress steps</h2>
          <ol>
            {PLANNED_STEPS.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </section>
      </main>
    </>
  )
}

export default App
