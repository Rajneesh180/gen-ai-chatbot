# ---- Stage 1: Build the React frontend ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend + serve frontend ----
FROM python:3.9-slim

# HuggingFace Spaces needs port 7860
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy only the index/data files needed at runtime (NOT the 3.4GB repos)
COPY data/faiss.index data/bm25.pkl data/metadata.pkl ./data/

# Copy the built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Pre-download the sentence-transformers model so cold starts are instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 7860

# Start the FastAPI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
