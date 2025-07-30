# PagerDuty Mass Incident Closure Tool

This script allows you to **bulk close open incidents** in PagerDuty based on your chosen time window and service selection.  
It is interactive, safe, and designed for use by PagerDuty admins, account owners, or users with sufficient permissions.

---

## Features

- **Interactive CLI:** Choose incidents to close by date or age, and by all or specific services.
- **Safe:** Double confirmation before any incidents are closed.
- **Secure:** Authenticates as you, using your PagerDuty user API key and email.
- **Clear feedback:** See exactly what will be closed before any action is taken.

---

## Prerequisites

- **Python 3.7+** installed on your system.
- The following Python packages:
  - `requests`
  - `python-dateutil`
  - `questionary`

  Install them with:

  ```bash
  pip install requests python-dateutil questionary
