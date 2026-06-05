# ArynoxTech AI Agent

**by Aryan Chavan (ArynoxTech)**
*A production-ready open-source AI agent for business data handling and desktop automation*

> **License:** MIT — free to use, modify, and distribute commercially. See [LICENSE](LICENSE).

---

## What It Can Do

| Category | Capabilities |
|----------|-------------|
| Chat & LLM | Online: Groq LLaMA 3.1 8B / Offline: Local Hugging Face model, natural conversation, RAG memory |
| File System | Open/create/edit/move/search any file or folder |
| Excel & Data | Read/create/modify Excel, formulas, pivot tables, GST calc, inventory, charts |
| PDF | Extract text & metadata from PDF files |
| Web Search | Google search with smart LLM filtering & summarization (online only) |
| System | Open any app (70+ known), monitor CPU/RAM/disk, type text |
| Database (Multi-Engine) | SQLite/PostgreSQL/MySQL — full SQL, migrations, import/export |
| Memory | Short-term, long-term, semantic search, RAG retrieval |
| Social Media | Open Instagram/Facebook/WhatsApp, check & reply messages |
| Assistant | Reminders, notes, timers, to-do lists, calendar events |
| Data Entry | CSV/JSON CRUD, batch import, validation, form generation |
| Data Analysis | Forecasting, hypothesis testing, regression, KPI metrics, ETL, time series |
| Reports | PDF, Excel, CSV, charts, HTML dashboards, scheduled reports |
| Business Utils | Data quality, profiling, PII detection, compliance, anomaly detection, merge |
| Camera | Take photos, video, object detection (90 classes), face recognition |
| ML Engineer | Train models, predict, evaluate, preprocess, feature engineering |
| Document Ingest | Index PDF/TXT/DOCX/images into searchable memory |
| Multi-Tab | Independent chat sessions with per-tab history, tools & background tasks |
| History Export | Auto-save all conversations to `data/history/*.json` |
| Background Tasks | Run persistent automation per tab (monitoring, polling, backups) |
| Voice Mode | Speech input & TTS output (en-IN, en-US, hi-IN) |
| API Settings | Set Groq API key via `.env` OR Streamlit UI sidebar |
| **Offline Mode** | Auto-detects when no internet/API key, falls back to local Hugging Face model |

---

## Quick Start

### Option 1 — Online Mode (Groq API)

