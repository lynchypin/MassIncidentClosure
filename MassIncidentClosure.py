import requests
import datetime
from dateutil import parser
import questionary
from datetime import datetime as dt, timezone

BASE_URL = "https://api.pagerduty.com"

def get_services(headers):
    services = []
    url = f"{BASE_URL}/services?limit=100"
    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        services.extend(data['services'])
        url = data.get('next', None)
    return services

def get_open_incidents(headers, service_ids=None):
    incidents = []
    url = f"{BASE_URL}/incidents?statuses[]=triggered&statuses[]=acknowledged&limit=100"
    if service_ids:
        for sid in service_ids:
            resp = requests.get(url + f"&service_ids[]={sid}", headers=headers)
            resp.raise_for_status()
            incidents.extend(resp.json()['incidents'])
    else:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        incidents = resp.json()['incidents']
    return incidents

def close_incident(headers, incident_id):
    url = f"{BASE_URL}/incidents/{incident_id}"
    payload = {
        "incident": {
            "type": "incident",
            "status": "resolved"
        }
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print(f"Closed incident {incident_id}")
    else:
        print(f"Failed to close incident {incident_id}: {resp.status_code} {resp.text}")

def main():
    print("PagerDuty Mass Incident Closure Tool\n")
    api_token = questionary.password("Enter your PagerDuty API token:").ask().strip()
    user_email = questionary.text("Enter your PagerDuty user email:").ask().strip()
    headers = {
        "Authorization": f"Token token={api_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
        "From": user_email
    }

    # Time filter
    time_choice = questionary.select(
        "Choose how to select incidents to close:",
        choices=[
            "Close incidents before a specific date",
            "Close incidents open longer than 30 days"
        ]).ask()

    if time_choice == "Close incidents before a specific date":
        date_str = questionary.text("Enter the cutoff date (YYYY-MM-DD):").ask().strip()
        try:
            cutoff_date = parser.parse(date_str)
        except Exception as e:
            print(f"Could not parse date: {e}")
            return
        # If only a date is entered, set time to midnight
        if cutoff_date.hour == 0 and cutoff_date.minute == 0 and cutoff_date.second == 0 and len(date_str) <= 10:
            cutoff_date = dt.combine(cutoff_date.date(), dt.min.time())
        # Make sure it's timezone-aware (UTC)
        if cutoff_date.tzinfo is None:
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        time_desc = f"Incidents created before {cutoff_date.date()}"
    else:
        cutoff_date = dt.utcnow() - datetime.timedelta(days=30)
        cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        time_desc = f"Incidents created before {cutoff_date.date()} (open > 30 days)"

    # Service filter
    service_choice = questionary.select(
        "Choose which services to close incidents on:",
        choices=[
            "Close on all services",
            "Choose specific services"
        ]).ask()

    if service_choice == "Close on all services":
        service_ids = None
        service_desc = "All services"
    else:
        services = get_services(headers)
        service_map = {svc['name']: svc['id'] for svc in services}
        print("\nYou will now select which services to close incidents on.")
        print("Use the arrow keys to move, space to select, and enter to confirm your choices.\n")
        selected_names = questionary.checkbox(
            "Select services (space to select, enter to confirm):",
            choices=list(service_map.keys())
        ).ask()
        if not selected_names:
            print("No services selected. Exiting.")
            return
        service_ids = [service_map[name] for name in selected_names]
        service_desc = "Selected services: " + ", ".join(selected_names)
        print("\nYou have selected the following services to close incidents on:")
        for name in selected_names:
            print(f" - {name}")
        print("All open incidents on these services matching your time filter will be closed.")

    # Summary and confirmation
    print("\nSummary of your choices:")
    print(f"Time filter: {time_desc}")
    print(f"Service filter: {service_desc}")
    print("Only open incidents (triggered or acknowledged) matching these criteria will be closed.")
    confirm = questionary.confirm("Proceed to close these incidents? (Y/N)").ask()
    if not confirm:
        print("Aborted by user.")
        return

    # Fetch and filter incidents
    print("\nFetching open incidents...")
    incidents = get_open_incidents(headers, service_ids)
    print(f"Found {len(incidents)} open incidents.")

    to_close = []
    for inc in incidents:
        created_at = parser.parse(inc['created_at'])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at < cutoff_date:
            to_close.append(inc)

    print(f"{len(to_close)} incidents match your criteria and will be closed.")
    if not to_close:
        print("No incidents to close. Exiting.")
        return

    confirm2 = questionary.confirm("Are you sure you want to close these incidents? (Y/N)").ask()
    if not confirm2:
        print("Aborted by user.")
        return

    for inc in to_close:
        print(f"Closing incident {inc['id']} (Service: {inc['service']['summary']}, Created: {inc['created_at']})")
        close_incident(headers, inc['id'])

    print("\nDone! All matching incidents have been closed.")

if __name__ == "__main__":
    main()
