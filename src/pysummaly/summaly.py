import re
from urllib.parse import urljoin, urlparse
import ipaddress

import aiohttp

import orjson
from lxml import html as lxml_html

from .plugins import check as check_fetch

private_regex = r'^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}$|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}$|192\.168\.\d{1,3}\.\d{1,3})'

async def fetch(session: aiohttp.ClientSession, url, timeout, content_length_limit, content_length_required, cf):
    if isinstance(cf, str):
        return cf
    try:
        resolver = aiohttp.DefaultResolver()
        infos = await resolver.resolve(url.split('://')[-1].split('/')[0], 0)
        for info in infos:
            ip = ipaddress.ip_address(info['host'])
            if ip.is_private or ip.is_loopback:
                raise Exception("Access to local IPs is denied.")
    except Exception as e:
        raise Exception(f"DNS resolution failed: {e}")
    async with session.get(url, timeout=timeout) as response:
        if content_length_required and response.content_length is None:
            raise aiohttp.ClientPayloadError("Content length required but not provided")
        if content_length_limit:
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
    cf = await check_fetch(session, page_url, timeout, content_length_limit, content_length_required)
    if isinstance(cf, dict):
        return cf
    tree = await fetch_tree(session, page_url, timeout, content_length_limit, content_length_required, cf)
    oembed_link = tree.xpath('//link[@type="application/json+oembed"]/@href')
    if not oembed_link:
        return None

    oembed_url = urljoin(page_url, oembed_link[0])
    oembed_response = await fetch(session, oembed_url, timeout, content_length_limit, content_length_required, cf)
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
    url_parsed = urlparse(url)

    match = re.search(r'"(https?://[^\"]+)"', url) 

    if not match or url_parsed.scheme != "https":
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

async def fetch_tree(session, url, timeout, content_length_limit, content_length_required, cf):
    html_content = await fetch(session, url, timeout, content_length_limit, content_length_required, cf=cf)
    return lxml_html.fromstring(html_content)

async def summarize(url, opts=None):
    opts = opts or {}
    user_agent = opts.get("userAgent")
    response_timeout = opts.get("responseTimeout", 10)
    operation_timeout = opts.get("operationTimeout", 10)
    content_length_limit = opts.get("contentLengthLimit", 100**6)
    content_length_required = opts.get("contentLengthRequired", False)

    headers = {"User-Agent": user_agent} if user_agent else {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 PySummalyBot/x.y.z"}
    timeout = aiohttp.ClientTimeout(total=operation_timeout, connect=response_timeout)

    if bool(re.match(private_regex, urlparse(url).hostname)): 
        return {}
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        cf = await check_fetch(session, url, timeout, content_length_limit, content_length_required, no_oembed=True)
        if isinstance(cf, dict):
            return cf
        tree = await fetch_tree(session, url, timeout, content_length_limit, content_length_required, cf=cf)

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

        mixi_sensitive = tree.xpath('//meta[@property="mixi:content-rating"]/@content')
        mixi_sensitive = mixi_sensitive[0] == "1" if mixi_sensitive else False
        sensitive = tree.xpath('//meta[@name="rating"]/@content')
        sensitive = sensitive[0] == "adult" or sensitive[0] == "RTA-5042-1996-1400-1577-RTA" if sensitive else False
        sensitive = mixi_sensitive or sensitive
        
        fediverse_creator = tree.xpath('//meta[@name="fediverse:creator"]/@content')
        fediverse_creator = fediverse_creator[0] if fediverse_creator else None

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
            "fediverseCreator": fediverse_creator,
            "activitypub": activity_pub,
            "player": oembed,
            "sitename": site_name,
            "sensitive": sensitive,
            "url": url,
        }