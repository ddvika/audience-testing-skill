# Runtime and browser adapters

## Requirements

Python 3.10+ on macOS/Linux (Windows via WSL), outbound HTTPS to `openrouter.ai`, an OpenRouter key, and a browser adapter. The native host route uses the standard library only. The standalone browser route adds Playwright and Chromium. A custom skill does not provide a browser, model credits, network access or parallel execution privileges by itself.

## A single user request

Input: URL + research question. Optional: audience, agent count, models, budget, scenarios.

1. Inspect the product's actual public UI with the authorized browser. Capture a short visible snapshot.
2. Start `audience.py host ... --snapshot ...` in a persistent terminal session. Supply the key through the environment, or `--prompt-key` with a TTY (echo is disabled during entry). Do not write shell commands that embed a key.
3. The first stdout JSON object contains `ready`, the chosen plan and ordered session IDs. The process remains alive; feed commands to its stdin. Do not close/restart it between actions.
4. Choose `isolated` for genuinely separate contexts, or `shared_account` for one authorized test account. In shared mode, serialize browser actions, open a fresh conversation for each persona, and keep its conversation URL for later visits. Model histories remain separate; server memory, personalization and quota may be shared. Report this explicitly. A new tab alone does not isolate an account. Follow the bridge's `next_session` preparation instructions and send the observed `session_context` on the first `next`.
5. Use the host's native browser tool to obtain observations and execute each returned action. The runner itself never executes a native browser action.
6. For a chat product, capture the literal submitted messages and visible product replies. Send the `transcript` command below while the process is active, after each response. Do not wait until the run deadline to save every dialogue.
7. Finish with `quit`. The finalizer makes one optional budgeted synthesis from recorded evidence and writes the standard report. Repeated finalization reuses its evidence fingerprint. Save/report incomplete sessions explicitly if the host's runtime ends early.

Example input line (the snapshot must come from the browser, not this example):

```json
{"command":"next","session_id":"p001-first_use","snapshot":{"url":"https://product.example","title":"Product","text":"Visible page text","viewport":{"width":1280,"height":900},"elements":[{"id":"button-start","role":"button","name":"Start"}]}}
```

Example output:

```json
{"session_id":"p001-first_use","status":"running","action":{"type":"click","target":"button-start"}}
```

After performing that action and observing the result:

```json
{"command":"next","session_id":"p001-first_use","result":{"status":"ok","reason":"Clicked Start; the setup screen appeared"},"snapshot":{"url":"https://product.example/setup","title":"Setup","text":"Visible setup screen","elements":[]}}
```

Do not send `ok` if the action was only proposed or failed. Use `blocked` for permissions/bot/login barriers and `error` for technical failures. A `stop` command can end a session without a further model call:

```json
{"command":"stop","session_id":"p001-first_use","status":"blocked","reason":"Login required"}
{"command":"quit"}
```

The host must apply its own action policy, exact-target checking and allowed-origin rules. The exported browser policy can be reused for semantic validation, but it does not replace the host's rules. Keep map `{observation id -> actual native locator}` per snapshot; refresh it after navigation. Do not reuse stale element indexes.

## Capturing product conversations

`transcript` records words already present in this session's successful events. It does not call a model or interact with the product. The host identifies message boundaries from the actual UI; the runner verifies exact text and source-event references. For each user message, cite its successful `fill` and later submission `click`, and pass the latter as `submission_event_id`. Product replies must be literal spans of cited task observations. Cross-session references and rewritten answers are rejected.

```json
{"command":"transcript","session_id":"p001-first_use","transcript":{"source":"captured_browser_text","capture_status":"complete","product_name":"Product","capture_note":"All visible messages in this visit were captured; original formatting may differ.","messages":[{"role":"user","text":"Exact submitted request","event_ids":["p001-first_use:e002","p001-first_use:e003"],"submission_event_id":"p001-first_use:e003"},{"role":"assistant","text":"Exact visible reply","event_ids":["p001-first_use:e005"]}]}}
```

Replace these examples with the real session's recorded IDs and literal text. Send the full chronological message list again after a follow-up. Identical submissions are idempotent; changed captures preserve the previous version in the run audit. A successful response includes `transcript_saved`, `message_count` and `changed`.

Use `capture_status: partial` when any visible content is missing or clipped, and explain the gap in `capture_note`. The default is partial. A clipped source observation automatically makes capture partial. Current limits are 100 messages, 10,000 characters per message and 200,000 characters per transcript. Do not remove words to fit the limit and then label the result complete. A capture is the recorded browser text, not a native server export or proof that hidden messages/attachments were retrieved.

This command requires an already recorded submitted task and must be sent before bridge shutdown. If the environment cannot capture a transcript, preserve the available observations and report the missing messages. The standalone adapter does not automatically classify message roles on arbitrary websites.

## CLI options

