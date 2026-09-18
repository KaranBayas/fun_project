# Secure Digital DMS — AI Services API

Centralized AI services gateway for the **Secure Digital Document Management System (SIH 2026)**.  
Combines **ArcFace biometric face recognition** and **BGE-M3 semantic document search** under a single FastAPI application protected by one shared API key.

---

## Architecture

```
Spring Boot Backend
        |
        |  X-API-Key: <AI_SERVICES_API_KEY>
        v
Unified FastAPI AI Services API  :8000
        |
        +──── Face Recognition  (InsightFace / ArcFace / buffalo_l)
        |
        +──── Semantic Search   (BAAI/bge-m3 → Qdrant)
```

---

## Project Structure

```
sih_2026/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application, lifespan, exception handlers
│   ├── config.py            # Settings (pydantic-settings, loads .env)
│   ├── security.py          # Shared API key dependency (hmac.compare_digest)
│   ├── errors.py            # Domain exception hierarchy
│   ├── api/
│   │   └── routes/
│   │       ├── face.py      # POST /api/v1/face/register  /api/v1/face/verify
│   │       └── documents.py # POST /api/v1/documents/index  /api/v1/documents/search
│   ├── services/
│   │   ├── face/
│   │   │   ├── face_service.py    # InsightFace embedding + cosine similarity
│   │   │   ├── face_database.py   # Fernet-encrypted face DB (JSON)
│   │   │   └── image_service.py   # Image decode / validation
│   │   └── search/
│   │       ├── embedding_service.py  # BGE-M3 sentence-transformers
│   │       ├── vector_service.py     # Qdrant async client wrapper
│   │       ├── document_processor.py # Extract → chunk → embed pipeline
│   │       ├── text_extractor.py     # PDF/DOCX/XLSX/PPTX/TXT/CSV/Image
│   │       ├── ocr_service.py        # PaddleOCR
│   │       └── chunker.py            # Fixed-size chunking with overlap
│   ├── db/
│   │   └── qdrant_client.py   # AsyncQdrantClient factory
│   ├── models/
│   │   └── schemas.py         # Pydantic request/response models
│   └── utils/
│       └── logging.py         # Structured logger
├── face_recognition/
│   └── face_data/
│       └── face_database.json # Encrypted face embeddings (Fernet)
├── tests/
│   ├── conftest.py
│   ├── test_authentication.py
│   ├── test_existing_face_db.py
│   ├── test_health.py
│   ├── test_openapi_swagger.py
│   ├── test_unified_documents.py
│   └── test_unified_face.py
├── .env                   # Real secrets — DO NOT commit
├── .env.example           # Placeholder template — safe to commit
├── requirements.txt       # Single unified dependency file
├── Dockerfile             # Single unified Docker image
├── docker-compose.yml     # FastAPI API + Qdrant
└── pytest.ini
```

---

## Setup

## Direct AWS EC2 Deployment

This service can run directly on an Amazon Linux 2023 **x86_64** EC2 instance;
Docker is not required. Use CPU-only inference. Keep Qdrant private: either run
it on the same host bound to `127.0.0.1`, or expose it only on a private VPC
network/security group.

### 1. Install operating-system prerequisites

Amazon Linux 2023 provides Python 3.12 and uses DNF. The Python packages below
are needed to build/install InsightFace, while the graphics/OpenMP libraries are
used by OpenCV and ONNX Runtime at runtime.

```bash
sudo dnf update -y
sudo dnf install -y python3.12 python3.12-pip python3.12-devel \
  gcc gcc-c++ make mesa-libGL glib2 libgomp git curl tar
```

