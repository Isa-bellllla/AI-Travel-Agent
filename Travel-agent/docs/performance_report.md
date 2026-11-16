# Measured validation report

This report describes the implemented project and the actual current-machine checks. It does not claim production readiness, natural-language benchmark success, publication, or restoration in a fresh cloud task.

| Check | Actual outcome |
|---|---|
| Regression suite | **90 passed**; 18.43 seconds in the recorded run. See `test-results.xml`. |
| Independent database benchmark | **564 / 564** checks correct across 141 cities: counts and peak-price min/max/mean. |
| Query latency, mean / median / p95 | 0.071 / 0.051 / 0.183 milliseconds in this run; tools only, no LLM or network time. See `tool_benchmark.json`. |
| Dataset integrity | 622 rows; original CSV/DOCX hashes unchanged. |
| Streamlit UI | AppTest passed homepage, planning navigation, chat input, reset, and unavailable-provider error state. |
| Actual web process | Started Streamlit; local HTTP health returned `ok`; homepage returned the Streamlit shell. |
| Actual acceptance run | **Blocked at turn 1**: configured local model endpoint unavailable. Nine later acceptance turns unrun. `acceptance_attempt.json` contains the failed attempt. |
| Development / held-out LLM scenarios | **Unrun**: 12 development and 10 held-out annotated scenarios provided. |
| Official A/B/C score, relevance %, intent %, perfect-case rate | **Not measured**; no completed, reviewed real-model cases. |
| Clarification latency compliance | **Not measured**; no real clarification completed. |
| Pretrained neural embedding retrieval / hosted LLM provider | **Unverified**; integration implemented but no configured model/provider used. |

Python 3.12.14; 4 CPU cores allocated; 32 GiB memory limit; no GPU utility or local Ollama binary found. `requirements.lock` records exact installed dependency versions. All paid API use remained disabled.

## What the automated tests establish

Tests exercise source schema and IDs, structured filters/calculations, grouped counts, price order, query injection rejection, SQLite read-only enforcement, explicit/unknown season handling, seasonal differences, candidate pool isolation, hybrid ranking, typed-plan execution, cumulative memory, preference removal/priority changes, budget flexibility, explicit slot clearing, long-history forwarding, session isolation, comparison/reference focus, no-match behavior, exact-quote grounding rejection, unknown/negative feature constraints, estimated-price disclosure, transactional failure, paid-provider guard, official scoring formulas, and Streamlit flows.

Where model output is involved, queued structured outputs are deliberate test doubles. They establish component behavior given a plan, **not** actual intent understanding, dynamic clarification quality, or model entailment accuracy. There is no rule-based/mock conversational fallback in the application.

## Remaining external prerequisite

Public model access checks returned `Tunnel connection failed: 403 Forbidden` for both Hugging Face and the Ollama registry. No TLS/security checks were disabled. No large model was downloaded. Ollama itself is not installed. A real local model must be installed and served, or an accessible pre-provisioned local inference endpoint configured. The project defaults to `qwen2.5:3b` on Ollama. Model quality, context handling near the model limit, CPU response speed, and semantic evidence judgments need real-model testing.

After inference is available, run the 10-turn acceptance conversation and development scenarios, review evidence and failures, freeze the system, then run held-out scenarios. Use human-approved annotations and report actual A/B/C scores with cumulative multi-turn scoring. Prompt optimization and model selection remain unperformed because no real-model result is available to guide them.

The LSA/TF-IDF baseline is implemented and tested; it does not substitute for validated neural semantic retrieval. Likewise, an HTTP/Streamlit UI pass does not imply the model-backed consumer conversation works in this machine.

## Reusable cloud configuration

Saved updated `install_script` and `start_skill` fields for the application workflow, replacing the earlier data-only instructions. Saved `registry.ollama.ai` as a custom allowed domain while preserving package-manager presets. These are draft changes only: they have not applied to this running machine or been published. Review and save them in environment settings, then publish when the desired runtime has been validated. Additional blob-download destinations may be required once registry access works. The ZIP is self-contained source/data and does not require publication to use on another suitable machine.

## Update 2 regression coverage

See `update_v2.md` for state reconciliation, category replacement, budget clarification, hotel entity planning, targeted seasonal QA, compound tool calls, recommendation prose, and the new Jupyter launcher. The suite now includes the user-reported scenarios. These are deterministic plan/tool tests; the revised LLM interpreter has not been tested against the user’s external API model.

## Update 3 general conversation policy

See `conversation_contract.md` for the user-confirmed matching/clarification/user-controlled completion contract. New tests cover every dataset city/country relationship and every recorded category transition, not only the previously reported example. Persistent brand filters, material uncertainty gates, weighted evidence coverage diagnostics, no-evidence clarification, user closing intent, and resumption with retained context are implemented. No real-model generalization score is claimed.

## Update 4 field grounding and clarification answers

See `update_v4.md`. Category/brand/location evidence is now compared in its bound source field, semantic evidence declares the hotel/property relation, and clarification memory records resolved answers. Regression coverage includes wrong-field and other-entity evidence plus multi-turn resolution despite stale repeated questions. All 75 tests passed; no live API-model rubric score is claimed.

## Update 5 UI-only redesign

See `ui_redesign.md` for browser screenshots, responsive checks, selected contrast measurements, and new UI regression tests. The v4 agent/model/query source modules are byte-for-byte unchanged. No real LLM evaluation was run as part of this UI work.

## Update 6 text rendering and recommendation tone

See `update_v6.md`. Actual CSV apostrophes now render as punctuation, and recommendations use natural introductions and verified highlights rather than repeated reason headings. The real-browser check confirms readable punctuation and inert source HTML. All 84 tests passed; no extra model calls or model-quality claims were introduced.

## Update 7 grouped introduction

See `update_v7.md`. Shared location/tier details are stated once, geographic matches stay in eligibility/diagnostics rather than sales highlights, and less-repeated actual hotel features lead the individual cards. All 90 tests passed. No new real-model quality score is claimed.
