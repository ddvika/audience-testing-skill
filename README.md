# Audience

**Unleash an AI crowd on your product.**

Put dozens or hundreds of AI agents in the role of your users. Audience is an open-source skill that gives them different personas, sends them through real browser journeys, and turns their recorded actions into a clear product report: where they got stuck, what worked, and what to fix next.

Give it a website, a research question and a budget. Start with a small pilot or request up to **1,000 personas**, using your choice of OpenRouter models. Budget, time and browser capacity determine how many journeys finish; this is simulated user research, not a recruited human panel.

[Русский](docs/README.ru.md) · [Installation](docs/installation.md) · [Sample report](examples/report.html) · [Report screenshot]([docs/assets/report-screenshot.png](https://github.com/ddvika/audience-testing-skill/blob/main/docs/assets/Изображение%20ChatGPT%209%20нояб.%202026%20г.%2C%2010_42_58.png)) · [How metrics work](skills/audience/references/metrics.md)

[![Audience: AI agents test your product, find where they get stuck, and show what to fix.](docs/assets/audience-cover.png)](examples/report.html)

*Download the sample HTML and open it locally to explore the interactive report.*

## Start with a product question

> Use Audience to test my product at `https://your-product.example`.
> Find out whether new users understand how to get their first useful result.
> Choose the audience and models. Keep OpenRouter spending under $2 and stop within 30 minutes.

Or specify the panel yourself: 12 agents, the models you want, and the scenarios to cover. The assistant still needs an authorized browser, Python and network access; installing a skill does not supply those capabilities.

## What you get

- **An explicit experiment design.** Who the personas represent, why those groups were chosen, what was planned and what actually ran.
- **Real interaction evidence.** Browser actions, visible responses and linked events. Captured product conversations appear in a readable dialogue appendix, with TXT and JSON export.
- **A product decision.** Up to three supported priorities, with a concrete change and a way to check whether it helped.
- **Useful measurements.** Task outcomes, journey progress, clarity, synthetic satisfaction and recommendation ratings, with denominators and missing data visible.
- **A report you can share.** One offline HTML file, plus Markdown and JSON. Cream, carmine, large numbers and small scroll animations; no external fonts or dashboard service.

## Try the report without a key

From the repository root:

```bash
python examples/generate_demo.py
```

Open `examples/report.html`. This builds a clearly labeled synthetic example; it does not contact a website or spend model credits.

## Run your first study

Python 3.10+ on macOS or Linux; Windows through WSL.

**Recommended: use it as a skill.** Install the complete [`skills/audience/`](skills/audience/) folder in a compatible assistant and give it the request above. This route can use the host's browser and an authorized test account. See [installation and host requirements](docs/installation.md).

**Standalone browser route — experimental:**

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[browser]'
python -m playwright install chromium

audience run https://your-product.example \
  --task "Can a new user find a product and understand its price? Stop before purchase." \
  --budget 2 \
  --max-minutes 30 \
  --output runs/first-study \
  --prompt-key
```

Replace the example URL with your product. `--prompt-key` reads the OpenRouter key without echoing it; a secret manager can instead supply `OPENROUTER_API_KEY`. Do not put a key in a command, source file or issue.

The standalone adapter creates isolated browser contexts and is best suited to public browsing/navigation checks. Its production guard can block legitimate POST requests; authentication and sending chat messages are not a supported standalone quick start. Use the host route for a signed-in test account or an AI chat product. See [current validation limits](skills/audience/references/validation.md).

## Choose agents, models and scenarios

Automatic selection is the default. Audience reads OpenRouter's live catalogue, filters compatible text models, and proposes a small panel under the configured budget. This is a cost/capability heuristic, not a proven optimal mix.

```bash
# Inspect compatible model IDs; this catalogue command needs no key.
audience models --eligible --limit 20

# Replace both model IDs with exact values from the catalogue.
audience run https://your-product.example \
  --task "Compare first-use and return journeys. Stop before checkout." \
  --agents 12 \
  --models provider/model-a,provider/model-b \
  --scenarios first_use,resume,regular \
  --concurrency 3 \
  --budget 5 \
  --max-minutes 30 \
  --output runs/manual-study \
  --prompt-key
```

The CLI accepts **1–1,000 personas**; budget and time determine how many can actually finish. Planned personas are never reported as completed tests. Standalone concurrency is 1–8 contexts. The host's browser capabilities determine what can run in parallel.

**Only one browser?** Use host mode with `--session-mode shared_account`. Personas take turns, each with a separate model history and product conversation. Server memory, account quota and personalization may still be shared; the report states that limitation. See [the host bridge](skills/audience/references/runtime.md).

## Read the findings, then inspect the evidence

The report follows this order: experiment design → main decision → release priorities → audience and journey differences → interface findings → impressions → conditional metrics → next-release plan → dialogue appendix.

For chat products, the host must capture the actual submitted messages and visible replies. Audience does not invent a transcript from feedback. If message capture is absent, the report says so and shows the available browser observations. The generic standalone adapter currently records observations rather than automatically identifying every product's message roles.

Regenerate a report from an existing run without new model calls:

```bash
audience report runs/first-study/run.json --output reports/first-study
```

Add `--forecast-inputs assumptions.json` only when you have explicit traffic, spend, activity or retention assumptions. [Metric definitions and forecast inputs](skills/audience/references/metrics.md) explain what can be calculated.

## What the results mean

Audience helps find product problems and form testable hypotheses. Its personas are simulations, not a recruited sample of customers. A satisfied AI agent can miss a wrong answer, so the workflow separates its opinion from an evidence review.

Synthetic CSAT/NPS and willingness to return are labeled as such. **They do not establish real retention, CAC, DAU or MAU.** Those metrics need external data or explicit assumptions. Modeled repeat visits do not represent elapsed days.

The current runner uses text/DOM observations; it is not a visual-design benchmark. The report interface is currently in Russian. Cross-host execution in Claude has not yet been validated; capability requirements and tested paths are documented in [validation status](skills/audience/references/validation.md).

## Cost and data boundaries

The configured OpenRouter cap covers probes, planning, agent decisions and final synthesis. Calls reserve estimated costs before execution; ambiguous charges remain reserved. The report separates confirmed spending from estimates. The cap does not include your assistant subscription, browser hosting or charges from the product under test.

Visible product text is sent to OpenRouter and the selected model providers. Use authorized test accounts and appropriate data. Keep run directories, chat transcripts and screenshots private unless you deliberately review them for sharing. The repository examples contain fictional data only.

The default workflow stops at payments, bookings, messages to other people, destructive actions and unexpected access barriers. Browser guards are best effort; they do not make an arbitrary production account a safe sandbox.

## Develop and contribute

```bash
python -m unittest discover -s skills/audience/scripts/tests -v
```

The source lives in `skills/audience/scripts/`: CLI, OpenRouter client, budget ledger, experiment planner, browser adapters and report renderer. CI uses offline fixtures and mocks; passing CI is not evidence that a live product was tested.

Useful contributions include browser adapters, reliable message capture, report localization and comparisons with human usability studies. Include a minimal reproduction and redact keys, account details and private conversations.

[MIT license](LICENSE). Independent project; not affiliated with OpenRouter, OpenAI or Anthropic.
