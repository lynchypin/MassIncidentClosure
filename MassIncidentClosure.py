import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import questionary
import requests
from dateutil import parser
from requests.adapters import HTTPAdapter, Retry

BASE_URL = "https://api.pagerduty.com"
PAGE_LIMIT = 100
# PagerDuty's bulk update endpoint accepts up to 250 incidents per request.
BULK_CHUNK = 250
AUDIT_LOG = "closed_incidents.log"


# --------------------------------------------------------------------------- #
# HTTP / API layer
# --------------------------------------------------------------------------- #
def build_session(api_token, user_email):
    """Create a requests session with auth headers and automatic retry/backoff."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Token token={api_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
        "From": user_email,
    })
    # Retry on rate limits (429) and transient server errors with exponential backoff.
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "PUT"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session


def validate_credentials(session):
    """Confirm the token/email work before doing anything destructive."""
    resp = session.get(f"{BASE_URL}/users/me")
    if resp.status_code == 401:
        raise SystemExit("Authentication failed: check your API token.")
    if resp.status_code == 403:
        raise SystemExit("Authentication failed: token lacks permission, or the "
                         "'From' email does not match a valid PagerDuty user.")
    resp.raise_for_status()


def paginate(session, path, params=None, list_key=None):
    """Fetch all pages from a PagerDuty list endpoint using offset pagination."""
    params = dict(params or {})
    params["limit"] = PAGE_LIMIT
    offset = 0
    results = []
    while True:
        params["offset"] = offset
        resp = session.get(f"{BASE_URL}{path}", params=params)
        resp.raise_for_status()
        data = resp.json()
        key = list_key or next(k for k, v in data.items() if isinstance(v, list))
        results.extend(data[key])
        if not data.get("more"):
            break
        offset += PAGE_LIMIT
    return results


def get_services(session):
    return paginate(session, "/services", list_key="services")


def get_open_incidents(session, service_ids=None, until=None):
    """Fetch open incidents, optionally scoped to services and created before `until`."""
    params = {"statuses[]": ["triggered", "acknowledged"]}
    if service_ids:
        params["service_ids[]"] = service_ids
    if until:
        # `until` filters on the created_at date range server-side.
        params["until"] = until.isoformat()
    return paginate(session, "/incidents", params=params, list_key="incidents")


def close_incidents(session, incidents):
    """Resolve incidents in bulk, chunked to respect the API's batch limit."""
    closed = 0
    for start in range(0, len(incidents), BULK_CHUNK):
        chunk = incidents[start:start + BULK_CHUNK]
        payload = {"incidents": [
            {"id": inc["id"], "type": "incident_reference", "status": "resolved"}
            for inc in chunk
        ]}
        resp = session.put(f"{BASE_URL}/incidents", json=payload)
        if resp.ok:
            closed += len(chunk)
            print(f"Resolved {len(chunk)} incidents.")
        else:
            print(f"Failed to resolve a batch of {len(chunk)}: "
                  f"{resp.status_code} {resp.text}")
    return closed


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse_cutoff(date_str):
    """Parse a YYYY-MM-DD (or fuller) date into a tz-aware UTC datetime."""
    cutoff = parser.parse(date_str)  # dateutil defaults missing time fields to midnight.
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return cutoff


