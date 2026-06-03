# ArynoxTech AI Agent — Complete Usage Guide

**Created by Aryan Chavan (ArynoxTech)**  
**Version:** 2.0.0  
**Python:** 3.13+ | **LLM Backend:** Groq LLaMA 3.1 8B  
**Tools:** 16 production-grade tools | **UI:** Streamlit multi-tab web app

---

## 1. Quick Start

### Install
```powershell
pip install -r D:\AI_AGENT\requirements.txt
```

### Set API Key
Create a `.env` file in the project root:
```
GROQ_API_KEY=gsk_your_key_here
```
Or set it via the Streamlit sidebar (⚙️ API Settings).

### Launch
```powershell
streamlit run D:\AI_AGENT\streamlit_app.py
```
Opens at `http://localhost:8501` — the multi-tab web interface.

### Alternative Launches
```powershell
# CLI mode
python cli.py

# Desktop app (PySide6)
python main.py
```

---

## 2. Multi-Tab Workspace

The Streamlit UI provides a **fully independent multi-tab workspace** — each tab behaves like a separate agent instance.

### Tab Bar (Top of Screen)
- Each tab button shows the session name
- **Orange ⏳ badge** indicates active background tasks in that tab
- Buttons: `➕ New` (create tab), `📋 History` (browse past sessions), `🗑️` (close active tab)

### Tab Independence
| Feature | Per-Tab Isolation |
|---------|-------------------|
| Chat history | Each tab has its own `messages[]` |
| Tool state | Loaded data, DataFrames, models are tab-scoped |
| Background tasks | Tasks continue running when you switch tabs |
| Auto-save | Each tab saves to its own `data/history/{id}_{name}.json` |

### Creating / Renaming / Closing Tabs
- **Create:** Click `➕ New` — a new tab "Session N" appears
- **Rename:** In the sidebar, type a new name in the "Rename tab" field
- **Close:** Click `🗑️` — the tab is saved then removed (minimum 1 tab stays)
- **Switch:** Click any tab button — current tab auto-saves before switching

### How Auto-Save Works
Every message exchange (user + assistant) triggers `save_session_to_json()` which writes to `data/history/{tab_id}_{safe_name}.json`. This means **zero data loss** — even if you close the browser, every conversation is persisted.

---

## 3. History Management

### Auto-Save Location
All sessions are saved to:
```
D:\AI_AGENT\data\history\{tab_id}_{sanitized_name}.json
```

### JSON Format
```json
{
  "tab_id": "a1b2c3d4",
  "name": "Session 1",
  "created_at": "2026-06-03T10:30:00",
  "updated_at": "2026-06-03T11:45:00",
  "message_count": 12,
  "messages": [
    {"role": "user", "content": "hello", "timestamp": "2026-06-03T10:30:00"},
    {"role": "assistant", "content": "Hi! How can I help?", "timestamp": "2026-06-03T10:30:01"}
  ]
}
```

### History Tab
1. Click `📋 History` in the top bar
2. Browse all past sessions — name, message count, created/updated timestamps
3. **Search** sessions by name or tab_id
4. **📂 Load** — opens the session in a new tab with all messages restored
5. **🗑️ Delete** — permanently removes the JSON file

### Manual Save
In the sidebar, click `💾 Save Session Now` to force-save the current tab's messages.

---

## 4. Background Task Automation

### How It Works
The agent can launch **daemon threads** that run in the background for a specific tab. These threads survive tab switches and keep appending results to that tab's chat in real-time.

### Starting a Task
The agent uses `run_background_task(tab_id, name, fn, interval)`:
- `tab_id` — which tab this task belongs to
- `name` — display name (shown with ⏳ badge)
- `fn` — callable that returns a string result
- `interval` — seconds between repeats (None = run once)

### Examples
```
"monitor CPU every 10 seconds"
"check the weather every 5 minutes and alert me"
"backup my database daily"
"watch this folder for new files"
```

