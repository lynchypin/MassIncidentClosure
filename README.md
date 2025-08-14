# PagerDuty Mass Incident Closure Tool

This script allows you to **bulk close open incidents** in PagerDuty based on your chosen time window and service selection.  
It is interactive, safe, and designed for use by PagerDuty admins, account owners, or users with sufficient permissions.

# OS Specific Notes

- For the best experience, use a modern terminal (Windows Terminal, PowerShell, or Mac Terminal).
- You’ll need your PagerDuty API token and user email to use the tool.
- If you encounter issues with interactive prompts on Windows, try running the script in Windows **Terminal or PowerShell** rather than **cmd.exe**.

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

  **OR**

  ```bash
 pip install -r requirements.txt

## PagerDuty User API Key (not an integration key!)

1. Log in to PagerDuty.
2. Click your avatar (top right) > **My Profile**.
3. Scroll to **User Settings** > **API Access Keys**.
4. Click **Create New API Key** and copy it somewhere safe.

You will also need your PagerDuty user email (the email you use to log in to PagerDuty).

---

## Usage

1. **Download the script** (e.g., `MassIncidentClosure.py`) to your computer.
2. **Open a terminal** and navigate to the script’s directory.
3. **Run the script:**

   ```bash
   python MassIncidentClosure.py

   ### Follow the prompts:

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

## Troubleshooting

### Permission errors
- Make sure you are using a **User API Key** (from your profile, not an integration).
- Make sure you enter your PagerDuty user email when prompted.
- You must have permission to resolve incidents on the selected services.

### No incidents closed
- Double-check your date and service selections.
- Only open incidents (`triggered` or `acknowledged`) older than your chosen date will be closed.

### Script errors
- Ensure you have installed all required Python packages.
- If you see a traceback, read the error message for clues (e.g., invalid date format).

---

## Security

- Your API key and email are only used for authentication and are **not stored**.
- Treat your API key like a password—**do not share it**.
