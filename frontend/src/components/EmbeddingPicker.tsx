import {
  API_EMBEDDINGS,
  API_EXTRACTION,
  LOCAL_EMBEDDINGS,
  LOCAL_EXTRACTION,
  AGENT_MODELS,
  type AgentChoice,
  type EmbeddingChoice,
  type ExtractionChoice,
} from '../lib/api'

const DEFAULTS: EmbeddingChoice = {
  provider: 'local',
  model: 'BAAI/bge-base-en-v1.5',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
}

export function loadEmbeddingChoice(): EmbeddingChoice {
  try {
    const raw = sessionStorage.getItem('jewel.embedding')
    if (!raw) return DEFAULTS
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<EmbeddingChoice>) }
  } catch {
    return DEFAULTS
  }
}

export function storeEmbeddingChoice(choice: EmbeddingChoice) {
  sessionStorage.setItem('jewel.embedding', JSON.stringify(choice))
}

const EXTRACTION_DEFAULTS: ExtractionChoice = {
  provider: 'local',
  model: 'qwen2.5:7b-instruct',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
}

export function loadExtractionChoice(): ExtractionChoice {
  try {
    const raw = sessionStorage.getItem('jewel.extraction')
    if (!raw) return EXTRACTION_DEFAULTS
    return { ...EXTRACTION_DEFAULTS, ...(JSON.parse(raw) as Partial<ExtractionChoice>) }
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
  const options = value.provider === 'local' ? LOCAL_EXTRACTION : API_EXTRACTION
  const known = options.some((option) => option.id === value.model)

  function update(patch: Partial<ExtractionChoice>) {
    const next = { ...value, ...patch }
    storeExtractionChoice(next)
    onChange(next)
  }

  return (
    <fieldset className="embedding">
      <legend>Read the file</legend>
      <label>
        Where it runs
        <select
          value={value.provider}
          onChange={(event) => {
            const provider = event.target.value as ExtractionChoice['provider']
            const model = provider === 'local' ? LOCAL_EXTRACTION[0].id : API_EXTRACTION[0].id
            const base = API_EXTRACTION.find((option) => option.id === model)?.base_url
            update({ provider, model, ...(base ? { base_url: base } : {}) })
          }}
        >
          <option value="local">On this computer</option>
          <option value="api">OpenAI-compatible API</option>
        </select>
      </label>
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
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
          {value.provider === 'api' ? <option value="other">Other model id</option> : null}
        </select>
      </label>
      {value.provider === 'api' && !known ? (
        <label>
          Model id
          <input
            value={value.model}
            onChange={(event) => update({ model: event.target.value })}
            placeholder="gpt-4o-mini"
          />
        </label>
      ) : null}
      {value.provider === 'api' ? (
        <>
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
            This is the step that reads the PDF. An API model does that work off this laptop.
            gpt-4o-mini uses https://api.openai.com/v1. kimi-k2.6 uses https://api.moonshot.ai/v1.
          </p>
        </>
      ) : (
        <p className="hint">Qwen runs on this computer. A long PDF will keep the machine busy.</p>
      )}
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

/** Local models, or an OpenAI-compatible key and model. */
export function EmbeddingPicker({
  value,
  onChange,
}: {
  value: EmbeddingChoice
  onChange: (value: EmbeddingChoice) => void
}) {
  const options = value.provider === 'local' ? LOCAL_EMBEDDINGS : API_EMBEDDINGS
  const known = options.some((option) => option.id === value.model)

  function update(patch: Partial<EmbeddingChoice>) {
    const next = { ...value, ...patch }
    storeEmbeddingChoice(next)
    onChange(next)
  }

  return (
    <fieldset className="embedding">
      <legend>Embedding model</legend>
      <label>
        Where it runs
        <select
          value={value.provider}
          onChange={(event) => {
            const provider = event.target.value as EmbeddingChoice['provider']
            update({
              provider,
              model: provider === 'local' ? LOCAL_EMBEDDINGS[0].id : API_EMBEDDINGS[0].id,
            })
          }}
        >
          <option value="local">On this computer</option>
          <option value="api">OpenAI-compatible API</option>
        </select>
      </label>
      <label>
        Model
        <select
          value={known ? value.model : 'other'}
          onChange={(event) => {
            if (event.target.value !== 'other') update({ model: event.target.value })
            else update({ model: '' })
          }}
        >
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
          {value.provider === 'api' ? <option value="other">Other model id</option> : null}
        </select>
      </label>
      {value.provider === 'api' && !known ? (
        <label>
          Model id
          <input
            value={value.model}
            onChange={(event) => update({ model: event.target.value })}
            placeholder="text-embedding-3-small"
          />
        </label>
      ) : null}
      {value.provider === 'api' ? (
        <>
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
            The key is kept in this browser tab and sent only when you build or ask. A graph
            has to be searched with the same model that built it.
          </p>
        </>
      ) : (
        <p className="hint">
          BGE large and Nomic are stronger than BGE base. The first build with a new local model
          downloads it. Search must use the same model the graph was built with.
        </p>
      )}
    </fieldset>
  )
}
