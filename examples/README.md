# Fictional report example

**Everything in this example is authored fixture data.** Seatly is a fictional ticket-selection service at the reserved `seatly.example` domain. No live product, browser session or model call produced these results.

Open [`report.html`](report.html) locally for the complete interactive report. The report is currently written in Russian, matching the bundled renderer's section labels. The README illustration at `docs/assets/report-preview.png` is an English summary of the same example; it is explicitly labeled as an illustration, not a screenshot.

The fixture contains:

- Six fictional personas in three task groups.
- Six first-use visits and two continuations of existing tasks.
- Six successful visit goals out of eight; the two continuations do not count as new tasks.
- Four of six personas with a latest satisfaction rating of 4 or 5.
- Two illustrated release priorities, with references to fictional events.
- Eight conversation records with the original authored request and reply text.
- No forecasts for real retention, CAC, DAU or MAU: the example supplies no real traffic, cost or activity data.

Rebuild from the repository root without credentials or network access:

```bash
python examples/generate_demo.py
```

This writes `demo-run.json`, `report.html`, `report.md` and `report.json` under `examples/` using the same renderer as the skill. To regenerate the illustration, install the optional development dependency Pillow and run:

```bash
python -m pip install Pillow
python examples/generate_preview.py
```

`fixture/scripted-persona` is a label for the authored fixture, not an OpenRouter model ID. Do not cite example counts as a product study or evidence of predictive accuracy.
