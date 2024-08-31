from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional
import traceback

from fastapi import FastAPI, HTTPException, Query

from fastapi.responses import ORJSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel
from pysummaly import extract_metadata


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    yield


app = FastAPI(lifespan=lifespan)


class GeneralScrapingOptions(BaseModel):
    lang: Optional[str] = None
    userAgent: Optional[str] = None
    responseTimeout: Optional[int] = None
    operationTimeout: Optional[int] = None
    contentLengthLimit: Optional[int] = None
    contentLengthRequired: Optional[bool] = None


@app.get("/")
@app.get("/url")
@cache(expire=600)
async def extract_metadata_endpoint(
    url: str,
    lang: Optional[str] = Query(None),
    userAgent: Optional[str] = Query(None),
    responseTimeout: Optional[int] = Query(None),
    operationTimeout: Optional[int] = Query(None),
    contentLengthLimit: Optional[int] = Query(None),
    contentLengthRequired: Optional[bool] = Query(None),
):
    responseTimeout = int(responseTimeout) if responseTimeout is not None else None
    operationTimeout = int(operationTimeout) if operationTimeout is not None else None
    contentLengthLimit = (
        int(contentLengthLimit) if contentLengthLimit is not None else None
    )

    opts = GeneralScrapingOptions(
        lang=lang,
        userAgent=userAgent,
        responseTimeout=responseTimeout,
        operationTimeout=operationTimeout,
        contentLengthLimit=contentLengthLimit,
        contentLengthRequired=contentLengthRequired,
    )

    try:
        metadata = await extract_metadata(url, opts.model_dump() if opts else {})
        if metadata is None:
            raise HTTPException(status_code=404, detail="Metadata not found")
        return ORJSONResponse(
            metadata, headers={"Cache-Control": "max-age=600, public"}
        )
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))