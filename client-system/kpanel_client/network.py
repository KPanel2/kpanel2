import requests


def is_url_reachable(url: str, timeout_sec: int = 5) -> bool:
    try:
        response = requests.get(url, timeout=timeout_sec)
        return response.status_code in (200, 204)
    except requests.RequestException:
        return False


def has_internet(check_url: str, timeout_sec: int = 5) -> bool:
    return is_url_reachable(check_url, timeout_sec=timeout_sec)
