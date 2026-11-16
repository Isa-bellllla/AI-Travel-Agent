# Update 2: relevance, clarification, and consultant-style answers

This update addresses the reported Japan/high-end → Dubai/luxury conversation, low-budget handling, season timing questions, and information-dump presentation. The failures were reported from a local deployment; no local API key or production trace was available in this cloud workspace. Changes were verified with deterministic regression tests using typed model-output contracts, not a fabricated live-model evaluation.

## What changed

- Current city/country/category slots replace earlier structural query filters. A newly supplied city is reconciled with its actual country in the CSV. Changing countries drops a previous incompatible city. The exclusive category slot prevents old high-end and new Top Luxury requirements being applied together.
- The interpreter receives actual category values and a compact hotel entity catalog containing IDs/names/locations. It maps explicit tier synonyms to source labels rather than searching for a nonexistent literal `luxury` category. Novel experience/amenity phrasing remains an LLM/semantic task.
- Preference updates support explicit replacements and exclusive semantic dimensions. Question-local feature checks no longer become permanent travel preferences.
- Recommendation count is separate from QA display limit. A previous cheapest-hotel question or an accidental one-result query limit no longer shrinks an ordinary shortlist to one. An explicitly requested one-hotel recommendation still returns one. The CSV has exactly **two Top Luxury Dubai records**, so returning two is correct for that filter.
- Structured material clarification needs are enforced by the agent, even if the planner picks recommend. Subjective budget state prompts for a nightly USD range instead of inventing one; a numeric follow-up resolves it; skipping the budget permits recommendations. Subjective revisions invalidate an old numeric ceiling; flexible and hard limits are distinguished.
- Seasonal timing uses recorded peak/off-season month fields through detail queries. It does not mistake a seasonal price comparison or a sampling date for the months. Missing months are explicitly unknown. Clarifying a budget is not a prerequisite to answering factual seasonal questions.
- All source columns can be selected/filtered through validated tools. Compound factual questions can run additional allowlisted queries. Ambiguous named-hotel detail queries ask which hotel, rather than silently selecting the cheapest match; numbered clarification choices retain their own reference IDs.
- Cards now explain why a stay belongs on the shortlist, show concise source-backed highlights and budget/travel timing considerations, and identify trade-offs. Database calculations are rendered as conversational sentences/tables rather than JSON. Narrow season questions omit unrelated descriptions and prices.

## Run on your Mac with Jupyter

1. Stop the old website process (the old notebook's `website.terminate()` if it started it, or Ctrl+C in its terminal). Leave your original project and `.env` available as a backup.
2. Extract the updated ZIP into a fresh folder. Open `Start_Travel_Agent.ipynb` **beside the new app.py** in Jupyter.
3. Run the notebook cells in order. Enter your provider's exact API model ID and key in its configuration cell. The application model ID may differ from your chat interface's display name. Keys are hidden and never printed or saved by the notebook.
4. The launcher waits for the website health endpoint, opens a browser tab, and provides a clickable link. It chooses a free port. Start a **New Conversation**; an old website process is still running old application code until restarted.
5. Try the reported scenarios. An optional cell runs the new `regression` evaluation split with your real API provider and records detailed traces for review. Those calls may incur charges.

The website and notebook launcher use the same agent implementation. You do not paste server code into app.py. The local-browser launcher is intended for Jupyter running on the same Mac; hosted Jupyter needs its platform's preview/proxy.

## Evidence and limits

48 regression/UI/component tests passed in the recorded run, including the newly reported transition, low-budget clarification/resolution, explicit skipped budget, named hotel's known/unknown season, ambiguous hotel references and follow-ups, compound counts/averages, and consultant-style output. Independent source-row comparison still passes all 564 deterministic database checks. Original CSV/DOCX hashes are unchanged.

No real API model was called in this workspace. The revised interpreter prompt, semantics of clarification, hotel-evidence entailment, and full conversational quality must still be checked using the locally configured model. `evaluation/cases.json` adds three regression scenarios without changing the held-out set. The launcher notebook prints the actual application `LLM_MODEL` for verification; it does not assume the chat model label is an API model ID.
