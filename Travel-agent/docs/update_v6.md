# Update 6 — readable punctuation and warmer recommendations

## Apostrophes and HTML entities

The actual CSV description for The New York Edition Hotel contains `Manhattan's`, not an encoded apostrophe. The old Markdown helper called `html.escape()` with quote encoding enabled and then escaped Markdown punctuation, including `#` inside the resulting `&#x27;`. That prevented the Markdown renderer from decoding the entity, so users saw the encoding literally.

The helper now decodes existing entities once, escapes source Markdown controls, then escapes HTML text characters with `quote=False`. Apostrophes and quotation marks stay readable. Ampersands and angle brackets remain safe at rendering time; Markdown links, emphasis controls, dollars and table pipes cannot alter the intended plain-text presentation. This helper is for Markdown text; HTML sidebar rendering continues to use HTML escaping separately.

## Consultant-style presentation

Recommendations now introduce the actual hotel and location with “I found … for you,” weave verified highlights into the user's preferences, and discuss reference rates and trade-offs conversationally. Repeated “Why I’d shortlist it for you / for your preference for” headings are removed. A requested category match is mentioned when appropriate. Highlights remain copied from verified evidence or source labels; no new amenities, availability, live deals, superlative guarantees or prices are generated for sales effect. Estimated rates, unknown details and budget limitations remain disclosed.

This is a rendering/presentation update. The v5 visual design is retained. Intent interpretation, clarification memory, hard filtering, semantic retrieval and evidence verification are unchanged; no extra model call is introduced by the new tone.

## Evidence

84 automated tests passed in the recorded run (12.32 seconds). New tests cover actual CSV apostrophes, existing encoded apostrophes, Markdown/HTML safety, the named Edition description, warmer recommendation text, verified personalized highlights, price estimates and over-budget caveats. Real Chromium/Streamlit rendering verified readable apostrophes, quotation marks and ampersands, while an HTML script probe stayed inert. See `text-rendering-check.json`. This was a presentation fixture, not a real LLM-quality evaluation; no paid LLM calls were made.

Stop the old website, extract the complete v6 project, and launch `Start_Travel_Agent.ipynb` from the new directory. Start a New Conversation to see newly rendered replies; previously stored replies are not automatically rewritten.
