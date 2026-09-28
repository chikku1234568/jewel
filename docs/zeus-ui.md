# Task: professional UI for jewel

Redesign the frontend only. The backend API is working and must stay as it is. Do not change Python, database schema, or route paths.

The app is **jewel**: a person signs in with Google, uploads their own documents, builds a knowledge graph, and asks one agent questions about that graph. Answers quote their files. This is not a medical product and not a demo with sample data.

## What is wrong now

`frontend/src/App.tsx` is one long page. Sign-in, documents, graph, and ask are stacked regions with plain CSS. It works. It does not look like a product.

## Pages

Use the React router already available, or add `react-router-dom` if it is not installed.

**`/` landing, signed out.** A professional first screen.

- Name: jewel.
- One sentence: your documents become a knowledge graph you can ask questions about.
- A short line that answers quote the user's files and are not medical, legal, or financial advice.
- One primary button: Sign in with Google. It must go to the existing `SIGN_IN_URL` (`GET /auth/google` on the API). Do not invent a second login.
- Three short steps, in this order: upload files, build the graph, ask a question. No fake screenshots of patients or sample corpora.
- If the URL has `?signin_error=`, show that error and then strip it, the way `takeSignInError` already does.

**`/app`, signed in.** If `GET /me` fails, send the person back to `/`.

The signed-in app has three areas, reachable from a simple nav. A top bar shows the Google name and email and Sign out (`POST /auth/logout`).

1. **Documents.** Upload, the library, build, progress, stop.
2. **Graph.** The entities and triples from `GET /graph`.
3. **Ask.** The question box, the tool trace, and the answer.

Keep the controls that already work. Do not drop them in the redesign.

- **Read the file** (`ExtractionPicker`): local Qwen, or an OpenAI-compatible chat model (`gpt-4o-mini`, `kimi-k2.6`, or another id) with base URL and API key.
- **Embedding model** (`EmbeddingPicker`): local BGE base, BGE large, Nomic, E5, or an OpenAI-compatible embeddings API (`text-embedding-3-small`, `text-embedding-3-large`, or another id) with base URL and key.
- **Answer model** (`AgentPicker`): defaults to `kimi-k2.6`. Base URL and key. An empty key means the server Kimi key.
- Above the upload button, the line that asks people to keep PDFs to about 20 pages.
- File picker accepts `.pdf,.txt,.md,.docx`.
- Library columns: file, time, status, actions. Status labels already exist in `DocumentLibrary.tsx`.
- **Build graph** starts `POST /documents/{id}/build` with the embedding fields and a nested `extraction` object. While status is `extracting`, show the progress bar (`build_done` / `build_total`, or "Building…" when the total is still 0) and a **Stop** button (`POST /documents/{id}/stop`).
- Open shows extracted text. Delete removes the file.
- Graph: click a name, show the quote, list triples as "subject predicate object".
- Ask: `POST /ask` with the question, the embedding fields, and a nested `agent` object. Show each tool step, then the answer.

## Visual bar

Calm, editorial, and precise. Light background, one accent color, real type hierarchy, plenty of space. It should feel like a tool a careful person would use for their own files.

Do not use a purple gradient, glassmorphism, or a dashboard full of cards that say nothing. Do not add a chart library. Do not add sample documents. Do not mention enoxaparin, clinics, or "not for clinical use" as the product identity. The one advice sentence above is enough.

Desktop and a narrow phone width both have to work. The nav can collapse to the three names. Buttons stay easy to hit.

## Technical constraints

- Stay in `frontend/`. The API base is `VITE_API_BASE_URL`, default `http://localhost:8000`.
- Every `fetch` keeps `credentials: 'include'`. The session is an httpOnly cookie. Do not put tokens in `localStorage`.
- The extraction key, embedding key, and agent key already live in `sessionStorage` inside the pickers. Leave that behavior.
- Do not rename API fields. Build body is the embedding object plus `extraction`. Ask body is the embedding object plus `question` and `agent`.
- `npm run build` must succeed. Match the existing TypeScript style.

## Done

A signed-out visit to `/` is the landing page with Google sign-in. After sign-in the person is in the app and can upload, build, watch the progress bar, stop, open the graph, and ask, with the three model pickers still present. Sign out returns to the landing page.