1. Get a free API key at [console.groq.com](https://console.groq.com)
2. Set your key in `.env`:
   ```powershell
   echo "GROQ_API_KEY=gsk_your_key_here" > .env
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Launch:
   ```powershell
   streamlit run streamlit_app.py
   ```
   Or CLI: `python cli.py`

### Option 2 — Offline Mode (Local Model, <5GB)

The agent can run **fully offline** using a local Hugging Face model. It auto-detects when no API key is available or when Groq API is unreachable, and seamlessly switches to the local model. Uses PyTorch with optional 4-bit quantization for GPU efficiency.

**Pre-requisites:** `transformers`, `torch`, `bitsandbytes`, `safetensors` — all already in `requirements.txt`.

#### Step 1: Download a Hugging Face Model (<5GB)

Recommended models (all under 5GB total, fits RTX 3050 4GB via 4-bit):

| Model | Size | VRAM (4-bit) | Notes |
|-------|------|-------------|-------|
| **SmolLM2-1.7B-Instruct** | ~3.2 GB | ~1.3 GB | Good balance, chat-trained. **Pre-downloaded & sharded.** |
| **TinyLlama-1.1B-Chat-v1.0** | ~2.0 GB | ~0.8 GB | Fastest option, works on any GPU |
| **Qwen2.5-1.5B-Instruct** | ~3.0 GB | ~1.2 GB | Strong 1.5B, modern architecture |
| **Llama-3.2-1B-Instruct** | ~2.0 GB | ~0.8 GB | Lightweight, good for CPU |
| **SmolLM2-360M-Instruct** | ~0.7 GB | ~0.3 GB | Ultra-light, runs on anything |

**Download methods:**

**Method A — Hugging Face CLI (recommended):**
```powershell
# Install
pip install huggingface-hub

# Download a model (example: SmolLM2-1.7B)
huggingface-cli download HuggingFaceTB/SmolLM2-1.7B-Instruct --local-dir D:\AI_AGENT\models\SmolLM2-1.7B-Instruct
```

**Method B — Manual download:**
1. Go to the model's Hugging Face page (e.g. https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct)
2. Click "Files and versions"
3. Download ALL `.safetensors` files, `config.json`, `tokenizer.json`, etc.
4. Place them in `D:\AI_AGENT\models\<model-name>\`

**Note for Windows (page file <8GB):** Models over ~2.5GB in a single `.safetensors` file may fail to load due to Windows mmap limitations. The agent handles this automatically — shards large files into <2GB shards on first load.

**Method c - Download from link:**
link :- https://drive.google.com/drive/folders/1M-mTgaALK1nFANCY6K2qy91GcdSWRORZ?usp=sharing

   
#### Step 2: Configure .env for offline mode

Edit your `.env` file:

```ini
# Optional — leave empty or remove to force offline mode
# GROQ_API_KEY=

# Enable local model
LOCAL_MODEL_ENABLED=1

# Path to your downloaded model folder
LOCAL_MODEL_PATH=D:\AI_AGENT\models\SmolLM2-1.7B-Instruct

# Optional settings (defaults shown)
# LOCAL_MODEL_N_CTX=2048       # Context window size
# LOCAL_MODEL_N_THREADS=4      # CPU threads for tokenization
# LOCAL_MODEL_MAX_TOKENS=512   # Max response tokens
# LOCAL_MODEL_TEMPERATURE=0.7  # Creativity (0.0-1.0)
# LOCAL_MODEL_TOP_P=0.95       # Top-p sampling
# LOCAL_MODEL_GPU_LAYERS=0     # Not used by transformers (auto-managed)
```

> **Tip:** Place model folders in `D:\AI_AGENT\models\`. The agent scans for `.safetensors` files.

#### Step 3: Run Offline

```powershell
streamlit run streamlit_app.py
```
Or use CLI: `python cli.py`

---

## How Auto-Detection Works

The agent uses an intelligent **LLM Factory** that checks availability in this order:

1. **Check Groq API** — If `GROQ_API_KEY` is set and the API responds, use **Online Mode**
2. **Check Local Model** — If `LOCAL_MODEL_ENABLED=1` and the model file exists, use **Offline Mode**
3. **Auto-detect** — Even without `LOCAL_MODEL_ENABLED`, if a model folder with `.safetensors` files exists in `models/`, the agent will automatically load it

The switch is **instant and seamless** — you don't need to restart the app. The mode is displayed in the sidebar (Streamlit UI) or on the welcome banner (CLI).

---

## Example Commands

```
"open notepad and type Hello World"
"create an Excel file with customer data"
"search for latest AI news"        (online only)
"take a photo"
"train a model on my data.csv with target column price"
"open instagram and check messages"
"set a reminder in 30 minutes"
"generate a PDF report"
"list files in my documents"
"what's my CPU usage?"
"remember my name is Aryan"
"detect faces in camera"
"preprocess my dataset for ML"
```

See **[WORK.md](WORK.md)** for the complete 100+ command reference.

---

## 16 Tools Included

`file_tool` · `excel_tool` · `pdf_tool` · `browser_tool` · `system_tool` ·
`database_tool` · `web_search_tool` · `data_analysis_tool` · `data_entry_tool` ·
`personal_assistant_tool` · `report_tool` · `app_automation_tool` ·
`document_ingestion_tool` · `camera_tool` · `ml_tool` · `business_utils_tool`

---

## Offline-Only Features

Most tools work fully offline:
- File operations, Excel, PDF, system control
- Camera, ML model training (scikit-learn)
- Database (SQLite), data analysis
- Reports, data entry, personal assistant
- Document ingestion and RAG memory

Tools that require internet **gracefully degrade**:
- **Web Search** — Returns a message: "Web search requires internet. Try again when connected."
- **Browser Automation** — Still works for local files and sites that are cached

---

## Project Structure

```
D:\AI_AGENT/
├── streamlit_app.py     # Web UI (recommended)
├── cli.py               # Command-line interface
├── requirements.txt     # All dependencies
├── .env                 # Your API key
├── README.md            # This file
├── WORK.md              # Full documentation
├── agent/               # Core orchestration
├── tools/               # 16 automation tools
├── memory/              # Memory & RAG systems
├── database/            # SQLite storage
├── config/              # Settings
├── models/ml_models/    # Trained ML models
├── reports/             # Generated reports
└── assets/captures/     # Camera photos/videos
```

---

## API Key Configuration

**Method 1 — `.env` file:**
```ini
GROQ_API_KEY="gsk_..."
```

**Method 2 — Streamlit UI:**
Sidebar -> API Settings -> paste key -> Click "New Chat"

The key is saved to `.env` automatically and masked in the UI.

---

## Speed

Common commands execute in **200ms–1s** via deterministic fast paths (no LLM wait).
Complex requests fall back to:
- **Online:** Groq API (~1–3s)
- **Offline:** Local model (~2–15s depending on model size and CPU)
See [WORK.md Section 3 — Fast Path System](WORK.md#3-fast-path-system-speed-optimization) for details.

---

## Security

- No credentials hardcoded — only in `.env`
- Social media sending requires user confirmation
- File deletion requires confirmation
- System paths (C:\Windows, etc.) are blocked
- Chat history stored locally only
- API key masked in UI

---

## License

Open source. Built by **Aryan Chavan (ArynoxTech)**.  
Python 3.13+ | Groq API | Streamlit | SQLite | scikit-learn | OpenCV

---

**Full documentation:** [WORK.md](WORK.md)
