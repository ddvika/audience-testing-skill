# Validation status — 2026-11-09

## Version 0.3.1 — public preview

- The public host protocol now accepts literal product transcripts with same-session evidence, confirmed submission events, chronological checks, clipping indicators and a revision audit. Unsupported reconstructed replies, drafts and cross-session references are rejected.
- An independent offline host fixture exercised two personas and one follow-up through normal commands, including three transcript submissions. The generated report retained all six messages exactly, without editing the checkpoint by hand. Models and browser observations were deterministic fixtures; no live product or model API was used.
- Public source export excludes private run directories, credentials, caches and browser state. Re-exporting a clean public checkout produces the same source files. Repository version and Python package version share one source.
- The Python wheel was built and installed in a fresh virtual environment. From outside the source checkout, its CLI rendered the fictional example with bundled CSS/JavaScript. The offline suite passed 237 tests on Python 3.12; the prepared GitHub workflow additionally targets Python 3.10 and 3.13, which were not executed locally.
- Fresh local Chromium checks covered desktop and 390px mobile, no-JavaScript reading, source anchors and literal TXT/JSON downloads for the two-persona fixture. The public example also passed desktop/mobile layout and browser error checks without external network requests. These are local rendered fixtures, not new live-product studies.
- Public examples and the README illustration contain authored fictional data only. They demonstrate report structure, not real product findings or the accuracy of human-behavior predictions.

The host selects transcript boundaries from observed messages; this is not universal automatic DOM chat extraction. Missing lifecycle instrumentation is reported as unknown. The standalone adapter remains experimental: its conservative HTTP/action guards can block valid product flows, including chat submission; use an authorized host browser for authenticated AI products.

## Version 0.3.0

Shared-account host execution now separates persona model histories and requires explicit new-chat/resume preparation. It records actual task lifecycle, distinguishes continuation from a new task, preserves a cumulative budget ledger and enforces a whole-run deadline. Isolated contexts remain available through the existing standalone route.

New regression coverage checks bounded waits, empty-chat false success, completed-result evidence, action-response normalization, deadline/ledger reuse, shared-account preparation and sparse reports. A fresh forward fixture exercised the real host, engine and renderer for three personas and nine visits in six separate fixture chats. Models and UI were stubbed; this is implementation validation, not evidence about a market product or human behavior.

Live-study results and actual provider costs must be recorded in the run artifacts; do not infer successful live testing from these checks.

The authorized live host integration was subsequently exercised on an authenticated AI-assistant website with `openai/gpt-5.4-mini`: six personas each submitted a distinct request in a separate product chat and received a real response; two other planned personas were left unstarted at the time limit. The revised driver retained separate histories and provider accounting. Early protocol/context failures were preserved and excluded from product findings. The final 220 offline checks passed. This validates this host/model path only, not every provider or isolated-account deployment.

Live feedback also demonstrated why an evidence review is necessary: a model can like an answer containing a numerical error or recommend a status already visible. Preserve raw reactions and identify independent reviewer corrections rather than presenting modeled satisfaction as factual correctness.

## Version 0.2.0

This revision implements the standard product-owner report, not validated prediction of human behavior.

- All 174 offline tests pass: planning and budget bounds, per-session evidence, first/repeat visits, survey denominators, NPS/CSAT, grouped recommendations, cached final synthesis, conditional forecasts, provenance, escaping, redaction, browser barriers and CLI finalization.
- Two isolated local browser journeys were actually executed against an in-memory room-catalogue fixture. Eight real browser observations were passed through the decision/evidence engine and report builder. Model decisions were scripted test responses; this was not a live-market product study or an OpenRouter integration run.
- A separate agent used the installed skill to regenerate a product-owner report from that recorded fixture without new model calls. It correctly distinguished fixture evidence, calculated survey results and missing real-market forecasts.
- Generic rich, sparse and blocked reports were rendered offline in Chromium. Group/metric/scenario controls, persona dialogs, evidence anchors, mobile widths 320/390, no JavaScript and reduced motion were checked. A 1,000-person fixture validates bounded HTML previews rather than a huge animated DOM.
- An exported Python wheel includes the report CSS/JS and renders an HTML report when imported independently from the installed skill source. No external report assets or libraries are required.
- This revision made no paid OpenRouter calls and did not repeat the live Nika product study. Revised planning/feedback/synthesis prompts were exercised with deterministic test responses; they still require validation against the selected live models during an authorized study.

## Earlier integration checks (version 0.1.0)

The live OpenRouter catalogue was retrieved; JSON requests to `openai/gpt-4o-mini` and `openai/gpt-4.1-mini` succeeded. Automatic model availability probes and an evidence-grounded browser-action proposal were checked under one $0.25 cap (confirmed cost $0.000476553). Those checks did not establish that every catalogue model is available or compatible. They do not validate the new v0.2 prompts.

A complete standalone Playwright + live OpenRouter study has not been validated in this environment. Current standalone coverage includes mocked browser/API orchestration and local actual-browser evidence, not a claim of production end-to-end validation. Cross-host installation/execution in Claude has not been exercised; it requires compatible skill, Python, network and browser capabilities.

Before declaring a product study complete, execute its actual sessions and retain the observations. Implementation tests, example reports and conditional arithmetic are not product findings or real retention/NPS/CAC measurements.
