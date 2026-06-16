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
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "x-sap-sac-custom-auth": "true",
            "Accept": "application/json",
        }

    # ── Stories ──────────────────────────────────────────────────────────

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

    # ── Models (OData dataexport API — same approach as sacapi library) ──

    def list_models(self) -> list:
        """List all available models via the OData dataexport administration endpoint."""
        url = f"{self.base_url}/api/v1/dataexport/administration/Namespaces/sac/Providers"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        providers = data.get("value", data) if isinstance(data, dict) else data
        return [
            {
                "id": p.get("ProviderID", p.get("id", "")),
                "name": p.get("ProviderName", p.get("name", "Unnamed")),
                "description": p.get("ProviderDescription", ""),
            }
            for p in providers
            if isinstance(p, dict)
        ]

    def get_model_metadata(self, model_id: str) -> dict:
        """Get dimension/measure definitions for a model."""
        url = f"{self.base_url}/api/v1/dataexport/providers/sac/{model_id}/"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_model_data(self, model_id: str, top: int = 5000, filters: str = "") -> pd.DataFrame:
        """Read fact data from a model via OData.

        Args:
            model_id: Technical model ID (e.g. 't.S.CAMT_SALES_PLAN:...')
            top: Max rows to return
            filters: Optional raw OData $filter string
        """
        params = f"$top={top}&$format=json"
        if filters:
            params += f"&$filter={filters}"
        url = f"{self.base_url}/api/v1/dataexport/providers/sac/{model_id}/FactData?{params}"
        resp = requests.get(url, headers=self._headers(), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("value", data) if isinstance(data, dict) else data
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