### Task Lifecycle
1. Task starts → thread is spawned as `daemon=True`
2. Tab button shows ⏳ badge while thread is alive
3. Results appear as assistant messages with `⏱️ TaskName [HH:MM:SS]:` prefix
4. Task dies when the tab is closed or the app is stopped
5. The info bar below tabs shows `⏳ Background tasks running: Monitor CPU`

---

## 5. All 16 Tools — Detailed Reference

---

### 5.1 File Tool (`tools/file_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `search` | Find files by glob/wildcard pattern | "find all pdf files" |
| `create` | Create a new file or folder | "create a file called notes.txt" |
| `read` | Read text file content | "read my notes.txt" |
| `write` | Write/overwrite content to file | "write Hello World to test.txt" |
| `rename` | Rename a file or folder | "rename old.txt to new.txt" |
| `move` | Move file to another directory | "move report.pdf to Documents" |
| `delete` | Delete file/folder (requires confirmation) | "delete temp.txt" |
| `organize` | Sort files into category folders by extension | "organize my Downloads folder" |

**Navigation shortcuts:** "open downloads", "open desktop", "open documents", "open c drive", "open d drive", "list files", "browse files"

---

### 5.2 Excel Tool (`tools/excel_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `read` | Read Excel/CSV with sheet selection, range, dtypes | "read my data.xlsx" |
| `create` | Create multi-sheet Excel with data validations, conditional formatting, named ranges, comments | "create an Excel file with customer data" |
| `modify` | Update cells, insert/delete rows/cols, find/replace, merge/unmerge, format ranges, copy/move/rename sheets | "update cell A1 to 100" |
| `analyze` | Full statistical analysis: numeric summary, skewness, kurtosis, correlation, value counts | "analyze this spreadsheet" |
| `gst_calc` | GST invoice calculator (CGST/SGST/IGST) with itemized breakdown | "calculate GST on 1000 rupees at 18%" |
| `inventory_report` | Stock status (normal/low/out/overstock), reorder suggestions, category breakdown | "create an inventory report" |
| `formula` | Write Excel formulas (SUM, AVERAGE, VLOOKUP, custom) | "add a sum formula to the total column" |
| `chart` | Add bar/line/pie/scatter/doughnut charts to existing workbook | "add a pie chart to the sales sheet" |
| `pivot_table` | Create pivot tables with rows/columns/values/aggfunc/margins | "create a pivot table by region" |
| `compare` | Compare two Excel files cell-by-cell, output colored diff report | "compare file1.xlsx and file2.xlsx" |
| `template` | Generate business templates: invoice, purchase order, timesheet, budget | "generate an invoice template" |
| `merge_workbooks` | Merge multiple workbooks into one, with per-file or numbered suffixes | "merge all sales files into one" |

**Dependencies:** `pip install openpyxl pandas`

---

### 5.3 PDF Tool (`tools/pdf_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `extract_text` | Extract all text from PDF pages | "extract text from report.pdf" |
| `extract_all` | Extract text + metadata + page count | "read this pdf" |
| `get_metadata` | PDF info: pages, author, title, subject, creator | "get pdf metadata" |

**Dependencies:** `pip install PyPDF2`

---

### 5.4 Browser Tool (`tools/browser_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `open` | Navigate to a URL in Chrome | "open google.com" |
| `get_text` | Extract visible page text | "get text from this page" |
| `screenshot` | Take a screenshot of the current page | "take a screenshot" |
| `click` | Click an element by CSS selector | "click the login button" |
| `fill_form` | Type text into a form field | "fill the search box with python" |
| `search` | Google search via automated browser | "search for weather in Mumbai" |

**Dependencies:** Selenium + ChromeDriver. Install: `pip install selenium webdriver-manager`

---

