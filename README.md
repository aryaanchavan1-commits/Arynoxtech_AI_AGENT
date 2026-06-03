# 🤖 ArynoxTech AI Agent

**by Aryan Chavan (ArynoxTech)**  
*A production-ready open-source AI agent for business data handling and desktop automation*

> **License:** MIT — free to use, modify, and distribute commercially. See [LICENSE](LICENSE).

---

## ✨ What It Can Do

| Category | Capabilities |
|----------|-------------|
| 💬 **Chat & LLM** | Groq LLaMA 3.1 8B, natural conversation, RAG memory |
| 📂 **File System** | Open/create/edit/move/search any file or folder |
| 📊 **Excel & Data** | Read/create/modify Excel, formulas, pivot tables, GST calc, inventory, charts |
| 📄 **PDF** | Extract text & metadata from PDF files |
| 🌐 **Web Search** | Google search with smart LLM filtering & summarization |
| 🖥️ **System** | Open any app (70+ known), monitor CPU/RAM/disk, type text |
| 🗄️ **Database (Multi-Engine)** | SQLite/PostgreSQL/MySQL — full SQL, migrations, import/export |
| 🧠 **Memory** | Short-term, long-term, semantic search, RAG retrieval |
| 📱 **Social Media** | Open Instagram/Facebook/WhatsApp, check & reply messages |
| 🗓️ **Assistant** | Reminders, notes, timers, to-do lists, calendar events |
| 📝 **Data Entry** | CSV/JSON CRUD, batch import, validation, form generation |
| 📈 **Data Analysis** | Forecasting, hypothesis testing, regression, KPI metrics, ETL, time series |
| 📊 **Reports** | PDF, Excel, CSV, charts, HTML dashboards, scheduled reports |
| 📋 **Business Utils** | Data quality, profiling, PII detection, compliance, anomaly detection, merge |
| 📷 **Camera** | Take photos, video, object detection (90 classes), face recognition |
| 🧪 **ML Engineer** | Train models, predict, evaluate, preprocess, feature engineering |
| 📄 **Document Ingest** | Index PDF/TXT/DOCX/images into searchable memory |
| 🗂️ **Multi-Tab** | Independent chat sessions with per-tab history, tools & background tasks |
| 📁 **History Export** | Auto-save all conversations to `data/history/*.json` |
| 🔄 **Background Tasks** | Run persistent automation per tab (monitoring, polling, backups) |
| 🎤 **Voice Mode** | Speech input & TTS output (en-IN, en-US, hi-IN) |
| 🔑 **API Settings** | Set Groq API key via `.env` OR Streamlit UI sidebar |

---

## 🚀 Quick Start

### 1. Get a Groq API Key
Free at [console.groq.com](https://console.groq.com)

### 2. Set Your API Key
**.env file:**
```powershell
echo "GROQ_API_KEY=gsk_your_key_here" > .env
```
**Or** set it in the Streamlit UI sidebar (⚙️ API Settings)

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Launch the Agent
```powershell
streamlit run streamlit_app.py
```
Or use CLI: `python cli.py`

---

## 💡 Example Commands

```
"open notepad and type Hello World"
"create an Excel file with customer data"
"search for latest AI news"
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

## 🛠️ 15 Tools Included

`file_tool` · `excel_tool` · `pdf_tool` · `browser_tool` · `system_tool` ·  
`database_tool` · `web_search_tool` · `data_analysis_tool` · `data_entry_tool` ·  
`personal_assistant_tool` · `report_tool` · `app_automation_tool` ·  
`document_ingestion_tool` · `camera_tool` · `ml_tool`

---

## 📁 Project Structure

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

## 🔑 API Key Configuration

**Method 1 — `.env` file:**
```
GROQ_API_KEY="gsk_..."
```

**Method 2 — Streamlit UI:**  
Sidebar → ⚙️ API Settings → paste key → Click "New Chat"

The key is saved to `.env` automatically and masked in the UI.

---

## ⚡ Speed

Common commands execute in **200ms–1s** via deterministic fast paths (no LLM wait).  
Complex requests fall back to Groq API (~1–3s).  
See [WORK.md §3 — Fast Path System](WORK.md#3-fast-path-system-speed-optimization) for details.

---

## 🔒 Security

- No credentials hardcoded — only in `.env`
- Social media sending requires user confirmation
- File deletion requires confirmation
- System paths (C:\Windows, etc.) are blocked
- Chat history stored locally only
- API key masked in UI

---

## 📄 License

Open source. Built by **Aryan Chavan (ArynoxTech)**.  
Python 3.13+ | Groq API | Streamlit | SQLite | scikit-learn | OpenCV

---

**Full documentation:** [WORK.md](WORK.md)
