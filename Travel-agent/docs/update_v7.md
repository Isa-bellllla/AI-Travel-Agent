# Update 7 — one shared introduction, then hotel-specific highlights

The list introduction now gives the shared destination once and, when explicitly requested and supported, the common hotel tier/brand. Individual cards start with the hotel name and its features rather than repeating “I found [name] in [same city] for you.” Different-city lists retain each hotel's own city; differing countries are not hidden.

City, country, category, brand and hotel-name evidence still drives filtering, eligibility and match diagnostics, but is not presented as a hotel-specific selling point. An exact match such as Hongkong vs HongKong is not a meaningful feature explanation. Shared constraints are summarized, while actual source features explain the individual choices.

Within the selected shortlist, less-repeated source label phrases get presentation priority. Verified user-relevant evidence remains preferred, and duplicate/overlapping phrases are suppressed. This is source-based presentation ordering, not a claim of worldwide uniqueness. If records do not establish distinctive amenities, none are invented to make hotels sound different. Prices, estimate disclosure, unknown preferences, and seasonal caveats are retained.

No extraction, evidence-verification, hard-filtering, recommendation eligibility or model-provider logic changed. No extra LLM calls are introduced. The v5 visual design and v6 punctuation fix remain.

90 automated tests passed in the recorded run (18.43 seconds). New tests verify one shared-location introduction, no per-card geographic wish-list echo, geographic eligibility/coverage still enforced, Conrad Hong Kong's actual feature labels displayed, different-city information retained, one shared-tier statement, and less-repeated actual features prioritized. These are rendering and component tests, not a new real-model quality evaluation.

## Run the updated build

Extract the complete archive into a fresh directory. Open its `Start_Travel_Agent.ipynb`, which now prints the root `VERSION` marker (`v7`) and project directory. Configure your API as before and launch a fresh website process. Start a New Conversation.

Do not reuse the earlier ad-hoc launcher that checked for the literal string `I found **` inside grounding.py as a v6 check. That wording has intentionally been removed from individual cards. The bundled notebook checks required files and reports a stable version marker, without treating a sales sentence as a version ID. Private `.env` values are not included in the archive or printed by the notebook.