### 5.5 System Tool (`tools/system_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `cpu` | CPU usage percentage per core | "what's my cpu usage" |
| `memory` | RAM used/total/available/percent | "check memory" |
| `disk` | Disk space per drive | "show disk space" |
| `system_info` | OS, processor, Python version, hostname | "system info" |
| `processes` | List top processes by CPU/RAM | "show running processes" |
| `open_app` | Launch any Windows app (70+ known apps) | "open notepad" |
| `type_text` | Type keystrokes into the focused window | "type Hello World" |
| `open_app_and_type` | Open app then type text in one command | "open notepad and type hello" |

**Known apps:** notepad, calculator, chrome, edge, firefox, vscode, excel, word, powerpoint, outlook, teams, discord, zoom, spotify, vlc, whatsapp, telegram, instagram, photoshop, and 50+ more.

---

### 5.6 Database Tool (`tools/database_tool.py`) — OVERHAULED v2.0

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `connect` | Connect to SQLite/PostgreSQL/MySQL with config | "connect to postgres on localhost" |
| `disconnect` | Close current database connection | "disconnect database" |
| `query` | Run SELECT with params (destructive ops blocked by default) | "SELECT * FROM users LIMIT 5" |
| `execute_sql` | Run INSERT/UPDATE/DELETE (requires allow_destructive=True) | "insert into users values (1, 'John')" |
| `list_tables` | List all tables with row counts and column info | "list all tables" |
| `describe_table` | Full schema: columns, types, indexes, foreign keys | "describe the users table" |
| `create_table` | Create table from schema dict (auto DDL per engine) | "create a users table with id and name" |
| `import_data` | Import CSV/Excel/JSON into a table (append/replace) | "import sales.csv into sales table" |
| `export_data` | Export table/query to CSV/Excel/JSON/Parquet | "export products to excel" |
| `backup_database` | Backup SQLite/PostgreSQL/MySQL database | "backup the database" |
| `run_migration` | Run DDL migration statements (tracked in _migrations table) | "run migration to add email column" |
| `store_memory` | Save a conversation/text into persistent memory | "remember that my email is john@abc.com" |
| `get_history` | Retrieve conversation history from memory | "show my conversation history" |
| `search` | Search stored memories by keyword (LIKE) | "search for email" |
| `store_preference` | Save a user preference (key-value) | "set my theme to dark" |
| `get_preference` | Retrieve a saved preference | "what's my theme" |
| `get_stats` | Database statistics (counts, file size) | "database stats" |

**Multi-Engine Connection:**
```python
# PostgreSQL
{"engine": "postgresql", "host": "localhost", "port": 5432, "database": "mydb", "user": "postgres", "password": "pass"}

# MySQL
{"engine": "mysql", "host": "localhost", "port": 3306, "database": "mydb", "user": "root", "password": "pass"}

# SQLite (default)
{"engine": "sqlite", "database": "memory/agent_memory.db"}
```

**Memory & Preferences:** Built-in tables (`memories`, `conversations`, `preferences`, `_migrations`) are auto-created on connect. FTS5 is used for SQLite full-text search.

**Dependencies:** `pip install psycopg2-binary pymysql pandas`

---

### 5.7 Web Search Tool (`tools/web_search_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `search` | Google search returning raw results (titles, URLs, snippets) | "search for latest AI news" |
| `get_page_content` | Extract clean, readable text from any URL | "get content from https://example.com" |
| `search_and_summarize` | Search + extract content + LLM-filtered summary | "search and summarize climate change" |

**Smart filtering:** LLM filters out spam, bias, and low-quality content from search results.

**Dependencies:** `pip install requests beautifulsoup4`

---

