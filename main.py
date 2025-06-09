# main.py
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Allow CORS for all origins (you can restrict to specific domains if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "YouTube Proxy is Live"}

@app.get("/proxy")
async def proxy_media(url: str, filename: str = "media", ext: str = "mp4", range: str = None):
    """
    Proxy media from a remote URL, allowing range requests and proper download support.
    Example usage: /proxy?url=https://example.com/video.mp4&filename=video&ext=mp4
    """
    headers = {"Range": range} if range else {}

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        try:
            response = await client.get(url, headers=headers, stream=True)
            return StreamingResponse(
                response.aiter_bytes(),
                status_code=response.status_code,
                headers={
                    "Content-Type": response.headers.get("Content-Type", "application/octet-stream"),
                    "Content-Length": response.headers.get("Content-Length", ""),
                    "Content-Range": response.headers.get("Content-Range", ""),
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": f'attachment; filename="{filename}.{ext}"',
                }
            )
        except Exception as e:
            return Response(f"Error proxying file: {str(e)}", status_code=500)
          
