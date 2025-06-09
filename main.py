from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

app = FastAPI()

@app.get("/meta")
async def get_meta(url: str):
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://gpt76.vercel.app/download", params={"url": url})
        return r.json()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/proxy")
async def proxy(url: str, filename: str = "media", ext: str = "mp4"):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        client = httpx.AsyncClient(headers=headers, timeout=60)
        response = await client.get(url, follow_redirects=True)
        await client.aclose()

        if response.status_code != 200:
            return JSONResponse(content={"error": "Failed to fetch media"}, status_code=400)

        return StreamingResponse(
            iter([response.content]),
            media_type="video/mp4" if ext == "mp4" else "audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"'}
        )
    except Exception as e:
        return JSONResponse(content={"error": f"Proxy failed: {str(e)}"}, status_code=500)
