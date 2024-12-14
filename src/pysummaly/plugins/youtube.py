# SkebはRetry-After: 0な429を返すらしい
from urllib.parse import quote
import ipaddress

import aiohttp
import yarl

async def test(url: yarl.URL) -> bool:
    if not url.host:
        return False
    return url.host == "youtube.com" or url.host == "youtu.be" or url.host == "www.youtube.com"


async def get_oembed_player(
    session: aiohttp.ClientSession,
    url,
    timeout,
    content_length_limit,
    content_length_required,
):
    try:
        resolver = aiohttp.DefaultResolver()
        infos = await resolver.resolve(url.split("://")[-1].split("/")[0], 0)
        for info in infos:
            ip = ipaddress.ip_address(info["host"])
            if ip.is_private or ip.is_loopback:
                raise Exception("Access to local IPs is denied.")
    except Exception as e:
        raise Exception(f"DNS resolution failed: {e}")
    async with session.get("https://www.youtube.com/oembed?format=json&url=" + quote(url), timeout=timeout) as response:
        if content_length_required and response.content_length is None:
            raise aiohttp.ClientPayloadError("Content length required but not provided")
        if content_length_limit:
            if (
                response.content_length
                and response.content_length > content_length_limit
            ):
                raise aiohttp.ClientPayloadError("Content length exceeds limit")
        return await response.json()