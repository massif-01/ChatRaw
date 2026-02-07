"""
ChatRaw - Minimalist AI Chat Interface
Python + FastAPI Backend
"""

import os
import json
import uuid
import asyncio
import aiohttp
import io
import struct
import logging
import shutil
from datetime import datetime
from typing import Optional, List, AsyncGenerator
from contextlib import asynccontextmanager

# ============ Structured Logging Setup ============

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "client_ip"):
            log_entry["client_ip"] = record.client_ip
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging():
    """Configure structured logging"""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "json")  # "json" or "text"
    
    # Create logger
    logger = logging.getLogger("chatraw")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler()
    
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
    
    logger.addHandler(handler)
    
    # Also configure uvicorn access logs
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(handler)
    
    return logger

# Initialize logger
logger = setup_logging()

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Form
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import sqlite3
import math
from collections import defaultdict
import time as time_module

# Document parsing
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document as DocxDocument
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

# ============ Embedding Binary Utils ============

def embedding_to_bytes(embedding: List[float]) -> bytes:
    """Convert embedding list to binary format"""
    return struct.pack(f'{len(embedding)}f', *embedding)

def bytes_to_embedding(data: bytes) -> List[float]:
    """Convert binary data back to embedding list"""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', data))

# ============ Shared HTTP Session ============

_http_session: Optional[aiohttp.ClientSession] = None

async def get_http_session() -> aiohttp.ClientSession:
    """Get or create shared HTTP session"""
    global _http_session
    if _http_session is None or _http_session.closed:
        timeout = aiohttp.ClientTimeout(total=300, connect=10)
        _http_session = aiohttp.ClientSession(timeout=timeout)
    return _http_session

async def close_http_session():
    """Close shared HTTP session"""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None

# ============ Models ============

class ModelCapability(BaseModel):
    vision: bool = False
    reasoning: bool = False
    tools: bool = False

