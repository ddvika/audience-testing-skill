# Security and study data

Audience can send visible product content and synthetic user prompts to models through OpenRouter. Use only products and test accounts you are authorized to assess. Provider data handling depends on the model and provider you select.

Keep `OPENROUTER_API_KEY` in an environment or secret manager, or enter it with `--prompt-key`. Never place keys in an issue, prompt, screenshot, repository or report. The project does not load `.env` files automatically.

Local study artifacts contain product observations, prompts, replies and URLs. They are private by default and excluded by the repository's ignore rules. Review them before sharing. Redaction is best effort, not a guarantee that arbitrary product content is free of personal data.

Browser restrictions and spend reservations are protective controls, not a security sandbox or a guarantee about provider billing. The host remains responsible for permitted interactions. Do not disable a host's safety controls to complete a study.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting when it is enabled for this repository. If it is unavailable, open an issue containing only a high-level description and ask for a private reporting channel. Do not publish exploit details, credentials or private study data in the issue.
