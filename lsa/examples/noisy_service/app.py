import requests


def charge_customer(amount: int) -> dict:
    response = requests.post("https://api.stripe.com/v1/charges", json={"amount": amount})
    return {"status": "submitted", "provider_status": response.status_code}


def refund_customer(amount: int) -> dict:
    response = requests.post("https://api.stripe.com/v1/refunds", json={"amount": amount})
    return {"status": "submitted", "provider_status": response.status_code}


def notify_customer(email: str) -> None:
    requests.post("https://api.mailgun.net/v3/messages", json={"email": email})


def sync_ledger(entry_id: str, amount: int) -> None:
    requests.post("https://ledger.internal/v1/entries", json={"entry_id": entry_id, "amount": amount})


def emit_analytics(event_name: str, customer_id: str) -> None:
    requests.post(
        "https://api.segment.io/v1/track",
        json={"event": event_name, "customer_id": customer_id},
    )
