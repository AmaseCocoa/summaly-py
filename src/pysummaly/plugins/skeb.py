# SkebはRetry-After: 0な429を返すらしい
import asyncio
import ipaddress
import re

import aiohttp
import yarl
from lxml import html


async def test(url: yarl.URL) -> bool:
    if not url.host:
        return False
    return url.host == "skeb.jp" or url.host == "ske.be"

async def find_request_key(html_content: str) -> str:
    tree = html.fromstring(html_content)
    script_tag = tree.xpath('//script/text()')
    if script_tag:
        script_content = script_tag[0]
        match = re.search(r'document\.cookie\s*=\s*"([^"]+)"', script_content)
        if match:
            cookie = match.group(1)
            request_key = re.search(r'request_key=([^;]+)', cookie)
            if request_key:
                return request_key.group(1)
            else:
                return None
        else:
            return None

async def fetch(
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
    async with session.get(url, timeout=timeout) as r:
        if r.status == 429:
            await asyncio.sleep(int(r.headers.get("Retry-After")))
            request_key = await find_request_key(await r.text())
            async with session.get(url, timeout=timeout, cookies={"request_key": request_key}) as response:
                if content_length_required and response.content_length is None:
                    raise aiohttp.ClientPayloadError("Content length required but not provided")
                if content_length_limit:
                    if (
                        response.content_length
                        and response.content_length > content_length_limit
                    ):
                        raise aiohttp.ClientPayloadError("Content length exceeds limit")
                return await response.text()
