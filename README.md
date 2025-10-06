# Ali'shere.AI — Simple Edition

This is the **simple** edition of Ali'shere.AI (no register/login). Features:
- Simple, clean HTML/CSS frontend (light theme)
- Flask backend (no auth) — chat, upload, persistent memory (SQLite)
- FAISS + sentence-transformers for searchable long-term memory (RAG)
- Docker + docker-compose included for easy deployment
- CC0 license (public domain)

## Quick start (Docker)
1. Copy `.env.example` to `.env` and fill `OPENAI_API_KEY`.
2. Build & run:
   ```bash
   docker compose up --build
   ```
3. Visit `http://localhost:8080` for the frontend and `http://localhost:5000` for backend API (if needed).

## Quick start (local, without Docker)
1. Create a Python venv and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
3. Run backend:
   ```bash
   cd backend
   python app.py
   ```
4. Open `frontend/index.html` in your browser (or serve it with a static server).

Notes:
- The sentence-transformers model will download on first run (may take a minute).
- Uploaded files, SQLite DB, and FAISS index are stored in `backend/` and are excluded from the repo (.gitignore recommends).
- This project is CC0 (public domain). Enjoy!

Prepared for: muhammad007ali098-stack
