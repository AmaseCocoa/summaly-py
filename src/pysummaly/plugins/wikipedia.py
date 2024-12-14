import re

import aiohttp
import yarl

def clip(text: str, length: int) -> str:
    if len(text) > length:
        return text[:length] + "..."
    else:
        return text

async def test(url: yarl.URL) -> bool:
    if not url.host:
        return False
    m = True if re.match(r"[a-zA-Z]{2}\.wikipedia\.org$", url.host) else False
    return m

async def summarize(url: yarl.URL, session: aiohttp.ClientSession):
    try:
        lang = url.host.split(".")[0]
    except IndexError:
        lang = None
    try:
        title = url.path.split("/")[2]
    except IndexError:
        title = None
    endpoint = f"https://{lang}.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro=&explaintext=&titles={title}"
    
    print(f'lang is {lang}')
    print(f'title is {title}')
    print(f'endpoint is {endpoint}')
    async with session.get(endpoint) as resp:
        body = await resp.json()
        if 'query' not in body or 'pages' not in body['query']:
            raise Exception("fetch failed")
        info = body['query']['pages'][list(body['query']['pages'].keys())[0]]
        return {
            'title': info['title'],
            'icon': 'https://wikipedia.org/static/favicon/wikipedia.ico',
            'description': clip(info['extract'], 300),
            'thumbnail': f'https://wikipedia.org/static/images/project-logos/{lang}wiki.png',
            'player': {
                'url': None,
                'width': None,
                'height': None,
                'allow': [],
            },
            'sitename': 'Wikipedia',
            'fediverseCreator': None,
            'activityPub': None,
        }