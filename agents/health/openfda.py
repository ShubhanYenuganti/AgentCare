import urllib.parse
import httpx

_TIMEOUT = 2.0


def check_drug_interactions(drug_names: list[str]) -> dict:
    if not drug_names:
        return {"status": "lookup_unavailable"}
    drug = urllib.parse.quote(drug_names[0])
    url = f"https://api.fda.gov/drug/label.json?search=drug_interactions:{drug}&limit=1"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"status": "lookup_unavailable"}


def check_drug_recall(drug_name: str) -> dict | None:
    drug = urllib.parse.quote(drug_name)
    url = f"https://api.fda.gov/drug/enforcement.json?search=product_description:{drug}+AND+status:Ongoing-Recall&limit=1"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results")
            if results:
                return results[0]
            return None
    except Exception:
        return None
