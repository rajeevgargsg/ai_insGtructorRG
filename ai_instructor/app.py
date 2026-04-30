"""
Algorithmic Instructional Designer -- Streamlit App
UI matches the AID reference design:
  Left  : upload files, pick files, learner profile, topic
  Right : result stats, 4 PDF downloads, run history table
"""

import io
import logging
import os
import pathlib
import sys
import time

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from core import (
    GenerationConfig,
    LearnerProfile,
    LessonArtifacts,
    LessonController,
    PROFILE_LABELS,
)
from core.pdf_generator import artifacts_to_pdf_bytes
try:
    from core.utils import token_stats, reset_token_stats
except ImportError:
    # Fallback if core/utils.py is an older version without token tracking
    token_stats = {"prompt": 0, "completion": 0, "calls": 0}
    def reset_token_stats():
        token_stats["prompt"] = 0
        token_stats["completion"] = 0
        token_stats["calls"] = 0

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Algorithmic Instructional Designer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}

/* hide default streamlit header padding */
.block-container{padding-top:1.5rem;padding-bottom:2rem;}

/* section headers */
.sec-hdr{
  font-size:.72rem;font-weight:600;letter-spacing:.09em;
  text-transform:uppercase;color:var(--color-text-secondary);
  margin:0 0 .5rem;
}

/* file pill */
.file-pill{
  display:inline-flex;align-items:center;gap:6px;
  background:var(--color-background-secondary);
  border:1px solid var(--color-border-tertiary);
  border-radius:6px;padding:4px 10px;font-size:.8rem;
  color:var(--color-text-secondary);margin:3px 3px 3px 0;
}

/* profile radio pills */
.profile-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;}
.p-pill{
  padding:6px 16px;border-radius:20px;font-size:.82rem;font-weight:500;
  border:1.5px solid var(--color-border-secondary);
  background:var(--color-background-primary);
  color:var(--color-text-secondary);cursor:pointer;transition:all .15s;
}
.p-pill.active{
  background:#7F77DD;border-color:#534AB7;color:#fff;
}

/* result card */
.result-card{
  background:var(--color-background-secondary);
  border:1px solid var(--color-border-tertiary);
  border-radius:12px;padding:1.2rem 1.4rem;
  margin-bottom:1rem;
}
.result-card h3{font-size:1rem;font-weight:600;margin:0 0 .6rem;}

