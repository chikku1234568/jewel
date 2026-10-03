import {
  API_EMBEDDINGS,
  API_EXTRACTION,
  AGENT_MODELS,
  type AgentChoice,
  type EmbeddingChoice,
  type ExtractionChoice,
} from '../lib/api'

const DEFAULTS: EmbeddingChoice = {
  provider: 'api',
  model: 'text-embedding-3-small',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
}

export function loadEmbeddingChoice(): EmbeddingChoice {
  try {
    const raw = sessionStorage.getItem('jewel.embedding')
    if (!raw) return DEFAULTS
    const saved = JSON.parse(raw) as Partial<EmbeddingChoice>
    // A tab that still has a removed local model starts over on the API default.
    if (saved.provider !== 'api') return DEFAULTS
    return { ...DEFAULTS, ...saved, provider: 'api' }
  } catch {
    return DEFAULTS
  }
}

export function storeEmbeddingChoice(choice: EmbeddingChoice) {
  sessionStorage.setItem('jewel.embedding', JSON.stringify(choice))
}

const EXTRACTION_DEFAULTS: ExtractionChoice = {
  provider: 'api',
  model: 'kimi-k2.6',
  base_url: 'https://api.moonshot.ai/v1',
  api_key: '',
}

export function loadExtractionChoice(): ExtractionChoice {
  try {
    const raw = sessionStorage.getItem('jewel.extraction')
    if (!raw) return EXTRACTION_DEFAULTS
    const saved = JSON.parse(raw) as Partial<ExtractionChoice>
    // A tab that still has the removed local Qwen choice starts over on the API default.
    if (saved.provider !== 'api') return EXTRACTION_DEFAULTS
    return { ...EXTRACTION_DEFAULTS, ...saved, provider: 'api' }
  } catch {
    return EXTRACTION_DEFAULTS
  }
}

function storeExtractionChoice(choice: ExtractionChoice) {
  sessionStorage.setItem('jewel.extraction', JSON.stringify(choice))
}

