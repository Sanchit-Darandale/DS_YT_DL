from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
import httpx, os, uuid
from fastapi import FastAPI, Query, HTTPException 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/meta")
async def get_meta(url: str):
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://gpt76.vercel.app/download", params={"url": url})
        return r.json()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

API_URL = "https://gpt76.vercel.app/download"

MIME_TYPES = {
    "mp3": "audio/mpeg",
    "480": "video/mp4",
    "720": "video/mp4",
    "1080": "video/mp4",
}

@app.get("/proxy")
async def stream_media(
    url: str = Query(..., description="YouTube video URL"),
    ext: str = Query("mp3", description="Format: mp3, 480, 720, 1080"),
    filename: str = Query("media", description="Filename without extension"),
):
    ext = ext.lower()
    if ext not in MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported format")

    async with httpx.AsyncClient() as client:
        res = await client.get(API_URL, params={"url": url})
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch data from public API")

        data = res.json()
        stream_url = data.get(ext if ext != "mp3" else "audio")

        if not stream_url:
            raise HTTPException(status_code=404, detail=f"{ext.upper()} format not available")

        # Proxy stream
        stream_response = await client.get(stream_url)
        if stream_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch stream")

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.{ext}"'
    }

    return StreamingResponse(
        iter([stream_response.content]),
        media_type=MIME_TYPES[ext],
        headers=headers
    )
