# Installation and host requirements

[English overview](../README.md) · [Описание по-русски](README.ru.md)

Audience has two parts: the installable folder `skills/audience/` and a Python runner. Install the whole folder, including its scripts and references; `SKILL.md` alone is not enough.

Get the source first:

```bash
git clone https://github.com/ddvika/audience-testing-skill.git
cd audience-testing-skill
```

## Pick the execution route

| Environment | Route | Required capabilities |
| --- | --- | --- |
| Assistant with an authorized browser and Python terminal | `host` — recommended | Skill loading, a persistent Python process, HTTPS access to OpenRouter, visible browser observations and actions |
| Local Python or an assistant allowed to run Playwright | `run` — experimental; public browsing/navigation | Python 3.10+, Playwright, Chromium and network access |
| Chat without executable resources or a usable browser | Planning only | It cannot run an actual product test in that environment |

The host route uses Python's standard library. The standalone route needs the `browser` extra. The current report interface is Russian. Review the [validation record](../skills/audience/references/validation.md) for tested paths; the project does not claim validation in every ChatGPT or Claude product.

For authenticated products and AI chat interactions, use the host's authorized browser. The standalone CLI has no account-state import, and its guards block sending messages and may block product POST requests.

## Claude Code

From the root of the cloned repository, copy the skill into the project where you want to use it:

```bash
mkdir -p /path/to/your-project/.claude/skills
cp -R skills/audience /path/to/your-project/.claude/skills/audience
```

Then start Claude Code in that project and invoke `/audience` with your URL, question and budget. A personal installation can instead use `~/.claude/skills/audience/`. Do not overwrite an existing installation without reviewing your local changes.

These paths follow the [official Claude Code skills documentation](https://code.claude.com/docs/en/skills). Installing the folder is supported by the skill format; Audience's complete Claude execution path has not yet been validated. Browser, shell, network and account permissions remain host responsibilities.

## ChatGPT / Codex and other skill hosts

Use your environment's supported custom-skill installer for the complete `skills/audience/` folder. If it accepts an archive, archive that folder as the top-level `audience/` directory rather than uploading the entire repository.

The assistant must be able to run Python, keep the host bridge alive, reach OpenRouter and operate an authorized browser. It should use the host's own browser tools when that environment requires them. A chat subscription or a successful skill upload alone does not guarantee these capabilities.

## Standalone Python

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[browser]'
python -m playwright install chromium
audience --help
```

On Windows, use these commands in WSL. To install only the Python runner for a host-driven browser or report generation:

```bash
python -m pip install -e .
```

Use `--prompt-key` in an interactive terminal to enter your OpenRouter key without echo, or inject `OPENROUTER_API_KEY` through your secret manager. The program does not automatically load `.env` files. Do not include a key in a shell command or commit it to the repository.

## The host bridge

An assistant obtains an actual product snapshot, then starts:

```bash
audience host https://your-product.example \
  --task "Check whether users can get a first useful result" \
  --snapshot /path/to/initial-snapshot.json \
  --session-mode shared_account \
  --agents 6 \
  --budget 2 \
  --max-minutes 30 \
  --output runs/host-study
```

This example expects the key to be supplied through the environment. The assistant exchanges JSON lines with the persistent process, executes only validated actions through its authorized browser, and submits real observations after each action. `host` does not click the browser by itself. See the complete [runtime contract](../skills/audience/references/runtime.md).

For one signed-in account, `shared_account` requires sequential personas and a separate product conversation for each. New tabs do not isolate account memory. Use `isolated` only when the host can actually provide separate browser contexts/accounts. Authentication remains a host/user step; do not feed passwords to the model.

Capture literal product conversations when testing a chat interface. The runner cannot infer missing messages from the final evaluation. Send each conversation through the bridge’s `transcript` command before `quit` or the deadline. Each submitted user message must cite its fill and submission events; replies must match recorded text exactly. Keep source references and partial-capture notes. The complete command format is in the runtime contract.

## Time, cost and incomplete sessions

The default budget is $1 and the default whole-run deadline is 30 minutes. Set both explicitly for repeatable studies. The clock includes planning and model calls. Treat the time value as a run deadline, not a guarantee that every requested persona will finish.

Use `--ledger-path` when continuing under an existing spending cap. Host `--resume` restores an existing checkpoint and its original deadline rather than resetting the budget. See the runtime contract before using recovery commands. Do not restart with a fresh ledger to disguise a charge or exceed the authorized cap.

For public reports, inspect observations, conversations and any optional screenshots before sharing. They can include private product or account data even when the API key is not present.

## Check the installation without spending

```bash
audience --help
python examples/generate_demo.py
python -m unittest discover -s skills/audience/scripts/tests -v
```

None of these commands should call OpenRouter. `audience models --eligible --limit 20` is a separate live catalogue request; it does not require a key.