/** Who reads the file and writes the triples. */
export function ExtractionPicker({
  value,
  onChange,
}: {
  value: ExtractionChoice
  onChange: (value: ExtractionChoice) => void
}) {
  const known = API_EXTRACTION.some((option) => option.id === value.model)

  function update(patch: Partial<ExtractionChoice>) {
    const next = { ...value, ...patch, provider: 'api' as const }
    storeExtractionChoice(next)
    onChange(next)
  }

  return (
    <fieldset className="embedding">
      <legend>Read the file</legend>
      <label>
        Model
        <select
          value={known ? value.model : 'other'}
          onChange={(event) => {
            const id = event.target.value
            if (id === 'other') {
              update({ model: '' })
              return
            }
            const base = API_EXTRACTION.find((option) => option.id === id)?.base_url
            update({ model: id, ...(base ? { base_url: base } : {}) })
          }}
        >
          {API_EXTRACTION.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
          <option value="other">Other model id</option>
        </select>
      </label>
      {!known ? (
        <label>
          Model id
          <input
            value={value.model}
            onChange={(event) => update({ model: event.target.value })}
            placeholder="gpt-4o-mini"
          />
        </label>
      ) : null}
      <label>
        Base URL
        <input
          value={value.base_url}
          onChange={(event) => update({ base_url: event.target.value })}
        />
      </label>
      <label>
        API key
        <input
          type="password"
          value={value.api_key}
          autoComplete="off"
          onChange={(event) => update({ api_key: event.target.value })}
        />
      </label>
      <p className="hint">
        This model reads the file and writes the triples. It needs your API key. gpt-4o-mini uses
        https://api.openai.com/v1. kimi-k2.6 uses https://api.moonshot.ai/v1.
      </p>
    </fieldset>
  )
}

const AGENT_DEFAULTS: AgentChoice = {
  model: 'kimi-k2.6',
  base_url: 'https://api.moonshot.ai/v1',
  api_key: '',
}

export function loadAgentChoice(): AgentChoice {
  try {
    const raw = sessionStorage.getItem('jewel.agent')
    if (!raw) return AGENT_DEFAULTS
    return { ...AGENT_DEFAULTS, ...(JSON.parse(raw) as Partial<AgentChoice>) }
  } catch {
    return AGENT_DEFAULTS
  }
}

function storeAgentChoice(choice: AgentChoice) {
  sessionStorage.setItem('jewel.agent', JSON.stringify(choice))
}

/** Who writes the answer. Defaults to Kimi. An empty key uses the server Kimi key. */
export function AgentPicker({
  value,
  onChange,
}: {
  value: AgentChoice
  onChange: (value: AgentChoice) => void
}) {
  const known = AGENT_MODELS.some((option) => option.id === value.model)

  function update(patch: Partial<AgentChoice>) {
    const next = { ...value, ...patch }
    storeAgentChoice(next)
    onChange(next)
  }

  return (
    <fieldset className="embedding">
      <legend>Answer model</legend>
      <label>
        Model
        <select
          value={known ? value.model : 'other'}
          onChange={(event) => {
            const id = event.target.value
            if (id === 'other') {
              update({ model: '' })
              return
            }
            const base = AGENT_MODELS.find((option) => option.id === id)?.base_url
            update({ model: id, ...(base ? { base_url: base } : {}) })
          }}
        >
          {AGENT_MODELS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
          <option value="other">Other model id</option>
        </select>
      </label>
      {!known ? (
        <label>
          Model id
          <input
            value={value.model}
            onChange={(event) => update({ model: event.target.value })}
            placeholder="kimi-k2.6"
          />
        </label>
      ) : null}
      <label>
        Base URL
        <input
          value={value.base_url}
          onChange={(event) => update({ base_url: event.target.value })}
        />
      </label>
      <label>
        API key
        <input
          type="password"
          value={value.api_key}
          autoComplete="off"
          placeholder="Leave empty to use the server Kimi key"
          onChange={(event) => update({ api_key: event.target.value })}
        />
      </label>
      <p className="hint">
        This model writes the answer after the graph search. It defaults to kimi-k2.6. Leave the
        key empty to use the Kimi key already on the server. kimi-k2.6 does not use thinking mode.
      </p>
    </fieldset>
  )
}

/** An OpenAI-compatible embeddings API. The user supplies the key. */
export function EmbeddingPicker({
  value,
  onChange,
}: {
  value: EmbeddingChoice
  onChange: (value: EmbeddingChoice) => void
}) {
  const known = API_EMBEDDINGS.some((option) => option.id === value.model)

  function update(patch: Partial<EmbeddingChoice>) {
    const next = { ...value, ...patch, provider: 'api' as const }
    storeEmbeddingChoice(next)
    onChange(next)
  }

  return (
    <fieldset className="embedding">
      <legend>Embedding model</legend>
      <label>
        Model
        <select
          value={known ? value.model : 'other'}
          onChange={(event) => {
            if (event.target.value !== 'other') update({ model: event.target.value })
            else update({ model: '' })
          }}
        >
          {API_EMBEDDINGS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
          <option value="other">Other model id</option>
        </select>
      </label>
      {!known ? (
        <label>
          Model id
          <input
            value={value.model}
            onChange={(event) => update({ model: event.target.value })}
            placeholder="text-embedding-3-small"
          />
        </label>
      ) : null}
      <label>
        Base URL
        <input
          value={value.base_url}
          onChange={(event) => update({ base_url: event.target.value })}
        />
      </label>
      <label>
        API key
        <input
          type="password"
          value={value.api_key}
          autoComplete="off"
          onChange={(event) => update({ api_key: event.target.value })}
        />
      </label>
      <p className="hint">
        This model turns the file and the question into vectors. It needs your API key. A graph
        has to be searched with the same model that built it.
      </p>
    </fieldset>
  )
}