### 5.8 Data Analysis Tool (`tools/data_analysis_tool.py`) — OVERHAULED v1.0

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `load_data` | Load CSV/Excel/JSON/Parquet/SQL into memory (multiple DataFrames) | "load sales.csv" |
| `clean_data` | Handle missing values, duplicates, outliers (IQR), fix types, strip whitespace | "clean this dataset" |
| `analyze` | Descriptive stats, groupby, pivot, crosstab, value_counts | "analyze this data" |
| `correlation` | Pearson/Spearman/Kendall with p-values, strength classification | "find correlation between price and quantity" |
| `forecasting` | Linear trend forecast with seasonal decomposition, confidence intervals | "forecast sales for next 30 days" |
| `hypothesis_test` | t-test (1-sample/independent/paired), ANOVA, chi-square, Shapiro-Wilk normality | "test if the mean is different from 100" |
| `regression_analysis` | OLS regression: R², adjR², F-stat, coefficients, p-values, residual analysis | "run regression on price vs features" |
| `kpi_metrics` | Growth rate, running total, YoY comparison, moving average, EMA, rank, rolling stats | "calculate growth rate month over month" |
| `etl_pipeline` | Full extract-transform-load: filter, sort, groupby, pivot, merge, add columns, fill NA, type conversion | "run a full ETL pipeline on my data" |
| `filter_query` | Pandas query syntax + condition filtering + sort + pagination | "filter where price > 100 and category == 'Electronics'" |
| `time_series_analysis` | ACF/PACF, ADF/KPSS stationarity tests, seasonal decomposition | "analyze time series patterns" |
| `export_data` | Export to CSV/Excel/JSON/Parquet/HTML/Markdown/clipboard | "export this to excel" |

**Examples:**
```
"load the CSV and analyze it"
"find correlations between all numeric columns"
"run a linear regression on this data"
"do an ETL pipeline: load, filter by region, group by category, save to Excel"
"forecast revenue for next quarter"
"test if two groups have different means"
```

**Dependencies:** `pip install pandas numpy scipy statsmodels`

---

### 5.9 Data Entry Tool (`tools/data_entry_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `create_csv` | Create a CSV file from data | "create a CSV with customer records" |
| `create_json` | Create a JSON file from data | "create a JSON file" |
| `import_data` | Import CSV/JSON/TXT into in-memory collection | "import my data.csv" |
| `validate_data` | Validate data against rules (required fields, types, ranges) | "validate this data" |
| `add_record` | Add a record to the collection | "add a new customer record" |
| `update_record` | Update an existing record by ID | "update customer 5's phone number" |
| `delete_record` | Delete a record by ID | "delete record 3" |
| `list_records` | List records with pagination | "show all records" |
| `batch_import` | Import multiple files at once | "import all CSV files in this folder" |
| `generate_form` | Generate a data entry form template | "create a data entry form" |
| `export_records` | Export collection to CSV/JSON | "export contacts to JSON" |
| `search_records` | Search by field or globally | "find records matching John" |

---

### 5.10 Personal Assistant Tool (`tools/personal_assistant_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `set_reminder` | Create a reminder with time/priority | "remind me to call John in 30 minutes" |
| `list_reminders` | View pending/completed/all reminders | "show my reminders" |
| `complete_reminder` | Mark a reminder as done | "mark reminder 3 as complete" |
| `create_note` | Take a note with tags and category | "take a note: meeting agenda..." |
| `search_notes` | Search notes by keyword | "search notes for project X" |
| `list_notes` | Browse all notes | "show all notes" |
| `set_timer` | Countdown timer (runs in background thread) | "set a timer for 5 minutes" |
| `add_todo` | Add task to to-do list with priority | "add milk and eggs to my shopping list" |
| `list_todos` | View pending tasks | "what's on my todo list" |
| `add_event` | Add a calendar event | "schedule a meeting tomorrow at 3pm" |
| `list_events` | View calendar events | "show my events" |
| `today_events` | Today's events summary | "what's on my calendar today" |
| `quick_info` | Current time, date, pending items summary | "what's my status" |
| `get_time` | Current date/time and timezone info | "what time is it" |

---

