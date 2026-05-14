# Optimization Agent — single-container deployment image.
#
# Build:  docker build -t or-agent .
# Run:    docker run -p 8000:8000 \
#             -e LLM_BACKEND=groq \
#             -e GROQ_API_KEY=$GROQ_API_KEY \
#             -e GROQ_CLASSIFICATION_MODEL=llama-3.1-8b-instant \
#             or-agent
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps:
#   glpk-utils → provides `glpsol`, the LP/MIP solver Pyomo shells out to
#   build-essential → some Python wheels still compile on slim base
#   curl → docker HEALTHCHECK probe
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        glpk-utils \
        build-essential \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache survives source-only changes)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Copy the rest of the source (filtered by .dockerignore)
COPY . /app

EXPOSE 8000

# Default to ollama backend — deployment must override LLM_BACKEND=groq + GROQ_API_KEY.
ENV LLM_BACKEND=ollama \
    API_HOST=0.0.0.0 \
    API_PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
