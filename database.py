"""
Database Module for Gemini Question Solver
SQLite-based persistent storage for questions, sessions, and statistics
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import json

# Database path
DATABASE_PATH = Path(__file__).parent / "data" / "questions.db"


def get_connection():
    """Get database connection with row factory"""
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            image_path TEXT,
            topic TEXT DEFAULT 'Genel',
            subtopic TEXT,
            status TEXT DEFAULT 'pending',
            solution TEXT,
            error TEXT,
            time_taken REAL,
            retry_count INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            solved_at TIMESTAMP
        )
    """)
    
    # Sessions table  
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            total INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # Topics table for reference
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            icon TEXT,
            color TEXT
        )
    """)
    
    # Insert default topics
    default_topics = [
        ('Matematik', '📐', '#6366f1'),
        ('Fizik', '⚡', '#f59e0b'),
        ('Kimya', '🧪', '#22c55e'),
        ('Biyoloji', '🧬', '#ec4899'),
        ('Türkçe', '📝', '#8b5cf6'),
        ('Tarih', '📜', '#f97316'),
        ('Coğrafya', '🌍', '#14b8a6'),
        ('İngilizce', '🔤', '#3b82f6'),
        ('Genel', '📚', '#64748b'),
    ]
    
    for name, icon, color in default_topics:
        cursor.execute(
            "INSERT OR IGNORE INTO topics (name, icon, color) VALUES (?, ?, ?)",
            (name, icon, color)
        )
    
    conn.commit()
    conn.close()


# ==================== Questions CRUD ====================

def save_question(
    filename: str,
    image_path: str = None,
    topic: str = "Genel",
    subtopic: str = None,
    status: str = "pending",
    solution: str = None,
    error: str = None,
    time_taken: float = None,
    session_id: str = None
) -> int:
    """Save a new question to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO questions 
        (filename, image_path, topic, subtopic, status, solution, error, time_taken, session_id, solved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        filename, image_path, topic, subtopic, status, solution, error, 
        time_taken, session_id,
        datetime.now().isoformat() if status in ('success', 'failed') else None
    ))
    
    question_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return question_id


def update_question(question_id: int, **kwargs) -> bool:
    """Update question fields"""
    if not kwargs:
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Build update query
    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values())
    values.append(question_id)
    
    cursor.execute(f"UPDATE questions SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_question(question_id: int) -> Optional[Dict]:
    """Get question by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_questions(
    status: str = None,
    topic: str = None,
    archived: bool = None,
    session_id: str = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Get questions with optional filters"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM questions WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if topic:
        query += " AND topic = ?"
        params.append(topic)
    
    if archived is not None:
        query += " AND archived = ?"
        params.append(1 if archived else 0)
    
    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_failed_questions() -> List[Dict]:
    """Get all failed questions for retry"""
    return get_questions(status='failed', archived=False)


def archive_questions(question_ids: List[int] = None, status: str = 'success') -> int:
    """Archive questions by IDs or by status"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if question_ids:
        placeholders = ",".join("?" * len(question_ids))
        cursor.execute(
            f"UPDATE questions SET archived = 1 WHERE id IN ({placeholders})",
            question_ids
        )
    else:
        cursor.execute(
            "UPDATE questions SET archived = 1 WHERE status = ? AND archived = 0",
            (status,)
        )
    
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def increment_retry(question_id: int) -> int:
    """Increment retry count for a question"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE questions SET retry_count = retry_count + 1 WHERE id = ?",
        (question_id,)
    )
    cursor.execute("SELECT retry_count FROM questions WHERE id = ?", (question_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row['retry_count'] if row else 0


def delete_question(question_id: int) -> bool:
    """Delete a single question by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count > 0


def delete_questions(question_ids: List[int] = None, status: str = None, all_questions: bool = False) -> int:
    """Delete multiple questions by IDs, status, or all"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if question_ids:
        placeholders = ",".join("?" * len(question_ids))
        cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", question_ids)
    elif status:
        cursor.execute("DELETE FROM questions WHERE status = ?", (status,))
    elif all_questions:
        cursor.execute("DELETE FROM questions")
    else:
        conn.close()
        return 0
    
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# ==================== Sessions ====================

def create_session(session_id: str, source: str = "web", total: int = 0) -> str:
    """Create a new session"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (id, source, total) VALUES (?, ?, ?)",
        (session_id, source, total)
    )
    conn.commit()
    conn.close()
    return session_id


def update_session(session_id: str, **kwargs) -> bool:
    """Update session fields"""
    if not kwargs:
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values())
    values.append(session_id)
    
    cursor.execute(f"UPDATE sessions SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_session(session_id: str) -> Optional[Dict]:
    """Get session by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ==================== Statistics ====================

def get_statistics() -> Dict[str, Any]:
    """Get overall statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total counts
    cursor.execute("SELECT COUNT(*) as total FROM questions WHERE archived = 0")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE status = 'success' AND archived = 0")
    success = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE status = 'failed' AND archived = 0")
    failed = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE archived = 1")
    archived = cursor.fetchone()['count']
    
    # By topic
    cursor.execute("""
        SELECT topic, COUNT(*) as count, 
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
        FROM questions WHERE archived = 0
        GROUP BY topic
    """)
    by_topic = [dict(row) for row in cursor.fetchall()]
    
    # Average time
    cursor.execute("SELECT AVG(time_taken) as avg_time FROM questions WHERE status = 'success'")
    avg_time = cursor.fetchone()['avg_time'] or 0
    
    # Get topics with icons
    cursor.execute("SELECT name, icon, color FROM topics")
    topics = {row['name']: {'icon': row['icon'], 'color': row['color']} for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'total': total,
        'success': success,
        'failed': failed,
        'archived': archived,
        'success_rate': round(success / total * 100, 1) if total > 0 else 0,
        'avg_time': round(avg_time, 2),
        'by_topic': by_topic,
        'topics': topics
    }


def get_topics() -> List[Dict]:
    """Get all topics with icons and colors"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM topics ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Initialize database on import
init_database()
