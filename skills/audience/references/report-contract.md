# Product report contract

## Contents

- Narrative and evidence
- Standard sections
- Visual system
- Incomplete runs
- Dialogue appendix
- Delivery checks

## Narrative and evidence

Build every report from a recorded run, using `scripts/audience.py report` or the live finalizer. Never copy a reference report's claims or numbers. Keep the underlying run and metrics in `report.json`; use `report.md` for text export. The renderer must be the bundled `audience_core.report_view`, not new model-generated HTML for each study.

Lead with the product decision supported by the strongest evidence. The first substantive section is explicitly **Дизайн эксперимента**. Answer: what product/task, who the AI personas represent, why those groups were selected, planned versus executed coverage, first/repeat sessions, models, device assignments versus measured viewports, and limitations. Age/occupation are hypotheses only when relevant to the observed product and task.

Then show no more than three primary changes. A repeated product/flow barrier should outrank a one-off objection to one answer. Explain each in this order:

1. What happened, for which task and how many distinct personas had supporting evidence.
2. What concrete screen, text, action or response should change.
3. Why that might help. Separate the observation from the causal hypothesis.
4. What to measure in a repeat test and then with people. Do not invent an expected percentage gain.

Keep an evidence link available for every finding. A generated proposal is not a screenshot; a model's judgment is not an observed human reaction. Distinct personas can still be correlated simulations. Do not present their count as statistical power.

The final synthesis can combine paraphrases of the same issue and choose product priorities. It must cite recorded evidence and cannot supply metric values. Arithmetic, denominators, counts, deduplication and forecast formulas come from code. Regenerating a report is offline and free of model calls.

## Standard sections

| Section | Question answered | Default visual |
| --- | --- | --- |
| Дизайн эксперимента | What was planned, who actually tested, and why these groups? | Compact numbers, group rationale, expandable plan/limitations |
| Главный вывод | What should the product owner decide? | Dark panel, one conclusion, up to three supported metrics |
| Что изменить в следующем релизе | Which changes matter first, and why? | Two/three scroll-linked recommendation scenes with evidence |
| Аудитория и клиентский путь | Who succeeds, at what task, and where is the difficulty? | Group bars, first/repeat modes, clickable persona profiles |
| Интерфейс | What is unclear and what should the user see instead? | Recorded observation and concrete proposal, with evidence |
| Впечатления и удовлетворённость | What was valued, disliked, easy or hard? | Synthetic CSAT/NPS/return intent, coverage, short attributed feedback |
| Прогноз продуктовых метрик | What follows if stated assumptions hold? | Conditional scenario comparison or clear missing-input state |
| План следующего релиза | What should the team do and how will it check? | Ranked changes and verification criteria |
| Приложение. Диалоги агентов с продуктом | What did each agent actually send and what did the product answer? | Expandable, attributed conversations and TXT/JSON export, accessible from the first screen and navigation |

Adapt emphasis to the task. Do not force a checkout or pricing section into an unrelated product. Preserve the standard section labels, but let missing information produce an honest concise state. Never pad a sparse study with generic criticisms.

## Visual system

Use the approved Audience report language:

- Cream background `#FFF4E6`, dark ink `#272C26`, secondary text `#68665B`, carmine accent `#CF1747`, thin rules `#E5D7C4`.
- Large, readable conclusions and numbers. Dark summary panel. Open spacing, pill controls, a consistent system font. One main takeaway per section.
- People matrix derived from the actual planned/executed panel. Show aggregate/limited previews for large panels and disclose the count; do not create thousands of animated elements.
- Charts derived from computed records; label denominator, unit and missing values. No decorative fabricated trend lines or sample results.
- Small `IntersectionObserver`/transform/opacity reveals. Sticky recommendation scene on wide screens, inline scenes on mobile. Never delay reading until an animation ends.
- A single offline HTML with inline CSS/JavaScript, no external fonts, analytics, CDN, framework, video or network dependency. Include saved dialogue text in the HTML appendix without display truncation. Keep the broader technical audit in companion JSON rather than repeating entire browser histories throughout the DOM.
- Respect reduced-motion preferences. Make keyboard use, visible focus, evidence links and no-JavaScript reading work. Keep nav opaque and mobile content free of page-wide horizontal overflow.
- Escape all product/page/model text. Never inject untrusted text as executable HTML or script. Do not auto-open external links or perform product actions inside the report.

## Incomplete runs

A login barrier, policy stop, unavailable browser, model error or exhausted budget is not proof that people dislike the product. Show what was actually observed and what remains untested. Do not count pending personas as tested or budget-limited sessions as product failures. Keep missing satisfaction/rating/return answers unknown.

For legacy runs, newly introduced survey fields may be absent. Preserve the useful old evidence, and explain that the relevant measurement was not collected. Never backfill new assessments, ratings, audience rationales or success claims as if they had been part of the original experiment.

If a run contains only blocked/pending sessions, lead with that limitation. Include a next test action; do not generate a confident product roadmap. A missing forecast input is a legitimate result, not a reason to invent market metrics.

## Delivery checks

Check counts against the JSON, unique persona denominators, first/repeat separation, evidence references, unsupported claims, forecast sources/formulas and research spend. Inspect a normal report and an incomplete report. For renderer changes, verify desktop/mobile, offline, no JavaScript, reduced motion and long labels. The complete pipeline must also be tested with product data unrelated to the reference example.

Do not say the product study is complete merely because code tests or fixture rendering passed. State separately whether a live target product was tested, whether real OpenRouter calls were made, and whether validation used synthetic fixtures.

## Dialogue appendix

Keep the product conversation separate from the testing model's decisions and survey feedback. On each session, retain an optional `transcript` object:

```json
{"source":"captured_browser_text","capture_status":"complete","capture_note":"All visible messages captured; native formatting may differ.","messages":[{"role":"user","text":"Exact submitted request","event_ids":["session-1:e002","session-1:e003"],"submission_event_id":"session-1:e003"},{"role":"assistant","text":"Exact visible product reply","event_ids":["session-1:e004"]}]}
```

Only include a user message after recorded evidence confirms submission. Use `assistant` for the product under test, not for Audience's planner or reviewer. Preserve chronological follow-up turns, paragraph breaks and available source links. Reference the observed event IDs; retain any source-span extraction audit in the reviewed run. When collecting transcripts after a legacy run, use literal spans from saved observations, never a summary or re-generated response. Preserve the raw run and make any extraction boundary explicit. Disclose clipping, inaccessible attachments or incomplete capture in `capture_note`; do not imply a server-native/full account export when only browser text was saved.

The HTML must show the agent name, scenario, model, session status, original request and product reply, with an optional link to the product conversation. Provide a direct navigation entry and TXT/JSON export. Preserve legibility without JavaScript and escape all product text. Do not label pending sessions as dialogues or silently omit an attempted session whose messages are missing. For a legacy run with no transcript, show an explicit missing-export state and the full available observations as evidence instead of claiming a complete conversation.
