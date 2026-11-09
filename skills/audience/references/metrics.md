# Metrics, experiment design and evidence

## Contents

- Evidence and experiment coverage
- Recorded feedback fields
- Denominators and participant-level answers
- Recommendations and priorities
- Conditional forecast inputs and formulas
- Cost accounting and artifacts

## Evidence and experiment coverage

Distinguish recorded browser facts, synthetic judgments, conditional calculations and missing evidence. An AI agent is a simulated persona, not an independent human respondent. Never infer market demand, willingness to pay or real retention from persona prose.

`plan.experiment_design` records the question, audience summary, reasons for selecting groups, group IDs/persona IDs, planned counts, scenario goals and limitations. The report starts with **Дизайн эксперимента** and explains why these groups fit the visible product. These are audience hypotheses, not demographic findings.

Keep planned, executed and evaluable counts separate. A session is executed only when it contains an actual visible browser observation and is not pending. A blocked or failed session may have observations but no evaluable product outcome. A persona with two visits counts as one persona and two sessions. Planned device allocation is not evidence of the viewport used: show measured `observation.viewport` separately when available, and mark missing viewport evidence unknown.

A supported result needs `completed`, `feedback.outcome=success`, a visible observation, and a valid same-session event reference. Event IDs must be unique within the session. A failed action or a concluding `finish` assertion is not supporting browser evidence. This checks provenance; the semantic interpretation remains the agent's assessment. Full traces stay available for review.

## Recorded feedback fields

The runner asks each completing agent for:

- `outcome`: `success`, `partial` or `failure`, with `evidence_ids`.
- `rating`: recommendation likelihood, integer zero through ten, or null. Used for synthetic NPS only.
- `return_intent`: boolean or null. This is stated preference after a simulated visit.
- `likes`, `dislikes`, `summary`: short statements about the recorded experience.
- `assessment`: `purpose_clear`, `next_step_clear`, `result_clear` as booleans or null; `satisfaction` integer one through five or null; `effort` integer one through five or null; `evidence_ids`.
- `journey`: optional explicit stage observations `{stage, reached, evidence_ids}`. Stages are `entry`, `start`, `action`, `result`, `return`. Do not assess `return` in a first-use session.
- `recommendations`: `{change, reason, evidence_ids}` plus `stage`, `scope` (`product`, `flow`, `detail`), `issue_key`, `observed`, `proposed`, `expected_metric`, `how_to_verify`.

Invalid or unsupported assessment values become null. Missing answers stay unknown; never fill them with zero, average scores or imagined feelings. A generic recommendation rating cannot become a satisfaction score. Preserve model and persona attribution.

## Denominators and participant-level answers

Task completion includes only observed completed, agent-abandoned and step-limited sessions. A step limit is an incomplete task, not a claim that the agent chose to leave. Exclude technical failures, access/policy blocks, budget limits, pending and running sessions, and show them separately. Session task metrics remain session-level; first-use and repeat-task metrics have their own denominators.

For NPS, CSAT, effort and return intent, use each persona's **latest valid answer to that question**, not every visit. Only eligible sessions with a valid feedback outcome and supporting recorded evidence contribute. This avoids double-counting someone who visited twice. Unknown is the planned persona population minus valid respondents.

- Synthetic NPS = one hundred times `(promoters − detractors) / valid respondents`. Promoters rate nine or ten, detractors zero through six, passives seven or eight. Show the respondent count; it is not customer NPS or a market benchmark.
- Synthetic CSAT = share rating satisfaction four or five out of valid one-to-five answers. Also show mean and full score distribution. It measures simulated satisfaction only.
- Return intent = share of valid boolean answers that are true. It is neither D7 nor D30 retention.
- Effort reports the mean of explicit one-to-five answers; never infer it from runtime duration.
- `satisfaction.assessment` uses latest valid answers. `satisfaction.first_use_assessment` uses only first-use answers so later familiarity cannot hide initial confusion. Label the chosen scope.

Segment comparisons retain their own sample sizes. Do not compare unweighted group means as a population estimate. A compressed repeat visit retains persona identity and browser context; it does not mean seven or thirty days have passed. Runtime duration includes model and browser latency and must not be called human time-to-value.

Journey stages appear only when explicitly assessed with evidence. Each stage has its own assessed count and unknown count. These observations are not automatically a monotonic conversion funnel.

## Recommendations and priorities

Group repeated issues using their stage and issue key, and count unique affected personas from cited events. Two visits by one persona are not two affected people. Without valid references, a recommendation remains a hypothesis and cannot enter the top priorities.

Order supported issues from product value to client journey to local detail; within a level consider affected personas and incomplete tasks. A product-wide issue needs evidence from at least two personas; otherwise describe it as a flow-level observation. A numerical uplift is never implied by this ordering.

