# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       check_url_liveness_v1
# input_schema:  {"urls": "list[str]", "timeout_sec": "int"}
# output_schema: {"live_urls": "list[str]", "failed_urls": "list[str]", "error_map": "dict"}

import asyncio
import json
import sys

import aiohttp


async def _check_url(session: aiohttp.ClientSession, url: str, timeout: int) -> tuple[str, str | None]:
    """Return (url, None) if live, (url, error_reason) if failed."""
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
            if resp.status < 400:
                return (url, None)
            return (url, f"HTTP_{resp.status}")
    except aiohttp.ClientConnectorError:
        return (url, "DNS_FAILURE")
    except asyncio.TimeoutError:
        return (url, "TIMEOUT")
    except aiohttp.ClientSSLError:
        return (url, "SSL_ERROR")
    except Exception as exc:
        return (url, f"UNKNOWN: {type(exc).__name__}")


async def _check_all(urls: list[str], timeout: int) -> tuple[list[str], list[str], dict[str, str]]:
    live: list[str] = []
    failed: list[str] = []
    error_map: dict[str, str] = {}

    async with aiohttp.ClientSession() as session:
        tasks = [_check_url(session, url, timeout) for url in urls]
        results = await asyncio.gather(*tasks)

    for url, error in results:
        if error is None:
            live.append(url)
        else:
            failed.append(url)
            error_map[url] = error

    return live, failed, error_map


def execute(inputs: dict) -> dict:
    """Check URL liveness via async HEAD requests."""
    urls = inputs["urls"]
    timeout = inputs.get("timeout_sec", 10)

    live, failed, error_map = asyncio.run(_check_all(urls, timeout))

    return {
        "live_urls": live,
        "failed_urls": failed,
        "error_map": error_map,
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
