import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("SAC_CLIENT_ID")
CLIENT_SECRET = os.getenv("SAC_CLIENT_SECRET")
TOKEN_URL     = os.getenv("SAC_TOKEN_URL")
BASE_URL      = os.getenv("SAC_BASE_URL")

MODEL_SHORT = "C3vrgh3epil2ate9pcq1bfe3h1j"
MODEL_NS    = "t.VDUPVI.C3vrgh3epil2ate9pcq1bfe3h1j"


def get_token():
    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def req(url, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "x-sap-sac-custom-auth": "true",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    raw = resp.content.decode("utf-8", errors="replace").strip()
    is_html = raw.startswith("<") or "<!DOCTYPE" in raw[:50]
    return resp.status_code, raw if not is_html else "(HTML)", resp.headers.get("Content-Type","")


if __name__ == "__main__":
    token = get_token()
    print("Token OK\n")

    for ep in [
        f"/sap/fpa/api/v1/models/{MODEL_SHORT}/dimensions",
        f"/sap/fpa/api/v1/models/{MODEL_SHORT}/data?$top=5",
        f"/sap/fpa/api/v1/models/{MODEL_NS}/dimensions",
        f"/sap/fpa/api/v1/models/{MODEL_NS}/data?$top=5",
    ]:
        s, b, ct = req(f"{BASE_URL}{ep}", token)
        print(f"[{s}] {ep}")
        print(f"  Content-Type: {ct}")
        print(f"  Body: {b[:600].encode('ascii', errors='replace').decode('ascii')}")
        print()