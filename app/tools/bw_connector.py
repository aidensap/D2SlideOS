import pandas as pd
from pathlib import Path
from app.config import BW_MODE

MOCK_DIR = Path(__file__).parent.parent.parent / "mock_data"


def list_available_reports() -> list[dict]:
    return [
        {"id": f.stem, "filename": f.name}
        for f in sorted(MOCK_DIR.glob("*.csv"))
    ]


def get_report(report_id: str) -> pd.DataFrame:
    if BW_MODE == "mock":
        return _get_mock(report_id)
    elif BW_MODE == "odata":
        return _get_odata(report_id)
    elif BW_MODE == "rfc":
        return _get_rfc(report_id)
    else:
        raise ValueError(f"未知 BW_MODE: {BW_MODE}")


def _get_mock(report_id: str) -> pd.DataFrame:
    path = MOCK_DIR / f"{report_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"找不到报表文件: {path}")
    return pd.read_csv(path)


def _get_odata(report_id: str) -> pd.DataFrame:
    # TODO: 接入 BW OData 端点
    # 需要配置 BW_ODATA_URL / BW_USERNAME / BW_PASSWORD
    raise NotImplementedError("OData 模式尚未实现，请联系系统管理员获取端点地址")


def _get_rfc(report_id: str) -> pd.DataFrame:
    # TODO: 接入 BW RFC（需要安装 SAP NW RFC SDK + pyrfc）
    # 通过 BAPI_MDDATAPROVIDER 调用 BEx Query
    raise NotImplementedError("RFC 模式尚未实现，需要安装 SAP NetWeaver RFC SDK")
