"""
Web Server for Gemini Parallel Question Solver
FastAPI-based web interface with real-time progress updates
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import GEMINI_API_KEY, OUTPUT_DIR, QUESTIONS_DIR
from src.gemini_client import GeminiClient
from src.parallel_processor import ParallelProcessor
from src.report_generator import ReportGenerator

# Initialize FastAPI app
app = FastAPI(
    title="Gemini Question Solver",
    description="Paralel soru çözme sistemi",
    version="1.0.0"
)

# Create directories
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Store active sessions
active_sessions = {}


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web interface"""
    html_path = Path(__file__).parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/status")
async def api_status():
    """Check API status"""
    return {
        "status": "ok",
        "api_key_set": bool(GEMINI_API_KEY),
        "questions_dir": str(QUESTIONS_DIR),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/scan-folder")
async def scan_folder():
    """Scan questions folder for images"""
    QUESTIONS_DIR.mkdir(exist_ok=True)
    
    supported_formats = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    found_files = []
    
    for file_path in sorted(QUESTIONS_DIR.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in supported_formats:
            found_files.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "path": str(file_path),
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
    
    return {
        "folder": str(QUESTIONS_DIR),
        "file_count": len(found_files),
        "files": found_files
    }


@app.post("/api/solve-folder")
async def solve_folder():
    """Create session from questions folder and start solving"""
    QUESTIONS_DIR.mkdir(exist_ok=True)
    
    supported_formats = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    found_files = []
    
    for file_path in sorted(QUESTIONS_DIR.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in supported_formats:
            found_files.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "path": str(file_path)
            })
    
    if not found_files:
        raise HTTPException(status_code=400, detail="No images found in questions folder")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    # Create session
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "status": "processing",
        "files": found_files,
        "results": [],
        "progress": 0,
        "total": len(found_files),
        "source": "folder",
        "created_at": datetime.now().isoformat()
    }
    
    # Start processing
    asyncio.create_task(process_session(session_id))
    
    return {
        "session_id": session_id,
        "file_count": len(found_files),
        "files": found_files
    }


@app.get("/api/image/{filename}")
async def get_image(filename: str):
    """Serve image from questions folder"""
    file_path = QUESTIONS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Determine content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    content_type = content_types.get(suffix, "image/jpeg")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type=content_type)


@app.get("/api/outputs")
async def list_outputs():
    """List all output reports"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    reports = []
    for file_path in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        if file_path.is_file() and file_path.suffix.lower() == ".md":
            reports.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                "path": str(file_path)
            })
    
    return {
        "folder": str(OUTPUT_DIR),
        "count": len(reports),
        "reports": reports
    }


@app.get("/api/report/{filename}")
async def get_report(filename: str):
    """Get report content as markdown"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    content = file_path.read_text(encoding="utf-8")
    return {
        "filename": filename,
        "content": content,
        "size": file_path.stat().st_size,
        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
    }


@app.get("/api/report/{filename}/raw")
async def get_report_raw(filename: str):
    """Get raw report file"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type="text/markdown", filename=filename)


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload question images"""
    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    
    uploaded_files = []
    for file in files:
        # Validate file type
        if not file.content_type.startswith("image/"):
            continue
        
        # Save file
        file_path = session_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
        
        uploaded_files.append({
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path)
        })
    
    if not uploaded_files:
        raise HTTPException(status_code=400, detail="No valid image files uploaded")
    
    # Store session info
    active_sessions[session_id] = {
        "status": "uploaded",
        "files": uploaded_files,
        "results": [],
        "progress": 0,
        "total": len(uploaded_files),
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "session_id": session_id,
        "file_count": len(uploaded_files),
        "files": uploaded_files
    }


@app.post("/api/solve/{session_id}")
async def solve_questions(session_id: str):
    """Start solving questions for a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    # Update status
    session["status"] = "processing"
    
    # Start processing in background
    asyncio.create_task(process_session(session_id))
    
    return {"status": "started", "session_id": session_id}


async def process_session(session_id: str):
    """Background task to process all questions"""
    session = active_sessions[session_id]
    
    try:
        client = GeminiClient()
        
        # Load images
        images = []
        for file_info in session["files"]:
            file_path = Path(file_info["path"])
            image_bytes = file_path.read_bytes()
            
            # Determine mime type
            suffix = file_path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(suffix, "image/jpeg")
            
            images.append((file_info["filename"], image_bytes, mime_type))
        
        # Process each image
        results = []
        for i, (filename, image_bytes, mime_type) in enumerate(images):
            result = await client.solve_question(image_bytes, mime_type, filename)
            results.append(result)
            
            # Update progress
            session["progress"] = i + 1
            session["results"] = results
        
        # Generate report
        generator = ReportGenerator()
        session_dir = UPLOAD_DIR / session_id
        report_path = generator.generate(results, session_dir, f"rapor_{session_id[:8]}.md")
        
        session["status"] = "completed"
        session["report_path"] = str(report_path)
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)


@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str):
    """Get processing progress for a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    return {
        "status": session["status"],
        "progress": session["progress"],
        "total": session["total"],
        "results": session.get("results", []),
        "error": session.get("error"),
        "report_path": session.get("report_path")
    }


@app.get("/api/results/{session_id}")
async def get_results(session_id: str):
    """Get final results for a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    return {
        "status": session["status"],
        "results": session.get("results", []),
        "report_path": session.get("report_path")
    }


# Mount static files for web assets
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