/* stat row */
.stat-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:.5rem;}
.stat-chip{
  font-size:.78rem;
  background:var(--color-background-tertiary);
  border:1px solid var(--color-border-tertiary);
  border-radius:5px;padding:2px 8px;
  color:var(--color-text-secondary);
}
.stat-chip b{color:var(--color-text-primary);}
.chip-green{background:#EAF3DE;border-color:#C0DD97;color:#3B6D11;}
.chip-amber{background:#FAEEDA;border-color:#FAC775;color:#854F0B;}
.chip-red  {background:#FCEBEB;border-color:#F7C1C1;color:#A32D2D;}
.chip-blue {background:#E6F1FB;border-color:#B5D4F4;color:#185FA5;}

/* dl button row */
.dl-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:.8rem;}
.dl-btn-lbl{
  font-size:.75rem;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;color:var(--color-text-secondary);
  margin-bottom:3px;
}

/* run history table */
.run-table{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:.5rem;}
.run-table th{
  background:var(--color-background-tertiary);
  border-bottom:1px solid var(--color-border-secondary);
  padding:6px 8px;text-align:left;font-weight:600;
  color:var(--color-text-secondary);font-size:.72rem;
  text-transform:uppercase;letter-spacing:.06em;
}
.run-table td{
  padding:6px 8px;border-bottom:1px solid var(--color-border-tertiary);
  color:var(--color-text-primary);vertical-align:top;
}
.run-table tr:last-child td{border-bottom:none;}
.badge{
  display:inline-block;border-radius:4px;padding:1px 7px;
  font-size:.72rem;font-weight:600;
}
.badge-pass{background:#EAF3DE;color:#3B6D11;}
.badge-fail{background:#FAEEDA;color:#854F0B;}
.badge-rl  {background:#FCEBEB;color:#A32D2D;}

/* generate button */
.stButton>button[kind="primary"]{
  width:100%;background:linear-gradient(135deg,#7F77DD,#534AB7);
  border:none;color:#fff;font-weight:600;border-radius:8px;
  padding:.6rem 1rem;font-size:.9rem;transition:all .2s;
}
.stButton>button[kind="primary"]:hover{
  transform:translateY(-1px);box-shadow:0 4px 14px rgba(127,119,221,.4);
}

/* log console */
.log-console{
  background:#0D1B2A;border-radius:8px;padding:.8rem 1rem;
  font-family:monospace;font-size:.75rem;color:#94A3B8;
  max-height:180px;overflow-y:auto;line-height:1.8;
}
.lc-done{color:#34D399;}.lc-run{color:#FCD34D;}
.lc-warn{color:#F87171;}.lc-info{color:#93C5FD;}

/* main header */
.main-hdr{
  background:linear-gradient(135deg,#0D1B2A 0%,#1B3A5F 50%,#534AB7 100%);
  border-radius:12px;padding:1.4rem 1.8rem;margin-bottom:1.5rem;color:#fff;
}
.main-hdr h1{font-size:1.5rem;font-weight:700;margin:0 0 .2rem;}
.main-hdr p{font-size:.85rem;opacity:.75;margin:0;}
.hdr-badge{
  display:inline-block;background:rgba(255,255,255,.15);
  border:1px solid rgba(255,255,255,.25);border-radius:14px;
  padding:.15rem .7rem;font-size:.72rem;font-weight:600;margin-right:.4rem;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
_defaults = dict(
    uploaded_files={},      # {name: bytes}
    selected_files=set(),   # names ticked for current run
    artifacts=None,
    pdf_bytes={},
    running=False,
    log_msgs=[],
    run_history=[],         # list of run summary dicts
    error=None,
    last_stats={},
)
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_text(file_bytes: bytes, name: str) -> str:
    ext = pathlib.Path(name).suffix.lower()
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as e:
            return f"[PDF error: {e}]"
    return file_bytes.decode("utf-8", errors="ignore")


def _log_html(msgs):
    lines = []
    for m in msgs[-20:]:
        tail = m.split("|")[-1]
        if any(x in m for x in ["DONE","PASS"]):
            cls = "lc-done"
        elif any(x in m for x in ["START","RETRY"]):
            cls = "lc-run"
        elif any(x in m for x in ["ERROR","MAXRETRY"]):
            cls = "lc-warn"
        else:
            cls = "lc-info"
        lines.append(f'<div class="{cls}">&rsaquo; {tail}</div>')
    return '<div class="log-console">' + "\n".join(lines) + "</div>"


def _fmt_bytes(n):
    return f"{n/1024:.1f} KB" if n < 1024*1024 else f"{n/1024/1024:.1f} MB"


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-hdr">
  <span class="hdr-badge">Groq</span>
  <span class="hdr-badge">LLaMA 3.3 70B</span>
  <span class="hdr-badge">Multi-Agent</span>
  <h1>The Algorithmic Instructional Designer</h1>
  <p>Upload source files. Pick which to include. Choose a learner profile.
     Click Generate. AID produces a verified, personalised lesson and
     renders it as polished PDFs you can download.</p>
</div>
""", unsafe_allow_html=True)

# ── API key (hidden input at top) ─────────────────────────────────────────────
api_key = st.text_input(
    "Groq API Key",
    value=os.getenv("GROQ_API_KEY",""),
    type="password",
    placeholder="gsk_…   (get a free key at console.groq.com)",
    label_visibility="collapsed",
)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TWO-COLUMN LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
left, right = st.columns([1, 1], gap="large")

# ─────────────────────────────────────────────────────────────────────────────
# LEFT COLUMN
# ─────────────────────────────────────────────────────────────────────────────
with left:

    # ── 1. Upload source files ────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">1. Upload source files</div>',
                unsafe_allow_html=True)

    new_files = st.file_uploader(
        "Drag PDFs / TXT / MD files here (or click to browse)",
        accept_multiple_files=True,
        type=["pdf","txt","md"],
        label_visibility="collapsed",
    )
    if new_files:
        for f in new_files:
            data = f.read()
            if f.name not in st.session_state.uploaded_files:
                st.session_state.uploaded_files[f.name] = data
                st.session_state.selected_files.add(f.name)

    if st.session_state.uploaded_files:
        for name, data in st.session_state.uploaded_files.items():
            sz = _fmt_bytes(len(data))
            st.markdown(
                f'<div class="file-pill">📄 {name} &nbsp;<span style="opacity:.5">{sz}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 2. Pick files for this run ────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">2. Pick which files to include in this run</div>',
                unsafe_allow_html=True)

    if st.session_state.uploaded_files:
        cols = st.columns(2)
        for i, name in enumerate(st.session_state.uploaded_files):
            with cols[i % 2]:
                checked = name in st.session_state.selected_files
                if st.checkbox(
                    f"{name} ({_fmt_bytes(len(st.session_state.uploaded_files[name]))})",
                    value=checked,
                    key=f"chk_{name}",
                ):
                    st.session_state.selected_files.add(name)
                else:
                    st.session_state.selected_files.discard(name)

        if st.button("↺  Refresh file list", use_container_width=False):
            st.rerun()
    else:
        st.caption("No files uploaded yet.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 3. Learner profile ────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">3. Pick a learner profile</div>',
                unsafe_allow_html=True)

    profile_options = ["beginner","ms_student","product_manager"]
    profile_labels  = ["Beginner","MSc Student","Product Manager"]
    profile_map     = {
        "beginner":        LearnerProfile.BEGINNER,
        "ms_student":      LearnerProfile.MSC_STUDENT,
        "product_manager": LearnerProfile.PRODUCT_MANAGER,
    }

    sel_profile = st.radio(
        "Learner profile",
        options=profile_options,
        format_func=lambda x: profile_labels[profile_options.index(x)],
        horizontal=True,
        label_visibility="collapsed",
        index=1,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 4. Topic ──────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">4. (Optional) Topic title and description</div>',
                unsafe_allow_html=True)

    topic_title = st.text_input(
        "Topic title",
        value="Embeddings and Vector Databases",
        label_visibility="collapsed",
        placeholder="Topic title",
    )
    topic_desc = st.text_area(
        "Topic description",
        value="How text is encoded as numeric vectors and retrieved at scale.",
        label_visibility="collapsed",
        placeholder="Topic description (optional)",
        height=70,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 5. Quality settings ───────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">5. Quality settings</div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        pass_threshold = st.slider(
            "Pass threshold %", 50, 90, 75, 5,
            help="Simulated student must score this % to pass"
        )
    with c2:
        max_retries = st.slider(
            "Max revisions", 0, 2, 0,
            help="Set to 0 on free Groq tier to save tokens"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Generate button ───────────────────────────────────────────────────────
    generate = st.button(
        "⚡  Generate lesson",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.running,
    )

    # ── Live log ──────────────────────────────────────────────────────────────
    if st.session_state.log_msgs:
        st.markdown("<br>", unsafe_allow_html=True)
        log_ph = st.empty()
        log_ph.markdown(
            _log_html(st.session_state.log_msgs),
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# RIGHT COLUMN
# ─────────────────────────────────────────────────────────────────────────────
with right:
    st.markdown('<div class="sec-hdr">Result</div>', unsafe_allow_html=True)

    result_ph   = st.empty()
    download_ph = st.empty()
    history_ph  = st.empty()

    def _render_right():
        """Render the result, downloads, and history panels."""
        with result_ph.container():
            if st.session_state.error:
                err = st.session_state.error
                is_rl = "RATE_LIMIT" in err
                if is_rl:
                    st.warning("⏱️  Groq rate limit hit")
                    st.markdown(err.replace("RATE_LIMIT:","").strip())
                else:
                    st.error("❌ Pipeline error")
                    with st.expander("Traceback"):
                        st.code(err, language="python")

            elif st.session_state.artifacts:
                arts  = st.session_state.artifacts
                stats = st.session_state.last_stats
                files_used = ", ".join(stats.get("files",[]))
                score      = stats.get("score_pct", 0)
                iters      = stats.get("iters", 1)
                tok_in     = stats.get("tok_in", 0)
                tok_out    = stats.get("tok_out", 0)
                calls      = stats.get("calls", 0)
                cost_usd   = (tok_in * 0.59 + tok_out * 0.79) / 1_000_000
                status_lbl = stats.get("status","done")

                st.markdown(f"**✓ {topic_title}** generated in {stats.get('elapsed',0)}s")

                chip_cls = "chip-green" if stats.get("passed") else \
                           "chip-red"   if "rate" in status_lbl.lower() else "chip-amber"

                st.markdown(
                    f"""<div class="stat-row">
  <span class="stat-chip">Profile: <b>{sel_profile}</b></span>
  <span class="stat-chip">Files: <b>{len(stats.get('files',[]))} — {files_used}</b></span>
  <span class="stat-chip {chip_cls}">Status: <b>{status_lbl}</b></span>
  <span class="stat-chip chip-blue">LLM usage: <b>{calls} calls</b>,
    {tok_in:,} in + {tok_out:,} out = {tok_in+tok_out:,} tokens
    (~${cost_usd:.3f})</span>
</div>""",
                    unsafe_allow_html=True,
                )

        with download_ph.container():
            if st.session_state.pdf_bytes:
                st.markdown("**Four PDFs ready to download:**")
                pdf = st.session_state.pdf_bytes
                dl_labels = [
                    ("lesson_plan",        "1. Lesson plan",
                     "(teacher's full reference, with reasoning + rationales)"),
                    ("student_handout",    "2. Student handout",
                     "(pre-class reading, key vocab, analogies)"),
                    ("quiz",               "3. Quiz",
                     "(student version, no answers)"),
                    ("teacher_answer_key", "4. Quiz teacher answer key",
                     "(with rationales)"),
                ]
                for key, label, note in dl_labels:
                    if key in pdf:
                        sz = _fmt_bytes(len(pdf[key]))
                        st.download_button(
                            label=f"📄 {label} — {sz}",
                            data=pdf[key],
                            file_name=f"AID_{topic_title.replace(' ','_')}_{key}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"dl_{key}_{len(st.session_state.run_history)}",
                            help=note,
                        )

        with history_ph.container():
            if st.session_state.run_history:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown('<div class="sec-hdr">Runs this session</div>',
                            unsafe_allow_html=True)
                rows = ""
                for i, r in enumerate(st.session_state.run_history, 1):
                    badge_cls = "badge-pass" if r["passed"] \
                        else "badge-rl" if "rate" in r["status"].lower() \
                        else "badge-fail"
                    rows += f"""<tr>
  <td>{i}</td>
  <td style="font-size:.72rem">{r['when']}</td>
  <td>{r['topic']}</td>
  <td><code style="font-size:.72rem">{r['profile']}</code></td>
  <td style="font-size:.72rem">{r['files']}</td>
  <td>{r['score_pct']}%</td>
  <td>{r['iters']}</td>
  <td>{r['tokens']:,}</td>
  <td>~${r['cost']:.3f}</td>
  <td><span class="badge {badge_cls}">{r['status']}</span></td>
</tr>"""
                st.markdown(
                    f"""<table class="run-table">
<tr>
  <th>#</th><th>When</th><th>Topic</th><th>Profile</th>
  <th>Files</th><th>Score</th><th>Iters</th>
  <th>Tokens</th><th>~Cost</th><th>Status</th>
</tr>
{rows}
</table>""",
                    unsafe_allow_html=True,
                )

    _render_right()


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION
# ══════════════════════════════════════════════════════════════════════════════
if generate:
    if not api_key.strip():
        st.error("⚠️  Enter your Groq API key at the top.")
        st.stop()

    selected = list(st.session_state.selected_files)
    if not selected and not st.session_state.uploaded_files:
        st.error("⚠️  Upload at least one source file.")
        st.stop()

    # Build source text from selected files (or all if none ticked)
    files_to_use = selected if selected else list(st.session_state.uploaded_files)
    source_parts = []
    for name in files_to_use:
        data = st.session_state.uploaded_files.get(name, b"")
        source_parts.append(f"--- {name} ---\n{_load_text(data, name)}")
    source = "\n\n".join(source_parts)

    if not source.strip():
        st.error("⚠️  Could not read content from selected files.")
        st.stop()

    cfg = GenerationConfig(
        topic_title       = topic_title or "Lesson",
        topic_description = topic_desc,
        learner_profile   = profile_map[sel_profile],
        pass_threshold    = pass_threshold / 100.0,
        max_retries       = max_retries,
        max_tokens        = 1024,
    )

    # Reset state
    st.session_state.update({
        "artifacts": None,
        "pdf_bytes": {},
        "running":   True,
        "log_msgs":  [],
        "error":     None,
    })
    reset_token_stats()

    t_start = time.time()
    log_box = left.empty()

    def _cb(msg):
        st.session_state.log_msgs.append(msg)
        log_box.markdown(
            _log_html(st.session_state.log_msgs),
            unsafe_allow_html=True,
        )

    try:
        ctrl               = LessonController(api_key=api_key.strip(), cfg=cfg)
        artifacts, iter_log = ctrl.run(source, progress_cb=_cb)

        elapsed  = round(time.time() - t_start)
        last     = iter_log[-1] if iter_log else {}
        score    = last.get("score_pct", 0)
        passed   = last.get("passed", False)
        iters    = len(iter_log)
        tok_in   = token_stats["prompt"]
        tok_out  = token_stats["completion"]
        calls    = token_stats["calls"]
        cost     = (tok_in * 0.59 + tok_out * 0.79) / 1_000_000

        if passed:
            status = "passed"
        elif iters > 1:
            status = f"retry cap hit (score {score}%, {iters} iteration(s))"
        else:
            status = f"complete (score {score}%)"

        st.session_state.artifacts  = artifacts
        st.session_state.last_stats = {
            "files":   files_to_use,
            "score_pct": score,
            "passed":  passed,
            "iters":   iters,
            "tok_in":  tok_in,
            "tok_out": tok_out,
            "calls":   calls,
            "elapsed": elapsed,
            "status":  status,
        }

        with st.spinner("Rendering PDFs ..."):
            st.session_state.pdf_bytes = artifacts_to_pdf_bytes(artifacts, cfg)

        # Add to run history
        st.session_state.run_history.append({
            "when":      time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "topic":     topic_title,
            "profile":   sel_profile,
            "files":     ", ".join(files_to_use),
            "score_pct": score,
            "passed":    passed,
            "iters":     iters,
            "tokens":    tok_in + tok_out,
            "cost":      cost,
            "status":    status,
        })

        st.session_state.running = False
        st.rerun()

    except RuntimeError as exc:
        err_str = str(exc)
        is_rl   = "RATE_LIMIT" in err_str
        st.session_state.error   = err_str if is_rl else (
            "RATE_LIMIT: " + err_str if "rate" in err_str.lower() else err_str
        )
        st.session_state.running = False

        # Still log to history
        tok_in  = token_stats["prompt"]
        tok_out = token_stats["completion"]
        cost    = (tok_in * 0.59 + tok_out * 0.79) / 1_000_000
        st.session_state.run_history.append({
            "when":      time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "topic":     topic_title,
            "profile":   sel_profile,
            "files":     ", ".join(files_to_use),
            "score_pct": 0,
            "passed":    False,
            "iters":     0,
            "tokens":    tok_in + tok_out,
            "cost":      cost,
            "status":    "rate limit" if is_rl else "error",
        })
        st.rerun()

    except Exception:
        import traceback
        st.session_state.error   = traceback.format_exc()
        st.session_state.running = False
        st.rerun()