Show at most three supported next-release priorities. Each has: what happened, whom it affected, what to change, what metric to check and how to repeat the test. Show fewer than three when evidence is limited. Preserve supported positive feedback separately. A final model synthesis may consolidate wording, but counts, references and formulas are recomputed and stale synthesis is rejected.

## Conditional forecast inputs and formulas

Always include **Прогноз продуктовых метрик**. If inputs are absent, explain which data are needed; never seed a real report with demonstration values. Forecasts are external assumptions, not inferred effects, statistical confidence intervals or causal estimates.

Pass a UTF-8 JSON file through `--forecast-inputs`. Fractions use zero through one, counts and spending are nonnegative. Explicit named scenarios support comparisons:

```json
{
  "source": "Допущения владельца продукта; один календарный месяц",
  "monthly_visitors": 10000,
  "marketing_spend": 300000,
  "currency": "RUB",
  "cohort_definition": "Новые пользователи, впервые получившие полезный результат в этом месяце",
  "active_definition": "Пользователь с хотя бы одной завершённой задачей",
  "baseline": {
    "label": "До изменений",
    "registration_rate": 0.35,
    "activation_rate": 0.60,
    "d7_retention": 0.25,
    "d30_retention": 0.12,
    "paid_conversion": 0.03,
    "mau": 5000,
    "active_days": 8
  },
  "scenarios": [
    {
      "name": "base",
      "label": "Если заданные условия выполнятся",
      "assumptions": {
        "registration_rate": 0.40,
        "activation_rate": 0.65,
        "d7_retention": 0.28,
        "d30_retention": 0.15,
        "paid_conversion": 0.036,
        "mau": 5800,
        "active_days": 9
      }
    }
  ]
}
```

These numbers illustrate the file format only. Never reuse them for another product. Scenario names and values come from the user or their analytics. Top-level scalar fields are common assumptions; local fields override them. A scenario does not silently inherit the baseline's changed rates. `source` and the exact input path of each value are retained in provenance.

Calculations:

| Metric | Definition |
| --- | --- |
| First-result share of visitors | `registration_rate × activation_rate`; activation is the share of registered users who get their first useful result |
| Activated users | `monthly_visitors × registration_rate × activation_rate` |
| D7 / D30 returners | Explicit `retention_cohort_size × d7_retention / d30_retention`; if cohort size is absent, use calculated activated users, with that assumption shown |
| D7 / D30 rate | Supplied fraction returning on that exact day; do not mix with “returned at any time within seven days” |
| New paying customers | `monthly_visitors × paid_conversion` in the same period |
| CAC | `marketing_spend / new paying customers`, assuming all stated acquisition spend belongs to that cohort |
| MAU | Explicit external active-user count; not inferred from return intent |
| Average DAU | `MAU × active_days / 30`, where active days is the monthly mean per active user |
| DAU / MAU | Calculated DAU divided by supplied MAU |
| Scenario delta | After minus baseline; relative change only when baseline is nonzero and units match |

An explicitly invalid cohort size never silently falls back to activated users. Zero customers make CAC undefined; zero MAU makes DAU/MAU undefined. Invalid or nonfinite arithmetic stays unavailable. Different currencies cannot be compared without an explicit conversion into one currency. A forecast can be partially available: show valid metrics and list missing inputs for the rest.

Legacy range input remains supported as a separate shape:

```json
{
  "source": "External analytics assumptions",
  "monthly_visitors": 1000,
  "marketing_spend": 1000,
  "currency": "RUB",
  "paid_conversion": [0.01, 0.04],
  "return_rate": [0.10, 0.20],
  "mau": [100, 200],
  "active_days": [3, 6]
}
```

Ranges are low/high assumptions. CAC reverses customer bounds; DAU multiplies the corresponding MAU/activity bounds. `return_rate` is only the supplied rate and needs its cohort/window interpretation. It does not generate MAU. Prefer named scenarios when before/after, activation or day-specific retention is requested.

## Cost accounting and artifacts

OpenRouter research costs are always USD and separate from the product's CAC currency. Separate provider-confirmed `actual` costs, conservative `estimated` costs, ambiguous `unknown` amounts and active `reserved` requests. `accounted_usd` is the sum charged against the cap, not a provider invoice. Never add a settled request's original reservation again. Unknown amounts prevent a claim that remaining budget is known.

`report.json` contains schema version two, the complete recorded run with accidental credentials redacted, computed metrics, experiment, audience groups, satisfaction, journey, ranked issues, forecast inputs/provenance and cost ledger. `report.md` and the offline `report.html` use those same computed values. They never contain fixed Nika counts, demonstration outcomes or a fabricated forecast.
