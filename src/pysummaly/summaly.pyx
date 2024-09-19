import re
from urllib.parse import urljoin, urlparse

import aiohttp
import orjson
from lxml import html as lxml_html

async def fetch(session, url, timeout, content_length_limit, content_length_required):
    async with session.get(url, timeout=timeout) as response:
        if content_length_required and response.content_length is None:
            raise aiohttp.ClientPayloadError("Content length required but not provided")
        if response.content_length and response.content_length > content_length_limit:
            raise aiohttp.ClientPayloadError("Content length exceeds limit")
        return await response.text()

async def fetch_head(session, url, timeout):
    async with session.head(url, timeout=timeout) as response:
        return response.status == 200

def escape_html_in_json(json_string):
    try:
        json_dict = orjson.loads(json_string)
        if "html" in json_dict:
            json_dict["html"] = json_dict["html"].replace('"', '\\"').replace("'", "\\'")
        return orjson.dumps(json_dict)
    except orjson.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None

async def get_oembed_player(session, page_url, timeout, content_length_limit, content_length_required):
    tree = await fetch_tree(session, page_url, timeout, content_length_limit, content_length_required)
    oembed_link = tree.xpath('//link[@type="application/json+oembed"]/@href')
    if not oembed_link:
        return None

    oembed_url = urljoin(page_url, oembed_link[0])
    oembed_response = await fetch(session, oembed_url, timeout, content_length_limit, content_length_required)
    oembed_response = escape_html_in_json(oembed_response)

    if oembed_response is None:
        return None

    try:
        oembed_data = orjson.loads(oembed_response.decode("utf-8"))
    except orjson.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None

    if oembed_data.get("version") != "1.0" or oembed_data.get("type") not in ["rich", "video"]:
        return None

    oembed_html_tree = lxml_html.fromstring(oembed_data.get("html", ""))
    iframe = oembed_html_tree.xpath("//iframe")

    if len(iframe) != 1:
        return None

    iframe = iframe[0]
    url = iframe.get("src")

    match = re.search(r'"(https?://[^\"]+)"', url)

    if not match or urlparse(url).scheme != "https":
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
        "autoplay", "clipboard-write", "fullscreen", "encrypted-media",
        "picture-in-picture", "web-share", "accelerometer"
    ]
    ignored_list = ["gyroscope"]
    allowed_permissions = [
        perm.strip().strip('\\"') for perm in allowed_permissions if perm and perm not in ignored_list
    ]

    if iframe.get("allowfullscreen") == "":
        allowed_permissions.append("fullscreen")

    non_safe_permissions = [perm for perm in allowed_permissions if perm not in safe_list]

    if non_safe_permissions:
        print(f"Non-safe permissions detected: {', '.join(non_safe_permissions)}. Skipping embed.")
        return None

    return {
        "url": url.rstrip("\\"),
        "width": width,
        "height": height,
        "allow": allowed_permissions,
    }

async def fetch_tree(session, url, timeout, content_length_limit, content_length_required):
    html_content = await fetch(session, url, timeout, content_length_limit, content_length_required)
    return lxml_html.fromstring(html_content)

async def extract_metadata(url, opts=None):
    opts = opts or {}
    user_agent = opts.get("userAgent")
    response_timeout = opts.get("responseTimeout", 10)
    operation_timeout = opts.get("operationTimeout", 10)
    content_length_limit = opts.get("contentLengthLimit", 100**6)
    content_length_required = opts.get("contentLengthRequired", False)

    headers = {"User-Agent": user_agent} if user_agent else {}
    timeout = aiohttp.ClientTimeout(total=operation_timeout, connect=response_timeout)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        tree = await fetch_tree(session, url, timeout, content_length_limit, content_length_required)

        title = (
            tree.xpath('//meta[@property="og:title"]/@content')
            or tree.xpath('//meta[@name="twitter:title"]/@content')
            or tree.xpath("//title/text()")
        )
        title = title[0] if title else None

        if not title:
            return None

        image = (
            tree.xpath('//meta[@property="og:image"]/@content')
            or tree.xpath('//meta[@name="twitter:image"]/@content')
            or tree.xpath('//link[@rel="image_src"]/@href')
            or tree.xpath('//link[@rel="apple-touch-icon"]/@href')
        )
        image = image[0] if image else None
        image = urljoin(url, image) if image else None

        description = (
            tree.xpath('//meta[@property="og:description"]/@content')
            or tree.xpath('//meta[@name="twitter:description"]/@content')
            or tree.xpath('//meta[@name="description"]/@content')
        )
        description = description[0] if description else None

        site_name = (
            tree.xpath('//meta[@property="og:site_name"]/@content')
            or tree.xpath('//meta[@name="application-name"]/@content')
        )
        site_name = site_name[0] if site_name else urlparse(url).hostname

        favicon = (
            tree.xpath('//link[@rel="shortcut icon"]/@href')
            or tree.xpath('//link[@rel="icon"]/@href')
        )
        favicon = favicon[0] if favicon else "/favicon.ico"
        favicon = urljoin(url, favicon)

        activity_pub = tree.xpath('//link[@rel="alternate"][@type="application/activity+json"]/@href')
        activity_pub = activity_pub[0] if activity_pub else None

        sensitive = tree.xpath('//meta[@property="mixi:content-rating"]/@content')
        sensitive = sensitive[0] == "1" if sensitive else False

        icon_url = await fetch_head(session, favicon, timeout)
        icon = favicon if icon_url else None

        oembed = await get_oembed_player(session, url, timeout, content_length_limit, content_length_required)
        if oembed is None:
            oembed = {"url": None, "width": None, "height": None}

        return {
            "title": title,
            "icon": icon,
            "description": description,
            "thumbnail": image,
            "player": oembed,
            "sitename": site_name,
            "sensitive": sensitive,
            "url": url,
        }
