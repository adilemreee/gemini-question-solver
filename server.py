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
from pydantic import BaseModel

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Query, Body, WebSocket, WebSocketDisconnect
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

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}  # session_id -> [ws]

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id] = [
                c for c in self.active_connections[session_id] if c != ws
            ]
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            dead = []
            for ws in self.active_connections[session_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(session_id, ws)

ws_manager = ConnectionManager()

# Rate limit tracking
class RateLimitTracker:
    def __init__(self):
        self.requests: list[dict] = []  # [{timestamp, model, tokens_in, tokens_out, duration}]
        self._lock = asyncio.Lock()

    async def record(self, model: str, duration: float, tokens_in: int = 0, tokens_out: int = 0):
        async with self._lock:
            self.requests.append({
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "duration": duration,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            })
            # Keep only last 1000 records
            if len(self.requests) > 1000:
                self.requests = self.requests[-1000:]

    def get_stats(self) -> dict:
        now = datetime.now()
        last_min = [r for r in self.requests if (now - datetime.fromisoformat(r["timestamp"])).total_seconds() < 60]
        last_hour = [r for r in self.requests if (now - datetime.fromisoformat(r["timestamp"])).total_seconds() < 3600]
        last_day = [r for r in self.requests if (now - datetime.fromisoformat(r["timestamp"])).total_seconds() < 86400]

        def _summary(entries):
            if not entries:
                return {"count": 0, "avg_duration": 0, "total_tokens_in": 0, "total_tokens_out": 0}
            return {
                "count": len(entries),
                "avg_duration": round(sum(e["duration"] for e in entries) / len(entries), 2),
                "total_tokens_in": sum(e["tokens_in"] for e in entries),
                "total_tokens_out": sum(e["tokens_out"] for e in entries),
            }

        return {
            "last_minute": _summary(last_min),
            "last_hour": _summary(last_hour),
            "last_day": _summary(last_day),
            "total_all_time": len(self.requests),
            "recent_requests": self.requests[-20:][::-1],
        }

rate_tracker = RateLimitTracker()


def move_to_topic_folder(image_path: str, topic: str) -> str:
    """Move solved question to topic folder and return new path"""
    source = Path(image_path)
    if not source.exists():
        return image_path
    
    # Create topic folder
    topic_folder = QUESTIONS_DIR / topic
    topic_folder.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename if exists
    dest = topic_folder / source.name
    counter = 1
    while dest.exists():
        stem = source.stem
        suffix = source.suffix
        dest = topic_folder / f"{stem}_{counter}{suffix}"
        counter += 1
    
    # Move file
    try:
        import shutil
        shutil.move(str(source), str(dest))
        return str(dest)
    except Exception:
        return image_path


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web interface (React build or legacy)"""
    # Try React build first
    react_index = Path(__file__).parent / "frontend" / "dist" / "index.html"
    if react_index.exists():
        return react_index.read_text(encoding="utf-8")
    # Fallback to legacy
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


class SelectedFilesRequest(BaseModel):
    filenames: List[str]


@app.post("/api/solve-selected")
async def solve_selected(request: SelectedFilesRequest):
    """Create session from selected files in questions folder and start solving"""
    QUESTIONS_DIR.mkdir(exist_ok=True)
    
    if not request.filenames:
        raise HTTPException(status_code=400, detail="No files selected")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    supported_formats = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    found_files = []
    
    for filename in request.filenames:
        file_path = QUESTIONS_DIR / filename
        if file_path.exists() and file_path.is_file() and file_path.suffix.lower() in supported_formats:
            found_files.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "path": str(file_path)
            })
    
    if not found_files:
        raise HTTPException(status_code=400, detail="No valid images found in selection")
    
    # Create session
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "status": "processing",
        "files": found_files,
        "results": [],
        "progress": 0,
        "total": len(found_files),
        "source": "folder_selected",
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
async def get_image(filename: str, topic: str = None):
    """Serve image from questions folder or topic subfolders"""
    file_path = None
    
    # First check if topic is specified
    if topic:
        topic_path = QUESTIONS_DIR / topic / filename
        if topic_path.exists():
            file_path = topic_path
    
    # Check root folder
    if not file_path:
        root_path = QUESTIONS_DIR / filename
        if root_path.exists():
            file_path = root_path
    
    # Search in all topic subfolders
    if not file_path:
        for subfolder in QUESTIONS_DIR.iterdir():
            if subfolder.is_dir():
                sub_path = subfolder / filename
                if sub_path.exists():
                    file_path = sub_path
                    break
    
    if not file_path:
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


@app.get("/api/topic-folders")
async def list_topic_folders():
    """List all topic folders with file counts"""
    QUESTIONS_DIR.mkdir(exist_ok=True)
    
    folders = []
    
    # Count files in root (unorganized)
    root_files = [f for f in QUESTIONS_DIR.iterdir() 
                  if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
    
    if root_files:
        folders.append({
            "name": "Yeni Sorular",
            "path": str(QUESTIONS_DIR),
            "count": len(root_files),
            "is_root": True
        })
    
    # List topic folders
    for folder in sorted(QUESTIONS_DIR.iterdir()):
        if folder.is_dir() and not folder.name.startswith('.'):
            files = [f for f in folder.iterdir() 
                    if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
            folders.append({
                "name": folder.name,
                "path": str(folder),
                "count": len(files),
                "is_root": False
            })
    
    return {
        "base_folder": str(QUESTIONS_DIR),
        "folders": folders,
        "total_folders": len(folders)
    }


@app.get("/api/topic-folder/{topic}")
async def get_topic_folder_files(topic: str):
    """Get files in a specific topic folder"""
    if topic == "Yeni Sorular":
        folder_path = QUESTIONS_DIR
        files = [f for f in folder_path.iterdir() 
                if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
    else:
        folder_path = QUESTIONS_DIR / topic
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="Topic folder not found")
        files = [f for f in folder_path.iterdir() 
                if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
    
    return {
        "topic": topic,
        "path": str(folder_path),
        "count": len(files),
        "files": [
            {
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            }
            for f in sorted(files)
        ]
    }


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


@app.delete("/api/report/{filename}")
async def delete_report(filename: str):
    """Delete a report file"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    file_path.unlink()
    return {"success": True, "filename": filename}


@app.get("/api/report/{filename}/pdf")
async def get_report_pdf(filename: str):
    """Export report as PDF with cover page, TOC, and page numbers"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        import markdown
        from weasyprint import HTML, CSS
        from io import BytesIO
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="PDF export dependencies not installed. Run: pip install markdown weasyprint"
        )
    
    # Read markdown content
    md_content = file_path.read_text(encoding="utf-8")
    
    # Pre-process LaTeX expressions → MathML for PDF rendering
    import re as _re2
    try:
        import latex2mathml.converter as l2m
        
        def _latex_to_mathml(md_text: str) -> str:
            """Convert LaTeX math expressions to MathML so WeasyPrint can render them."""
            # Display math: $$...$$ and \[...\]
            def _convert_display(m):
                latex = m.group(1).strip()
                try:
                    mathml = l2m.convert(latex)
                    # Force display mode
                    mathml = mathml.replace('display="inline"', 'display="block"')
                    return f'<div class="math-block">{mathml}</div>'
                except Exception:
                    return m.group(0)
            
            # Inline math: $...$ and \(...\)
            def _convert_inline(m):
                latex = m.group(1).strip()
                try:
                    mathml = l2m.convert(latex)
                    return f'<span class="math-inline">{mathml}</span>'
                except Exception:
                    return m.group(0)
            
            # Order matters: process $$ before $
            md_text = _re2.sub(r'\$\$(.+?)\$\$', _convert_display, md_text, flags=_re2.DOTALL)
            md_text = _re2.sub(r'\\\[(.+?)\\\]', _convert_display, md_text, flags=_re2.DOTALL)
            md_text = _re2.sub(r'\\\((.+?)\\\)', _convert_inline, md_text, flags=_re2.DOTALL)
            # Single $ inline – avoid matching currency like $5
            md_text = _re2.sub(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', _convert_inline, md_text, flags=_re2.DOTALL)
            return md_text
        
        md_content = _latex_to_mathml(md_content)
    except ImportError:
        pass  # latex2mathml not installed, skip conversion
    
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
    html_body = md.convert(md_content)
    
    # Extract stats from content for cover page
    import re as _re
    total_match = _re.search(r'\*\*Toplam Soru\*\*\s*\|\s*(\d+)', md_content)
    success_match = _re.search(r'\*\*Başarılı\*\*\s*\|\s*(\d+)', md_content)
    rate_match = _re.search(r'\*\*Başarı Oranı\*\*\s*\|\s*([\d.]+)%', md_content)
    date_match = _re.search(r'\*\*Oluşturulma Tarihi\*\*:\s*(.+)', md_content)
    
    total_q = total_match.group(1) if total_match else "?"
    success_q = success_match.group(1) if success_match else "?"
    rate_q = rate_match.group(1) if rate_match else "?"
    report_date = date_match.group(1).strip() if date_match else datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Full HTML with cover page, TOC, and enhanced styling
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
            
            @page {{
                size: A4;
                margin: 2.5cm 2cm;
                @bottom-center {{
                    content: counter(page) " / " counter(pages);
                    font-family: 'Inter', sans-serif;
                    font-size: 10px;
                    color: #9ca3af;
                }}
                @top-right {{
                    content: "Gemini Question Solver";
                    font-family: 'Inter', sans-serif;
                    font-size: 9px;
                    color: #c7d2fe;
                }}
            }}
            
            @page :first {{
                margin: 0;
                @bottom-center {{ content: none; }}
                @top-right {{ content: none; }}
            }}
            
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                line-height: 1.8;
                color: #1a1a2e;
                background: #ffffff;
                margin: 0;
                padding: 0;
            }}
            
            /* Cover Page */
            .cover-page {{
                page-break-after: always;
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 60px;
            }}
            
            .cover-logo {{
                font-size: 72px;
                margin-bottom: 40px;
            }}
            
            .cover-title {{
                font-size: 36px;
                font-weight: 800;
                margin-bottom: 12px;
                letter-spacing: -0.5px;
            }}
            
            .cover-subtitle {{
                font-size: 18px;
                font-weight: 300;
                opacity: 0.9;
                margin-bottom: 60px;
            }}
            
            .cover-stats {{
                display: flex;
                gap: 40px;
                margin-bottom: 60px;
            }}
            
            .cover-stat {{
                text-align: center;
            }}
            
            .cover-stat-value {{
                font-size: 42px;
                font-weight: 700;
                display: block;
            }}
            
            .cover-stat-label {{
                font-size: 13px;
                opacity: 0.8;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            
            .cover-date {{
                font-size: 14px;
                opacity: 0.7;
                margin-top: auto;
            }}
            
            /* TOC */
            .toc-page {{
                page-break-after: always;
                padding: 40px;
            }}
            
            .toc-title {{
                font-size: 24px;
                font-weight: 700;
                color: #6366f1;
                margin-bottom: 24px;
                border-bottom: 3px solid #6366f1;
                padding-bottom: 12px;
            }}
            
            .toc-item {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px dotted #e5e7eb;
                font-size: 14px;
            }}
            
            .toc-item-title {{
                color: #374151;
            }}
            
            /* Content */
            .content {{
                padding: 0 20px;
            }}
            
            h1 {{
                font-size: 28px;
                color: #6366f1;
                border-bottom: 3px solid #6366f1;
                padding-bottom: 12px;
                margin-bottom: 24px;
                page-break-after: avoid;
            }}
            
            h2 {{
                font-size: 22px;
                color: #4f46e5;
                margin-top: 32px;
                border-left: 4px solid #6366f1;
                padding-left: 12px;
                page-break-after: avoid;
            }}
            
            h3 {{
                font-size: 18px;
                color: #4338ca;
                margin-top: 24px;
                page-break-after: avoid;
            }}
            
            p {{
                margin-bottom: 16px;
                text-align: justify;
            }}
            
            code {{
                background: #f3f4f6;
                padding: 2px 8px;
                border-radius: 4px;
                font-family: 'Monaco', 'Consolas', monospace;
                font-size: 14px;
            }}
            
            pre {{
                background: #1e1e2e;
                color: #cdd6f4;
                padding: 20px;
                border-radius: 8px;
                overflow-x: auto;
                font-size: 13px;
                page-break-inside: avoid;
            }}
            
            pre code {{
                background: transparent;
                padding: 0;
                color: inherit;
            }}
            
            strong {{
                color: #6366f1;
            }}
            
            ul, ol {{
                margin-left: 24px;
                margin-bottom: 16px;
            }}
            
            li {{
                margin-bottom: 8px;
            }}
            
            hr {{
                border: none;
                border-top: 2px solid #e5e7eb;
                margin: 32px 0;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                page-break-inside: avoid;
            }}
            
            th, td {{
                border: 1px solid #e5e7eb;
                padding: 12px;
                text-align: left;
            }}
            
            th {{
                background: #f3f4f6;
                font-weight: 600;
            }}
            
            .math-block {{
                background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                padding: 16px 20px;
                border-radius: 8px;
                border-left: 4px solid #6366f1;
                margin: 16px 0;
                overflow-x: auto;
                text-align: center;
            }}
            
            .math-inline {{
                display: inline;
                vertical-align: middle;
            }}
            
            math {{
                font-family: 'Times New Roman', 'Cambria Math', serif;
                font-size: 1.1em;
            }}
            
            .math-block math {{
                font-size: 1.3em;
            }}
            
            .solution-section {{
                background: #fafafa;
                padding: 20px;
                border-radius: 12px;
                margin: 16px 0;
                border: 1px solid #e5e7eb;
                page-break-inside: avoid;
            }}
            
            .footer {{
                margin-top: 48px;
                padding-top: 16px;
                border-top: 1px solid #e5e7eb;
                text-align: center;
                color: #9ca3af;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <!-- Cover Page -->
        <div class="cover-page">
            <div class="cover-logo">🧠</div>
            <div class="cover-title">Soru Çözüm Raporu</div>
            <div class="cover-subtitle">Gemini Question Solver ile oluşturuldu</div>
            <div class="cover-stats">
                <div class="cover-stat">
                    <span class="cover-stat-value">{total_q}</span>
                    <span class="cover-stat-label">Toplam Soru</span>
                </div>
                <div class="cover-stat">
                    <span class="cover-stat-value">{success_q}</span>
                    <span class="cover-stat-label">Başarılı</span>
                </div>
                <div class="cover-stat">
                    <span class="cover-stat-value">%{rate_q}</span>
                    <span class="cover-stat-label">Başarı Oranı</span>
                </div>
            </div>
            <div class="cover-date">{report_date}</div>
        </div>
        
        <!-- Content -->
        <div class="content">
            {html_body}
        </div>
        
        <div class="footer">
            Gemini Question Solver ile otomatik oluşturuldu &bull; {report_date}
        </div>
    </body>
    </html>
    '''
    
    # Generate PDF
    pdf_buffer = BytesIO()
    HTML(string=html_template).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    pdf_filename = filename.replace('.md', '.pdf')
    
    from fastapi.responses import Response
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={pdf_filename}"
        }
    )

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
    """Background task to process all questions in parallel"""
    session = active_sessions[session_id]
    
    try:
        from config import MAX_CONCURRENT_REQUESTS
        
        client = GeminiClient()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
        # Create database session
        db.create_session(session_id, source=session.get("source", "web"), total=session["total"], files=session["files"])
        
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
        
        # Process images in parallel
        results = []
        success_count = 0
        failed_count = 0
        completed_count = 0
        
        async def solve_single(idx: int, filename: str, image_path: str, image_bytes: bytes, mime_type: str):
            """Solve a single question with semaphore control"""
            nonlocal completed_count, success_count, failed_count
            
            async with semaphore:
                result = await client.solve_question(image_bytes, mime_type, filename)
                result["_idx"] = idx
                result["_image_path"] = image_path
                
                completed_count += 1
                if result["success"]:
                    success_count += 1
                else:
                    failed_count += 1
                
                # Track rate limit
                await rate_tracker.record(
                    model=client.model_name,
                    duration=result.get("time_taken", 0),
                )
                
                # Update progress
                session["progress"] = completed_count
                
                # Broadcast via WebSocket
                await ws_manager.broadcast(session_id, {
                    "type": "progress",
                    "progress": completed_count,
                    "total": session["total"],
                    "status": "processing",
                    "latest_result": {
                        "filename": result["filename"],
                        "success": result["success"],
                        "topic": result.get("topic"),
                        "time_taken": result.get("time_taken"),
                    }
                })
                
                return result
        
        # Create tasks for all images
        tasks = [
            solve_single(i, filename, image_path, image_bytes, mime_type)
            for i, (filename, image_path, image_bytes, mime_type) in enumerate(images)
        ]
        
        # Run all tasks concurrently
        parallel_results = await asyncio.gather(*tasks)
        
        # Sort results by original index to maintain order
        parallel_results.sort(key=lambda r: r["_idx"])
        
        # Post-process results (save to DB, move files)
        for result in parallel_results:
            image_path = result.pop("_image_path")
            result.pop("_idx")
            
            topic = result.get("topic", "Genel")
            new_image_path = image_path
            
            # Move successful questions to topic folder (only for folder source)
            if result["success"] and session.get("source") in ["folder", "folder_selected"]:
                new_image_path = move_to_topic_folder(image_path, topic)
            
            # Save to database
            db.save_question(
                filename=result["filename"],
                image_path=new_image_path,
                topic=topic,
                subtopic=result.get("subtopic"),
                status="success" if result["success"] else "failed",
                solution=result.get("solution"),
                error=result.get("error"),
                time_taken=result.get("time_taken"),
                session_id=session_id
            )
            
            results.append(result)
        
        session["results"] = results
        
        # Update session in database
        db.update_session(
            session_id,
            success=success_count,
            failed=failed_count,
            completed_at=datetime.now().isoformat()
        )
        
        # Generate report with descriptive name
        generator = ReportGenerator()
        session_dir = UPLOAD_DIR / session_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_name = f"Cozum_{timestamp}_{len(results)}soru.md"
        report_path = generator.generate(results, session_dir, report_name)
        
        session["status"] = "completed"
        session["report_path"] = str(report_path)
        
        # Persist to database
        db.save_session_state(session_id, session)
        
        # Broadcast completion via WebSocket
        await ws_manager.broadcast(session_id, {
            "type": "completed",
            "status": "completed",
            "progress": session["total"],
            "total": session["total"],
            "results": results,
            "report_path": str(report_path),
        })
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        
        # Persist error state
        db.save_session_state(session_id, session)
        
        # Broadcast error via WebSocket
        await ws_manager.broadcast(session_id, {
            "type": "error",
            "status": "error",
            "error": str(e),
        })


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


# ==================== WebSocket ====================

@app.websocket("/ws/progress/{session_id}")
async def ws_progress(ws: WebSocket, session_id: str):
    """WebSocket endpoint for real-time progress updates"""
    await ws_manager.connect(session_id, ws)
    try:
        # Send current state immediately
        if session_id in active_sessions:
            session = active_sessions[session_id]
            await ws.send_json({
                "type": "init",
                "status": session["status"],
                "progress": session["progress"],
                "total": session["total"],
            })
        # Keep connection alive
        while True:
            data = await ws.receive_text()
            # Client can send "ping" to keep alive
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, ws)
    except Exception:
        ws_manager.disconnect(session_id, ws)


# ==================== Rate Limit Dashboard ====================

@app.get("/api/rate-limit")
async def get_rate_limit():
    """Get API rate limit stats"""
    return rate_tracker.get_stats()


# ==================== AI Features ====================

@app.post("/api/questions/{question_id}/explain")
async def explain_question(question_id: int, body: dict = Body(...)):
    """Re-explain a solution step more simply (Bunu anlamadım)"""
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if not question.get("solution"):
        raise HTTPException(status_code=400, detail="No solution to explain")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    selected_text = body.get("selected_text", "")
    
    explain_prompt = f"""Aşağıda bir matematik/fen sorusunun çözümü var. Öğrenci çözümün bir kısmını anlamadı.

--- ORIJINAL ÇÖZÜM ---
{question['solution']}

--- ANLAŞILMAYAN KISIM ---
{selected_text if selected_text else "Tüm çözüm"}

Lütfen bu kısmı çok daha basit ve anlaşılır şekilde açıkla:
1. Günlük hayattan benzetmeler kullan
2. Adım adım, yavaş yavaş anlat
3. Gerekiyorsa görsel temsiller (ASCII art) kullan
4. Neden bu adımı yaptığımızı açıkla
5. Türkçe açıklama yap
6. Matematiksel ifadeleri açık şekilde yaz"""

    try:
        client = GeminiClient()
        
        # If question has an image, include it
        image_path = Path(question.get("image_path", ""))
        contents = [explain_prompt]
        
        if image_path.exists():
            from google.genai import types
            image_bytes = image_path.read_bytes()
            suffix = image_path.suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_map.get(suffix, "image/jpeg"))
            contents.append(image_part)
        
        import time as _time
        start = _time.time()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.client.models.generate_content,
                model=client.model_name,
                contents=contents
            ),
            timeout=120
        )
        duration = _time.time() - start
        await rate_tracker.record(model=client.model_name, duration=duration)
        
        return {
            "success": True,
            "explanation": response.text,
            "time_taken": duration,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/questions/{question_id}/hints")
async def get_hints(question_id: int, body: dict = Body({})):
    """Get progressive hints for a question (İpucu modu)"""
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    hint_level = body.get("level", 1)  # 1=subtle, 2=moderate, 3=detailed
    
    hint_prompts = {
        1: """Bu soruyu analiz et ama ÇÖZME. Sadece şu bilgileri ver:
- Sorunun hangi konuya ait olduğunu belirt
- Hangi formül veya kavramın kullanılacağına dair küçük bir ipucu ver
- Çözümün ilk adımını sadece kelimelerle tarif et (hesaplama yapma)
Türkçe yaz.""",
        2: """Bu soruyu analiz et ve ORTA SEVİYE ipucu ver:
- Kullanılacak formülleri yaz
- Çözümün ana adımlarını listele (ama hesaplama yapma)
- Hangi değerlerin birbirine eşitlenmesi gerektiğini belirt
- Sonucu söyleme!
Türkçe yaz.""",
        3: """Bu soruyu analiz et ve DETAYLI ipucu ver:
- Kullanılacak formülleri yaz
- Çözümün adımlarını detaylı açıkla
- Sayısal değerlerin yerine koyulmasını göster
- Ama SON CEVABI yine de söyleme, öğrenci kendisi bulsun
Türkçe yaz.""",
    }
    
    prompt = hint_prompts.get(hint_level, hint_prompts[1])
    
    try:
        client = GeminiClient()
        
        image_path = Path(question.get("image_path", ""))
        if not image_path.exists():
            image_path = QUESTIONS_DIR / question["filename"]
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")
        
        from google.genai import types
        image_bytes = image_path.read_bytes()
        suffix = image_path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_map.get(suffix, "image/jpeg"))
        
        import time as _time
        start = _time.time()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.client.models.generate_content,
                model=client.model_name,
                contents=[prompt, image_part]
            ),
            timeout=120
        )
        duration = _time.time() - start
        await rate_tracker.record(model=client.model_name, duration=duration)
        
        return {
            "success": True,
            "hint": response.text,
            "level": hint_level,
            "time_taken": duration,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/topics/{topic}/summary")
async def get_topic_summary(topic: str):
    """Generate a topic summary with key formulas (Konu özeti) and save to DB"""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
    
    # Get recent successful questions for this topic
    questions = db.get_questions(topic=topic, status="success", limit=20, archived=False)
    if not questions:
        # Also check archived
        questions = db.get_questions(topic=topic, status="success", limit=20)
    
    if not questions:
        raise HTTPException(status_code=404, detail=f"No solved questions found for topic: {topic}")
    
    # Collect solutions
    solutions = [q["solution"] for q in questions if q.get("solution")][:10]
    solutions_text = "\n\n---\n\n".join(solutions)
    
    summary_prompt = f"""Aşağıda "{topic}" konusunda çözülmüş sorular var. Bu çözümlerden yola çıkarak kapsamlı bir KONU ÖZETİ oluştur.

--- ÇÖZÜLMÜŞ SORULAR ---
{solutions_text}

Lütfen şu formatta bir özet oluştur:

## 📚 {topic} - Konu Özeti

### 📌 Temel Kavramlar
- Konunun ana kavramlarını listele

### 📐 Formüller ve Kurallar
- Tüm önemli formülleri yaz (LaTeX formatında)
- Her formülün ne zaman kullanıldığını açıkla

### 💡 Çözüm Stratejileri
- Bu konuda soru çözerken dikkat edilmesi gereken noktaları listele
- Yaygın hataları belirt

### 🎯 Sık Çıkan Soru Tipleri
- En çok karşılaşılan soru tiplerini listele
- Her tip için kısa çözüm stratejisi ver

Türkçe açıklama yap. Matematiksel ifadeleri LaTeX formatında yaz."""

    try:
        client = GeminiClient()
        
        import time as _time
        start = _time.time()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.client.models.generate_content,
                model=client.model_name,
                contents=[summary_prompt]
            ),
            timeout=180
        )
        duration = _time.time() - start
        await rate_tracker.record(model=client.model_name, duration=duration)
        
        # Save to database
        summary_id = db.save_summary(
            topic=topic,
            summary=response.text,
            based_on=len(solutions),
            time_taken=duration
        )
        
        return {
            "success": True,
            "id": summary_id,
            "topic": topic,
            "summary": response.text,
            "based_on": len(solutions),
            "time_taken": duration,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/summaries")
async def list_summaries(topic: Optional[str] = Query(None)):
    """List all saved topic summaries"""
    summaries = db.get_summaries(topic=topic)
    return {"summaries": summaries}


@app.get("/api/summaries/{summary_id}")
async def get_summary(summary_id: int):
    """Get a saved summary by ID"""
    summary = db.get_summary(summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary


@app.delete("/api/summaries/{summary_id}")
async def delete_summary(summary_id: int):
    """Delete a saved summary"""
    if db.delete_summary(summary_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Summary not found")


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


@app.delete("/api/questions/{question_id}")
async def delete_question(question_id: int):
    """Delete a single question by ID"""
    success = db.delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question deleted", "id": question_id}


@app.delete("/api/questions")
async def delete_questions(
    question_ids: Optional[List[int]] = None,
    status: Optional[str] = Query(None, enum=["success", "failed"]),
    all_questions: bool = False
):
    """Delete multiple questions"""
    if not question_ids and not status and not all_questions:
        raise HTTPException(
            status_code=400, 
            detail="Provide question_ids, status, or set all_questions=true"
        )
    
    count = db.delete_questions(
        question_ids=question_ids,
        status=status,
        all_questions=all_questions
    )
    
    return {
        "message": f"Deleted {count} questions",
        "count": count
    }


# Mount static files for web assets
# React build assets (JS, CSS chunks)
react_assets_dir = Path(__file__).parent / "frontend" / "dist" / "assets"
if react_assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(react_assets_dir)), name="react-assets")

web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