| Option | Meaning |
|---|---|
| `--agents auto` | Choose a small count under the cap; never a claim of statistical power |
| `--agents 1..1000` | Exact requested persona count, if estimated cost fits |
| `--models id-a,id-b` | Exact catalogue IDs, manually selected |
| `--budget 1` | Total USD cap across availability probes, planning, decisions and final synthesis; conservative reservations |
| `--max-steps 12` | Maximum model decisions per persona per scenario |
| `--scenarios first_use,resume,regular` | Explicit ordered session modes |
| `--device desktop` | Fix the viewport type when the native host only supports one device size |
| `--concurrency 3` | Standalone only, 1–8 simultaneous persona contexts |
| `--session-mode shared_account` | Host only: several personas using one signed-in account sequentially, separate product conversations and model histories |
| `--session-mode isolated` | Default: host provides isolated contexts; standalone creates them |
| `--ledger-path file.json` | Reuse accounting for retries under the same total budget; never reset expenses |
| `--max-minutes 30` | Whole-run wall-clock limit, including planning and model calls |
| `--site-mode production` | Standalone conservative network/interaction guard |
| `--allow-origin https://sub.example` | Standalone explicit extra product origin |
| `--screenshots` | Standalone opt-in local page screenshots; may contain visible private data |
| `--forecast-inputs file.json` | Explicit scenario assumptions for product metrics |

`models --output catalogue.json --limit 10` saves the full matched catalogue and prints only 10 rows. `models --eligible` shows models usable by this text/DOM adapter; image/audio-only models remain discoverable in the full catalogue but cannot act as these users.

## Files and failures

A run produces `plan.json`, `run.json`, `usage.json`, HTML/Markdown/JSON reports. The usage ledger contains model IDs, token counts, costs and reservations, not prompts or keys. Treat run observations as potentially sensitive product evidence; share only within the user's requested scope.

Model/API errors, budget exhaustion, step limits and blocked browser actions are separate from user dislike. An invalid model JSON response is recorded as an error; do not silently turn it into a negative UX judgment. A failed billable call may retain an uncertain cost reservation. Do not reset a ledger to “try again for free”. Use a new output directory for a separately authorized run.

## Several personas in one native browser

Pass `--session-mode shared_account --agents 8 --max-minutes 30`. Preparation is a host operation, not a fictional persona action. Each persona must perform its own real task. Pass `session_context: {kind: "new_chat", url: "<observed URL>"}` with its initial snapshot; for `resume`, restore the URL actually recorded for that persona and use `kind: "resume_previous_task"`. Keep unrelated account history out of model observations. Product account state is not isolated by this mode.

Read the current UI to supply optional `task_state` (`idle`, `running`, `completed`, `failed`). While `running`, the engine requests bounded `wait` actions without spending on repeated model decisions. Re-observe after the wait using the host's permitted wait/observation mechanism. Never infer completion from a disappeared spinner alone: an actual result must be visible. For chat products, only set completion for the answer to the current persona's submitted request, not illustrative landing-page cards. Resume means reopening a prior task; it is not a second task or real retention.

The action endpoint may accept a stream of multiple complete JSON action objects only by retaining its first object and discarding all later proposals. It validates that entire stream, records normalization, then applies ordinary semantic action checks against the current snapshot. Planning and synthesis JSON remain strict. No later action executes without a new observation.

If a protocol/runtime defect is corrected mid-study, restore with `--resume` and the original output directory and ledger. `{"command":"retry","session_id":"..."}` reopens only an errored session, at most twice, while preserving its audit, decisions, budget and original deadline. It refuses pending/unconfirmed browser actions. Then obtain a fresh snapshot and call `next`; never replay a browser action because a model response failed.

## Compatibility

- ChatGPT Work/Codex with skills, code execution, network and native browser: use `host`.
- Claude with custom skills and an authorized browser tool plus code/network: use `host` with that browser tool.
- Claude Code/Codex CLI/local Python where headless browser execution is allowed: use `run`.
- A chat environment without these capabilities: the skill can prepare a plan, but cannot truthfully execute a browser study there.

Do not claim testing in every ChatGPT/Claude variant. Capability detection is part of execution.

Official references checked 2026-11-07:
- https://openrouter.ai/docs/api/api-reference/models/get-models
- https://openrouter.ai/docs/cookbook/administration/usage-accounting
- https://support.claude.com/en/articles/12512198-how-to-create-custom-skills

## Report regeneration

`python scripts/audience.py report /path/run.json --output /path/report` renders the recorded
study without API calls. Add `--forecast-inputs /path/assumptions.json` to recalculate conditional
metrics from explicit external inputs. This never reruns browser journeys or fills absent
assessment fields. See [the report contract](report-contract.md) and [metrics](metrics.md).

The final live synthesis uses only recorded evidence and the existing budget ledger. It is
optional when coverage or remaining funds are insufficient. Planned set-aside funds are not
actual expenses. A synthesis error cannot turn incomplete sessions into completed testing.