def write_audit_log(incidents, path=AUDIT_LOG):
    """Append a record of resolved incidents for an audit trail."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(path, "a", encoding="utf-8") as fh:
        for inc in incidents:
            fh.write(json.dumps({
                "resolved_at": timestamp,
                "id": inc["id"],
                "service": inc.get("service", {}).get("summary"),
                "created_at": inc.get("created_at"),
            }) + "\n")
    return path


def ask(prompt):
    """Wrap questionary prompts so cancelling (Ctrl-C / Esc) exits cleanly."""
    answer = prompt.ask()
    if answer is None:
        raise SystemExit("Cancelled.")
    return answer


# --------------------------------------------------------------------------- #
# Configuration: resolve from CLI args, falling back to interactive prompts
# --------------------------------------------------------------------------- #
def build_arg_parser():
    p = argparse.ArgumentParser(
        description="Bulk-close open PagerDuty incidents by age/date and service.")
    p.add_argument("--token", help="PagerDuty user API token "
                   "(or set PAGERDUTY_TOKEN). Prompted if omitted.")
    p.add_argument("--email", help="PagerDuty user email for the 'From' header "
                   "(or set PAGERDUTY_EMAIL). Prompted if omitted.")
    p.add_argument("--before", metavar="YYYY-MM-DD",
                   help="Close incidents created before this date.")
    p.add_argument("--older-than-days", type=int, metavar="N",
                   help="Close incidents open longer than N days.")
    p.add_argument("--service-ids", nargs="+", metavar="ID",
                   help="Limit to these service IDs (default: all services).")
    p.add_argument("--dry-run", action="store_true",
                   help="List matching incidents but do not close anything.")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompts (for non-interactive use).")
    p.add_argument("--no-log", action="store_true",
                   help="Do not write the audit log file.")
    return p


def resolve_cutoff(args):
    """Determine the cutoff datetime from args, or prompt for it."""
    if args.before:
        return parse_cutoff(args.before), f"Incidents created before {args.before}"
    if args.older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
        return cutoff, (f"Incidents created before {cutoff.date()} "
                        f"(open > {args.older_than_days} days)")

    choice = ask(questionary.select(
        "Choose how to select incidents to close:",
        choices=[
            "Close incidents before a specific date",
            "Close incidents open longer than 30 days",
        ]))
    if choice == "Close incidents before a specific date":
        date_str = ask(questionary.text("Enter the cutoff date (YYYY-MM-DD):")).strip()
        try:
            cutoff = parse_cutoff(date_str)
        except (ValueError, OverflowError) as e:
            raise SystemExit(f"Could not parse date: {e}")
        return cutoff, f"Incidents created before {cutoff.date()}"
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    return cutoff, f"Incidents created before {cutoff.date()} (open > 30 days)"


def resolve_services(args, session):
    """Determine which service IDs to scope to, or prompt for them."""
    if args.service_ids:
        return args.service_ids, "Selected services: " + ", ".join(args.service_ids)

    # With nothing specified and no way (or need) to prompt, target all services.
    # The time filter still constrains what gets closed.
    if args.yes or not sys.stdin.isatty():
        return None, "All services"

    choice = ask(questionary.select(
        "Choose which services to close incidents on:",
        choices=["Close on all services", "Choose specific services"]))
    if choice == "Close on all services":
        return None, "All services"

    services = get_services(session)
    service_map = {svc["name"]: svc["id"] for svc in services}
    print("\nUse the arrow keys to move, space to select, and enter to confirm.\n")
    selected_names = ask(questionary.checkbox(
        "Select services (space to select, enter to confirm):",
        choices=list(service_map.keys())))
    if not selected_names:
        raise SystemExit("No services selected. Exiting.")
    return ([service_map[name] for name in selected_names],
            "Selected services: " + ", ".join(selected_names))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    if args.before and args.older_than_days is not None:
        raise SystemExit("Use only one of --before / --older-than-days.")

    print("PagerDuty Mass Incident Closure Tool\n")

    api_token = args.token or os.environ.get("PAGERDUTY_TOKEN")
    if not api_token:
        api_token = ask(questionary.password("Enter your PagerDuty API token:"))
    api_token = api_token.strip()

    user_email = args.email or os.environ.get("PAGERDUTY_EMAIL")
    if not user_email:
        user_email = ask(questionary.text("Enter your PagerDuty user email:"))
    user_email = user_email.strip()

    session = build_session(api_token, user_email)
    validate_credentials(session)

    cutoff_date, time_desc = resolve_cutoff(args)
    service_ids, service_desc = resolve_services(args, session)

    print("\nSummary of your choices:")
    print(f"Time filter: {time_desc}")
    print(f"Service filter: {service_desc}")
    print("Only open incidents (triggered or acknowledged) matching these criteria "
          "will be closed.")
    if args.dry_run:
        print("DRY RUN: no incidents will be closed.")

    if not args.yes and not args.dry_run:
        if not ask(questionary.confirm("Proceed to close these incidents?")):
            raise SystemExit("Aborted by user.")

    print("\nFetching open incidents...")
    to_close = get_open_incidents(session, service_ids, until=cutoff_date)

    print(f"{len(to_close)} incidents match your criteria.")
    if not to_close:
        raise SystemExit("No incidents to close. Exiting.")

    for inc in to_close:
        print(f" - {inc['id']} (Service: {inc['service']['summary']}, "
              f"Created: {inc['created_at']})")

    if args.dry_run:
        print(f"\nDry run complete. {len(to_close)} incidents would be closed.")
        return

    if not args.yes:
        if not ask(questionary.confirm("Are you sure you want to close these incidents?")):
            raise SystemExit("Aborted by user.")

    closed = close_incidents(session, to_close)

    if not args.no_log:
        log_path = write_audit_log(to_close)
        print(f"Audit log written to {log_path}")

    print(f"\nDone! Closed {closed} of {len(to_close)} matching incidents.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
    except requests.HTTPError as e:
        sys.exit(f"\nAPI error: {e}")