Legacy `.doc` files are converted by `soffice`; this application therefore
requires LibreOffice at runtime. Amazon Linux documents installing the official
LibreOffice RPM bundle separately. Download the current x86_64 RPM bundle from
the [Amazon Linux LibreOffice guide](https://docs.aws.amazon.com/linux/al2023/ug/al2023-libreoffice.html),
then install its extracted RPMs:

```bash
cd /tmp
# Set LO_VERSION to the stable version selected from the official download page.
LO_VERSION=25.2.5
curl -fLO "https://download.documentfoundation.org/libreoffice/stable/${LO_VERSION}/rpm/x86_64/LibreOffice_${LO_VERSION}_Linux_x86-64_rpm.tar.gz"
tar -xzf "LibreOffice_${LO_VERSION}_Linux_x86-64_rpm.tar.gz"
sudo dnf install -y LibreOffice_*_Linux_x86-64_rpm/RPMS/*.rpm
soffice --version
```

### 2. Clone and install the service

```bash
git clone <YOUR_REPOSITORY_URL> /opt/sih-ai-services
cd /opt/sih-ai-services
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"
```

`requirements.txt` selects the official CPU-only PyTorch wheel for Linux x86_64.
The CUDA value must be `False`; do not install a CUDA or `nvidia-*` package.

### 3. Configure secrets and face data

Create `/opt/sih-ai-services/.env` from `.env.example`, fill in real values, and
protect it. Never commit it. Transfer the existing encrypted
`face_database.json` separately through an approved secure channel if existing
registrations must be retained. The database is intentionally Git-ignored
because encrypted biometric records remain sensitive personal data.

```bash
cp .env.example .env
chmod 600 .env
mkdir -p face_recognition/face_data
# Securely transfer the existing encrypted face_database.json here when needed.
```

Set `QDRANT_URL=http://127.0.0.1:6333` when Qdrant runs locally, or a private
VPC endpoint such as `http://10.0.2.25:6333` for a separate Qdrant host. No
Python change is needed.

### 4. Start Qdrant privately

Install a supported Qdrant x86_64 binary/release following the
[official Qdrant installation guide](https://qdrant.tech/documentation/installation/).
For a single-host deployment, configure Qdrant with
`QDRANT__SERVICE__HOST=127.0.0.1` and persistent local block storage, then
start it before FastAPI. Qdrant recommends a POSIX-compatible SSD/NVMe-backed
filesystem rather than NFS or object storage. Do not open port 6333 in the EC2
security group.

### 5. Start and verify FastAPI

```bash
source /opt/sih-ai-services/.venv/bin/activate
cd /opt/sih-ai-services
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

From the instance, verify `curl http://127.0.0.1:8000/health`; Swagger is at
`http://<EC2_PRIVATE_OR_PUBLIC_DNS>:8000/docs`. Permit inbound TCP 8000 only
from the Spring Boot backend/security group. Do not expose Qdrant (6333/6334).
All non-health API routes still require `X-API-Key`.

### 6. Run with systemd

Create a service unit outside this repository, using a dedicated non-login
service account and an EnvironmentFile that is readable only by that account:

```ini
[Unit]
Description=SIH AI Services API
After=network.target

[Service]
User=sih-ai
Group=sih-ai
WorkingDirectory=/opt/sih-ai-services
EnvironmentFile=/opt/sih-ai-services/.env
ExecStart=/opt/sih-ai-services/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Save it as `/etc/systemd/system/sih-ai-services.service`, then run
`sudo systemctl daemon-reload`, `sudo systemctl enable --now sih-ai-services`,
and `sudo journalctl -u sih-ai-services -f`. Do not place keys in the unit file.

### 1. Prerequisites

- Python 3.12
- Docker + Docker Compose (for Qdrant)

### 2. Virtual Environment

```bash
cd /Users/karanbayas/Documents/sih_2026
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `.env`

Copy the example and fill in your secrets:

```bash
cp .env.example .env
```

Required variables in `.env`:

```
FACE_ENCRYPTION_KEY=<your-existing-fernet-key>
AI_SERVICES_API_KEY=<your-secure-api-key>
```

> **IMPORTANT:** `FACE_ENCRYPTION_KEY` must match the key used when embeddings were originally registered. Changing it will make existing face data unreadable.

Generate a new `AI_SERVICES_API_KEY` if needed:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Starting the Services

### Start Qdrant (vector database)

```bash
# Option 1: Docker Compose (recommended — starts both API + Qdrant)
docker compose up -d

# Option 2: Qdrant only
docker run -d --name dms-ai-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

### Start FastAPI (local development)

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API available at: **http://localhost:8000**

---

## API Reference

### Base URL

```
http://localhost:8000
```

### Authentication

All endpoints except `/health` require the header:

```
X-API-Key: YOUR_API_KEY
```

Missing or invalid key → `HTTP 401 Unauthorized`

```json
{
  "success": false,
  "error_code": "UNAUTHORIZED",
  "message": "Invalid or missing API key."
}
```

---

### Health Check (public — no API key required)

```bash
GET /health

curl http://localhost:8000/health
```

Response:
```json
{"status": "ok", "service": "Secure Digital DMS - AI Services API", "version": "1.0.0"}
```

---

### Face Recognition

#### Register a Face

```bash
POST /api/v1/face/register

curl -X POST http://localhost:8000/api/v1/face/register \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "user_id=OFFICER-001" \
  -F "image=@/path/to/face.jpg"
```

Response:
```json
{"success": true, "user_id": "OFFICER-001"}
```

#### Verify a Face

```bash
POST /api/v1/face/verify

curl -X POST http://localhost:8000/api/v1/face/verify \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "user_id=OFFICER-001" \
  -F "image=@/path/to/face.jpg"
```

Response:
```json
{"success": true, "user_id": "OFFICER-001", "match": true}
```

---

### Semantic Search & Document Indexing

#### Index a Document

```bash
POST /api/v1/documents/index

curl -X POST http://localhost:8000/api/v1/documents/index \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "document_id=DOC-2026-001" \
  -F "case_id=CASE-101" \
  -F "document_type=FIR" \
  -F "file=@/path/to/document.pdf"
```

Response:
```json
{"success": true, "document_id": "DOC-2026-001", "case_id": "CASE-101", "chunks_indexed": 12}
```

#### Search Documents

```bash
POST /api/v1/documents/search

curl -X POST http://localhost:8000/api/v1/documents/search \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "chain of custody evidence", "top_k": 5}'
```

Response:
```json
{
  "results": [
    {"document_id": "DOC-2026-001", "case_id": "CASE-101", "score": 0.92}
  ]
}
```

#### Backward-Compatible Aliases

```bash
POST /api/v1/index-document   # Alias for /api/v1/documents/index
POST /api/v1/search           # Alias for /api/v1/documents/search
```

---

## Swagger / OpenAPI UI

Navigate to: **http://localhost:8000/docs**

1. Click **Authorize** (🔒 button, top right)
2. Enter your `AI_SERVICES_API_KEY`
3. Click **Authorize** → **Close**
4. All protected endpoints will now include the `X-API-Key` header automatically

---

## Supported Document Formats

| Format | Extension(s) |
|--------|-------------|
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| Excel | `.xlsx` |
| PowerPoint | `.pptx` |
| Text / CSV | `.txt`, `.csv` |
| Images (OCR) | `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff` |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

All tests run without Qdrant or InsightFace models — ML inference is mocked.

---

## Docker Deployment

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f api

# Stop all services
docker compose down
```

The `docker-compose.yml` starts:
- **`dms-ai-qdrant`** — Qdrant vector database on ports 6333/6334
- **`dms-ai-api`** — Unified FastAPI AI Services on port 8000

---

## Security Notes

- `AI_SERVICES_API_KEY` is **never** hardcoded, logged, or returned from any endpoint.
- `FACE_ENCRYPTION_KEY` is **never** printed, logged, or exposed.
- API key comparison uses `hmac.compare_digest()` to prevent timing attacks.
- Face embeddings are **never** returned to clients.
- Face embeddings are **never** stored in Qdrant (encrypted local JSON only).
- Plaintext document chunks are **never** stored in Qdrant (vectors only).
