import httpx
from ..settings import settings


class ZabbixNotConfigured(Exception):
    pass


class ZabbixError(Exception):
    pass


def _require_configured():
    if not (settings.ZABBIX_URL and settings.ZABBIX_USERNAME and settings.ZABBIX_PASSWORD):
        raise ZabbixNotConfigured(
            "Zabbix integration is not configured (set ZABBIX_URL, ZABBIX_USERNAME, "
            "ZABBIX_PASSWORD in backend/.env)"
        )


def _zbx_call(method: str, params: dict, auth: str | None = None) -> dict:
    _require_configured()
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        payload["auth"] = auth

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            settings.ZABBIX_URL,
            json=payload,
            headers={"Content-Type": "application/json-rpc"},
        )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ZabbixError(data["error"].get("data") or data["error"].get("message") or str(data["error"]))
    return data["result"]


def zabbix_login() -> str:
    """Authenticate against the Zabbix API and return a session token."""
    return _zbx_call(
        "user.login",
        {"username": settings.ZABBIX_USERNAME, "password": settings.ZABBIX_PASSWORD},
    )


def list_host_groups() -> list[dict]:
    """Return [{groupid, name}, ...] for every host group in Zabbix."""
    auth = zabbix_login()
    groups = _zbx_call("hostgroup.get", {"output": ["groupid", "name"]}, auth=auth)
    return sorted(groups, key=lambda g: g["name"])


def list_hosts_in_groups(group_ids: list[str]) -> list[dict]:
    """Return [{hostname, ip}, ...] for every host in the given Zabbix group IDs."""
    auth = zabbix_login()
    hosts = _zbx_call(
        "host.get",
        {
            "groupids": group_ids,
            "output": ["host", "name"],
            "selectInterfaces": ["ip"],
        },
        auth=auth,
    )
    results = []
    for h in hosts:
        for iface in h.get("interfaces", []):
            ip = iface.get("ip")
            if ip:
                results.append({"hostname": h.get("name") or h.get("host"), "ip": ip})
    return results
