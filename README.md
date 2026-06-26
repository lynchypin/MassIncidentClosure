# PagerDuty Mass Incident Closure Tool

This script allows you to **bulk close open incidents** in PagerDuty based on your chosen time window and service selection.  
It is interactive, safe, and authenticates with your **personal PagerDuty _User_ API key** (see below) — **not** an account-level/admin or integration key. It acts as you, so you can close any incidents your own PagerDuty user has permission to resolve.

# OS Specific Notes

- For the best experience, use a modern terminal (Windows Terminal, PowerShell, or Mac Terminal).
- You’ll need your PagerDuty **User** API key (see below) and user email to use the tool.
- If you encounter issues with interactive prompts on Windows, try running the script in Windows **Terminal or PowerShell** rather than **cmd.exe**.

---

## Features

- **Interactive CLI:** Choose incidents to close by date or age, and by all or specific services.
- **Non-interactive mode:** Pass everything as command-line flags for scripting and automation.
- **Dry run:** Preview exactly which incidents *would* be closed without closing anything.
- **Safe:** Double confirmation before any incidents are closed (interactive mode).
- **Robust:** Handles API pagination, rate limits (with automatic retry/backoff), and closes incidents in bulk.
- **Auditable:** Writes a log of every closed incident (ID, service, timestamp) to `closed_incidents.log`.
- **Secure:** Authenticates as you, using your PagerDuty user API key and email. Credentials are never stored.

---

## Prerequisites

- **Python 3.9+** installed on your system.
- The Python packages listed in `requirements.txt` (`requests`, `python-dateutil`, `questionary`).

### Setup

The path to this project may contain spaces, so **keep the quotes** in the `cd` command below.

```bash
cd "/path/to/MassIncidentClosure"

# Create a virtual environment (once)
python3 -m venv .venv

# Install dependencies into it
.venv/bin/pip install -r requirements.txt
```

> **Tip:** Using `.venv/bin/python` directly (as shown throughout this README)
> avoids needing to `source .venv/bin/activate`, which sidesteps shell/activation
> issues. If you prefer to activate it: `source .venv/bin/activate` (then just use
> `python`), and `deactivate` when finished.

## PagerDuty **User** API Key (not an admin / account-level or integration key!)

> ⚠️ **Use a personal _User_ API key — not an account-level (admin) API key and
> not an integration/routing key.**
>
> - A **User API key** is created from *your own profile* and acts **as you**,
>   with exactly the permissions your PagerDuty user already has. This is what
>   the tool needs, and it's why you also provide your user email (the `From`
>   header) for the audit trail.
> - An **account-level / admin (General Access) API key** is created under
>   **Integrations → API Access Keys** and is **not** what this tool uses. Account
>   keys don't represent a specific user, so the resolve action has no valid `From`
>   user and will fail.
> - An **integration / Events API routing key** is for sending events *into*
>   PagerDuty and will not work here at all.

Create your **User** API key:

  1. Log in to PagerDuty.
  2. Click your avatar (top right) > **My Profile**.
  3. Open the **User Settings** tab.
  4. Under **API Access Keys**, click **Create API User Token** and copy it somewhere safe.

  You will also need your PagerDuty user email (the email you use to log in to PagerDuty).

---

## Usage

### Interactive mode (default)

Run the script with no arguments and follow the prompts:

```bash
.venv/bin/python MassIncidentClosure.py
```

#### Follow the prompts:

- **Enter your PagerDuty API token:**  
  Paste the User API Key you created above.

- **Enter your PagerDuty user email:**  
  This is your PagerDuty login email. It is required for authentication.

- **Choose how to select incidents to close:**
  - **Close incidents before a specific date:**  
    Enter a date (YYYY-MM-DD). All open incidents created before this date will be eligible for closure.
  - **Close incidents open longer than 30 days:**  
    All open incidents created more than 30 days ago will be eligible for closure.

- **Choose which services to close incidents on:**
  - **Close on all services:**  
    The script will consider incidents from all services.
  - **Choose specific services:**  
    - You’ll see a checklist of all your PagerDuty services.
    - Use the **arrow keys** to move, **spacebar** to select/deselect, and **enter** to confirm your choices.
    - The script will only consider incidents from the services you select.

- **Review your choices:**  
  The script will print a summary of your selections (date, services, etc.) and ask for confirmation.

- **Final confirmation:**  
  You must confirm again before any incidents are closed.

- **Closure:**  
  The script will close all matching open incidents and print the results.

### Non-interactive mode (flags)

Provide your criteria as command-line flags to skip the prompts — useful for
scripting, scheduled jobs, or CI. Run with `--help` to see all options:

```bash
.venv/bin/python MassIncidentClosure.py --help
```

| Flag | Description |
|------|-------------|
| `--token TOKEN` | PagerDuty user API token (or set the `PAGERDUTY_TOKEN` env var). Prompted if omitted. |
| `--email EMAIL` | PagerDuty user email for the `From` header (or set `PAGERDUTY_EMAIL`). Prompted if omitted. |
| `--before YYYY-MM-DD` | Close incidents created before this date. |
| `--older-than-days N` | Close incidents open longer than N days. |
| `--service-ids ID [ID ...]` | Limit to these service IDs (default: all services). |
| `--dry-run` | List matching incidents but **do not close anything**. |
| `--yes`, `-y` | Skip confirmation prompts (for non-interactive use). |
| `--no-log` | Do not write the `closed_incidents.log` audit file. |

`--before` and `--older-than-days` are mutually exclusive.

**Examples:**

```bash
# Preview what would be closed — closes nothing:
.venv/bin/python MassIncidentClosure.py \
  --token "$PAGERDUTY_TOKEN" --email you@company.com \
  --before 2026-01-01 --dry-run

# Close everything open more than 30 days, no prompts:
.venv/bin/python MassIncidentClosure.py \
  --token "$PAGERDUTY_TOKEN" --email you@company.com \
  --older-than-days 30 --yes

# Scope to specific services using env vars for credentials:
export PAGERDUTY_TOKEN=... PAGERDUTY_EMAIL=you@company.com
.venv/bin/python MassIncidentClosure.py \
  --before 2026-01-01 --service-ids PXXXXXX PYYYYYY --yes
```

> When run without a terminal (e.g. in CI) and no `--service-ids` are given,
> the tool targets **all services** filtered by your time window.

### Audit log

Each closed incident is recorded as a line of JSON in `closed_incidents.log`
(ID, service, created/resolved timestamps). Use `--no-log` to disable.

### Running the tests

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## Troubleshooting

### Permission errors
- Make sure you are using a **User API key** created from **My Profile → User Settings**
  — **not** an account-level/admin (General Access) key from **Integrations → API Access Keys**,
  and **not** an integration/routing key. Only a User key carries a valid `From` user for resolving incidents.
- Make sure the email you enter matches the user who owns that API key.
- You must have permission to resolve incidents on the selected services.

### No incidents closed
- Double-check your date and service selections.
- Only open incidents (`triggered` or `acknowledged`) older than your chosen date will be closed.

### Script errors
- Ensure you have installed all required Python packages.
- If you see a traceback, read the error message for clues (e.g., invalid date format).

### `NotOpenSSLWarning` about LibreSSL
- Harmless. It comes from macOS's older system Python. To silence it, install a
  newer Python (e.g. `brew install python@3.12`) and recreate the virtual environment.

---

## Security

- Your API key and email are only used for authentication and are **not stored**.
- Treat your API key like a password—**do not share it**.
- A record of which incidents were closed is written to `closed_incidents.log`
  (no credentials are included). Use `--no-log` to disable it.
