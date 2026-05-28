import requests
import pandas as pd


class SACConnector:
    def __init__(self, base_url, token_url, client_id, client_secret):
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None

    def get_token(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_token()}"}

    def list_stories(self) -> list:
        url = f"{self.base_url}/api/v1/stories"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        stories = data if isinstance(data, list) else data.get("value", data.get("stories", []))
        return [{"id": s.get("storyId", s.get("id", "")), "name": s.get("name", s.get("title", "Unnamed"))} for s in stories]

    def export_story_data(self, story_id: str) -> pd.DataFrame:
        url = f"{self.base_url}/api/v1/stories/{story_id}/export"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return pd.DataFrame(data)
        for key in ("data", "rows", "value", "records"):
            if key in data:
                return pd.DataFrame(data[key])
        return pd.DataFrame([data])