class ModelConfig(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    id: str = ""
    name: str = ""
    api_key: str = ""
    api_url: str = ""
    model_id: str = ""
    context_length: int = 8192
    max_output: int = 4096
    type: str = "chat"  # chat, embedding, rerank
    capability: ModelCapability = ModelCapability()

class ChatSettings(BaseModel):
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = True
    system_prompt: str = ""

class RAGSettings(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    score_threshold: float = 0.5

class UISettings(BaseModel):
    logo_data: str = ""
    logo_text: str = "ChatRaw"
    subtitle: str = ""
    theme_mode: str = "light"
    user_avatar: str = ""
    assistant_avatar: str = ""

class Settings(BaseModel):
    chat_settings: ChatSettings = ChatSettings()
    rag_settings: RAGSettings = RAGSettings()
    ui_settings: UISettings = UISettings()

class ChatRequest(BaseModel):
    chat_id: Optional[str] = ""
    message: str = ""
    use_rag: Optional[bool] = False
    use_thinking: Optional[bool] = False  # Enable thinking/reasoning mode
    image_base64: Optional[str] = ""
    web_content: Optional[str] = ""  # Parsed web page content
    web_url: Optional[str] = ""  # Source URL for reference
    
    class Config:
        extra = "ignore"  # Ignore extra fields

class Chat(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

class Message(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    created_at: str

# ============ Database ============

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self.init_db()
    
    def get_conn(self):
        """Get reusable connection (singleton pattern for SQLite)"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent read performance
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn
    
    def init_db(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS model_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key TEXT,
                api_url TEXT NOT NULL,
                model_id TEXT NOT NULL,
                context_length INTEGER DEFAULT 8192,
                max_output INTEGER DEFAULT 4096,
                type TEXT NOT NULL,
                capability TEXT,
                created_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content TEXT,
                created_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                created_at TEXT
            );
            
            -- Indexes for faster queries
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_model_type ON model_configs(type);
        """)
        
        conn.commit()
        
        # Migrate old JSON embeddings to binary format
        self._migrate_embeddings(conn)
        
        # Initialize defaults
        self._init_defaults(conn)
    
    def _migrate_embeddings(self, conn):
        """Migrate old JSON embeddings to binary BLOB format"""
        cursor = conn.cursor()
        # Check if there are any text-based embeddings to migrate
        cursor.execute("SELECT id, embedding FROM document_chunks WHERE embedding IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        if row and row["embedding"]:
            # Check if it's JSON (starts with '[')
            try:
                data = row["embedding"]
                if isinstance(data, str) and data.startswith('['):
                    logger.info("Migrating embeddings from JSON to binary format")
                    cursor.execute("SELECT id, embedding FROM document_chunks WHERE embedding IS NOT NULL")
                    rows = cursor.fetchall()
                    for r in rows:
                        if isinstance(r["embedding"], str):
                            try:
                                emb_list = json.loads(r["embedding"])
                                emb_bytes = embedding_to_bytes(emb_list)
                                cursor.execute("UPDATE document_chunks SET embedding = ? WHERE id = ?", (emb_bytes, r["id"]))
                            except:
                                pass
                    conn.commit()
                    logger.info(f"Migrated {len(rows)} embeddings to binary format")
            except:
                pass
    
    def _init_defaults(self, conn):
        cursor = conn.cursor()
        
        # Default settings
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("global",))
        if not cursor.fetchone():
            settings = Settings()
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", 
                         ("global", settings.model_dump_json()))
        
        # Default models
        for model_type, model_id_default in [("chat", "default-chat"), ("embedding", "default-embedding"), ("rerank", "default-rerank")]:
            cursor.execute("SELECT id FROM model_configs WHERE id = ?", (model_id_default,))
            if not cursor.fetchone():
                model = ModelConfig(
                    id=model_id_default,
                    name=f"{model_type.capitalize()} Model",
                    type=model_type
                )
                cursor.execute("""
                    INSERT INTO model_configs (id, name, api_key, api_url, model_id, context_length, max_output, type, capability, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (model.id, model.name, model.api_key, model.api_url, model.model_id,
                      model.context_length, model.max_output, model.type, 
                      json.dumps(model.capability.model_dump()), datetime.now().isoformat()))
        
        conn.commit()
    
    # Settings
    def get_settings(self) -> Settings:
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("global",))
        row = cursor.fetchone()
        if row:
            return Settings.model_validate_json(row["value"])
        return Settings()
    
    def save_settings(self, settings: Settings):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ("global", settings.model_dump_json()))
        conn.commit()
    
    # Model configs
    def get_model_configs(self) -> List[ModelConfig]:
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT * FROM model_configs")
        rows = cursor.fetchall()
        
        configs = []
        for row in rows:
            cap = json.loads(row["capability"]) if row["capability"] else {}
            configs.append(ModelConfig(
                id=row["id"],
                name=row["name"],
                api_key=row["api_key"] or "",
                api_url=row["api_url"] or "",
                model_id=row["model_id"] or "",
                context_length=row["context_length"],
                max_output=row["max_output"],
                type=row["type"],
                capability=ModelCapability(**cap)
            ))
        return configs
    
    def get_model_by_type(self, model_type: str) -> Optional[ModelConfig]:
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT * FROM model_configs WHERE type = ? LIMIT 1", (model_type,))
        row = cursor.fetchone()
        
        if row:
            cap = json.loads(row["capability"]) if row["capability"] else {}
            return ModelConfig(
                id=row["id"],
                name=row["name"],
                api_key=row["api_key"] or "",
                api_url=row["api_url"] or "",
                model_id=row["model_id"] or "",
                context_length=row["context_length"],
                max_output=row["max_output"],
                type=row["type"],
                capability=ModelCapability(**cap)
            )
        return None
    
    def save_model_config(self, config: ModelConfig) -> ModelConfig:
        if not config.id:
            config.id = str(uuid.uuid4())
        
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO model_configs 
            (id, name, api_key, api_url, model_id, context_length, max_output, type, capability, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (config.id, config.name or config.model_id, config.api_key, config.api_url, config.model_id,
              config.context_length, config.max_output, config.type,
              json.dumps(config.capability.model_dump()), datetime.now().isoformat()))
        conn.commit()
        return config
    
    def delete_model_config(self, model_id: str):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM model_configs WHERE id = ?", (model_id,))
        conn.commit()
    
    # Chats
    def get_chats(self) -> List[Chat]:
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT * FROM chats ORDER BY updated_at DESC LIMIT 10")
        rows = cursor.fetchall()
        
        return [Chat(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        ) for row in rows]
    
    def create_chat(self, title: str = "New Chat") -> Chat:
        conn = self.get_conn()
        cursor = conn.cursor()
        # Cleanup old chats and their messages
        cursor.execute("""
            DELETE FROM messages WHERE chat_id IN (
                SELECT id FROM chats ORDER BY updated_at DESC LIMIT -1 OFFSET 9
            )
        """)
        cursor.execute("""
            DELETE FROM chats WHERE id IN (
                SELECT id FROM chats ORDER BY updated_at DESC LIMIT -1 OFFSET 9
            )
        """)
        
        chat_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute("INSERT INTO chats (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                      (chat_id, title, now, now))
        conn.commit()
        
        return Chat(id=chat_id, title=title, created_at=now, updated_at=now)
    
    def update_chat_title(self, chat_id: str, title: str):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
                      (title, datetime.now().isoformat(), chat_id))
        conn.commit()
    
    def delete_chat(self, chat_id: str):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
    
    # Messages
    def get_messages(self, chat_id: str) -> List[Message]:
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
        rows = cursor.fetchall()
        
        return [Message(
            id=row["id"],
            chat_id=row["chat_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"]
        ) for row in rows]
    
    def add_message(self, chat_id: str, role: str, content: str) -> Message:
        msg_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                      (msg_id, chat_id, role, content, now))
        cursor.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
        conn.commit()
        
        return Message(id=msg_id, chat_id=chat_id, role=role, content=content, created_at=now)
    
    # Documents
    def get_documents(self):
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT id, filename, created_at FROM documents ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [{"id": r["id"], "filename": r["filename"], "created_at": r["created_at"]} for r in rows]
    
    def save_document(self, filename: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO documents (id, filename, content, created_at) VALUES (?, ?, ?, ?)",
                      (doc_id, filename, content, datetime.now().isoformat()))
        conn.commit()
        return doc_id
    
    def delete_document(self, doc_id: str):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
    
    def save_chunk(self, doc_id: str, content: str, embedding: List[float] = None):
        """Save chunk with binary embedding"""
        chunk_id = str(uuid.uuid4())
        conn = self.get_conn()
        cursor = conn.cursor()
        emb_data = embedding_to_bytes(embedding) if embedding else None
        cursor.execute("INSERT INTO document_chunks (id, document_id, content, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
                      (chunk_id, doc_id, content, emb_data, datetime.now().isoformat()))
        conn.commit()
    
    def get_chunks_with_embedding(self, limit: int = 500, offset: int = 0):
        """Get chunks with pagination for memory efficiency"""
        cursor = self.get_conn().cursor()
        cursor.execute(
            "SELECT id, document_id, content, embedding FROM document_chunks WHERE embedding IS NOT NULL LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = cursor.fetchall()
        
        chunks = []
        for r in rows:
            emb_data = r["embedding"]
            if emb_data:
                # Handle both binary and legacy JSON format
                if isinstance(emb_data, bytes):
                    emb = bytes_to_embedding(emb_data)
                else:
                    emb = json.loads(emb_data) if isinstance(emb_data, str) else []
            else:
                emb = []
            chunks.append({"id": r["id"], "document_id": r["document_id"], "content": r["content"], "embedding": emb})
        return chunks
    
    def get_total_chunks_count(self) -> int:
        """Get total count of chunks with embeddings"""
        cursor = self.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
        return cursor.fetchone()[0]

# ============ LLM Service ============

class LLMService:
    def __init__(self, db: Database):
        self.db = db
    
    async def chat_stream(self, chat_id: str, message: str, use_rag: bool = False, use_thinking: bool = False, image_base64: str = "", web_content: str = "", web_url: str = "") -> AsyncGenerator[str, None]:
        """Stream chat responses with optional thinking/reasoning support"""
        config = self.db.get_model_by_type("chat")
        if not config or not config.api_url or not config.model_id:
            yield json.dumps({"error": "Chat model not configured"})
            return
        
        settings = self.db.get_settings()
        
        # Build messages
        history = self.db.get_messages(chat_id)
        messages = []
        
        # Add system prompt if configured
        if settings.chat_settings.system_prompt:
            messages.append({"role": "system", "content": settings.chat_settings.system_prompt})
        
        # Add conversation history
        messages.extend([{"role": m.role, "content": m.content} for m in history])
        
        # RAG context and references
        rag_context = ""
        rag_references = []
        if use_rag:
            rag_context, rag_references = await self.build_rag_context(message)
        
        # Web content context
        web_context = ""
        if web_content:
            web_context = f"以下是用户提供的网页内容作为参考 (来源: {web_url}):\n---\n{web_content}\n---\n\n"
        
        # User message
        final_message = message
        if rag_context:
            final_message = f"{rag_context}User question: {message}"
        if web_context:
            final_message = f"{web_context}{final_message}"
        
        # Handle image
        if image_base64 and config.capability.vision:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": final_message},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": final_message})
        
        # API request
        url = config.api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        payload = {
            "model": config.model_id,
            "messages": messages,
            "temperature": settings.chat_settings.temperature,
            "top_p": settings.chat_settings.top_p,
            "max_tokens": config.max_output,
            "stream": True
        }
        
        # Enable thinking/reasoning mode if requested
        # Different models use different parameters:
        # - DeepSeek R1: enable_thinking + stream_options.include_reasoning
        # - Qwen QwQ: enable_thinking
        # - OpenAI o1: reasoning_effort (but o1 thinks by default)
        # - GPTOSS/compatible APIs: enable_thinking
        if use_thinking:
            payload["enable_thinking"] = True
            payload["stream_options"] = {"include_reasoning": True}
        
        full_response = ""
        full_thinking = ""
        
        try:
            session = await get_http_session()
            async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        yield json.dumps({"error": f"API error ({resp.status}): {error_text}"})
                        return
                    
                    buffer = ""
                    async for chunk in resp.content.iter_any():
                        buffer += chunk.decode("utf-8")
                        
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            
                            if not line.startswith("data: "):
                                continue
                            
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            
                            try:
                                chunk_data = json.loads(data)
                                if chunk_data.get("choices") and len(chunk_data["choices"]) > 0:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    
                                    # Handle reasoning/thinking content (DeepSeek, Qwen, etc.)
                                    # Only process if thinking mode is enabled
                                    if use_thinking:
                                        reasoning = delta.get("reasoning_content", "") or delta.get("reasoning", "") or delta.get("thinking", "")
                                        if reasoning:
                                            full_thinking += reasoning
                                            yield json.dumps({"thinking": reasoning})
                                    
                                    # Handle regular content
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        yield json.dumps({"content": content})
                            except json.JSONDecodeError:
                                continue
            
            # Save response (include thinking in saved message if present)
            if full_response:
                save_content = full_response
                if full_thinking:
                    save_content = f"<thinking>\n{full_thinking}\n</thinking>\n\n{full_response}"
                self.db.add_message(chat_id, "assistant", save_content)
                
                # Update title
                messages_count = len(self.db.get_messages(chat_id))
                if messages_count <= 2:
                    title = message[:30] + "..." if len(message) > 30 else message
                    self.db.update_chat_title(chat_id, title)
            
            # Send references if RAG was used
            if rag_references:
                yield json.dumps({"references": rag_references})
            
            yield json.dumps({"done": True})
            
        except asyncio.TimeoutError:
            yield json.dumps({"error": "Request timeout"})
        except Exception as e:
            yield json.dumps({"error": str(e)})
    
    async def chat_non_stream(self, chat_id: str, message: str, use_rag: bool = False, use_thinking: bool = False, image_base64: str = "", web_content: str = "", web_url: str = "") -> dict:
        """Non-streaming chat, returns dict with content, thinking, and references"""
        config = self.db.get_model_by_type("chat")
        if not config or not config.api_url or not config.model_id:
            raise HTTPException(status_code=500, detail="Chat model not configured")
        
        settings = self.db.get_settings()
        
        history = self.db.get_messages(chat_id)
        messages = []
        
        # Add system prompt if configured
        if settings.chat_settings.system_prompt:
            messages.append({"role": "system", "content": settings.chat_settings.system_prompt})
        
        # Add conversation history
        messages.extend([{"role": m.role, "content": m.content} for m in history])
        
        # RAG context and references
        rag_context = ""
        rag_references = []
        if use_rag:
            rag_context, rag_references = await self.build_rag_context(message)
        
        # Web content context
        web_context = ""
        if web_content:
            web_context = f"以下是用户提供的网页内容作为参考 (来源: {web_url}):\n---\n{web_content}\n---\n\n"
        
        final_message = message
        if rag_context:
            final_message = f"{rag_context}User question: {message}"
        if web_context:
            final_message = f"{web_context}{final_message}"
        
        if image_base64 and config.capability.vision:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": final_message},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": final_message})
        
        url = config.api_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        payload = {
            "model": config.model_id,
            "messages": messages,
            "temperature": settings.chat_settings.temperature,
            "top_p": settings.chat_settings.top_p,
            "max_tokens": config.max_output,
            "stream": False
        }
        
        # Enable thinking/reasoning mode if requested
        if use_thinking:
            payload["enable_thinking"] = True
        
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise HTTPException(status_code=500, detail=f"API error: {error_text}")
            
            data = await resp.json()
            msg_data = data["choices"][0]["message"]
            content = msg_data.get("content", "")
            
            # Extract thinking/reasoning content if thinking mode is enabled
            thinking = ""
            if use_thinking:
                thinking = msg_data.get("reasoning_content", "") or msg_data.get("reasoning", "") or msg_data.get("thinking", "")
            
            # Save response (include thinking in saved message if present)
            save_content = content
            if thinking:
                save_content = f"<thinking>\n{thinking}\n</thinking>\n\n{content}"
            self.db.add_message(chat_id, "assistant", save_content)
            
            messages_count = len(self.db.get_messages(chat_id))
            if messages_count <= 2:
                title = message[:30] + "..." if len(message) > 30 else message
                self.db.update_chat_title(chat_id, title)
            
            return {"content": content, "thinking": thinking, "references": rag_references}
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for single text"""
        results = await self.get_embeddings_batch([text])
        return results[0] if results else []
    
    async def get_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """Get embeddings for multiple texts in batches (reduces API calls)"""
        config = self.db.get_model_by_type("embedding")
        if not config or not config.api_url or not config.model_id:
            logger.warning("No embedding model configured")
            return [[] for _ in texts]
        
        url = config.api_url.rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        all_embeddings = []
        session = await get_http_session()
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {"model": config.model_id, "input": batch}
            
            try:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Embedding API error ({resp.status}): {error_text[:200]}")
                        # Return empty embeddings for this batch
                        all_embeddings.extend([[] for _ in batch])
                        continue
                    
                    data = await resp.json()
                    # Sort by index to ensure correct order (some APIs return unordered)
                    sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                    batch_embeddings = [item["embedding"] for item in sorted_data]
                    all_embeddings.extend(batch_embeddings)
                    logger.debug(f"Got {len(batch_embeddings)} embeddings (batch {i//batch_size + 1})")
                    
            except Exception as e:
                logger.error(f"Embedding batch exception: {e}")
                all_embeddings.extend([[] for _ in batch])
        
        return all_embeddings
    
    async def rerank(self, query: str, documents: List[str]) -> List[dict]:
        """Rerank documents using rerank model, returns list of {index, score}"""
        config = self.db.get_model_by_type("rerank")
        if not config or not config.api_url or not config.model_id:
            logger.debug("No rerank model configured, skipping rerank")
            return []
        
        url = config.api_url.rstrip("/") + "/rerank"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        payload = {
            "model": config.model_id,
            "query": query,
            "documents": documents,
            "return_documents": False
        }
        
        try:
            logger.debug(f"Calling rerank API with {len(documents)} documents")
            session = await get_http_session()
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Rerank API error ({resp.status}): {error_text[:200]}")
                    return []
                
                data = await resp.json()
                # Handle different response formats
                results = data.get("results") or data.get("data") or []
                logger.debug(f"Got {len(results)} reranked results")
                return results
        except Exception as e:
            logger.error(f"Rerank exception: {e}")
            return []
    
    async def build_rag_context(self, query: str) -> tuple:
        """Build RAG context from documents, returns (context_string, references_list)"""
        settings = self.db.get_settings()
        
        query_embedding = await self.get_embedding(query)
        if not query_embedding:
            return "", []
        
        # Paginated loading for memory efficiency
        candidates = []
        offset = 0
        batch_size = 200
        
        while True:
            chunks = self.db.get_chunks_with_embedding(limit=batch_size, offset=offset)
            if not chunks:
                break
            
            for chunk in chunks:
                if not chunk["embedding"]:
                    continue
                score = self.cosine_similarity(query_embedding, chunk["embedding"])
                if score >= settings.rag_settings.score_threshold:
                    candidates.append({"content": chunk["content"], "score": round(score, 2)})
            
            offset += batch_size
            # Early exit if we have enough high-scoring candidates
            if len(candidates) >= 50:
                break
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Get more candidates for reranking (2x top_k or at least 10)
        rerank_pool_size = max(settings.rag_settings.top_k * 2, 10)
        candidates = candidates[:rerank_pool_size]
        
        if not candidates:
            return "", []
        
        # Second stage: Rerank using rerank model
        rerank_config = self.db.get_model_by_type("rerank")
        if rerank_config and rerank_config.api_url and rerank_config.model_id:
            documents = [c["content"] for c in candidates]
            rerank_results = await self.rerank(query, documents)
            
            if rerank_results:
                # Rebuild results using rerank scores
                results = []
                for r in rerank_results:
                    idx = r.get("index", 0)
                    rerank_score = r.get("relevance_score") or r.get("score", 0)
                    if idx < len(candidates):
                        results.append({
                            "content": candidates[idx]["content"],
                            "score": round(rerank_score, 2)
                        })
                
                results.sort(key=lambda x: x["score"], reverse=True)
                results = results[:settings.rag_settings.top_k]
                logger.info(f"RAG using reranked results, top score: {results[0]['score'] if results else 'N/A'}")
            else:
                # Fallback to embedding scores if rerank failed
                results = candidates[:settings.rag_settings.top_k]
                logger.warning("RAG rerank failed, using embedding scores")
        else:
            # No rerank model, use embedding scores directly
            results = candidates[:settings.rag_settings.top_k]
            logger.debug("RAG using embedding scores (no rerank model)")
        
        if not results:
            return "", []
        
        context = "Here are relevant references:\n\n"
        for i, r in enumerate(results):
            context += f"[Reference {i+1}] (Relevance: {r['score']:.2f})\n{r['content']}\n\n"
        context += "Please answer based on the above references. If there's no relevant information, answer based on your knowledge.\n\n"
        
        # Return both context and references for frontend display
        references = [{"content": r["content"], "score": r["score"]} for r in results]
        return context, references
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

# ============ RAG Service ============

class RAGService:
    def __init__(self, db: Database, llm: LLMService):
        self.db = db
        self.llm = llm
    
    def chunk_document(self, content: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split document into chunks, ensuring each chunk <= chunk_size"""
        paragraphs = content.split("\n\n")
        chunks = []
        current = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If paragraph itself is longer than chunk_size, force split it
            if len(para) > chunk_size:
                # First, save current buffer if not empty
                if current.strip():
                    chunks.append(current.strip())
                    current = ""
                # Force split the long paragraph
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
                continue
            
            if len(current) + len(para) > chunk_size:
                if current.strip():
                    chunks.append(current.strip())
                    if len(current) > overlap:
                        current = current[-overlap:] + " "
                    else:
                        current = ""
            
            current += para + "\n\n"
        
        if current.strip():
            chunks.append(current.strip())
        
        # Fallback: if still no chunks, force split entire content
        if not chunks and content:
            for i in range(0, len(content), chunk_size - overlap):
                chunks.append(content[i:i + chunk_size])
        
        return chunks
    
    async def process_document(self, filename: str, content: str):
        settings = self.db.get_settings()
        
        doc_id = self.db.save_document(filename, content)
        chunks = self.chunk_document(content, settings.rag_settings.chunk_size, settings.rag_settings.chunk_overlap)
        
        for chunk in chunks:
            embedding = await self.llm.get_embedding(chunk)
            self.db.save_chunk(doc_id, chunk, embedding if embedding else None)

# ============ App ============

DATA_DIR = os.environ.get("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

# CORS configuration from environment
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")  # Comma-separated origins or "*" for all

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "120"))  # requests per window (increased for dev)
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))  # window in seconds

# File upload limits (in bytes)
MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))  # 50MB default
MAX_IMAGE_SIZE = int(os.environ.get("MAX_IMAGE_SIZE", str(20 * 1024 * 1024)))  # 20MB default

# ============ Rate Limiting Middleware ============

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware using sliding window"""
    
    def __init__(self, app, requests_per_window: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.request_counts = defaultdict(list)  # ip -> list of timestamps
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, considering proxy headers"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _clean_old_requests(self, ip: str, now: float):
        """Remove requests outside the current window"""
        cutoff = now - self.window_seconds
        self.request_counts[ip] = [ts for ts in self.request_counts[ip] if ts > cutoff]
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static files
        if request.url.path in ["/health", "/ready"] or not request.url.path.startswith("/api"):
            return await call_next(request)
        
        # Skip rate limiting for plugin-related requests
        # These are essential for plugin system and shouldn't count against API limits
        if "/lib/" in request.url.path or request.url.path.endswith("/icon") or request.url.path.endswith("/main.js"):
            return await call_next(request)
        
        # Skip rate limiting for plugin metadata requests (needed for initialization)
        if request.url.path == "/api/plugins" or request.url.path.startswith("/api/plugins/"):
            return await call_next(request)
        
        ip = self._get_client_ip(request)
        now = time_module.time()
        
        # Clean old requests and check limit
        self._clean_old_requests(ip, now)
        
        if len(self.request_counts[ip]) >= self.requests_per_window:
            return JSONResponse(
                {"error": "Rate limit exceeded. Please try again later."},
                status_code=429,
                headers={"Retry-After": str(self.window_seconds)}
            )
        
        # Record this request
        self.request_counts[ip].append(now)
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.requests_per_window - len(self.request_counts[ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)
        
        return response

db = Database(os.path.join(DATA_DIR, "chatraw.db"))
llm_service = LLMService(db)
rag_service = RAGService(db, llm_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle: startup and shutdown"""
    logger.info("Starting ChatRaw service")
    yield
    # Cleanup on shutdown
    logger.info("Shutting down ChatRaw service")
    await close_http_session()

app = FastAPI(title="ChatRaw", lifespan=lifespan)

# Add GZip compression middleware for static assets
app.add_middleware(GZipMiddleware, minimum_size=500)

# Add rate limiting middleware (if enabled)
if RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware, requests_per_window=RATE_LIMIT_REQUESTS, window_seconds=RATE_LIMIT_WINDOW)

# Parse CORS origins: "*" for all, or comma-separated list like "http://localhost:3000,https://example.com"
cors_origins = ["*"] if CORS_ORIGINS == "*" else [origin.strip() for origin in CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if CORS_ORIGINS != "*" else False,  # credentials not allowed with "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Note: CSP with strict script-src is not compatible with Alpine.js (requires unsafe-eval)
        # If you need CSP, consider using Alpine.js CSP build: https://alpinejs.dev/advanced/csp
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ============ API Routes ============

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and container orchestration"""
    return {"status": "healthy", "service": "chatraw"}

@app.get("/ready")
async def readiness_check():
    """Readiness check - verifies database connectivity"""
    try:
        # Test database connection
        cursor = db.get_conn().cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Check if required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chats'")
        if not cursor.fetchone():
            return JSONResponse({"status": "not_ready", "reason": "database not initialized"}, status_code=503)
        
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "reason": str(e)}, status_code=503)

@app.get("/fonts/{path:path}")
async def fonts(path: str):
    """Serve font files with long-term caching for optimal performance"""
    try:
        font_path = os.path.join("static", "fonts", path)
        if not os.path.exists(font_path):
            raise HTTPException(status_code=404, detail="Font file not found")
        
        return FileResponse(
            font_path,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        logger.error(f"Error serving font file: {str(e)}")
        raise HTTPException(status_code=404, detail="Font file not found")

@app.get("/api/settings")
async def get_settings(include_logo: bool = False):
    """Get settings. By default excludes logo_data for faster initial load."""
    settings = db.get_settings().model_dump()
    if not include_logo:
        # Exclude large logo_data from initial load for better LCP
        settings['ui_settings']['logo_data'] = '' if settings['ui_settings'].get('logo_data') else ''
    return settings

@app.get("/api/settings/logo")
async def get_settings_logo():
    """Get logo_data separately for lazy loading."""
    settings = db.get_settings()
    return {"logo_data": settings.ui_settings.logo_data}

@app.post("/api/settings")
async def save_settings(settings: Settings):
    db.save_settings(settings)
    return {"success": True}

@app.get("/api/models")
async def get_models():
    configs = db.get_model_configs()
    return [c.model_dump() for c in configs]

@app.post("/api/models")
async def save_model(config: ModelConfig):
    saved = db.save_model_config(config)
    return saved.model_dump()

@app.post("/api/models/verify")
async def verify_model(config: ModelConfig):
    if not config.api_url or not config.model_id:
        return {"success": False, "error": "API URL and Model ID required"}
    
    url = config.api_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    
    try:
        session = await get_http_session()
        if config.type == "chat":
            payload = {
                "model": config.model_id,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
                "stream": False
            }
            async with session.post(f"{url}/chat/completions", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    return {"success": True}
                else:
                    text = await resp.text()
                    return {"success": False, "error": f"API error ({resp.status}): {text[:200]}"}
        elif config.type == "embedding":
            payload = {"model": config.model_id, "input": "test"}
            async with session.post(f"{url}/embeddings", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    return {"success": True}
                else:
                    text = await resp.text()
                    return {"success": False, "error": f"API error ({resp.status}): {text[:200]}"}
        else:  # rerank
            payload = {
                "model": config.model_id,
                "query": "test query",
                "documents": ["test document 1", "test document 2"]
            }
            async with session.post(f"{url}/rerank", json=payload, headers=headers) as resp:
                text = await resp.text()
                # Check if endpoint is actually supported
                if "Unexpected endpoint" in text or "not found" in text.lower() or "not supported" in text.lower():
                    return {"success": False, "error": "Rerank not supported. LM Studio doesn't have /v1/rerank endpoint."}
                if resp.status == 200:
                    # Try to parse response to verify it's a real rerank response
                    try:
                        data = json.loads(text)
                        if "results" in data or "data" in data:
                            return {"success": True}
                        else:
                            return {"success": False, "error": "Invalid rerank response format"}
                    except:
                        return {"success": False, "error": "Invalid rerank response"}
                else:
                    return {"success": False, "error": f"API error ({resp.status}): {text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    db.delete_model_config(model_id)
    return {"success": True}

@app.get("/api/chats")
async def get_chats():
    chats = db.get_chats()
    return [c.model_dump() for c in chats]

@app.post("/api/chats")
async def create_chat():
    chat = db.create_chat("New Chat")
    return chat.model_dump()

@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    db.delete_chat(chat_id)
    return {"success": True}

@app.get("/api/chats/{chat_id}/messages")
async def get_messages(chat_id: str):
    messages = db.get_messages(chat_id)
    return [m.model_dump() for m in messages]

@app.post("/api/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    
    chat_id = body.get("chat_id", "") or ""
    message = body.get("message", "") or ""
    use_rag = body.get("use_rag", False) or False
    use_thinking = body.get("use_thinking", False) or False
    image_base64 = body.get("image_base64", "") or ""
    web_content = body.get("web_content", "") or ""
    web_url = body.get("web_url", "") or ""
    
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)
    
    # Create chat if needed
    if not chat_id:
        chat_obj = db.create_chat("New Chat")
        chat_id = chat_obj.id
    
    # Save user message
    db.add_message(chat_id, "user", message)
    
    settings = db.get_settings()
    
    if settings.chat_settings.stream:
        # Streaming response
        async def generate():
            # Send chat_id first
            yield json.dumps({"chat_id": chat_id}) + "\n"
            
            # Stream content
            async for chunk in llm_service.chat_stream(chat_id, message, use_rag, use_thinking, image_base64, web_content, web_url):
                yield chunk + "\n"
        
        return StreamingResponse(
            generate(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity"
            }
        )
    else:
        # Non-streaming response
        result = await llm_service.chat_non_stream(chat_id, message, use_rag, use_thinking, image_base64, web_content, web_url)
        return {"chat_id": chat_id, "content": result["content"], "thinking": result.get("thinking", ""), "references": result["references"]}

@app.get("/api/documents")
async def get_documents():
    return db.get_documents()

def _parse_pdf_sync(content: bytes) -> str:
    """Synchronous PDF parsing (to be run in thread pool)"""
    if not PDF_SUPPORT:
        raise ValueError("PDF support not available. Install pypdf.")
    
    try:
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")

def _parse_docx_sync(content: bytes) -> str:
    """Synchronous DOCX parsing (to be run in thread pool)"""
    if not DOCX_SUPPORT:
        raise ValueError("DOCX support not available. Install python-docx.")
    
    try:
        docx_file = io.BytesIO(content)
        doc = DocxDocument(docx_file)
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {str(e)}")

def _parse_text_sync(content: bytes) -> str:
    """Synchronous text decoding"""
    try:
        return content.decode("utf-8")
    except:
        return content.decode("latin-1")

async def parse_document_content(filename: str, content: bytes) -> str:
    """Parse document based on file extension (async - runs blocking IO in thread pool)"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    if ext == 'pdf':
        return await asyncio.to_thread(_parse_pdf_sync, content)
    elif ext in ('docx', 'doc'):
        if ext == 'doc':
            raise ValueError("Old .doc format not supported. Please convert to .docx")
        return await asyncio.to_thread(_parse_docx_sync, content)
    elif ext in ('txt', 'md', 'markdown', 'text'):
        return await asyncio.to_thread(_parse_text_sync, content)
    else:
        # Try to decode as text
        return await asyncio.to_thread(_parse_text_sync, content)

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    # Check file size limit
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            {"error": f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB"},
            status_code=413
        )
    
    # Parse document based on file type (async to avoid blocking)
    try:
        text = await parse_document_content(file.filename, content)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    
    if not text.strip():
        return JSONResponse({"error": "No text content found in document"}, status_code=400)
    
    # Return streaming progress
    async def generate_progress():
        settings = db.get_settings()
        doc_id = db.save_document(file.filename, text)
        chunks = rag_service.chunk_document(text, settings.rag_settings.chunk_size, settings.rag_settings.chunk_overlap)
        
        total = len(chunks)
        yield json.dumps({"status": "chunking", "total": total}) + "\n"
        
        # Batch embedding for efficiency (10 chunks per API call)
        batch_size = 10
        processed = 0
        
        for i in range(0, total, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            embeddings = await llm_service.get_embeddings_batch(batch_chunks, batch_size=batch_size)
            
            # Save each chunk with its embedding
            for chunk, embedding in zip(batch_chunks, embeddings):
                db.save_chunk(doc_id, chunk, embedding if embedding else None)
                processed += 1
                progress = int(processed / total * 100)
                yield json.dumps({"status": "embedding", "progress": progress, "current": processed, "total": total}) + "\n"
        
        yield json.dumps({"status": "done", "filename": file.filename}) + "\n"
    
    return StreamingResponse(generate_progress(), media_type="application/x-ndjson")

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    db.delete_document(doc_id)
    return {"success": True}

@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    import base64
    content = await file.read()
    
    # Check image size limit
    if len(content) > MAX_IMAGE_SIZE:
        return JSONResponse(
            {"success": False, "error": f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)}MB"},
            status_code=413
        )
    
    b64 = base64.b64encode(content).decode("utf-8")
    return {"success": True, "filename": file.filename, "base64": b64}

@app.post("/api/upload/document")
async def upload_document_for_chat(file: UploadFile = File(...)):
    """Parse a document and return its content for chat attachment"""
    try:
        content = await file.read()
        
        # Check file size limit
        if len(content) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {"success": False, "error": f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB"},
                status_code=413
            )
        
        try:
            text = await parse_document_content(file.filename, content)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            return JSONResponse({"success": False, "error": f"Parse error: {str(e)}"}, status_code=500)
        
        if not text.strip():
            return JSONResponse({"success": False, "error": "No text content found in document"}, status_code=400)
        
        # Limit content length for chat context (max ~8000 chars)
        max_length = 8000
        if len(text) > max_length:
            text = text[:max_length] + "...\n\n[内容已截断]"
        
        return {
            "success": True,
            "filename": file.filename,
            "content": text,
            "length": len(text)
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Upload error: {str(e)}"}, status_code=500)

class ParseUrlRequest(BaseModel):
    url: str

# ============ Plugin Models ============

class ProxyRequest(BaseModel):
    """Request model for HTTP proxy"""
    service_id: str
    url: str
    method: str = "POST"
    headers: dict = {}
    body: dict = {}

class PluginInstallRequest(BaseModel):
    """Request model for plugin installation"""
    source_url: str

class PluginSettingsUpdate(BaseModel):
    """Request model for plugin settings update"""
    settings: dict = {}

class PluginToggleRequest(BaseModel):
    """Request model for plugin enable/disable"""
    enabled: bool


@app.post("/api/fetch-raw-url")
async def fetch_raw_url(request: ParseUrlRequest):
    """Fetch raw HTML from URL (no content extraction). Used by url_parser plugins."""
    from urllib.parse import urlparse

    url = request.url.strip()

    if not url:
        return JSONResponse({"success": False, "error": "URL is required"}, status_code=400)

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return JSONResponse({"success": False, "error": "Invalid URL"}, status_code=400)
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid URL format"}, status_code=400)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        session = await get_http_session()
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
            if resp.status != 200:
                return JSONResponse({"success": False, "error": f"Failed to fetch URL (HTTP {resp.status})"}, status_code=400)
            html = await resp.text()
        return {"success": True, "html": html, "url": url}
    except asyncio.TimeoutError:
        return JSONResponse({"success": False, "error": "Request timeout - page took too long to load"}, status_code=400)
    except aiohttp.ClientError as e:
        return JSONResponse({"success": False, "error": f"Network error: {str(e)}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/parse-url")
async def parse_url(request: ParseUrlRequest):
    """Parse web page content from URL"""
    import re
    from urllib.parse import urlparse
    
    url = request.url.strip()
    
    # Validate URL format
    if not url:
        return JSONResponse({"success": False, "error": "URL is required"}, status_code=400)
    
    # Add https:// if no protocol specified
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return JSONResponse({"success": False, "error": "Invalid URL"}, status_code=400)
    except:
        return JSONResponse({"success": False, "error": "Invalid URL format"}, status_code=400)
    
    try:
        # Fetch the web page
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        session = await get_http_session()
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
            if resp.status != 200:
                return JSONResponse({"success": False, "error": f"Failed to fetch URL (HTTP {resp.status})"}, status_code=400)
            
            html = await resp.text()
        
        # Try to use trafilatura for content extraction
        try:
            import trafilatura
            content = trafilatura.extract(html, include_comments=False, include_tables=True, no_fallback=False)
            
            if not content:
                # Fallback: simple HTML tag stripping
                content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
        except ImportError:
            # trafilatura not installed, use simple extraction
            content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
        
        if not content:
            return JSONResponse({"success": False, "error": "Could not extract content from page"}, status_code=400)
        
        # Limit content length (max ~8000 chars to leave room for user message)
        max_length = 8000
        if len(content) > max_length:
            content = content[:max_length] + "...\n\n[内容已截断]"
        
        # Extract title from HTML
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else parsed.netloc
        
        return {
            "success": True,
            "title": title,
            "content": content,
            "url": url,
            "length": len(content)
        }
        
    except asyncio.TimeoutError:
        return JSONResponse({"success": False, "error": "Request timeout - page took too long to load"}, status_code=400)
    except aiohttp.ClientError as e:
        return JSONResponse({"success": False, "error": f"Network error: {str(e)}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Failed to parse URL: {str(e)}"}, status_code=500)

# ============ Plugin Management ============

PLUGINS_DIR = os.path.join(DATA_DIR, "plugins")
PLUGINS_INSTALLED_DIR = os.path.join(PLUGINS_DIR, "installed")
PLUGINS_CONFIG_FILE = os.path.join(PLUGINS_DIR, "config.json")

# Plugin upload size limit (10MB)
MAX_PLUGIN_SIZE = int(os.environ.get("MAX_PLUGIN_SIZE", str(10 * 1024 * 1024)))

# Ensure plugin directories exist
os.makedirs(PLUGINS_INSTALLED_DIR, exist_ok=True)

# Auto-install bundled plugins with lib/ directory (offline dependencies)
BUNDLED_PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "Plugins", "Plugin_market")

def auto_install_bundled_plugins():
    """Auto-copy lib/ directory for installed plugins with offline dependencies
    
    This handles plugins like markdown-enhancer that bundle KaTeX, Mermaid, etc.
    Online installation only downloads main.js/manifest.json/icon.png, not lib/.
    This function ensures lib/ is copied from the bundled version in the Docker image.
    
    Note: Does NOT auto-install plugins - only supplements lib/ for already installed plugins.
    """
    if not os.path.exists(BUNDLED_PLUGINS_DIR):
        return
    
    for plugin_id in os.listdir(BUNDLED_PLUGINS_DIR):
        bundled_dir = os.path.join(BUNDLED_PLUGINS_DIR, plugin_id)
        if not os.path.isdir(bundled_dir):
            continue
        
        # Check if this plugin has a lib/ directory (needs special handling)
        lib_dir = os.path.join(bundled_dir, "lib")
        if not os.path.exists(lib_dir):
            continue
        
        installed_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
        installed_lib = os.path.join(installed_dir, "lib")
        
        # Only copy lib/ if plugin is already installed but lib/ is missing
        if os.path.exists(installed_dir) and not os.path.exists(installed_lib):
            shutil.copytree(lib_dir, installed_lib)
            print(f"[Plugins] Auto-installed lib/ for {plugin_id}")

# Run auto-install on startup
auto_install_bundled_plugins()

# Simple file lock for config
import threading
_plugin_config_lock = threading.Lock()

def validate_plugin_id(plugin_id: str) -> bool:
    """Validate plugin ID to prevent path traversal attacks"""
    if not plugin_id:
        return False
    # Only allow alphanumeric, dash, underscore
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', plugin_id):
        return False
    # Prevent path traversal
    if '..' in plugin_id or '/' in plugin_id or '\\' in plugin_id:
        return False
    return True

def load_plugin_config() -> dict:
    """Load plugin configuration from file (thread-safe)"""
    with _plugin_config_lock:
        if os.path.exists(PLUGINS_CONFIG_FILE):
            try:
                with open(PLUGINS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load plugin config: {e}")
        return {"plugins": {}, "api_keys": {}}

def save_plugin_config(config: dict):
    """Save plugin configuration to file (thread-safe)"""
    with _plugin_config_lock:
        try:
            with open(PLUGINS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}")

def get_installed_plugins() -> List[dict]:
    """Get list of installed plugins with their config"""
    plugins = []
    config = load_plugin_config()
    
    if not os.path.exists(PLUGINS_INSTALLED_DIR):
        return plugins
    
    for plugin_id in os.listdir(PLUGINS_INSTALLED_DIR):
        plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        
        if os.path.isdir(plugin_dir) and os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                
                # Merge with config
                plugin_config = config.get("plugins", {}).get(plugin_id, {})
                # Default to False (disabled) for plugins without explicit config
                # This prevents auto-enabling of plugins after updates/restarts
                manifest["enabled"] = plugin_config.get("enabled", False)
                manifest["settings_values"] = plugin_config.get("settings_values", {})
                plugins.append(manifest)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_id}: {e}")
    
    return plugins

@app.get("/api/plugins")
async def get_plugins():
    """Get list of installed plugins"""
    return get_installed_plugins()

@app.get("/api/plugins/market")
async def get_plugin_market():
    """Get plugin market listing from index.json"""
    try:
        market_index = os.path.join("Plugins", "Plugin_market", "index.json")
        if os.path.exists(market_index):
            with open(market_index, "r", encoding="utf-8") as f:
                market_data = json.load(f)
                return market_data
        else:
            logger.warning(f"Plugin market index not found: {market_index}")
            return {"plugins": []}
    except Exception as e:
        logger.error(f"Error loading plugin market: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/plugins/install")
async def install_plugin(request: PluginInstallRequest):
    """Install a plugin from URL"""
    import zipfile
    import shutil
    import tempfile
    
    source_url = request.source_url.rstrip("/")
    plugin_dir = None  # Track for cleanup on failure
    
    try:
        session = await get_http_session()
        
        # Determine if it's a directory URL or zip URL
        if source_url.endswith(".zip"):
            # Download zip file with size limit
            async with session.get(source_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return JSONResponse({"success": False, "error": f"Failed to download: HTTP {resp.status}"}, status_code=400)
                
                # Check content length if available
                content_length = resp.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_PLUGIN_SIZE:
                    return JSONResponse({"success": False, "error": f"Plugin too large (max {MAX_PLUGIN_SIZE // (1024*1024)}MB)"}, status_code=400)
                
                zip_content = await resp.read()
                if len(zip_content) > MAX_PLUGIN_SIZE:
                    return JSONResponse({"success": False, "error": f"Plugin too large (max {MAX_PLUGIN_SIZE // (1024*1024)}MB)"}, status_code=400)
            
            # Extract zip
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "plugin.zip")
                with open(zip_path, "wb") as f:
                    f.write(zip_content)
                
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        # Check for zip bomb (total uncompressed size)
                        total_size = sum(info.file_size for info in zf.infolist())
                        if total_size > MAX_PLUGIN_SIZE * 10:  # 10x compression ratio limit
                            return JSONResponse({"success": False, "error": "Plugin archive too large when extracted"}, status_code=400)
                        zf.extractall(temp_dir)
                except zipfile.BadZipFile:
                    return JSONResponse({"success": False, "error": "Invalid zip file"}, status_code=400)
                
                # Find manifest.json
                manifest_path = None
                plugin_source_dir = None
                for root, dirs, files in os.walk(temp_dir):
                    if "manifest.json" in files:
                        manifest_path = os.path.join(root, "manifest.json")
                        plugin_source_dir = root
                        break
                
                if not manifest_path:
                    return JSONResponse({"success": False, "error": "No manifest.json found in zip"}, status_code=400)
                
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                
                plugin_id = manifest.get("id")
                if not plugin_id:
                    return JSONResponse({"success": False, "error": "Plugin manifest missing 'id'"}, status_code=400)
                
                # Validate plugin ID
                if not validate_plugin_id(plugin_id):
                    return JSONResponse({"success": False, "error": "Invalid plugin ID (only alphanumeric, dash, underscore allowed)"}, status_code=400)
                
                # Copy to installed directory
                plugin_dest_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
                if os.path.exists(plugin_dest_dir):
                    shutil.rmtree(plugin_dest_dir)
                shutil.copytree(plugin_source_dir, plugin_dest_dir)
        else:
            # It's a GitHub raw directory URL, download individual files
            # First get manifest.json
            manifest_url = f"{source_url}/manifest.json"
            async with session.get(manifest_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return JSONResponse({"success": False, "error": f"Failed to fetch manifest: HTTP {resp.status}"}, status_code=400)
                try:
                    # GitHub raw returns text/plain, so we need to parse manually
                    manifest_text = await resp.text()
                    manifest = json.loads(manifest_text)
                except Exception as e:
                    return JSONResponse({"success": False, "error": f"Invalid manifest.json format: {str(e)}"}, status_code=400)
            
            plugin_id = manifest.get("id")
            if not plugin_id:
                return JSONResponse({"success": False, "error": "Plugin manifest missing 'id'"}, status_code=400)
            
            # Validate plugin ID
            if not validate_plugin_id(plugin_id):
                return JSONResponse({"success": False, "error": "Invalid plugin ID (only alphanumeric, dash, underscore allowed)"}, status_code=400)
            
            # Create plugin directory
            plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
            os.makedirs(plugin_dir, exist_ok=True)
            
            # Save manifest
            with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            
            # Download main.js (required)
            main_js = manifest.get("main", "main.js")
            main_url = f"{source_url}/{main_js}"
            async with session.get(main_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    # Cleanup on failure
                    if plugin_dir and os.path.exists(plugin_dir):
                        shutil.rmtree(plugin_dir)
                    return JSONResponse({"success": False, "error": f"Failed to download main.js: HTTP {resp.status}"}, status_code=400)
                main_content = await resp.text()
                with open(os.path.join(plugin_dir, main_js), "w", encoding="utf-8") as f:
                    f.write(main_content)
            
            # Download icon (optional)
            icon_file = manifest.get("icon", "icon.png")
            icon_url = f"{source_url}/{icon_file}"
            try:
                async with session.get(icon_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        icon_content = await resp.read()
                        with open(os.path.join(plugin_dir, icon_file), "wb") as f:
                            f.write(icon_content)
            except Exception:
                pass  # Icon is optional
        
        # Add to config
        config = load_plugin_config()
        if "plugins" not in config:
            config["plugins"] = {}
        config["plugins"][plugin_id] = {"enabled": True, "settings_values": {}}
        save_plugin_config(config)
        
        logger.info(f"Plugin installed: {plugin_id}")
        return {"success": True, "plugin_id": plugin_id, "manifest": manifest}
        
    except Exception as e:
        # Cleanup on unexpected error
        if plugin_dir and os.path.exists(plugin_dir):
            try:
                import shutil
                shutil.rmtree(plugin_dir)
            except:
                pass
        logger.error(f"Plugin install error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/plugins/upload")
async def upload_plugin(file: UploadFile = File(...)):
    """Upload and install a plugin from zip file"""
    import zipfile
    import shutil
    import tempfile
    
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return JSONResponse({"success": False, "error": "Only .zip files are supported"}, status_code=400)
    
    try:
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_PLUGIN_SIZE:
            return JSONResponse({"success": False, "error": f"Plugin too large (max {MAX_PLUGIN_SIZE // (1024*1024)}MB)"}, status_code=400)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "plugin.zip")
            with open(zip_path, "wb") as f:
                f.write(content)
            
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Check for zip bomb
                    total_size = sum(info.file_size for info in zf.infolist())
                    if total_size > MAX_PLUGIN_SIZE * 10:
                        return JSONResponse({"success": False, "error": "Plugin archive too large when extracted"}, status_code=400)
                    zf.extractall(temp_dir)
            except zipfile.BadZipFile:
                return JSONResponse({"success": False, "error": "Invalid zip file"}, status_code=400)
            
            # Find manifest.json
            manifest_path = None
            plugin_source_dir = None
            for root, dirs, files in os.walk(temp_dir):
                if "manifest.json" in files:
                    manifest_path = os.path.join(root, "manifest.json")
                    plugin_source_dir = root
                    break
            
            if not manifest_path:
                return JSONResponse({"success": False, "error": "No manifest.json found in zip"}, status_code=400)
            
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                return JSONResponse({"success": False, "error": "Invalid manifest.json format"}, status_code=400)
            
            plugin_id = manifest.get("id")
            if not plugin_id:
                return JSONResponse({"success": False, "error": "Plugin manifest missing 'id'"}, status_code=400)
            
            # Validate plugin ID
            if not validate_plugin_id(plugin_id):
                return JSONResponse({"success": False, "error": "Invalid plugin ID (only alphanumeric, dash, underscore allowed)"}, status_code=400)
            
            # Copy to installed directory
            plugin_dest_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
            if os.path.exists(plugin_dest_dir):
                shutil.rmtree(plugin_dest_dir)
            shutil.copytree(plugin_source_dir, plugin_dest_dir)
        
        # Add to config
        config = load_plugin_config()
        if "plugins" not in config:
            config["plugins"] = {}
        config["plugins"][plugin_id] = {"enabled": True, "settings_values": {}}
        save_plugin_config(config)
        
        logger.info(f"Plugin uploaded: {plugin_id}")
        return {"success": True, "plugin_id": plugin_id, "manifest": manifest}
        
    except Exception as e:
        logger.error(f"Plugin upload error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.delete("/api/plugins/{plugin_id}")
async def uninstall_plugin(plugin_id: str):
    """Uninstall a plugin"""
    import shutil
    
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"success": False, "error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    
    if not os.path.exists(plugin_dir):
        return JSONResponse({"success": False, "error": "Plugin not found"}, status_code=404)
    
    try:
        shutil.rmtree(plugin_dir)
        
        # Remove from config
        config = load_plugin_config()
        if "plugins" in config and plugin_id in config["plugins"]:
            del config["plugins"][plugin_id]
            save_plugin_config(config)
        
        logger.info(f"Plugin uninstalled: {plugin_id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Plugin uninstall error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/plugins/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str, request: PluginToggleRequest):
    """Enable or disable a plugin"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"success": False, "error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    
    if not os.path.exists(plugin_dir):
        return JSONResponse({"success": False, "error": "Plugin not found"}, status_code=404)
    
    config = load_plugin_config()
    if "plugins" not in config:
        config["plugins"] = {}
    if plugin_id not in config["plugins"]:
        config["plugins"][plugin_id] = {}
    
    config["plugins"][plugin_id]["enabled"] = request.enabled
    save_plugin_config(config)
    
    return {"success": True, "enabled": request.enabled}

@app.post("/api/plugins/{plugin_id}/settings")
async def update_plugin_settings(plugin_id: str, request: PluginSettingsUpdate):
    """Update plugin settings"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"success": False, "error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    
    if not os.path.exists(plugin_dir):
        return JSONResponse({"success": False, "error": "Plugin not found"}, status_code=404)
    
    config = load_plugin_config()
    if "plugins" not in config:
        config["plugins"] = {}
    if plugin_id not in config["plugins"]:
        config["plugins"][plugin_id] = {}
    
    config["plugins"][plugin_id]["settings_values"] = request.settings
    save_plugin_config(config)
    
    return {"success": True}

@app.get("/api/plugins/{plugin_id}/main.js")
async def get_plugin_js(plugin_id: str):
    """Get plugin JavaScript file"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    manifest_path = os.path.join(plugin_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        return JSONResponse({"error": "Plugin not found"}, status_code=404)
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        main_file = manifest.get("main", "main.js")
        # Prevent path traversal in main file name
        main_file = os.path.basename(main_file)
        main_path = os.path.join(plugin_dir, main_file)
        
        if not os.path.exists(main_path):
            return JSONResponse({"error": "Plugin main.js not found"}, status_code=404)
        
        return FileResponse(main_path, media_type="application/javascript")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/plugins/{plugin_id}/lib/{filename:path}")
async def get_plugin_lib(plugin_id: str, filename: str):
    """Get plugin library file from lib directory (supports subdirectories like fonts/)"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"error": "Invalid plugin ID"}, status_code=400)
    
    # Normalize and validate filename to prevent path traversal
    # Allow subdirectories like "fonts/file.woff2" but block ".." and absolute paths
    filename = os.path.normpath(filename)
    if not filename or filename.startswith('.') or '..' in filename or filename.startswith('/'):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    lib_dir = os.path.join(plugin_dir, "lib")
    lib_path = os.path.join(lib_dir, filename)
    
    # Security check: ensure the resolved path is within lib directory
    lib_path = os.path.realpath(lib_path)
    lib_dir = os.path.realpath(lib_dir)
    if not lib_path.startswith(lib_dir + os.sep) and lib_path != lib_dir:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    
    if not os.path.exists(lib_path) or not os.path.isfile(lib_path):
        return JSONResponse({"error": "Library file not found"}, status_code=404)
    
    # Determine MIME type based on file extension
    media_type = "application/octet-stream"
    if filename.endswith(".js"):
        media_type = "application/javascript"
    elif filename.endswith(".css"):
        media_type = "text/css"
    elif filename.endswith(".json"):
        media_type = "application/json"
    elif filename.endswith(".woff2"):
        media_type = "font/woff2"
    elif filename.endswith(".woff"):
        media_type = "font/woff"
    elif filename.endswith(".ttf"):
        media_type = "font/ttf"
    elif filename.endswith(".eot"):
        media_type = "application/vnd.ms-fontobject"
    
    return FileResponse(lib_path, media_type=media_type)

@app.get("/api/plugins/{plugin_id}/icon")
async def get_plugin_icon(plugin_id: str):
    """Get plugin icon"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    manifest_path = os.path.join(plugin_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        return JSONResponse({"error": "Plugin not found"}, status_code=404)
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        icon_file = manifest.get("icon", "icon.png")
        # Prevent path traversal in icon file name
        icon_file = os.path.basename(icon_file)
        icon_path = os.path.join(plugin_dir, icon_file)
        
        if not os.path.exists(icon_path):
            return JSONResponse({"error": "Icon not found"}, status_code=404)
        
        # Detect MIME type from extension
        ext = icon_file.lower().split('.')[-1] if '.' in icon_file else 'png'
        mime_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'svg': 'image/svg+xml',
            'webp': 'image/webp',
            'ico': 'image/x-icon'
        }
        media_type = mime_types.get(ext, 'image/png')
        
        return FileResponse(icon_path, media_type=media_type)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/plugins/{plugin_id}/manifest")
async def get_plugin_manifest(plugin_id: str):
    """Get plugin manifest"""
    # Validate plugin ID
    if not validate_plugin_id(plugin_id):
        return JSONResponse({"error": "Invalid plugin ID"}, status_code=400)
    
    plugin_dir = os.path.join(PLUGINS_INSTALLED_DIR, plugin_id)
    manifest_path = os.path.join(plugin_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        return JSONResponse({"error": "Plugin not found"}, status_code=404)
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        # Merge with config
        config = load_plugin_config()
        plugin_config = config.get("plugins", {}).get(plugin_id, {})
        manifest["enabled"] = plugin_config.get("enabled", True)
        manifest["settings_values"] = plugin_config.get("settings_values", {})
        
        return manifest
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/proxy/request")
async def proxy_request(request: ProxyRequest):
    """Generic HTTP proxy for plugins - protects API keys"""
    from urllib.parse import urlparse
    
    # Validate URL
    try:
        parsed = urlparse(request.url)
        if not parsed.scheme in ('http', 'https'):
            return JSONResponse({"success": False, "error": "Only HTTP(S) URLs are allowed"}, status_code=400)
        if not parsed.netloc:
            return JSONResponse({"success": False, "error": "Invalid URL"}, status_code=400)
        # Block internal/private networks (basic SSRF protection)
        hostname = parsed.hostname.lower() if parsed.hostname else ''
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1') or hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
            return JSONResponse({"success": False, "error": "Access to internal networks is not allowed"}, status_code=400)
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid URL format"}, status_code=400)
    
    # Validate HTTP method
    allowed_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH'}
    if request.method.upper() not in allowed_methods:
        return JSONResponse({"success": False, "error": f"Method {request.method} not allowed"}, status_code=400)
    
    config = load_plugin_config()
    api_key = config.get("api_keys", {}).get(request.service_id)
    
    headers = {**request.headers}
    if api_key:
        # Add API key based on common patterns
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
    
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    # Remove potentially dangerous headers
    headers.pop("Host", None)
    headers.pop("Cookie", None)
    
    try:
        session = await get_http_session()
        async with session.request(
            method=request.method.upper(),
            url=request.url,
            headers=headers,
            json=request.body if request.body else None,
            timeout=aiohttp.ClientTimeout(total=30),
            allow_redirects=False  # Prevent redirect-based attacks
        ) as resp:
            try:
                data = await resp.json()
            except:
                text = await resp.text()
                # Limit response size
                data = {"raw": text[:50000] if len(text) > 50000 else text}
            
            if resp.status != 200:
                return JSONResponse({"success": False, "error": data, "status": resp.status}, status_code=resp.status)
            
            return {"success": True, "data": data}
    except asyncio.TimeoutError:
        return JSONResponse({"success": False, "error": "Request timeout"}, status_code=504)
    except aiohttp.ClientError as e:
        logger.error(f"Proxy request client error: {e}")
        return JSONResponse({"success": False, "error": f"Network error: {str(e)}"}, status_code=502)
    except Exception as e:
        logger.error(f"Proxy request error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# Maximum file size for proxy upload (20MB)
MAX_PROXY_UPLOAD_SIZE = int(os.environ.get("MAX_PROXY_UPLOAD_SIZE", str(20 * 1024 * 1024)))

@app.post("/api/proxy/upload")
async def proxy_upload(
    file: UploadFile = File(...),
    service_id: str = Form(...),
    url: str = Form(...),
    extra_fields: str = Form(default="{}"),
    file_field_name: str = Form(default="file")
):
    """
    Proxy file upload to external API (e.g., Whisper, OCR services).
    Protects API keys by adding them server-side.
    
    Args:
        file: The file to upload
        service_id: Service identifier for API key lookup
        url: Target URL to upload to
        extra_fields: JSON string of additional form fields
        file_field_name: Name of the file field in the multipart form (default: "file")
    """
    from urllib.parse import urlparse
    import aiohttp
    
    # Validate URL
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return JSONResponse({"success": False, "error": "Only HTTP(S) URLs are allowed"}, status_code=400)
        if not parsed.netloc:
            return JSONResponse({"success": False, "error": "Invalid URL"}, status_code=400)
        # Block internal/private networks (SSRF protection)
        hostname = parsed.hostname.lower() if parsed.hostname else ''
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1') or hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
            return JSONResponse({"success": False, "error": "Access to internal networks is not allowed"}, status_code=400)
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid URL format"}, status_code=400)
    
    # Read and validate file size
    try:
        file_content = await file.read()
        if len(file_content) > MAX_PROXY_UPLOAD_SIZE:
            return JSONResponse({
                "success": False, 
                "error": f"File too large (max {MAX_PROXY_UPLOAD_SIZE // (1024*1024)}MB)"
            }, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Failed to read file: {str(e)}"}, status_code=400)
    
    # Parse extra fields
    try:
        extra = json.loads(extra_fields) if extra_fields else {}
        if not isinstance(extra, dict):
            extra = {}
    except json.JSONDecodeError:
        extra = {}
    
    # Get API key
    config = load_plugin_config()
    api_key = config.get("api_keys", {}).get(service_id)
    
    # Build headers
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        # Build multipart form data
        form_data = aiohttp.FormData()
        
        # Add the file
        form_data.add_field(
            file_field_name,
            file_content,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream"
        )
        
        # Add extra fields
        for key, value in extra.items():
            if isinstance(value, (dict, list)):
                form_data.add_field(key, json.dumps(value))
            else:
                form_data.add_field(key, str(value))
        
        # Send request
        session = await get_http_session()
        async with session.post(
            url,
            data=form_data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),  # Longer timeout for file uploads
            allow_redirects=False
        ) as resp:
            try:
                data = await resp.json()
            except:
                text = await resp.text()
                data = {"raw": text[:50000] if len(text) > 50000 else text}
            
            if resp.status != 200:
                return JSONResponse({
                    "success": False, 
                    "error": data, 
                    "status": resp.status
                }, status_code=resp.status)
            
            return {"success": True, "data": data}
            
    except asyncio.TimeoutError:
        return JSONResponse({"success": False, "error": "Upload timeout"}, status_code=504)
    except aiohttp.ClientError as e:
        logger.error(f"Proxy upload client error: {e}")
        return JSONResponse({"success": False, "error": f"Network error: {str(e)}"}, status_code=502)
    except Exception as e:
        logger.error(f"Proxy upload error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/plugins/api-keys")
async def get_api_keys():
    """Get masked API keys for display (shows first 4 and last 4 chars)"""
    try:
        config = load_plugin_config()
        api_keys = config.get("api_keys", {})
        
        # Return masked keys for display
        masked = {}
        for service_id, key in api_keys.items():
            if key and len(key) > 10:
                masked[service_id] = key[:4] + '*' * (len(key) - 8) + key[-4:]
            elif key:
                masked[service_id] = '*' * len(key)
        
        return {"api_keys": masked}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/plugins/api-key")
async def save_api_key(request: Request):
    """Save API key for a service"""
    import re
    
    try:
        body = await request.json()
        service_id = body.get("service_id")
        api_key = body.get("api_key", "")
        
        if not service_id:
            return JSONResponse({"success": False, "error": "service_id required"}, status_code=400)
        
        # Validate service_id format (alphanumeric, dash, underscore, dot)
        if not re.match(r'^[a-zA-Z0-9_.-]+$', service_id):
            return JSONResponse({"success": False, "error": "Invalid service_id format"}, status_code=400)
        
        # Limit service_id and api_key length
        if len(service_id) > 100:
            return JSONResponse({"success": False, "error": "service_id too long"}, status_code=400)
        if len(api_key) > 500:
            return JSONResponse({"success": False, "error": "api_key too long"}, status_code=400)
        
        config = load_plugin_config()
        if "api_keys" not in config:
            config["api_keys"] = {}
        
        if api_key:
            config["api_keys"][service_id] = api_key
        elif service_id in config["api_keys"]:
            del config["api_keys"][service_id]
        
        save_plugin_config(config)
        return {"success": True}
    except json.JSONDecodeError:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# Custom StaticFiles with caching headers
class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        # Add cache headers for versioned static files (js, css with ?v=)
        if path.endswith(('.js', '.css', '.woff2', '.png', '.jpg', '.ico')):
            # Long cache for static assets (1 year)
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif path.endswith('.html') or path == '' or path == '/':
            # No cache for HTML (always revalidate)
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        return response

# Static files with GZip compression and caching - must be last
# Note: app.mount() creates a sub-application that bypasses main app middleware
# So we wrap StaticFiles with GZipMiddleware directly
from starlette.middleware.gzip import GZipMiddleware as StaticGZip
static_app = CachedStaticFiles(directory="static", html=True)
gzipped_static_app = StaticGZip(static_app, minimum_size=500)
app.mount("/", gzipped_static_app, name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 51111))
    logger.info(f"ChatRaw starting on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

