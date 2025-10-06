#!/usr/bin/env python3
import os, pathlib, json, time
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from PyPDF2 import PdfReader
import openai
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

BASE_DIR = pathlib.Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploaded"
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = BASE_DIR / "ai_assistant.db"
FAISS_INDEX_PATH = BASE_DIR / "faiss_index.bin"
FAISS_META_PATH = BASE_DIR / "faiss_meta.json"

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. Set it in .env or environment. Chat responses will fail.")

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024  # 12 MB

limiter = Limiter(app, key_func=get_remote_address, default_limits=["500 per day", "200 per hour"])

# Database models
Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    role = Column(String(32))
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DocumentChunk(Base):
    __tablename__ = 'doc_chunks'
    id = Column(Integer, primary_key=True)
    file_name = Column(String(256))
    chunk_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# Embeddings & FAISS
EMB_MODEL = "all-MiniLM-L6-v2"
EMB_DIM = 384
print("Loading embedding model (may take a minute on first run)...")
embedder = SentenceTransformer(EMB_MODEL)

if pathlib.Path(FAISS_INDEX_PATH).exists():
    index = faiss.read_index(str(FAISS_INDEX_PATH))
    with open(FAISS_META_PATH, "r", encoding="utf-8") as f:
        faiss_meta = json.load(f)
else:
    index = faiss.IndexFlatL2(EMB_DIM)
    faiss_meta = {}

def save_faiss():
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    with open(FAISS_META_PATH, "w", encoding="utf-8") as f:
        json.dump(faiss_meta, f, ensure_ascii=False, indent=2)

def embed_texts(texts):
    embs = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embs.astype("float32")

def chunk_text(text, chunk_size=600, overlap=100):
    words = text.split()
    chunks = []
    i=0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

# Routes
@app.route('/')
def index():
    # Frontend is static nginx in Docker; also provide a simple message
    return jsonify({"status":"Ali'shere.AI backend. Use the frontend to chat."})

@app.route('/api/upload', methods=['POST'])
@limiter.limit("20 per hour")
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify({'error':'no file uploaded'}), 400
    filename = secure_filename(f.filename)
    if not (filename.lower().endswith('.txt') or filename.lower().endswith('.pdf')):
        return jsonify({'error':'unsupported file type'}), 400
    dest = UPLOAD_DIR / filename
    f.save(dest)
    # extract text
    text = ""
    if filename.lower().endswith('.txt'):
        text = open(dest, 'r', encoding='utf-8', errors='ignore').read()
    else:
        reader = PdfReader(dest)
        pages = [p.extract_text() or '' for p in reader.pages]
        text = '\\n'.join(pages)
    chunks = chunk_text(text)
    embs = embed_texts(chunks)
    start = index.ntotal
    index.add(embs)
    session = SessionLocal()
    for i, chunk in enumerate(chunks):
        db_chunk = DocumentChunk(file_name=filename, chunk_text=chunk)
        session.add(db_chunk); session.commit()
        faiss_meta[str(start + i)] = {'db_id': db_chunk.id, 'file_name': filename}
    session.close()
    save_faiss()
    return jsonify({'status':'ok', 'chunks': len(chunks)})

@app.route('/api/chat', methods=['POST'])
@limiter.limit("200 per hour")
def chat():
    data = request.get_json() or {}
    msg = data.get('message','').strip()
    if not msg:
        return jsonify({'error':'empty message'}), 400
    session = SessionLocal()
    user_msg = Message(role='user', content=msg)
    session.add(user_msg); session.commit()
    # search faiss
    q_emb = embed_texts([msg])
    retrieved = []
    if index.ntotal > 0:
        D, I = index.search(q_emb, 5)
        for fid in I[0]:
            if fid == -1: continue
            meta = faiss_meta.get(str(int(fid)))
            if not meta: continue
            chunk = session.query(DocumentChunk).filter_by(id=meta['db_id']).first()
            if chunk:
                retrieved.append({'file': chunk.file_name, 'text': chunk.chunk_text})
    system_prompt = "You are a helpful assistant. Use the retrieved documents when answering. Be concise."
    if retrieved:
        doc_texts = '\\n\\n---\\n\\n'.join([f\"Source: {r['file']}\\n{r['text']}\" for r in retrieved])
        system_prompt += "\\n\\nRetrieved documents:\\n" + doc_texts[:4000]
    messages = [{"role":"system","content":system_prompt},{"role":"user","content":msg}]
    try:
        resp = openai.ChatCompletion.create(model='gpt-4o-mini', messages=messages, max_tokens=400, temperature=0.2)
        reply = resp['choices'][0]['message']['content'].strip()
    except Exception as e:
        reply = f"LLM error: {e}"
    assistant_msg = Message(role='assistant', content=reply)
    session.add(assistant_msg); session.commit(); session.close()
    return jsonify({'reply': reply})

@app.route('/api/history', methods=['GET'])
def history():
    session = SessionLocal()
    msgs = session.query(Message).order_by(Message.id.asc()).all()
    out = [{'role':m.role,'content':m.content,'created_at':str(m.created_at)} for m in msgs]
    session.close()
    return jsonify(out)

@app.route('/api/reset', methods=['POST'])
def reset():
    # Clears only the chat messages (not the FAISS index)
    session = SessionLocal()
    session.query(Message).delete(); session.commit(); session.close()
    return jsonify({'status':'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
