import requests


def has_internet(check_url: str, timeout_sec: int = 5) -> bool:
    try:
        response = requests.get(check_url, timeout=timeout_sec)
        return response.status_code in (200, 204)
    except requests.RequestException:
        return False