### 5.11 Report Tool (`tools/report_tool.py`) — OVERHAULED v2.0

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `generate_pdf` | Professional PDF with title page, TOC, sections, tables, embedded charts, headers/footers | "generate a PDF report with sales data" |
| `generate_excel` | Multi-sheet Excel with styled headers, alternating rows, summary formulas, conditional formatting, data bars, color scales, embedded charts | "create an Excel report" |
| `generate_csv` | CSV export with configurable delimiter, encoding, BOM | "export as CSV" |
| `generate_chart` | 7 chart types: bar, bar_stacked, line, pie, scatter, area, histogram, box, heatmap | "create a bar chart of monthly revenue" |
| `generate_html_dashboard` | Full HTML dashboard with KPI cards, charts, tables, multi-tab pages, print/PDF button | "create a sales dashboard" |
| `generate_dashboard` | Multi-chart combined image (2×2 grid) + optional PDF via weasyprint | "create a dashboard of all metrics" |
| `schedule_report` | Schedule recurring report generation (cron/interval-based) | "schedule this report weekly" |
| `list_reports` | Browse all generated reports with filter by name/date/format | "show my reports" |
| `generate_from_template` | Render Jinja2 template with variables → PDF/Excel/CSV/Chart/HTML | "generate report from template" |
| `compare_reports` | Side-by-side comparison of two datasets with chart + HTML comparison report | "compare this month vs last month sales" |

**Chart types supported:** `bar`, `bar_stacked`, `line`, `pie`, `scatter`, `area`, `histogram`, `box`, `heatmap`

**Palettes:** `default`, `corporate`, `pastel`, `monochrome`

**Dependencies:** `pip install reportlab matplotlib openpyxl jinja2 pyyaml weasyprint`

---

### 5.12 App Automation Tool (`tools/app_automation_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `open_social` | Open social platform (Instagram/Facebook/WhatsApp/Telegram/Twitter/Gmail) in browser | "open instagram" |
| `check_messages` | Open DMs/inbox and read visible text | "check my messages" |
| `reply_message` | Type and send a reply (requires user confirmation for safety) | "reply to John's message" |
| `open_app` | Open any desktop application | "open spotify" |
| `open_web` | Open any URL in browser | "open youtube.com" |

**Supported platforms:** Instagram DMs, Facebook Messenger, Twitter/X DMs, WhatsApp Web, Telegram Web, Gmail, Outlook, LinkedIn Messages.

**Safety:** All "send" actions require explicit user confirmation. No credentials stored in code.

---

### 5.13 Document Ingestion Tool (`tools/document_ingestion_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `ingest_file` | Extract text from file → chunk → store in FTS5 for RAG retrieval | "ingest this PDF and learn from it" |
| `ingest_directory` | Batch ingest entire directory (recursive) | "ingest all documents in the folder" |

**Supported formats:** PDF, TXT, MD, HTML, JSON, YAML, DOCX (best-effort), images via OCR (best-effort).

Ingested content is chunked and indexed in SQLite FTS5 for later question-answering via RAG retrieval.

---

### 5.14 Camera Tool (`tools/camera_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `capture_photo` | Take a photo from webcam → saves to `assets/captures/` | "take a photo" |
| `record_video` | Record short video with configurable duration | "record video for 10 seconds" |
| `detect_faces` | Detect faces in camera frame | "detect faces" |
| `detect_objects` | Detect 90+ object types via MobileNet-SSD (COCO classes) | "detect objects" |
| `identify_object` | AI explains what the detected object is | "what is this?" |
| `recognize_person` | Identify a known person by name | "who is this?" |
| `learn_new_person` | Capture + name a new person | "learn this person as John" |
| `save_face` | Associate a name with the last detected face | "save this face as Sarah" |
| `list_known_people` | List all stored face profiles | "who do you know?" |
| `list_cameras` | List all connected camera devices | "list cameras" |

**Object Detection:** MobileNet-SSD (90 COCO classes). First use auto-downloads ~23MB model.

**Face Recognition:** LBPH-based. Face data stored in `data/known_faces/{name}/`.

**Cross-platform:** Works on Windows, macOS, Linux, and mobile browsers (Streamlit).

**Dependencies:** `pip install opencv-python-headless opencv-contrib-python numpy`

