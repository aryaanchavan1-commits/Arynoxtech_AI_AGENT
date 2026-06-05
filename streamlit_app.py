"""
ArynoxTech AI Agent - Multi-Tab Streamlit GUI (Optimized)
=========================================================
Run: streamlit run streamlit_app.py
"""

import streamlit as st
import asyncio
import os
import threading
import time
import re
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

st.set_page_config(page_title="ArynoxTech AI Agent", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

from utils.logger import LoggerFactory
LoggerFactory.initialize()
from agent.agent_core import AgentCore
from config.settings import LLM_CONFIG, BASE_DIR
from utils.llm_factory import get_llm_factory, LLMMode

HISTORY_DIR = BASE_DIR / "data" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

# ── Async helper ──────────────────────────────────────────────────────────────
_loop: Optional[asyncio.AbstractEventLoop] = None

def _run_async(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    try:
        return _loop.run_until_complete(coro)
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

# ── Voice ─────────────────────────────────────────────────────────────────────
def speak_text(text: str):
    def _speak():
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                import pyttsx3
                e = pyttsx3.init()
                e.setProperty("rate", 175)
                e.setProperty("volume", 0.9)
                clean = re.sub(r'[^\w\s.,!?;:\-]', '', text)
                if clean.strip():
                    e.say(clean)
                    e.runAndWait()
                e.stop()
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()

def listen_for_speech(timeout: int = 5) -> str:
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.energy_threshold = 300
        r.pause_threshold = 0.5
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = r.listen(source, timeout=timeout, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                return ""
        lang = st.session_state.get("voice_lang", "en-IN")
        return r.recognize_google(audio, language=lang).strip()
    except Exception:
        return ""

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
.block-container{padding-top:0.8rem!important}
.stApp header{display:none!important}
@media(max-width:768px){.main .block-container{padding:0.3rem!important}h1{font-size:1.1rem!important}.stChatInput{font-size:14px!important}}
.tab-container{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.tab-btn{border-radius:6px 6px 0 0!important;font-size:12px!important;padding:2px 10px!important;border-bottom:none!important;min-width:0!important}
.tab-btn-active{background-color:#4472C4!important;color:#fff!important}
.tab-btn-close{padding:0 4px!important;min-width:20px!important;font-size:11px!important;line-height:1!important}
div[data-testid="stButton"] button{border-radius:6px!important}
.st-emotion-cache-1t41c2q{padding:0!important}
.report-file{padding:4px 8px;background:#f0f2f6;border-radius:6px;margin:2px 0;font-size:13px}
.badge{background:#ff9800;color:#fff;border-radius:8px;padding:0 6px;font-size:10px;margin-left:4px}
</style>""", unsafe_allow_html=True)

# ── Init Agent (once) ────────────────────────────────────────────────────────
if "agent" not in st.session_state:
    with st.spinner("Initializing..."):
        agent = AgentCore()
        connected = agent.check_model_connection()
        if not connected:
            llm_factory = get_llm_factory()
            mode = llm_factory.detect_mode()
            if mode == LLMMode.UNAVAILABLE:
                st.error(
                    "⚠️ No LLM backend available.\n\n"
                    "• Set **GROQ_API_KEY** in `.env` for online mode\n"
                    "• OR enable offline mode by:\n"
                    "  1. Setting `LOCAL_MODEL_ENABLED=1` in `.env`\n"
                    "  2. Downloading a Hugging Face model (e.g., SmolLM2-1.7B, TinyLlama-1.1B)\n"
                    "  3. Setting `LOCAL_MODEL_PATH=path/to/model-folder` in `.env`\n\n"
                    "See README.md for detailed offline setup instructions."
                )
                st.stop()
        st.session_state.agent = agent

# ── Tab data model ────────────────────────────────────────────────────────────
def _new_tab(name: str = None) -> dict:
    tid = uuid.uuid4().hex[:8]
    return {
        "id": tid, "name": name or f"Session {len(st.session_state.tab_order)+1}",
        "messages": [], "tool_states": {}, "task_names": [],
        "created_at": datetime.now().isoformat(), "updated_at": "",
        "dirty": False, "last_save": 0.0,
    }

def _init():
    if "tabs" in st.session_state: return
    tab = _new_tab("Session 1")
    st.session_state.tabs = {tab["id"]: tab}
    st.session_state.tab_order = [tab["id"]]
    st.session_state.active_tab = tab["id"]
    st.session_state.show_history = False
    st.session_state.voice_mode = False
    st.session_state.tts_enabled = True
    st.session_state.listening = False
_init()

def _tab() -> dict:
    return st.session_state.tabs.get(st.session_state.active_tab, st.session_state.tabs[st.session_state.tab_order[0]])

# ── JSON save (background, debounced) ─────────────────────────────────────────
def _save_json(tab: dict):
    if not tab.get("messages") or tab.get("dirty") is False: return
    safe = re.sub(r'[^\w\-_]', '_', tab["name"])[:40]
    path = HISTORY_DIR / f"{tab['id']}_{safe}.json"
    data = {
        "tab_id": tab["id"], "name": tab["name"],
        "created_at": tab["created_at"], "updated_at": datetime.now().isoformat(),
        "message_count": len(tab["messages"]),
        "messages": [{"role": m["role"], "content": m["content"], "timestamp": m.get("timestamp","")} for m in tab["messages"]],
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tab["dirty"] = False
        tab["last_save"] = time.time()
    except Exception:
        pass

def _mark_dirty(tab: dict):
    tab["dirty"] = True
    tab["updated_at"] = datetime.now().isoformat()

@st.cache_data(ttl=10, show_spinner=False)
def _list_history() -> list:
    sessions = []
    for f in sorted(HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            d["file_path"] = str(f)
            sessions.append(d)
        except Exception:
            continue
    return sessions

@st.cache_data(ttl=10, show_spinner=False)
def _list_reports() -> list:
    files = sorted(REPORT_DIR.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [f for f in files if f.suffix.lower() in (".pdf",".xlsx",".csv",".png",".jpg")][:10]

# ── Process input (non-blocking) ──────────────────────────────────────────────
def process_input(text: str):
    if not text.strip(): return
    tab = _tab()
    tab["messages"].append({"role": "user", "content": text, "timestamp": datetime.now().isoformat()})
    _mark_dirty(tab)
    st.session_state._pending_prompt = text
    st.session_state._processing = True
    _list_history.clear()

# ── History helpers (defined before use) ──────────────────────────────────────
def _load_history(fp: str):
    try:
        with open(fp, encoding="utf-8") as f: data = json.load(f)
    except: return
    _save_json(_tab())
    tab = _new_tab(data.get("name","Loaded"))
    tab["messages"] = data.get("messages", [])
    st.session_state.tabs[tab["id"]] = tab
    st.session_state.tab_order.append(tab["id"])
    st.session_state.active_tab = tab["id"]
    st.session_state.show_history = False

def _del_history(fp: str):
    try: Path(fp).unlink(missing_ok=True)
    except: pass

# ── Render ────────────────────────────────────────────────────────────────────
st.markdown("### 💬 ArynoxTech AI Agent")

# ── Tab Bar ───────────────────────────────────────────────────────────────────
tab_ids = st.session_state.tab_order
cols = st.columns([0.14]*min(len(tab_ids), 6) + [0.08, 0.08, 0.1])
for i, tid in enumerate(tab_ids):
    if i >= 6: break
    t = st.session_state.tabs[tid]
    label = t["name"]
    if t["task_names"]: label += f" ⏳{len(t['task_names'])}"
    with cols[i]:
        st.button(label, key=f"tb_{tid}", use_container_width=True,
                  type="primary" if tid == st.session_state.active_tab else "secondary",
                  on_click=lambda tid=tid: _switch_tab(tid))
with cols[-3]:
    st.button("➕", key="tb_new", use_container_width=True, on_click=lambda: _new_tab_action())
with cols[-2]:
    st.button("📋" if not st.session_state.show_history else "✕", key="tb_hist", use_container_width=True,
              on_click=lambda: setattr(st.session_state, "show_history", not st.session_state.show_history))
with cols[-1]:
    if len(tab_ids) > 1:
        st.button("🗑️", key="tb_close", use_container_width=True, on_click=lambda: _close_tab_action())

st.divider()

# ── Tab actions (callbacks) ───────────────────────────────────────────────────
def _switch_tab(tid: str):
    _save_json(_tab())
    st.session_state.active_tab = tid
    st.session_state.show_history = False

def _new_tab_action():
    _save_json(_tab())
    tab = _new_tab()
    st.session_state.tabs[tab["id"]] = tab
    st.session_state.tab_order.append(tab["id"])
    st.session_state.active_tab = tab["id"]
    st.session_state.show_history = False

def _close_tab_action():
    if len(st.session_state.tab_order) <= 1: return
    tid = st.session_state.active_tab
    _save_json(st.session_state.tabs.get(tid, {}))
    st.session_state.tab_order = [t for t in st.session_state.tab_order if t != tid]
    st.session_state.tabs.pop(tid, None)
    st.session_state.active_tab = st.session_state.tab_order[0]

# ── HISTORY TAB ───────────────────────────────────────────────────────────────
if st.session_state.show_history:
    st.subheader("📋 Session History")
    sessions = _list_history()
    search_q = st.text_input("Search", placeholder="Search sessions...", key="hs", label_visibility="collapsed")
    if search_q:
        q = search_q.lower()
        sessions = [s for s in sessions if q in s.get("name","").lower()]
    if not sessions:
        st.info("No saved sessions. Conversations auto-save as JSON.")
    else:
        st.caption(f"{len(sessions)} sessions")
        for s in sessions:
            c1,c2,c3,c4 = st.columns([3,1.5,0.7,0.7])
            with c1: st.markdown(f"**{s.get('name','?')}**  \n📝 {s.get('message_count',0)} msgs")
            with c2: st.caption(f"{(s.get('updated_at') or s.get('created_at',''))[:19].replace('T',' ')}")
            with c3:
                st.button("📂", key=f"hl_{s.get('tab_id','')}", on_click=lambda fp=s.get("file_path",""): _load_history(fp))
            with c4:
                st.button("🗑️", key=f"hd_{s.get('tab_id','')}", on_click=lambda fp=s.get("file_path",""): (_del_history(fp), _list_history.clear()))
    st.divider()
    st.button("← Back", use_container_width=True, on_click=lambda: setattr(st.session_state,"show_history",False))
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**🤖 ArynoxTech**")
    st.caption(f"`{_tab()['name']}` - {len(_tab()['messages'])} msgs")

    # ── LLM Mode Indicator ──────────────────────────────────────────────────
    if "agent" in st.session_state:
        mode_name = st.session_state.agent.current_llm_mode
        if "Online" in mode_name:
            st.success(f"✅ **Online** — Groq API")
        elif "Offline" in mode_name:
            st.info(f"💻 **Offline** — Local Model")
        else:
            st.error(f"❌ **Unavailable**")
    else:
        st.warning("⏳ Initializing...")

    if _tab()["task_names"]:
        st.info(f"⏳ Running: {', '.join(_tab()['task_names'])}")

    nn = st.text_input("Tab Name", value=_tab()["name"], label_visibility="collapsed", placeholder="Rename tab...")
    if nn and nn != _tab()["name"]:
        _tab()["name"] = nn; _mark_dirty(_tab())

    st.divider()

    with st.expander("🎤 Voice", expanded=False):
        st.session_state.voice_mode = st.toggle("Voice Input", st.session_state.voice_mode, key="vm")
        st.session_state.tts_enabled = st.toggle("Spoken Output", st.session_state.tts_enabled, key="tts")
        st.selectbox("Lang", ["en-IN","en-US","hi-IN"], key="voice_lang", label_visibility="collapsed")

    if st.session_state.voice_mode and st.button("🎤 Speak", use_container_width=True, key="vb"):
        st.session_state.listening = True

    if st.session_state.listening:
        with st.status("🎤 Listening..."):
            spoken = listen_for_speech(timeout=6)
            st.session_state.listening = False
        if spoken:
            st.success(f"✅ {spoken}")
            process_input(spoken); st.rerun()
        else:
            st.info("No speech"); st.rerun()

    st.divider()

    st.button("💾 Save", use_container_width=True, on_click=lambda: (_save_json(_tab()), None))
    st.button("📋 History", use_container_width=True, on_click=lambda: setattr(st.session_state,"show_history",True))

    st.divider()

    with st.expander("⚙️ API Key", expanded=False):
        ck = LLM_CONFIG.get("api_key","")
        st.caption(f"Key: `{ck[:8]}...{ck[-4:]}`" if len(ck)>12 else "Not set")
        nk = st.text_input("API Key", type="password", placeholder="gsk_...", label_visibility="collapsed", key="ak")
        if nk:
            LLM_CONFIG["api_key"] = nk; os.environ["GROQ_API_KEY"] = nk
            ep = Path(".env")
            ec = ep.read_text() if ep.exists() else ""
            ec = re.sub(r"GROQ_API_KEY=.*", f'GROQ_API_KEY="{nk}"', ec) if "GROQ_API_KEY" in ec else ec + f'\nGROQ_API_KEY="{nk}"'
            ep.write_text(ec); st.success("✅ Updated")

    st.divider()

    st.markdown("**🛠️ Tools**")
    for t in ["Excel","File","PDF","Browser","System","Database","Web Search","Data Analysis","Data Entry",
              "Assistant","Report Gen","Social Media","App Automation","Camera","ML","Business Utils"]:
        st.markdown(f"- {t}")

    st.divider()

    with st.expander("📁 Upload", expanded=False):
        uf = st.file_uploader("File", type=["pdf","xlsx","xls","csv","txt","md","docx","json"], label_visibility="collapsed")
        if uf:
            from config.settings import UPLOADS_DIR
            p = UPLOADS_DIR / uf.name
            with open(p,"wb") as f: f.write(uf.getbuffer())
            st.success(f"✅ {uf.name}")
            st.button("📖 Ingest", use_container_width=True, on_click=lambda: process_input(f"ingest document '{p}' and learn from it"))

    st.divider()

    st.markdown("**📁 Reports**")
    reports = _list_reports()
    if reports:
        for rf in reports:
            with open(rf,"rb") as fh:
                sz = round(rf.stat().st_size/1024, 1)
                st.download_button(f"⬇ {rf.name[:18]} ({sz}KB)", data=fh, file_name=rf.name,
                                   mime="application/octet-stream", use_container_width=True, key=f"dl_{rf.name}")
    else:
        st.caption("No reports yet.")

# ── MAIN CHAT ─────────────────────────────────────────────────────────────────
# Process pending prompt (shows spinner, runs BEFORE messages render)
if st.session_state.get("_pending_prompt"):
    prompt = st.session_state.pop("_pending_prompt")
    with st.spinner("🤔 Thinking..."):
        try:
            response = _run_async(st.session_state.agent.process_user_input(prompt))
        except Exception as e:
            response = f"❌ Error: {e}"
    tab = _tab()
    tab["messages"].append({"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()})
    _mark_dirty(tab)
    threading.Thread(target=_save_json, args=(tab,), daemon=True).start()
    _list_history.clear()
    st.session_state._processing = False
    st.rerun()

tab = _tab()

# Chat input handled BEFORE message rendering so new user msg shows immediately
if st.session_state.get("_processing"):
    st.info("⏳ Processing your request...")
else:
    prompt = st.chat_input(f"Ask in [{tab['name']}]...")
    if prompt:
        process_input(prompt)
        st.rerun()

if tab["task_names"]:
    st.info(f"⏳ **Active tasks:** {', '.join(tab['task_names'])}")

for idx, msg in enumerate(tab["messages"]):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and st.session_state.voice_mode and st.session_state.tts_enabled and idx == len(tab["messages"])-1:
            st.button("🔊", key=f"sp_{idx}", on_click=lambda c=msg["content"]: speak_text(c))

# Speak last assistant msg once (only when not mid-processing)
if not st.session_state.get("_processing") and st.session_state.voice_mode and st.session_state.tts_enabled and tab["messages"]:
    last = tab["messages"][-1]
    k = f"lss_{tab['id']}"
    if last["role"] == "assistant" and st.session_state.get(k) != len(tab["messages"]):
        st.session_state[k] = len(tab["messages"])
        speak_text(last["content"])

st.markdown("---")
st.caption("ArynoxTech AI Agent · MIT License · 16 tools · Multi-tab · Background automation")
