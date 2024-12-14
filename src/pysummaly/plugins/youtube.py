# SkebはRetry-After: 0な429を返すらしい
from urllib.parse import quote, urlparse
import re
import ipaddress

import aiohttp
import yarl
from lxml import html


async def test(url: yarl.URL) -> bool:
    if not url.host:
        return False
    return (
        url.host == "youtube.com"
        or url.host == "youtu.be"
        or url.host == "www.youtube.com"
    )


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
    async with session.get(
        "https://www.youtube.com/oembed?format=json&url=" + quote(url), timeout=timeout
    ) as response:
        if content_length_required and response.content_length is None:
            raise aiohttp.ClientPayloadError("Content length required but not provided")
        if content_length_limit:
            if (
                response.content_length
                and response.content_length > content_length_limit
            ):
                raise aiohttp.ClientPayloadError("Content length exceeds limit")
        r = await response.json()
        tree = html.fromstring(r["html"])
        iframe = tree.xpath("//iframe")
        if len(iframe) != 1:
            return None
        iframe = iframe[0]
        url = iframe.get("src")
        url_parsed = yarl.URL(url)

        match = re.search(r'"(https?:\/\/[^\"]+)"', url)

        if url_parsed.scheme != "https":  # not match or
            print("Non Matching URL")
            return None

        width = iframe.get("width", "").rstrip("%").strip('\\"')
        height = iframe.get("height", "").rstrip("%").strip('\\"')

        try:
            width = int(width) if width.isdigit() else None
            height = min(int(height), 1024) if height.isdigit() else None
        except ValueError:
            print("ValueError in width/height conversion")
            return None

        allowed_permissions = iframe.get("allow", "").split(";")
        safe_list = [
            "autoplay",
            "clipboard-write",
            "fullscreen",
            "encrypted-media",
            "picture-in-picture",
            "web-share",
        ]
        ignored_list = ["gyroscope", "accelerometer"]
        allowed_permissions = [
            perm.strip().strip('\\"')
            for perm in allowed_permissions
            if perm and perm not in ignored_list
        ]

        if iframe.get("allowfullscreen") == "":
            allowed_permissions.append("fullscreen")

        non_safe_permissions = [
            perm for perm in allowed_permissions 
            if perm not in safe_list and perm not in ignored_list
        ]


        if non_safe_permissions:
            print(
                f"Non-safe permissions detected: {', '.join(non_safe_permissions)}. Skipping embed."
            )
            return None

        return {
            "url": url.rstrip("\\"),
            "width": width,
            "height": height,
            "allow": allowed_permissions,
        }