---

### 5.15 ML Tool (`tools/ml_tool.py`)

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `train_model` | Train classification or regression model (auto-detect based on target) | "train a model on data.csv with target column price" |
| `predict` | Make predictions using a trained model | "predict using the saved model" |
| `evaluate` | Evaluate model: accuracy/R²/RMSE/classification report | "evaluate my model" |
| `preprocess` | Fill missing values, scale features, encode categories, remove outliers | "preprocess my dataset for ML" |
| `feature_engineering` | Create interaction features, binning, date features, polynomial features | "do feature engineering on the data" |
| `list_models` | Browse all saved models in `models/ml_models/` | "list my models" |
| `load_model` | Load a previously saved model | "load the random forest model" |

**Auto-detects** classifier vs regressor based on target column unique values.  
**Saves** models as pickle files in `models/ml_models/`.  
**Feature importance** reported for tree-based models.

**Dependencies:** `pip install scikit-learn scipy pandas`

---

### 5.16 Business Utils Tool (`tools/business_utils.py`) — NEW v1.0

| Action | Description | Example Command |
|--------|-------------|-----------------|
| `data_quality_report` | Comprehensive quality score (0-100) with missing, duplicates, outliers, constant/high-cardinality/skewed/mixed-type columns, recommendations | "run a data quality check on my CSV" |
| `schema_validation` | Validate data against schema: types (int/float/str/bool/datetime/email/phone/url), nullable, required, min/max, enum, regex patterns | "validate data against my schema" |
| `data_profiling` | Full profile: column types (numeric/categorical/datetime/boolean/text), statistics, quantiles, correlation matrix, value distributions, memory usage | "profile my dataset" |
| `pii_detection` | Detect PII (email, phone, SSN, credit card, IP, passport, PAN, Aadhaar) with confidence scores and masking suggestions | "find any PII in this data" |
| `compliance_check` | GDPR compliance assessment: retention, consent, anonymization, minimization, storage security | "check GDPR compliance" |
| `anomaly_detection` | Detect anomalies via Z-score, IQR, or MAD methods with per-column detail | "find anomalies in my sales data" |
| `data_schema_inference` | Auto-infer JSON Schema from data (types, enums, min/max, nullability) | "infer the schema of this CSV" |
| `merge_datasets` | Merge two datasets (inner/left/right/outer) with auto-detect join columns, merge statistics, integrity checks | "merge customers.csv with orders.csv" |

**PII types detected:** email, phone, SSN, credit card, IP address, passport, PAN, Aadhaar.

**Anomaly methods:** `zscore` (default, threshold=3), `iqr` (multiplier=1.5), `mad` (threshold=3).

**Dependencies:** `pip install pandas numpy`

---

## 6. Business Data Handling Workflows

### Workflow 1: End-to-End Data Quality & Dashboard
```
"load data from sales.csv"
"run a data quality report on it"
"profile the dataset"
"detect any PII in the data"
"find anomalies using z-score method"
"generate an HTML dashboard with KPIs and charts"
```

### Workflow 2: Database Analytics & Forecasting
```
"connect to PostgreSQL on localhost with database analytics"
"list all tables"
"query SELECT * FROM monthly_sales WHERE year = 2026"
"analyze this data for trends"
"forecast sales for the next 6 months"
"export the forecast to Excel"
```

### Workflow 3: ML Pipeline — Raw Data to Predictions
```
"load raw_data.csv"
"clean the data — fill missing values and remove outliers"
"do feature engineering on the dataset"
"preprocess for ML — scale and encode"
"train a model with target column price"
"evaluate the model"
"predict on new data"
"export predictions to CSV"
```

### Workflow 4: GST Invoice → Inventory → Report
```
"upload the invoice CSV"
"calculate GST at 18% on all items"
"create an inventory report from stock data"
"generate a PDF report with GST summary and inventory status"
"email the PDF to team@company.com"
```

