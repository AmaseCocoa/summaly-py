# spotify.linkなどでoembedが解釈されないので
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import ipaddress
import re

import aiohttp
import yarl


async def test(url: yarl.URL) -> bool:
    if not url.host:
        return False
    m = True if re.match(r"[a-zA-Z0-9]+\.app\.link", url.host) else False
    return m or url.host == "spotify.link"


async def fetch(
    session: aiohttp.ClientSession,
    url,
    timeout,
    content_length_limit,
    content_length_required,
):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_params['$web_only'] = 'true'
    new_query_string = urlencode(query_params, doseq=True)
    url_noredirect = urlunparse(parsed_url._replace(query=new_query_string))
    try:
        resolver = aiohttp.DefaultResolver()
        infos = await resolver.resolve(url_noredirect.split("://")[-1].split("/")[0], 0)
        for info in infos:
            ip = ipaddress.ip_address(info["host"])
            if ip.is_private or ip.is_loopback:
                raise Exception("Access to local IPs is denied.")
    except Exception as e:
        raise Exception(f"DNS resolution failed: {e}")
    async with session.get(url_noredirect, timeout=timeout) as response:
        if content_length_required and response.content_length is None:
            raise aiohttp.ClientPayloadError("Content length required but not provided")
        if content_length_limit:
            if (
                response.content_length
                and response.content_length > content_length_limit
            ):
                raise aiohttp.ClientPayloadError("Content length exceeds limit")
        return await response.text()