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
from datetime import datetime
from typing import Optional, List, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import math

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

class RAGSettings(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    score_threshold: float = 0.5

class UISettings(BaseModel):
    logo_data: str = ""
    logo_text: str = "ChatRaw"
    subtitle: str = ""
    theme_mode: str = "dark"
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
                    print("[DB] Migrating embeddings from JSON to binary format...")
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
                    print(f"[DB] Migrated {len(rows)} embeddings to binary format")
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
    
    async def chat_stream(self, chat_id: str, message: str, use_rag: bool = False, image_base64: str = "", web_content: str = "", web_url: str = "") -> AsyncGenerator[str, None]:
        """Stream chat responses"""
        config = self.db.get_model_by_type("chat")
        if not config or not config.api_url or not config.model_id:
            yield json.dumps({"error": "Chat model not configured"})
            return
        
        settings = self.db.get_settings()
        
        # Build messages
        history = self.db.get_messages(chat_id)
        messages = [{"role": m.role, "content": m.content} for m in history]
        
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
        
        full_response = ""
        
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
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        yield json.dumps({"content": content})
                            except json.JSONDecodeError:
                                continue
            
            # Save response
            if full_response:
                self.db.add_message(chat_id, "assistant", full_response)
                
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
    
    async def chat_non_stream(self, chat_id: str, message: str, use_rag: bool = False, image_base64: str = "", web_content: str = "", web_url: str = "") -> dict:
        """Non-streaming chat, returns dict with content and references"""
        config = self.db.get_model_by_type("chat")
        if not config or not config.api_url or not config.model_id:
            raise HTTPException(status_code=500, detail="Chat model not configured")
        
        settings = self.db.get_settings()
        
        history = self.db.get_messages(chat_id)
        messages = [{"role": m.role, "content": m.content} for m in history]
        
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
        
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise HTTPException(status_code=500, detail=f"API error: {error_text}")
            
            data = await resp.json()
            content = data["choices"][0]["message"]["content"]
            
            self.db.add_message(chat_id, "assistant", content)
            
            messages_count = len(self.db.get_messages(chat_id))
            if messages_count <= 2:
                title = message[:30] + "..." if len(message) > 30 else message
                self.db.update_chat_title(chat_id, title)
            
            return {"content": content, "references": rag_references}
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text"""
        config = self.db.get_model_by_type("embedding")
        if not config or not config.api_url or not config.model_id:
            print("[Embedding] No embedding model configured")
            return []
        
        url = config.api_url.rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        
        payload = {"model": config.model_id, "input": text}
        
        try:
            session = await get_http_session()
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[Embedding] API error ({resp.status}): {error_text[:200]}")
                    return []
                data = await resp.json()
                embedding = data["data"][0]["embedding"]
                print(f"[Embedding] Got embedding with {len(embedding)} dimensions")
                return embedding
        except Exception as e:
            print(f"[Embedding] Exception: {e}")
            return []
    
    async def rerank(self, query: str, documents: List[str]) -> List[dict]:
        """Rerank documents using rerank model, returns list of {index, score}"""
        config = self.db.get_model_by_type("rerank")
        if not config or not config.api_url or not config.model_id:
            print("[Rerank] No rerank model configured, skipping rerank")
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
            print(f"[Rerank] Calling rerank API with {len(documents)} documents")
            session = await get_http_session()
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[Rerank] API error ({resp.status}): {error_text[:200]}")
                    return []
                
                data = await resp.json()
                # Handle different response formats
                results = data.get("results") or data.get("data") or []
                print(f"[Rerank] Got {len(results)} reranked results")
                return results
        except Exception as e:
            print(f"[Rerank] Exception: {e}")
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
                print(f"[RAG] Using reranked results, top score: {results[0]['score'] if results else 'N/A'}")
            else:
                # Fallback to embedding scores if rerank failed
                results = candidates[:settings.rag_settings.top_k]
                print("[RAG] Rerank failed, using embedding scores")
        else:
            # No rerank model, use embedding scores directly
            results = candidates[:settings.rag_settings.top_k]
            print("[RAG] No rerank model configured, using embedding scores")
        
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

db = Database(os.path.join(DATA_DIR, "chatraw.db"))
llm_service = LLMService(db)
rag_service = RAGService(db, llm_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle: startup and shutdown"""
    print("🚀 Starting ChatRaw...")
    yield
    # Cleanup on shutdown
    print("🛑 Shutting down ChatRaw...")
    await close_http_session()

app = FastAPI(title="ChatRaw", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ API Routes ============

@app.get("/api/settings")
async def get_settings():
    return db.get_settings().model_dump()

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
            async for chunk in llm_service.chat_stream(chat_id, message, use_rag, image_base64, web_content, web_url):
                yield chunk + "\n"
        
        return StreamingResponse(
            generate(), 
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming response
        result = await llm_service.chat_non_stream(chat_id, message, use_rag, image_base64, web_content, web_url)
        return {"chat_id": chat_id, "content": result["content"], "references": result["references"]}

@app.get("/api/documents")
async def get_documents():
    return db.get_documents()

def parse_pdf(content: bytes) -> str:
    """Parse PDF file content to text"""
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

def parse_docx(content: bytes) -> str:
    """Parse DOCX file content to text"""
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

def parse_document_content(filename: str, content: bytes) -> str:
    """Parse document based on file extension"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    if ext == 'pdf':
        return parse_pdf(content)
    elif ext in ('docx', 'doc'):
        if ext == 'doc':
            raise ValueError("Old .doc format not supported. Please convert to .docx")
        return parse_docx(content)
    elif ext in ('txt', 'md', 'markdown', 'text'):
        try:
            return content.decode("utf-8")
        except:
            return content.decode("latin-1")
    else:
        # Try to decode as text
        try:
            return content.decode("utf-8")
        except:
            return content.decode("latin-1")

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    
    # Parse document based on file type
    try:
        text = parse_document_content(file.filename, content)
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
        
        for i, chunk in enumerate(chunks):
            embedding = await llm_service.get_embedding(chunk)
            db.save_chunk(doc_id, chunk, embedding if embedding else None)
            progress = int((i + 1) / total * 100)
            yield json.dumps({"status": "embedding", "progress": progress, "current": i + 1, "total": total}) + "\n"
        
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
    b64 = base64.b64encode(content).decode("utf-8")
    return {"success": True, "filename": file.filename, "base64": b64}

@app.post("/api/upload/document")
async def upload_document_for_chat(file: UploadFile = File(...)):
    """Parse a document and return its content for chat attachment"""
    content = await file.read()
    
    try:
        text = parse_document_content(file.filename, content)
    except ValueError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)
    
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

class ParseUrlRequest(BaseModel):
    url: str

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

# Static files - must be last
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 51111))
    print(f"🚀 ChatRaw running at: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

