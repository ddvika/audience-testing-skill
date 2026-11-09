# Contributing

Audience is an experimental product-testing skill and Python runner. Useful contributions improve reproducibility, browser integration, persona coverage and evidence quality.

Start with a small issue explaining the product behavior or workflow you want to improve. For a fix, include a recorded or synthetic example that reproduces the problem without private data.

## Run the offline checks

```bash
python -m unittest discover -s skills/audience/scripts/tests -q
python examples/generate_demo.py
```

No OpenRouter key is required. Live tests spend money and must use an explicitly authorized target, account and budget. Keep those tests separate from deterministic CI.

For report changes, inspect desktop and narrow screens, keyboard navigation, reduced motion and reading without JavaScript. Check that source-event links resolve and long saved messages are not shortened.

## Pull requests

Explain the observed problem, the resulting behavior and the checks you ran. Keep raw study records out of the repository. Preserve unknown values and distinguish product failures from runner, access or budget failures. Never replace missing evidence with plausible data.

The canonical runtime in this repository is `skills/audience/scripts/`. The report assets ship in the Python wheel; changes to packaging should verify a built wheel as well as the source tree.
