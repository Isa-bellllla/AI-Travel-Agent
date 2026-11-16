# Stillwater — a grounded travel consultant

A Streamlit hotel recommendation and database QA application built around the included **622-hotel dataset** and original evaluation rubric. A language model interprets messages and selects evidence; read-only deterministic tools filter, calculate, compare, and render source-backed answers. There is no keyword-chatbot or mock fallback in the application.

**Validation status:** database, retrieval, memory/tool contracts, scoring, and Streamlit navigation are tested. Real LLM conversations, neural embedding retrieval, and rubric quality scores have **not** been validated in this environment: no inference server/model is installed, and model registries are blocked by outbound policy. The app shows a service-unavailable state until a model is configured. See [the measured report](docs/performance_report.md). This is a runnable implementation with those explicit validation limits, not a claim that the conversational acceptance test passed.

The latest update adds field- and subject-aware evidence checks and records resolved clarification answers to prevent repeated questions. See [Update 4](docs/update_v4.md) for details. General clarification/coverage policies, persistent brand preferences, and user-controlled conversation completion are retained. See [the conversation contract](docs/conversation_contract.md) (Chinese) for how this differs from underlying model training and what remains unverified.

Latest: [Update 6](docs/update_v6.md) fixes literal HTML apostrophe codes and gives recommendations a warmer travel-consultant voice, retaining verified facts and the v5 design. Restart the website and start a New Conversation after upgrading.

Latest: [Update 7](docs/update_v7.md) summarizes a common destination once and introduces each hotel through its own source-backed features. Use the bundled `Start_Travel_Agent.ipynb`; it prints the project directory and `VERSION` marker. Older v6-specific phrase checks are no longer suitable.

## New travel website design

Update 5 brings a warm editorial design, locally bundled travel imagery, high-contrast text, responsive chat, and a desktop trip summary. The v4 agent/model/query logic is unchanged. See [UI details and verification](docs/ui_redesign.md). Extract the complete project including `assets/` and `.streamlit/`; restart the old server before launching the new version.

![Stillwater homepage](docs/ui-homepage.png)

## Jupyter on your Mac

Open **Start_Travel_Agent.ipynb** in the extracted project folder and run its cells in order. It installs dependencies, accepts a hidden API key and exact model ID, chooses a free port, and opens the website in your browser after its health check succeeds. The notebook also includes optional regression evaluation and stop-server cells. Stop the old server and start a new conversation after upgrading. See [Update 2](docs/update_v2.md) for fixes and migration instructions.

## Install

Use Python 3.12. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cp .env.example .env
```

`requirements.lock` pins the tested Python environment; `requirements.txt` lists direct dependencies. With uv, use `UV_CACHE_DIR=/workspace/.cache/uv uv venv .venv` then `UV_CACHE_DIR=/workspace/.cache/uv uv pip install --python .venv/bin/python -r requirements.lock`. Do not overwrite an existing `.env`. No database upload, credentials, or external service is needed for deterministic tests.

## Configure a real local LLM

Install [Ollama](https://ollama.com/download) for your operating system. On Linux, follow its official installation instructions. Run:

```bash
ollama serve
# In another terminal:
ollama pull qwen2.5:3b
```

The default `.env.example` targets this local model. A quantized 3B model typically needs several GB of RAM; this machine has 4 CPU cores and 32 GB RAM but no GPU. No large models were downloaded during development. Local CPU latency and the 45-second clarification target require measurement. A larger model may improve interpretation but must be chosen against available resources.

Optional neural embeddings:

```bash
ollama pull nomic-embed-text
# Set EMBEDDING_MODEL=nomic-embed-text in .env, then restart Streamlit.
```

Without that setting, retrieval combines TF-IDF, a reproducible 96-dimensional local latent semantic index, structured filters, label overlap, budget fit, and evidence reranking. This **is not pretrained neural embedding validation**. With the embedding model set, Ollama embeddings are cached under `.cache/`, keyed by dataset hash, model name, and endpoint; unavailable configured embeddings cause an explicit error rather than silently changing retrieval. Delete the cache after replacing a model behind the same name.

The current cloud policy denies `registry.ollama.ai` and `huggingface.co`. Model installation requires network access to the selected registry and any blob hosts identified by its download errors, or an accessible pre-provisioned inference server. Keep TLS verification enabled. No secret is needed for public local-model downloads.

For a hosted OpenAI-compatible provider, explicitly configure `LLM_PROVIDER=openai`, `LLM_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `ALLOW_PAID_API=true`. This enables potentially paid requests and must be a deliberate choice. The key stays in environment settings or an ignored `.env`, never the UI. No hosted API calls were made during development. The provider must support JSON-schema response formatting; hosted-provider integration is unverified here.

## Run

```bash
.venv/bin/python -m streamlit run app.py --server.headless=true --browser.gatherUsageStats=false
```

The homepage and chat navigation work without a model; submitting a message requires a reachable configured model. Conversation history, preferences, last shortlist, focus, and pending questions are isolated in each Streamlit session. **New Conversation** clears the session. Refreshing/closing the browser may lose it: there is no user account or durable conversation storage. Full history is passed to interpretation; it is never silently truncated. Conversations exceeding the configured model's context window can fail, with state preserved.

The interface contains no API keys, debugging controls, or evaluation metrics. Prices are always reference USD/night rates, never live booking quotes.

## Test and evaluate

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/audit.py
.venv/bin/python -m scripts.benchmark
# Requires a REAL configured LLM:
.venv/bin/python -m evaluation.run --split development --output evaluation/runs/development.json
.venv/bin/python -m evaluation.run --split acceptance --output evaluation/runs/acceptance.json
# Run held-out prompts only after freezing model, prompt, and pipeline:
.venv/bin/python -m evaluation.run --split held_out --output evaluation/runs/held_out.json
```

The runner saves actual history, plans, preferences, slots, query parameters, evidence, hotel IDs, responses, timings, model, and dataset version. Failed runs exit nonzero. Unit tests that queue structured model outputs test component contracts; they do **not** demonstrate real language understanding. Developer traces contain conversation text; treat exported runs as private when they contain personal information.

Follow [evaluation instructions](evaluation/README.md) to annotate cases against the original rubric. No score is assigned automatically for subjective relevance or intent. After annotation:

```bash
.venv/bin/python -m evaluation.run --score-file evaluation/runs/annotated.json
```

## Design and limitations

- [Data schema, quality, and supported questions](docs/schema_report.md)
- [Architecture, constraints, and phase completion](docs/architecture.md)
- [Measured checks and unresolved validation](docs/performance_report.md)
- [Original rubric text extraction](docs/rubric_extracted.txt) (the DOCX remains authoritative)

There is no `hotel_id` source column; stable IDs hash `(Country, City, Hotel Name)`. Missing amenities are unknown, not false. Exact quote anchoring checks provenance; **whether a quote entails a preference is an LLM judgment requiring human review**. The system never treats embedding similarity as proof of a hard constraint. Hard semantic constraints need explicit evidence and may yield fewer than three options.

Semantic recommendation review is limited to 24 top candidates. Semantic aggregates review up to 80 structured candidates and refuse to report exhaustive totals when more remain. No-match messages distinguish structured absence from missing semantic evidence. In unknown seasons, hard budget filtering uses the higher recorded rate and excludes estimated prices; this is conservative. It does not guarantee actual affordability or availability.

The project ships as a single-user development app, not a booking service. Authentication, persistent storage, multi-worker deployment, and production operations are outside this implementation.