### Workflow 5: Multi-Dataset Merge & Schema Validation
```
"load left: customers.csv, right: orders.csv"
"merge datasets on customer_id using outer join"
"infer the schema of the merged data"
"validate against required schema"
"check for PII and run GDPR compliance"
"generate a quality report"
"export the clean merged data to Excel"
```

---

## 7. Voice Commands

### Toggle
- **Voice Input:** Toggle in sidebar (`🎤 Voice Commands` section)
- **Spoken Output (TTS):** Sidebar toggle — agent reads responses aloud
- **Language:** `en-IN` (default), `en-US`, `hi-IN`

### How It Works
1. Enable "Voice Input" toggle
2. Click `🎤 Click to Speak`
3. Speak your command (6-second timeout)
4. Speech is transcribed via Google Speech Recognition
5. Command is processed as if typed
6. If "Spoken Output" is enabled, the response is read aloud via `pyttsx3`

### Tips
- Speak clearly at normal pace
- For Hindi, select `hi-IN` language
- Each assistant message has a `🔊 Play` button for individual playback
- Voice mode works on mobile browsers through Streamlit

---

## 8. API Key Configuration

### Method 1: `.env` File (Recommended)
Create `D:\AI_AGENT\.env`:
```
GROQ_API_KEY="gsk_your_key_here"
```

### Method 2: Streamlit Sidebar UI
1. Click `⚙️ API Settings` in the sidebar
2. Enter your Groq API key in the password field
3. Key is saved to `.env` and environment variable automatically

### Method 3: Environment Variable
```powershell
$env:GROQ_API_KEY="gsk_your_key_here"
```

### Getting a Groq API Key
1. Go to https://console.groq.com
2. Sign up for a free account
3. Navigate to API Keys → Create new key
4. Copy the key (starts with `gsk_...`)
5. Free tier includes rate limits on `llama-3.1-8b-instant`

---

## 9. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                 Streamlit Multi-Tab UI               │
│  Tab[0]  Tab[1]  Tab[2]  [+]  [📋 History]  [🗑️]   │
│  ┌────────────────────────────────────────────────┐  │
│  │  Each Tab: Independent chat, tool state,       │  │
│  │  running background tasks, auto-save to JSON   │  │
│  └────────────────────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│              Agent Core (Singleton)                   │
│  - process_user_input(text)                          │
│  - Fast-path routing (deterministic, ~200ms)         │
│  - Fallback: LLM Planner (Groq API, ~1-3s)           │
│  - Tool Registry (16 tools)                          │
│  - Memory System (short-term + long-term + semantic) │
└────┬──────────────────────┬──────────────────────┬────┘
     │                      │                      │
     ▼                      ▼                      ▼
