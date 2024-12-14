from typing import Coroutine, Any

import aiohttp
import yarl
from lxml import html

from . import skeb, branchio, wikipedia


async def check(
    session: aiohttp.ClientSession,
    url: str,
    timeout,
    content_length_limit,
    content_length_required,
) -> Coroutine[Any, Any, dict] | None:
    url_parsed: yarl.URL = yarl.URL(url)
    args = {
        "session": session,
        "url": url,
        "timeout": timeout,
        "content_length_limit": content_length_limit,
        "content_length_required": content_length_required,
    }
    if await skeb.test(url_parsed):
        return html.fromstring(await skeb.fetch(**args))
    elif await branchio.test(url_parsed):
        return html.fromstring(await branchio.fetch(**args))
    elif await wikipedia.test(url_parsed):
        return await wikipedia.summarize(url_parsed, session)
    return None