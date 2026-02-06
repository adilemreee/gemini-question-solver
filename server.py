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

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Query
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
import database as db

# Initialize FastAPI app
app = FastAPI(
    title="Gemini Question Solver",
    description="Paralel soru çözme sistemi",
    version="2.0.0"
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
    stats = db.get_statistics()
    return {
        "status": "ok",
        "api_key_set": bool(GEMINI_API_KEY),
        "questions_dir": str(QUESTIONS_DIR),
        "timestamp": datetime.now().isoformat(),
        "stats": stats
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
        
        # Create database session
        db.create_session(session_id, source=session.get("source", "web"), total=session["total"])
        
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
            
            images.append((file_info["filename"], file_info["path"], image_bytes, mime_type))
        
        # Process each image
        results = []
        success_count = 0
        failed_count = 0
        
        for i, (filename, image_path, image_bytes, mime_type) in enumerate(images):
            result = await client.solve_question(image_bytes, mime_type, filename)
            results.append(result)
            
            # Save to database
            db.save_question(
                filename=filename,
                image_path=image_path,
                topic=result.get("topic", "Genel"),
                subtopic=result.get("subtopic"),
                status="success" if result["success"] else "failed",
                solution=result.get("solution"),
                error=result.get("error"),
                time_taken=result.get("time_taken"),
                session_id=session_id
            )
            
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
            
            # Update progress
            session["progress"] = i + 1
            session["results"] = results
        
        # Update session in database
        db.update_session(
            session_id,
            success=success_count,
            failed=failed_count,
            completed_at=datetime.now().isoformat()
        )
        
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


# ==================== Questions API ====================

@app.get("/api/questions")
async def list_questions(
    status: Optional[str] = Query(None, enum=["pending", "success", "failed"]),
    topic: Optional[str] = None,
    archived: Optional[bool] = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List all questions with optional filters"""
    questions = db.get_questions(
        status=status,
        topic=topic,
        archived=archived,
        limit=limit,
        offset=offset
    )
    return {
        "count": len(questions),
        "questions": questions
    }


@app.get("/api/questions/failed")
async def get_failed_questions():
    """Get all failed questions for retry"""
    questions = db.get_failed_questions()
    return {
        "count": len(questions),
        "questions": questions
    }


@app.get("/api/questions/{question_id}")
async def get_question(question_id: int):
    """Get single question by ID"""
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@app.post("/api/questions/{question_id}/retry")
async def retry_question(question_id: int):
    """Retry a failed question"""
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question["status"] != "failed":
        raise HTTPException(status_code=400, detail="Question is not in failed state")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    # Increment retry count
    retry_count = db.increment_retry(question_id)
    
    # Find image file
    image_path = Path(question.get("image_path", ""))
    if not image_path.exists():
        # Try questions folder
        image_path = QUESTIONS_DIR / question["filename"]
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    # Solve again
    client = GeminiClient()
    image_bytes = image_path.read_bytes()
    
    suffix = image_path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }
    mime_type = mime_types.get(suffix, "image/jpeg")
    
    result = await client.solve_question(image_bytes, mime_type, question["filename"])
    
    # Update in database
    db.update_question(
        question_id,
        status="success" if result["success"] else "failed",
        solution=result.get("solution"),
        error=result.get("error"),
        time_taken=result.get("time_taken"),
        topic=result.get("topic", "Genel"),
        subtopic=result.get("subtopic"),
        solved_at=datetime.now().isoformat() if result["success"] else None
    )
    
    return {
        "success": result["success"],
        "retry_count": retry_count,
        "result": result
    }


@app.post("/api/questions/retry-all-failed")
async def retry_all_failed():
    """Retry all failed questions"""
    failed = db.get_failed_questions()
    
    if not failed:
        return {"message": "No failed questions to retry", "count": 0}
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    # Create a session for batch retry
    session_id = str(uuid.uuid4())
    files = []
    
    for q in failed:
        image_path = Path(q.get("image_path", ""))
        if not image_path.exists():
            image_path = QUESTIONS_DIR / q["filename"]
        
        if image_path.exists():
            files.append({
                "filename": q["filename"],
                "path": str(image_path),
                "question_id": q["id"]
            })
    
    if not files:
        raise HTTPException(status_code=400, detail="No image files found for retry")
    
    active_sessions[session_id] = {
        "status": "processing",
        "files": files,
        "results": [],
        "progress": 0,
        "total": len(files),
        "source": "retry",
        "created_at": datetime.now().isoformat()
    }
    
    # Start processing
    asyncio.create_task(process_retry_session(session_id))
    
    return {
        "session_id": session_id,
        "count": len(files),
        "message": f"Retrying {len(files)} failed questions"
    }


async def process_retry_session(session_id: str):
    """Process retry session"""
    session = active_sessions[session_id]
    
    try:
        client = GeminiClient()
        results = []
        
        for i, file_info in enumerate(session["files"]):
            file_path = Path(file_info["path"])
            image_bytes = file_path.read_bytes()
            
            suffix = file_path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
            }
            mime_type = mime_types.get(suffix, "image/jpeg")
            
            result = await client.solve_question(image_bytes, mime_type, file_info["filename"])
            results.append(result)
            
            # Update database
            if "question_id" in file_info:
                db.update_question(
                    file_info["question_id"],
                    status="success" if result["success"] else "failed",
                    solution=result.get("solution"),
                    error=result.get("error"),
                    time_taken=result.get("time_taken"),
                    topic=result.get("topic", "Genel"),
                    retry_count=db.increment_retry(file_info["question_id"])
                )
            
            session["progress"] = i + 1
            session["results"] = results
        
        session["status"] = "completed"
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)


@app.post("/api/questions/archive")
async def archive_questions(
    question_ids: Optional[List[int]] = None,
    archive_successful: bool = False
):
    """Archive questions by IDs or all successful ones"""
    if question_ids:
        count = db.archive_questions(question_ids=question_ids)
    elif archive_successful:
        count = db.archive_questions(status="success")
    else:
        raise HTTPException(status_code=400, detail="Provide question_ids or set archive_successful=true")
    
    return {
        "message": f"Archived {count} questions",
        "count": count
    }


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics"""
    return db.get_statistics()


@app.get("/api/topics")
async def get_topics():
    """Get all available topics"""
    return db.get_topics()


# Mount static files for web assets
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
