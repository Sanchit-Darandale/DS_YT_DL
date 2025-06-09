from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
import httpx, os, uuid
from fastapi import FastAPI, Query, HTTPException, Request
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
# Proxy endpoint to stream or download from public API
@app.get("/proxy")
async def proxy_download(
    url: str = Query(..., description="YouTube URL"),
    format: str = Query("mp3", description="Format: mp3, 480, 720, 1080"),
    filename: str = Query("media", description="Optional filename (without extension)")
):
    api_url = f"https://gpt76.vercel.app/download?url={url}&format={format}"
    ext = "mp3" if format == "mp3" else "mp4"
    file_name = f"{filename}.{ext}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(api_url, timeout=60.0)
            if resp.status_code != 200:
                return JSONResponse(content={"error": "Failed to fetch video"}, status_code=400)

            headers = {
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Content-Type": "audio/mpeg" if ext == "mp3" else "video/mp4",
            }

            return StreamingResponse(resp.aiter_bytes(), headers=headers)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
