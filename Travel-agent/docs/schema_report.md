# Dataset and rubric audit

The input files were read before implementation. Full machine-readable statistics are in `data_audit.json`; the rubric was extracted using ZIP integrity checks and WordprocessingML parsing. Original CSV and DOCX bytes are preserved.

622 records; 59 countries; 141 cities. No duplicate `(Country, City, Hotel Name)` keys. There is no source ID. The application derives stable, 16-hex SHA-256 IDs with an `h_` prefix and checks collisions.

| Actual CSV column | Internal field | Missing rows | Meaning/use |
|---|---|---:|---|
| Country | country | 0 | Location filter |
| City | city | 0 | Location filter |
| Hotel Name | name | 0 | Identity and hotel lookup |
| brand | brand | 181 | Recorded brand text, not inferred ownership |
| Brand level | category | 214 | high-end, Top Luxury, International chain, or blank |
| Off-season price (USD/night) | off_price | 0 | Numeric USD/night reference |
| Peak season price (USD/night) | peak_price | 0 | Numeric USD/night reference |
| Peak season months | peak_months | 512 | Optional explicit seasonal months |
| Off-season months | off_months | 579 | Optional explicit seasonal months |
| Peak season sampling month | peak_sample | 606 | Sampling metadata; not a season definition |
| Off-season sampling months | off_sample | 595 | Sampling metadata; not a season definition |
| Label | labels | 4 | Free-form feature/experience evidence |
| courtesy | benefits | 348 | Benefits; some subject to availability |
| Reasons for recommendation | description | 0 | Free-form hotel description |
| Remark | remark | 621 | Source caveats |
| price_missing | estimated | 0 | Boolean flag; 1 record True |

Both price columns have finite nonnegative values. Off-season range: USD 67–5,301; peak range: USD 100–5,301. The `price_missing=True` row has numeric values but they must be labeled estimated. Completeness does not establish price freshness. There are no travel dates, booking inventory, authoritative star ratings, guest reviews, distances, GPS coordinates, or exchange rates. Free text is inconsistent and cannot establish universal absence of an amenity.

Supported: counts, filters, sorting, min/max/mean, grouping, recorded brand/category/location queries, exact hotel details, price comparisons and seasonal deltas, source-grounded feature questions, and evidence-based recommendations. Explicit season-month matching uses the recorded text; absent, conflicting, or unrecognized month information yields unknown. Sampling dates are not used as seasonal definitions. Without a matching month, conservative budget checks use the higher rate.

Unsupported without additional integrations: live availability, bookings, guaranteed room benefits, current deals, real-time rates, inferred travel times/distances, unrecorded amenities, personal safety guarantees, or conversion to other currencies. Blank brand/category/seasonality/benefits remain unknown.

# Rubric interpretation

A is 1 only when every factual hotel claim is supported, with estimated prices disclosed. One fabricated hotel, unsupported amenity, contradicted field, or live availability claim gives 0.

B requires recognition of at least 80% of pre-annotated explicit preference concepts, all verifiable hard constraints, and a specific source-backed reason for each recommendation. Valid no-match needs verified eligibility analysis; sampled semantic retrieval cannot establish exhaustive absence. If no concepts exist, recognition is N/A, never divide by zero.

C requires clarification only for material ambiguity, direct action when clear, and incorporation of supplied follow-up answers. Quiet does not imply remote, and relaxation does not imply a spa. Open-ended exploration can proceed without imposing constraints.

Initial clarification: score A/C against that turn and B=N/A. Comparable case-level totals are assigned only after the predefined follow-up has been supplied, with cumulative preferences. An unfinished conversation has no completed 0–3 quality score. No diagnostic adds points to A+B+C.

Report completed-case average /3, normalized percentage, A/B/C pass rates, perfect-case rate, mean/median/p95 latency, and clarification compliance within 45 seconds. Memory, reference resolution, query correctness, and tool selection remain separate diagnostics. The rubric is an evaluation specification, not a training corpus. Synthetic scenarios are engineering drafts requiring evaluator approval before an official evaluation.