┌──────────┐     ┌──────────────────┐     ┌──────────────┐
│ Planner  │     │  Fast Path Router│     │Task Manager  │
│ - LLM    │     │ - Direct tool    │     │- Daemon      │
│   plan   │     │   invocation     │     │  threads     │
│ - Keyword│     │ - No LLM latency │     │- Per-tab     │
│   route  │     │ - 20+ patterns   │     │  isolation   │
└──────────┘     └──────────────────┘     └──────────────┘
```

### Components

| Component | File | Description |
|-----------|------|-------------|
| Agent Core | `agent/agent_core.py` | Central orchestrator, tool registry, input routing |
| Planner | `agent/planner.py` | LLM-based task decomposition + keyword routing |
| Task Manager | `agent/task_manager.py` | Background thread executor and queue |
| Short-Term Memory | `memory/short_term_memory.py` | Recent N messages context |
| Long-Term Memory | `memory/long_term_memory.py` | Persistent SQLite key-value store |
| Semantic Memory | `memory/semantic_memory.py` | FTS5 full-text search across ingested documents |
| RAG Retrieval | `memory/rag_retrieval.py` | Dense + sparse + rerank hybrid retrieval |
| DB Manager | `database/db_manager.py` | Thread-safe SQLite operations |
| Llama Client | `utils/llama_client.py` | Groq API wrapper with retry/fallback |

### Fast Path System (No LLM Needed)

| Input Pattern | Direct Handler | Latency |
|---------------|---------------|---------|
| "open \<app\>" | `system_tool.open_app` | ~200ms |
| "open \<app\> and type \<txt\>" | compound handler | ~800ms |
| "type \<text\>" | `system_tool.type_text` | ~200ms |
| "take photo" / "record video" | `camera_tool` | ~500ms |
| "list files" / "open downloads" | `file_tool` / explorer | ~200ms |
| "calculate GST" | `excel_tool.gst_calc` | ~300ms |
| "generate pdf/excel/csv/chart" | `report_tool` | ~500ms |
| "search for \<query\>" | `web_search_tool` | ~2s |
| "remember …" | `database_tool.store_memory` | ~100ms |
| "what's my cpu/ram/disk" | `system_tool` | ~500ms |
| "set a reminder" | `personal_assistant_tool` | ~200ms |
| Everything else | LLM Planner (Groq) | ~1-3s |

---

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| "GROQ_API_KEY not found" | Add key to `.env` file or set via Streamlit sidebar ⚙️ |
| "Module not found" | Run `pip install -r requirements.txt` |
| "Streamlit app not loading" | Run with `streamlit run streamlit_app.py` (not `python`) |
| "Cannot connect to Groq API" | Check API key is valid; check internet connection |
| "Browser automation not available" | Install Chrome + ChromeDriver: `pip install selenium webdriver-manager` |
| "Camera not opening" | Check webcam connection; install `opencv-python-headless` |
| "cv2.face module not found" | Run `pip install opencv-contrib-python` |
| "Object detection not working" | First use downloads ~23MB model — requires internet |
| "Face recognition fails" | Ensure good lighting; face must be clearly visible |
| "ML model training fails" | Install scikit-learn: `pip install scikit-learn scipy` |
| "Report generation fails" | Install reportlab, openpyxl, matplotlib: `pip install reportlab openpyxl matplotlib` |
| "Database connect fails" | Check host/port/credentials; for PG: `pip install psycopg2-binary`; for MySQL: `pip install pymysql` |
| "History tab is empty" | Conversations auto-save after each exchange; check `data/history/*.json` |
| "Tab not switching" | Refresh the browser; tabs are preserved in session state |
| "Background task stopped" | Tasks are daemon threads — they stop when app exits; ensure interval > 0 |
| "Multiple tabs lost on refresh" | Sessions persist in `data/history/*.json`; load via 📋 History |
| "App runs slowly" | Use fast-path commands to skip LLM latency (see Section 9) |
| "Feature not working on macOS/Linux" | System automation tools are Windows-optimized; file/camera/ML tools work cross-platform |
| "PII detection false positives" | Adjust confidence thresholds; column name hints improve accuracy |
| "Anomaly detection returns nothing" | Try different method: `zscore` (default), `iqr`, or `mad` |
| "Export format not supported" | Supported: csv, xlsx, json, parquet, html, markdown, clipboard |
| "KPI metrics empty" | Ensure date_column and value_column are specified correctly |
| "Merge datasets fails" | Ensure both datasets have at least one common column for the join key |
| "`reportlab` import error" | Install: `pip install reportlab` |
| "Cannot find generated reports" | Reports saved to `assets/reports/` and `reports/` directories |
| "Voice input not working" | Install: `pip install SpeechRecognition pyttsx3`; check microphone access |
| "Session history not loading" | JSON files in `data/history/` may be corrupted; check valid JSON format |

---

## 11. License

**MIT License** — Copyright (c) 2026 Aryan Chavan (ArynoxTech)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

**Built by Aryan Chavan (ArynoxTech)**  
Python 3.13+ | Groq API | Streamlit | PySide6 | SQLite | scikit-learn | OpenCV | OpenPyXL | ReportLab | Matplotlib
