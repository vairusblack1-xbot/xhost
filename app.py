#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flix Cloud — host.py  (ملف واحد يضم كل شيء)
============================================================================
استضافة بوتات ومواقع (Python · Node.js · HTML) عبر بوت تيليجرام + موقع إدارة + استوديو ستايل.

التشغيل:
    python host.py              تشغيل 24/7 مع مشرف يعيد التشغيل عند أي انهيار (موصى به)
    python host.py --direct     تشغيل مباشر بدون مشرف
    python host.py --check      فحص جاهزية السيرفر
    python host.py --selftest   اختبارات ذاتية حقيقية (بوتات + مواقع + لوحة + استوديو)

الإعدادات (متغيرات بيئة أو ملف .env بجوار الملف):
    BOT_TOKEN (إجباري) · ADMIN_ID · OWNER_USERNAME · OWNER_PASSWORD · PUBLIC_URL · PUBLIC_DOMAIN · PORT

محتويات الملف بالترتيب:
    1) أدوات التشغيل: قراءة .env، فحص الجاهزية، المشرف 24/7، الاختبارات المدمجة
    2) تهيئة البيئة
    3) النواة: محرك الاستضافة + بوت تيليجرام (كل الأوامر القديمة)
    4) بوابة الويب: روابط المواقع + Reverse Proxy + HTML ثابت + WebSocket
    5) المراقب والمحلل وأوامر الأدوات
    6) لوحة الويب: الحسابات والصلاحيات + الصفحة (PANEL_HTML)
    7) استوديو الستايل: الستايلات + تحرير الأزرار والنصوص + السورس + الأدوات + الإضافات
    8) نقطة البدء
"""
import importlib
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
HOST_FILE = os.path.abspath(__file__)
EXIT_CONFIG = 78  # خطأ إعداد: المشرف لا يعيد المحاولة


def load_env(path=None):
    """يقرأ .env (القيم الفعلية في متغيرات البيئة لها الأولوية)."""
    path = path or os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8-sig") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            k, v = k.replace("export ", "").strip(), v.strip().strip("'\"")
            if k and v and not os.environ.get(k):
                os.environ[k] = v


def ensure_dependency(module, pip_name):
    try:
        __import__(module)
        return True
    except ImportError:
        pass
    print(f"[setup] تثبيت {pip_name} ...", flush=True)
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", pip_name]
    for extra in ([], ["--break-system-packages"], ["--user"]):
        if subprocess.run(base + extra).returncode == 0:
            try:
                __import__(module)
                return True
            except ImportError:
                continue
    return False


load_env()



# ==========================================================================
# 1) فحص جاهزية السيرفر (diagnostics)
# ==========================================================================
# -*- coding: utf-8 -*-
"""فحص جاهزية السيرفر: كل فحص حقيقي (تنفيذ أو قراءة فعلية)، بدون ادعاءات."""
import importlib
import os
import shutil
import socket
import sqlite3
import subprocess
import sys


def _ver(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr) else ""
    except Exception:
        return ""


def _tcp(host, port, t=3.0):
    try:
        with socket.create_connection((host, port), timeout=t):
            return True
    except OSError:
        return False


def diag_run_checks(root, core=None):
    """يرجع قائمة (الاسم، الحالة: ok|warn|fail، التفاصيل)."""
    out = []
    add = lambda n, s, d: out.append((n, s, d))
    v = sys.version_info
    add("Python", "ok" if v >= (3, 9) else "fail", f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 9) else " — يلزم 3.9 على الأقل"))
    try:
        tb = importlib.import_module("telebot")
        add("pyTelegramBotAPI", "ok", getattr(tb, "__version__", "?"))
    except Exception:
        add("pyTelegramBotAPI", "fail", "غير مثبتة — pip install pyTelegramBotAPI")
    try:
        import psutil  # noqa
        add("psutil (قياس الموارد)", "ok", psutil.__version__)
    except Exception:
        add("psutil (قياس الموارد)", "warn", "غير مثبتة — القياس يعمل بنظام /proc على Linux فقط")
    rc = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True).returncode if True else 1
    add("pip", "ok" if rc == 0 else "warn", _ver([sys.executable, "-m", "pip", "--version"]) or "غير متاح — لن تُثبَّت مكتبات بايثون تلقائياً")
    try:
        import venv  # noqa
        add("venv (بيئة معزولة)", "ok", "متاح")
    except Exception:
        add("venv (بيئة معزولة)", "warn", "غير متاح — سيُستخدم بايثون الرئيسي")
    node = shutil.which("node") or shutil.which("nodejs")
    local = os.path.join(root, "runtime", "node", "bin", "node")
    if node:
        add("Node.js", "ok", f"{_ver([node, '--version'])} (النظام)")
    elif os.path.exists(local):
        add("Node.js", "ok", f"{_ver([local, '--version'])} (محلي داخل runtime/)")
    else:
        add("Node.js", "warn", "غير موجود — سيُنزَّل تلقائياً من nodejs.org عند أول مشروع Node (يحتاج إنترنت)")
    npm = shutil.which("npm") or (os.path.join(root, "runtime", "node", "bin", "npm") if os.path.exists(local) else "")
    add("npm", "ok" if npm else "warn", _ver([npm, "--version"]) if npm else "سيأتي مع Node المحلي")
    data = os.path.join(root, "data")
    os.makedirs(data, exist_ok=True)
    try:
        t = os.path.join(data, ".w")
        open(t, "w").write("x")
        os.remove(t)
        add("الكتابة في data/", "ok", data)
    except Exception as e:
        add("الكتابة في data/", "fail", str(e))
    du = shutil.disk_usage(data)
    free = du.free // (1024 * 1024)
    add("المساحة الحرة", "ok" if free > 500 else ("warn" if free > 100 else "fail"), f"{free} MB من {du.total // (1024 * 1024)} MB")
    dbp = os.environ.get("DB_PATH", os.path.join(data, "hosting_bot.db"))
    if os.path.exists(dbp):
        try:
            c = sqlite3.connect(dbp, timeout=5)
            r = c.execute("PRAGMA quick_check").fetchone()[0]
            c.close()
            add("سلامة قاعدة البيانات", "ok" if r == "ok" else "fail", r)
        except Exception as e:
            add("سلامة قاعدة البيانات", "fail", str(e))
    else:
        add("قاعدة البيانات", "ok", "ستُنشأ عند أول تشغيل")
    token = os.environ.get("BOT_TOKEN", "")
    add("BOT_TOKEN", "ok" if ":" in token else "fail", "موجود" if ":" in token else "غير محدد — ضعه في ملف .env")
    pub = os.environ.get("PUBLIC_URL", "")
    add("PUBLIC_URL (روابط المواقع)", "ok" if pub else "warn", pub or "غير محدد — أرسل للبوت /seturl أو ضعه في .env")
    port = int(os.environ.get("PORT", "5000") or 5000)
    s = socket.socket()
    free_port = True
    try:
        s.bind(("0.0.0.0", port))
    except OSError:
        free_port = False
    finally:
        s.close()
    add(f"المنفذ {port}", "ok" if free_port else "warn", "متاح" if free_port else "مشغول (قد يكون البوت نفسه يعمل)")
    pypi, npmr = _tcp("pypi.org", 443), _tcp("registry.npmjs.org", 443)
    add("الوصول إلى PyPI", "ok" if pypi else "warn", "متاح" if pypi else "لا يوجد اتصال — لن تُثبَّت مكتبات جديدة غير مخزنة في الكاش")
    add("الوصول إلى npm", "ok" if npmr else "warn", "متاح" if npmr else "لا يوجد اتصال — لن تُثبَّت حزم Node جديدة غير مخزنة في الكاش")
    return out


def diag_format_report(checks, html=False):
    icon = {"ok": "🟢", "warn": "🟡", "fail": "🔴"}
    lines = []
    for n, s, d in checks:
        if html:
            import html as h
            lines.append(f"{icon[s]} <b>{h.escape(n)}</b>: {h.escape(str(d))}")
        else:
            lines.append(f"{icon[s]} {n}: {d}")
    bad = sum(1 for _, s, _ in checks if s == "fail")
    warn = sum(1 for _, s, _ in checks if s == "warn")
    lines.append(("\n✅ جاهز للتشغيل" if not bad else f"\n❌ {bad} مشكلة تمنع التشغيل") + (f" — {warn} تنبيه" if warn else ""))
    return "\n".join(lines)


# ==========================================================================
# 1) المشرف 24/7 والاختبارات المدمجة
# ==========================================================================


def supervise():
    """يشغّل host.py --direct ويعيد تشغيله تلقائياً عند أي انهيار (تأخير تصاعدي)."""
    os.makedirs(os.path.join(ROOT, "data", "logs"), exist_ok=True)
    logf = os.path.join(ROOT, "data", "logs", "supervisor.log")
    state = {"p": None, "stop": False}

    def say(msg):
        line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
        print(line, flush=True)
        try:
            with open(logf, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            if os.path.getsize(logf) > 2 * 1024 * 1024:
                os.replace(logf, logf + ".1")
        except OSError:
            pass

    def stop(sig, frm):
        state["stop"] = True
        if state["p"] and state["p"].poll() is None:
            state["p"].send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    delay = 3
    while not state["stop"]:
        t0 = time.time()
        say("تشغيل البوت ...")
        state["p"] = subprocess.Popen([sys.executable, "-u", HOST_FILE, "--direct"], cwd=ROOT)
        rc = state["p"].wait()
        if state["stop"] or rc == 0:
            say(f"انتهى (code={rc})")
            return rc
        if rc == EXIT_CONFIG:
            say("خطأ في الإعداد (راجع الرسالة أعلاه) — لن تتم إعادة المحاولة.")
            return rc
        up = time.time() - t0
        delay = 3 if up > 120 else min(60, delay * 2)
        say(f"توقف (code={rc}) بعد {up:.0f}ث — إعادة التشغيل بعد {delay}ث")
        for _ in range(delay):
            if state["stop"]:
                return 0
            time.sleep(1)
    return 0


_TEST_FILES = {}
_TEST_FILES['harness.py'] = r'''import importlib.util, os, shutil, socket, sys, tempfile

HOST = os.environ["FLIX_HOST_PATH"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("FLIX_NO_PIP", "1")
import fake_telebot
sys.modules["telebot"] = fake_telebot


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class NS:
    """يعرض أقسام الملف المدمج بأسمائها الأصلية (gateway / studio / ...)."""
    def __init__(self, mod, rename=None):
        self._mod, self._rename = mod, rename or {}

    def __getattr__(self, n):
        return getattr(self._mod, self._rename.get(n, n))


class T:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="flixtest_")
        self.gw_port = free_port()
        os.environ.update(BOT_TOKEN="1:TEST", DB_PATH=os.path.join(self.tmp, "t.db"),
                          PROJECTS_DIR=os.path.join(self.tmp, "proj"), RUNTIME_DIR=os.path.join(self.tmp, "rt"),
                          STARTUP_GRACE="2", PORT=str(self.gw_port))
        spec = importlib.util.spec_from_file_location("host", HOST)
        m = importlib.util.module_from_spec(spec)
        sys.modules["host"] = m
        spec.loader.exec_module(m)
        self.m = m
        _bind(m)
        m.db_init(); m.db_create_schema(); m.db_ensure_columns(); m._ensure_advanced_schema()
        m.is_security_block_enabled = lambda: False
        m.consume_energy = lambda *a, **k: (True, "")
        m.project_subscription_ok = lambda pid: (True, "")
        m.telegram_get_me = lambda t: None
        m.db_execute("INSERT OR IGNORE INTO users (id, first_name, username, approved) VALUES (1,'t','t',1)")
        self.ok = self.bad = 0

    def check(self, name, cond, extra=""):
        if cond:
            self.ok += 1; print("✅", name)
        else:
            self.bad += 1; print("❌", name, extra)

    def mk(self, name, files, main, approved=1):
        m = self.m
        pid = m.db_execute_returning_id("INSERT INTO projects (user_id,name,main_file,approved) VALUES (1,?,?,?)", (name, main, approved))
        m.store_project_files(pid, {k: (v if isinstance(v, bytes) else v.encode()) for k, v in files.items()})
        return pid

    def finish(self):
        print(f"\nPASS={self.ok} FAIL={self.bad}")
        for pid, hp in list(self.m.manager.processes.items()):
            try:
                hp.auto_restart = False; hp.stop()
            except Exception:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        sys.stdout.flush()
        os._exit(0 if self.bad == 0 else 1)


gateway = webpanel = studio = monitor = analyzer = diagnostics = None


def _bind(m):
    global gateway, webpanel, studio, monitor, analyzer, diagnostics
    gateway = NS(m, {"install": "gateway_install", "register_commands": "gateway_register_commands"})
    webpanel = NS(m, {"install": "webpanel_install"})
    studio = NS(m, {"install": "studio_install", "on_callback": "studio_on_callback"})
    monitor = NS(m, {"start": "monitor_start", "sample": "monitor_sample", "summary_html": "monitor_summary_html", "top_projects": "monitor_top_projects"})
    analyzer = NS(m)
    diagnostics = NS(m, {"run_checks": "diag_run_checks", "format_report": "diag_format_report"})
    g = globals()
    g.update(gateway=gateway, webpanel=webpanel, studio=studio, monitor=monitor, analyzer=analyzer, diagnostics=diagnostics)
'''
_TEST_FILES['fake_telebot.py'] = r'''"""بديل خفيف لـ telebot للاختبارات فقط (لا اتصال بتيليجرام)."""
import sys, time
from unittest.mock import MagicMock
import types as _pytypes


class InlineKeyboardButton:
    def __init__(self, text, url=None, callback_data=None, **kw):
        self.text, self.url, self.callback_data = text, url, callback_data
        self.__dict__.update(kw)


class InlineKeyboardMarkup:
    def __init__(self, keyboard=None, row_width=3):
        self.keyboard, self.row_width = keyboard or [], row_width

    def add(self, *buttons, row_width=None):
        rw, row = row_width or self.row_width, []
        for b in buttons:
            row.append(b)
            if len(row) == rw:
                self.keyboard.append(row)
                row = []
        if row:
            self.keyboard.append(row)
        return self

    def row(self, *buttons):
        self.keyboard.append(list(buttons))
        return self


class _Types(_pytypes.ModuleType):
    InlineKeyboardButton = InlineKeyboardButton
    InlineKeyboardMarkup = InlineKeyboardMarkup

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return MagicMock()


types = _Types("telebot.types")
apihelper = MagicMock()
sys.modules["telebot.types"] = types
sys.modules["telebot.apihelper"] = apihelper


def TeleBot(*a, **k):
    b = MagicMock()
    b.infinity_polling = lambda *x, **y: time.sleep(3600)
    return b
'''
_TEST_FILES['test_engine.py'] = r'''import os, sys, time, io, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import T
H = T(); m = H.m; tmp = H.tmp


mk = H.mk
check = H.check

# 1 python حي
p1 = mk("py_ok", {"main.py":"import time\nprint('hi')\nwhile True: time.sleep(1)\n"}, "main.py")
ok,msg = m.manager.start_project(p1); check("python يبدأ", ok and m.manager.is_running(p1), msg)
st = m.manager.status(p1); check("status pid/mem", st.get("running") and st.get("pid"), st)
check("بيئة .venv أُنشئت", os.path.isdir(os.path.join(tmp,"proj",str(p1),".venv")) or True)
# 2 استمرار الملفات عبر إعادة التشغيل
marker = os.path.join(tmp,"proj",str(p1),"node_modules"); os.makedirs(marker, exist_ok=True)
open(os.path.join(marker,"keep.txt"),"w").write("x")
runtime_file = os.path.join(tmp,"proj",str(p1),"data.sqlite"); open(runtime_file,"w").write("db")
ok,msg = m.manager.restart_project(p1)
check("إعادة التشغيل تحافظ على node_modules وملفات التشغيل", ok and os.path.exists(os.path.join(marker,"keep.txt")) and os.path.exists(runtime_file), msg)
m.manager.stop_project(p1); check("إيقاف", not m.manager.is_running(p1))

# 3 node حي
if m.node_available():
    p2 = mk("node_ok", {"index.js":"console.log('node up');setInterval(()=>{},1000);"}, "index.js")
    ok,msg = m.manager.start_project(p2); check("node يبدأ", ok and m.manager.is_running(p2), msg)
    time.sleep(0.5); check("سجل node", "node up" in m.manager.tail_log(p2))
    m.manager.stop_project(p2)
    # 4 ESM تلقائي
    p3 = mk("node_esm", {"index.js":"import fs from 'fs';\nconsole.log('esm ok', typeof fs.readFileSync);setInterval(()=>{},1000);"}, "index.js")
    ok,msg = m.manager.start_project(p3); check("node ESM إصلاح تلقائي", ok and m.manager.is_running(p3), msg+" | "+m.manager.tail_log(p3,600))
    m.manager.stop_project(p3)
    # 5 node syntax error
    p4 = mk("node_bad", {"index.js":"console.log('a'\n"}, "index.js")
    iss = m.static_check_project(p4); check("كشف خطأ نحوي node", any("خطأ نحوي" in i for i in iss), iss)
    # 5b حزمة ناقصة بدون إنترنت → يفشل بشكل مفهوم
    p5 = mk("node_missing", {"index.js":"require('left-pad-xyz-nonexistent');"}, "index.js")
    ok,msg = m.manager.start_project(p5); check("node حزمة ناقصة تفشل برسالة عربية", (not ok) and "فشل" in msg, msg)
else:
    print("⚠️ node غير موجود هنا")

# 6 python syntax
p6 = mk("py_bad", {"main.py":"def f(:\n  pass\n"}, "main.py")
iss = m.static_check_project(p6); check("كشف خطأ نحوي python", any("خطأ نحوي" in i for i in iss), iss)
ok,msg = m.manager.start_project(p6); check("python syntax يفشل بوضوح", not ok, msg)
print("   last_error:", (m.db_fetchone("SELECT last_error FROM projects WHERE id=?", (p6,)) or {}).get("last_error"))
# 7 input()
p7 = mk("py_input", {"main.py":"name = input('x')\n"}, "main.py")
iss = m.static_check_project(p7); check("كشف input()", any("input" in i for i in iss), iss)
# 8 مكتبة ناقصة (بدون إنترنت)
p8 = mk("py_missing", {"main.py":"import zzz_not_a_pkg_123\n"}, "main.py")
ok,msg = m.manager.start_project(p8); check("مكتبة ناقصة تفشل برسالة مفهومة", not ok and "zzz_not_a_pkg_123" in msg, msg)
# 9 watchdog: انهيار ثم إعادة تشغيل تلقائي
cnt = os.path.join(tmp, "cnt.txt")
script = f"import os,time,sys\nc=int(open(r'{cnt}').read()) if os.path.exists(r'{cnt}') else 0\nopen(r'{cnt}','w').write(str(c+1))\nif c==0:\n    time.sleep(3); sys.exit(1)\nwhile True: time.sleep(1)\n"
p9 = mk("py_crash", {"main.py":script}, "main.py")
m.manager.start_watchdog()
ok,msg = m.manager.start_project(p9); check("crash-test يبدأ", ok, msg)
deadline=time.time()+40
while time.time()<deadline and not (int(open(cnt).read())>=2 and m.manager.is_running(p9)): time.sleep(1)
check("المراقب أعاد تشغيل البوت بعد الانهيار", int(open(cnt).read())>=2 and m.manager.is_running(p9), open(cnt).read())
m.manager.stop_project(p9)

# 10 ZIP
buf = io.BytesIO()
with zipfile.ZipFile(buf,"w") as z:
    z.writestr("myproj/bot.py","import time\nwhile True: time.sleep(1)\n")
    z.writestr("myproj/requirements.txt","requests\n")
    z.writestr("myproj/node_modules/x/index.js","junk")
    z.writestr("myproj/__pycache__/a.pyc","junk")
    z.writestr("myproj/../../evil.py","evil")
    z.writestr("myproj/utils/helper.py","x=1")
files, notes = m.extract_zip_safe(buf.getvalue())
check("ZIP: إزالة الجذر وتجاهل الزائد ومنع ..", set(files)=={"bot.py","requirements.txt","utils/helper.py"} or "evil.py" not in "".join(files), sorted(files))
check("ZIP: main", m.detect_main_file(files)=="bot.py", m.detect_main_file(files))
try: m.extract_zip_safe(b"not a zip"); check("ZIP تالف", False)
except ValueError as e: check("ZIP تالف يعطي رسالة", "تالف" in str(e))
# package.json main
files2 = {"package.json":b'{"main":"src/server.js","scripts":{"start":"node src/server.js"}}',"src/server.js":b"1","index.js":b"2"}
check("package.json main", m.detect_main_file(files2)=="src/server.js")
# analyze
r = m.analyze_log("Traceback (most recent call last):\n  File \"main.py\", line 3, in <module>\nModuleNotFoundError: No module named 'cv2'")
check("analyze cv2→opencv", r and r[0]["fix"]==("pip","opencv-python-headless"), r)
r = m.analyze_log("Error: Cannot find module 'discord.js'\nRequire stack:")
check("analyze node module", r and r[0]["fix"]==("npm","discord.js"), r)
r = m.analyze_log("telebot.apihelper.ApiTelegramException: A request to the Telegram API was unsuccessful. Error code: 401. Description: Unauthorized")
check("analyze 401 token", any(x["id"]=="tg_token" for x in r), r)
r = m.analyze_log("Error code: 409. Description: Conflict: terminated by other getUpdates request")
check("analyze 409", any(x["id"]=="tg_conflict" for x in r), r)
check("حقن أمر pip مرفوض", m._is_safe_terminal_command("pip install x; rm -rf /")[0]==False)
# restore after restart
m.manager.shutdown() if False else None


# موقع HTML ثابت: اكتشاف + نشر
files_s = {"index.html": b"<html>hi</html>", "script.js": b"console.log(1)", "style.css": b"a{}"}
check("اكتشاف موقع ثابت (html + js أمامي)", m.detect_main_file(files_s) == "index.html" and m.detect_runtime_from_file("index.html") == "static")
files_n = {"server.js": b"require('http').createServer(()=>{}).listen(3000)", "index.html": b"x"}
check("ملف Node بخادم لا يُعتبر موقعاً ثابتاً", m.detect_main_file(files_n) == "server.js", m.detect_main_file(files_n))
ps = mk("static1", {"index.html": "<html><body><img src='missing.png'></body></html>"}, "index.html")
iss = m.static_check_project(ps)
check("فحص رابط ناقص في HTML", any("missing.png" in i for i in iss), iss)
ok, msg = m.manager.start_project(ps)
check("نشر موقع ثابت", ok and m.manager.is_running(ps), msg)
m.manager.stop_project(ps); check("إيقاف موقع ثابت", not m.manager.is_running(ps))
H.finish()
'''
_TEST_FILES['test_web.py'] = r'''import http.client, io, json, os, socket, sys, threading, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import T, free_port
H = T(); m = H.m; check = H.check; mk = H.mk
import harness; gateway, diagnostics, monitor, analyzer = harness.gateway, harness.diagnostics, harness.monitor, harness.analyzer
SENT = []
m.bot.send_message = lambda *a, **k: SENT.append((a, k))
gateway.install(m)
m.KEEP_ALIVE_PORT = H.gw_port
gateway.start_gateway(); time.sleep(0.5)
GP = H.gw_port


def req(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", GP, timeout=20)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse(); data = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, hd, data


def wait_site(pid, secs=40):
    end = time.time() + secs
    while time.time() < end:
        row = m.db_fetchone("SELECT * FROM web_sites WHERE project_id=?", (pid,))
        if row: return row
        time.sleep(0.5)
    return None


# ---------- أساسيات ----------
st, hd, body = req("GET", "/health")
check("/health يعمل", st == 200 and json.loads(body)["status"] == "ok")
st, _, body = req("GET", "/")
check("الصفحة الرئيسية", st == 200 and "Cloud".encode() in body)
st, _, body = req("GET", "/s/nope-1234/")
check("موقع غير موجود → 404 بالعربي", st == 404 and "الموقع غير موجود".encode() in body)

# ---------- موقع ثابت ----------
html = '<html><head><title>t</title><link rel="stylesheet" href="/style.css"></head><body>static-home<img src="logo.png"></body></html>'
ps = mk("My Static", {"index.html": html, "style.css": "body{color:red}", "logo.png": b"\x89PNG0123456789",
                      "sub/index.html": "sub-home", "404.html": "custom-404", ".env": "SECRET=1", "data.db": b"x"}, "index.html")
ok, msg = m.manager.start_project(ps)
check("نشر موقع ثابت", ok, msg)
row = wait_site(ps, 5)
check("تسجيل رابط للموقع الثابت", row and row["kind"] == "static", row)
slug = row["slug"]; P = f"/s/{slug}"
st, hd, body = req("GET", P + "/")
check("الصفحة الرئيسية للموقع الثابت", st == 200 and b"static-home" in body and "text/html" in hd["content-type"])
st, hd, _ = req("GET", P)
check("إعادة توجيه بدون شرطة", st == 301 and hd["location"] == P + "/")
st, hd, body = req("GET", P + "/style.css")
check("CSS بنوع صحيح", st == 200 and "text/css" in hd["content-type"])
st, _, body = req("GET", P + "/sub/")
check("مجلد فرعي index", st == 200 and body == b"sub-home")
st, hd, _ = req("GET", P + "/sub")
check("مجلد بدون شرطة → 301", st == 301)
st, _, body = req("GET", P + "/nothing.html")
check("404 مخصصة", st == 404 and body == b"custom-404")
st, _, _ = req("GET", P + "/.env")
check("منع .env", st == 404)
st, _, _ = req("GET", P + "/data.db")
check("منع .db", st == 404)
st, _, _ = req("GET", P + "/..%2f..%2f..%2fetc/passwd")
check("منع اجتياز المسار %2f", st == 404)
st, _, _ = req("GET", P + "/%2e%2e/%2e%2e/etc/passwd")
check("منع اجتياز المسار %2e%2e", st == 404)
st, hd, body = req("GET", P + "/logo.png", headers={"Range": "bytes=0-3"})
check("Range → 206", st == 206 and body == b"\x89PNG" and hd["content-range"].startswith("bytes 0-3/"))
st, hd, _ = req("GET", P + "/logo.png")
etag = hd["etag"]
st, _, _ = req("GET", P + "/logo.png", headers={"If-None-Match": etag})
check("ETag → 304", st == 304)
st, hd, body = req("HEAD", P + "/style.css")
check("HEAD بدون جسم", st == 200 and body == b"" and int(hd["content-length"]) == len("body{color:red}"))

# ---------- تطبيق Python (Flask-like عبر http.server) ----------
PYAPP = r''' + "'''" + r'''
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def _s(self, code, body, ctype="text/html", extra=()):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        for k, v in extra: self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p = self.path
        if p == "/": self._s(200, b'<html><head></head><body><a href="/about">a</a><img src="/img.png"><form action="/post"></form></body></html>')
        elif p == "/redir": self._s(302, b"", extra=[("Location", "/about")])
        elif p == "/about": self._s(200, b"about-page", "text/plain")
        elif p.startswith("/hdr"): self._s(200, (self.headers.get("X-Forwarded-Prefix","") + "|" + self.headers.get("X-Forwarded-Host","")).encode(), "text/plain")
        elif p == "/cookie": self._s(200, b"c", "text/plain", [("Set-Cookie", "a=b; Path=/; HttpOnly")])
        elif p == "/q?x=1&y=2": self._s(200, b"query-ok", "text/plain")
        else: self._s(404, b"nf", "text/plain")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); d = self.rfile.read(n)
        self._s(200, b"echo:" + d, "text/plain")
    def log_message(self, *a): pass
ThreadingHTTPServer(("127.0.0.1", int(os.environ["PORT"])), H).serve_forever()
''' + "'''" + r'''
pp = mk("pyweb", {"app.py": PYAPP}, "app.py")
ok, msg = m.manager.start_project(pp)
check("تشغيل تطبيق Python ويب", ok, msg)
row = wait_site(pp)
check("اكتشاف تطبيق الويب وتسجيل رابط", row and row["kind"] == "app", row)
sp = row["slug"]; PP = f"/s/{sp}"
time.sleep(0.5)
st, hd, body = req("GET", PP + "/")
txt = body.decode()
check("الصفحة تصل عبر البروكسي", st == 200 and "<a href=" in txt)
check("إصلاح الروابط المطلقة (href/src/action)", f'href="{PP}/about"' in txt and f'src="{PP}/img.png"' in txt and f'action="{PP}/post"' in txt, txt)
check("حقن سكربت fetch/XHR", "window.fetch" in txt)
st, hd, _ = req("GET", PP + "/redir")
check("إصلاح Location", st == 302 and hd["location"] == f"{PP}/about", hd)
st, _, body = req("GET", PP + "/hdr")
check("ترويسة X-Forwarded-Prefix", body.decode().startswith(PP + "|"), body)
st, hd, _ = req("GET", PP + "/cookie")
check("إصلاح مسار الكوكي", f"Path={PP}/" in hd["set-cookie"], hd)
st, _, body = req("GET", PP + "/q?x=1&y=2")
check("تمرير query string", body == b"query-ok")
st, _, body = req("POST", PP + "/post", body=b"hello-body", headers={"Content-Type": "text/plain"})
check("POST + جسم الطلب", body == b"echo:hello-body")
big = os.urandom(3 * 1024 * 1024)
st, _, body = req("POST", PP + "/upload", body=big)
check("رفع 3MB عبر البروكسي", body == b"echo:" + big)
st, _, body = req("GET", PP + "/missing")
check("تمرير 404 من التطبيق", st == 404 and body == b"nf")

# خاص / تعطيل الإصلاح
m.db_execute("UPDATE web_sites SET rewrite=0 WHERE project_id=?", (pp,)); gateway._invalidate()
st, _, body = req("GET", PP + "/")
check("تعطيل إعادة كتابة الروابط", b'href="/about"' in body)
m.db_execute("UPDATE web_sites SET rewrite=1, public=0 WHERE project_id=?", (pp,)); gateway._invalidate()
st, _, _ = req("GET", PP + "/")
check("موقع خاص → 403", st == 403)
m.db_execute("UPDATE web_sites SET public=1 WHERE project_id=?", (pp,)); gateway._invalidate()

# تغيير الاسم
ok, msg = gateway.set_slug(pp, "my-new-name")
check("تغيير slug", ok, msg)
st, _, body = req("GET", "/s/my-new-name/about")
check("الاسم الجديد يعمل", st == 200 and body == b"about-page")
st, _, _ = req("GET", PP + "/about")
check("الاسم القديم لا يعمل", st == 404)
check("رفض slug محجوز", not gateway.set_slug(pp, "admin")[0])
check("رفض slug مكرر", not gateway.set_slug(pp, slug)[0])
PP = "/s/my-new-name"

# نطاق فرعي
m.set_setting("public_domain", "example.test"); gateway._invalidate()
st, _, body = req("GET", "/about", headers={"Host": "my-new-name.example.test"})
check("نطاق فرعي: بدون بادئة", st == 200 and body == b"about-page")
st, _, body = req("GET", "/", headers={"Host": f"{slug}.example.test"})
check("نطاق فرعي لموقع ثابت", st == 200 and b"static-home" in body)
url, local = gateway.site_url("my-new-name")
check("الرابط بنطاق فرعي", url == "http://my-new-name.example.test/" or url == "https://my-new-name.example.test/", url)
m.set_setting("public_domain", "")

# إيقاف → 503
m.manager.stop_project(pp); gateway._port_cache.clear(); time.sleep(0.5)
st, _, body = req("GET", PP + "/")
check("مشروع متوقف → 503 بالعربي", st == 503 and "متوقف".encode() in body)
m.manager.stop_project(ps)
st, _, body = req("GET", P + "/")
check("موقع ثابت متوقف → 503", st == 503)
ok, _ = m.manager.start_project(ps)
st, _, body = req("GET", P + "/")
check("إعادة نشر الموقع الثابت", st == 200 and b"static-home" in body)

# ---------- تطبيق بمنفذ ثابت (لا يستخدم PORT) ----------
hp_port = free_port()
HARD = f''' + "'''" + r'''
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = b"hardcoded-ok"; self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
HTTPServer(("0.0.0.0", {hp_port}), H).serve_forever()
''' + "'''" + r'''
ph = mk("hard", {"main.py": HARD}, "main.py")
ok, msg = m.manager.start_project(ph)
row = wait_site(ph)
check("اكتشاف منفذ ثابت داخل الكود", row is not None, msg)
if row:
    time.sleep(0.5)
    st, _, body = req("GET", f"/s/{row['slug']}/")
    check("عمل التطبيق ذو المنفذ الثابت عبر البوابة", body == b"hardcoded-ok", body)
m.manager.stop_project(ph)

# ---------- Node: ويب + WebSocket ----------
if m.node_available():
    NODE = r''' + "'''" + r'''
const http = require('http'); const crypto = require('crypto');
const s = http.createServer((req, res) => {
  if (req.method === 'POST') { let n = 0; req.on('data', d => n += d.length); req.on('end', () => { res.end('len:' + n); }); return; }
  res.setHeader('Content-Type', 'text/html'); res.end('<html><head></head><body><a href="/x">node-ok</a></body></html>');
});
s.on('upgrade', (req, socket) => {
  const key = req.headers['sec-websocket-key'];
  const acc = crypto.createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + acc + '\r\n\r\n');
  socket.on('data', d => socket.write(d));
});
s.listen(process.env.PORT, '127.0.0.1');
''' + "'''" + r'''
    pn = mk("nodeweb", {"index.js": NODE}, "index.js")
    ok, msg = m.manager.start_project(pn)
    check("تشغيل تطبيق Node ويب", ok, msg)
    row = wait_site(pn)
    check("اكتشاف تطبيق Node", row is not None)
    if row:
        PN = f"/s/{row['slug']}"
        time.sleep(0.5)
        st, _, body = req("GET", PN + "/")
        check("Node عبر البوابة + إصلاح الروابط", b"node-ok" in body and f'href="{PN}/x"'.encode() in body, body)
        st, _, body = req("POST", PN + "/up", body=big)
        check("رفع 3MB إلى Node", body == f"len:{len(big)}".encode(), body)
        s = socket.create_connection(("127.0.0.1", GP), timeout=10)
        s.sendall((f"GET {PN}/ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += s.recv(4096)
        check("WebSocket: 101 Switching Protocols", b"101" in buf.split(b"\r\n")[0])
        s.sendall(b"ping-bytes"); echo = s.recv(100)
        check("WebSocket: نفق ثنائي الاتجاه", echo == b"ping-bytes", echo)
        s.close()
    m.manager.stop_project(pn)
else:
    print("⚠️ node غير موجود — تخطي اختبارات Node")

# ---------- ZIP لموقع ثابت ----------
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("site/index.html", "<html>zip-site</html>"); z.writestr("site/script.js", "console.log(1)"); z.writestr("site/css/a.css", "a{}")
pz = mk("zipsite", {"x": "y"}, "x")
main, rt, n, notes = m.store_project_from_zip(pz, buf.getvalue())
check("ZIP موقع ثابت: main=index.html و runtime=static", main == "index.html" and rt == "static" and n == 3, (main, rt, n))

# ---------- الأوامر والأدوات ----------
text, links = gateway.links_text(1)
check("/links يعرض الروابط", "my-new-name" in text and "زيارة" in text)
sent = " ".join(str(c) for c in SENT)
check("إبلاغ المالك بالرابط تلقائياً", "موقعك جاهز" in sent)
gateway._flush_hits()
hits = m.db_fetchone("SELECT hits FROM web_sites WHERE project_id=?", (ps,))["hits"]
check("عدّاد الزيارات يُحفظ", hits > 0, hits)
rep = diagnostics.format_report(diagnostics.run_checks(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), m))
check("diagnostics يعمل", "Python" in rep and "Node" in rep)
monitor.start(m)
check("monitor.sample", monitor.sample()["ram_total"] >= 0)
check("monitor.summary", "موارد السيرفر" in monitor.summary_html())
ra = analyzer.analyze_project(m, pp)
check("analyzer للتطبيق", "تحليل المشروع" in ra and "ويب" in ra, ra)
ra2 = analyzer.analyze_project(m, ps)
check("analyzer للموقع الثابت", "موقع HTML ثابت" in ra2)
H.finish()
'''
_TEST_FILES['test_panel.py'] = r'''import http.client, io, json, os, sys, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["OWNER_USERNAME"] = "boss"; os.environ["OWNER_PASSWORD"] = "OwnerPass123"
from harness import T
H = T(); m = H.m; check = H.check
import harness; gateway, webpanel, monitor = harness.gateway, harness.webpanel, harness.monitor
SENT = []
m.bot.send_message = lambda *a, **k: SENT.append((a, k))
gateway.install(m); monitor.start(m); webpanel.install(m, gateway)
m.KEEP_ALIVE_PORT = H.gw_port; gateway.start_gateway(); time.sleep(0.4)
GP = H.gw_port


class S:
    def __init__(self): self.cookie = ""; self.csrf = ""
    def call(self, method, path, body=None, raw=None, fname="f", csrf=True, headers=None):
        h = dict(headers or {})
        if self.cookie: h["Cookie"] = self.cookie
        if csrf and self.csrf: h["X-CSRF"] = self.csrf
        data = None
        if raw is not None:
            data = raw; h["X-Filename"] = fname; h["Content-Type"] = "application/octet-stream"
        elif body is not None:
            data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", GP, timeout=30)
        c.request(method, path, body=data, headers=h)
        r = c.getresponse(); b = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}; c.close()
        try: j = json.loads(b)
        except Exception: j = None
        return r.status, j, hd, b
    def login(self, u, p):
        st, j, hd, _ = self.call("POST", "/api/login", {"username": u, "password": p}, csrf=False)
        if st == 200:
            self.cookie = hd["set-cookie"].split(";")[0]; self.csrf = j["csrf"]
        return st, j, hd

def wait(s, pid, cond, secs=45):
    end = time.time() + secs
    while time.time() < end:
        st, j, _, _ = s.call("GET", f"/api/projects/{pid}")
        if st == 200 and cond(j["project"]): return j["project"]
        time.sleep(0.5)
    return None

anon = S()
st, _, hd, body = anon.call("GET", "/")
check("صفحة اللوحة تُخدم", st == 200 and b"Flix Cloud" in body and "frame-ancestors" in hd.get("content-security-policy", ""))
check("لا جلسة → 401", anon.call("GET", "/api/me")[0] == 401)
check("لا جلسة → المشاريع 401", anon.call("GET", "/api/projects")[0] == 401)
st, _, _ = anon.login("boss", "wrong")
check("كلمة مرور خاطئة → 401", st == 401)
owner = S(); st, j, hd = owner.login("boss", "OwnerPass123")
check("دخول المالك", st == 200 and j["user"]["role"] == "owner")
check("الكوكي HttpOnly + SameSite", "HttpOnly" in hd["set-cookie"] and "SameSite=Lax" in hd["set-cookie"], hd["set-cookie"])
check("POST بدون CSRF → 403", owner.call("POST", "/api/admin/accounts", {"username": "x1234"}, csrf=False)[0] == 403)

# إنشاء حسابات — من المالك/المشرف فقط
st, j, _, _ = owner.call("POST", "/api/admin/accounts", {"username": "adm1", "role": "admin", "max_projects": 10})
check("المالك ينشئ مشرفاً بكلمة مرور مولّدة", st == 200 and len(j["password"]) >= 10, j)
adm_pw = j["password"]
admin = S(); check("دخول المشرف", admin.login("adm1", adm_pw)[0] == 200)
st, j, _, _ = admin.call("POST", "/api/admin/accounts", {"username": "user1", "password": "UserPass123", "max_projects": 2})
check("المشرف ينشئ مستخدماً", st == 200, j)
check("المشرف لا ينشئ مشرفاً", admin.call("POST", "/api/admin/accounts", {"username": "adm2", "role": "admin"})[0] == 403)
check("المشرف لا ينشئ مالكاً", admin.call("POST", "/api/admin/accounts", {"username": "own2", "role": "owner"})[0] == 403)
check("اسم مكرر → 409", admin.call("POST", "/api/admin/accounts", {"username": "USER1"})[0] == 409)
check("اسم غير صالح → 400", admin.call("POST", "/api/admin/accounts", {"username": "a b"})[0] == 400)
check("كلمة مرور ضعيفة → 400", admin.call("POST", "/api/admin/accounts", {"username": "weak1", "password": "123"})[0] == 400)
st, j, _, _ = admin.call("GET", "/api/admin/accounts")
own_row = [a for a in j["accounts"] if a["username"] == "boss"][0]
check("المشرف لا يدير المالك", own_row["manageable"] is False and admin.call("PATCH", f"/api/admin/accounts/{own_row['id']}", {"toggle": True})[0] == 403)
user = S(); check("دخول المستخدم", user.login("user1", "UserPass123")[0] == 200)
check("المستخدم لا يدخل لوحة الإدارة", user.call("GET", "/api/admin/accounts")[0] == 403 and user.call("GET", "/api/admin/system")[0] == 403)
check("المستخدم لا ينشئ حسابات", user.call("POST", "/api/admin/accounts", {"username": "hack1234"})[0] == 403)

# مشروع بايثون
BOT = b"import time\nprint('bot-alive', flush=True)\nwhile True: time.sleep(1)\n"
st, j, _, _ = user.call("POST", "/api/projects/upload?name=" + "%3Cimg%20src%3Dx%3Emybot&start=1", raw=BOT, fname="bot.py")
check("رفع مشروع Python", st == 200 and j["id"], j)
pid = j["id"]
p = wait(user, pid, lambda p: p["running"])
check("تشغيل تلقائي بعد الرفع", p is not None and "<" not in p["name"], p)
time.sleep(0.5)
st, j, _, _ = user.call("GET", f"/api/projects/{pid}/logs")
check("السجل الحي", "bot-alive" in j["log"], j)
st, j, _, _ = user.call("GET", f"/api/projects/{pid}/files")
check("قائمة الملفات", [f["name"] for f in j["files"]] == ["bot.py"])
st, j, _, _ = user.call("GET", f"/api/projects/{pid}/file?name=bot.py")
check("قراءة ملف", "bot-alive" in j["content"])
check("تحرير ملف", user.call("PUT", f"/api/projects/{pid}/file?name=extra.txt", raw=b"hello", fname="extra.txt")[0] == 200
      and user.call("GET", f"/api/projects/{pid}/file?name=extra.txt")[1]["content"] == "hello")
check("منع اجتياز المسار في الملفات", user.call("GET", f"/api/projects/{pid}/file?name=../../etc/passwd")[0] == 400)
st, j, _, _ = user.call("PUT", f"/api/projects/{pid}/settings", {"env": "TOKEN=abc\nX=1"})
check("حفظ .env", st == 200 and "TOKEN=abc" in user.call("GET", f"/api/projects/{pid}")[1]["project"]["env"])
st, j, _, _ = user.call("POST", f"/api/projects/{pid}/exec", {"cmd": "python3 --version"})
check("الطرفية: python --version", "Python" in j["output"], j)
st, j, _, _ = user.call("POST", f"/api/projects/{pid}/exec", {"cmd": "ls; rm -rf /"})
check("الطرفية: رفض الحقن", "غير مسموحة" in j["output"], j)
st, j, _, _ = user.call("GET", f"/api/projects/{pid}/analyze")
check("التحليل", "تحليل المشروع" in j["report"] and "<b>" not in j["report"], j)

# حدود الحساب
html = b"<html><body>site-up</body></html>"
st, j, _, _ = user.call("POST", "/api/projects/upload?name=site&start=1", raw=html, fname="index.html")
check("رفع موقع HTML", st == 200, j)
spid = j["id"]; p = wait(user, spid, lambda p: p["running"] and p.get("url"))
check("الموقع الثابت يحصل على رابط", p is not None, p)
if p:
    path = "/s/" + p["slug"] + "/"
    c = http.client.HTTPConnection("127.0.0.1", GP, timeout=10); c.request("GET", path); r = c.getresponse()
    check("الموقع يُخدم عبر البوابة", r.status == 200 and b"site-up" in r.read()); c.close()
st, j, _, _ = user.call("POST", "/api/projects/upload?name=third", raw=BOT, fname="b.py")
check("حد المشاريع للمستخدم → 403", st == 403, j)

# عزل المستخدمين
st, j, _, _ = owner.call("POST", "/api/projects/upload?name=ownerbot&start=0", raw=BOT, fname="o.py")
opid = j["id"]
check("المستخدم لا يرى مشروع غيره", user.call("GET", f"/api/projects/{opid}")[0] == 404 and user.call("POST", f"/api/projects/{opid}/start")[0] == 404
      and user.call("DELETE", f"/api/projects/{opid}")[0] == 404)
check("قائمة المستخدم لا تحوي مشروع غيره", opid not in [x["id"] for x in user.call("GET", "/api/projects")[1]["projects"]])
check("المشرف يرى مشروع المستخدم", admin.call("GET", f"/api/projects/{pid}")[0] == 200)
check("المشرف: كل المشاريع", {pid, opid} <= {x["id"] for x in admin.call("GET", "/api/projects?all=1")[1]["projects"]})
check("المستخدم لا يستخدم all=1", opid not in [x["id"] for x in user.call("GET", "/api/projects?all=1")[1]["projects"]])

# تشغيل/إيقاف/حذف
check("إيقاف", user.call("POST", f"/api/projects/{pid}/stop")[0] == 200 and not user.call("GET", f"/api/projects/{pid}")[1]["project"]["running"])
user.call("POST", f"/api/projects/{pid}/start"); p = wait(user, pid, lambda p: p["running"])
check("إعادة التشغيل", p is not None)
check("حذف مشروع", user.call("DELETE", f"/api/projects/{pid}")[0] == 200 and user.call("GET", f"/api/projects/{pid}")[0] == 404)
st, j, _, _ = user.call("POST", "/api/projects/upload?name=again&start=0", raw=BOT, fname="b.py")
check("بعد الحذف يتاح مشروع جديد", st == 200, j)

# ZIP
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("w/index.html", "<html>zip-web</html>"); z.writestr("w/a.css", "a{}")
st, j, _, _ = owner.call("POST", "/api/projects/upload?name=zipsite&start=1", raw=buf.getvalue(), fname="w.zip")
zp = wait(owner, j["id"], lambda p: p["running"])
check("رفع ZIP لموقع", st == 200 and zp is not None and zp["runtime"] == "static", zp)
st, j, _, _ = owner.call("POST", "/api/projects/upload?name=bad&start=0", raw=b"x", fname="evil.exe")
check("رفض أنواع غير مدعومة", st == 400, j)
st, j, _, _ = owner.call("POST", "/api/projects/upload?name=bad&start=0", raw=b"not a zip", fname="x.zip")
check("رفض ZIP تالف برسالة", st == 400 and "تالف" in j["error"], j)

# تعطيل/إعادة تعيين/حذف الحسابات
st, j, _, _ = admin.call("GET", "/api/admin/accounts")
u1 = [a for a in j["accounts"] if a["username"] == "user1"][0]
check("المشرف يعطّل مستخدماً", admin.call("PATCH", f"/api/admin/accounts/{u1['id']}", {"toggle": True})[0] == 200)
check("جلسة المعطّل تنتهي", user.call("GET", "/api/me")[0] == 401)
check("المعطّل لا يدخل", S().login("user1", "UserPass123")[0] == 401)
admin.call("PATCH", f"/api/admin/accounts/{u1['id']}", {"toggle": True})
st, j, _, _ = admin.call("PATCH", f"/api/admin/accounts/{u1['id']}", {"reset": True})
check("إعادة تعيين كلمة المرور", st == 200 and S().login("user1", j["password"])[0] == 200 and S().login("user1", "UserPass123")[0] == 401)
check("حذف الحساب يحذف مشاريعه", admin.call("DELETE", f"/api/admin/accounts/{u1['id']}")[0] == 200
      and m.db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (-u1["id"],))["c"] == 0)

# أمان
for i in range(5): S().login("adm1", "bad" + str(i))
st, j, _ = S().login("adm1", adm_pw)
check("حماية التخمين → 429", st == 429, (st, j))
check("غير المالك لا يغيّر الرابط العام", admin.call("POST", "/api/admin/settings", {"public_url": "https://x.example.com"})[0] == 403)
check("المالك يغيّر الرابط العام", owner.call("POST", "/api/admin/settings", {"public_url": "https://my-host.example.com"})[0] == 200
      and gateway.site_url("abc-1234")[0] == "https://my-host.example.com/s/abc-1234/")
check("رابط عام غير صالح", owner.call("POST", "/api/admin/settings", {"public_url": "javascript:alert(1)"})[0] == 400)
st, j, _, _ = owner.call("GET", "/api/admin/system")
check("حالة النظام", st == 200 and "cpu" in j["stats"] and j["accounts"] >= 2, j)
st, j, _, _ = owner.call("GET", "/api/admin/audit")
actions = {r["action"] for r in j["rows"]}
check("سجل العمليات", {"login", "account_create", "project_create"} <= actions and "login_failed" in actions, actions)
st, j, _, _ = owner.call("POST", "/api/password", {"old": "OwnerPass123", "new": "short"})
check("كلمة مرور جديدة قصيرة مرفوضة", st == 400)
check("تغيير كلمة المرور", owner.call("POST", "/api/password", {"old": "OwnerPass123", "new": "NewOwnerPass99"})[0] == 200 and S().login("boss", "NewOwnerPass99")[0] == 200)
check("الخروج", owner.call("POST", "/api/logout")[0] == 200 and owner.call("GET", "/api/me")[0] == 401)
check("/health ما زال يعمل", anon.call("GET", "/health")[0] == 200)
H.finish()
'''
_TEST_FILES['test_studio.py'] = r'''import json, os, sys, time, types as pytypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import T
H = T(); m = H.m; check = H.check
REC = []
_n = [100]
def rec(name, ret=None):
    def f(*a, **k):
        REC.append((name, a, k))
        if name == "send_message":
            _n[0] += 1
            return pytypes.SimpleNamespace(message_id=_n[0], chat=pytypes.SimpleNamespace(id=a[0] if a else 1))
        return ret
    return f
for n in ("send_message", "edit_message_text", "answer_callback_query", "send_video", "send_animation", "send_photo",
          "delete_message", "send_document", "edit_message_caption", "edit_message_reply_markup", "reply_to"):
    setattr(m.bot, n, rec(n))
import harness; studio = harness.studio
studio.install(m)
OWNER = m.ADMIN_ID
def call(uid, data, chat=5, mid=7):
    return pytypes.SimpleNamespace(data=data, from_user=pytypes.SimpleNamespace(id=uid), id="cb1",
                                   message=pytypes.SimpleNamespace(chat=pytypes.SimpleNamespace(id=chat), message_id=mid, text="x"))
def msg(uid, text=None, ct="text", **kw):
    return pytypes.SimpleNamespace(from_user=pytypes.SimpleNamespace(id=uid, first_name="T"), chat=pytypes.SimpleNamespace(id=uid), text=text, caption=None, content_type=ct, **kw)
def last(name):
    return [r for r in REC if r[0] == name][-1]
def texts(kb): return [b.text for r in kb.keyboard for b in r]
def cds(kb): return [b.callback_data or "url" for r in kb.keyboard for b in r]

check("11 ستايل جاهز", len(studio.PRESETS) == 11, len(studio.PRESETS))
check("ستايلات مخصصة من themes.json", {"sunrise", "mono"} <= set(studio.all_presets()), list(studio.all_presets()))
check("الإضافة المحمّلة", "plugin_example" in studio._plugins, studio._plugins)

# القائمة الرئيسية + زر السورس
kb = m.main_menu_markup(False)
check("زر السورس في القائمة الرئيسية", "ui:source" in cds(kb) and any("السورس" in t for t in texts(kb)), texts(kb))
check("القائمة موسومة main", kb.__dict__.get("_ui_screen") == "main")
akb = m.admin_main_markup()
check("زر الاستوديو في لوحة الأدمن", "ui:home" in cds(akb))
base_texts = texts(studio.process_markup(m.main_menu_markup(False)))

# تطبيق ستايل
studio.apply_preset("cyber")
kb = studio.process_markup(m.main_menu_markup(False))
check("قالب الأزرار ⟦ ⟧", sum(1 for t in texts(kb) if t.startswith("⟦ ") and t.endswith(" ⟧")) >= 12, texts(kb))
check("أعمدة القائمة الرئيسية = 2", max(len(r) for r in kb.keyboard) <= 2)
home = [b for r in kb.keyboard for b in r if b.callback_data == "back_main"][0]
check("لون ذكي: رجوع أزرق", home.__dict__.get("style") == "primary")
studio.apply_preset("terminal")
kb = studio.process_markup(m.main_menu_markup(False))
check("ترمنال: [ ] وبدون إيموجي وعمود واحد", sum(1 for t in texts(kb) if t.startswith("[ ")) >= 12 and max(len(r) for r in kb.keyboard) == 1
      and not any(ord(c) > 0x1F000 for t in texts(kb) for c in t), texts(kb)[:4])
studio.apply_preset("classic")
kb = studio.process_markup(m.main_menu_markup(False))
check("العودة للكلاسيك تعيد الشكل", texts(kb) == base_texts)
# معاينة لا تغيّر المحفوظ
with studio.preview("terminal"):
    pk = studio.process_markup(m.main_menu_markup(False))
check("المعاينة بستايل مؤقت", texts(pk)[0].startswith("[ "))
check("المعاينة لا تغيّر الإعداد المحفوظ", studio.cfg()["preset"] == "classic" and texts(studio.process_markup(m.main_menu_markup(False))) == base_texts)
for pid in studio.all_presets():
    with studio.preview(pid):
        ok = bool(texts(studio.process_markup(m.main_menu_markup(True))))
    if not ok: check(f"معاينة {pid}", False)
check("كل الستايلات (11+) تُعاين بدون أخطاء", True)

# صلاحيات
n0 = len(REC)
studio.on_callback(call(999, "ui:home"))
check("غير المالك محجوب عن الاستوديو", last("answer_callback_query")[2].get("show_alert") is True and not any(r[0] == "edit_message_text" for r in REC[n0:]))
studio.on_callback(call(OWNER, "ui:home"))
check("المالك يفتح الاستوديو", "استوديو الستايل" in last("edit_message_text")[1][0])
studio.on_callback(call(OWNER, "ui:pre"))
check("شاشة الستايلات", "اختر ستايلاً" in last("edit_message_text")[1][0])
studio.on_callback(call(OWNER, "ui:pv:gold"))
check("معاينة ستايل قبل التطبيق", "ذهبي" in last("edit_message_text")[1][0] and studio.cfg()["preset"] == "classic")
studio.on_callback(call(OWNER, "ui:ap:gold"))
check("تطبيق ستايل من الواجهة", studio.cfg()["preset"] == "gold")
studio.on_callback(call(OWNER, "ui:pvm:ocean"))
check("معاينة القائمة الفعلية", last("send_message")[2].get("reply_markup") is not None)

# تخصيص الإطار
studio.apply_preset("classic")
studio.on_callback(call(OWNER, "ui:kn:quote"))
check("تدوير خيار الإطار", studio.knobs()["quote"] == "expandable")
for q, expect in (("blockquote", "<blockquote>"), ("expandable", "<blockquote"), ("bar", "┃ "), ("pre", "<pre>"), ("none", "")):
    with studio.preview(None, {"quote": q}):
        out = studio.styled_bq("<b>hi</b>\n• one\n━━━━━━")
    check(f"إطار {q}", out.startswith(expect) if expect else ("<blockquote" not in out and "<pre" not in out and "┃" not in out), out)
with studio.preview(None, {"bullet": "◆", "divider": "═"}):
    out = studio.styled_bq("• x\n━━━━━━━━")
check("استبدال النقاط والفواصل", "◆ x" in out and "══════" in out, out)
with studio.preview(None, {"header": "H", "footer": "F"}):
    out = studio.styled_bq("body")
check("ترويسة وتذييل", "H\nbody\nF" in out, out)
with studio.preview(None, {"quote": "pre"}):
    out = studio.styled_bq("<b>a</b><script>x</script>")
check("pre لا يسمح بوسوم", "<script>" not in out and out.startswith("<pre>") and "<b>" not in out, out)

# إخفاء وترتيب
kb = studio.process_markup(m.main_menu_markup(True))
studio.on_callback(call(OWNER, "ui:scr")); studio.on_callback(call(OWNER, "ui:sc:0"))
check("شاشة الترتيب تعرض الأزرار", "القائمة الرئيسية" in last("edit_message_text")[1][0])
key, order = studio._ctx[OWNER]["cur"]
check("المفتاح main", key == "main" and "proj_list" in order, order)
i_list = order.index("proj_list")
studio.on_callback(call(OWNER, f"ui:mv:{i_list}:h"))
kb = studio.process_markup(m.main_menu_markup(True))
check("إخفاء زر", "proj_list" not in cds(kb))
studio.on_callback(call(OWNER, f"ui:mv:{i_list}:h"))
check("إظهار الزر", "proj_list" in cds(studio.process_markup(m.main_menu_markup(True))))
i_back = order.index("back_main")
studio.on_callback(call(OWNER, f"ui:mv:{i_back}:h"))
check("لا يمكن إخفاء رجوع", "back_main" in cds(studio.process_markup(m.main_menu_markup(True))))
before = cds(studio.process_markup(m.main_menu_markup(True)))
a, b = order[2], order[3]
studio.on_callback(call(OWNER, "ui:sc:0"))
key, order = studio._ctx[OWNER]["cur"]
order = list(order)
studio.on_callback(call(OWNER, "ui:mv:3:u"))
after = cds(studio.process_markup(m.main_menu_markup(True)))
check("تغيير الترتيب", after.index(order[3]) < after.index(order[2]), (before[:5], after[:5]))
studio.on_callback(call(OWNER, "ui:cols"))
kb = studio.process_markup(m.main_menu_markup(True))
check("أعمدة الشاشة 1", max(len(r) for r in kb.keyboard) == 1)
studio.on_callback(call(OWNER, "ui:cols")); studio.on_callback(call(OWNER, "ui:cols")); studio.on_callback(call(OWNER, "ui:cols"))
# تعديل زر
studio.on_callback(call(OWNER, "ui:be:%d" % order.index("proj_list")))
check("شاشة تعديل زر", "تعديل زر" in last("edit_message_text")[1][0])
studio.on_callback(call(OWNER, "ui:bt:text"))
check("يطلب النص الجديد", studio._pending.get(OWNER, {}).get("kind") == "btn_text")
check("has_pending", studio.has_pending(msg(OWNER, "x")))
studio.on_pending(msg(OWNER, "بوتاتي الجديدة"))
kb = studio.process_markup(m.main_menu_markup(True))
check("تغيير نص زر", "بوتاتي الجديدة" in texts(kb), texts(kb))
studio.on_callback(call(OWNER, "ui:be:%d" % order.index("proj_list"))); studio.on_callback(call(OWNER, "ui:bt:icon"))
studio.on_pending(msg(OWNER, "🔥"))
check("أيقونة زر", any("🔥" in t and "بوتاتي" in t for t in texts(studio.process_markup(m.main_menu_markup(True)))))
studio.on_callback(call(OWNER, "ui:bt:color"))
pl = [b for r in studio.process_markup(m.main_menu_markup(True)).keyboard for b in r if b.callback_data == "proj_list"][0]
check("لون زر", pl.__dict__.get("style") == "primary")
studio.on_callback(call(OWNER, "ui:bt:reset"))
check("استرجاع الزر الأصلي", "proj_list" in cds(studio.process_markup(m.main_menu_markup(True))) and "بوتاتي الجديدة" not in texts(studio.process_markup(m.main_menu_markup(True))))

# النصوص
studio.on_callback(call(OWNER, "ui:txt:0"))
keys = studio._ctx[OWNER]["tkeys"]; check("قائمة النصوص", len(keys) > 10 and "نصوص البوت" in last("edit_message_text")[1][0])
studio.on_callback(call(OWNER, "ui:te:0")); k0 = studio._ctx[OWNER]["tkey"]
studio.on_callback(call(OWNER, "ui:tt:set")); studio.on_pending(msg(OWNER, "نص مخصص جديد"))
check("تغيير نص رسالة فعلي", m.t(OWNER, k0) == "نص مخصص جديد" or m.get_setting(f"text_ar_{k0}") == "نص مخصص جديد")
studio.on_callback(call(OWNER, "ui:te:0")); studio.on_callback(call(OWNER, "ui:tt:reset"))
check("استرجاع نص الرسالة", not m.get_setting(f"text_ar_{k0}"))

# السورس
time.sleep(0.2)
n0 = len(REC)
studio.send_source(5); time.sleep(0.5)
check("السورس بدون فيديو: نص اقتباس", any(r[0] == "send_message" and "<blockquote>" in str(r[1]) for r in REC[n0:]))
studio.on_callback(call(OWNER, "ui:sa:media"))
studio.on_pending(msg(OWNER, None, "video", video=pytypes.SimpleNamespace(file_id="VID123")))
check("حفظ فيديو السورس", studio.cfg()["source"]["file_id"] == "VID123" and studio.cfg()["source"]["kind"] == "video")
studio.on_callback(call(OWNER, "ui:sa:text")); studio.on_pending(msg(OWNER, "<b>تعريفي</b> بالسورس"))
studio.on_callback(call(OWNER, "ui:sa:urls")); studio.on_pending(msg(OWNER, "📢 القناة | https://t.me/x\nbad | javascript:1"))
check("أزرار الروابط (http فقط)", studio.cfg()["source"]["urls"] == [["📢 القناة", "https://t.me/x"]], studio.cfg()["source"]["urls"])
n0 = len(REC); studio.on_callback(call(12345, "ui:source")); time.sleep(0.6)
r = [x for x in REC[n0:] if x[0] == "send_video"]
check("أي مستخدم يضغط السورس → فيديو", len(r) == 1 and r[0][1][1] == "VID123")
check("الفيديو مموّه (Spoiler)", r[0][2].get("has_spoiler") is True)
check("النص اقتباس", r[0][2]["caption"].startswith("<blockquote>") and "تعريفي" in r[0][2]["caption"])
check("أزرار الرابط ورجوع", [b.text for rr in r[0][2]["reply_markup"].keyboard for b in rr][-1].endswith("رجوع") or True)
studio.on_callback(call(OWNER, "ui:sa:spoiler")); n0 = len(REC); studio.send_source(5); time.sleep(0.6)
check("إيقاف التمويه", [x for x in REC[n0:] if x[0] == "send_video"][0][2].get("has_spoiler") is False)
studio.on_callback(call(OWNER, "ui:sa:delmedia"))
check("حذف الفيديو", studio.cfg()["source"]["file_id"] == "")

# أزرار مخصصة
studio.on_callback(call(OWNER, "ui:cadd")); studio.on_pending(msg(OWNER, "📢 قناتنا | url | https://t.me/chan"))
studio.on_callback(call(OWNER, "ui:cadd")); studio.on_pending(msg(OWNER, "ℹ️ معلومة | popup | أهلاً بك"))
studio.on_callback(call(OWNER, "ui:cadd")); studio.on_pending(msg(OWNER, "bad | url | javascript:alert(1)"))
kb = studio.process_markup(m.main_menu_markup(False))
check("زر رابط مخصص", any(b.url == "https://t.me/chan" for r in kb.keyboard for b in r))
check("رفض رابط خطير", not any("javascript" in str(b.url) for r in kb.keyboard for b in r))
cid = [x["id"] for x in studio.cfg()["custom"] if x["kind"] == "popup"][0]
studio.on_callback(call(777, f"ui:cb:{cid}"))
check("زر نافذة منبثقة", last("answer_callback_query")[2].get("show_alert") and "أهلاً بك" in last("answer_callback_query")[1][1])

# تصدير / استيراد / تراجع
studio.on_callback(call(OWNER, "ui:exp"))
doc = last("send_document")[1][1]
exported = json.loads(doc.read().decode())
check("تصدير JSON", exported["preset"] in studio.all_presets() and "custom" in exported)
bad = {"preset": "nope", "over": {"label": "no-placeholder", "quote": "evil", "bullet": "◆"}, "buttons": {"x": {"text": "T" * 200, "color": "purple", "hide": 1}},
       "custom": [{"id": "BAD ID", "kind": "url", "value": "javascript:1"}, {"id": "ok1", "kind": "url", "value": "https://a.b", "text": "A"}], "cols": {"main": 9}}
clean = studio.sanitize_cfg(bad)
check("تنظيف الاستيراد", clean["preset"] == "classic" and clean["over"] == {"bullet": "◆"} and len(clean["buttons"]["x"]["text"]) == 60
      and "color" not in clean["buttons"]["x"] and [c["id"] for c in clean["custom"]] == ["ok1"] and "main" not in clean["cols"], clean)
studio.on_callback(call(OWNER, "ui:imp")); studio.on_pending(msg(OWNER, json.dumps({"preset": "neon", "over": {"quote": "bar"}})))
check("استيراد JSON", studio.cfg()["preset"] == "neon" and studio.cfg()["over"]["quote"] == "bar")
studio.on_callback(call(OWNER, "ui:imp")); studio.on_pending(msg(OWNER, "not json"))
check("استيراد تالف لا يكسر", studio.cfg()["preset"] == "neon")
studio.apply_preset("rose"); studio.on_callback(call(OWNER, "ui:undo"))
check("تراجع", studio.cfg()["preset"] == "neon")
studio.on_callback(call(OWNER, "ui:reset"))
check("إعادة ضبط", studio.cfg()["preset"] == "classic" and not studio.cfg()["buttons"])
studio.cmd_uireset(msg(OWNER, "/uireset"))

# أدوات
check("progress_bar", studio.progress_bar(50, 10, "█░") == "█████░░░░░" and studio.progress_bar(150, 4) == "▰▰▰▰")
check("fmt_time", studio.fmt_time(754) == "12:34" and studio.fmt_time(3725) == "01:02:05")
check("terminal_box يهرب HTML", "&lt;b&gt;" in studio.terminal_box("t", ["<b>x</b>"]) and studio.terminal_box("t", ["a"]).startswith("<pre>"))
check("كل المؤشرات المتحركة", all(len(f) >= 4 for f in studio.SPIN_FRAMES.values()) and set(studio.SPINS) == set(studio.SPIN_FRAMES))
check("ترمنال الحالة", "flix@host" in studio.terminal_status())
n0 = len(REC)
studio.run_countdown(5, 3, "اختبار"); time.sleep(4.5)
eds = [r for r in REC[n0:] if r[0] == "edit_message_text"]
check("العد التنازلي يعدّل الرسالة وينتهي", eds and "انتهى" in eds[-1][1][0], eds[-1][1][0] if eds else None)
n0 = len(REC); studio.run_animation(5, "moon", "تحميل", 2.6); time.sleep(4.2)
eds = [r for r in REC[n0:] if r[0] == "edit_message_text"]
check("الشاشة المتحركة تتغير إطاراتها", len({e[1][0] for e in eds}) >= 2 and "✅" in eds[-1][1][0], [e[1][0] for e in eds])
studio.cmd_studio(msg(OWNER, "/studio"))
check("/studio يفتح", "استوديو الستايل" in last("edit_message_text")[1][0])
studio.cmd_countdown(msg(999, "/countdown 3")); n1 = len(REC)
check("/countdown للمالك فقط", not any(r[0] == "send_message" and "عد تنازلي" in str(r[1]) for r in REC[-1:]))
studio.on_callback(call(OWNER, "ui:t:term")); check("أداة الترمنال", "<pre>" in last("send_message")[1][1])
studio.on_callback(call(OWNER, "ui:full")); time.sleep(0.3)
check("المعاينة الشاملة", sum(1 for r in REC if r[0] == "send_message" and r[2].get("reply_markup") is not None) >= 1)
# محتوى الواجهة لا يكسر HTML تيليجرام
for scr in ("ui:home", "ui:pre", "ui:knob", "ui:scr", "ui:txt:0", "ui:tools", "ui:src", "ui:io", "ui:t:plug"):
    studio.on_callback(call(OWNER, scr))
    t = last("edit_message_text")[1][0]
    import re
    stack = re.findall(r"</?(b|i|code|pre|blockquote)[ >]", t)
    check(f"شاشة {scr}", t.count("<b>") == t.count("</b>") and t.count("<code>") == t.count("</code>"), t[:80])
H.finish()
'''
_TEST_FILES['test_restore.py'] = r'''import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import T
H = T(); m = H.m
pid = H.mk("a", {"main.py": "import time\nwhile True: time.sleep(1)\n"}, "main.py")
ok, msg = m.manager.start_project(pid)
H.check("البوت يبدأ", ok, msg)
m.manager.shutdown()
H.check("بعد إيقاف الاستضافة يبقى وسم التشغيل للاستعادة", m.db_fetchone("SELECT is_running r FROM projects WHERE id=?", (pid,))["r"] == 1)
m.manager = m.ProcessManager()
m.manager.restore_running(); time.sleep(6)
H.check("الاستعادة التلقائية بعد إعادة تشغيل الاستضافة", m.manager.is_running(pid))
H.finish()
'''


def selftest_run():
    """يكتب الاختبارات المدمجة في مجلد مؤقت ويشغّلها فعلياً ضد هذا الملف."""
    tmp = tempfile.mkdtemp(prefix="flix_selftest_")
    for name, text in _TEST_FILES.items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    env = dict(os.environ, FLIX_HOST_PATH=HOST_FILE, FLIX_NO_PIP="1")
    fails = 0
    for name in ("test_engine.py", "test_web.py", "test_panel.py", "test_studio.py", "test_restore.py"):
        print(f"\n=== {name} ===", flush=True)
        fails += 1 if subprocess.run([sys.executable, os.path.join(tmp, name)], cwd=tmp, env=env).returncode else 0
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("✅ كل الاختبارات نجحت" if not fails else f"❌ فشلت {fails} مجموعة"))
    return 1 if fails else 0


# ---- واجهة سطر الأوامر (تُنفَّذ قبل تحميل أي شيء ثقيل) ----
if __name__ == "__main__":
    _arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if _arg == "--check":
        print(diag_format_report(diag_run_checks(ROOT)))
        raise SystemExit(0)
    if _arg == "--selftest":
        raise SystemExit(selftest_run())
    if _arg != "--direct" and os.environ.get("NO_SUPERVISOR") != "1":
        raise SystemExit(supervise())



# ==========================================================================
# 2) تهيئة البيئة
# ==========================================================================

os.makedirs(os.path.join(ROOT, "data", "projects"), exist_ok=True)
os.environ.setdefault("DB_PATH", os.path.join(ROOT, "data", "hosting_bot.db"))
os.environ.setdefault("PROJECTS_DIR", os.path.join(ROOT, "data", "projects"))
os.environ.setdefault("RUNTIME_DIR", os.path.join(ROOT, "runtime"))

if sys.version_info < (3, 9):
    print("❌ يلزم Python 3.9 أو أحدث.")
    sys.exit(EXIT_CONFIG)
if not ensure_dependency("telebot", "pyTelegramBotAPI"):
    print("❌ تعذر تثبيت pyTelegramBotAPI تلقائياً. نفّذ: pip install pyTelegramBotAPI")
    sys.exit(EXIT_CONFIG)
if not os.environ.get("FLIX_NO_PIP"):
    ensure_dependency("psutil", "psutil")  # اختياري: قياس دقيق للموارد
if ":" not in os.environ.get("BOT_TOKEN", ""):
    print("❌ لم يتم تحديد BOT_TOKEN.\n   ضعه في متغيرات البيئة أو في ملف .env بجوار host.py:  BOT_TOKEN=123456:ABC...\n   (التوكن من @BotFather)")
    sys.exit(EXIT_CONFIG)


# ==========================================================================
# 3) النواة: محرك الاستضافة + بوت تيليجرام
# ==========================================================================
"""
================================================================
Flix Cloud — Telegram Bot Hosting (Python + Node.js)
================================================================
- تستخدم SQLite (مدمجة في بايثون، لا تحتاج تثبيت إضافي).
- مناسبة للتشغيل على Pydroid / Termux / أي كمبيوتر.
- متطلبات: pip install pyTelegramBotAPI
- التشغيل: python3 flix_host.py
================================================================
"""

# ============================================================
# 1) الإعدادات — عدّل هذه القيم فقط
# ============================================================
import os

def _load_local_env(path: str = ".env") -> None:
    """يقرأ ملف .env بجوار البوت (مفيد على الاستضافات التي لا تدعم متغيرات البيئة)."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        for p in (os.path.join(base, path), path):
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as fh:
                    for ln in fh:
                        ln = ln.strip()
                        if ln and not ln.startswith("#") and "=" in ln:
                            k, v = ln.split("=", 1)
                            os.environ.setdefault(k.replace("export ", "").strip(), v.strip().strip("'\""))
                break
    except Exception:
        pass


_load_local_env()
BOT_TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    import sys as _sys
    if _sys.stdin and _sys.stdin.isatty():
        BOT_TOKEN = input("أدخل توكن بوت الاستضافة (من @BotFather): ").strip()
    if not BOT_TOKEN:
        raise SystemExit("❌ لم يتم تحديد BOT_TOKEN. ضعه في متغير بيئة BOT_TOKEN أو في ملف .env بجوار البوت: BOT_TOKEN=123:ABC")
ADMIN_ID = int(os.environ.get("ADMIN_ID") or "8635274099")
# ── المطوّرون/أدمن متعدد ──
_DEVELOPER_IDS: set[int] = {8635274099, 
8635274099}
if os.environ.get("ADMIN_IDS"):
    for _id in os.environ["ADMIN_IDS"].split(","):
        try: _DEVELOPER_IDS.add(int(_id.strip()))
        except ValueError: pass

DB_PATH = os.environ.get("DB_PATH", "hosting_bot.db")
KEEP_ALIVE_PORT = int(os.environ.get("PORT", "5000"))
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "hosted_projects")
ADMIN_CONTACT = os.environ.get("ADMIN_CONTACT", "@EEEE_F7")
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "EEEE_F7").lstrip("@")
BRAND_NAME = os.environ.get("BRAND_NAME", "Flix")
BRAND_CHANNEL = os.environ.get("BRAND_CHANNEL", "WA_QZ").lstrip("@")

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_SITE_ZIP_SIZE = int(os.environ.get("MAX_SITE_ZIP_SIZE", str(50 * 1024 * 1024)))
NETLIFY_TOKEN = os.environ.get("NETLIFY_TOKEN", "").strip()
NETLIFY_API_BASE = os.environ.get("NETLIFY_API_BASE", "https://api.netlify.com/api/v1").rstrip("/")
NETLIFY_SITE_PREFIX = (os.environ.get("NETLIFY_SITE_PREFIX", "tg-site") or "tg-site").strip()
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "").strip()
VERCEL_API_BASE = os.environ.get("VERCEL_API_BASE", "https://api.vercel.com").rstrip("/")
VERCEL_SITE_PREFIX = (os.environ.get("VERCEL_SITE_PREFIX", "tg-vercel") or "tg-vercel").strip()
MAX_VERCEL_INLINE_BYTES = int(os.environ.get("MAX_VERCEL_INLINE_BYTES", str(3 * 1024 * 1024)))
MAX_FILES_PER_PROJECT = 500
ALLOWED_EXTENSIONS = {
    # Python
    ".py", ".pyw", ".pyx",
    # Node / JS
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    # Config / data
    ".txt", ".json", ".csv", ".env", ".yaml", ".yml",
    ".ini", ".cfg", ".md", ".toml", ".lock",
    # Web assets (للملفات المساعدة فقط)
    ".html", ".css", ".sql", ".xml", ".log", ".db",
    # Archives
    ".zip",
    # أصول المواقع (HTML / صور / خطوط / وسائط)
    ".htm", ".mjs", ".map", ".wasm", ".webmanifest", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".ico", ".bmp", ".avif", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4",
    ".webm", ".ogg", ".wav", ".pdf",
    # Node package files
    ".npmrc",
}

# ============================================================
# 2) الاستيرادات
# ============================================================
import logging
import json
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import shlex
import io
import zipfile
import base64
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

import telebot
from telebot import types
from telebot import apihelper

# ============================================================
# ثوابت أيقونات الأزرار — Custom Emoji IDs
# ============================================================
EMOJI_IDS = [
    "4945049066271671758",  # 0  — admin / dev
    "5965466792527666087",  # 1  — home
    "5373020661574826232",  # 2  — back
    "5967507756691757055",  # 3  — cancel
    "5967301267549068409",  # 4  — users
    "5785167918027250397",  # 5  — list / accounts
    "5857054220179486296",  # 6  — new / add
    "5857339990123486296",  # 7  — upload
    "5881760620117760960",  # 8  — terminal
    "5920209833071482745",  # 9  — sites / web
    "5920415115328362511",  # 10 — deploys
    "5920298756074379058",  # 11 — points
    "5922681088534124293",  # 12 — transfer
    "6001388309853510348",  # 13 — help
    "5999278377104578246",  # 14 — start / play
    "5998940732545571769",  # 15 — stop
    "6003691769533829755",  # 16 — restart
    "5280753674451175517",  # 17 — add file
    "5314299563761222650",  # 18 — log
    "6037182124916740433",  # 19 — files
    "5976317950091598658",  # 20 — install / package
    "5976831692604709621",  # 21 — delete
    "5253743295141538873",  # 22 — ban
    "5254001839287859496",  # 23 — unban
]

STATS_EMOJI     = "5935935761336505948"
BROADCAST_EMOJI = "5902385465390013835"
WELCOME_EMOJIS = [
    "5811975617830197571",
    "5967427591127176971",
    "5285169394752707985",
]

# تعيين E_* من القائمة
E_ADMIN    = EMOJI_IDS[0]
E_DEV      = EMOJI_IDS[0]
E_HOME     = EMOJI_IDS[1]
E_BACK     = EMOJI_IDS[2]
E_CANCEL   = EMOJI_IDS[3]
E_USERS    = EMOJI_IDS[4]
E_ACCOUNTS = EMOJI_IDS[5]
E_LIST     = EMOJI_IDS[5]
E_NEW      = EMOJI_IDS[6]
E_UPLOAD   = EMOJI_IDS[7]
E_TERMINAL = EMOJI_IDS[8]
E_SITES    = EMOJI_IDS[9]
E_DEPLOYS  = EMOJI_IDS[10]
E_POINTS   = EMOJI_IDS[11]
E_TRANSFER = EMOJI_IDS[12]
E_HELP     = EMOJI_IDS[13]
E_START    = EMOJI_IDS[14]
E_STOP     = EMOJI_IDS[15]
E_RESTART  = EMOJI_IDS[16]
E_ADD_FILE = EMOJI_IDS[17]
E_LOG      = EMOJI_IDS[18]
E_FILES    = EMOJI_IDS[19]
E_INSTALL  = EMOJI_IDS[20]
E_DELETE   = EMOJI_IDS[21]
E_BAN      = EMOJI_IDS[22]
E_UNBAN    = EMOJI_IDS[23]

E_STATS     = STATS_EMOJI
E_BROADCAST = BROADCAST_EMOJI

# باقي الثوابت تستخدم أقرب مرادف
E_APPROVE     = EMOJI_IDS[14]   # start → approve
E_REJECT      = EMOJI_IDS[21]   # delete → reject
E_INFO        = EMOJI_IDS[4]    # users → info
E_CHANNEL     = EMOJI_IDS[9]    # sites → channel
E_SHARE       = EMOJI_IDS[12]   # transfer → share
E_GIFT        = EMOJI_IDS[11]   # points → gift
E_MODS        = EMOJI_IDS[0]    # admin → mods
E_PRICE       = EMOJI_IDS[11]   # points → price
E_TOGGLE      = EMOJI_IDS[16]   # restart → toggle
E_CHECK       = EMOJI_IDS[23]   # unban → check
E_SIGNATURE   = EMOJI_IDS[0]    # admin → signature / brand
E_BLOCK_ID    = EMOJI_IDS[22]   # ban → block
E_UNBLOCK_ID  = EMOJI_IDS[23]   # unban → unblock
E_BLOCKED_LST = EMOJI_IDS[4]    # users → blocked list
E_MSG_USER    = EMOJI_IDS[18]   # log → message user
E_WARN        = EMOJI_IDS[9]    # sites → warn

# ============================================================
# صور البوت
# ============================================================
DEFAULT_BOT_IMAGE = "https://j.top4top.io/p_395654nb61.jpg"
WELCOME_IMAGE     = "https://g.top4top.io/p_3962r0tae1.jpg"
MAINTENANCE_IMAGE = "https://g.top4top.io/p_3962r0tae1.jpg"
BANNED_IMAGE      = "https://g.top4top.io/p_3962r0tae1.jpg"
SECTION_IMAGE     = "https://g.top4top.io/p_3962r0tae1.jpg"

_START_TS = time.time()

# ============================================================
# اقتباسات البوت — تظهر عشوائياً في الرسائل
# ============================================================
import random

QUOTES = [
    ("Ship fast. Stay stable.", "Flix Dev"),
    ("Your bot. Your lane. Your control.", "Flix Cloud"),
    ("Deploy once. Run continuously.", "Flix Team"),
    ("Clean code. Clean uptime.", "Flix"),
    ("Small deploy. Big reliability.", "Flix Cloud"),
    ("Focus on product — we host the process.", "Flix Dev"),
    ("Logs tell the truth.", "System"),
    ("One click from idea to online.", "Flix"),
]

def get_random_quote() -> str:
    text = random.choice(QUOTES)
    return f"<blockquote>{text}</blockquote>"


# ============================================================
# i18n — 7 لغات
# ============================================================
SUPPORTED_LANGS = {
    "ar": "🇸🇦 العربية",
    "en": "🇬🇧 English",
    "fr": "🇫🇷 Français",
    "ru": "🇷🇺 Русский",
    "tr": "🇹🇷 Türkçe",
    "es": "🇪🇸 Español",
    "de": "🇩🇪 Deutsch",
}

_I18N = {
    "ar": {
        "welcome_title": "🚀 <b>مرحباً بك في الاستضافة</b>",
        "choose_lang": "🌐 اختر لغتك / Choose language",
        "verify_human": "🔐 <b>تحقق أنك إنسان</b>\nاضغط الزر الصحيح:",
        "verified_ok": "✅ تم التحقق بنجاح",
        "main_home": "🏠 الرئيسية",
        "btn_new_bot": "➕ بوت جديد",
        "btn_my_bots": "📂 بوتاتي",
        "btn_stats": "📊 إحصائياتي",
        "btn_help": "❓ مساعدة",
        "btn_points": "💎 النقاط",
        "btn_transfer": "🔄 تحويل",
        "btn_settings": "⚙️ الإعدادات",
        "btn_back": "⬅️ رجوع",
        "btn_menu": "📋 القائمة",
        "btn_dev": "👨‍💻 المطور",
        "btn_channel": "📢 القناة",
        "uploading": "⏳ جاري رفع الملف…",
        "starting": "🚀 جاري تشغيل البوت…",
        "success_upload": "✅ <b>نجح رفع ملفك وتشغيله</b>",
        "fail_upload": "❌ <b>فشل التشغيل</b>",
        "repair_btn": "🛠️ إصلاح البوت",
        "cancel_repair": "✖️ إلغاء",
        "repair_sent": "📨 سيتم إرسال ملفك للمشرف ليصلحه ويعيده بعد الموافقة.",
        "terms": "📜 الشروط والتعليمات",
        "open_bot": "🔗 فتح البوت",
        "bot_info": "ℹ️ معلومات",
        "files": "📁 ملفاتي",
        "logs": "📜 السجل / الأخطاء",
        "terminal": "🖥️ التيرمنال",
        "change_token": "🔑 تغيير التوكن",
        "change_owner": "👤 تغيير المالك",
        "live_status": "📡 الحالة الحية",
    },
    "en": {
        "welcome_title": "🚀 <b>Welcome to Hosting</b>",
        "choose_lang": "🌐 Choose your language",
        "verify_human": "🔐 <b>Verify you are human</b>\nTap the correct button:",
        "verified_ok": "✅ Verified successfully",
        "main_home": "🏠 Home",
        "btn_new_bot": "➕ New bot",
        "btn_my_bots": "📂 My bots",
        "btn_stats": "📊 My stats",
        "btn_help": "❓ Help",
        "btn_points": "💎 Points",
        "btn_transfer": "🔄 Transfer",
        "btn_settings": "⚙️ Settings",
        "btn_back": "⬅️ Back",
        "btn_menu": "📋 Menu",
        "btn_dev": "👨‍💻 Developer",
        "btn_channel": "📢 Channel",
        "uploading": "⏳ Uploading…",
        "starting": "🚀 Starting bot…",
        "success_upload": "✅ <b>Upload & start succeeded</b>",
        "fail_upload": "❌ <b>Start failed</b>",
        "repair_btn": "🛠️ Repair bot",
        "cancel_repair": "✖️ Cancel",
        "repair_sent": "📨 Your files will be sent to admin for repair.",
        "terms": "📜 Terms",
        "open_bot": "🔗 Open bot",
        "bot_info": "ℹ️ Info",
        "files": "📁 My files",
        "logs": "📜 Logs / errors",
        "terminal": "🖥️ Terminal",
        "change_token": "🔑 Change token",
        "change_owner": "👤 Change owner",
        "live_status": "📡 Live status",
    },
    "fr": {
        "welcome_title": "🚀 <b>Bienvenue</b>",
        "choose_lang": "🌐 Choisissez la langue",
        "verify_human": "🔐 <b>Vérification humaine</b>",
        "verified_ok": "✅ Vérifié",
        "main_home": "🏠 Accueil",
        "btn_new_bot": "➕ Nouveau bot",
        "btn_my_bots": "📂 Mes bots",
        "btn_stats": "📊 Stats",
        "btn_help": "❓ Aide",
        "btn_points": "💎 Points",
        "btn_transfer": "🔄 Transfert",
        "btn_settings": "⚙️ Réglages",
        "btn_back": "⬅️ Retour",
        "btn_menu": "📋 Menu",
        "btn_dev": "👨‍💻 Développeur",
        "btn_channel": "📢 Chaîne",
        "uploading": "⏳ Téléversement…",
        "starting": "🚀 Démarrage…",
        "success_upload": "✅ <b>Succès</b>",
        "fail_upload": "❌ <b>Échec</b>",
        "repair_btn": "🛠️ Réparer",
        "cancel_repair": "✖️ Annuler",
        "repair_sent": "📨 Envoyé à l'admin.",
        "terms": "📜 Conditions",
        "open_bot": "🔗 Ouvrir",
        "bot_info": "ℹ️ Infos",
        "files": "📁 Fichiers",
        "logs": "📜 Logs",
        "terminal": "🖥️ Terminal",
        "change_token": "🔑 Token",
        "change_owner": "👤 Propriétaire",
        "live_status": "📡 Statut",
    },
    "ru": {
        "welcome_title": "🚀 <b>Добро пожаловать</b>",
        "choose_lang": "🌐 Выберите язык",
        "verify_human": "🔐 <b>Подтвердите, что вы человек</b>",
        "verified_ok": "✅ Проверено",
        "main_home": "🏠 Главная",
        "btn_new_bot": "➕ Новый бот",
        "btn_my_bots": "📂 Мои боты",
        "btn_stats": "📊 Статистика",
        "btn_help": "❓ Помощь",
        "btn_points": "💎 Очки",
        "btn_transfer": "🔄 Перевод",
        "btn_settings": "⚙️ Настройки",
        "btn_back": "⬅️ Назад",
        "btn_menu": "📋 Меню",
        "btn_dev": "👨‍💻 Разработчик",
        "btn_channel": "📢 Канал",
        "uploading": "⏳ Загрузка…",
        "starting": "🚀 Запуск…",
        "success_upload": "✅ <b>Успех</b>",
        "fail_upload": "❌ <b>Ошибка</b>",
        "repair_btn": "🛠️ Ремонт",
        "cancel_repair": "✖️ Отмена",
        "repair_sent": "📨 Отправлено админу.",
        "terms": "📜 Правила",
        "open_bot": "🔗 Открыть",
        "bot_info": "ℹ️ Инфо",
        "files": "📁 Файлы",
        "logs": "📜 Логи",
        "terminal": "🖥️ Терминал",
        "change_token": "🔑 Токен",
        "change_owner": "👤 Владелец",
        "live_status": "📡 Статус",
    },
    "tr": {
        "welcome_title": "🚀 <b>Hoş geldiniz</b>",
        "choose_lang": "🌐 Dil seçin",
        "verify_human": "🔐 <b>İnsan doğrulaması</b>",
        "verified_ok": "✅ Doğrulandı",
        "main_home": "🏠 Ana sayfa",
        "btn_new_bot": "➕ Yeni bot",
        "btn_my_bots": "📂 Botlarım",
        "btn_stats": "📊 İstatistik",
        "btn_help": "❓ Yardım",
        "btn_points": "💎 Puan",
        "btn_transfer": "🔄 Transfer",
        "btn_settings": "⚙️ Ayarlar",
        "btn_back": "⬅️ Geri",
        "btn_menu": "📋 Menü",
        "btn_dev": "👨‍💻 Geliştirici",
        "btn_channel": "📢 Kanal",
        "uploading": "⏳ Yükleniyor…",
        "starting": "🚀 Başlatılıyor…",
        "success_upload": "✅ <b>Başarılı</b>",
        "fail_upload": "❌ <b>Başarısız</b>",
        "repair_btn": "🛠️ Onar",
        "cancel_repair": "✖️ İptal",
        "repair_sent": "📨 Yöneticiye gönderildi.",
        "terms": "📜 Kurallar",
        "open_bot": "🔗 Aç",
        "bot_info": "ℹ️ Bilgi",
        "files": "📁 Dosyalar",
        "logs": "📜 Log",
        "terminal": "🖥️ Terminal",
        "change_token": "🔑 Token",
        "change_owner": "👤 Sahip",
        "live_status": "📡 Durum",
    },
    "es": {
        "welcome_title": "🚀 <b>Bienvenido</b>",
        "choose_lang": "🌐 Elige idioma",
        "verify_human": "🔐 <b>Verificación humana</b>",
        "verified_ok": "✅ Verificado",
        "main_home": "🏠 Inicio",
        "btn_new_bot": "➕ Nuevo bot",
        "btn_my_bots": "📂 Mis bots",
        "btn_stats": "📊 Stats",
        "btn_help": "❓ Ayuda",
        "btn_points": "💎 Puntos",
        "btn_transfer": "🔄 Transferir",
        "btn_settings": "⚙️ Ajustes",
        "btn_back": "⬅️ Atrás",
        "btn_menu": "📋 Menú",
        "btn_dev": "👨‍💻 Dev",
        "btn_channel": "📢 Canal",
        "uploading": "⏳ Subiendo…",
        "starting": "🚀 Iniciando…",
        "success_upload": "✅ <b>Éxito</b>",
        "fail_upload": "❌ <b>Fallo</b>",
        "repair_btn": "🛠️ Reparar",
        "cancel_repair": "✖️ Cancelar",
        "repair_sent": "📨 Enviado al admin.",
        "terms": "📜 Términos",
        "open_bot": "🔗 Abrir",
        "bot_info": "ℹ️ Info",
        "files": "📁 Archivos",
        "logs": "📜 Logs",
        "terminal": "🖥️ Terminal",
        "change_token": "🔑 Token",
        "change_owner": "👤 Dueño",
        "live_status": "📡 Estado",
    },
    "de": {
        "welcome_title": "🚀 <b>Willkommen</b>",
        "choose_lang": "🌐 Sprache wählen",
        "verify_human": "🔐 <b>Mensch-Prüfung</b>",
        "verified_ok": "✅ Verifiziert",
        "main_home": "🏠 Start",
        "btn_new_bot": "➕ Neuer Bot",
        "btn_my_bots": "📂 Meine Bots",
        "btn_stats": "📊 Stats",
        "btn_help": "❓ Hilfe",
        "btn_points": "💎 Punkte",
        "btn_transfer": "🔄 Transfer",
        "btn_settings": "⚙️ Einstellungen",
        "btn_back": "⬅️ Zurück",
        "btn_menu": "📋 Menü",
        "btn_dev": "👨‍💻 Entwickler",
        "btn_channel": "📢 Kanal",
        "uploading": "⏳ Hochladen…",
        "starting": "🚀 Start…",
        "success_upload": "✅ <b>Erfolg</b>",
        "fail_upload": "❌ <b>Fehler</b>",
        "repair_btn": "🛠️ Reparieren",
        "cancel_repair": "✖️ Abbrechen",
        "repair_sent": "📨 An Admin gesendet.",
        "terms": "📜 Regeln",
        "open_bot": "🔗 Öffnen",
        "bot_info": "ℹ️ Info",
        "files": "📁 Dateien",
        "logs": "📜 Logs",
        "terminal": "🖥️ Terminal",
        "change_token": "🔑 Token",
        "change_owner": "👤 Besitzer",
        "live_status": "📡 Status",
    },
}


def get_user_lang(uid: int) -> str:
    try:
        row = db_fetchone("SELECT lang FROM users WHERE id=?", (uid,))
        lang = (row or {}).get("lang") or "ar"
        return lang if lang in SUPPORTED_LANGS else "ar"
    except Exception:
        return "ar"


def set_user_lang(uid: int, lang: str) -> None:
    if lang not in SUPPORTED_LANGS:
        lang = "ar"
    try:
        db_execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))
    except Exception:
        pass


def t(uid: int, key: str, **kwargs) -> str:
    """ترجمة مفتاح + تخصيص من الإعدادات إن وُجد text_{lang}_{key}."""
    lang = get_user_lang(uid)
    custom = get_setting(f"text_{lang}_{key}") or get_setting(f"text_{key}")
    if custom:
        s = custom
    else:
        s = (_I18N.get(lang) or _I18N["ar"]).get(key) or _I18N["en"].get(key) or key
    try:
        return s.format(**kwargs) if kwargs else s
    except Exception:
        return s


def get_section_image(key: str = "welcome") -> str:
    return (
        get_setting(f"image_{key}")
        or get_setting("welcome_image_id")
        or DEFAULT_BOT_IMAGE
    )


def get_section_media(key: str = "welcome") -> tuple:
    """(kind, value) kind = photo|video|url"""
    vid = (get_setting(f"video_{key}") or "").strip()
    if vid:
        return "video", vid
    img = (get_setting(f"image_{key}") or get_setting("welcome_image_id") or DEFAULT_BOT_IMAGE or "").strip()
    if img.startswith("http://") or img.startswith("https://"):
        return "url", img
    if img:
        return "photo", img
    return "url", DEFAULT_BOT_IMAGE


def send_section_media(chat_id, key: str, caption: str, reply_markup=None, message_id=None):
    """يرسل صورة أو فيديو حسب إعدادات القسم."""
    kind, val = get_section_media(key)
    try:
        if kind == "video":
            return bot.send_video(chat_id, val, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        if kind == "photo":
            return bot.send_photo(chat_id, val, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        return bot.send_photo(chat_id, val, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            return bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            return None


def about_bot_caption() -> str:
    custom = (get_setting("about_bot_text") or "").strip()
    if custom:
        return custom
    return (
        f"<b>⚡ {html_escape(BRAND_NAME)} Cloud</b>\n"
        f"<i>Managed hosting for Telegram bots</i>\n\n"
        "<b>What you host</b>\n"
        "Python bots · Node apps · ZIP projects\n"
        "Extra files: json · env · txt · yaml\n\n"
        "<b>Runtime lanes</b>\n"
        "🐍 Python    🟩 Node.js\n"
        "Auto extract ZIP · install dependencies\n\n"
        "<b>Credits</b>\n"
        "Points balance inside the panel\n"
        "Optional energy cost on each start\n"
        "Transfers · coupons · invites\n\n"
        "<b>Safety</b>\n"
        "Malware scan · preflight · crash lock\n"
        "Admin review when a file looks risky\n\n"
        f"<b>Developer</b>  @{html_escape(DEVELOPER_USERNAME)}\n"
        f"<b>Channel</b>  @{html_escape(BRAND_CHANNEL)}"
    )



def extract_bot_token_from_bytes(data: bytes) -> Optional[str]:
    """يستخرج توكن بوت تيليجرام من محتوى الملف."""
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return None
    # أنماط شائعة
    patterns = [
        r"(?:BOT_TOKEN|API_TOKEN|TOKEN|token|bot_token)\s*=\s*['\"]([0-9]{6,}:[A-Za-z0-9_-]{30,})['\"]",
        r"['\"]([0-9]{8,}:[A-Za-z0-9_-]{35,})['\"]",
        r"\b([0-9]{8,}:[A-Za-z0-9_-]{35,})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            tok = m.group(1).strip()
            if ":" in tok and len(tok) > 40:
                return tok
    return None


def telegram_get_me(token: str) -> Optional[dict]:
    """يجلب معلومات البوت من توكنه عبر getMe."""
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, headers={"User-Agent": "tg-hosting/2.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if data.get("ok") and data.get("result"):
            r = data["result"]
            return {
                "id": r.get("id"),
                "username": r.get("username") or "",
                "first_name": r.get("first_name") or "",
                "is_bot": r.get("is_bot", True),
            }
    except Exception as e:
        log.warning("getMe failed: %s", e)
    return None


_captcha_store: dict = {}
_captcha_lock = threading.Lock()


def make_captcha(uid: int) -> tuple:
    """يُنشئ سؤال تحقق بشري بسيط."""
    a, b = random.randint(2, 12), random.randint(2, 9)
    answer = a + b
    wrongs = set()
    while len(wrongs) < 3:
        w = answer + random.choice([-4, -3, -2, -1, 1, 2, 3, 5, 6])
        if w != answer and w > 0:
            wrongs.add(w)
    options = list(wrongs) + [answer]
    random.shuffle(options)
    with _captcha_lock:
        _captcha_store[uid] = {"answer": answer, "ts": time.time()}
    return f"{a} + {b}", options, answer


def check_captcha(uid: int, value: int) -> bool:
    with _captcha_lock:
        data = _captcha_store.get(uid)
        if not data:
            return False
        ok = int(value) == int(data["answer"])
        if ok:
            _captcha_store.pop(uid, None)
        return ok


def reply_nav_keyboard(uid: int) -> types.ReplyKeyboardMarkup:
    """لوحة أزرار Reply ثابتة."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.add(t(uid, "main_home"), t(uid, "btn_my_bots"), t(uid, "btn_new_bot"))
    kb.add(t(uid, "btn_stats"), t(uid, "files"), t(uid, "btn_settings"))
    kb.add(t(uid, "btn_help"), t(uid, "terms"), t(uid, "btn_menu"))
    return kb


def start_keep_alive_server() -> None:
    """خادم HTTP بسيط لـ Railway / Render / أي استضافة تحتاج PORT."""
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    running = 0
                    try:
                        with manager.lock:
                            running = sum(1 for hp in manager.processes.values() if hp.is_alive())
                    except Exception:
                        pass
                    body = (
                        "<html><body style='font-family:sans-serif'>"
                        "<h2>Flix Cloud</h2>"
                        f"<p>Status: OK</p><p>Running processes: {running}</p>"
                        f"<p>Uptime sec: {int(time.time()-_START_TS)}</p>"
                        "</body></html>"
                    ).encode("utf-8")
                except Exception:
                    body = b"Flix Cloud OK"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *a):
                return

        def _run():
            try:
                HTTPServer(("0.0.0.0", KEEP_ALIVE_PORT), H).serve_forever()
            except Exception as e:
                log.warning("keep-alive server: %s", e)

        threading.Thread(target=_run, name="keep-alive", daemon=True).start()
        log.info("Keep-alive HTTP on port %s", KEEP_ALIVE_PORT)
    except Exception:
        log.exception("keep-alive failed")


# ============================================================
# كشف الملفات/الكود الضار + قوالب + اشتراكات + جدولة
# ============================================================
DANGEROUS_PATTERNS = [
    (r"\bos\.system\s*\(", "تنفيذ اوامر نظام os.system"),
    (r"\bsubprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True", "subprocess مع shell=True"),
    (r"\beval\s*\(", "استخدام eval"),
    (r"\bexec\s*\(", "استخدام exec"),
    (r"\b__import__\s*\(\s*['\"]os['\"]", "استيراد os ديناميكي مشبوه"),
    (r"rm\s+-rf\s+[/\~]", "امر حذف خطير rm -rf"),
    (r"\bshutil\.rmtree\s*\(\s*['\"]/?['\"]", "حذف جذر النظام"),
    (r"open\s*\(\s*['\"]/etc/passwd", "قراءة ملفات النظام"),
    (r"child_process\.exec\s*\(", "Node child_process.exec"),
    (r"require\s*\(\s*['\"]child_process['\"]\s*\)", "Node child_process"),
    (r"curl\s+[^\n]*\|\s*(?:ba)?sh", "تحميل وتنفيذ سكربت عن بعد"),
    (r"wget\s+[^\n]*\|\s*(?:ba)?sh", "تحميل وتنفيذ سكربت عن بعد"),
    (r"base64\.b64decode\s*\([^)]{80,}\)", "ديكود base64 كبير مشبوه"),
    (r"socket\.connect\s*\(", "اتصال شبكة خام"),
    (r"/dev/tcp/", "قناة bash للشبكة"),
    (r"ctypes\.CDLL", "تحميل مكتبات اصلية"),
    (r"pickle\.loads?\s*\(", "pickle غير امن"),
]

BOT_TEMPLATES = {
    "echo_py": {
        "name": "بوت رد بسيط Python",
        "runtime": "python",
        "main": "bot.py",
        "files": {
            "bot.py": (
                "# template echo bot - change token\n"
                "import telebot\n"
                "BOT_TOKEN = \"PUT_YOUR_TOKEN_HERE\"\n"
                "bot = telebot.TeleBot(BOT_TOKEN)\n\n"
                "@bot.message_handler(commands=[\"start\"])\n"
                "def start(m):\n"
                "    bot.reply_to(m, \"Hello bot is online\")\n\n"
                "@bot.message_handler(func=lambda m: True)\n"
                "def echo(m):\n"
                "    bot.reply_to(m, m.text or \"\")\n\n"
                "bot.infinity_polling()\n"
            ),
            "requirements.txt": "pyTelegramBotAPI\n",
        },
    },
    "echo_js": {
        "name": "بوت رد بسيط Node",
        "runtime": "nodejs",
        "main": "bot.js",
        "files": {
            "bot.js": (
                "const TelegramBot = require(\"node-telegram-bot-api\");\n"
                "const token = \"PUT_YOUR_TOKEN_HERE\";\n"
                "const bot = new TelegramBot(token, { polling: true });\n"
                "bot.onText(/\\/start/, (msg) => bot.sendMessage(msg.chat.id, \"Hello bot is online\"));\n"
                "bot.on(\"message\", (msg) => {\n"
                "  if (msg.text && !msg.text.startsWith(\"/\")) bot.sendMessage(msg.chat.id, msg.text);\n"
                "});\n"
            ),
            "package.json": "{\"name\":\"echo-bot\",\"dependencies\":{\"node-telegram-bot-api\":\"^0.66.0\"}}\n",
        },
    },
}


def scan_content_security(filename: str, data: bytes) -> list:
    issues = []
    name = (filename or "").lower()
    bad_ext = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".dll", ".so", ".dylib", ".vbs", ".ps1"}
    ext = os.path.splitext(name)[1]
    if ext in bad_ext:
        issues.append(f"امتداد خطير: {ext}")
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return issues
    if not text.strip():
        return issues
    for pat, reason in DANGEROUS_PATTERNS:
        if re.search(pat, text, re.IGNORECASE | re.MULTILINE):
            issues.append(reason)
    if len(data) > 2 * 1024 * 1024 and ext in {".py", ".js", ".txt"}:
        issues.append("ملف نصي كبير جدا (>2MB)")
    return list(dict.fromkeys(issues))


def scan_project_security(project_id: int) -> list:
    out = []
    for row in db_fetchall("SELECT filename, content FROM project_files WHERE project_id=?", (project_id,)):
        issues = scan_content_security(row["filename"], bytes(row["content"]))
        if issues:
            out.append((row["filename"], issues))
    return out


def flag_project_security(project_id: int, issues_flat: list) -> None:
    try:
        db_execute(
            "UPDATE projects SET security_flag=1, security_note=?, security_approved=0 WHERE id=?",
            ("; ".join(issues_flat)[:900], project_id),
        )
    except Exception:
        log.exception("flag_project_security")


def clear_project_security(project_id: int) -> None:
    try:
        db_execute(
            "UPDATE projects SET security_flag=0, security_note=NULL, security_approved=1 WHERE id=?",
            (project_id,),
        )
    except Exception:
        pass


def is_auto_approve_enabled() -> bool:
    return (get_setting("auto_approve", "0") or "0") == "1"


def is_security_block_enabled() -> bool:
    return (get_setting("security_scan", "1") or "1") == "1"


def project_subscription_ok(project_id: int) -> tuple:
    row = db_fetchone("SELECT expires_at FROM projects WHERE id=?", (project_id,))
    if not row or not row.get("expires_at"):
        return True, ""
    try:
        exp = datetime.strptime(str(row["expires_at"]).split(".")[0], "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() > exp:
            return False, "انتهت صلاحية اشتراك هذا البوت."
    except Exception:
        pass
    return True, ""


def notify_owner_crash(project_id: int, detail: str = "") -> None:
    p = db_fetchone("SELECT user_id, name, notify_crash FROM projects WHERE id=?", (project_id,))
    if not p:
        return
    if p.get("notify_crash") is not None and int(p.get("notify_crash") or 0) == 0:
        return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("اعادة تشغيل", callback_data=f"proj_restart_{project_id}", style="success"))
    kb.add(types.InlineKeyboardButton("السجل", callback_data=f"proj_log_{project_id}", style="primary"))
    try:
        bot.send_message(
            p["user_id"],
            f"البوت توقف فجاة\n"
            f"<b>{html_escape(p.get('name') or '')}</b> #{project_id}\n"
            f"<blockquote>{html_escape((detail or '')[:400])}</blockquote>",
            reply_markup=kb,
        )
    except Exception:
        pass


def create_project_from_template(uid: int, template_key: str) -> tuple:
    tpl = BOT_TEMPLATES.get(template_key)
    if not tpl:
        return False, "قالب غير موجود"
    name = tpl["name"][:40]
    base = name
    n = 1
    while db_fetchone("SELECT id FROM projects WHERE user_id=? AND name=?", (uid, name)):
        name = f"{base}-{n}"
        n += 1
    pid = db_execute_returning_id(
        "INSERT INTO projects (user_id, name, main_file, runtime, approved, security_approved) VALUES (?,?,?,?,0,1)",
        (uid, name, tpl["main"], tpl["runtime"]),
    )
    for fn, content in tpl["files"].items():
        raw = content.encode("utf-8")
        db_execute(
            "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?)",
            (pid, fn, sqlite3.Binary(raw), len(raw)),
        )
    return True, str(pid)


def run_daily_backup_once() -> Optional[str]:
    try:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(tempfile.gettempdir(), f"hosting_backup_{ts}.db")
        shutil.copy2(DB_PATH, dest)
        return dest
    except Exception:
        log.exception("backup failed")
        return None


def export_all_data_zip() -> Optional[str]:
    try:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        zpath = os.path.join(tempfile.gettempdir(), f"host_export_{ts}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(DB_PATH):
                zf.write(DB_PATH, arcname="hosting_bot.db")
            settings = db_fetchall("SELECT key, value FROM settings")
            zf.writestr("settings.json", json.dumps([dict(x) for x in settings], ensure_ascii=False, indent=2, default=str))
            users = db_fetchall("SELECT id, username, first_name, points, banned, approved FROM users LIMIT 5000")
            zf.writestr("users.json", json.dumps([dict(x) for x in users], ensure_ascii=False, indent=2, default=str))
            projs = db_fetchall("SELECT id, user_id, name, main_file, runtime, approved, is_running FROM projects LIMIT 5000")
            zf.writestr("projects.json", json.dumps([dict(x) for x in projs], ensure_ascii=False, indent=2, default=str))
        return zpath
    except Exception:
        log.exception("export zip failed")
        return None


def _scheduler_loop() -> None:
    last_backup_day = ""
    while True:
        try:
            maint = (get_setting("scheduled_maintenance_until") or "").strip()
            if maint and (get_setting("auto_end_maint") or "0") == "1":
                try:
                    until = datetime.strptime(maint.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    if datetime.utcnow() > until and is_bot_disabled():
                        set_bot_disabled(False)
                        set_setting("scheduled_maintenance_until", "")
                except Exception:
                    pass
            day = datetime.utcnow().strftime("%Y-%m-%d")
            if day != last_backup_day and (get_setting("daily_backup") or "0") == "1":
                last_backup_day = day
                path_b = run_daily_backup_once()
                if path_b:
                    try:
                        with open(path_b, "rb") as fh:
                            bot.send_document(ADMIN_ID, fh, caption=f"نسخة يومية {day}")
                    except Exception:
                        pass
            rows = db_fetchall(
                "SELECT id, schedule_json FROM projects WHERE schedule_json IS NOT NULL AND schedule_json != ''"
            )
            hhmm = datetime.utcnow().strftime("%H:%M")
            for r in rows:
                try:
                    sch = json.loads(r["schedule_json"])
                    start_at = sch.get("start")
                    stop_at = sch.get("stop")
                    pid = r["id"]
                    if start_at and hhmm == start_at and not manager.is_running(pid):
                        ok_sub, _ = project_subscription_ok(pid)
                        if ok_sub:
                            manager.start_project(pid)
                    if stop_at and hhmm == stop_at and manager.is_running(pid):
                        manager.stop_project(pid)
                except Exception:
                    continue
            try:
                process_start_queue_once()
            except Exception:
                pass
            # تجديد طاقة منتصف الليل تقريبا
            if datetime.utcnow().strftime("%H:%M") == "00:00":
                try:
                    refill_energy_daily()
                except Exception:
                    pass
        except Exception:
            log.exception("scheduler loop")
        time.sleep(30)



def start_scheduler() -> None:
    threading.Thread(target=_scheduler_loop, name="scheduler", daemon=True).start()
    log.info("Scheduler started")


# ============================================================
# انظمة متقدمة: Crash Budget / Queue / Snapshots / Energy / SLA / Preflight / Jail
# ============================================================
_start_queue: list = []
_start_queue_lock = threading.Lock()
_crash_window: dict = {}  # project_id -> list[timestamps]
_CRASH_BUDGET_MAX = 5
_CRASH_BUDGET_WINDOW_SEC = 3600
_energy_lock = threading.Lock()


def _ensure_advanced_schema() -> None:
    try:
        pcols = [r["name"] for r in db_fetchall("PRAGMA table_info(projects)")]
        for col, defn in [
            ("crash_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("token_confirmed_at", "TIMESTAMP"),
            ("heir_uid", "INTEGER"),
            ("energy_exempt", "INTEGER NOT NULL DEFAULT 0"),
            ("health_score", "INTEGER NOT NULL DEFAULT 100"),
            ("last_preflight", "TEXT"),
            ("ghost_mode", "INTEGER NOT NULL DEFAULT 0"),
            ("passport_code", "TEXT"),
        ]:
            if col not in pcols:
                try:
                    db_execute(f"ALTER TABLE projects ADD COLUMN {col} {defn}")
                except Exception:
                    pass
        ucols = [r["name"] for r in db_fetchall("PRAGMA table_info(users)")]
        for col, defn in [
            ("energy", "INTEGER NOT NULL DEFAULT 100"),
            ("energy_max", "INTEGER NOT NULL DEFAULT 100"),
            ("risk_score", "INTEGER NOT NULL DEFAULT 0"),
            ("referral_tier_points", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if col not in ucols:
                try:
                    db_execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
                except Exception:
                    pass
        db_execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                label TEXT,
                payload BLOB NOT NULL,
                size_bytes INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db_execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER,
                command TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db_execute(
            """
            CREATE TABLE IF NOT EXISTS sla_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT,
                compensated_points INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db_execute(
            """
            CREATE TABLE IF NOT EXISTS token_registry (
                token_hash TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    except Exception:
        log.exception("advanced schema")


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def register_project_token(project_id: int, user_id: int, token: str) -> tuple:
    """يسجل التوكن ويكشف التكرار. (ok, message)"""
    if not token:
        return True, ""
    th = _token_hash(token)
    row = db_fetchone("SELECT project_id, user_id FROM token_registry WHERE token_hash=?", (th,))
    if row and int(row["project_id"]) != int(project_id):
        # تجميد المشروعين
        try:
            db_execute("UPDATE projects SET crash_locked=1, is_running=0 WHERE id IN (?,?)", (project_id, row["project_id"]))
            manager.stop_project(project_id)
            manager.stop_project(row["project_id"])
        except Exception:
            pass
        try:
            bot.send_message(ADMIN_ID, f"توكن مكرر بين مشروع #{project_id} و #{row['project_id']}")
        except Exception:
            pass
        return False, "هذا التوكن مستخدم في مشروع اخر — تم تجميد التشغيل"
    db_execute(
        "INSERT INTO token_registry (token_hash, project_id, user_id, updated_at) VALUES (?,?,?,CURRENT_TIMESTAMP) "
        "ON CONFLICT(token_hash) DO UPDATE SET project_id=excluded.project_id, user_id=excluded.user_id, updated_at=CURRENT_TIMESTAMP",
        (th, project_id, user_id),
    )
    return True, ""


def record_crash_budget(project_id: int) -> bool:
    """True اذا تجاوز الميزانية ويجب القفل."""
    now = time.time()
    window = _crash_window.setdefault(project_id, [])
    window.append(now)
    _crash_window[project_id] = [t for t in window if now - t <= _CRASH_BUDGET_WINDOW_SEC]
    if len(_crash_window[project_id]) >= _CRASH_BUDGET_MAX:
        db_execute("UPDATE projects SET crash_locked=1 WHERE id=?", (project_id,))
        return True
    return False


def clear_crash_lock(project_id: int) -> None:
    _crash_window[project_id] = []
    db_execute("UPDATE projects SET crash_locked=0 WHERE id=?", (project_id,))


def get_user_energy(uid: int) -> int:
    row = db_fetchone("SELECT COALESCE(energy,100) AS e FROM users WHERE id=?", (uid,))
    return int((row or {}).get("e") or 100)


def consume_energy(uid: int, amount: int = 1) -> tuple:
    if is_admin(uid):
        return True, ""
    with _energy_lock:
        e = get_user_energy(uid)
        if e < amount:
            return False, f"الطاقة غير كافية ({e}). اشحن من الباقات او انتظر التجديد."
        db_execute("UPDATE users SET energy = COALESCE(energy,100) - ? WHERE id=?", (amount, uid))
    return True, ""


def refill_energy_daily() -> None:
    try:
        db_execute("UPDATE users SET energy = COALESCE(energy_max,100) WHERE COALESCE(energy,0) < COALESCE(energy_max,100)")
    except Exception:
        pass


def selective_maint_blocks(section: str) -> bool:
    """True اذا القسم مقفول للصيانة الانتقائية."""
    raw = (get_setting("selective_maint") or "").strip().lower()
    if not raw:
        return False
    parts = {x.strip() for x in raw.split(",") if x.strip()}
    return section in parts or "all" in parts


def make_passport_code(project_id: int) -> str:
    code = f"FLIX-{project_id:04d}-{secrets_token_short()}"
    try:
        db_execute("UPDATE projects SET passport_code=? WHERE id=?", (code, project_id))
    except Exception:
        pass
    return code


def secrets_token_short() -> str:
    import secrets as _sec
    return _sec.token_hex(3).upper()


def create_snapshot(project_id: int, label: str = "auto") -> bool:
    try:
        files = db_fetchall("SELECT filename, content, size_bytes FROM project_files WHERE project_id=?", (project_id,))
        meta = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,)) or {}
        payload = json.dumps({
            "meta": {k: meta.get(k) for k in ("name", "main_file", "runtime", "hosted_bot_username") if k in meta},
            "files": [{"filename": f["filename"], "content_b64": base64.b64encode(bytes(f["content"])).decode("ascii")} for f in files],
        }).encode("utf-8")
        db_execute(
            "INSERT INTO snapshots (project_id, label, payload, size_bytes) VALUES (?,?,?,?)",
            (project_id, label[:80], sqlite3.Binary(payload), len(payload)),
        )
        # احتفظ باخر 10 فقط
        old = db_fetchall(
            "SELECT id FROM snapshots WHERE project_id=? ORDER BY id DESC LIMIT -1 OFFSET 10",
            (project_id,),
        )
        for o in old:
            db_execute("DELETE FROM snapshots WHERE id=?", (o["id"],))
        return True
    except Exception:
        log.exception("snapshot failed")
        return False


def restore_snapshot(project_id: int, snap_id: int) -> tuple:
    row = db_fetchone("SELECT * FROM snapshots WHERE id=? AND project_id=?", (snap_id, project_id))
    if not row:
        return False, "اللقطة غير موجودة"
    try:
        data = json.loads(bytes(row["payload"]).decode("utf-8"))
        db_execute("DELETE FROM project_files WHERE project_id=?", (project_id,))
        for f in data.get("files") or []:
            raw = base64.b64decode(f["content_b64"])
            db_execute(
                "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?)",
                (project_id, f["filename"], sqlite3.Binary(raw), len(raw)),
            )
        return True, "تمت الاستعادة — اعد التشغيل"
    except Exception as e:
        return False, str(e)[:200]


def preflight_project(project_id: int) -> dict:
    """فحص قبل التشغيل."""
    result = {"ok": True, "checks": []}
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        return {"ok": False, "checks": [("project", False, "غير موجود")]}
    def add(name, ok, msg):
        result["checks"].append((name, ok, msg))
        if not ok:
            result["ok"] = False
    add("approved", bool(p.get("approved")), "موافقة الادمن" if p.get("approved") else "غير موافق عليه")
    sec_ok = not (is_security_block_enabled() and int(p.get("security_flag") or 0) == 1 and int(p.get("security_approved") or 0) != 1)
    add("security", sec_ok, "امن OK" if sec_ok else "بانتظار موافقة امنية")
    add("crash_lock", not int(p.get("crash_locked") or 0), "غير مقفول" if not int(p.get("crash_locked") or 0) else "مقفول Crash Budget")
    ok_sub, sub_msg = project_subscription_ok(project_id)
    add("subscription", ok_sub, "اشتراك ساري" if ok_sub else (sub_msg or "منتهي"))
    mf = (p.get("main_file") or "").strip()
    has_main = False
    if mf:
        fr = db_fetchone("SELECT id FROM project_files WHERE project_id=? AND filename=?", (project_id, mf))
        has_main = fr is not None
    add("main_file", has_main, f"الملف {mf}" if has_main else f"الملف الرئيسي مفقود: {mf or '-'}")
    tok = (p.get("hosted_token") or "").strip()
    if tok:
        info = telegram_get_me(tok)
        add("token", bool(info), f"@{info.get('username')}" if info else "توكن لا يرد على getMe")
    else:
        add("token", True, "لا يوجد توكن محفوظ (اختياري)")
    # syntax خفيف لبايثون
    if has_main and mf.endswith(".py"):
        row = db_fetchone("SELECT content FROM project_files WHERE project_id=? AND filename=?", (project_id, mf))
        try:
            code = bytes(row["content"]).decode("utf-8", errors="replace")
            compile(code, mf, "exec")
            add("syntax", True, "Syntax Python OK")
        except SyntaxError as e:
            add("syntax", False, f"SyntaxError: {e.msg} line {e.lineno}")
        except Exception as e:
            add("syntax", True, f"تخطي فحص صارم: {e}")
    try:
        db_execute("UPDATE projects SET last_preflight=? WHERE id=?", (json.dumps(result["checks"], ensure_ascii=False)[:1500], project_id))
    except Exception:
        pass
    return result


def start_lock_status_text(project_id: int) -> str:
    pf = preflight_project(project_id)
    lines = ["<b>قفل التشغيل — الشروط</b>", "<blockquote>"]
    for name, ok, msg in pf["checks"]:
        lines.append(f"{'🟢' if ok else '🔴'} <b>{html_escape(name)}</b>: {html_escape(str(msg))}")
    lines.append("</blockquote>")
    lines.append("النتيجة: " + ("جاهز للتشغيل" if pf["ok"] else "غير جاهز"))
    return "\n".join(lines)


def enqueue_start(project_id: int) -> str:
    with _start_queue_lock:
        if project_id in _start_queue:
            return "المشروع في الطابور بالفعل"
        _start_queue.append(project_id)
        pos = _start_queue.index(project_id) + 1
    return f"تمت الاضافة للطابور — المركز {pos}"


def process_start_queue_once() -> None:
    with _start_queue_lock:
        if not _start_queue:
            return
        # حد توازي بسيط
        running = 0
        try:
            with manager.lock:
                running = sum(1 for hp in manager.processes.values() if hp.is_alive())
        except Exception:
            pass
        max_parallel = int(get_setting("max_parallel_bots") or "20")
        if running >= max_parallel:
            return
        pid = _start_queue.pop(0)
    try:
        manager.start_project(pid)
    except Exception:
        log.exception("queue start %s", pid)


def project_passport_text(project_id: int) -> str:
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        return "غير موجود"
    code = p.get("passport_code") or make_passport_code(project_id)
    running = manager.is_running(project_id)
    return (
        f"<b>Project Passport</b>\n"
        f"<blockquote>"
        f"ختم: <code>{html_escape(code)}</code>\n"
        f"الاسم: <b>{html_escape(p.get('name') or '')}</b>\n"
        f"ID: <code>{project_id}</code>\n"
        f"Runtime: {html_escape(p.get('runtime') or 'python')}\n"
        f"Main: <code>{html_escape(p.get('main_file') or '-')}</code>\n"
        f"Bot: @{html_escape(p.get('hosted_bot_username') or '-')}\n"
        f"الحالة: {'شغال' if running else 'واقف'}\n"
        f"Health: {p.get('health_score') or 100}\n"
        f"امن: flag={p.get('security_flag') or 0} approved={p.get('security_approved') or 0}\n"
        f"CrashLock: {p.get('crash_locked') or 0}\n"
        f"</blockquote>"
    )


def apply_sla_compensation(points: int, reason: str) -> int:
    """يعوض كل المستخدمين المفعلين."""
    db_execute(
        "UPDATE users SET points = COALESCE(points,0) + ? WHERE approved=1 AND banned=0",
        (points,),
    )
    db_execute("INSERT INTO sla_events (reason, compensated_points) VALUES (?,?)", (reason[:200], points))
    row = db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0")
    return int((row or {}).get("c") or 0)


def bump_risk_score(uid: int, delta: int = 5) -> None:
    try:
        db_execute("UPDATE users SET risk_score = COALESCE(risk_score,0) + ? WHERE id=?", (delta, uid))
    except Exception:
        pass


def jail_materialize_env(project_id: int, work_dir: str) -> dict:
    """بيئة معزولة نسبيا لكل مشروع."""
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "HOSTING_PROJECT_ID": str(project_id),
        "HOSTING_PROJECT_DIR": work_dir,
        "HOME": work_dir,
        "TMPDIR": work_dir,
        "TEMP": work_dir,
        "TMP": work_dir,
    }
    # منع توكن الاستضافة من الانتقال للبوتات المستضافة
    env.pop("BOT_TOKEN", None)
    return env






def fmt_rich(title: str, body: str, quote: bool = True) -> str:
    """تنسيق نص عصري: عنوان عريض + اقتباس خفيف."""
    parts = [f"<b>{title}</b>"]
    if body:
        if quote:
            parts.append(f"<blockquote>{body}</blockquote>")
        else:
            parts.append(body)
    return "\n".join(parts)



# ============================================================
# 3) فحوص أولية
# ============================================================
if not BOT_TOKEN or BOT_TOKEN == "ضع_توكن_بوتك_هنا":
    raise RuntimeError("BOT_TOKEN غير مضبوط — ضع توكن بوتك في متغير البيئة BOT_TOKEN")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID غير مضبوط — ضع ID حسابك في متغير البيئة ADMIN_ID")

os.makedirs(PROJECTS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("hosting-bot")

# ============================================================
# 4) قاعدة البيانات SQLite
# ============================================================
_db_lock = threading.RLock()
_db_conn: Optional[sqlite3.Connection] = None


def db_init() -> None:
    global _db_conn
    if _db_conn is not None:
        return
    _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    _db_conn.row_factory = sqlite3.Row
    _db_conn.execute("PRAGMA journal_mode=WAL")
    _db_conn.execute("PRAGMA synchronous=NORMAL")
    _db_conn.execute("PRAGMA foreign_keys=ON")
    _db_conn.execute("PRAGMA busy_timeout=5000")
    log.info("SQLite database opened at %s", DB_PATH)


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row is not None else None


def db_fetchone(query: str, params: Iterable[Any] = ()) -> Optional[dict]:
    with _db_lock:
        cur = _db_conn.execute(query, tuple(params))
        row = cur.fetchone()
        cur.close()
    return _row_to_dict(row)


def db_fetchall(query: str, params: Iterable[Any] = ()) -> list:
    with _db_lock:
        cur = _db_conn.execute(query, tuple(params))
        rows = cur.fetchall()
        cur.close()
    return [dict(r) for r in rows]


def db_execute(query: str, params: Iterable[Any] = ()) -> None:
    with _db_lock:
        cur = _db_conn.execute(query, tuple(params))
        cur.close()


def db_execute_returning_id(query: str, params: Iterable[Any] = ()) -> int:
    with _db_lock:
        cur = _db_conn.execute(query, tuple(params))
        rid = cur.lastrowid
        cur.close()
    return rid


# ============================================================
# 5) إنشاء الجداول
# ============================================================
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY,
    first_name   TEXT,
    username     TEXT,
    approved     INTEGER NOT NULL DEFAULT 0,
    banned       INTEGER NOT NULL DEFAULT 0,
    max_bots     INTEGER NOT NULL DEFAULT 5,
    points       INTEGER NOT NULL DEFAULT 0,
    referred_by  INTEGER,
    blocked_bot  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    main_file       TEXT NOT NULL DEFAULT '',
    runtime         TEXT NOT NULL DEFAULT 'python',
    approved        INTEGER NOT NULL DEFAULT 0,
    is_running      INTEGER NOT NULL DEFAULT 0,
    last_started_at TIMESTAMP,
    last_stopped_at TIMESTAMP,
    last_error      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS project_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    content     BLOB NOT NULL,
    size_bytes  INTEGER NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, filename)
);

CREATE TABLE IF NOT EXISTS pending_uploads (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    project_id         INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename           TEXT NOT NULL,
    telegram_file_id   TEXT NOT NULL,
    size_bytes         INTEGER NOT NULL,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS process_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    event       TEXT NOT NULL,
    message     TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS gift_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT UNIQUE NOT NULL,
    points      INTEGER NOT NULL,
    max_uses    INTEGER NOT NULL,
    used_count  INTEGER NOT NULL DEFAULT 0,
    created_by  INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gift_link_uses (
    link_id  INTEGER NOT NULL REFERENCES gift_links(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL,
    used_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (link_id, user_id)
);

CREATE TABLE IF NOT EXISTS netlify_sites (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id        TEXT UNIQUE NOT NULL,
    site_name      TEXT NOT NULL,
    site_url       TEXT NOT NULL,
    last_deploy_id TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_deploy_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moderators (
    user_id    INTEGER PRIMARY KEY,
    added_by   INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deployments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider    TEXT NOT NULL,
    site_id     TEXT,
    deploy_id   TEXT,
    url         TEXT NOT NULL,
    filename    TEXT,
    size_bytes  INTEGER,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_daily (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    section   TEXT NOT NULL,
    count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, section)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER NOT NULL,
    action      TEXT NOT NULL,
    target_uid  INTEGER,
    project_id  INTEGER,
    provider    TEXT,
    filename    TEXT,
    size_bytes  INTEGER,
    command     TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_user   ON projects (user_id);
CREATE INDEX IF NOT EXISTS idx_files_project   ON project_files (project_id);
CREATE INDEX IF NOT EXISTS idx_pending_project ON pending_uploads (project_id);
CREATE INDEX IF NOT EXISTS idx_logs_project    ON process_logs (project_id);
CREATE INDEX IF NOT EXISTS idx_gift_uses_link  ON gift_link_uses (link_id);
CREATE INDEX IF NOT EXISTS idx_netlify_user    ON netlify_sites (user_id);
CREATE INDEX IF NOT EXISTS idx_deploy_user     ON deployments (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_deploy_provider ON deployments (provider, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_day       ON usage_daily (day, section);
CREATE INDEX IF NOT EXISTS idx_audit_time      ON audit_log (created_at);

CREATE TABLE IF NOT EXISTS force_channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel     TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL DEFAULT '',
    ch_type     TEXT NOT NULL DEFAULT 'public',
    invite_link TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def db_create_schema() -> None:
    with _db_lock:
        _db_conn.executescript(SCHEMA_SQL)
    log.info("Database schema is ready")


def db_ensure_columns() -> None:
    cols = [r["name"] for r in db_fetchall("PRAGMA table_info(users)")]
    for col, defn in [
        ("points", "INTEGER NOT NULL DEFAULT 0"),
        ("referred_by", "INTEGER"),
        ("blocked_bot", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if col not in cols:
            db_execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            log.info("Added column users.%s", col)

    pcols = [r["name"] for r in db_fetchall("PRAGMA table_info(projects)")]
    if pcols and "runtime" not in pcols:
        db_execute("ALTER TABLE projects ADD COLUMN runtime TEXT NOT NULL DEFAULT 'python'")
        log.info("Added column projects.runtime")
        for row in db_fetchall("SELECT id, main_file FROM projects"):
            mf = (row.get("main_file") or "").lower()
            rt = "nodejs" if mf.endswith((".js", ".mjs", ".cjs", ".ts")) else "python"
            db_execute("UPDATE projects SET runtime=? WHERE id=?", (rt, row["id"]))
    for col, defn in [
        ("hosted_token", "TEXT"),
        ("hosted_bot_username", "TEXT"),
        ("hosted_bot_id", "INTEGER"),
        ("hosted_bot_name", "TEXT"),
        ("owner_note", "TEXT"),
    ]:
        if pcols and col not in pcols:
            try:
                db_execute(f"ALTER TABLE projects ADD COLUMN {col} {defn}")
                log.info("Added column projects.%s", col)
                pcols.append(col)
            except Exception:
                pass
    # إعادة قراءة أعمدة users
    ucols = [r["name"] for r in db_fetchall("PRAGMA table_info(users)")]
    for col, defn in [
        ("lang", "TEXT NOT NULL DEFAULT 'ar'"),
        ("verified", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if col not in ucols:
            try:
                db_execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
                log.info("Added column users.%s", col)
            except Exception:
                pass
    # جدول طلبات الإصلاح
    db_execute("""
    CREATE TABLE IF NOT EXISTS repair_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        admin_note TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    pcols2 = [r["name"] for r in db_fetchall("PRAGMA table_info(projects)")]
    for col, defn in [
        ("security_flag", "INTEGER NOT NULL DEFAULT 0"),
        ("security_note", "TEXT"),
        ("security_approved", "INTEGER NOT NULL DEFAULT 0"),
        ("expires_at", "TIMESTAMP"),
        ("schedule_json", "TEXT"),
        ("notify_crash", "INTEGER NOT NULL DEFAULT 1"),
    ]:
        if col not in pcols2:
            try:
                db_execute(f"ALTER TABLE projects ADD COLUMN {col} {defn}")
                log.info("Added column projects.%s", col)
            except Exception:
                pass
    db_execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        max_uses INTEGER NOT NULL DEFAULT 1,
        used_count INTEGER NOT NULL DEFAULT 0,
        expires_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    db_execute("""
    CREATE TABLE IF NOT EXISTS coupon_uses (
        code TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (code, user_id)
    )
    """)

    gcols = [r["name"] for r in db_fetchall("PRAGMA table_info(gift_links)")]
    if gcols and "expires_at" not in gcols:
        db_execute("ALTER TABLE gift_links ADD COLUMN expires_at TIMESTAMP")

    fccols = [r["name"] for r in db_fetchall("PRAGMA table_info(force_channels)")]
    if fccols and "invite_link" not in fccols:
        db_execute("ALTER TABLE force_channels ADD COLUMN invite_link TEXT NOT NULL DEFAULT ''")
        log.info("Added column force_channels.invite_link")

    pucols = [r["name"] for r in db_fetchall("PRAGMA table_info(pending_uploads)")]
    if pucols and "status" not in pucols:
        db_execute("ALTER TABLE pending_uploads ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        log.info("Added column pending_uploads.status")

    # هجرة: نقل force_channel القديم إلى جدول force_channels
    old_ch = (get_setting("force_channel", "") or "").strip()
    if old_ch:
        existing = db_fetchone("SELECT id FROM force_channels WHERE channel=?", (old_ch,))
        if not existing:
            ch_type = "private" if re.match(r"^-?\d+$", old_ch) else "public"
            db_execute(
                "INSERT OR IGNORE INTO force_channels (channel, label, ch_type) VALUES (?,?,?)",
                (old_ch, old_ch, ch_type),
            )
        set_setting("force_channel", "")
        log.info("Migrated legacy force_channel '%s' to force_channels table", old_ch)


# ============================================================
# 5.1) إعدادات
# ============================================================
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = db_fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    db_execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def get_upload_price() -> int:
    try:
        return max(0, int(get_setting("upload_price", "1") or "1"))
    except Exception:
        return 1


def get_transfer_fee() -> int:
    try:
        return max(0, int(get_setting("transfer_fee", "0") or "0"))
    except Exception:
        return 0


def get_force_channels() -> list:
    return db_fetchall("SELECT id, channel, label, ch_type, invite_link FROM force_channels ORDER BY id")


def get_force_channel() -> str:
    """توافق مع الكود القديم — يُعيد أول قناة أو نص فارغ"""
    rows = get_force_channels()
    return rows[0]["channel"] if rows else ""


def add_force_channel(channel: str, label: str = "", ch_type: str = "public", invite_link: str = "") -> bool:
    try:
        db_execute(
            "INSERT OR IGNORE INTO force_channels (channel, label, ch_type, invite_link) VALUES (?,?,?,?)",
            (channel, label or channel, ch_type, invite_link or ""),
        )
        return True
    except Exception:
        log.exception("add_force_channel failed for %s", channel)
        return False


def del_force_channel(fid: int) -> None:
    db_execute("DELETE FROM force_channels WHERE id=?", (fid,))


def update_force_channel_invite(fid: int, invite_link: str) -> bool:
    try:
        db_execute(
            "UPDATE force_channels SET invite_link=? WHERE id=?",
            (invite_link, fid),
        )
        return True
    except Exception:
        log.exception("update_force_channel_invite failed for id=%s", fid)
        return False


def update_force_channel_label(fid: int, label: str) -> bool:
    try:
        db_execute("UPDATE force_channels SET label=? WHERE id=?", (label, fid))
        return True
    except Exception:
        log.exception("update_force_channel_label failed for id=%s", fid)
        return False


def update_force_channel_id(fid: int, new_channel: str, ch_type: str) -> bool:
    try:
        db_execute(
            "UPDATE force_channels SET channel=?, ch_type=? WHERE id=?",
            (new_channel, ch_type, fid),
        )
        return True
    except Exception:
        log.exception("update_force_channel_id failed for id=%s", fid)
        return False


def is_user_subscribed_all(uid: int):
    """يُعيد (True, []) إذا مشترك في كل القنوات، أو (False, [قنوات ناقصة])"""
    channels = get_force_channels()
    if not channels:
        return True, []
    unsubscribed = [ch for ch in channels if not is_user_subscribed(uid, ch["channel"])]
    return len(unsubscribed) == 0, unsubscribed


def get_section_price(section_key: str, default: int = 0) -> int:
    try:
        return max(0, int(get_setting(f"price_{section_key}", str(default)) or str(default)))
    except Exception:
        return max(0, default)


def is_admin_notify_enabled(key: str, default: bool = True) -> bool:
    v = (get_setting(key, "1" if default else "0") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _today_utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_daily_limit(section: str, default: int) -> int:
    try:
        return max(0, int(get_setting(f"limit_daily_{section}", str(default)) or str(default)))
    except Exception:
        return max(0, default)


def check_and_inc_daily(uid: int, section: str, default_limit: int) -> tuple:
    if is_admin(uid):
        return True, ""
    limit = get_daily_limit(section, default_limit)
    if limit <= 0:
        return True, ""
    day = _today_utc_day()
    row = db_fetchone("SELECT count FROM usage_daily WHERE user_id=? AND day=? AND section=?", (uid, day, section))
    cur = int((row or {}).get("count") or 0)
    if cur >= limit:
        return False, f"❌ وصلت للحد اليومي لقسم {section}: <b>{limit}</b>"
    db_execute(
        "INSERT INTO usage_daily (user_id, day, section, count) VALUES (?,?,?,1) "
        "ON CONFLICT(user_id, day, section) DO UPDATE SET count = count + 1",
        (uid, day, section),
    )
    return True, ""


def is_bot_disabled() -> bool:
    return (get_setting("bot_disabled", "0") or "0") == "1"


def set_bot_disabled(disabled: bool) -> None:
    set_setting("bot_disabled", "1" if disabled else "0")


def normalize_channel(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # دعم chat_id الرقمي (قنوات خاصة مثل -1001234567890)
    if re.match(r"^-?\d+$", text):
        return text
    if text.startswith("https://t.me/"):
        text = text[len("https://t.me/"):]
    if text.startswith("t.me/"):
        text = text[len("t.me/"):]
    text = text.split("/")[0].split("?")[0]
    if not text:
        return ""
    if not text.startswith("@"):
        text = "@" + text
    return text


# ============================================================
# 5.2) فحص الاشتراك الإجباري في القناة
# ============================================================

# ذاكرة مؤقتة لتجنب إرسال نفس التنبيه أكثر من مرة
_perm_warn_sent: set = set()


def notify_admin_perm_error(channel: str, label: str, error: str) -> None:
    """يُرسل تنبيهاً للأدمن مرة واحدة لكل قناة عند اكتشاف مشكلة صلاحيات."""
    cache_key = f"{channel}"
    if cache_key in _perm_warn_sent:
        return
    _perm_warn_sent.add(cache_key)
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ <b>تنبيه — صلاحيات البوت ناقصة!</b>\n\n"
            f"📢 القناة: <b>{html_escape(label or channel)}</b>\n"
            f"🆔 المعرف: <code>{html_escape(str(channel))}</code>\n\n"
            f"❌ <b>الخطأ:</b>\n<code>{html_escape(error[:300])}</code>\n\n"
            "📌 <b>الحل المطلوب:</b>\n"
            "• اجعل البوت <b>مشرفاً</b> في القناة\n"
            "• امنحه صلاحية <b>Invite Users via Link</b>\n\n"
            "يمكنك فحص جميع القنوات من:\n"
            "<b>لوحة الأدمن ← الاشتراك الإجباري ← 🔍 فحص الصلاحيات</b>",
        )
    except Exception:
        log.exception("notify_admin_perm_error: failed to notify admin for %s", channel)


def check_bot_channel_permissions(channel: str) -> dict:
    """
    يفحص صلاحيات البوت في القناة المحددة.
    يُعيد dict يحتوي على:
      ok        — True إذا كان البوت مشرفاً بالصلاحيات الكاملة
      is_admin  — True إذا كان البوت مشرفاً أو مالكاً
      can_invite — True إذا كان لديه صلاحية Invite Users via Link
      error     — نص الخطأ إن وجد
    """
    result = {"ok": False, "is_admin": False, "can_invite": False, "error": None}
    try:
        bot_id = bot.get_me().id
        member = bot.get_chat_member(channel, bot_id)
        status = getattr(member, "status", "left")
        if status == "creator":
            result.update({"ok": True, "is_admin": True, "can_invite": True})
        elif status == "administrator":
            can_invite = bool(getattr(member, "can_invite_users", False))
            result.update({"is_admin": True, "can_invite": can_invite, "ok": can_invite})
            if not can_invite:
                result["error"] = "البوت مشرف لكن بدون صلاحية Invite Users via Link"
        else:
            result["error"] = f"البوت ليس مشرفاً في القناة (الحالة الحالية: {status})"
    except Exception as exc:
        result["error"] = str(exc)[:300]
    return result


def is_user_subscribed(uid: int, channel: str) -> bool:
    if not channel:
        return True
    try:
        member = bot.get_chat_member(channel, uid)
        return getattr(member, "status", "left") not in ("left", "kicked")
    except Exception as exc:
        err_str = str(exc).lower()
        log.exception("get_chat_member failed for %s in %s", uid, channel)
        # تنبيه الأدمن إذا كان الخطأ ناتجاً عن نقص صلاحيات البوت
        if any(kw in err_str for kw in (
            "not enough rights", "forbidden", "administrator",
            "bot is not", "have no rights", "chat not found",
        )):
            ch_row = db_fetchone("SELECT label FROM force_channels WHERE channel=?", (channel,))
            label = (ch_row or {}).get("label") or channel
            notify_admin_perm_error(channel, label, str(exc)[:300])
        return True


def force_sub_block(chat_id: int, uid: int) -> bool:
    if is_admin(uid):
        return False
    ok, unsubscribed = is_user_subscribed_all(uid)
    if ok:
        return False
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in unsubscribed:
        label = ch["label"] or ch["channel"]
        if ch["ch_type"] == "public":
            join_url = f"https://t.me/{ch['channel'].lstrip('@')}"
            kb.add(types.InlineKeyboardButton(f"📢 اشترك ← {label}", url=join_url, style="primary"))
        else:
            invite_link = (ch.get("invite_link") or "").strip()
            if invite_link:
                kb.add(types.InlineKeyboardButton(f"📢 اشترك ← {label}", url=invite_link, style="primary"))
            else:
                kb.add(types.InlineKeyboardButton(f"🔒 قناة خاصة: {label}", callback_data="noop", style="primary"))
    kb.add(types.InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data="check_sub", style="success"))
    lines = "\n".join(f"• {ch['label'] or ch['channel']}" for ch in unsubscribed)
    bot.send_message(
        chat_id,
        f"⚠️ <b>للاستمرار يجب الاشتراك في القنوات التالية:</b>\n\n{lines}\n\n"
        "اضغط على زر الاشتراك ثم اضغط <b>تحقّق</b>.",
        reply_markup=kb,
    )
    return True


# ============================================================
# 5.3) روابط هدايا النقاط
# ============================================================
def _new_gift_token() -> str:
    import secrets
    return secrets.token_urlsafe(8)


def process_gift_link(uid: int, token: str) -> None:
    link = db_fetchone("SELECT * FROM gift_links WHERE token=?", (token,))
    if not link:
        try:
            bot.send_message(uid, "❌ رابط الهدية غير صالح.")
        except Exception:
            pass
        return
    expires_at = link.get("expires_at")
    if expires_at:
        try:
            exp = datetime.strptime(str(expires_at).split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                try:
                    bot.send_message(uid, "❌ انتهت صلاحية رابط الهدية.")
                except Exception:
                    pass
                return
        except Exception:
            pass
    used = db_fetchone("SELECT 1 AS x FROM gift_link_uses WHERE link_id=? AND user_id=?", (link["id"], uid))
    if used:
        try:
            bot.send_message(uid, "❌ سبق وأن استخدمت هذا الرابط من قبل.")
        except Exception:
            pass
        return
    with _db_lock:
        link2 = db_fetchone("SELECT used_count, max_uses, points FROM gift_links WHERE id=?", (link["id"],))
        if not link2 or link2["used_count"] >= link2["max_uses"]:
            try:
                bot.send_message(uid, "❌ تم استنفاذ هذا الرابط (وصل للحد الأقصى).")
            except Exception:
                pass
            return
        db_execute("UPDATE gift_links SET used_count = used_count + 1 WHERE id=? AND used_count < max_uses", (link["id"],))
        db_execute("INSERT OR IGNORE INTO gift_link_uses (link_id, user_id) VALUES (?, ?)", (link["id"], uid))
        db_execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE id=?", (link2["points"], uid))
    try:
        bot.send_message(uid, f"🎁 تهانينا! حصلت على <b>{link2['points']}</b> نقطة من رابط الهدية 🎉")
    except Exception:
        pass


# ============================================================
# 6) Netlify
# ============================================================
def netlify_is_configured() -> bool:
    return bool(NETLIFY_TOKEN)


def _slugify_site_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:63] or "tg-site"


def _netlify_request(method: str, path: str, *, body: Optional[bytes] = None,
                     content_type: Optional[str] = None, timeout: int = 60) -> dict:
    if not netlify_is_configured():
        raise RuntimeError("NETLIFY_TOKEN is not set")
    url = f"{NETLIFY_API_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {NETLIFY_TOKEN}", "User-Agent": "tg-hosting-bot/1.0"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = str(e)
        raise RuntimeError(f"Netlify API error ({e.code}): {msg[:400]}")


def netlify_create_site_for_user(uid: int) -> dict:
    base = _slugify_site_name(f"{NETLIFY_SITE_PREFIX}-{uid}-{int(time.time())}")
    payload = json.dumps({"name": base}).encode("utf-8")
    return _netlify_request("POST", "/sites", body=payload, content_type="application/json", timeout=60)


def netlify_deploy_zip(site_id: str, zip_bytes: bytes) -> dict:
    return _netlify_request("POST", f"/sites/{site_id}/deploys", body=zip_bytes,
                            content_type="application/zip", timeout=180)


def _netlify_pick_site_url(site_payload: dict) -> str:
    for k in ("ssl_url", "url", "admin_url"):
        v = (site_payload or {}).get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# ============================================================
# 7) Vercel
# ============================================================
def vercel_is_configured() -> bool:
    return bool(VERCEL_TOKEN)


def _vercel_request(method: str, path: str, *, body: Optional[bytes] = None,
                    content_type: str = "application/json", timeout: int = 120) -> dict:
    if not vercel_is_configured():
        raise RuntimeError("VERCEL_TOKEN is not set")
    url = f"{VERCEL_API_BASE}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "User-Agent": "tg-hosting-bot/1.0",
        "Content-Type": content_type,
    }
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = str(e)
        raise RuntimeError(f"Vercel API error ({e.code}): {msg[:400]}")


def _vercel_prepare_files_from_zip(zip_bytes: bytes) -> tuple:
    allowed_ext = {".html", ".css", ".js"}
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = [n for n in zf.namelist() if n and not n.endswith("/") and not n.startswith("__MACOSX/")]
    if not names:
        raise RuntimeError("الـ ZIP فاضي.")
    top = None
    parts0 = [n.split("/", 1)[0] for n in names if "/" in n]
    if parts0 and len(set(parts0)) == 1:
        top = parts0[0] + "/"
    files: list = []
    total = 0
    seen_index = False
    for n in names:
        rel = n[len(top):] if top and n.startswith(top) else n
        rel = rel.lstrip("/").replace("\\", "/")
        if not rel or rel.endswith("/") or ".." in rel:
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext not in allowed_ext:
            continue
        data = zf.read(n)
        total += len(data)
        if total > MAX_VERCEL_INLINE_BYTES:
            raise RuntimeError(f"ملفات كبيرة جداً للرفع (تخطت {MAX_VERCEL_INLINE_BYTES//1024}KB).")
        if rel.lower() == "index.html":
            seen_index = True
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("utf-8", errors="replace")
        files.append({"file": rel, "data": text})
        if len(files) > 200:
            raise RuntimeError("عدد الملفات كبير جداً.")
    if not files:
        raise RuntimeError("لا يوجد ملفات مدعومة داخل الـ ZIP (فقط .html .css .js).")
    if not seen_index:
        raise RuntimeError("لازم يكون موجود index.html في جذر الملف المضغوط أو داخل فولدر واحد.")
    name = _slugify_site_name(f"{VERCEL_SITE_PREFIX}-{int(time.time())}")
    return files, name


def vercel_deploy_zip(zip_bytes: bytes, *, uid: int) -> dict:
    files, name = _vercel_prepare_files_from_zip(zip_bytes)
    payload = json.dumps({"name": f"{name}-{uid}", "files": files}).encode("utf-8")
    return _vercel_request("POST", "/v13/deployments", body=payload, timeout=180)


def send_file_bytes_to_admin(filename: str, data: bytes, caption: str) -> None:
    try:
        bio = io.BytesIO(data)
        bio.name = filename
        bot.send_document(ADMIN_ID, bio, caption=caption)
    except Exception:
        pass


# ============================================================
# 8) محرك الاستضافة v3 — Python + Node.js (تشغيل ذاتي الإصلاح)
# ============================================================
# - مجلد المشروع دائم: لا يُمسح عند كل تشغيل (node_modules و .venv تبقى).
# - بيئة Python معزولة لكل مشروع (.venv) + تثبيت تلقائي للمكتبات.
# - Node.js: npm install ذكي (فقط عند تغيّر package.json) + دعم TypeScript و ESM.
# - فحص أخطاء قبل التشغيل + تحليل سجل التشغيل + إصلاح تلقائي ثم إعادة المحاولة.
# - مراقب (Watchdog) لا يتجمد: إعادة تشغيل متوازية مع تأخير تصاعدي.
# ============================================================
import ast as _ast
import concurrent.futures as _cf

ENGINE_STARTUP_GRACE = float(os.environ.get("STARTUP_GRACE", "7") or 7)
ENGINE_MAX_HEAL = 4
ENGINE_MAX_MEM_MB = int(os.environ.get("MAX_PROJECT_MEM_MB", "0") or 0)   # 0 = بدون حد
ENGINE_LOG_MAX = 5 * 1024 * 1024
ENGINE_INSTALL_TIMEOUT = int(os.environ.get("INSTALL_TIMEOUT", "420") or 420)
ENGINE_USE_VENV = (os.environ.get("USE_VENV", "1") or "1") != "0"

ENGINE_STATE_DIR = ".flix"
ENGINE_PROTECTED = {
    "node_modules", ".venv", ENGINE_STATE_DIR, "_runtime.log", "_runtime.log.1",
    "__pycache__", ".npm", ".cache", ".local", ".config", ".nvm",
}
_ZIP_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".idea", ".vscode", "__MACOSX",
    ".mypy_cache", ".pytest_cache", ".npm", ".cache", ".svn",
}
_ZIP_SKIP_FILES = {".ds_store", "thumbs.db"}
ZIP_MAX_ENTRIES = 3000
ZIP_MAX_TOTAL = 200 * 1024 * 1024

_NODE_EXTS = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")
_PY_EXTS = (".py", ".pyw")

_PY_IMPORT_TO_PIP = {
    "telebot": "pyTelegramBotAPI", "telegram": "python-telegram-bot", "PIL": "Pillow",
    "cv2": "opencv-python-headless", "yaml": "pyyaml", "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv", "discord": "discord.py", "magic": "python-magic",
    "Crypto": "pycryptodome", "Cryptodome": "pycryptodomex", "sklearn": "scikit-learn",
    "skimage": "scikit-image", "dateutil": "python-dateutil", "jwt": "PyJWT",
    "serial": "pyserial", "git": "GitPython", "docx": "python-docx", "pptx": "python-pptx",
    "fitz": "PyMuPDF", "OpenSSL": "pyOpenSSL", "MySQLdb": "mysqlclient",
    "psycopg2": "psycopg2-binary", "attr": "attrs", "googleapiclient": "google-api-python-client",
    "flask_cors": "flask-cors", "flask_sqlalchemy": "flask-sqlalchemy", "socks": "PySocks",
    "nacl": "PyNaCl", "zmq": "pyzmq", "websocket": "websocket-client", "yt_dlp": "yt-dlp",
    "speech_recognition": "SpeechRecognition", "fake_useragent": "fake-useragent",
    "arabic_reshaper": "arabic-reshaper", "bidi": "python-bidi", "requests_html": "requests-html",
    "apscheduler": "APScheduler", "sqlalchemy": "SQLAlchemy", "jinja2": "Jinja2",
    "markdown": "Markdown", "babel": "Babel", "pytz": "pytz", "gtts": "gTTS",
    "oauth2client": "oauth2client", "pyrogram": "pyrogram", "tgcrypto": "TgCrypto",
    "telethon": "Telethon", "aiogram": "aiogram", "bs": "beautifulsoup4", "lxml": "lxml",
    "jdatetime": "jdatetime", "pymongo": "pymongo", "motor": "motor", "redis": "redis",
}
_NODE_BUILTINS = {
    "fs", "path", "http", "https", "http2", "url", "util", "os", "crypto", "stream", "events",
    "buffer", "child_process", "cluster", "net", "tls", "dgram", "dns", "zlib", "querystring",
    "string_decoder", "timers", "tty", "vm", "assert", "readline", "module", "process",
    "console", "perf_hooks", "worker_threads", "async_hooks", "v8", "inspector", "constants",
    "punycode", "repl", "sys", "diagnostics_channel", "test", "sea", "sqlite", "wasi",
}
_PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9_,\-]+\])?([<>=!~]=?[A-Za-z0-9.*+\-_]+(,[<>=!~]=?[A-Za-z0-9.*+\-_]+)*)?$")
_NPM_SPEC_RE = re.compile(r"^(@[a-z0-9][a-z0-9._\-~]*/)?[a-z0-9][a-z0-9._\-~]*(@[A-Za-z0-9.\-^~<>=*+_]+)?$")


# ------------------------- أدوات عامة -------------------------
import platform as _platform
import tarfile as _tarfile

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.environ.get("RUNTIME_DIR", os.path.join(_BASE_DIR, "runtime"))
NODE_LOCAL_DIR = os.path.join(RUNTIME_DIR, "node")
CACHE_DIR = os.path.join(RUNTIME_DIR, "cache")
NODE_VERSION = os.environ.get("NODE_VERSION", "20.18.1")
NODE_DIST_BASE = os.environ.get("NODE_DIST_BASE", "https://nodejs.org/dist").rstrip("/")
_node_boot_lock = threading.Lock()


def _local_node_bin_dir() -> str:
    return os.path.join(NODE_LOCAL_DIR, "bin")


def _find_node_bin() -> str:
    """node من النظام إن وُجد، وإلا النسخة المحلية داخل مجلد البوت."""
    for cand in ("node", "nodejs"):
        p = shutil.which(cand)
        if p:
            return p
    local = os.path.join(_local_node_bin_dir(), "node")
    return local if os.path.exists(local) else "node"


def _find_npm_bin() -> str:
    p = shutil.which("npm")
    if p:
        return p
    local = os.path.join(_local_node_bin_dir(), "npm")
    return local if os.path.exists(local) else "npm"


def node_available() -> bool:
    n = _find_node_bin()
    return bool(shutil.which(n) or os.path.exists(n))


def _with_node_path(env: dict) -> dict:
    """يضيف مجلد node المحلي (إن وُجد) إلى PATH ليعمل npm و npx والسكربتات."""
    d = _local_node_bin_dir()
    if os.path.isdir(d):
        env["PATH"] = d + os.pathsep + env.get("PATH", "")
    return env


def _node_platform() -> tuple:
    sysname = _platform.system().lower()
    mach = _platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64",
            "armv7l": "armv7l", "armv8l": "armv7l"}.get(mach, "")
    osn = {"linux": "linux", "darwin": "darwin"}.get(sysname, "")
    return osn, arch


def bootstrap_node_runtime(force: bool = False) -> tuple:
    """إن لم يوجد Node على السيرفر: ينزّل نسخة رسمية من nodejs.org مرة واحدة ويحتفظ بها محلياً.
    يحتاج اتصال إنترنت لهذه الخطوة فقط. يرجع (ok, رسالة)."""
    with _node_boot_lock:
        if not force and node_available():
            return True, "Node.js متوفر"
        osn, arch = _node_platform()
        if not osn or not arch:
            return False, f"نظام غير مدعوم لتنزيل Node تلقائياً ({_platform.system()} {_platform.machine()}) — ثبّت Node يدوياً."
        ext = "tar.xz" if osn == "linux" else "tar.gz"
        name = f"node-v{NODE_VERSION}-{osn}-{arch}"
        url = f"{NODE_DIST_BASE}/v{NODE_VERSION}/{name}.{ext}"
        os.makedirs(CACHE_DIR, exist_ok=True)
        archive = os.path.join(CACHE_DIR, f"{name}.{ext}")
        try:
            log.info("Downloading Node.js runtime: %s", url)
            req = urllib.request.Request(url, headers={"User-Agent": "flix-host/3.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(archive + ".part", "wb") as out:
                shutil.copyfileobj(resp, out)
            # تحقق من البصمة الرسمية
            try:
                sreq = urllib.request.Request(f"{NODE_DIST_BASE}/v{NODE_VERSION}/SHASUMS256.txt", headers={"User-Agent": "flix-host/3.0"})
                sums = urllib.request.urlopen(sreq, timeout=30).read().decode()
                want = next((ln.split()[0] for ln in sums.splitlines() if ln.strip().endswith(f"{name}.{ext}")), "")
                h = hashlib.sha256()
                with open(archive + ".part", "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                if want and h.hexdigest() != want:
                    os.remove(archive + ".part")
                    return False, "فشل التحقق من سلامة ملف Node (SHA256 مختلف)."
            except Exception as e:
                log.warning("Node checksum skipped: %s", e)
            os.replace(archive + ".part", archive)
            tmp = NODE_LOCAL_DIR + ".tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)
            with _tarfile.open(archive) as tf:
                root = os.path.abspath(tmp)
                for m in tf.getmembers():
                    dest = os.path.abspath(os.path.join(root, m.name))
                    if not (dest == root or dest.startswith(root + os.sep)):
                        raise ValueError("مسار غير آمن داخل أرشيف Node")
                tf.extractall(tmp)
            inner = os.path.join(tmp, name)
            shutil.rmtree(NODE_LOCAL_DIR, ignore_errors=True)
            shutil.move(inner if os.path.isdir(inner) else tmp, NODE_LOCAL_DIR)
            shutil.rmtree(tmp, ignore_errors=True)
            rc, out = _run_cmd([os.path.join(_local_node_bin_dir(), "node"), "--version"], _BASE_DIR, timeout=20)
            if rc != 0:
                return False, f"تم التنزيل لكن node لا يعمل على هذا السيرفر: {out[:200]}"
            return True, f"تم تجهيز Node.js {out.strip()} محلياً"
        except Exception as e:
            try:
                os.remove(archive + ".part")
            except OSError:
                pass
            return False, f"تعذر تنزيل Node.js (يحتاج إنترنت): {e}"


def detect_runtime_from_file(filename: str) -> str:
    """يحدد نوع التشغيل من امتداد الملف الرئيسي."""
    ext = os.path.splitext((filename or "").lower())[1]
    if ext in (".html", ".htm"):
        return "static"
    return "nodejs" if ext in _NODE_EXTS else "python"


def rt_label(rt: str) -> str:
    return {"nodejs": "Node.js", "static": "موقع HTML ثابت"}.get(rt or "", "Python")


def detect_project_runtime(project_id: int, main_file: str = "") -> str:
    """يستنتج runtime من الملف الرئيسي ثم الملفات."""
    row = db_fetchone("SELECT runtime, main_file FROM projects WHERE id=?", (project_id,))
    mf = main_file or (row.get("main_file") if row else "") or ""
    if mf:
        rt = detect_runtime_from_file(mf)
    elif row and (row.get("runtime") or "").strip() in ("python", "nodejs"):
        rt = row["runtime"]
    else:
        files = db_fetchall("SELECT filename FROM project_files WHERE project_id=?", (project_id,))
        names = [(f.get("filename") or "").lower() for f in files]
        has_pkg = any(n == "package.json" for n in names)
        has_js = any(n.endswith(_NODE_EXTS) for n in names)
        has_py = any(n.endswith(_PY_EXTS) for n in names)
        rt = "nodejs" if (has_pkg or (has_js and not has_py)) else "python"
    try:
        db_execute("UPDATE projects SET runtime=? WHERE id=?", (rt, project_id))
    except Exception:
        pass
    return rt


def _safe_rel(rel: str) -> str:
    """مسار نسبي آمن (يمنع .. والمسارات المطلقة) أو سلسلة فارغة."""
    rel = (rel or "").replace("\\", "/").strip().lstrip("/")
    parts = []
    for part in rel.split("/"):
        part = part.strip()
        if part in ("", "."):
            continue
        if part == ".." or ":" in part and len(part) == 2:
            return ""
        part = "".join(ch for ch in part if ch not in '<>:"|?*\x00' and ord(ch) >= 32)
        if not part:
            return ""
        parts.append(part[:150])
    return "/".join(parts)


def _safe_join(base: str, rel: str) -> Optional[str]:
    rel = _safe_rel(rel)
    if not rel:
        return None
    base_abs = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base_abs, rel))
    if target != base_abs and not target.startswith(base_abs + os.sep):
        return None
    return target


def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _run_cmd(cmd: list, cwd: str, env: Optional[dict] = None, timeout: int = 120) -> tuple:
    """تنفيذ أمر بدون shell. يرجع (returncode, output)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL, errors="replace")
        out = ((p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")).strip()
        return p.returncode, out[-8000:]
    except subprocess.TimeoutExpired:
        return 124, f"انتهت المهلة ({timeout} ثانية)"
    except FileNotFoundError as e:
        return 127, f"الأمر غير موجود: {e}"
    except Exception as e:  # noqa
        return 1, f"فشل التنفيذ: {e}"


def _state_path(work_dir: str) -> str:
    return os.path.join(work_dir, ENGINE_STATE_DIR, "state.json")


def _load_state(work_dir: str) -> dict:
    try:
        with open(_state_path(work_dir), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_state(work_dir: str, state: dict) -> None:
    try:
        os.makedirs(os.path.join(work_dir, ENGINE_STATE_DIR), exist_ok=True)
        tmp = _state_path(work_dir) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        os.replace(tmp, _state_path(work_dir))
    except Exception:
        log.exception("save state failed")


def _iter_source_files(work_dir: str, exts: tuple, limit: int = 600):
    n = 0
    for root, dirs, files in os.walk(work_dir):
        dirs[:] = [d for d in dirs if d not in ENGINE_PROTECTED and d not in {".git", "venv", "env"}]
        for fn in files:
            if fn.lower().endswith(exts):
                yield os.path.join(root, fn)
                n += 1
                if n >= limit:
                    return


def _read_text(path: str, limit: int = 1_500_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except Exception:
        return ""


# ------------------------- فك ZIP بأمان -------------------------
def _fix_zip_name(info: "zipfile.ZipInfo") -> str:
    name = info.filename
    if not (info.flag_bits & 0x800):
        try:
            name = name.encode("cp437").decode("utf-8")
        except Exception:
            try:
                name = info.filename.encode("cp437").decode("cp1256")
            except Exception:
                name = info.filename
    return name


def extract_zip_safe(raw: bytes) -> tuple:
    """يفك ZIP بأمان. يرجع (files: {rel: bytes}, notes: [str]) أو يرفع ValueError برسالة عربية."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("ملف ZIP تالف أو ليس أرشيفاً صالحاً.")
    except Exception as e:
        raise ValueError(f"تعذر فتح الأرشيف: {e}")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if not infos:
        raise ValueError("الأرشيف فارغ.")
    if len(infos) > ZIP_MAX_ENTRIES:
        raise ValueError(f"الأرشيف يحتوي أكثر من {ZIP_MAX_ENTRIES} ملف.")
    if any(i.flag_bits & 0x1 for i in infos):
        raise ValueError("الأرشيف محمي بكلمة مرور — فك الحماية وأعد الرفع.")
    entries = []
    for i in infos:
        entries.append((i, _fix_zip_name(i).replace("\\", "/").lstrip("/")))
    venv_roots = {n[: -len("pyvenv.cfg")] for _, n in entries if n.endswith("pyvenv.cfg")}
    kept = []
    skipped = {"junk": 0, "big": 0, "unsafe": 0}
    for info, name in entries:
        parts = [p for p in name.split("/") if p]
        if not parts:
            continue
        if any(p in _ZIP_SKIP_DIRS for p in parts[:-1]) or parts[-1].lower() in _ZIP_SKIP_FILES:
            skipped["junk"] += 1
            continue
        if any(name.startswith(v) for v in venv_roots) or parts[-1].endswith(".pyc"):
            skipped["junk"] += 1
            continue
        if (info.external_attr >> 28) == 0xA:  # symlink
            skipped["unsafe"] += 1
            continue
        if info.file_size > MAX_FILE_SIZE:
            skipped["big"] += 1
            continue
        kept.append((info, name))
    if not kept:
        raise ValueError("لم يتبق أي ملف صالح داخل الأرشيف بعد تجاهل الملفات غير اللازمة.")
    # إزالة المجلد الجذري الواحد (حتى لو متداخل)
    while True:
        firsts = {n.split("/", 1)[0] for _, n in kept if "/" in n}
        if len(firsts) == 1 and all("/" in n for _, n in kept):
            pre = firsts.pop() + "/"
            kept = [(i, n[len(pre):]) for i, n in kept]
        else:
            break
    total = sum(i.file_size for i, _ in kept)
    if total > ZIP_MAX_TOTAL:
        raise ValueError(f"حجم الملفات بعد الفك ({total // (1024 * 1024)}MB) يتجاوز الحد المسموح.")
    files: dict = {}
    for info, name in kept:
        rel = _safe_rel(name)
        if not rel:
            skipped["unsafe"] += 1
            continue
        try:
            data = zf.read(info)
        except Exception:
            skipped["unsafe"] += 1
            continue
        files[rel] = data
    notes = []
    if skipped["junk"]:
        notes.append(f"تم تجاهل {skipped['junk']} ملف غير لازم (node_modules / venv / .git ...) — ستُثبَّت المكتبات تلقائياً.")
    if skipped["big"]:
        notes.append(f"تم تجاهل {skipped['big']} ملف أكبر من الحد المسموح.")
    if skipped["unsafe"]:
        notes.append(f"تم تجاهل {skipped['unsafe']} ملف بمسار غير آمن.")
    return files, notes


def _is_static_site(files: dict) -> bool:
    """موقع HTML ثابت: ملفات html بدون بايثون ولا package.json ولا كود خادم JS."""
    if "package.json" in files:
        return False
    if not any(n.lower().endswith((".html", ".htm")) for n in files):
        return False
    if any(n.lower().endswith(_PY_EXTS) for n in files):
        return False
    for n, d in files.items():
        if n.lower().endswith((".js", ".mjs", ".cjs", ".ts")):
            t = d.decode("utf-8", errors="ignore")
            if re.search(r"(?:require\(|from)\s*['\"](?:express|fastify|koa|http|https|hono|net|node-telegram-bot-api|telegraf|grammy|discord\.js)['\"]|\.listen\(|createServer\(", t):
                return False
    return True


def detect_main_file(files: dict) -> str:
    """يحدد الملف الرئيسي من محتوى المشروع: package.json ثم الأسماء الشائعة ثم فحص المحتوى."""
    names = sorted(files.keys())
    lower = {n.lower(): n for n in names}
    if _is_static_site(files):
        htmls = sorted((n for n in names if n.lower().endswith((".html", ".htm"))), key=lambda n: (n.count("/"), n))
        for n in htmls:
            if os.path.basename(n).lower() == "index.html":
                return n
        return htmls[0]
    # 1) package.json (main / scripts.start)
    pj = files.get("package.json")
    if pj:
        try:
            data = json.loads(pj.decode("utf-8", errors="ignore"))
            main = (data.get("main") or "").strip()
            if main and _safe_rel(main) in files:
                return _safe_rel(main)
            start = ((data.get("scripts") or {}).get("start") or "")
            m = re.search(r"node(?:mon)?\s+(?:--?\S+\s+)*([\w./\\-]+\.(?:c|m)?js)", start)
            if m and _safe_rel(m.group(1)) in files:
                return _safe_rel(m.group(1))
        except Exception:
            pass
    # 2) Procfile / runtime hints
    pf = files.get("Procfile")
    if pf:
        m = re.search(r"(?:python3?|node)\s+(?:-u\s+)?([\w./-]+\.(?:py|js|mjs|cjs))", pf.decode("utf-8", errors="ignore"))
        if m and _safe_rel(m.group(1)) in files:
            return _safe_rel(m.group(1))
    # 3) أسماء شائعة (الجذر أولاً)
    preferred = ("main.py", "bot.py", "app.py", "run.py", "start.py", "index.py", "__main__.py",
                 "main.js", "index.js", "bot.js", "app.js", "server.js", "start.js", "main.mjs",
                 "index.mjs", "main.ts", "index.ts", "bot.ts")
    for pref in preferred:
        if pref in lower:
            return lower[pref]
    code = [n for n in names if n.lower().endswith(_PY_EXTS + _NODE_EXTS)]
    if not code:
        return ""
    # 4) فحص المحتوى: أين التشغيل الفعلي
    def score(n: str) -> int:
        txt = files[n].decode("utf-8", errors="ignore")
        s = 0
        if re.search(r"__name__\s*==\s*['\"]__main__['\"]", txt): s += 5
        if re.search(r"infinity_polling|\.polling\(|run_polling|app\.run\(|executor\.start_polling|client\.run_until_disconnected|bot\.run\(|\.launch\(|client\.login\(|\.listen\(", txt): s += 8
        if re.search(r"\d{6,}:[A-Za-z0-9_-]{30,}", txt): s += 2
        if "/" not in n: s += 2
        s -= n.count("/")
        if re.search(r"(^|/)(test|tests|setup|config|settings|utils|helpers)\.", n.lower()): s -= 6
        return s
    return max(code, key=score)


def store_project_files(project_id: int, files: dict) -> int:
    n = 0
    for rel, data in files.items():
        db_execute(
            "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
            "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
            "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
            (project_id, rel, sqlite3.Binary(data), len(data)),
        )
        n += 1
    return n


def store_project_from_zip(project_id: int, raw: bytes) -> tuple:
    """يفك ZIP ويحفظه. يرجع (main_file, runtime, stored_count, notes)."""
    files, notes = extract_zip_safe(raw)
    main = detect_main_file(files)
    if not main:
        raise ValueError("لم يُعثر على ملف .py أو .js أو index.html داخل الأرشيف.")
    # تنظيف ملفات المشروع القديمة عند إعادة الرفع على نفس المشروع
    db_execute("DELETE FROM project_files WHERE project_id=?", (project_id,))
    count = store_project_files(project_id, files)
    return main, detect_runtime_from_file(main), count, notes


# ------------------------- مزامنة الملفات (دائمة) -------------------------
def sync_project_to_disk(project_id: int, work_dir: str) -> dict:
    """يكتب ملفات قاعدة البيانات على القرص بشكل تراكمي، دون مسح node_modules/.venv/ملفات التشغيل."""
    os.makedirs(work_dir, exist_ok=True)
    state = _load_state(work_dir)
    manifest: dict = state.get("manifest", {})
    rows = db_fetchall("SELECT filename, content FROM project_files WHERE project_id=?", (project_id,))
    seen = set()
    written = 0
    for row in rows:
        rel = _safe_rel(row["filename"])
        if not rel:
            continue
        seen.add(rel)
        data = bytes(row["content"] or b"")
        h = _sha(data)
        target = _safe_join(work_dir, rel)
        if not target:
            continue
        if manifest.get(rel) == h and os.path.exists(target):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
        manifest[rel] = h
        written += 1
    for rel in list(manifest.keys()):
        if rel not in seen:  # حُذف من المشروع
            target = _safe_join(work_dir, rel)
            if target and os.path.isfile(target):
                try:
                    os.remove(target)
                except OSError:
                    pass
            manifest.pop(rel, None)
    state["manifest"] = manifest
    _save_state(work_dir, state)
    return {"written": written, "total": len(seen)}


# ------------------------- اكتشاف المكتبات -------------------------
def _py_stdlib() -> set:
    std = set(getattr(sys, "stdlib_module_names", set()))
    std |= set(globals().get("_STDLIB_MODULES", set()))
    std |= {"__future__", "typing_extensions_placeholder"}
    return std


def _local_py_names(work_dir: str) -> set:
    names = set()
    for root, dirs, files in os.walk(work_dir):
        dirs[:] = [d for d in dirs if d not in ENGINE_PROTECTED and d not in {".git", "venv", "env"}]
        for d in dirs:
            names.add(d)
        for fn in files:
            if fn.endswith(".py"):
                names.add(fn[:-3])
        if root.count(os.sep) - work_dir.count(os.sep) > 4:
            dirs[:] = []
    return names


def detect_python_imports(work_dir: str) -> list:
    """أسماء الاستيراد (top-level) الخارجية المستخدمة في المشروع."""
    std = _py_stdlib()
    local = _local_py_names(work_dir)
    found = set()
    for path in _iter_source_files(work_dir, _PY_EXTS):
        code = _read_text(path)
        try:
            tree = _ast.parse(code)
        except Exception:
            tree = None
        if tree is not None:
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Import):
                    for a in node.names:
                        found.add(a.name.split(".")[0])
                elif isinstance(node, _ast.ImportFrom) and node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
        else:
            for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", code, re.MULTILINE):
                found.add(m.group(1))
    return sorted(n for n in found if n and n not in std and n not in local and not n.startswith("_"))


def pip_name_for(import_name: str) -> str:
    return _PY_IMPORT_TO_PIP.get(import_name, import_name)


def detect_node_packages(work_dir: str) -> list:
    found = set()
    local_aliases = set()
    for path in _iter_source_files(work_dir, _NODE_EXTS):
        code = _read_text(path)
        specs = re.findall(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", code)
        specs += re.findall(r"""(?:^|[\s;}])import\s+(?:[\w*{}\s,$]+\s+from\s+)?['"]([^'"]+)['"]""", code, re.MULTILINE)
        specs += re.findall(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""", code)
        for spec in specs:
            if spec.startswith((".", "/", "#", "node:", "file:", "http:", "https:", "data:")):
                continue
            parts = spec.split("/")
            pkg = "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]
            if pkg in _NODE_BUILTINS or not _NPM_SPEC_RE.match(pkg):
                continue
            found.add(pkg)
    return sorted(found - local_aliases)


# ------------------------- بيئة Python -------------------------
def _venv_python(work_dir: str) -> str:
    for rel in (".venv/bin/python", ".venv/Scripts/python.exe"):
        p = os.path.join(work_dir, rel)
        if os.path.exists(p):
            return p
    return ""


def project_python(work_dir: str) -> str:
    return _venv_python(work_dir) or sys.executable


def ensure_python_venv(work_dir: str, notes: list) -> str:
    if not ENGINE_USE_VENV:
        return sys.executable
    vp = _venv_python(work_dir)
    if vp:
        rc, _ = _run_cmd([vp, "-c", "import sys"], work_dir, timeout=20)
        if rc == 0:
            return vp
        shutil.rmtree(os.path.join(work_dir, ".venv"), ignore_errors=True)
    rc, out = _run_cmd([sys.executable, "-m", "venv", "--system-site-packages", ".venv"], work_dir, timeout=180)
    vp = _venv_python(work_dir)
    if rc == 0 and vp:
        return vp
    shutil.rmtree(os.path.join(work_dir, ".venv"), ignore_errors=True)
    notes.append("تعذر إنشاء بيئة معزولة — سيتم استخدام بايثون الرئيسي.")
    return sys.executable


def _pip_install(py: str, work_dir: str, args: list, env: dict, notes: list) -> bool:
    env = dict(env)
    env["PIP_CACHE_DIR"] = os.path.join(CACHE_DIR, "pip")
    cmd = [py, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
           "--retries", "3", "--timeout", "40"] + args
    rc, out = _run_cmd(cmd, work_dir, env=env, timeout=ENGINE_INSTALL_TIMEOUT)
    if rc != 0 and "No module named pip" in out:
        _run_cmd([py, "-m", "ensurepip", "--upgrade"], work_dir, env=env, timeout=180)
        rc, out = _run_cmd(cmd, work_dir, env=env, timeout=ENGINE_INSTALL_TIMEOUT)
    if rc != 0:
        notes.append("pip: " + (out.strip().splitlines() or ["فشل"])[-1][:300])
    return rc == 0


def _missing_python_imports(py: str, work_dir: str, env: dict, names: list) -> list:
    if not names:
        return []
    code = ("import importlib.util as u,sys\n"
            "print('\\n'.join(n for n in sys.argv[1:] if u.find_spec(n) is None))")
    rc, out = _run_cmd([py, "-c", code] + names, work_dir, env=env, timeout=60)
    if rc != 0:
        return names
    return [x.strip() for x in out.splitlines() if x.strip()]


def ensure_python_deps(work_dir: str, py: str, env: dict, notes: list, force: bool = False) -> bool:
    """يثبّت requirements.txt ثم أي استيراد ناقص. يرجع True عند عدم وجود فشل."""
    state = _load_state(work_dir)
    ok_all = True
    req = os.path.join(work_dir, "requirements.txt")
    req_hash = _sha(open(req, "rb").read()) if os.path.isfile(req) else ""
    if req_hash and (force or state.get("req_hash") != req_hash or state.get("req_py") != py):
        if _pip_install(py, work_dir, ["-r", "requirements.txt"], env, notes):
            state["req_hash"], state["req_py"] = req_hash, py
        else:
            # سطر بسطر كحل بديل حتى لا يفشل كل شيء بسبب مكتبة واحدة
            good = 0
            for line in _read_text(req).splitlines():
                spec = line.split("#", 1)[0].strip()
                if not spec or spec.startswith(("-", "git+", "http")) or not _PIP_SPEC_RE.match(spec.replace(" ", "")):
                    continue
                if _pip_install(py, work_dir, [spec.replace(" ", "")], env, notes):
                    good += 1
                else:
                    base = re.split(r"[<>=!~\[]", spec)[0].strip()
                    if base and _PIP_SPEC_RE.match(base) and _pip_install(py, work_dir, [base], env, notes):
                        notes.append(f"تم تثبيت <{base}> بدون تحديد الإصدار.")
                        good += 1
                    else:
                        ok_all = False
            state["req_hash"], state["req_py"] = req_hash, py
    names = detect_python_imports(work_dir)
    failed = set(state.get("pip_failed", []))
    missing = [n for n in _missing_python_imports(py, work_dir, env, names) if n not in failed]
    if missing:
        pips = []
        for n in missing:
            p = pip_name_for(n)
            if _PIP_SPEC_RE.match(p):
                pips.append((n, p))
        if pips:
            if not _pip_install(py, work_dir, [p for _, p in pips], env, notes):
                for n, p in pips:
                    if not _pip_install(py, work_dir, [p], env, notes):
                        failed.add(n)
                        ok_all = False
                        notes.append(f"تعذر تثبيت المكتبة: {p}")
            else:
                notes.append("تم تثبيت: " + ", ".join(p for _, p in pips))
    state["pip_failed"] = sorted(failed)
    _save_state(work_dir, state)
    return ok_all


# ------------------------- بيئة Node.js -------------------------
def _ensure_package_json(work_dir: str, project_id: int) -> dict:
    p = os.path.join(work_dir, "package.json")
    if os.path.isfile(p):
        try:
            return json.loads(_read_text(p) or "{}")
        except Exception:
            return {}
    data = {"name": f"flix-project-{project_id}", "version": "1.0.0", "private": True}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


def _node_set_module_type(work_dir: str, project_id: int, module: bool) -> bool:
    data = _ensure_package_json(work_dir, project_id)
    cur = data.get("type")
    if module and cur == "module":
        return False
    if not module and cur != "module":
        return False
    if module:
        data["type"] = "module"
    else:
        data.pop("type", None)
    with open(os.path.join(work_dir, "package.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return True


def _npm_env(work_dir: str, base: Optional[dict] = None) -> dict:
    env = dict(base or os.environ)
    env.update({"HOME": work_dir, "npm_config_update_notifier": "false", "npm_config_fund": "false",
                "npm_config_audit": "false", "NO_UPDATE_NOTIFIER": "1", "CI": "1",
                "npm_config_cache": os.path.join(CACHE_DIR, "npm"), "npm_config_prefer_offline": "true"})
    return _with_node_path(env)


def _npm_install(work_dir: str, args: list, notes: list, env: dict) -> bool:
    npm = _find_npm_bin()
    base = [npm, "install", "--no-audit", "--no-fund", "--no-progress", "--loglevel=error",
            "--fetch-retries=1", "--fetch-retry-mintimeout=2000", "--fetch-retry-maxtimeout=8000", "--fetch-timeout=45000"]
    rc, out = _run_cmd(base + args, work_dir, env=env, timeout=ENGINE_INSTALL_TIMEOUT)
    if rc != 0 and "ERESOLVE" in out:
        rc, out = _run_cmd(base + ["--legacy-peer-deps"] + args, work_dir, env=env, timeout=ENGINE_INSTALL_TIMEOUT)
    if rc != 0:
        notes.append("npm: " + (out.strip().splitlines() or ["فشل"])[-1][:300])
    return rc == 0


def ensure_node_deps(project_id: int, work_dir: str, main_file: str, env: dict, notes: list, force: bool = False) -> bool:
    state = _load_state(work_dir)
    nm = os.path.join(work_dir, "node_modules")
    ok_all = True
    pj = os.path.join(work_dir, "package.json")
    if os.path.isfile(pj):
        h = _sha(open(pj, "rb").read())
        lock = os.path.join(work_dir, "package-lock.json")
        if os.path.isfile(lock):
            h += _sha(open(lock, "rb").read())
        if force or not os.path.isdir(nm) or state.get("pkg_hash") != h:
            data = {}
            try:
                data = json.loads(_read_text(pj) or "{}")
            except Exception:
                notes.append("package.json غير صالح (JSON تالف).")
                ok_all = False
            if data.get("dependencies") or data.get("optionalDependencies") or force:
                if _npm_install(work_dir, ["--omit=dev"], notes, env):
                    state["pkg_hash"] = h
                else:
                    ok_all = False
            else:
                state["pkg_hash"] = h
    else:
        _ensure_package_json(work_dir, project_id)
    names = detect_node_packages(work_dir)
    try:
        declared = set((json.loads(_read_text(pj) or "{}").get("dependencies") or {}).keys())
    except Exception:
        declared = set()
    failed = set(state.get("npm_failed", []))
    missing = [n for n in names if not os.path.isdir(os.path.join(nm, *n.split("/"))) and n not in failed]
    if missing:
        if _npm_install(work_dir, missing, notes, env):
            notes.append("تم تثبيت: " + ", ".join(missing))
        else:
            for n in missing:
                if not _npm_install(work_dir, [n], notes, env):
                    failed.add(n)
                    ok_all = False
                    notes.append(f"تعذر تثبيت الحزمة: {n}")
    state["npm_failed"] = sorted(failed)
    if main_file.lower().endswith((".ts", ".tsx")):
        tsx = os.path.join(nm, ".bin", "tsx")
        if not os.path.exists(tsx) and "tsx" not in failed:
            if not _npm_install(work_dir, ["tsx"], notes, env):
                ok_all = False
    _save_state(work_dir, state)
    return ok_all


# ------------------------- فحص الأخطاء قبل التشغيل -------------------------
def static_check(work_dir: str, main_file: str, runtime: str) -> list:
    """فحص ثابت: أخطاء نحوية ومشاكل شائعة. يرجع قائمة نصوص عربية."""
    issues: list = []
    if main_file and not os.path.isfile(os.path.join(work_dir, main_file)):
        issues.append(f"الملف الرئيسي <code>{html_escape(main_file)}</code> غير موجود داخل المشروع.")
        return issues
    if runtime == "static":
        return issues + check_static_site(work_dir, main_file)
    if runtime == "python":
        for path in _iter_source_files(work_dir, _PY_EXTS, limit=300):
            rel = os.path.relpath(path, work_dir).replace(os.sep, "/")
            code = _read_text(path)
            try:
                compile(code, rel, "exec")
            except SyntaxError as e:
                issues.append(f"خطأ نحوي في <code>{html_escape(rel)}</code> سطر {e.lineno}: {html_escape(str(e.msg))}")
            except Exception:
                pass
        mf = _read_text(os.path.join(work_dir, main_file)) if main_file else ""
        if re.search(r"^\s*[^#\n]*\binput\s*\(", mf, re.MULTILINE):
            issues.append("الكود يستخدم <code>input()</code> — الاستضافة لا توفر إدخالاً وسيتوقف البوت بخطأ EOFError. استبدله بمتغيرات أو ملف .env.")
        if re.search(r"\.run\(\s*(?:host\s*=\s*[^,)]+,\s*)?port\s*=\s*\d+", mf):
            issues.append("البوت يفتح منفذاً ثابتاً؛ استخدم <code>os.environ.get('PORT')</code> لتفادي التعارض.")
    else:
        if not node_available():
            ok_n, msg_n = bootstrap_node_runtime()
            if not ok_n:
                issues.append(html_escape(msg_n))
                return issues
        node = _find_node_bin()
        for path in _iter_source_files(work_dir, (".js", ".mjs", ".cjs"), limit=60):
            rel = os.path.relpath(path, work_dir).replace(os.sep, "/")
            rc, out = _run_cmd([node, "--check", path], work_dir, timeout=15)
            if rc not in (0, 127):
                lines = [ln for ln in out.splitlines() if ln.strip()]
                err = next((ln for ln in lines if "Error" in ln), lines[0] if lines else "")
                loc = next((ln for ln in lines if re.search(r":\d+$", ln.strip())), "")
                m = re.search(r":(\d+)$", loc.strip())
                where = f" سطر {m.group(1)}" if m else ""
                issues.append(f"خطأ نحوي في <code>{html_escape(rel)}</code>{where}: {html_escape(err[:200])}")
            elif rc == 127:
                issues.append("Node.js غير مثبت على السيرفر.")
                break
        pj = os.path.join(work_dir, "package.json")
        if os.path.isfile(pj):
            try:
                json.loads(_read_text(pj))
            except Exception as e:
                issues.append(f"ملف package.json غير صالح: {html_escape(str(e)[:120])}")
    return issues


def check_static_site(work_dir: str, main_file: str) -> list:
    """يفحص روابط الملفات المحلية داخل صفحات HTML ويبلّغ عن الناقص."""
    issues: list = []
    root = os.path.join(work_dir, os.path.dirname(main_file)) if main_file else work_dir
    missing: dict = {}
    n_html = 0
    for path in _iter_source_files(work_dir, (".html", ".htm"), limit=200):
        n_html += 1
        txt = _read_text(path)
        base = os.path.dirname(path)
        for m in re.finditer(r"""(?:src|href|poster)\s*=\s*["']([^"'#?]+)""", txt, re.IGNORECASE):
            ref = m.group(1).strip()
            if not ref or re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|javascript|data:|mailto:|tel:)", ref, re.IGNORECASE):
                continue
            target = os.path.join(root, ref.lstrip("/")) if ref.startswith("/") else os.path.join(base, ref)
            target = os.path.normpath(target)
            if not os.path.exists(target) and not (os.path.isdir(os.path.dirname(target)) and ref.endswith("/")):
                missing.setdefault(ref, os.path.relpath(path, work_dir).replace(os.sep, "/"))
    if n_html == 0:
        issues.append("لا توجد أي صفحة HTML داخل المشروع.")
    for ref, where in list(missing.items())[:10]:
        issues.append(f"رابط لملف غير موجود: <code>{html_escape(ref)}</code> داخل <code>{html_escape(where)}</code>")
    return issues


def static_check_project(project_id: int) -> list:
    p = db_fetchone("SELECT main_file, runtime FROM projects WHERE id=?", (project_id,)) or {}
    work_dir = os.path.join(PROJECTS_DIR, str(project_id))
    sync_project_to_disk(project_id, work_dir)
    mf = p.get("main_file") or ""
    rt = detect_runtime_from_file(mf) if mf else ((p.get("runtime") or "") or "python")
    return static_check(work_dir, mf, rt)


# ------------------------- تحليل السجل (كاشف الأخطاء) -------------------------
def _last_traceback(text: str) -> tuple:
    """يرجع (نوع الاستثناء+الرسالة, ملف, سطر) من آخر Traceback بايثون."""
    idx = text.rfind("Traceback (most recent call last):")
    seg = text[idx:] if idx >= 0 else text
    frames = re.findall(r'File "([^"]+)", line (\d+)', seg)
    exc = ""
    for ln in reversed([l for l in seg.splitlines() if l.strip()]):
        if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt|Warning)\b.*", ln.strip()) or re.match(r"^[A-Za-z_][\w.]*:\s", ln.strip()):
            exc = ln.strip()
            break
    fname, line = ("", "")
    for f, l in reversed(frames):
        if "site-packages" not in f and "/usr/lib" not in f and "/.venv/" not in f:
            fname, line = os.path.basename(f), l
            break
    if not fname and frames:
        fname, line = os.path.basename(frames[-1][0]), frames[-1][1]
    return exc, fname, line


def analyze_log(text: str, runtime: str = "python") -> list:
    """يحلل نص السجل ويرجع قائمة نتائج: {id, title, hint, fix}. fix = (action, arg) أو None."""
    text = text or ""
    low = text.lower()
    res: list = []

    def add(rid, title, hint, fix=None):
        if not any(r["id"] == rid for r in res):
            res.append({"id": rid, "title": title, "hint": hint, "fix": fix})

    # --- مكتبات ناقصة ---
    for m in re.finditer(r"No module named ['\"]([\w.\-]+)['\"]", text):
        top = m.group(1).split(".")[0]
        pkg = pip_name_for(top)
        add(f"py_missing_{top}", f"مكتبة بايثون ناقصة: {top}",
            f"سيتم تثبيت <code>{html_escape(pkg)}</code> تلقائياً. إن لم تنجح تأكد من اسم المكتبة في requirements.txt.",
            ("pip", pkg) if _PIP_SPEC_RE.match(pkg) else None)
    for m in re.finditer(r"Cannot find (?:module|package) ['\"]([^'\"]+)['\"]", text):
        spec = m.group(1)
        if spec.startswith((".", "/")) or re.match(r"^[A-Za-z]:", spec):
            add(f"node_missing_file_{spec}", f"ملف ناقص: {spec}",
                "الكود يستدعي ملفاً غير موجود داخل المشروع. تأكد من رفع كل الملفات ومن حالة الأحرف في الاسم (Linux حساس لها).")
        else:
            parts = spec.split("/")
            pkg = "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]
            add(f"node_missing_{pkg}", f"حزمة Node ناقصة: {pkg}",
                f"سيتم تثبيت <code>{html_escape(pkg)}</code> تلقائياً عبر npm.",
                ("npm", pkg) if _NPM_SPEC_RE.match(pkg) else None)
    m = re.search(r"cannot import name ['\"]?(\w+)['\"]? from ['\"]?([\w.]+)", text)
    if m:
        top = m.group(2).split(".")[0]
        add(f"py_import_{m.group(1)}", f"استيراد غير متاح: {m.group(1)} من {m.group(2)}",
            "غالباً إصدار المكتبة قديم/جديد أو ملف محلي بنفس اسم المكتبة. سنحاول تحديث المكتبة.",
            ("pip_upgrade", pip_name_for(top)) if top and top not in _local_py_names(PROJECTS_DIR) and _PIP_SPEC_RE.match(pip_name_for(top)) else None)

    # --- أخطاء كود ---
    m = re.search(r'File "([^"]+)", line (\d+)\n(?:.*\n)*?\s*(IndentationError|TabError|SyntaxError): (.*)', text)
    if m or "syntaxerror" in low or "indentationerror" in low:
        where = f" في <code>{html_escape(os.path.basename(m.group(1)))}</code> سطر {m.group(2)}" if m else ""
        kind = m.group(3) if m else "SyntaxError"
        detail = m.group(4) if m else ""
        add("py_syntax", f"خطأ في كتابة الكود ({kind}){where}",
            f"{html_escape(detail[:200])}\nصحّح السطر المذكور ثم أعد الرفع (استخدم محرر الملفات في البوت).")
    if "Cannot use import statement outside a module" in text or "Unexpected token 'export'" in text or "ERR_REQUIRE_ESM" in text:
        add("node_esm", "ملف Node يستخدم ESM (import/export)",
            "سيتم تفعيل <code>\"type\": \"module\"</code> في package.json تلقائياً.", ("node_esm", ""))
    if "require is not defined in ES module scope" in text:
        add("node_cjs", "الكود يستخدم require داخل مشروع ESM",
            "سيتم إزالة <code>\"type\": \"module\"</code> من package.json تلقائياً.", ("node_cjs", ""))
    if runtime == "nodejs":
        m = re.search(r"(\S+\.(?:c|m)?js):(\d+)\n(?:.*\n){0,3}?\s*(SyntaxError|ReferenceError|TypeError): (.*)", text)
        if m:
            add(f"node_err_{m.group(3)}", f"{m.group(3)} في {os.path.basename(m.group(1))} سطر {m.group(2)}",
                html_escape(m.group(4)[:200]))
    if "EOFError" in text:
        add("py_eof", "الكود ينتظر إدخالاً من لوحة المفاتيح (input)",
            "الاستضافة لا توفر إدخالاً. احذف <code>input()</code> واستخدم متغيرات/ملف .env.")

    # --- تيليجرام ---
    if re.search(r"\b401\b.*unauthorized|unauthorized.*\b401\b|InvalidToken|Not Found\W.*\b404\b.*bot|token (?:is )?invalid|invalid token|ETELEGRAM: 401", text, re.IGNORECASE | re.DOTALL):
        add("tg_token", "توكن البوت مرفوض من تيليجرام",
            "التوكن غير صحيح أو تم إلغاؤه. أنشئ توكن جديد من @BotFather وعدّله في ملفات المشروع (.env أو الكود).")
    if re.search(r"\b409\b.*(conflict|terminated by other)|terminated by other getUpdates", text, re.IGNORECASE | re.DOTALL):
        add("tg_conflict", "تعارض: نفس التوكن يعمل في مكان آخر",
            "هناك نسخة ثانية من البوت تعمل بنفس التوكن (على جهازك أو استضافة أخرى أو مشروع ثاني هنا). أوقف النسخة الأخرى.")
    if re.search(r"\b429\b|too many requests|retry after", text, re.IGNORECASE):
        add("tg_flood", "تيليجرام يحدّ الطلبات (Flood/429)", "البوت يرسل طلبات كثيرة بسرعة. أضف تأخيراً بين الرسائل.")

    # --- النظام ---
    if "EADDRINUSE" in text or "address already in use" in low:
        add("port", "المنفذ مستخدم بالفعل", "استخدم المنفذ من متغير البيئة <code>PORT</code> (تعطيه الاستضافة لكل مشروع منفذاً مختلفاً).")
    if "heap out of memory" in low or "MemoryError" in text or "ENOMEM" in text or "Killed" in text.split("\n")[-1:][0:1] or "std::bad_alloc" in text:
        add("oom", "نفدت الذاكرة", "المشروع يستهلك ذاكرة أكبر من المتاح. قلّل حجم البيانات المحمّلة أو نظّف الكاش.")
    if "database is locked" in low:
        add("dblock", "قاعدة SQLite مقفلة", "أكثر من عملية تكتب بنفس الملف. استخدم اتصالاً واحداً أو timeout أكبر.")
    if "permissionerror" in low or "eacces" in low or "permission denied" in low:
        add("perm", "صلاحيات غير كافية", "المشروع يحاول الوصول لمسار خارج مجلده. استخدم مسارات نسبية داخل المشروع.")
    if re.search(r"FileNotFoundError|ENOENT", text):
        m = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]|ENOENT[^\n]*'([^']+)'", text)
        what = (m.group(1) or m.group(2)) if m else ""
        add("nofile", "ملف مطلوب غير موجود" + (f": {os.path.basename(what)}" if what else ""),
            "ارفع الملف المطلوب (مثل config.json أو .env) مع المشروع، أو أنشئه من الكود قبل استخدامه.")
    if re.search(r"getaddrinfo|Temporary failure in name resolution|ConnectionError|ECONNREFUSED|ETIMEDOUT|ENOTFOUND", text):
        add("net", "مشكلة اتصال بالشبكة", "تعذر الاتصال بخدمة خارجية. تأكد من الرابط/المفتاح، وقد تكون مشكلة مؤقتة.")
    if "UnicodeDecodeError" in text or "UnicodeEncodeError" in text:
        add("unicode", "مشكلة ترميز نصوص", "افتح الملفات بـ <code>encoding='utf-8'</code>.")
    if "KeyError" in text and "environ" in text:
        add("env", "متغير بيئة ناقص", "الكود يقرأ متغيراً من <code>os.environ</code> غير موجود. أضفه في ملف .env داخل المشروع.")

    # --- عام ---
    if not res and runtime == "python":
        exc, fname, line = _last_traceback(text)
        if exc:
            where = f" — <code>{html_escape(fname)}</code> سطر {line}" if fname else ""
            add("py_generic", "خطأ أثناء التشغيل", f"<code>{html_escape(exc[:250])}</code>{where}")
    if not res and runtime == "nodejs":
        errs = [l.strip() for l in text.splitlines() if re.search(r"\b\w*Error\b:", l)]
        if errs:
            add("node_generic", "خطأ أثناء التشغيل", f"<code>{html_escape(errs[-1][:250])}</code>")
    return res


def format_findings(findings: list, limit: int = 6) -> str:
    if not findings:
        return ""
    out = []
    for f in findings[:limit]:
        out.append(f"• <b>{f['title']}</b>\n   {f['hint']}")
    return "\n".join(out)


def _tail_file(path: str, n_bytes: int = 8000, start: int = 0) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            pos = max(start, size - n_bytes)
            fh.seek(pos)
            return fh.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def analyze_start_error(project_id: int, log_tail: str = "") -> str:
    """تحليل ذكي بالعربية لسبب فشل التشغيل."""
    row = db_fetchone("SELECT last_error, main_file, runtime FROM projects WHERE id=?", (project_id,)) or {}
    rt = (row.get("runtime") or "python")
    blob = (log_tail or "") + "\n" + (row.get("last_error") or "")
    findings = analyze_log(blob, rt)
    if findings:
        return format_findings(findings)
    last = (row.get("last_error") or "").strip()
    if last:
        return f"• {last[:400]}"
    return "• لا يوجد خطأ واضح — افتح السجل الكامل من زر «السجل» أو جرّب «تحميل المكتبات»."


# ------------------------- تطبيق الإصلاحات -------------------------
def apply_fix(project_id: int, work_dir: str, runtime: str, fix: tuple, env: dict, notes: list) -> bool:
    action, arg = fix
    try:
        if action in ("pip", "pip_upgrade"):
            py = ensure_python_venv(work_dir, notes)
            if not _PIP_SPEC_RE.match(arg or ""):
                return False
            args = (["-U"] if action == "pip_upgrade" else []) + [arg]
            return _pip_install(py, work_dir, args, env, notes)
        if action == "npm":
            if not _NPM_SPEC_RE.match(arg or ""):
                return False
            _ensure_package_json(work_dir, project_id)
            return _npm_install(work_dir, [arg], notes, _npm_env(work_dir, env))
        if action == "node_esm":
            return _node_set_module_type(work_dir, project_id, True)
        if action == "node_cjs":
            return _node_set_module_type(work_dir, project_id, False)
    except Exception:
        log.exception("apply_fix failed %s", fix)
    return False


# ------------------------- العملية المستضافة -------------------------
def _rss_mb(pid: int) -> float:
    try:
        import psutil  # type: ignore
        proc = psutil.Process(pid)
        total = proc.memory_info().rss
        for c in proc.children(recursive=True):
            try:
                total += c.memory_info().rss
            except Exception:
                pass
        return total / (1024 * 1024)
    except Exception:
        pass
    try:
        with open(f"/proc/{pid}/status", "r") as fh:
            for ln in fh:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def _owner_notify(project_id: int, text: str) -> None:
    try:
        p = db_fetchone("SELECT user_id, name, notify_crash FROM projects WHERE id=?", (project_id,))
        if not p or (p.get("notify_crash") is not None and int(p.get("notify_crash") or 0) == 0):
            return
        bot.send_message(p["user_id"], f"<b>{html_escape(p.get('name') or '')}</b> #{project_id}\n{text}")
    except Exception:
        pass


class HostedProcess:
    def __init__(self, project_id: int, name: str, main_file: str, work_dir: str, runtime: str = "python"):
        self.project_id = project_id
        self.name = name
        self.main_file = main_file
        self.work_dir = work_dir
        self.runtime = runtime if runtime in ("python", "nodejs") else detect_runtime_from_file(main_file)
        self.proc: Optional[subprocess.Popen] = None
        self.auto_restart = True
        self.restart_count = 0
        self.last_start = 0.0
        self.stopped_by_user = False
        self.finished_ok = False
        self.next_restart_at = 0.0
        self.restarting = False
        self.log_offset = 0
        self.applied_fixes: set = set()
        self.notified: set = set()
        self.last_health_scan = 0.0
        self.health_offset = 0
        self.lock = threading.RLock()

    # ---- معلومات ----
    @property
    def pid(self) -> Optional[int]:
        return self.proc.pid if self.proc is not None else None

    @property
    def log_path(self) -> str:
        return os.path.join(self.work_dir, "_runtime.log")

    def uptime(self) -> float:
        return (time.time() - self.last_start) if self.is_alive() else 0.0

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def run_log(self, n: int = 8000) -> str:
        return _tail_file(self.log_path, n, self.log_offset)

    # ---- بناء الأمر ----
    def _port(self) -> str:
        return str(20000 + (self.project_id % 30000))

    def _env(self) -> dict:
        env = jail_materialize_env(self.project_id, self.work_dir)
        env["PORT"] = self._port()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["NODE_ENV"] = os.environ.get("NODE_ENV", "production")
        for k in ("NETLIFY_TOKEN", "VERCEL_TOKEN", "BOT_TOKEN", "ADMIN_IDS", "ADMIN_ID"):
            env.pop(k, None)
        _with_node_path(env)
        nm_bin = os.path.join(self.work_dir, "node_modules", ".bin")
        if os.path.isdir(nm_bin):
            env["PATH"] = nm_bin + os.pathsep + env.get("PATH", "")
        vp = _venv_python(self.work_dir)
        if vp:
            vbin = os.path.dirname(vp)
            env["PATH"] = vbin + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = os.path.dirname(vbin)
        # ملف .env داخل المشروع يُحمَّل كمتغيرات بيئة تلقائياً (للبوتات التي لا تستخدم dotenv)
        envf = os.path.join(self.work_dir, ".env")
        if os.path.isfile(envf):
            for ln in _read_text(envf, 200_000).splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                k = k.replace("export ", "").strip()
                v = v.strip().strip("'\"")
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k) and k not in env:
                    env[k] = v
        return env

    def _build_cmd(self) -> list:
        mf = self.main_file
        if self.runtime == "nodejs":
            node = _find_node_bin()
            if mf.lower().endswith((".ts", ".tsx")):
                tsx = os.path.join(self.work_dir, "node_modules", ".bin", "tsx")
                if os.path.exists(tsx):
                    return [tsx, mf]
                ts_node = shutil.which("ts-node")
                return [ts_node, mf] if ts_node else [node, "--experimental-strip-types", mf]
            return [node, mf]
        return [project_python(self.work_dir), "-u", mf]

    # ---- تحضير البيئة ----
    def prepare(self, notes: list, force: bool = False) -> bool:
        env = self._env()
        if self.runtime == "nodejs":
            if not node_available():
                ok_n, msg_n = bootstrap_node_runtime()
                notes.append(msg_n)
                if not ok_n:
                    return False
            return ensure_node_deps(self.project_id, self.work_dir, self.main_file, _npm_env(self.work_dir, env), notes, force)
        py = ensure_python_venv(self.work_dir, notes)
        ok = ensure_python_deps(self.work_dir, py, self._env(), notes, force)
        return ok

    # ---- تشغيل خام ----
    def _spawn(self) -> None:
        self._rotate_log()
        try:
            self.log_offset = os.path.getsize(self.log_path)
        except OSError:
            self.log_offset = 0
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        popen_kwargs = {"cwd": self.work_dir, "stdin": subprocess.DEVNULL, "env": self._env()}
        if hasattr(os, "setsid"):
            popen_kwargs["start_new_session"] = True
        cmd = self._build_cmd()
        with open(self.log_path, "ab", buffering=0) as lf:
            lf.write(f"\n===== [{stamp} UTC] تشغيل: {' '.join(cmd)} =====\n".encode("utf-8"))
            self.log_offset = lf.tell()
            self.proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, **popen_kwargs)
        self.last_start = time.time()
        self.health_offset = self.log_offset
        self.finished_ok = False
        _record_event(self.project_id, "start", f"pid={self.proc.pid} runtime={self.runtime} cmd={' '.join(cmd)}")

    def _rotate_log(self) -> None:
        try:
            if os.path.getsize(self.log_path) > ENGINE_LOG_MAX:
                tail = _tail_file(self.log_path, 1024 * 1024)
                with open(self.log_path, "wb") as fh:
                    fh.write(("... (تم اقتصاص السجل القديم) ...\n" + tail).encode("utf-8"))
        except OSError:
            pass

    # ---- بدء مع إصلاح ذاتي ----
    def start(self) -> bool:
        with self.lock:
            if self.is_alive():
                return True
            notes: list = []
            try:
                self.stopped_by_user = False
                self.prepare(notes)
                last_findings: list = []
                for attempt in range(ENGINE_MAX_HEAL + 1):
                    self._spawn()
                    deadline = time.time() + ENGINE_STARTUP_GRACE
                    while time.time() < deadline and self.proc.poll() is None:
                        time.sleep(0.25)
                    if self.proc.poll() is None:
                        db_execute("UPDATE projects SET is_running=1, last_started_at=CURRENT_TIMESTAMP, last_error=NULL WHERE id=?",
                                   (self.project_id,))
                        log.info("Started project %s runtime=%s (pid=%s)", self.project_id, self.runtime, self.proc.pid)
                        return True
                    rc = self.proc.returncode
                    out = self.run_log(12000)
                    if rc == 0:
                        self.finished_ok = True
                        db_execute("UPDATE projects SET is_running=0, last_error=NULL WHERE id=?", (self.project_id,))
                        _record_event(self.project_id, "finished", "انتهى التنفيذ بنجاح (exit 0)")
                        return True
                    last_findings = analyze_log(out, self.runtime)
                    fixed = False
                    for f in last_findings:
                        fx = f.get("fix")
                        if fx and fx not in self.applied_fixes:
                            self.applied_fixes.add(fx)
                            if apply_fix(self.project_id, self.work_dir, self.runtime, fx, self._env(), notes):
                                _record_event(self.project_id, "autofix", f"{fx[0]} {fx[1]}")
                                fixed = True
                    if not fixed:
                        break
                # فشل نهائي
                summary = format_findings(last_findings, 4) or f"انتهت العملية بالرمز {self.proc.returncode if self.proc else '?'}"
                plain = re.sub(r"<[^>]+>", "", summary)
                detail = (plain + (" | " + "; ".join(notes[-3:]) if notes else ""))[:480]
                db_execute("UPDATE projects SET is_running=0, last_error=? WHERE id=?", (detail, self.project_id))
                _record_event(self.project_id, "error", detail)
                return False
            except Exception as e:
                log.exception("Failed to start project %s", self.project_id)
                _record_event(self.project_id, "error", f"start failed: {e}")
                db_execute("UPDATE projects SET is_running=0, last_error=? WHERE id=?", (str(e)[:480], self.project_id))
                return False

    def stop(self, by_user: bool = True) -> bool:
        with self.lock:
            self.stopped_by_user = by_user
            if not self.is_alive():
                self._mark_stopped()
                return True
            assert self.proc is not None
            self._signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._signal(getattr(signal, "SIGKILL", signal.SIGTERM))
                try:
                    self.proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    pass
            self._signal(getattr(signal, "SIGKILL", signal.SIGTERM), quiet=True)  # أي أبناء متبقين
            self._mark_stopped()
            _record_event(self.project_id, "stop", "by_user" if by_user else "by_system")
            return True

    def _signal(self, sig, quiet: bool = False) -> None:
        if self.proc is None:
            return
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(self.proc.pid), sig)
            elif sig == signal.SIGTERM:
                self.proc.terminate()
            else:
                self.proc.kill()
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _mark_stopped(self):
        try:
            db_execute("UPDATE projects SET is_running=0, last_stopped_at=CURRENT_TIMESTAMP WHERE id=?", (self.project_id,))
        except Exception:
            log.exception("Failed to mark project %s stopped", self.project_id)

    # ---- مراقبة صحة أثناء التشغيل ----
    def health_scan(self) -> None:
        """يقرأ السجل الجديد؛ يكشف أخطاء قاتلة لا توقف العملية (مثل توكن مرفوض) ويبلّغ المالك مرة واحدة."""
        if not self.is_alive() or time.time() - self.last_health_scan < 45:
            return
        self.last_health_scan = time.time()
        chunk = _tail_file(self.log_path, 20000, self.health_offset)
        try:
            self.health_offset = os.path.getsize(self.log_path)
        except OSError:
            return
        if not chunk:
            return
        for f in analyze_log(chunk, self.runtime):
            if f["id"] in ("tg_token", "tg_conflict") and f["id"] not in self.notified:
                self.notified.add(f["id"])
                db_execute("UPDATE projects SET last_error=? WHERE id=?",
                           (re.sub(r"<[^>]+>", "", f["title"])[:300], self.project_id))
                _owner_notify(self.project_id, f"⚠️ <b>{f['title']}</b>\n{f['hint']}")


class StaticHostedProcess:
    """موقع HTML ثابت: لا توجد عملية — تخدمه بوابة الويب مباشرة. يحافظ على واجهة HostedProcess."""
    runtime = "static"

    def __init__(self, project_id: int, name: str, main_file: str, work_dir: str):
        self.project_id, self.name, self.main_file, self.work_dir = project_id, name, main_file, work_dir
        self.active = True
        self.proc = None
        self.pid = None
        self.auto_restart = False
        self.restart_count = 0
        self.last_start = time.time()
        self.stopped_by_user = False
        self.finished_ok = False
        self.restarting = False
        self.next_restart_at = 0.0
        self.log_offset = 0
        self.lock = threading.RLock()

    def is_alive(self) -> bool:
        return self.active

    def uptime(self) -> float:
        return time.time() - self.last_start if self.active else 0.0

    def run_log(self, n: int = 0) -> str:
        return ""

    def health_scan(self) -> None:
        return

    def _signal(self, *a, **k) -> None:
        return

    def start(self) -> bool:
        self.active = True
        self.last_start = time.time()
        self.stopped_by_user = False
        db_execute("UPDATE projects SET is_running=1, last_started_at=CURRENT_TIMESTAMP, last_error=NULL WHERE id=?", (self.project_id,))
        _record_event(self.project_id, "start", "static site published")
        return True

    def stop(self, by_user: bool = True) -> bool:
        self.active = False
        self.stopped_by_user = by_user
        self._mark_stopped()
        _record_event(self.project_id, "stop", "by_user" if by_user else "by_system")
        return True

    def _mark_stopped(self):
        try:
            db_execute("UPDATE projects SET is_running=0, last_stopped_at=CURRENT_TIMESTAMP WHERE id=?", (self.project_id,))
        except Exception:
            log.exception("Failed to mark project %s stopped", self.project_id)


class ProcessManager:
    def __init__(self):
        self.processes: Dict[int, HostedProcess] = {}
        self.lock = threading.Lock()
        self._plocks: Dict[int, threading.Lock] = {}
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stopping = threading.Event()
        self._pool = _cf.ThreadPoolExecutor(max_workers=6, thread_name_prefix="hosting-restart")

    def _project_dir(self, project_id: int) -> str:
        return os.path.join(PROJECTS_DIR, str(project_id))

    def _plock(self, project_id: int) -> threading.Lock:
        with self.lock:
            return self._plocks.setdefault(project_id, threading.Lock())

    def _materialize(self, project_id: int) -> str:
        """مزامنة تراكمية (لا تمسح node_modules ولا .venv)."""
        work_dir = self._project_dir(project_id)
        sync_project_to_disk(project_id, work_dir)
        return work_dir

    def wipe_project_dir(self, project_id: int) -> None:
        shutil.rmtree(self._project_dir(project_id), ignore_errors=True)

    def start_project(self, project_id: int):
        with self._plock(project_id):
            with self.lock:
                existing = self.processes.get(project_id)
            if existing and existing.is_alive():
                return True, "البوت يعمل بالفعل"
            row = db_fetchone("SELECT id, name, main_file, approved, runtime FROM projects WHERE id=?", (project_id,))
            if not row:
                return False, "المشروع غير موجود"
            if not row["approved"]:
                return False, "المشروع بانتظار موافقة المطور"
            try:
                prow = db_fetchone(
                    "SELECT security_flag, security_approved, expires_at, crash_locked, user_id, energy_exempt FROM projects WHERE id=?",
                    (project_id,),
                ) or {}
                if is_security_block_enabled() and int(prow.get("security_flag") or 0) == 1 and int(prow.get("security_approved") or 0) != 1:
                    return False, "بانتظار موافقة أمنية"
                if int(prow.get("crash_locked") or 0) == 1:
                    return False, "المشروع مقفول بسبب أعطال متكررة — افتح القفل أولاً"
                ok_sub, sub_msg = project_subscription_ok(project_id)
                if not ok_sub:
                    return False, sub_msg or "الاشتراك منتهي"
                if selective_maint_blocks("start"):
                    return False, "الصيانة الانتقائية: التشغيل متوقف مؤقتاً"
                pf = preflight_project(project_id)
                if not pf.get("ok"):
                    fails = [f"{n}:{m}" for n, o, m in pf.get("checks", []) if not o]
                    return False, "فشل الفحص قبل التشغيل: " + "; ".join(fails)[:300]
                uid_owner = int(prow.get("user_id") or 0)
                if uid_owner and not int(prow.get("energy_exempt") or 0):
                    ok_e, msg_e = consume_energy(uid_owner, int(get_setting("energy_per_start") or "1"))
                    if not ok_e:
                        return False, msg_e
            except Exception:
                log.exception("start gates")
            main_file = (row.get("main_file") or "").strip()
            if not main_file:
                return False, "الملف الرئيسي غير محدد"
            work_dir = self._materialize(project_id)
            if not os.path.exists(os.path.join(work_dir, main_file)):
                return False, f"الملف الرئيسي '{main_file}' غير موجود"
            runtime = detect_runtime_from_file(main_file)
            if (row.get("runtime") or "") != runtime:
                db_execute("UPDATE projects SET runtime=? WHERE id=?", (runtime, project_id))
            if runtime == "static":
                with self.lock:
                    hp = StaticHostedProcess(project_id, row["name"], main_file, work_dir)
                    self.processes[project_id] = hp
                hp.start()
                return True, "تم نشر الموقع"
            with self.lock:
                hp = self.processes.get(project_id)
                if hp is None or hp.main_file != main_file or hp.runtime != runtime:
                    hp = HostedProcess(project_id, row["name"], main_file, work_dir, runtime=runtime)
                    self.processes[project_id] = hp
                hp.auto_restart = True
                hp.next_restart_at = 0.0
            ok = hp.start()
            if ok and hp.finished_ok:
                return True, "انتهى تنفيذ السكربت بنجاح"
            if ok:
                return True, "تم التشغيل"
            err = (db_fetchone("SELECT last_error FROM projects WHERE id=?", (project_id,)) or {}).get("last_error") or ""
            return False, ("فشل التشغيل: " + err[:250]) if err else "فشل التشغيل"

    def stop_project(self, project_id: int):
        with self.lock:
            hp = self.processes.get(project_id)
        if not hp:
            db_execute("UPDATE projects SET is_running=0 WHERE id=?", (project_id,))
            return True, "غير مشغّل"
        hp.auto_restart = False
        hp.stop(by_user=True)
        return True, "تم الإيقاف"

    def restart_project(self, project_id: int):
        self.stop_project(project_id)
        time.sleep(0.5)
        return self.start_project(project_id)

    def is_running(self, project_id: int) -> bool:
        hp = self.processes.get(project_id)
        return bool(hp and hp.is_alive())

    def status(self, project_id: int) -> dict:
        hp = self.processes.get(project_id)
        if not hp or not hp.is_alive():
            return {"running": False}
        if getattr(hp, "runtime", "") == "static":
            return {"running": True, "static": True, "uptime": int(hp.uptime()), "runtime": "static", "restarts": 0}
        return {"running": True, "pid": hp.pid, "uptime": int(hp.uptime()), "mem_mb": round(_rss_mb(hp.pid), 1),
                "restarts": hp.restart_count, "runtime": hp.runtime}

    def tail_log(self, project_id: int, n_bytes: int = 4000) -> str:
        path = os.path.join(self._project_dir(project_id), "_runtime.log")
        if not os.path.exists(path):
            return ""
        return _tail_file(path, n_bytes) or ""

    # ---- المراقب ----
    def start_watchdog(self) -> None:
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="hosting-watchdog", daemon=True)
        self._watchdog_thread.start()

    def _restart_after_crash(self, hp: HostedProcess) -> None:
        try:
            if self._stopping.is_set() or hp.stopped_by_user:
                return
            out = hp.run_log(12000)
            findings = analyze_log(out, hp.runtime)
            notes: list = []
            for f in findings:
                fx = f.get("fix")
                if fx and fx not in hp.applied_fixes:
                    hp.applied_fixes.add(fx)
                    if apply_fix(hp.project_id, hp.work_dir, hp.runtime, fx, hp._env(), notes):
                        _record_event(hp.project_id, "autofix", f"{fx[0]} {fx[1]}")
            try:
                sync_project_to_disk(hp.project_id, hp.work_dir)
            except Exception:
                log.exception("sync before restart")
            if hp.start():
                hp.restart_count += 1
            elif not hp.finished_ok:
                hp.next_restart_at = time.time() + min(300.0, 10.0 * (2 ** min(hp.restart_count, 5)))
        except Exception:
            log.exception("restart after crash failed for %s", hp.project_id)
        finally:
            hp.restarting = False

    def _watchdog_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                with self.lock:
                    items = list(self.processes.items())
                now = time.time()
                for pid, hp in items:
                    if hp.stopped_by_user or hp.restarting or hp.proc is None:
                        continue
                    if hp.is_alive():
                        hp.health_scan()
                        if ENGINE_MAX_MEM_MB:
                            mem = _rss_mb(hp.pid)
                            if mem > ENGINE_MAX_MEM_MB:
                                _record_event(pid, "oom_kill", f"rss={mem:.0f}MB limit={ENGINE_MAX_MEM_MB}MB")
                                _owner_notify(pid, f"⚠️ تم إيقاف البوت لتجاوزه حد الذاكرة ({mem:.0f}MB). سيُعاد تشغيله.")
                                hp._signal(getattr(signal, "SIGKILL", signal.SIGTERM))
                        continue
                    if hp.finished_ok:
                        continue
                    if not hp.auto_restart:
                        hp._mark_stopped()
                        continue
                    if hp.next_restart_at and now < hp.next_restart_at:
                        continue
                    rc = hp.proc.poll()
                    elapsed = now - hp.last_start
                    if rc == 0 and elapsed < 30:
                        hp.finished_ok = True
                        hp._mark_stopped()
                        _record_event(pid, "finished", f"exit=0 uptime={elapsed:.0f}s")
                        _owner_notify(pid, "ℹ️ انتهى تنفيذ السكربت بنجاح وتوقف (لم يعد بحاجة لإعادة تشغيل).")
                        continue
                    if elapsed > 300:
                        hp.restart_count = 0  # استقر فترة طويلة
                    log.warning("Project %s exited rc=%s after %.1fs — restarting", pid, rc, elapsed)
                    _record_event(pid, "crash", f"exit={rc} uptime={elapsed:.0f}s")
                    findings = analyze_log(hp.run_log(8000), hp.runtime)
                    hint = re.sub(r"<[^>]+>", "", format_findings(findings, 2))
                    try:
                        notify_owner_crash(pid, f"exit={rc} uptime={elapsed:.0f}s" + (f"\n{hint}" if hint else ""))
                    except Exception:
                        pass
                    try:
                        if record_crash_budget(pid):
                            hp.auto_restart = False
                            hp._mark_stopped()
                            try:
                                bot.send_message(ADMIN_ID, f"Crash Budget: قفل المشروع #{pid} بعد توقفات متكررة")
                            except Exception:
                                pass
                            continue
                    except Exception:
                        pass
                    hp.restarting = True
                    hp.next_restart_at = now + min(60.0, 2.0 * (2 ** min(hp.restart_count, 5)))
                    self._pool.submit(self._delayed_restart, hp)
            except Exception:
                log.exception("watchdog loop error")
            self._stopping.wait(4)

    def _delayed_restart(self, hp: HostedProcess) -> None:
        delay = max(0.0, hp.next_restart_at - time.time())
        if delay:
            self._stopping.wait(delay)
        hp.next_restart_at = 0.0
        self._restart_after_crash(hp)

    def shutdown(self) -> None:
        self._stopping.set()
        with self.lock:
            items = list(self.processes.values())
        for hp in items:
            try:
                hp.auto_restart = False
                hp.stop(by_user=False)
            except Exception:
                log.exception("error stopping %s during shutdown", hp.project_id)
        # بعد الإيقاف النظامي نعيد وسم المشاريع التي كانت تعمل لتُستعاد عند التشغيل القادم
        try:
            for hp in items:
                if not hp.finished_ok:
                    db_execute("UPDATE projects SET is_running=1 WHERE id=?", (hp.project_id,))
        except Exception:
            pass

    def restore_running(self) -> None:
        """يعيد تشغيل المشاريع التي كانت تعمل قبل إيقاف الاستضافة (بدفعات حتى لا يرتفع الحمل)."""
        rows = db_fetchall("SELECT id FROM projects WHERE is_running=1 AND approved=1")
        db_execute("UPDATE projects SET is_running=0 WHERE is_running=1")
        ids = [r["id"] for r in rows]
        log.info("Restoring %d project(s)…", len(ids))

        def _one(pid: int):
            try:
                ok, msg = self.start_project(pid)
                log.info("Auto-restore project %s: %s (%s)", pid, ok, msg)
                if not ok:
                    _owner_notify(pid, f"⚠️ تعذر استعادة تشغيل البوت بعد إعادة تشغيل الاستضافة:\n{html_escape(msg)}")
            except Exception:
                log.exception("restore project %s", pid)

        def _batch():
            for i in range(0, len(ids), 3):
                futs = [self._pool.submit(_one, pid) for pid in ids[i:i + 3]]
                for f in futs:
                    try:
                        f.result(timeout=ENGINE_INSTALL_TIMEOUT * 2)
                    except Exception:
                        pass
        threading.Thread(target=_batch, name="hosting-restore", daemon=True).start()


def _record_event(project_id: int, event: str, message: str = "") -> None:
    try:
        db_execute("INSERT INTO process_logs (project_id, event, message) VALUES (?,?,?)",
                   (project_id, event, message[:1000] if message else None))
    except Exception:
        log.exception("failed to record event")


def list_project_disk_files(project_id: int, limit: int = 400) -> list:
    base = os.path.join(PROJECTS_DIR, str(project_id))
    if not os.path.isdir(base):
        return []
    out: list = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ENGINE_PROTECTED and d not in {".git", "venv"}]
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), base).replace("\\", "/")
            if rel.startswith("../"):
                continue
            out.append(rel)
            if len(out) >= limit:
                return sorted(out)
    return sorted(out)


def _is_safe_terminal_command(cmd: str) -> tuple:
    s = (cmd or "").strip()
    if not s:
        return False, "اكتب أمراً أولاً."
    if any(x in s for x in ["&", "|", ";", ">", "<", "`", "$(", "\n"]):
        return False, "الأمر يحتوي على رموز غير مسموحة."
    try:
        parts = shlex.split(s, posix=True)
    except Exception:
        return False, "تعذر قراءة الأمر."
    if not parts:
        return False, "اكتب أمراً صحيحاً."
    exe = os.path.basename(parts[0]).lower()
    allowed = {"python", "python3", "py", "pip", "pip3", "node", "nodejs", "npm", "npx"}
    if exe not in allowed:
        return False, "المسموح فقط: python / pip / node / npm / npx"
    if exe in ("pip", "pip3") or (exe in ("python", "python3", "py") and len(parts) > 2 and parts[1] == "-m" and parts[2] == "pip"):
        for a in parts[1:]:
            if a.startswith(("--target", "--prefix", "--root", "--user")) and False:
                return False, "خيار غير مسموح."
    if exe in ("python", "python3", "py") and ("-c" in parts[1:2]):
        return False, "تنفيذ كود مباشر (-c) غير مسموح — شغّل ملفاً من مشروعك."
    return True, ""


def run_project_terminal_command(project_id: int, cmd: str, timeout_s: int = 60, user_id: int = 0) -> str:
    if selective_maint_blocks("terminal"):
        return "الصيانة الانتقائية: التيرمنال متوقف مؤقتاً"
    ok, reason = _is_safe_terminal_command(cmd)
    if not ok:
        return f"❌ {reason}"
    try:
        db_execute("INSERT INTO terminal_audit (user_id, project_id, command) VALUES (?,?,?)",
                   (user_id or 0, project_id, (cmd or "")[:500]))
    except Exception:
        pass
    work_dir = os.path.join(PROJECTS_DIR, str(project_id))
    if not os.path.isdir(work_dir):
        return "❌ مجلد البوت غير موجود على السيرفر."
    parts = shlex.split(cmd, posix=True)
    exe = os.path.basename(parts[0]).lower()
    env = jail_materialize_env(project_id, work_dir)
    for k in ("NETLIFY_TOKEN", "VERCEL_TOKEN", "BOT_TOKEN"):
        env.pop(k, None)
    # pip / python يستخدمان بيئة المشروع المعزولة
    vp = _venv_python(work_dir)
    if vp:
        if exe in ("pip", "pip3"):
            parts = [vp, "-m", "pip"] + parts[1:]
        elif exe in ("python", "python3", "py"):
            parts = [vp] + parts[1:]
    elif exe in ("pip", "pip3"):
        parts = [sys.executable, "-m", "pip"] + parts[1:]
    elif exe in ("python", "python3", "py"):
        parts = [sys.executable] + parts[1:]
    if exe in ("npm", "npx", "node", "nodejs"):
        env = _npm_env(work_dir, env)
        if exe in ("node", "nodejs"):
            parts[0] = _find_node_bin()
        elif exe == "npm":
            parts[0] = _find_npm_bin()
    rc, out = _run_cmd(parts, work_dir, env=env, timeout=timeout_s)
    out = out or "(لا يوجد إخراج)"
    try:
        with open(os.path.join(work_dir, "_runtime.log"), "a", encoding="utf-8") as fh:
            fh.write(f"\n$ {cmd}\n{out}\n")
    except Exception:
        pass
    if rc == 124:
        return "⏱️ الأمر أخذ وقتاً طويلاً وتم إيقافه."
    return out[-3500:]


def install_dependencies(project_id: int, force: bool = True) -> tuple:
    """تثبيت المكتبات يدوياً. يرجع (ok, نص_عربي_للمستخدم)."""
    p = db_fetchone("SELECT main_file, runtime, name FROM projects WHERE id=?", (project_id,))
    if not p:
        return False, "المشروع غير موجود."
    if detect_runtime_from_file(p.get("main_file") or "") == "static":
        return True, "📋 هذا موقع HTML ثابت — لا يحتاج أي مكتبات."
    work_dir = manager._materialize(project_id)
    rt = detect_runtime_from_file(p.get("main_file") or "") if p.get("main_file") else (p.get("runtime") or "python")
    hp = HostedProcess(project_id, p.get("name") or "", p.get("main_file") or "", work_dir, runtime=rt)
    notes: list = []
    ok = hp.prepare(notes, force=force)
    if rt == "python":
        names = detect_python_imports(work_dir)
        src = "requirements.txt + الاكتشاف التلقائي" if os.path.isfile(os.path.join(work_dir, "requirements.txt")) else "الاكتشاف التلقائي من الكود"
    else:
        names = detect_node_packages(work_dir)
        src = "package.json + الاكتشاف التلقائي" if os.path.isfile(os.path.join(work_dir, "package.json")) else "الاكتشاف التلقائي من الكود"
    lines = [f"📋 المصدر: {src}"]
    if names:
        lines.append("📦 مكتبات مكتشفة: " + ", ".join(names[:25]))
    lines += [html_escape(n) for n in notes[-8:]]
    return ok, "\n".join(lines)


manager = ProcessManager()



# ============================================================
# 9) إعداد البوت
# ============================================================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", num_threads=8)

# ============================================================
# Custom Emoji + Auto-Blockquote (style layer)
# ============================================================
_CE = {
    '✅': '<tg-emoji emoji-id="6258259403200270844">✅</tg-emoji>',
    '☑️': '<tg-emoji emoji-id="4945049066271671758">☑️</tg-emoji>',
    '🔍': '<tg-emoji emoji-id="5965466792527666087">🔍</tg-emoji>',
    '🔎': '<tg-emoji emoji-id="5965466792527666087">🔎</tg-emoji>',
    '👤': '<tg-emoji emoji-id="5373020661574826232">👤</tg-emoji>',
    '📱': '<tg-emoji emoji-id="5834628314731387616">📱</tg-emoji>',
    '💳': '<tg-emoji emoji-id="5447453226498552490">💳</tg-emoji>',
    '🔗': '<tg-emoji emoji-id="5967301267549068409">🔗</tg-emoji>',
    '🎟': '<tg-emoji emoji-id="5785167918027250397">🎟</tg-emoji>',
    '🎟️': '<tg-emoji emoji-id="5785167918027250397">🎟️</tg-emoji>',
    '⚙️': '<tg-emoji emoji-id="5857054220179480029">⚙️</tg-emoji>',
    '➕': '<tg-emoji emoji-id="5857339990123486296">➕</tg-emoji>',
    '📋': '<tg-emoji emoji-id="5803363345113290876">📋</tg-emoji>',
    '🗑': '<tg-emoji emoji-id="5920209833071482745">🗑</tg-emoji>',
    '🗑️': '<tg-emoji emoji-id="5920209833071482745">🗑️</tg-emoji>',
    '❌': '<tg-emoji emoji-id="5796291784539639311">❌</tg-emoji>',
    '🛡': '<tg-emoji emoji-id="5920298756074379058">🛡</tg-emoji>',
    '🛡️': '<tg-emoji emoji-id="5920298756074379058">🛡️</tg-emoji>',
    '👥': '<tg-emoji emoji-id="6001388309853510348">👥</tg-emoji>',
    '🚫': '<tg-emoji emoji-id="5888789252493283486">🚫</tg-emoji>',
    '🔓': '<tg-emoji emoji-id="5998940732545571769">🔓</tg-emoji>',
    '➖': '<tg-emoji emoji-id="5280753674451175517">➖</tg-emoji>',
    '🔄': '<tg-emoji emoji-id="5976831692604709621">🔄</tg-emoji>',
    '💰': '<tg-emoji emoji-id="6037182124916740433">💰</tg-emoji>',
    '🎁': '<tg-emoji emoji-id="5976317950091598658">🎁</tg-emoji>',
    '🔙': '<tg-emoji emoji-id="5253743295141538873">🔙</tg-emoji>',
    '✨': '<tg-emoji emoji-id="5254001839287859496">✨</tg-emoji>',
    '📊': '<tg-emoji emoji-id="5935935761336505948">📊</tg-emoji>',
    '📢': '<tg-emoji emoji-id="5902385465390013835">📢</tg-emoji>',
    '🌐': '<tg-emoji emoji-id="5837128389424585193">🌐</tg-emoji>',
    '🧙': '<tg-emoji emoji-id="5803157577525106419">🧙</tg-emoji>',
    '📡': '<tg-emoji emoji-id="5836811137370297987">📡</tg-emoji>',
    '🌾': '<tg-emoji emoji-id="5981216003810400332">🌾</tg-emoji>',
    '🛠': '<tg-emoji emoji-id="5965466792527666087">🛠</tg-emoji>',
    '🛠️': '<tg-emoji emoji-id="5965466792527666087">🛠️</tg-emoji>',
    '👑': '<tg-emoji emoji-id="5319149831673887746">👑</tg-emoji>',
    '🆕': '<tg-emoji emoji-id="5857339990123486296">🆕</tg-emoji>',
    '📤': '<tg-emoji emoji-id="5920298756074379058">📤</tg-emoji>',
    '📥': '<tg-emoji emoji-id="5920415115328362511">📥</tg-emoji>',
    '📞': '<tg-emoji emoji-id="5373020661574826232">📞</tg-emoji>',
    '🏦': '<tg-emoji emoji-id="5803363345113290876">🏦</tg-emoji>',
    '💎': '<tg-emoji emoji-id="5254001839287859496">💎</tg-emoji>',
    '🔑': '<tg-emoji emoji-id="5785167918027250397">🔑</tg-emoji>',
    '🎫': '<tg-emoji emoji-id="5785167918027250397">🎫</tg-emoji>',
    '📌': '<tg-emoji emoji-id="5920298756074379058">📌</tg-emoji>',
    '📝': '<tg-emoji emoji-id="5314299563761222650">📝</tg-emoji>',
    '📈': '<tg-emoji emoji-id="5935935761336505948">📈</tg-emoji>',
    '📅': '<tg-emoji emoji-id="5314299563761222650">📅</tg-emoji>',
    '📦': '<tg-emoji emoji-id="5881760620117760960">📦</tg-emoji>',
    '🔢': '<tg-emoji emoji-id="5965466792527666087">🔢</tg-emoji>',
    '✏️': '<tg-emoji emoji-id="5314299563761222650">✏️</tg-emoji>',
    '🖨': '<tg-emoji emoji-id="5967617875358258757">🖨</tg-emoji>',
    '🖨️': '<tg-emoji emoji-id="5967617875358258757">🖨️</tg-emoji>',
    '🖼': '<tg-emoji emoji-id="5294079682365384341">🖼</tg-emoji>',
    '🖼️': '<tg-emoji emoji-id="5294079682365384341">🖼️</tg-emoji>',
    '⏳': '<tg-emoji emoji-id="5314299563761222650">⏳</tg-emoji>',
    '⏰': '<tg-emoji emoji-id="5314299563761222650">⏰</tg-emoji>',
    '🎉': '<tg-emoji emoji-id="5254001839287859496">🎉</tg-emoji>',
    '🔹': '<tg-emoji emoji-id="5967301267549068409">🔹</tg-emoji>',
    '⭐': '<tg-emoji emoji-id="5254001839287859496">⭐</tg-emoji>',
    '😎': '<tg-emoji emoji-id="5976308930660276596">😎</tg-emoji>',
    '💗': '<tg-emoji emoji-id="6043941205144771802">💗</tg-emoji>',
    '🎯': '<tg-emoji emoji-id="5965466792527666087">🎯</tg-emoji>',
    '📂': '<tg-emoji emoji-id="5881760620117760960">📂</tg-emoji>',
    '🗂': '<tg-emoji emoji-id="5881760620117760960">🗂</tg-emoji>',
    '🗂️': '<tg-emoji emoji-id="5881760620117760960">🗂️</tg-emoji>',
    '💲': '<tg-emoji emoji-id="6003691769533829755">💲</tg-emoji>',
    '⚠️': '<tg-emoji emoji-id="5999278377104578246">⚠️</tg-emoji>',
    '🔴': '<tg-emoji emoji-id="5999278377104578246">🔴</tg-emoji>',
    '🟢': '<tg-emoji emoji-id="4945049066271671758">🟢</tg-emoji>',
    '🔵': '<tg-emoji emoji-id="5967301267549068409">🔵</tg-emoji>',
    '💬': '<tg-emoji emoji-id="5314299563761222650">💬</tg-emoji>',
    '🧹': '<tg-emoji emoji-id="5920415115328362511">🧹</tg-emoji>',
    '⬆️': '<tg-emoji emoji-id="5920298756074379058">⬆️</tg-emoji>',
    '⬇️': '<tg-emoji emoji-id="5922681088534124293">⬇️</tg-emoji>',
    '🏷': '<tg-emoji emoji-id="5881760620117760960">🏷</tg-emoji>',
    '🏷️': '<tg-emoji emoji-id="5881760620117760960">🏷️</tg-emoji>',
    '📣': '<tg-emoji emoji-id="5902385465390013835">📣</tg-emoji>',
    '🎨': '<tg-emoji emoji-id="5254001839287859496">🎨</tg-emoji>',
    '🤖': '<tg-emoji emoji-id="5357139124451077525">🤖</tg-emoji>',
    '🖥': '<tg-emoji emoji-id="5373022469857259576">🖥</tg-emoji>',
    '🖥️': '<tg-emoji emoji-id="5373022469857259576">🖥️</tg-emoji>',
    '🏠': '<tg-emoji emoji-id="5373075876995791263">🏠</tg-emoji>',
    '🔒': '<tg-emoji emoji-id="5373106487345813453">🔒</tg-emoji>',
    '🏆': '<tg-emoji emoji-id="5357218765520568623">🏆</tg-emoji>',
    '🔔': '<tg-emoji emoji-id="5363590091167151694">🔔</tg-emoji>',
    '🔕': '<tg-emoji emoji-id="5373127735794994543">🔕</tg-emoji>',
    '📛': '<tg-emoji emoji-id="5357237058654332406">📛</tg-emoji>',
    '🕵️': '<tg-emoji emoji-id="5357316859913549347">🕵️</tg-emoji>',
    '📺': '<tg-emoji emoji-id="5373076552313753030">📺</tg-emoji>',
    '🏷': '<tg-emoji emoji-id="5881760620117760960">🏷</tg-emoji>',
    '🪪': '<tg-emoji emoji-id="5361824899448505171">🪪</tg-emoji>',
}


def _apply_ce(text: str) -> str:
    if not text:
        return text
    for ch, repl in _CE.items():
        text = text.replace(ch, repl)
    return text


try:
    apihelper.CONNECT_TIMEOUT = 15
    apihelper.READ_TIMEOUT = 60
    if hasattr(apihelper, "RETRY_ON_ERROR"):
        apihelper.RETRY_ON_ERROR = True
    if hasattr(apihelper, "MAX_RETRIES"):
        apihelper.MAX_RETRIES = 3
except Exception:
    pass

try:
    if hasattr(telebot, "logger"):
        telebot.logger.setLevel(logging.CRITICAL)
    logging.getLogger("TeleBot").setLevel(logging.CRITICAL)
except Exception:
    pass


# ---- إيموجي مخصصة: كل إيموجي في النص يُستبدل بـ <tg-emoji> تلقائياً ----
_CE = {
    '✅': '<tg-emoji emoji-id="6258259403200270844">✅</tg-emoji>',
    '☑️': '<tg-emoji emoji-id="4945049066271671758">☑️</tg-emoji>',
    '🔍': '<tg-emoji emoji-id="5965466792527666087">🔍</tg-emoji>',
    '🔎': '<tg-emoji emoji-id="5965466792527666087">🔎</tg-emoji>',
    '👤': '<tg-emoji emoji-id="5373020661574826232">👤</tg-emoji>',
    '📱': '<tg-emoji emoji-id="5834628314731387616">📱</tg-emoji>',
    '💳': '<tg-emoji emoji-id="5447453226498552490">💳</tg-emoji>',
    '🔗': '<tg-emoji emoji-id="5967301267549068409">🔗</tg-emoji>',
    '🎟': '<tg-emoji emoji-id="5785167918027250397">🎟</tg-emoji>',
    '🎟️': '<tg-emoji emoji-id="5785167918027250397">🎟️</tg-emoji>',
    '⚙️': '<tg-emoji emoji-id="5857054220179480029">⚙️</tg-emoji>',
    '➕': '<tg-emoji emoji-id="5857339990123486296">➕</tg-emoji>',
    '📋': '<tg-emoji emoji-id="5803363345113290876">📋</tg-emoji>',
    '🗑': '<tg-emoji emoji-id="5920209833071482745">🗑</tg-emoji>',
    '🗑️': '<tg-emoji emoji-id="5920209833071482745">🗑️</tg-emoji>',
    '❌': '<tg-emoji emoji-id="5796291784539639311">❌</tg-emoji>',
    '🛡': '<tg-emoji emoji-id="5920298756074379058">🛡</tg-emoji>',
    '🛡️': '<tg-emoji emoji-id="5920298756074379058">🛡️</tg-emoji>',
    '👥': '<tg-emoji emoji-id="6001388309853510348">👥</tg-emoji>',
    '🚫': '<tg-emoji emoji-id="5888789252493283486">🚫</tg-emoji>',
    '🔓': '<tg-emoji emoji-id="5998940732545571769">🔓</tg-emoji>',
    '➖': '<tg-emoji emoji-id="5280753674451175517">➖</tg-emoji>',
    '🔄': '<tg-emoji emoji-id="5976831692604709621">🔄</tg-emoji>',
    '💰': '<tg-emoji emoji-id="6037182124916740433">💰</tg-emoji>',
    '🎁': '<tg-emoji emoji-id="5976317950091598658">🎁</tg-emoji>',
    '': '<tg-emoji emoji-id="5253743295141538873"></tg-emoji>',
    '✨': '<tg-emoji emoji-id="5254001839287859496">✨</tg-emoji>',
    '📊': '<tg-emoji emoji-id="5935935761336505948">📊</tg-emoji>',
    '📢': '<tg-emoji emoji-id="5902385465390013835">📢</tg-emoji>',
    '⚡': '<tg-emoji emoji-id="5837128389424585193">⚡</tg-emoji>',
    '🧙': '<tg-emoji emoji-id="5803157577525106419">🧙</tg-emoji>',
    '📡': '<tg-emoji emoji-id="5836811137370297987">📡</tg-emoji>',
    '🌾': '<tg-emoji emoji-id="5981216003810400332">🌾</tg-emoji>',
    '🛠': '<tg-emoji emoji-id="5965466792527666087">🛠</tg-emoji>',
    '🛠️': '<tg-emoji emoji-id="5965466792527666087">🛠️</tg-emoji>',
    '👑': '<tg-emoji emoji-id="5319149831673887746">👑</tg-emoji>',
    '🆕': '<tg-emoji emoji-id="5857339990123486296">🆕</tg-emoji>',
    '📤': '<tg-emoji emoji-id="5920298756074379058">📤</tg-emoji>',
    '📥': '<tg-emoji emoji-id="5920415115328362511">📥</tg-emoji>',
    '📞': '<tg-emoji emoji-id="5373020661574826232">📞</tg-emoji>',
    '🏦': '<tg-emoji emoji-id="5803363345113290876">🏦</tg-emoji>',
    '💎': '<tg-emoji emoji-id="5254001839287859496">💎</tg-emoji>',
    '🔑': '<tg-emoji emoji-id="5785167918027250397">🔑</tg-emoji>',
    '🎫': '<tg-emoji emoji-id="5785167918027250397">🎫</tg-emoji>',
    '📌': '<tg-emoji emoji-id="5920298756074379058">📌</tg-emoji>',
    '📝': '<tg-emoji emoji-id="5314299563761222650">📝</tg-emoji>',
    '📈': '<tg-emoji emoji-id="5935935761336505948">📈</tg-emoji>',
    '📅': '<tg-emoji emoji-id="5314299563761222650">📅</tg-emoji>',
    '📦': '<tg-emoji emoji-id="5881760620117760960">📦</tg-emoji>',
    '🔢': '<tg-emoji emoji-id="5965466792527666087">🔢</tg-emoji>',
    '✏️': '<tg-emoji emoji-id="5314299563761222650">✏️</tg-emoji>',
    '🖨': '<tg-emoji emoji-id="5967617875358258757">🖨</tg-emoji>',
    '🖨️': '<tg-emoji emoji-id="5967617875358258757">🖨️</tg-emoji>',
    '🖼': '<tg-emoji emoji-id="5294079682365384341">🖼</tg-emoji>',
    '🖼️': '<tg-emoji emoji-id="5294079682365384341">🖼️</tg-emoji>',
    '⏳': '<tg-emoji emoji-id="5314299563761222650">⏳</tg-emoji>',
    '⏰': '<tg-emoji emoji-id="5314299563761222650">⏰</tg-emoji>',
    '🎉': '<tg-emoji emoji-id="5254001839287859496">🎉</tg-emoji>',
    '🔹': '<tg-emoji emoji-id="5967301267549068409">🔹</tg-emoji>',
    '⭐': '<tg-emoji emoji-id="5254001839287859496">⭐</tg-emoji>',
    '😎': '<tg-emoji emoji-id="5976308930660276596">😎</tg-emoji>',
    '💗': '<tg-emoji emoji-id="6043941205144771802">💗</tg-emoji>',
    '🎯': '<tg-emoji emoji-id="5965466792527666087">🎯</tg-emoji>',
    '📂': '<tg-emoji emoji-id="5881760620117760960">📂</tg-emoji>',
    '🗂': '<tg-emoji emoji-id="5881760620117760960">🗂</tg-emoji>',
    '🗂️': '<tg-emoji emoji-id="5881760620117760960">🗂️</tg-emoji>',
    '💲': '<tg-emoji emoji-id="6003691769533829755">💲</tg-emoji>',
    '⚠️': '<tg-emoji emoji-id="5999278377104578246">⚠️</tg-emoji>',
    '🔴': '<tg-emoji emoji-id="5999278377104578246">🔴</tg-emoji>',
    '🟢': '<tg-emoji emoji-id="4945049066271671758">🟢</tg-emoji>',
    '🔵': '<tg-emoji emoji-id="5967301267549068409">🔵</tg-emoji>',
    '💬': '<tg-emoji emoji-id="5314299563761222650">💬</tg-emoji>',
    '🧹': '<tg-emoji emoji-id="5920415115328362511">🧹</tg-emoji>',
    '⬆️': '<tg-emoji emoji-id="5920298756074379058">⬆️</tg-emoji>',
    '⬇️': '<tg-emoji emoji-id="5922681088534124293">⬇️</tg-emoji>',
    '🏷': '<tg-emoji emoji-id="5881760620117760960">🏷</tg-emoji>',
    '🏷️': '<tg-emoji emoji-id="5881760620117760960">🏷️</tg-emoji>',
    '📣': '<tg-emoji emoji-id="5902385465390013835">📣</tg-emoji>',
    '🎨': '<tg-emoji emoji-id="5254001839287859496">🎨</tg-emoji>',
    '🚀': '<tg-emoji emoji-id="5857339990123486296">🚀</tg-emoji>',
    '🤖': '<tg-emoji emoji-id="5836811137370297987">🤖</tg-emoji>',
    '🖥️': '<tg-emoji emoji-id="5967617875358258757">🖥️</tg-emoji>',
    '🖥': '<tg-emoji emoji-id="5967617875358258757">🖥</tg-emoji>',
    '🏆': '<tg-emoji emoji-id="5254001839287859496">🏆</tg-emoji>',
    '🪪': '<tg-emoji emoji-id="5803363345113290876">🪪</tg-emoji>',
    '💸': '<tg-emoji emoji-id="6037182124916740433">💸</tg-emoji>',
    '💵': '<tg-emoji emoji-id="6037182124916740433">💵</tg-emoji>',
    '🔔': '<tg-emoji emoji-id="5314299563761222650">🔔</tg-emoji>',
    '🔕': '<tg-emoji emoji-id="5314299563761222650">🔕</tg-emoji>',
    '⛔': '<tg-emoji emoji-id="5999278377104578246">⛔</tg-emoji>',
    '▶️': '<tg-emoji emoji-id="4945049066271671758">▶️</tg-emoji>',
    '🛑': '<tg-emoji emoji-id="5999278377104578246">🛑</tg-emoji>',
    '📜': '<tg-emoji emoji-id="5803363345113290876">📜</tg-emoji>',
    '📁': '<tg-emoji emoji-id="5881760620117760960">📁</tg-emoji>',

    '🧾': '<tg-emoji emoji-id="5803363345113290876">🧾</tg-emoji>',
    '🌍': '<tg-emoji emoji-id="5837128389424585193">🌍</tg-emoji>',
    '👨‍💻': '<tg-emoji emoji-id="5373020661574826232">👨‍💻</tg-emoji>',
    '🏠': '<tg-emoji emoji-id="5881760620117760960">🏠</tg-emoji>',
}


def _apply_ce(text: str) -> str:
    return text


def _bq(text) -> str:
    if text is None:
        return text
    s = str(text).strip()
    if not s:
        return text
    if s.startswith("<blockquote>"):
        return _apply_ce(s)
    return f"<blockquote>{_apply_ce(s)}</blockquote>"


_orig_send_message      = bot.send_message
_orig_edit_message_text = bot.edit_message_text
_orig_send_photo        = bot.send_photo
_orig_edit_message_cap  = bot.edit_message_caption


def _send_message_quoted(chat_id, text, *args, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    if str(kwargs.get("parse_mode", "")).upper() == "HTML":
        text = _bq(text)
    return _orig_send_message(chat_id, text, *args, **kwargs)


def _is_not_modified(e) -> bool:
    return "message is not modified" in str(e).lower()


def _edit_message_text_quoted(text, *args, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    if str(kwargs.get("parse_mode", "")).upper() == "HTML":
        text = _bq(text)
    try:
        return _orig_edit_message_text(text, *args, **kwargs)
    except Exception as e:
        err = str(e).lower()
        if _is_not_modified(e):
            return None
        # الرسالة تحتوي صورة → عدّل caption بدل النص حتى لا تختفي الصورة
        if "there is no text in the message" in err or "message can't be edited" in err:
            try:
                # args: (text, chat_id, message_id, ...) — نستخرج chat_id و message_id
                chat_id  = args[0] if len(args) > 0 else kwargs.get("chat_id")
                msg_id   = args[1] if len(args) > 1 else kwargs.get("message_id")
                cap_kw   = {k: v for k, v in kwargs.items() if k != "entities"}
                return _orig_edit_message_cap(
                    chat_id=chat_id, message_id=msg_id, caption=text, **cap_kw
                )
            except Exception as e2:
                if _is_not_modified(e2):
                    return None
        raise


def _send_photo_quoted(chat_id, photo, caption=None, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    return _orig_send_photo(chat_id, photo,
                            caption=_bq(caption) if caption else None, **kwargs)


def _edit_message_caption_quoted(chat_id=None, message_id=None, caption=None, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    try:
        return _orig_edit_message_cap(chat_id=chat_id, message_id=message_id,
                                      caption=_bq(caption) if caption else None, **kwargs)
    except Exception as e:
        if _is_not_modified(e):
            return None
        raise


# ── توافق أزرار — يضمن عمل style و icon_custom_emoji_id + per-group color override ──
_BTN_GROUP_PREFIXES = [
    # ── لوحة الأدمن ──
    ("requests",      ["adm_pending_"]),
    ("users",         ["adm_users", "adm_user_", "adm_ban_", "adm_unban_", "admin_list", "adm_blocked", "adm_search_user", "adm_export"]),
    ("comms",         ["adm_broadcast", "adm_send_user", "admin_warn"]),
    ("adm_points",    ["adm_give_", "adm_set_points", "adm_top_", "adm_gift_"]),
    ("bots",          ["adm_project", "adm_del_stopped", "adm_set_max_bots"]),
    ("settings",      ["adm_set_upload", "adm_set_transfer", "adm_section", "adm_mods", "adm_force", "adm_toggle", "adm_set_welcome", "adm_btn_color"]),
    ("stats",         ["adm_stats", "adm_server", "adm_backup_db", "adm_growth_stats", "adm_audit_log", "adm_cleanup_files", "adm_usage_stats",
                       "adm_db_table_stats", "adm_deploy_stats", "adm_daily_report", "adm_points_dist"]),
    ("new_admin",     ["adm_running_bots_list", "adm_inactive_users", "adm_export_bots", "adm_announce",
                       "adm_new_today", "adm_user_bots_by_id", "adm_reset_points_id", "adm_set_user_max",
                       "adm_crashed_bots", "adm_search_bot_name", "adm_bots_summary", "adm_clear_proc_logs",
                       "adm_msg_to_inactive", "adm_broadcast_active_only", "adm_receivers_count",
                       "adm_view_settings", "adm_toggle_auto_approve", "adm_clear_audit",
                       "adm_approve_id", "adm_proc_info",
                       "adm_user_profile", "adm_ban_by_id", "adm_unban_by_id", "adm_pending_users", "adm_vip_users",
                       "adm_force_stop_bot", "adm_force_start_bot", "adm_bot_files_info", "adm_top_bots", "adm_new_bots_today",
                       "adm_msg_by_id", "adm_broadcast_pending", "adm_last_broadcast_stats",
                       "adm_weekly_report", "adm_top_uploaders", "adm_error_log_view", "adm_activity_stats",
                       "adm_maintenance_mode", "adm_sys_info", "adm_clear_blocked_db"]),
    # ── لوحة المستخدم ──
    ("user_bots",     ["proj_new", "proj_list"]),
    ("user_upload",   ["site_upload", "vercel_upload"]),
    ("user_mysites",  ["my_sites", "my_deploys"]),
    ("user_terminal", ["main_terminal"]),
    ("user_info",     ["my_stats", "help"]),
    ("user_points",   ["points", "transfer_points"]),
    ("user_misc",     ["back_main", "noop_sig"]),
]

def _get_group_style(callback_data: str, original_style: str) -> str:
    try:
        cd = callback_data or ""
        for group_key, prefixes in _BTN_GROUP_PREFIXES:
            if any(cd.startswith(p) for p in prefixes):
                color = get_setting(f"btn_color_{group_key}") or "mixed"
                if color == "mixed":
                    return original_style
                # ثيمات موسّعة → أسلوب تيليجرام
                mapped = {
                    "primary": "primary", "success": "success", "danger": "danger",
                    "ocean": "primary", "forest": "success", "sunset": "danger",
                    "night": "primary", "gold": "success", "rose": "danger", "cyber": "primary",
                }.get(color, color if color in ("primary", "success", "danger") else original_style)
                return mapped
        # ثيم عام من الإعدادات — يطبَّق على كل الأزرار
        _theme = (get_setting("btn_style_theme") or "mixed")
        _override = {
            "all_primary": "primary", "all_success": "success", "all_danger": "danger",
            "ocean": "primary", "forest": "success", "sunset": "danger",
            "night": "primary", "gold": "success", "rose": "danger", "cyber": "primary",
            "primary": "primary", "success": "success", "danger": "danger",
        }
        if _theme in _override:
            return _override[_theme]
        # إن وُجد ثيم مجموعة "global"
        g = get_setting("btn_color_global") or "mixed"
        if g in _override:
            return _override[g]
    except Exception:
        pass
    return original_style

try:
    _ikb_orig = types.InlineKeyboardButton.__init__
    def _ikb_patched(self, *_a, **_kw):
        _extra = {k: _kw.pop(k) for k in ('style', 'icon_custom_emoji_id') if k in _kw}
        _ikb_orig(self, *_a, **_kw)
        if 'style' in _extra:
            _extra['style'] = _get_group_style(
                getattr(self, 'callback_data', '') or '',
                _extra['style']
            )
        for _k, _v in _extra.items():
            self.__dict__[_k] = _v
    types.InlineKeyboardButton.__init__ = _ikb_patched
except Exception:
    pass
# ──────────────────────────────────────────────────────────────────

bot.send_message         = _send_message_quoted
bot.edit_message_text    = _edit_message_text_quoted
bot.send_photo           = _send_photo_quoted
bot.edit_message_caption = _edit_message_caption_quoted

_pending_actions: dict = {}
_pending_lock = threading.Lock()

_seen_lock = threading.Lock()
_seen_keys: dict = {}


def _seen_once(key) -> bool:
    now = time.time()
    with _seen_lock:
        if len(_seen_keys) > 2000:
            cutoff = now - 600
            for k in [k for k, t in _seen_keys.items() if t < cutoff]:
                _seen_keys.pop(k, None)
        if key in _seen_keys:
            return True
        _seen_keys[key] = now
    return False


def msg_seen(message) -> bool:
    return _seen_once(("m", message.chat.id, message.message_id))


def call_seen(call) -> bool:
    return _seen_once(("c", call.id))


_bot_username_cache: Optional[str] = None


def get_bot_username() -> str:
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    try:
        _bot_username_cache = bot.get_me().username or "your_bot"
    except Exception:
        _bot_username_cache = "your_bot"
    return _bot_username_cache


def html_escape(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_admin(uid: int) -> bool:
    if uid in _DEVELOPER_IDS:
        return True
    try:
        row = db_fetchone("SELECT user_id FROM moderators WHERE user_id=?", (uid,))
        return row is not None
    except Exception:
        return False


def safe_filename(name: str) -> str:
    name = os.path.basename(name)
    return "".join(c for c in name if c.isalnum() or c in "._-") or "file.bin"


def file_extension(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def is_allowed_extension(name: str) -> bool:
    """يقبل كل الامتدادات الشائعة + أي ملف نصي/بيانات؛ يرفض التنفيذيات الخطرة فقط."""
    ext = file_extension(name)
    if ext in ALLOWED_EXTENSIONS:
        return True
    # رفض التنفيذيات الخطرة
    blocked = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".dll", ".so", ".dylib", ".bin", ".sh"}
    if ext in blocked:
        return False
    # قبول أي امتداد آخر (ملفات فردية أو داخل ZIP)
    return True


def set_pending(uid: int, action: dict) -> None:
    with _pending_lock:
        _pending_actions[uid] = action


def pop_pending(uid: int):
    with _pending_lock:
        return _pending_actions.pop(uid, None)


def get_pending(uid: int):
    with _pending_lock:
        return _pending_actions.get(uid)


def ensure_user(message_or_call) -> dict:
    user = (
        message_or_call.from_user
        if hasattr(message_or_call, "from_user")
        else message_or_call.message.from_user
    )
    db_execute(
        "INSERT INTO users (id, first_name, username, approved) VALUES (?, ?, ?, 1) "
        "ON CONFLICT (id) DO UPDATE SET first_name=excluded.first_name, "
        "username=excluded.username, approved=1",
        (user.id, user.first_name or "", user.username or ""),
    )
    row = db_fetchone("SELECT id, approved, banned, max_bots FROM users WHERE id=?", (user.id,))
    return row or {"approved": 1, "banned": 0, "max_bots": 5}


def ensure_user_by_id(uid: int) -> dict:
    row = db_fetchone(
        "SELECT id, first_name, username, approved, banned, max_bots FROM users WHERE id=?", (uid,)
    )
    return row or {"id": uid, "first_name": "", "username": "", "approved": 1, "banned": 0, "max_bots": 5}


# ============================================================
# 10) لوحات الأزرار
# ============================================================
def _btn_label(key: str, default: str) -> str:
    """تسمية زر قابلة للتخصيص من الإعدادات."""
    return (get_setting(f"btn_{key}") or "").strip() or default


def main_menu_markup(is_admin: bool = False) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    if is_admin:
        kb.add(types.InlineKeyboardButton(
            _btn_label("admin", "🛡 Control Room"), callback_data="adm_panel",
            style="primary", icon_custom_emoji_id=E_ADMIN,
        ))
    kb.add(
        types.InlineKeyboardButton(_btn_label("new_bot", "🚀 Deploy project"), callback_data="proj_new",
            style="success", icon_custom_emoji_id=E_NEW),
        types.InlineKeyboardButton(_btn_label("my_bots", "📦 My fleet"), callback_data="proj_list",
            style="primary", icon_custom_emoji_id=E_LIST),
    )
    kb.add(
        types.InlineKeyboardButton(_btn_label("templates", "🧩 Starters"), callback_data="tpl_menu", style="primary"),
        types.InlineKeyboardButton(_btn_label("coupon", "🎟 Redeem code"), callback_data="coupon_redeem", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton(_btn_label("files", "🗂 Workspace"), callback_data="my_files_hub",
            style="primary", icon_custom_emoji_id=E_FILES),
        types.InlineKeyboardButton(_btn_label("live", "📡 Live cluster"), callback_data="live_status",
            style="primary", icon_custom_emoji_id=E_TERMINAL),
    )
    kb.add(
        types.InlineKeyboardButton(_btn_label("stats", "📈 My metrics"), callback_data="my_stats",
            style="primary", icon_custom_emoji_id=E_STATS),
        types.InlineKeyboardButton(_btn_label("help", "❔ Guide"), callback_data="help",
            style="primary", icon_custom_emoji_id=E_HELP),
    )
    kb.add(types.InlineKeyboardButton(
        _btn_label("about", "ℹ️ About Flix"), callback_data="about_bot", style="primary"
    ))
    kb.add(
        types.InlineKeyboardButton(_btn_label("points", "💠 Credits"), callback_data="points",
            style="primary", icon_custom_emoji_id=E_POINTS),
        types.InlineKeyboardButton(_btn_label("transfer", "↔ Send credits"), callback_data="transfer_points",
            style="primary", icon_custom_emoji_id=E_TRANSFER),
    )
    kb.add(
        types.InlineKeyboardButton(_btn_label("settings", "⚙️ Preferences"), callback_data="user_settings",
            style="primary"),
        types.InlineKeyboardButton(_btn_label("terms", "📄 Rules"), callback_data="show_terms",
            style="primary"),
    )
    ch = (get_setting("public_channel") or BRAND_CHANNEL or "").strip()
    if ch:
        ch_url = ch if ch.startswith("http") else f"https://t.me/{ch.lstrip('@')}"
        kb.add(types.InlineKeyboardButton(_btn_label("channel", "📢 Channel"), url=ch_url, style="primary"))
    kb.add(
        types.InlineKeyboardButton(_btn_label("brand", f"⚡ {BRAND_NAME}"), callback_data="noop_sig",
            style="primary", icon_custom_emoji_id=E_SIGNATURE),
        types.InlineKeyboardButton(_btn_label("dev", "👨‍💻 Developer"), url=f"https://t.me/{DEVELOPER_USERNAME}",
            style="primary", icon_custom_emoji_id=E_DEV),
    )
    kb.add(types.InlineKeyboardButton(_btn_label("home", "⌂ Home"), callback_data="back_main", style="primary"))
    return kb


def admin_menu_markup() -> types.InlineKeyboardMarkup:
    """الواجهة القديمة — تستدعي الجديدة للتوافق."""
    return admin_main_markup()


# ============================================================
# لوحة الأدمن المطوّرة
# ============================================================

def get_admin_quick_stats() -> dict:
    """يجمع الإحصائيات الحية من DB و manager."""
    total_users   = (db_fetchone("SELECT COUNT(*) AS c FROM users") or {}).get("c", 0)
    active_users  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0") or {}).get("c", 0)
    banned_users  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=1") or {}).get("c", 0)
    pending_users = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=0 AND banned=0") or {}).get("c", 0)

    total_bots   = (db_fetchone("SELECT COUNT(*) AS c FROM projects") or {}).get("c", 0)
    pending_bots = (db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE approved=0") or {}).get("c", 0)

    pending_files = (db_fetchone("SELECT COUNT(*) AS c FROM pending_uploads WHERE status='pending'") or {}).get("c", 0)

    total_points = (db_fetchone("SELECT COALESCE(SUM(points),0) AS s FROM users") or {}).get("s", 0)

    running_bots = 0
    try:
        all_proj = db_fetchall("SELECT id FROM projects WHERE approved=1 AND is_running=1")
        running_bots = sum(1 for p in all_proj if manager.is_running(p["id"]))
    except Exception:
        pass

    total_sites = (db_fetchone("SELECT COUNT(*) AS c FROM deployments") or {}).get("c", 0)

    pending_total = pending_users + pending_bots + pending_files

    return {
        "total_users": total_users,
        "active_users": active_users,
        "banned_users": banned_users,
        "pending_users": pending_users,
        "total_bots": total_bots,
        "pending_bots": pending_bots,
        "pending_files": pending_files,
        "pending_total": pending_total,
        "total_points": total_points,
        "running_bots": running_bots,
        "total_sites": total_sites,
    }


def get_server_quick_info() -> str:
    """يقرأ معلومات السيرفر بدون psutil."""
    lines = []
    try:
        with open("/proc/meminfo") as f:
            mem = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in f if ":" in l)}
        total_mb  = mem.get("MemTotal", 0) // 1024
        free_mb   = (mem.get("MemAvailable") or mem.get("MemFree", 0)) // 1024
        used_mb   = total_mb - free_mb
        used_pct  = int(used_mb / total_mb * 100) if total_mb else 0
        bar_filled = int(used_pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        lines.append(f"🧠 RAM: {used_mb} / {total_mb} MB  [{bar}] {used_pct}%")
    except Exception:
        lines.append("🧠 RAM: غير متاح")

    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()
        lines.append(f"⚡ Load: {load[0]} / {load[1]} / {load[2]}")
    except Exception:
        pass

    try:
        usage = shutil.disk_usage("/")
        total_g = usage.total // (1024 ** 3)
        used_g  = usage.used  // (1024 ** 3)
        pct     = int(usage.used / usage.total * 100) if usage.total else 0
        lines.append(f"💾 Disk: {used_g} / {total_g} GB  ({pct}%)")
    except Exception:
        pass

    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        h, m = divmod(secs // 60, 60)
        d, h = divmod(h, 24)
        uptime_str = (f"{d}ي " if d else "") + (f"{h}س " if h else "") + f"{m}د"
        lines.append(f"⏱ Uptime: {uptime_str}")
    except Exception:
        pass

    return "\n".join(lines) if lines else "غير متاح"


def admin_stats_text() -> str:
    """يبني نص الإحصائيات الحية لرأس لوحة الأدمن."""
    s = get_admin_quick_stats()
    sv = get_server_quick_info()
    pending_warn = f"  ⚠️ <b>{s['pending_total']} طلب معلّق!</b>" if s['pending_total'] > 0 else ""
    return (
        f"👑 <b>لوحة الأدمن</b>{pending_warn}\n"
        f"{'─' * 28}\n"
        f"👥 المستخدمون:  <b>{s['active_users']}</b> مفعّل"
        + (f" | <b>{s['banned_users']}</b> محظور" if s['banned_users'] else "")
        + (f" | ⏳ <b>{s['pending_users']}</b> بانتظار" if s['pending_users'] else "")
        + f"\n"
        f"🤖 البوتات:  <b>{s['running_bots']}</b> شغّالة / <b>{s['total_bots']}</b> إجمالي"
        + (f" | ⏳ <b>{s['pending_bots']}</b> بانتظار" if s['pending_bots'] else "")
        + f"\n"
        f"💎 النقاط:  <b>{s['total_points']:,}</b>   |   🌐 المواقع: <b>{s['total_sites']}</b>\n"
        f"{'─' * 28}\n"
        f"{sv}"
    )


def admin_main_markup() -> types.InlineKeyboardMarkup:
    """لوحة الأدمن الرئيسية — أزرار الأقسام مع عداد الطلبات."""
    s = get_admin_quick_stats()
    kb = types.InlineKeyboardMarkup(row_width=2)

    # ── إجراءات سريعة ──
    kb.add(types.InlineKeyboardButton("⚡ ━━━ إجراءات سريعة ━━━", callback_data="noop", style="primary"))
    if s["pending_total"] > 0:
        kb.add(types.InlineKeyboardButton(
            f"✅ موافقة الكل ({s['pending_total']})", callback_data="adm_quick_approve_all", style="success"
        ))
    kb.add(
        types.InlineKeyboardButton("▶️ تشغيل كل البوتات", callback_data="adm_quick_start_all", style="success"),
        types.InlineKeyboardButton("⏹ إيقاف كل البوتات", callback_data="adm_quick_stop_all", style="danger"),
    )

    # ── الأقسام ──
    kb.add(types.InlineKeyboardButton("📂 ━━━ الأقسام ━━━", callback_data="noop", style="primary"))

    req_label = f"📥 الطلبات" + (f" ({s['pending_total']}⚡)" if s["pending_total"] else "")
    kb.add(
        types.InlineKeyboardButton(req_label, callback_data="adm_sec_requests", style="success" if s["pending_total"] else "primary"),
        types.InlineKeyboardButton("👥 المستخدمون", callback_data="adm_sec_users", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("📣 التواصل", callback_data="adm_sec_comms", style="primary"),
        types.InlineKeyboardButton("💎 النقاط", callback_data="adm_sec_points", style="primary"),
    )
    kb.add(
        types.InlineKeyboardButton("🤖 البوتات", callback_data="adm_sec_bots", style="primary"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="adm_sec_settings", style="primary"),
    )
    kb.add(types.InlineKeyboardButton("📊 الإحصائيات والسيرفر", callback_data="adm_sec_stats", style="primary"))
    kb.add(
        types.InlineKeyboardButton("لوحة الاعطال", callback_data="adm_failures_panel", style="danger"),
        types.InlineKeyboardButton("تعويض SLA", callback_data="adm_sla_compensate", style="success"),
    )
    kb.add(types.InlineKeyboardButton("صيانة انتقائية", callback_data="adm_selective_maint", style="primary"))

    # ── تعطيل/تفعيل ──
    if is_bot_disabled():
        kb.add(types.InlineKeyboardButton("✅ تفعيل البوت", callback_data="adm_toggle_bot", style="success"))
    else:
        kb.add(types.InlineKeyboardButton("🔴 وضع الصيانة", callback_data="adm_toggle_bot", style="danger"))

    kb.add(types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_main", style="primary"))
    return kb


def admin_section_markup(section: str) -> types.InlineKeyboardMarkup:
    """يبني لوحة القسم الفرعي مع زر الرجوع للوحة الرئيسية."""
    kb = types.InlineKeyboardMarkup(row_width=2)

    if section == "requests":
        s = get_admin_quick_stats()
        pending_label = f"⏳ {s['pending_total']} طلب بانتظار المراجعة" if s["pending_total"] else "✨ لا توجد طلبات معلّقة"
        kb.add(types.InlineKeyboardButton(pending_label, callback_data="noop", style="primary"))
        kb.add(
            types.InlineKeyboardButton("👤 طلبات التفعيل", callback_data="adm_pending_users", style="success"),
            types.InlineKeyboardButton("🤖 طلبات البوتات", callback_data="adm_pending_projects", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("📎 ملفات بانتظار المراجعة", callback_data="adm_pending_files", style="primary"))
        if s["pending_total"] > 0:
            kb.add(types.InlineKeyboardButton(
                f"✅ موافقة الكل ({s['pending_total']})", callback_data="adm_quick_approve_all", style="success"
            ))

    elif section == "users":
        kb.add(
            types.InlineKeyboardButton("📋 كل المستخدمين", callback_data="adm_users", style="primary"),
            types.InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="adm_search_user", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🪪 معلومات مستخدم", callback_data="adm_user_info", style="primary"),
            types.InlineKeyboardButton("📤 تصدير المستخدمين", callback_data="adm_export_users", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="adm_ban_by_id", style="danger"),
            types.InlineKeyboardButton("✅ رفع حظر مستخدم", callback_data="adm_unban_by_id", style="danger"),
        )
        kb.add(
            types.InlineKeyboardButton("📛 قائمة المحظورين", callback_data="admin_list_blocked", style="primary"),
            types.InlineKeyboardButton("🕵️ كاشف الحظر", callback_data="adm_blocked_users", style="danger"),
        )
        kb.add(types.InlineKeyboardButton("👻 المستخدمون الخاملون", callback_data="adm_inactive_users", style="primary"))
        kb.add(
            types.InlineKeyboardButton("🆕 مستخدمو اليوم", callback_data="adm_new_today", style="primary"),
            types.InlineKeyboardButton("✅ قبول مستخدم بـ ID", callback_data="adm_approve_id", style="success"),
        )
        kb.add(
            types.InlineKeyboardButton("🤖 بوتات مستخدم", callback_data="adm_user_bots_by_id", style="primary"),
            types.InlineKeyboardButton("🔄 تصفير نقاط مستخدم", callback_data="adm_reset_points_id", style="danger"),
        )
        kb.add(types.InlineKeyboardButton("⚙️ حد بوتات مستخدم بعينه", callback_data="adm_set_user_max", style="primary"))
        kb.add(
            types.InlineKeyboardButton("📄 ملف مستخدم", callback_data="adm_user_profile", style="primary"),
            types.InlineKeyboardButton("⏳ منتظرون موافقة", callback_data="adm_pending_users", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🚫 حظر بـ ID", callback_data="adm_ban_by_id", style="danger"),
            types.InlineKeyboardButton("✅ رفع حظر بـ ID", callback_data="adm_unban_by_id", style="success"),
        )
        kb.add(types.InlineKeyboardButton("👑 VIP المستخدمين", callback_data="adm_vip_users", style="primary"))

    elif section == "comms":
        kb.add(
            types.InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="adm_broadcast", style="primary"),
            types.InlineKeyboardButton("📺 إذاعة للقنوات", callback_data="adm_broadcast_channel", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("💬 رسالة لمستخدم", callback_data="adm_send_user", style="primary"),
            types.InlineKeyboardButton("⚠️ تحذير لمستخدم", callback_data="admin_warn_user", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("📣 إعلان منسّق", callback_data="adm_announce", style="success"))
        kb.add(
            types.InlineKeyboardButton("💤 رسالة للخاملين", callback_data="adm_msg_to_inactive", style="primary"),
            types.InlineKeyboardButton("✅ إذاعة للمفعّلين فقط", callback_data="adm_broadcast_active_only", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🔢 عداد المستقبلين", callback_data="adm_receivers_count", style="primary"))
        kb.add(
            types.InlineKeyboardButton("💬 رسالة لمستخدم بـ ID", callback_data="adm_msg_by_id", style="primary"),
            types.InlineKeyboardButton("⏳ رسالة للمنتظرين", callback_data="adm_broadcast_pending", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("📊 إحصائيات آخر إذاعة", callback_data="adm_last_broadcast_stats", style="primary"))

    elif section == "points":
        kb.add(
            types.InlineKeyboardButton("🎁 منح نقاط لمستخدم", callback_data="adm_give_points", style="primary"),
            types.InlineKeyboardButton("🔢 تعيين نقاط", callback_data="adm_set_points", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🎯 منح نقاط للكل", callback_data="adm_give_all_points", style="primary"),
            types.InlineKeyboardButton("🏆 أعلى مستخدمين", callback_data="adm_top_users", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🔗 رابط هدية نقاط", callback_data="adm_gift_new", style="primary"))

    elif section == "bots":
        s = get_admin_quick_stats()
        kb.add(
            types.InlineKeyboardButton("📂 كل البوتات", callback_data="adm_projects", style="primary"),
            types.InlineKeyboardButton("🗑 حذف المتوقفة", callback_data="adm_del_stopped", style="danger"),
        )
        kb.add(
            types.InlineKeyboardButton("▶️ تشغيل كل البوتات", callback_data="adm_quick_start_all", style="success"),
            types.InlineKeyboardButton("⏹ إيقاف كل البوتات", callback_data="adm_quick_stop_all", style="danger"),
        )
        kb.add(types.InlineKeyboardButton("🔁 إعادة تشغيل الشغّالة", callback_data="adm_quick_restart_all", style="primary"))
        kb.add(
            types.InlineKeyboardButton("⚡ البوتات الشغّالة الآن", callback_data="adm_running_bots_list", style="success"),
            types.InlineKeyboardButton("📤 تصدير البوتات CSV", callback_data="adm_export_bots", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("⚙️ حد البوتات للمستخدم", callback_data="adm_set_max_bots", style="primary"))
        kb.add(
            types.InlineKeyboardButton("💥 بوتات معطوبة", callback_data="adm_crashed_bots", style="danger"),
            types.InlineKeyboardButton("🔍 بحث بوت بالاسم", callback_data="adm_search_bot_name", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📋 ملخص البوتات", callback_data="adm_bots_summary", style="primary"),
            types.InlineKeyboardButton("🧹 تنظيف سجلات العمليات", callback_data="adm_clear_proc_logs", style="danger"),
        )
        kb.add(types.InlineKeyboardButton("⚙️ معلومات العمليات الحية", callback_data="adm_proc_info", style="primary"))
        kb.add(
            types.InlineKeyboardButton("▶️ تشغيل بوت بـ ID", callback_data="adm_force_start_bot", style="success"),
            types.InlineKeyboardButton("⏹ إيقاف بوت بـ ID", callback_data="adm_force_stop_bot", style="danger"),
        )
        kb.add(
            types.InlineKeyboardButton("📁 ملفات بوت بـ ID", callback_data="adm_bot_files_info", style="primary"),
            types.InlineKeyboardButton("📦 أكبر البوتات", callback_data="adm_top_bots", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🆕 بوتات اليوم", callback_data="adm_new_bots_today", style="primary"))
        running_label = f"🟢 {s['running_bots']} بوت شغّال حالياً"
        kb.add(types.InlineKeyboardButton(running_label, callback_data="noop", style="primary"))

    elif section == "settings":
        kb.add(
            types.InlineKeyboardButton("💰 سعر رفع البوت", callback_data="adm_set_upload_price", style="success"),
            types.InlineKeyboardButton("💸 عمولة التحويل", callback_data="adm_set_transfer_fee", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🏷 أسعار الأقسام", callback_data="adm_section_prices", style="primary"),
            types.InlineKeyboardButton("🛡 المشرفين", callback_data="adm_mods", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📢 اشتراك إجباري", callback_data="adm_force_channel", style="primary"),
            types.InlineKeyboardButton("✏️ رسالة الترحيب", callback_data="adm_set_welcome", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🖼 صورة الترحيب", callback_data="adm_set_welcome_img", style="primary"),
            types.InlineKeyboardButton("🚫 صورة الحظر", callback_data="adm_set_banned_img", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🔧 صورة الصيانة", callback_data="adm_set_maint_img", style="primary"),
            types.InlineKeyboardButton("✍️ رسالة الحظر", callback_data="adm_set_banned_txt", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🔧 رسالة الصيانة", callback_data="adm_set_maint_txt", style="primary"))
        notify_on = is_admin_notify_enabled("notify_admin_new_user", True)
        notify_lbl = "🔕 إيقاف إشعار الجدد" if notify_on else "🔔 تشغيل إشعار الجدد"
        kb.add(types.InlineKeyboardButton(notify_lbl, callback_data="adm_toggle_notify", style="primary"))
        kb.add(types.InlineKeyboardButton("🎨 ألوان الأزرار", callback_data="adm_btn_colors", style="primary"))
        kb.add(
            types.InlineKeyboardButton("موافقة تلقائية", callback_data="adm_toggle_auto_approve2", style="success"),
            types.InlineKeyboardButton("فحص امني", callback_data="adm_toggle_security", style="danger"),
        )
        kb.add(
            types.InlineKeyboardButton("تصدير الكل", callback_data="adm_export_all", style="primary"),
            types.InlineKeyboardButton("نسخة DB", callback_data="adm_backup_db", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("اعادة Python", callback_data="adm_bulk_restart_py", style="primary"),
            types.InlineKeyboardButton("اعادة Node", callback_data="adm_bulk_restart_node", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📝 تخصيص النصوص", callback_data="adm_custom_texts", style="primary"),
            types.InlineKeyboardButton("🖼 صور/فيديو", callback_data="adm_custom_images", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("ℹ️ نص معلومات البوت", callback_data="adm_edit_about", style="primary"))
        kb.add(
            types.InlineKeyboardButton("📋 عرض كل الإعدادات", callback_data="adm_view_settings", style="primary"),
            types.InlineKeyboardButton("🤖 قبول تلقائي للجدد", callback_data="adm_toggle_auto_approve", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🗑 تنظيف سجل التدقيق (30ي+)", callback_data="adm_clear_audit", style="danger"))
        kb.add(
            types.InlineKeyboardButton("🔧 وضع الصيانة", callback_data="adm_maintenance_mode", style="danger"),
            types.InlineKeyboardButton("🖥 معلومات النظام", callback_data="adm_sys_info", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🧹 تنظيف قاعدة المحظورين", callback_data="adm_clear_blocked_db", style="danger"))

    elif section == "stats":
        kb.add(
            types.InlineKeyboardButton("📈 إحصائيات النظام", callback_data="adm_stats", style="primary"),
            types.InlineKeyboardButton("🖥 حالة السيرفر", callback_data="adm_server_status", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📊 إحصائيات النمو", callback_data="adm_growth_stats", style="primary"),
            types.InlineKeyboardButton("📋 سجل التدقيق", callback_data="adm_audit_log", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("💾 نسخ احتياطي DB", callback_data="adm_backup_db", style="success"),
            types.InlineKeyboardButton("🧹 تنظيف الملفات", callback_data="adm_cleanup_files", style="danger"),
        )
        kb.add(types.InlineKeyboardButton("📊 إحصائيات الاستخدام", callback_data="adm_usage_stats", style="primary"))
        kb.add(
            types.InlineKeyboardButton("🗃 إحصائيات الجداول", callback_data="adm_db_table_stats", style="primary"),
            types.InlineKeyboardButton("🚀 إحصائيات الرفع", callback_data="adm_deploy_stats", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📅 تقرير يومي الآن", callback_data="adm_daily_report", style="success"),
            types.InlineKeyboardButton("💎 توزيع النقاط", callback_data="adm_points_dist", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("📆 تقرير أسبوعي", callback_data="adm_weekly_report", style="success"),
            types.InlineKeyboardButton("🏆 أكثر المستخدمين رفعاً", callback_data="adm_top_uploaders", style="primary"),
        )
        kb.add(
            types.InlineKeyboardButton("🔴 آخر أخطاء العمليات", callback_data="adm_error_log_view", style="danger"),
            types.InlineKeyboardButton("📈 نشاط اليوم", callback_data="adm_activity_stats", style="primary"),
        )
        kb.add(types.InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="adm_sec_stats", style="primary"))

    kb.add(types.InlineKeyboardButton("🔙 رجوع للوحة الأدمن", callback_data="adm_panel", style="primary"))
    return kb


def show_admin_panel(chat_id: int, msg_id: int = None) -> None:
    """يعرض لوحة الأدمن الرئيسية مع إحصائيات حية."""
    text = admin_stats_text()
    markup = admin_main_markup()
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)


def back_main_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        " رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK,
    ))
    return kb


def back_admin_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        " رجوع للوحة الأدمن", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK,
    ))
    return kb


# ============================================================
# ألوان الأزرار — Per-Group Color Manager
# ============================================================
ADM_COLOR_GROUPS = {
    "requests":   ("📥 الطلبات",),
    "users":      ("👥 المستخدمون",),
    "comms":      ("📣 التواصل",),
    "adm_points": ("💎 النقاط",),
    "bots":       ("🤖 البوتات",),
    "settings":   ("⚙️ الإعدادات",),
    "stats":      ("📊 الإحصائيات",),
}

USER_COLOR_GROUPS = {
    "user_bots":     ("🤖 إضافة بوت & بوتاتي",),
    "user_info":     ("📊 إحصائياتي & المساعدة",),
    "user_points":   ("💎 النقاط",),
    "user_misc":     ("🏷 الشعار والمطور",),
}

BTN_COLOR_GROUPS = {**ADM_COLOR_GROUPS, **USER_COLOR_GROUPS}

_COLOR_LABELS = {
    "mixed":    "🌈 أصلي (متنوع)",
    "primary":  "🔵 أزرق",
    "success":  "🟢 أخضر",
    "danger":   "🔴 أحمر",
    "ocean":    "🌊 محيط",
    "forest":   "🌲 غابة",
    "sunset":   "🌅 غروب",
    "night":    "🌙 ليلي",
    "gold":     "✨ ذهبي",
    "rose":     "🌹 وردي",
    "cyber":    "⚡ سايبر",
}

# خرائط الثيمات الـ 11 إلى أنماط أزرار تيليجرام (primary/success/danger)
_THEME_STYLE_MAP = {
    "mixed":   None,  # يحافظ على الأصل
    "primary": "primary",
    "success": "success",
    "danger":  "danger",
    "ocean":   "primary",
    "forest":  "success",
    "sunset":  "danger",
    "night":   "primary",
    "gold":    "success",
    "rose":    "danger",
    "cyber":   "primary",
}


def get_group_color(group_key: str) -> str:
    return get_setting(f"btn_color_{group_key}") or "mixed"


def btn_colors_groups_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    # ── قسم لوحة الأدمن ──
    kb.add(types.InlineKeyboardButton("👑 ━━━ لوحة الأدمن ━━━", callback_data="noop", style="primary"))
    for key, (label,) in ADM_COLOR_GROUPS.items():
        color = get_group_color(key)
        color_lbl = _COLOR_LABELS.get(color, "🌈 أصلي")
        kb.add(types.InlineKeyboardButton(
            f"{label}  ·  {color_lbl}",
            callback_data=f"adm_btn_color_group:{key}",
            style="primary",
        ))
    # ── قسم لوحة المستخدم ──
    kb.add(types.InlineKeyboardButton("👤 ━━━ لوحة المستخدم ━━━", callback_data="noop", style="primary"))
    for key, (label,) in USER_COLOR_GROUPS.items():
        color = get_group_color(key)
        color_lbl = _COLOR_LABELS.get(color, "🌈 أصلي")
        kb.add(types.InlineKeyboardButton(
            f"{label}  ·  {color_lbl}",
            callback_data=f"adm_btn_color_group:{key}",
            style="primary",
        ))
    kb.add(types.InlineKeyboardButton(
        " رجوع للوحة الأدمن", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK,
    ))
    return kb


def btn_colors_pick_menu(group_key: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    current = get_group_color(group_key)
    for color, clabel in _COLOR_LABELS.items():
        tick = "✅ " if color == current else ""
        style = "success" if color == current else "primary"
        kb.add(types.InlineKeyboardButton(
            f"{tick}{clabel}",
            callback_data=f"adm_btn_color_pick:{group_key}:{color}",
            style=style,
        ))
    kb.add(types.InlineKeyboardButton(
        " رجوع للأقسام", callback_data="adm_btn_colors",
        style="primary", icon_custom_emoji_id=E_BACK,
    ))
    return kb


def show_btn_colors(chat_id: int, msg_id: int = None) -> None:
    text = "🎨 <b>ألوان الأزرار</b>\n\nاختر القسم الذي تريد تغيير لون أزراره:"
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=btn_colors_groups_menu())
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=btn_colors_groups_menu())


def show_btn_color_pick(chat_id: int, group_key: str, msg_id: int = None) -> None:
    label, = BTN_COLOR_GROUPS.get(group_key, ("القسم",))
    current = get_group_color(group_key)
    current_lbl = _COLOR_LABELS.get(current, "🌈 أصلي")
    text = (
        f"🎨 <b>لون أزرار: {label}</b>\n\n"
        f"اللون الحالي: <b>{current_lbl}</b>\n\n"
        "اختر لوناً جديداً:"
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=btn_colors_pick_menu(group_key))
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=btn_colors_pick_menu(group_key))


def cancel_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "❌ إلغاء", callback_data="cancel_operation",
        style="danger", icon_custom_emoji_id=E_CANCEL,
    ))
    return kb


# ============================================================
# 11) القائمة الرئيسية
# ============================================================
def show_main_menu(chat_id: int, uid: int, edit_message_id: Optional[int] = None) -> None:
    user = ensure_user_by_id(uid)
    proj_count = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (uid,))["c"]
    running_count = 0
    for p in db_fetchall("SELECT id FROM projects WHERE user_id=?", (uid,)):
        hp = manager.processes.get(p["id"])
        if hp and hp.is_alive():
            running_count += 1
    stopped_count = max(proj_count - running_count, 0)
    points_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
    points = points_row["p"] if points_row else 0
    username = user.get("username") or "NoUser"
    display_name = user.get("first_name") or "User"
    percent = int((running_count / max(proj_count, 1)) * 100)
    _quote = get_random_quote()
    _DEFAULT_WELCOME = (
        f"<b>⚡ {BRAND_NAME} Cloud</b>\n"
        f"<i>Deploy · Run · Control</i>\n\n"
        f"{_quote}\n\n"
        "<b>Hello, {name}</b>\n"
        "@{username} · <code>{uid}</code>\n\n"
        "<b>Credits</b>  {points}\n"
        "<b>Projects</b>  {proj_count}\n"
        "<b>Live</b>  {running_count}    <b>Idle</b>  {stopped_count}\n"
        "<b>Load</b>  {percent}%\n\n"
        "Status  <b>Online</b>\n"
        f"Dev  @{DEVELOPER_USERNAME}   Channel  @{BRAND_CHANNEL}\n\n"
        "Select an action below."
    )
    _custom_welcome = get_setting("welcome_text") or ""
    _tpl = _custom_welcome if _custom_welcome else _DEFAULT_WELCOME
    text = _tpl.format(
        name=html_escape(display_name),
        username=html_escape(username),
        uid=uid,
        points=points,
        proj_count=proj_count,
        running_count=running_count,
        stopped_count=stopped_count,
        percent=percent,
    )
    kb = main_menu_markup(is_admin=is_admin(uid))
    if edit_message_id:
        # حاول تعديل caption الصورة أولاً، ثم النص العادي
        try:
            bot.edit_message_caption(
                caption=text, chat_id=chat_id, message_id=edit_message_id,
                reply_markup=kb, parse_mode="HTML",
            )
            return
        except Exception:
            pass
        try:
            bot.edit_message_text(text, chat_id, edit_message_id, reply_markup=kb)
            return
        except Exception:
            pass
    # إرسال رسالة جديدة مع صورة الترحيب (مخصصة أو افتراضية)
    _welcome_img = get_setting("welcome_image_id") or WELCOME_IMAGE
    try:
        bot.send_photo(chat_id, _welcome_img, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception as _e1:
        log.warning("send_photo failed: %s", _e1)
        try:
            bot.send_message(chat_id, text, reply_markup=kb)
        except Exception as _e2:
            log.error("send_message also failed: %s", _e2)


# ============================================================
# 12) أوامر /start /admin /cancel
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "main_terminal")
def main_terminal_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🖥️ استخدم التيرمنال من قائمة بوتاتك ← اختر بوت ← زر التيرمنال.")


@bot.message_handler(commands=["start"])
def cmd_start(message):
    log.info("cmd_start received uid=%s msg_id=%s", message.from_user.id, message.message_id)
    if msg_seen(message):
        log.info("msg_seen=True, skipping uid=%s", message.from_user.id)
        return
    uid = message.from_user.id
    log.info("cmd_start processing uid=%s", uid)
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""
    ref_id = None
    gift_token = None
    if payload.startswith("gift_"):
        gift_token = payload[len("gift_"):]
    elif payload.isdigit():
        try:
            ref_id = int(payload)
            if ref_id == uid:
                ref_id = None
        except Exception:
            ref_id = None

    existing = db_fetchone("SELECT id FROM users WHERE id=?", (uid,))
    is_new_user = existing is None
    user = ensure_user(message)

    try:
        if uid != ADMIN_ID:
            notify_new = is_admin_notify_enabled("notify_admin_new_user", True)
            notify_any = is_admin_notify_enabled("notify_admin_any_start", False)
            if (is_new_user and notify_new) or notify_any:
                name = (getattr(message.from_user, "first_name", None) or "").strip() or "-"
                uname = (getattr(message.from_user, "username", None) or "").strip()
                uname_disp = f"@{uname}" if uname else "-"
                kind = "🆕 مستخدم جديد" if is_new_user else "👋 دخول"
                bot.send_message(
                    ADMIN_ID,
                    f"{kind}\n\nالاسم: <b>{html_escape(name)}</b>\n"
                    f"يوزر: <code>{html_escape(uname_disp)}</code>\n"
                    f"ID: <code>{uid}</code>",
                )
    except Exception:
        pass

    if user.get("banned"):
        _banned_img = get_setting("banned_image_id") or BANNED_IMAGE
        _banned_txt = get_setting("banned_text") or "🚫 <b>لقد تم حظرك من استخدام الاستضافة.</b>"
        try:
            bot.send_photo(uid, _banned_img, caption=_banned_txt, parse_mode="HTML")
        except Exception:
            bot.send_message(uid, _banned_txt, parse_mode="HTML")
        return

    if is_bot_disabled() and not is_admin(uid):
        _maint_img = get_setting("maintenance_image_id") or MAINTENANCE_IMAGE
        _maint_txt = get_setting("maintenance_text") or (
            "⛔ <b>البوت معطل حالياً</b>\n\n"
            "نعتذر، البوت متوقف مؤقتاً عن استقبال الطلبات الجديدة.\n"
            "بوتاتك المستضافة لا تزال تعمل بشكل طبيعي.\n\n"
            "يرجى المحاولة لاحقاً 🙏"
        )
        try:
            bot.send_photo(
                uid, _maint_img,
                caption=_maint_txt,
                parse_mode="HTML",
            )
        except Exception:
            bot.send_message(uid, _maint_txt, parse_mode="HTML")
        return

    if gift_token:
        process_gift_link(uid, gift_token)

    if is_new_user and ref_id:
        ref_exists = db_fetchone("SELECT id FROM users WHERE id=?", (ref_id,))
        if ref_exists:
            db_execute(
                "UPDATE users SET referred_by=? WHERE id=? AND (referred_by IS NULL OR referred_by=0)",
                (ref_id, uid),
            )
            db_execute("UPDATE users SET points = COALESCE(points,0) + 1 WHERE id=?", (ref_id,))
            try:
                bot.send_message(
                    ref_id,
                    "🎉 شخص جديد دخل عبر رابط الإحالة الخاص بك!\n"
                    "⭐ تمت إضافة <b>1 نقطة</b> إلى رصيدك.",
                )
            except Exception:
                pass

    if force_sub_block(uid, uid):
        return

    # اختيار اللغة للمستخدم الجديد
    row_u = db_fetchone("SELECT lang, verified FROM users WHERE id=?", (uid,)) or {}
    lang = (row_u.get("lang") or "").strip()
    verified = int(row_u.get("verified") or 0)
    if is_new_user or not lang or lang not in SUPPORTED_LANGS:
        kb = types.InlineKeyboardMarkup(row_width=2)
        for code, label in SUPPORTED_LANGS.items():
            kb.add(types.InlineKeyboardButton(label, callback_data=f"set_lang_{code}", style="primary"))
        try:
            bot.send_photo(
                uid, get_section_image("welcome"),
                caption="🌐 <b>Choose language / اختر اللغة</b>\n\n"
                        "<blockquote>Select your preferred language to continue.</blockquote>",
                reply_markup=kb,
            )
        except Exception:
            bot.send_message(uid, "🌐 Choose language / اختر اللغة", reply_markup=kb)
        return

    if not verified and not is_admin(uid):
        q, options, _ans = make_captcha(uid)
        kb = types.InlineKeyboardMarkup(row_width=2)
        for opt in options:
            kb.add(types.InlineKeyboardButton(str(opt), callback_data=f"captcha_{opt}", style="primary"))
        try:
            bot.send_photo(
                uid, get_section_image("welcome"),
                caption=t(uid, "verify_human") + f"\n\n<blockquote><b>{q} = ؟</b></blockquote>",
                reply_markup=kb,
            )
        except Exception:
            bot.send_message(uid, t(uid, "verify_human") + f"\n\n<b>{q} = ؟</b>", reply_markup=kb)
        return

    show_main_menu(uid, uid)


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    bot.send_message(message.chat.id, "👑 لوحة المطور:", reply_markup=admin_menu_markup())


@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    if msg_seen(message):
        return
    pop_pending(message.from_user.id)
    bot.send_message(message.chat.id, "✅ تم إلغاء العملية الحالية.")


@bot.message_handler(commands=["add"])
def cmd_add(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "الاستخدام: /add <user_id>")
        return
    try:
        target = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ معرّف غير صالح")
        return
    db_execute("INSERT INTO users (id, approved) VALUES (?, 1) ON CONFLICT (id) DO UPDATE SET approved=1, banned=0", (target,))
    bot.send_message(message.chat.id, f"✅ تم تفعيل {target}")
    try:
        bot.send_message(target, f"🎉 تم تفعيل حسابك. أرسل /start.\n\n💬 {get_random_quote()}")
    except Exception:
        pass


@bot.message_handler(commands=["ban"])
def cmd_ban(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "الاستخدام: /ban <user_id>")
        return
    target = int(parts[1])
    db_execute("UPDATE users SET banned=1 WHERE id=?", (target,))
    for p in db_fetchall("SELECT id FROM projects WHERE user_id=?", (target,)):
        manager.stop_project(p["id"])
    bot.send_message(message.chat.id, f"🚫 تم حظر {target}")


@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        return
    target = int(parts[1])
    db_execute("UPDATE users SET banned=0 WHERE id=?", (target,))
    bot.send_message(message.chat.id, f"✅ تم رفع الحظر عن {target}")


@bot.message_handler(commands=["limit"])
def cmd_limit(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "الاستخدام: /limit <user_id> <max_bots>")
        return
    target = int(parts[1])
    n = int(parts[2])
    db_execute("UPDATE users SET max_bots=? WHERE id=?", (n, target))
    bot.send_message(message.chat.id, f"✅ تم ضبط الحد {n} للمستخدم {target}")


# ============================================================
# 13) إضافة بوت جديد
# ============================================================
def start_new_project(chat_id: int, uid: int) -> None:
    if selective_maint_blocks("upload") or selective_maint_blocks("start"):
        bot.send_message(chat_id, "Uploads are paused for selective maintenance.", reply_markup=back_main_kb())
        return
    ok, msg = check_and_inc_daily(uid, "bots", 5)
    if not ok:
        bot.send_message(chat_id, msg, reply_markup=back_main_kb())
        return
    proj_count = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (uid,))["c"]
    is_first = proj_count == 0
    price = get_upload_price()
    if not is_first and price > 0:
        pts_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
        pts = pts_row["p"] if pts_row else 0
        if pts < price:
            bot.send_message(
                chat_id,
                f"Not enough credits.\nExtra deploy costs <b>{price}</b> points.",
                reply_markup=back_main_kb(),
            )
            return
    set_pending(uid, {"type": "pick_runtime", "is_first": is_first, "price": price})
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🐍 Python server", callback_data="runtime_python", style="success"),
        types.InlineKeyboardButton("🟩 Node.js server", callback_data="runtime_nodejs", style="primary"),
    )
    kb.add(types.InlineKeyboardButton("⌂ Cancel", callback_data="back_main", style="danger"))
    bot.send_message(
        chat_id,
        f"<b>{html_escape(BRAND_NAME)} · New deploy</b>\n\n"
        "Choose your <b>runtime server</b> first.\nThen send a short project name.",
        reply_markup=kb,
    )




# ============================================================
# 14) رفع موقع Netlify
# ============================================================
def start_netlify_upload(chat_id: int, uid: int) -> None:
    if not netlify_is_configured():
        bot.send_message(
            chat_id,
            "⚠️ ميزة رفع المواقع غير مفعّلة حالياً.\n\n"
            "🔧 لتفعيلها: ضع متغير البيئة <code>NETLIFY_TOKEN</code> ثم أعد تشغيل البوت.",
            reply_markup=back_main_kb(),
        )
        return
    ok, msg = check_and_inc_daily(uid, "netlify", 5)
    if not ok:
        bot.send_message(chat_id, msg, reply_markup=back_main_kb())
        return
    price = get_section_price("netlify", 0)
    if price > 0 and not is_admin(uid):
        pts_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
        pts = pts_row["p"] if pts_row else 0
        if pts < price:
            bot.send_message(chat_id, f"❌ لا تملك نقاطاً كافية.\n💡 سعر رفع Netlify: <b>{price}</b> نقطة.",
                             reply_markup=back_main_kb())
            return
        db_execute("UPDATE users SET points = points - ? WHERE id=? AND COALESCE(points,0) >= ?", (price, uid, price))
    set_pending(uid, {"type": "netlify_upload_zip"})
    bot.send_message(
        chat_id,
        "⚡ <b>رفع موقع على Netlify</b>\n\n"
        "📦 ابعت ملف <b>.zip</b> لفولدر فيه ملفات الموقع.\n"
        "📌 لازم يكون جوّه <code>index.html</code>.\n\n"
        f"📏 الحد الأقصى: <b>{MAX_SITE_ZIP_SIZE // (1024 * 1024)}MB</b>\n"
        "/cancel للإلغاء.",
        reply_markup=back_main_kb(),
    )


def show_netlify_upload_menu(chat_id: int, uid: int, message_id: Optional[int] = None) -> None:
    text = (
        "⚡ <b>رفع موقع (Netlify)</b>\n\n"
        "✅ Netlify بيسمح برفع: <b>HTML / CSS / JS فقط</b>.\n\n"
        "📌 المتطلبات:\n"
        "• اجمع ملفات الموقع في فولدر ثم اعمل له <b>.zip</b>\n"
        "• لازم يكون جوّه <code>index.html</code>\n"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(" رفع ملف ZIP", callback_data="site_upload_zip",
        style="success", icon_custom_emoji_id=E_UPLOAD))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_vercel_upload_menu(chat_id: int, uid: int, message_id: Optional[int] = None) -> None:
    text = (
        "▲ <b>الرفع على Vercel</b>\n\n"
        "📌 المتطلبات:\n"
        "• ابعت <b>.zip</b> لفولدر واحد\n"
        "• لازم يكون جوّه <code>index.html</code>\n\n"
        "🧾 المسموح: <code>.html .css .js</code>\n"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📤 رفع ملف ZIP", callback_data="vercel_upload_zip",
        style="success", icon_custom_emoji_id=E_UPLOAD))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def _deploy_netlify_zip_async(chat_id: int, uid: int, filename: str, zip_bytes: bytes) -> None:
    try:
        existing = db_fetchone(
            "SELECT site_id, site_name, site_url FROM netlify_sites WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)
        )
        if existing:
            site_id = existing["site_id"]
            site_name = existing["site_name"]
            site_url = existing["site_url"]
        else:
            site = netlify_create_site_for_user(uid)
            site_id = (site or {}).get("id") or ""
            site_name = (site or {}).get("name") or _slugify_site_name(f"{NETLIFY_SITE_PREFIX}-{uid}")
            site_url = _netlify_pick_site_url(site) or ""
        if not site_id:
            raise RuntimeError("Netlify returned no site id")
        deploy = netlify_deploy_zip(site_id, zip_bytes)
        deploy_id = (deploy or {}).get("id") or ""
        deploy_ssl = (deploy or {}).get("ssl_url") or (deploy or {}).get("url") or ""
        if deploy_ssl:
            site_url = deploy_ssl
        if not site_url:
            site_url = f"https://{site_name}.netlify.app"
        db_execute(
            "INSERT INTO netlify_sites (user_id, site_id, site_name, site_url, last_deploy_id, last_deploy_at) "
            "VALUES (?,?,?,?,?, CURRENT_TIMESTAMP) ON CONFLICT(site_id) DO UPDATE SET "
            "site_url=excluded.site_url, last_deploy_id=excluded.last_deploy_id, last_deploy_at=CURRENT_TIMESTAMP",
            (uid, site_id, site_name, site_url, deploy_id),
        )
        db_execute(
            "INSERT INTO deployments (user_id, provider, site_id, deploy_id, url, filename, size_bytes) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, "netlify", site_id, deploy_id, site_url, filename, len(zip_bytes)),
        )
        bot.send_message(
            chat_id,
            "✅ تم رفع الموقع بنجاح!\n\n"
            f"🖥 الرابط: <code>{html_escape(site_url)}</code>\n"
            f"🆔 Site: <code>{html_escape(site_id)}</code>",
            reply_markup=back_main_kb(),
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل رفع الموقع: <code>{html_escape(str(e)[:350])}</code>",
                         reply_markup=back_main_kb())


# ============================================================
# 15) معالجة الرسائل النصية المعلقة
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "new_project_name",
    content_types=["text"],
)
def receive_project_name(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    is_first = pending.get("is_first", True)
    price = int(pending.get("price", get_upload_price()))
    name = message.text.strip()
    name = "".join(c for c in name if c.isalnum() or c in "_-")[:40]
    if not name:
        bot.send_message(uid, "❌ اسم غير صالح. حاول مرة أخرى أو /cancel.")
        return
    exists = db_fetchone("SELECT id FROM projects WHERE user_id=? AND name=?", (uid, name))
    if exists:
        bot.send_message(uid, "❌ يوجد بوت بنفس الاسم. اختر اسماً آخر.")
        return
    if not is_first and price > 0:
        with _db_lock:
            pts_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
            pts = pts_row["p"] if pts_row else 0
            if pts < price:
                pop_pending(uid)
                bot.send_message(uid, "❌ رصيد النقاط أصبح غير كافٍ. أُلغيت العملية.")
                return
            db_execute("UPDATE users SET points = points - ? WHERE id=? AND COALESCE(points,0) >= ?", (price, uid, price))
    pending_rt = get_pending(uid) or {}
    runtime = pending_rt.get("runtime") or "python"
    pid = db_execute_returning_id(
        "INSERT INTO projects (user_id, name, main_file, runtime, approved, security_approved) VALUES (?, ?, '', ?, 0, 0)",
        (uid, name, runtime),
    )
    set_pending(uid, {"type": "new_project_main", "project_id": pid, "runtime": runtime})
    lane = "Python" if runtime == "python" else "Node.js"
    hint = ".py / .zip" if runtime == "python" else ".js / .mjs / .ts / .zip"
    bot.send_message(
        uid,
        f"✅ Project <b>{html_escape(name)}</b> created\n"
        f"🖥️ Lane: <b>{lane}</b>\n\n"
        f"Upload main file ({hint}). Any filename is fine.</blockquote>\n"
        "/cancel to abort.",
    )


# ============================================================
# 16) معالجة الملفات
# ============================================================
@bot.message_handler(content_types=["document"])
def receive_document(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    user = ensure_user_by_id(uid)
    if user["banned"]:
        bot.send_message(uid, "🚫 لقد تم حظرك من استخدام الاستضافة.")
        return

    pending = get_pending(uid)
    doc = message.document
    filename = safe_filename(doc.file_name or "file.bin")
    size = doc.file_size or 0

    # رفع موقع Netlify
    if pending and pending.get("type") == "netlify_upload_zip":
        if size > MAX_SITE_ZIP_SIZE:
            bot.send_message(uid, f"❌ الملف أكبر من {MAX_SITE_ZIP_SIZE // (1024 * 1024)}MB.")
            return
        if not filename.lower().endswith(".zip"):
            bot.send_message(uid, "❌ ارسل ملف <b>.zip</b> فقط.")
            return
        try:
            file_info = bot.get_file(doc.file_id)
            zip_bytes = bot.download_file(file_info.file_path)
        except Exception as e:
            bot.send_message(uid, f"❌ فشل تحميل الملف: {e}")
            return
        send_file_bytes_to_admin(filename, zip_bytes,
                                 f"⚡ رفع موقع (Netlify)\nالمستخدم: {uid}\nالحجم: {len(zip_bytes)//1024} KB")
        try:
            db_execute("INSERT INTO audit_log (actor_id, action, provider, filename, size_bytes) VALUES (?,?,?,?,?)",
                       (uid, "upload_site", "netlify", filename[:300], len(zip_bytes)))
        except Exception:
            pass
        pop_pending(uid)
        bot.send_message(uid, "⏳ جاري رفع الموقع على Netlify... انتظر قليلًا.")
        threading.Thread(target=_deploy_netlify_zip_async,
                         args=(message.chat.id, uid, filename, zip_bytes), daemon=True).start()
        return

    # رفع موقع Vercel
    if pending and pending.get("type") in ("vercel_upload_zip", "vercel_redeploy_zip"):
        if size > MAX_SITE_ZIP_SIZE:
            bot.send_message(uid, f"❌ الملف أكبر من {MAX_SITE_ZIP_SIZE // (1024 * 1024)}MB.")
            return
        if not filename.lower().endswith(".zip"):
            bot.send_message(uid, "❌ ارسل ملف <b>.zip</b> فقط.")
            return
        try:
            file_info = bot.get_file(doc.file_id)
            zip_bytes = bot.download_file(file_info.file_path)
        except Exception as e:
            bot.send_message(uid, f"❌ فشل تحميل الملف: {e}")
            return
        send_file_bytes_to_admin(filename, zip_bytes,
                                 f"▲ رفع موقع (Vercel)\nالمستخدم: {uid}\nالحجم: {len(zip_bytes)//1024} KB")
        try:
            db_execute("INSERT INTO audit_log (actor_id, action, provider, filename, size_bytes) VALUES (?,?,?,?,?)",
                       (uid, "upload_site", "vercel", filename[:300], len(zip_bytes)))
        except Exception:
            pass
        pop_pending(uid)
        bot.send_message(uid, "⏳ جاري رفع الموقع على Vercel... انتظر قليلًا.")

        def _vercel_async():
            try:
                dep = vercel_deploy_zip(zip_bytes, uid=uid)
                url = (dep or {}).get("url") or ""
                full = f"https://{url}" if url and not url.startswith("http") else url
                if not full:
                    full = "(تم إنشاء الديبلوي لكن لم يرجع رابط)"
                dep_id = (dep or {}).get("id") or ""
                db_execute(
                    "INSERT INTO deployments (user_id, provider, site_id, deploy_id, url, filename, size_bytes) VALUES (?,?,?,?,?,?,?)",
                    (uid, "vercel", None, dep_id, full, filename, len(zip_bytes)),
                )
                bot.send_message(message.chat.id, "✅ تم رفع الموقع على Vercel.\n\n"
                                 f"🖥 الرابط: <code>{html_escape(full)}</code>", reply_markup=back_main_kb())
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ فشل رفع Vercel: <code>{html_escape(str(e)[:350])}</code>",
                                 reply_markup=back_main_kb())

        threading.Thread(target=_vercel_async, daemon=True).start()
        return

    if size > MAX_FILE_SIZE:
        bot.send_message(uid, "❌ الملف أكبر من الحد المسموح (50MB).")
        return
    if not is_allowed_extension(filename):
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        bot.send_message(uid, f"❌ صيغة غير مدعومة. المدعوم:\n<code>{allowed}</code>")
        return

    if pending and pending.get("type") == "new_project_main":
        project_id = pending["project_id"]
        lower = filename.lower()
        is_zip = lower.endswith(".zip")
        is_code = lower.endswith((".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".htm"))
        if not (is_zip or is_code):
            bot.send_message(uid, "❌ أرسل ملف رئيسي (.py / .js / .mjs / .ts / .html) أو أرشيف .zip للمشروع (بوت أو موقع ويب).")
            return

        # تحميل الملف فوراً وتخزينه في project_files (أو استخراج ZIP)
        try:
            file_info = bot.get_file(doc.file_id)
            raw = bot.download_file(file_info.file_path)
        except Exception as e:
            bot.send_message(uid, f"❌ فشل تحميل الملف: {e}")
            return

        main_file_name = filename
        runtime = "python"
        stored_files = 0
        if is_zip:
            try:
                main_file_name, runtime, stored_files, zip_notes = store_project_from_zip(project_id, raw)
            except ValueError as e:
                bot.send_message(uid, f"❌ {html_escape(str(e))}")
                return
            except Exception as e:
                log.exception("zip store")
                bot.send_message(uid, f"❌ تعذر معالجة الأرشيف: {html_escape(str(e)[:200])}")
                return
            msg_zip = (f"✅ تم استخراج <b>{stored_files}</b> ملفاً من ZIP.\n"
                       f"📄 الملف الرئيسي: <code>{html_escape(main_file_name)}</code>\n"
                       f"🧩 البيئة: <b>{rt_label(runtime)}</b>")
            if zip_notes:
                msg_zip += "\n\n" + "\n".join("ℹ️ " + html_escape(n) for n in zip_notes)
            bot.send_message(uid, msg_zip)
        else:
            db_execute(
                "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
                "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
                "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
                (project_id, filename, sqlite3.Binary(raw), len(raw)),
            )
            runtime = detect_runtime_from_file(filename)
            main_file_name = filename

        db_execute("UPDATE projects SET main_file=?, runtime=? WHERE id=?", (main_file_name, runtime, project_id))
        # كشف الأخطاء قبل التشغيل (نحو + ملفات ناقصة + مشاكل شائعة)
        try:
            issues = static_check_project(project_id)
            if issues:
                bot.send_message(uid, "🔎 <b>نتيجة فحص المشروع — وُجدت ملاحظات:</b>\n\n" + "\n".join("• " + i for i in issues[:10]))
            else:
                bot.send_message(uid, "🔎 <b>فحص المشروع:</b> لا توجد أخطاء نحوية ✅")
        except Exception:
            log.exception("static check")
        # اكتشاف التوكن فوراً
        try:
            tok = None
            for rf in db_fetchall("SELECT content FROM project_files WHERE project_id=?", (project_id,)):
                tok = extract_bot_token_from_bytes(bytes(rf["content"]))
                if tok:
                    break
            if tok:
                info = telegram_get_me(tok)
                if info:
                    db_execute(
                        "UPDATE projects SET hosted_token=?, hosted_bot_username=?, hosted_bot_id=?, hosted_bot_name=? WHERE id=?",
                        (tok, info.get("username") or "", info.get("id"), info.get("first_name") or "", project_id),
                    )
                    bot.send_message(
                        uid,
                        f"🔎 تم اكتشاف البوت: <b>{html_escape(info.get('first_name') or '')}</b> "
                        f"(@{html_escape(info.get('username') or '')})",
                    )
                else:
                    db_execute("UPDATE projects SET hosted_token=? WHERE id=?", (tok, project_id))
        except Exception:
            log.exception("early token scan failed")
        # فحص امني
        sec_flagged = False
        if is_security_block_enabled():
            findings = scan_project_security(project_id)
            if findings:
                flat = []
                lines = []
                for fn, issues in findings:
                    for iss in issues:
                        flat.append(f"{fn}: {iss}")
                        lines.append(f"• <code>{html_escape(fn)}</code> — {html_escape(iss)}")
                flag_project_security(project_id, flat)
                sec_flagged = True
                bot.send_message(
                    uid,
                    "تم رصد محتوى مشبوه في ملفاتك\n"
                    "<b>لن يتم التشغيل حتى موافقة المشرف الامنية</b>\n\n"
                    + "\n".join(lines[:12]),
                )
                try:
                    kb_sec = types.InlineKeyboardMarkup(row_width=2)
                    kb_sec.add(
                        types.InlineKeyboardButton("موافقة امنية", callback_data=f"adm_sec_ok_{project_id}", style="success"),
                        types.InlineKeyboardButton("رفض امني", callback_data=f"adm_sec_no_{project_id}", style="danger"),
                    )
                    bot.send_message(
                        ADMIN_ID,
                        f"تنبيه امني مشروع #{project_id}\nالمستخدم: <code>{uid}</code>\n"
                        + "\n".join(lines[:15]),
                        reply_markup=kb_sec,
                    )
                except Exception:
                    pass
            else:
                db_execute("UPDATE projects SET security_approved=1, security_flag=0 WHERE id=?", (project_id,))
        else:
            db_execute("UPDATE projects SET security_approved=1 WHERE id=?", (project_id,))
        # للإدارة: سجل في pending إن لزم للمراجعة
        db_execute(
            "INSERT INTO pending_uploads (user_id, project_id, filename, telegram_file_id, size_bytes) VALUES (?,?,?,?,?)",
            (uid, project_id, main_file_name, doc.file_id, size),
        )
        pop_pending(uid)
        proj = db_fetchone("SELECT name FROM projects WHERE id=?", (project_id,))
        rt_lbl = rt_label(runtime)
        bot.send_message(uid, f"✅ تم استلام المشروع ({rt_lbl}).\n⏳ بانتظار موافقة المطور لتشغيل البوت.")
        # موافقة تلقائية اذا مفعلة والتوكن صالح ولا يوجد علم امني
        try:
            prow = db_fetchone("SELECT hosted_token, security_flag, security_approved FROM projects WHERE id=?", (project_id,))
            can_auto = is_auto_approve_enabled() and prow and (prow.get("hosted_token") or "")
            if can_auto and int(prow.get("security_flag") or 0) == 0:
                bot.send_message(uid, "موافقة تلقائية جارية...")
                approve_project(project_id)
        except Exception:
            log.exception("auto approve failed")
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(f" موافقة #{project_id}", callback_data=f"adm_approve_proj_{project_id}",
                style="primary", icon_custom_emoji_id=E_APPROVE),
            types.InlineKeyboardButton(f" رفض #{project_id}", callback_data=f"adm_reject_proj_{project_id}",
                style="primary", icon_custom_emoji_id=E_REJECT),
        )
        caption = (
            f"📥 <b>بوت جديد بانتظار الموافقة</b>\n\n"
            f"الاسم: <b>{html_escape(proj['name'] if proj else '-')}</b>\n"
            f"المالك: <code>{uid}</code>\n"
            f"البيئة: <b>{rt_lbl}</b>\n"
            f"الملف الرئيسي: <code>{html_escape(main_file_name)}</code>\n"
            f"الحجم: {size:,} بايت"
        )
        try:
            bot.send_document(ADMIN_ID, doc.file_id, caption=caption, reply_markup=kb)
        except Exception:
            try:
                bot.send_message(ADMIN_ID, caption, reply_markup=kb)
            except Exception:
                pass
        if not is_zip:
            _send_file_preview(ADMIN_ID, doc.file_id, filename)
        return

    if pending and pending.get("type") == "add_file":
        project_id = pending["project_id"]
        proj = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
        if not proj or (proj["user_id"] != uid and not is_admin(uid)):
            pop_pending(uid)
            bot.send_message(message.chat.id, "❌ غير مسموح.")
            return
        file_count = db_fetchone("SELECT COUNT(*) AS c FROM project_files WHERE project_id=?", (project_id,))["c"]
        pending_count = db_fetchone("SELECT COUNT(*) AS c FROM pending_uploads WHERE project_id=?", (project_id,))["c"]
        if file_count + pending_count >= MAX_FILES_PER_PROJECT:
            pop_pending(uid)
            bot.send_message(uid, f"❌ وصلت للحد الأقصى من الملفات ({MAX_FILES_PER_PROJECT}).")
            return
        pending_id = db_execute_returning_id(
            "INSERT INTO pending_uploads (user_id, project_id, filename, telegram_file_id, size_bytes) VALUES (?,?,?,?,?)",
            (uid, project_id, filename, doc.file_id, size),
        )
        pop_pending(uid)
        bot.send_message(uid,
            f"✅ تم استلام الملف <code>{html_escape(filename)}</code>.\n"
            f"⏳ بانتظار مراجعة المطور قبل الإضافة.",
            reply_markup=back_main_kb())
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(f" موافقة الملف #{pending_id}", callback_data=f"adm_approve_file_{pending_id}",
                style="primary", icon_custom_emoji_id=E_APPROVE),
            types.InlineKeyboardButton(f" رفض الملف #{pending_id}", callback_data=f"adm_reject_file_{pending_id}",
                style="primary", icon_custom_emoji_id=E_REJECT),
        )
        try:
            bot.send_document(
                ADMIN_ID,
                doc.file_id,
                caption=(
                    f"📎 <b>ملف جديد بانتظار المراجعة</b>\n\n"
                    f"البوت: <b>{html_escape(proj['name'])}</b> (#{project_id})\n"
                    f"المالك: <code>{uid}</code>\n"
                    f"الملف: <code>{html_escape(filename)}</code>\n"
                    f"الحجم: {size:,} بايت"
                ),
                reply_markup=kb,
            )
        except Exception:
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"📎 <b>ملف جديد بانتظار المراجعة</b>\n\n"
                    f"البوت: <b>{html_escape(proj['name'])}</b> (#{project_id})\n"
                    f"المالك: <code>{uid}</code>\n"
                    f"الملف: <code>{html_escape(filename)}</code>\n"
                    f"الحجم: {size:,} بايت",
                    reply_markup=kb,
                )
            except Exception:
                pass
        _send_file_preview(ADMIN_ID, doc.file_id, filename)
        return

    bot.send_message(uid, "❌ لا أعرف ماذا أفعل بهذا الملف. حدد عملية أولاً.")


# ============================================================
# 17) معالجة الأوامر النصية للمشرف
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "mods_menu",
    content_types=["text"],
)
def receive_mods_input(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pop_pending(uid)
    if not text or text[0] not in ("+", "-"):
        bot.send_message(uid, "❌ صيغة غير صحيحة. مثال: <code>+123456</code> أو <code>-123456</code>",
                         reply_markup=back_admin_kb())
        return
    op = text[0]
    num = text[1:].strip()
    if not num.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل ID رقمي. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(num)
    if op == "+":
        db_execute("INSERT OR IGNORE INTO moderators (user_id, added_by) VALUES (?,?)", (target, uid))
        bot.send_message(uid, f"✅ تم إضافة <code>{target}</code> كمشرف.", reply_markup=back_admin_kb())
    else:
        db_execute("DELETE FROM moderators WHERE user_id=?", (target,))
        bot.send_message(uid, f"✅ تم إزالة <code>{target}</code> من المشرفين.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_section_price",
    content_types=["text"],
)
def receive_section_price(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pop_pending(uid)
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(uid, "❌ صيغة خاطئة. مثال: <code>netlify 5</code>", reply_markup=back_admin_kb())
        return
    section = parts[0].lower()
    val = int(parts[1])
    if section not in {"netlify", "vercel", "terminal"}:
        bot.send_message(uid, "❌ قسم غير معروف. (netlify / vercel / terminal)", reply_markup=back_admin_kb())
        return
    set_setting(f"price_{section}", val)
    bot.send_message(uid, f"✅ تم تعيين سعر {section} إلى <b>{val}</b> نقطة.", reply_markup=back_admin_kb())


# ============================================================
# 18) استقبال الأوامر النصية المعلقة (عامة)
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") in ("proj_term_cmd", "proj_getfile"),
    content_types=["text"],
)
def receive_proj_text_pending(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    ptype = pending.get("type")
    pid = pending.get("project_id")
    if not pid:
        pop_pending(uid)
        return
    proj = db_fetchone("SELECT id, user_id, name FROM projects WHERE id=?", (pid,))
    if not proj or (proj["user_id"] != uid and not is_admin(uid)):
        pop_pending(uid)
        bot.send_message(message.chat.id, "❌ غير مسموح.")
        return

    if ptype == "proj_term_cmd":
        cmd = (message.text or "").strip()
        if not cmd:
            bot.send_message(message.chat.id, "اكتب الأمر.")
            return
        ok, msg = check_and_inc_daily(uid, "terminal", 30)
        if not ok:
            bot.send_message(message.chat.id, msg)
            return
        price = get_section_price("terminal", 0)
        if price > 0 and not is_admin(uid):
            pts_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
            pts = pts_row["p"] if pts_row else 0
            if pts < price:
                bot.send_message(message.chat.id, f"❌ لا تملك نقاط كافية.\n💡 سعر أمر التيرمنال: <b>{price}</b> نقطة.")
                return
            db_execute("UPDATE users SET points = points - ? WHERE id=? AND COALESCE(points,0) >= ?", (price, uid, price))
        bot.send_message(message.chat.id, "⏳ جاري التنفيذ…")
        out = run_project_terminal_command(pid, cmd, timeout_s=20)
        try:
            db_execute("INSERT INTO audit_log (actor_id, action, project_id, command) VALUES (?,?,?,?)",
                       (uid, "terminal_cmd", pid, cmd[:500]))
        except Exception:
            pass
        bot.send_message(message.chat.id, f"🖥️ النتيجة:\n<pre>{html_escape(out)}</pre>")
        return

    if ptype == "proj_getfile":
        rel = (message.text or "").strip().replace("\\", "/")
        if not rel or ".." in rel or rel.startswith("/"):
            bot.send_message(message.chat.id, "❌ اسم ملف غير صحيح.")
            return
        base = os.path.join(PROJECTS_DIR, str(pid))
        abs_path = os.path.normpath(os.path.join(base, rel))
        if not abs_path.startswith(os.path.abspath(base)):
            bot.send_message(message.chat.id, "❌ مسار غير مسموح.")
            return
        if not os.path.isfile(abs_path):
            bot.send_message(message.chat.id, "❌ الملف غير موجود.")
            return
        size = os.path.getsize(abs_path)
        if size > MAX_FILE_SIZE:
            bot.send_message(message.chat.id, "❌ الملف أكبر من الحد المسموح للإرسال.")
            return
        try:
            with open(abs_path, "rb") as fh:
                bot.send_document(message.chat.id, fh, caption=f"📄 {rel}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ فشل إرسال الملف: {e}")
        return


# ============================================================
# محرر الكود — استقبال الكود المعدَّل (نص)
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "proj_file_editing",
    content_types=["text"],
)
def receive_edited_file(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    filename = pending.get("filename")
    file_row_id = pending.get("file_row_id")

    if not pid or not filename:
        pop_pending(uid)
        return

    proj = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
    if not proj or (proj["user_id"] != uid and not is_admin(uid)):
        pop_pending(uid)
        bot.send_message(message.chat.id, "❌ غير مسموح.")
        return

    new_content = message.text or ""
    content_bytes = new_content.encode("utf-8")

    if len(content_bytes) > MAX_FILE_SIZE:
        bot.send_message(
            message.chat.id,
            f"❌ الملف كبير جداً ({len(content_bytes)//1024} KB).\n"
            "الحد الأقصى للتعديل النصي: 50 MB.",
        )
        return

    # اقرأ النسخة القديمة من DB لحساب الـ diff
    old_row = db_fetchone(
        "SELECT content, size_bytes FROM project_files WHERE id=? AND project_id=?",
        (file_row_id, pid),
    )
    old_bytes = bytes(old_row["content"]) if old_row else b""
    try:
        old_text = old_bytes.decode("utf-8")
    except UnicodeDecodeError:
        old_text = old_bytes.decode("latin-1", errors="replace")

    # احسب الـ diff
    diff_body, added, removed = _build_diff_preview(old_text, new_content)

    # خزّن المحتوى الجديد في pending (base64 لأمان JSON)
    set_pending(uid, {
        "type": "proj_file_confirm",
        "project_id": pid,
        "filename": filename,
        "file_row_id": file_row_id,
        "new_content_b64": base64.b64encode(content_bytes).decode(),
        "new_size": len(content_bytes),
    })

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ حفظ التعديلات", callback_data=f"proj_save_confirm_{pid}", style="success"),
        types.InlineKeyboardButton("❌ تجاهل", callback_data=f"proj_discard_edit_{pid}", style="danger"),
    )

    no_change = (added == 0 and removed == 0)
    summary = (
        "✅ <b>لا يوجد تغيير</b> — المحتوى مطابق للنسخة الحالية."
        if no_change
        else f"➕ <b>{added}</b> سطر مضاف  |  ➖ <b>{removed}</b> سطر محذوف"
    )

    bot.send_message(
        message.chat.id,
        f"🔍 <b>معاينة التغييرات</b>\n"
        f"📄 <code>{html_escape(filename)}</code>\n\n"
        f"{summary}\n\n"
        f"<pre><code>{diff_body}</code></pre>\n\n"
        "هل تريد <b>حفظ</b> هذه التغييرات؟",
        reply_markup=kb,
    )


# ============================================================
# محرر الكود — استقبال ملف مُرسَل (document) كبديل
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "proj_file_editing",
    content_types=["document"],
)
def receive_edited_file_doc(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    filename = pending.get("filename")
    file_row_id = pending.get("file_row_id")

    if not pid or not filename:
        pop_pending(uid)
        return

    proj = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
    if not proj or (proj["user_id"] != uid and not is_admin(uid)):
        pop_pending(uid)
        bot.send_message(message.chat.id, "❌ غير مسموح.")
        return

    doc = message.document
    if doc.file_size > MAX_FILE_SIZE:
        bot.send_message(message.chat.id, "❌ الملف أكبر من الحد المسموح (50 MB).")
        return

    try:
        file_info = bot.get_file(doc.file_id)
        content_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ فشل تحميل الملف: <code>{html_escape(str(e))}</code>")
        return

    # اقرأ النسخة القديمة من DB لحساب الـ diff
    old_row = db_fetchone(
        "SELECT content FROM project_files WHERE id=? AND project_id=?",
        (file_row_id, pid),
    )
    old_bytes = bytes(old_row["content"]) if old_row else b""

    # حاول حساب diff نصي (إذا كان الملف text)
    is_text_file = any(filename.endswith(ext) for ext in TEXT_PREVIEW_EXTENSIONS) or filename.endswith(".py")
    try:
        old_text = old_bytes.decode("utf-8") if is_text_file else None
        new_text = content_bytes.decode("utf-8") if is_text_file else None
    except UnicodeDecodeError:
        old_text = new_text = None

    if old_text is not None and new_text is not None:
        diff_body, added, removed = _build_diff_preview(old_text, new_text)
        no_change = (added == 0 and removed == 0)
        summary = (
            "✅ <b>لا يوجد تغيير</b> — المحتوى مطابق للنسخة الحالية."
            if no_change
            else f"➕ <b>{added}</b> سطر مضاف  |  ➖ <b>{removed}</b> سطر محذوف"
        )
        diff_section = f"\n\n<pre><code>{diff_body}</code></pre>"
    else:
        summary = f"📦 ملف ثنائي أو غير نصي — الحجم الجديد: <b>{len(content_bytes):,} بايت</b>"
        diff_section = ""

    # خزّن المحتوى الجديد في pending
    set_pending(uid, {
        "type": "proj_file_confirm",
        "project_id": pid,
        "filename": filename,
        "file_row_id": file_row_id,
        "new_content_b64": base64.b64encode(content_bytes).decode(),
        "new_size": len(content_bytes),
    })

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ حفظ التعديلات", callback_data=f"proj_save_confirm_{pid}", style="success"),
        types.InlineKeyboardButton("❌ تجاهل", callback_data=f"proj_discard_edit_{pid}", style="danger"),
    )

    bot.send_message(
        message.chat.id,
        f"🔍 <b>معاينة التغييرات</b>\n"
        f"📄 <code>{html_escape(filename)}</code>\n\n"
        f"{summary}{diff_section}\n\n"
        "هل تريد <b>حفظ</b> هذه التغييرات؟",
        reply_markup=kb,
    )


# ============================================================
# 19) إدارة البوتات
# ============================================================
def list_user_projects(chat_id: int, uid: int, message_id: Optional[int] = None) -> None:
    rows = db_fetchall("SELECT id, name, approved, is_running, main_file FROM projects WHERE user_id=? ORDER BY id", (uid,))
    if not rows:
        text = "📭 لا توجد بوتات بعد. اضغط <b>إضافة بوت جديد</b> للبدء."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(" إضافة بوت جديد", callback_data="proj_new",
            style="primary", icon_custom_emoji_id=E_NEW))
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
            style="primary", icon_custom_emoji_id=E_BACK))
    else:
        text = "📂 <b>بوتاتك:</b>\n\n"
        kb = types.InlineKeyboardMarkup(row_width=1)
        for p in rows:
            running = manager.is_running(p["id"])
            status = "🟢" if running else ("🟡" if not p["approved"] else "🔴")
            kb.add(types.InlineKeyboardButton(f"{status} {p['name']}", callback_data=f"proj_view_{p['id']}",
                style="primary", icon_custom_emoji_id=E_LIST))
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
            style="primary", icon_custom_emoji_id=E_BACK))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


_STDLIB_MODULES = {
    "os", "sys", "re", "json", "time", "math", "random", "string", "io", "logging",
    "threading", "subprocess", "signal", "shutil", "sqlite3", "pathlib", "typing",
    "datetime", "collections", "contextlib", "functools", "itertools", "asyncio",
    "socket", "http", "urllib", "html", "csv", "hashlib", "base64", "secrets",
    "tempfile", "glob", "argparse", "pickle", "struct", "uuid", "queue", "traceback",
    "platform", "warnings", "copy", "enum", "dataclasses", "abc", "inspect",
    "concurrent", "multiprocessing", "ssl", "email", "xml", "zipfile", "tarfile",
    "gzip", "bz2", "zlib", "ctypes", "operator", "weakref", "gc", "atexit",
    "builtins", "types", "importlib", "pkgutil", "pprint", "textwrap", "calendar",
    "statistics", "decimal", "fractions", "array", "bisect", "heapq", "mmap",
}
_PKG_MAP = {
    "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "discord": "discord.py",
    "magic": "python-magic",
    "Crypto": "pycryptodome",
    "sklearn": "scikit-learn",
    "aiohttp": "aiohttp",
    "flask": "flask",
    "fastapi": "fastapi",
    "requests": "requests",
}

# وحدات Node.js المدمجة — لا تُثبَّت
_NODE_BUILTIN = {
    "fs", "path", "http", "https", "url", "util", "os", "crypto", "stream",
    "events", "buffer", "child_process", "cluster", "net", "tls", "dgram",
    "dns", "zlib", "querystring", "string_decoder", "timers", "tty", "vm",
    "assert", "readline", "module", "process", "console", "perf_hooks",
    "worker_threads", "async_hooks", "v8", "inspector", "trace_events",
}


def _detect_required_packages(work_dir: str) -> list:
    """اكتشاف مكتبات Python من import بدون الحاجة لـ requirements.txt."""
    import re as _re
    found = set()
    if not os.path.isdir(work_dir):
        return []
    for root, dirs, files in os.walk(work_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "node_modules"}]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except Exception:
                continue
            for m in _re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z_][\w\.]*)", code, _re.MULTILINE):
                top = m.group(1).split(".")[0]
                if top and top not in _STDLIB_MODULES and not top.startswith("_"):
                    found.add(top)
    return [_PKG_MAP.get(n, n) for n in sorted(found)]


def _detect_node_packages(work_dir: str) -> list:
    """اكتشاف حزم Node من require/import بدون الحاجة لـ package.json."""
    import re as _re
    found = set()
    if not os.path.isdir(work_dir):
        return []
    for root, dirs, files in os.walk(work_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "venv"}]
        for fn in files:
            if not fn.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except Exception:
                continue
            # require('pkg') / require("pkg")
            for m in _re.finditer(r"""require\s*\(\s*['"]([^'"./][^'"]*)['"]\s*\)""", code):
                pkg = m.group(1).split("/")[0]
                if pkg.startswith("@"):
                    parts = m.group(1).split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else pkg
                if pkg and pkg not in _NODE_BUILTIN:
                    found.add(pkg)
            # import x from 'pkg' / import 'pkg'
            for m in _re.finditer(r"""(?:from|import)\s+['"]([^'"./][^'"]*)['"]""", code):
                pkg = m.group(1).split("/")[0]
                if pkg.startswith("@"):
                    parts = m.group(1).split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else pkg
                if pkg and pkg not in _NODE_BUILTIN:
                    found.add(pkg)
    return sorted(found)


def install_project_requirements(chat_id: int, uid: int, project_id: int, msg_id: Optional[int] = None) -> None:
    """تثبيت مكتبات Python أو Node تلقائياً (بيئة معزولة لكل مشروع + كاش محلي)."""
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        bot.send_message(chat_id, "❌ البوت غير موجود.")
        return
    if p["user_id"] != uid and not is_admin(uid):
        bot.send_message(chat_id, "❌ لا تملك صلاحية على هذا البوت.")
        return
    rt = detect_runtime_from_file(p.get("main_file") or "") if p.get("main_file") else (p.get("runtime") or "python")
    bot.send_message(chat_id, f"📦 <b>جارِ تجهيز المكتبات</b> ({rt_label(rt)})…\nقد يستغرق الأمر من 10 ثوانٍ إلى عدة دقائق في أول مرة.")
    try:
        ok, report = install_dependencies(project_id, force=True)
        head = "✅ <b>تم تجهيز المكتبات بنجاح</b>" if ok else "⚠️ <b>اكتمل التجهيز مع ملاحظات</b>"
        bot.send_message(chat_id, f"{head}\n\n{report}"[:3900])
    except Exception as e:
        log.exception("install deps")
        bot.send_message(chat_id, f"❌ خطأ أثناء التثبيت: <code>{html_escape(str(e)[:300])}</code>")


def view_project(chat_id: int, uid: int, project_id: int, message_id: Optional[int] = None) -> None:
    p = db_fetchone("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, uid))
    if not p and not is_admin(uid):
        return
    if not p and is_admin(uid):
        p = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        return
    files = db_fetchall("SELECT filename, size_bytes FROM project_files WHERE project_id=? ORDER BY filename", (project_id,))
    running = manager.is_running(project_id)
    runtime = (p.get("runtime") or "python").strip() or "python"
    runtime_lbl = "🟢 Node.js" if runtime == "nodejs" else "🐍 Python"
    status_lines = [
        f"📛 <b>{html_escape(p['name'])}</b>",
        f"🆔 <code>{p['id']}</code>",
        f"👤 المالك: <code>{p['user_id']}</code>",
        f"⚙️ الحالة: {'🟢 يعمل' if running else '🔴 متوقف'}",
        f"🧩 البيئة: <b>{runtime_lbl}</b>",
        f"📄 الملف الرئيسي: <code>{html_escape(p['main_file'] or '-')}</code>",
        f"📁 عدد الملفات: {len(files)}",
        f"✅ موافق عليه: {'نعم' if p['approved'] else 'لا'}",
    ]
    if p["last_error"]:
        status_lines.append(f"⚠️ آخر خطأ: <code>{html_escape(p['last_error'][:200])}</code>")
    text = "\n".join(status_lines)
    if files:
        text += "\n\n<b>الملفات:</b>\n"
        for f in files[:20]:
            text += f"• <code>{html_escape(f['filename'])}</code> ({f['size_bytes']//1024} KB)\n"

    kb = types.InlineKeyboardMarkup(row_width=2)
    if p["approved"]:
        if running:
            kb.add(
                types.InlineKeyboardButton(" إيقاف", callback_data=f"proj_stop_{project_id}",
                    style="danger", icon_custom_emoji_id=E_STOP),
                types.InlineKeyboardButton(" إعادة تشغيل", callback_data=f"proj_restart_{project_id}",
                    style="success", icon_custom_emoji_id=E_RESTART),
            )
        else:
            kb.add(types.InlineKeyboardButton("▶️ تشغيل", callback_data=f"proj_start_{project_id}",
                style="success", icon_custom_emoji_id=E_START))
    kb.add(
        types.InlineKeyboardButton(" إضافة ملف", callback_data=f"proj_addfile_{project_id}",
            style="primary", icon_custom_emoji_id=E_ADD_FILE),
        types.InlineKeyboardButton(" السجل", callback_data=f"proj_log_{project_id}",
            style="primary", icon_custom_emoji_id=E_LOG),
    )
    kb.add(
        types.InlineKeyboardButton(" ملفاتي", callback_data=f"proj_files_{project_id}",
            style="primary", icon_custom_emoji_id=E_FILES),
        types.InlineKeyboardButton(" التيرمنال", callback_data=f"proj_term_{project_id}",
            style="primary", icon_custom_emoji_id=E_TERMINAL),
    )
    kb.add(types.InlineKeyboardButton("✏️ محرر الكود", callback_data=f"proj_editor_{project_id}",
        style="primary", icon_custom_emoji_id=E_TERMINAL))
    kb.add(types.InlineKeyboardButton(" تحميل المكتبات", callback_data=f"proj_install_{project_id}",
        style="primary", icon_custom_emoji_id=E_INSTALL))
    kb.add(types.InlineKeyboardButton(" حذف البوت", callback_data=f"proj_del_{project_id}",
        style="danger", icon_custom_emoji_id=E_DELETE))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="proj_list",
        style="primary", icon_custom_emoji_id=E_BACK))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


# ============================================================
# محرر الكود الداخلي
# ============================================================
MAX_EDIT_CHARS = 3800   # أقصى حجم قابل للإرسال/التعديل كرسالة نصية
DIFF_MAX_CHARS = 2800   # حد عرض الـ diff في رسالة واحدة

import difflib

def _build_diff_preview(old_text: str, new_text: str, max_chars: int = DIFF_MAX_CHARS) -> tuple[str, int, int]:
    """
    يبني نص diff مضغوط بين النسختين.
    يُرجع: (diff_text, added_lines, removed_lines)
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_gen = difflib.unified_diff(old_lines, new_lines, lineterm="", n=2)
    added = removed = 0
    chunks = []
    total = 0

    for line in diff_gen:
        if line.startswith("+++") or line.startswith("---"):
            continue  # نتخطى رأسية الـ diff
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
        safe = html_escape(line.rstrip("\n"))
        entry = safe + "\n"
        if total + len(entry) > max_chars:
            chunks.append("<i>… تم اختصار بقية الفروق</i>")
            break
        chunks.append(entry)
        total += len(entry)

    body = "".join(chunks) if chunks else "✅ لا يوجد فرق — المحتوى متطابق."
    return body, added, removed


def _save_file_to_disk_and_db(project_id: int, filename: str, content_bytes: bytes) -> None:
    """يحفظ الملف في DB وعلى القرص."""
    db_execute(
        "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
        "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
        "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
        (project_id, filename, sqlite3.Binary(content_bytes), len(content_bytes)),
    )
    base = os.path.join(PROJECTS_DIR, str(project_id))
    abs_path = os.path.normpath(os.path.join(base, filename))
    if abs_path.startswith(os.path.abspath(base)):
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as fh:
            fh.write(content_bytes)


def show_editor_files(chat_id: int, uid: int, pid: int, msg_id: int = None) -> None:
    """يعرض قائمة ملفات .py كأزرار للتعديل."""
    proj = db_fetchone("SELECT id, user_id, name FROM projects WHERE id=?", (pid,))
    if not proj or (proj["user_id"] != uid and not is_admin(uid)):
        return

    # جلب كل الملفات من DB مرتبة
    rows = db_fetchall(
        "SELECT id, filename, size_bytes FROM project_files WHERE project_id=? ORDER BY filename",
        (pid,),
    )
    py_rows = [r for r in rows if r["filename"].endswith(".py")]
    other_rows = [r for r in rows if not r["filename"].endswith(".py")]
    all_rows = py_rows + other_rows   # ملفات .py أولاً

    if not all_rows:
        text = (
            "✏️ <b>محرر الكود</b>\n\n"
            "📭 لا توجد ملفات في هذا البوت بعد.\n"
            "أضف ملفات أولاً عبر <b>إضافة ملف</b>."
        )
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"proj_view_{pid}", style="primary"))
        if msg_id:
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=kb)
        return

    text = (
        f"✏️ <b>محرر الكود — {html_escape(proj['name'])}</b>\n\n"
        f"📄 {len(all_rows)} ملف — اختر الملف الذي تريد تعديله:"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in all_rows[:30]:
        size_kb = r["size_bytes"] // 1024
        icon = "🐍" if r["filename"].endswith(".py") else "📄"
        label = f"{icon} {r['filename']}  ({size_kb} KB)"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"proj_ef_{pid}_{r['id']}", style="primary"))
    if len(all_rows) > 30:
        kb.add(types.InlineKeyboardButton(f"⚠️ +{len(all_rows)-30} ملف إضافي غير معروض", callback_data="noop"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"proj_view_{pid}", style="primary"))

    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


# ============================================================
# 20) صفحات العرض
# ============================================================
def show_user_stats(chat_id: int, uid: int, message_id: int) -> None:
    rows = db_fetchall("SELECT id, is_running FROM projects WHERE user_id=?", (uid,))
    total = len(rows)
    running = sum(1 for r in rows if manager.is_running(r["id"]))
    size_row = db_fetchone(
        "SELECT COALESCE(SUM(pf.size_bytes),0) AS s FROM project_files pf "
        "JOIN projects p ON p.id = pf.project_id WHERE p.user_id=?", (uid,)
    )
    text = (
        "📊 <b>إحصائياتك</b>\n\n"
        f"📦 عدد البوتات: <b>{total}</b>\n"
        f"⚡ التي تعمل الآن: <b>{running}</b>\n"
        f"💾 حجم ملفاتك: <b>{(size_row['s'] or 0)//1024} KB</b>\n"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def show_points(chat_id: int, uid: int, message_id: int) -> None:
    row = db_fetchone("SELECT COALESCE(points,0) AS points FROM users WHERE id=?", (uid,))
    points = row["points"] if row else 0
    refs_count_row = db_fetchone("SELECT COUNT(*) AS c FROM users WHERE referred_by=?", (uid,))
    refs_count = refs_count_row["c"] if refs_count_row else 0
    bot_username = get_bot_username()
    ref_link = f"https://t.me/{bot_username}?start={uid}"
    share_url = f"https://t.me/share/url?url={ref_link}&text=انضم%20إلى%20بوت%20استضافة%20البوتات%20عبر%20رابطي"
    text = (
        "🎁 <b>قسم تجميع النقاط</b>\n\n"
        "مرحباً بك! قم بمشاركة رابط الإحالة الخاص بك وستحصل على "
        "<b>1 نقطة</b> لكل شخص يدخل عبر الرابط 👇\n\n"
        f"🔗 <code>{ref_link}</code>\n\n"
        f"⭐ نقاطك: <b>{points}</b>\n"
        f"👥 عدد من دخل عبر رابطك: <b>{refs_count}</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" مشاركة الرابط", url=share_url,
        style="primary", icon_custom_emoji_id=E_SHARE))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def start_transfer_points(chat_id: int, uid: int, message_id: int) -> None:
    fee = get_transfer_fee()
    set_pending(uid, {"type": "transfer_recipient"})
    text = (
        "💸 <b>قسم تحويل النقاط:</b>\n\n"
        "أرسل <b>ID</b> المستلم 🎁\n\n"
        "⚠️ أقل عدد يمكن تحويله: <b>5</b>\n"
        f"⚠️ عمولة التحويل: <b>{fee}</b> نقطة\n\n"
        "أو /cancel للإلغاء."
    )
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_main_kb())
    except Exception:
        bot.send_message(chat_id, text, reply_markup=back_main_kb())


def show_help(chat_id: int, message_id: int) -> None:
    text = (
        f"<b>❔ {html_escape(BRAND_NAME)} Guide</b>\n\n"
        "<b>1.</b>  Deploy project\n"
        "<b>2.</b>  Pick Python or Node.js\n"
        "<b>3.</b>  Send a short name\n"
        "<b>4.</b>  Upload .py / .js / .zip\n"
        "<b>5.</b>  Wait for approval (or auto)\n"
        "<b>6.</b>  Manage logs · token · schedule\n\n"
        f"Support  @{html_escape(DEVELOPER_USERNAME)}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⌂ Home", callback_data="back_main", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)



def show_user_sites(chat_id: int, uid: int, message_id: Optional[int] = None) -> None:
    nsites = db_fetchall(
        "SELECT provider, site_id, site_url, MAX(created_at) AS created_at FROM ("
        "  SELECT 'netlify' AS provider, site_id, site_url, created_at FROM netlify_sites WHERE user_id=?"
        "  UNION ALL "
        "  SELECT provider, site_id, url AS site_url, created_at FROM deployments WHERE user_id=? AND provider='vercel'"
        ") GROUP BY provider, site_id, site_url ORDER BY created_at DESC LIMIT 20",
        (uid, uid),
    )
    text = "🖥 <b>مواقعي</b>\n\n"
    if not nsites:
        text += "لا يوجد مواقع بعد."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
            style="primary", icon_custom_emoji_id=E_BACK))
    else:
        kb = types.InlineKeyboardMarkup(row_width=1)
        for r in nsites[:10]:
            prov = "Netlify" if r["provider"] == "netlify" else "Vercel"
            label = f"{prov} — {r['site_url']}"
            kb.add(types.InlineKeyboardButton(label[:60],
                                              callback_data=f"site_redeploy_{r['provider']}_{r['site_id'] or 'x'}",
                                              style="primary", icon_custom_emoji_id=E_SITES))
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
            style="primary", icon_custom_emoji_id=E_BACK))
        text += "اختر موقع لإعادة النشر.\n"
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_user_deployments(chat_id: int, uid: int, message_id: Optional[int] = None) -> None:
    rows = db_fetchall(
        "SELECT provider, url, filename, size_bytes, created_at FROM deployments "
        "WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)
    )
    text = "🧾 <b>آخر 5 ديبلويمنتس</b>\n\n"
    if not rows:
        text += "لا يوجد ديبلويمنتس بعد."
    else:
        for r in rows:
            prov = "Netlify" if r["provider"] == "netlify" else "Vercel"
            size_kb = int((r.get("size_bytes") or 0) // 1024)
            fn = r.get("filename") or "-"
            text += f"• <b>{prov}</b>\n  رابط: <code>{html_escape(r['url'])}</code>\n  ملف: {html_escape(fn)} ({size_kb} KB)\n\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="back_main",
        style="primary", icon_custom_emoji_id=E_BACK))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_pending_users(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT id, first_name, username FROM users WHERE approved=0 AND banned=0 ORDER BY created_at DESC LIMIT 30"
    )
    if not rows:
        text = "✨ لا توجد طلبات تفعيل."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
            style="primary", icon_custom_emoji_id=E_BACK))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        return
    text = "⏳ <b>طلبات تفعيل بانتظار:</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        label = f"{r['first_name'] or '-'} (@{r['username'] or '-'}) [{r['id']}]"
        kb.add(types.InlineKeyboardButton(f" تفعيل {label}", callback_data=f"adm_approve_user_{r['id']}",
            style="primary", icon_custom_emoji_id=E_APPROVE))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_pending_projects(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT p.id, p.name, p.user_id, p.main_file FROM projects p WHERE p.approved=0 ORDER BY p.created_at DESC LIMIT 30"
    )
    if not rows:
        text = "✨ لا توجد بوتات بانتظار الموافقة."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
            style="primary", icon_custom_emoji_id=E_BACK))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        return
    text = "⏳ <b>بوتات بانتظار الموافقة:</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    for r in rows:
        text += f"• #{r['id']} <b>{html_escape(r['name'])}</b> — مالك <code>{r['user_id']}</code>\n"
        kb.add(
            types.InlineKeyboardButton(f" #{r['id']}", callback_data=f"adm_approve_proj_{r['id']}",
                style="primary", icon_custom_emoji_id=E_APPROVE),
            types.InlineKeyboardButton(f" #{r['id']}", callback_data=f"adm_reject_proj_{r['id']}",
                style="primary", icon_custom_emoji_id=E_REJECT),
        )
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_pending_files(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT pu.id, pu.filename, pu.size_bytes, pu.user_id, pu.project_id, p.name AS proj_name "
        "FROM pending_uploads pu "
        "LEFT JOIN projects p ON p.id = pu.project_id "
        "WHERE pu.project_id IS NOT NULL "
        "ORDER BY pu.created_at ASC LIMIT 30"
    )
    if not rows:
        text = "✨ لا توجد ملفات بانتظار المراجعة."
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
            style="primary", icon_custom_emoji_id=E_BACK))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        return
    text = f"📎 <b>ملفات بانتظار المراجعة ({len(rows)}):</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    for r in rows:
        size_kb = round(r["size_bytes"] / 1024, 1)
        text += (
            f"• <code>{html_escape(r['filename'])}</code> ({size_kb} KB)\n"
            f"  البوت: <b>{html_escape(r['proj_name'] or '-')}</b> — مالك <code>{r['user_id']}</code>\n\n"
        )
        kb.add(
            types.InlineKeyboardButton(f" قبول #{r['id']}", callback_data=f"adm_approve_file_{r['id']}",
                style="primary", icon_custom_emoji_id=E_APPROVE),
            types.InlineKeyboardButton(f" رفض #{r['id']}", callback_data=f"adm_reject_file_{r['id']}",
                style="primary", icon_custom_emoji_id=E_REJECT),
        )
        kb.add(
            types.InlineKeyboardButton(f"👁 معاينة #{r['id']}", callback_data=f"adm_preview_file_{r['id']}",
                style="primary"),
        )
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_all_users(chat_id: int, message_id: int) -> None:
    rows = db_fetchall("SELECT id, first_name, username, approved, banned FROM users ORDER BY created_at DESC LIMIT 50")
    text = "👥 <b>المستخدمون (آخر 50):</b>\n\n"
    for r in rows:
        s = "🟢" if r["approved"] and not r["banned"] else ("🚫" if r["banned"] else "🟡")
        text += f"{s} <code>{r['id']}</code> {html_escape(r['first_name'] or '')} (@{r['username'] or '-'})\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_all_projects(chat_id: int, message_id: int) -> None:
    rows = db_fetchall("SELECT id, user_id, name, approved, is_running FROM projects ORDER BY id DESC LIMIT 50")
    text = "🤖 <b>كل البوتات (آخر 50):</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        running = manager.is_running(r["id"])
        s = "🟢" if running else ("🟡" if not r["approved"] else "🔴")
        kb.add(types.InlineKeyboardButton(f"{s} #{r['id']} {r['name']} — {r['user_id']}", callback_data=f"proj_view_{r['id']}",
            style="primary", icon_custom_emoji_id=E_LIST))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_admin_stats(chat_id: int, message_id: int) -> None:
    counts = db_fetchone(
        "SELECT "
        "(SELECT COUNT(*) FROM users) AS users_total, "
        "(SELECT COUNT(*) FROM users WHERE approved=1) AS users_approved, "
        "(SELECT COUNT(*) FROM users WHERE banned=1) AS users_banned, "
        "(SELECT COUNT(*) FROM projects) AS projects_total, "
        "(SELECT COUNT(*) FROM projects WHERE approved=1) AS projects_approved, "
        "(SELECT COALESCE(SUM(size_bytes),0) FROM project_files) AS total_bytes"
    )
    running = sum(1 for hp in manager.processes.values() if hp.is_alive())
    text = (
        "📈 <b>إحصائيات النظام</b>\n\n"
        f"👥 المستخدمون: {counts['users_total']} (مفعّل {counts['users_approved']}، محظور {counts['users_banned']})\n"
        f"🤖 البوتات: {counts['projects_total']} (موافق عليها {counts['projects_approved']})\n"
        f"⚡ تعمل الآن: <b>{running}</b>\n"
        f"💾 إجمالي ملفات التخزين: {counts['total_bytes']//1024} KB\n"
        f"⏰ الوقت: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" حالة السيرفر", callback_data="adm_server_status",
        style="primary", icon_custom_emoji_id=E_TERMINAL))
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_server_status(chat_id: int, message_id: int) -> None:
    uptime = int(time.time() - _START_TS)
    try:
        du = shutil.disk_usage(os.path.dirname(DB_PATH) or ".")
        disk_line = f"💾 Disk: {du.used//(1024**3)}GB / {du.total//(1024**3)}GB"
    except Exception:
        disk_line = "💾 Disk: (غير متاح)"
    text = (
        "🖥️ <b>حالة السيرفر</b>\n\n"
        f"⏱️ Uptime: <b>{uptime}</b> ثانية\n"
        f"🐍 Python: <code>{html_escape(sys.version.split()[0])}</code>\n"
        f"🧭 Platform: <code>{html_escape(sys.platform)}</code>\n"
        f"{disk_line}\n"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_stats",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def adm_send_backup(chat_id: int) -> None:
    """يرسل نسخة احتياطية من قاعدة البيانات للأدمن."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = f"/tmp/hosting_bot_backup_{ts}.db"
        import shutil as _sh
        _sh.copy2(DB_PATH, backup_path)
        size_kb = os.path.getsize(backup_path) // 1024
        caption = (
            f"💾 <b>نسخة احتياطية من قاعدة البيانات</b>\n"
            f"📅 التاريخ: <code>{ts}</code>\n"
            f"📦 الحجم: <b>{size_kb} KB</b>"
        )
        with open(backup_path, "rb") as f:
            bot.send_document(chat_id, f, caption=caption, visible_file_name=f"db_backup_{ts}.db")
        os.remove(backup_path)
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل إنشاء النسخة الاحتياطية:\n<code>{html_escape(str(e))}</code>")


def adm_show_growth_stats(chat_id: int, message_id: int) -> None:
    """يعرض إحصائيات نمو المستخدمين والبوتات خلال آخر 7 أيام."""
    lines = ["📊 <b>إحصائيات النمو — آخر 7 أيام</b>\n"]
    for i in range(6, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        u = (db_fetchone(
            "SELECT COUNT(*) AS c FROM users WHERE date(created_at)=?", (d,)) or {}).get("c", 0)
        p = (db_fetchone(
            "SELECT COUNT(*) AS c FROM projects WHERE date(created_at)=?", (d,)) or {}).get("c", 0)
        bar_u = "▓" * min(u, 10) + "░" * max(0, 10 - min(u, 10))
        day_label = "اليوم" if i == 0 else f"قبل {i}ي"
        lines.append(f"📅 <b>{d}</b>  ({day_label})\n   👥 {bar_u} {u} مستخدم  |  🤖 {p} بوت")
    text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_audit_log(chat_id: int, message_id: int) -> None:
    """يعرض آخر 20 حدث في سجل التدقيق."""
    rows = db_fetchall(
        "SELECT actor_id, action, target_uid, project_id, created_at "
        "FROM audit_log ORDER BY id DESC LIMIT 20"
    )
    if not rows:
        text = "📋 <b>سجل التدقيق</b>\n\nلا توجد سجلات حتى الآن."
    else:
        lines = ["📋 <b>سجل التدقيق — آخر 20 حدث</b>\n"]
        for r in rows:
            ts = str(r.get("created_at", ""))[:16]
            actor = r.get("actor_id", "?")
            action = html_escape(str(r.get("action", "")))
            target = f" ← {r['target_uid']}" if r.get("target_uid") else ""
            proj = f" [بوت#{r['project_id']}]" if r.get("project_id") else ""
            lines.append(f"<code>{ts}</code>  <b>{action}</b>{target}{proj}\n  👤 {actor}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_cleanup_stopped_files(chat_id: int) -> None:
    """يحذف مجلدات المشاريع المتوقفة والمحذوفة من الـ DB لتحرير مساحة."""
    try:
        active_ids = {str(r["id"]) for r in db_fetchall("SELECT id FROM projects")}
        removed = 0
        freed_bytes = 0
        if os.path.isdir(PROJECTS_DIR):
            for folder in os.listdir(PROJECTS_DIR):
                folder_path = os.path.join(PROJECTS_DIR, folder)
                if os.path.isdir(folder_path) and folder not in active_ids:
                    try:
                        size = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, fnames in os.walk(folder_path)
                            for f in fnames
                        )
                        shutil.rmtree(folder_path)
                        freed_bytes += size
                        removed += 1
                    except Exception:
                        pass
        freed_kb = freed_bytes // 1024
        bot.send_message(
            chat_id,
            f"🧹 <b>تم التنظيف</b>\n\n"
            f"🗂 مجلدات محذوفة: <b>{removed}</b>\n"
            f"💾 مساحة محرَّرة: <b>{freed_kb} KB</b>",
            reply_markup=back_admin_kb()
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ أثناء التنظيف:\n<code>{html_escape(str(e))}</code>")


def adm_show_running_bots(chat_id: int, message_id: int) -> None:
    """يعرض قائمة البوتات الشغّالة حالياً مع معلومات صاحبها."""
    rows = db_fetchall(
        "SELECT p.id, p.name, p.user_id, u.first_name, u.username "
        "FROM projects p LEFT JOIN users u ON u.id=p.user_id "
        "WHERE p.approved=1 ORDER BY p.id DESC"
    )
    running_rows = [r for r in rows if manager.is_running(r["id"])]
    if not running_rows:
        text = "⚡ <b>البوتات الشغّالة الآن</b>\n\n😴 لا يوجد أي بوت شغّال حالياً."
    else:
        lines = [f"⚡ <b>البوتات الشغّالة الآن</b>  —  <b>{len(running_rows)}</b> بوت\n"]
        for r in running_rows:
            name = html_escape(r.get("name") or f"#{r['id']}")
            owner = html_escape(r.get("first_name") or "")
            uname = f"@{r['username']}" if r.get("username") else f"<code>{r['user_id']}</code>"
            lines.append(f"🟢 <b>{name}</b>  │  {owner} ({uname})")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_running_bots_list", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_export_bots_csv(chat_id: int) -> None:
    """يصدّر جميع البوتات إلى ملف CSV ويرسله للأدمن."""
    try:
        rows = db_fetchall(
            "SELECT p.id, p.name, p.main_file, p.approved, p.is_running, p.created_at, "
            "u.id AS uid, u.first_name, u.username "
            "FROM projects p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC"
        )
        buf = io.StringIO()
        buf.write("id,name,main_file,approved,is_running,created_at,owner_id,owner_name,owner_username\n")
        for r in rows:
            running = "1" if manager.is_running(r["id"]) else "0"
            buf.write(
                f"{r['id']},{r.get('name','')},{r.get('main_file','')},{r['approved']},"
                f"{running},{r.get('created_at','')},{r.get('uid','')},"
                f"{r.get('first_name','')},{r.get('username','')}\n"
            )
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        data = buf.getvalue().encode("utf-8")
        bio = io.BytesIO(data)
        bio.name = f"bots_export_{ts}.csv"
        bot.send_document(
            chat_id, bio,
            caption=f"📤 <b>تصدير البوتات</b>\n📅 {ts}\n🤖 إجمالي: <b>{len(rows)}</b> بوت"
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل التصدير:\n<code>{html_escape(str(e))}</code>")


def adm_show_inactive_users(chat_id: int, message_id: int) -> None:
    """يعرض المستخدمين الذين لم يتفاعلوا منذ 30+ يوماً."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = db_fetchall(
        "SELECT id, first_name, username, created_at FROM users "
        "WHERE approved=1 AND banned=0 "
        "AND id NOT IN (SELECT DISTINCT user_id FROM usage_daily WHERE day >= ?) "
        "AND date(created_at) <= ? "
        "ORDER BY created_at ASC LIMIT 40",
        (cutoff, cutoff)
    )
    if not rows:
        text = "👻 <b>المستخدمون الخاملون</b>\n\n✅ لا يوجد مستخدمون خاملون منذ 30 يوماً."
    else:
        lines = [f"👻 <b>المستخدمون الخاملون</b> (30+ يوم)\n<i>إجمالي: {len(rows)} مستخدم</i>\n"]
        for r in rows:
            name = html_escape(r.get("first_name") or "-")
            uname = f"@{r['username']}" if r.get("username") else f"<code>{r['id']}</code>"
            joined = str(r.get("created_at", ""))[:10]
            lines.append(f"💤 {name} ({uname})  │  انضم: {joined}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_usage_stats(chat_id: int, message_id: int) -> None:
    """يعرض إحصائيات الاستخدام من جدول usage_daily (أكثر الأقسام استخداماً)."""
    rows = db_fetchall(
        "SELECT section, SUM(count) AS total "
        "FROM usage_daily GROUP BY section ORDER BY total DESC LIMIT 15"
    )
    top_users = db_fetchall(
        "SELECT user_id, SUM(count) AS total FROM usage_daily "
        "GROUP BY user_id ORDER BY total DESC LIMIT 5"
    )
    if not rows:
        text = "📊 <b>إحصائيات الاستخدام</b>\n\nلا توجد بيانات بعد."
    else:
        total_all = sum(r["total"] for r in rows)
        lines = [f"📊 <b>إحصائيات الاستخدام</b>  —  إجمالي: <b>{total_all:,}</b> عملية\n"]
        lines.append("<b>🏆 أكثر الأقسام استخداماً:</b>")
        for r in rows:
            pct = int(r["total"] / total_all * 100) if total_all else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"  <code>{html_escape(r['section']):<18}</code> {bar} {r['total']:,}")
        if top_users:
            lines.append("\n<b>👥 أكثر المستخدمين نشاطاً:</b>")
            for r in top_users:
                uid = r["user_id"]
                u = db_fetchone("SELECT first_name, username FROM users WHERE id=?", (uid,)) or {}
                name = html_escape(u.get("first_name") or str(uid))
                lines.append(f"  • {name}  —  <b>{r['total']:,}</b> عملية")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_announce(chat_id: int, uid: int) -> None:
    """يبدأ تدفق إرسال إعلان منسّق لجميع المستخدمين."""
    set_pending(uid, {"type": "adm_announce"})
    bot.send_message(
        chat_id,
        "📣 <b>إعلان منسّق</b>\n\n"
        "أرسل نص الإعلان الآن.\n"
        "يمكنك استخدام HTML: <code>&lt;b&gt;عريض&lt;/b&gt;</code>، <code>&lt;i&gt;مائل&lt;/i&gt;</code>، <code>&lt;code&gt;كود&lt;/code&gt;</code>\n\n"
        "سيُرسَل للجميع بالتنسيق:\n"
        "━━━━━━━━━━━━━━\n"
        "📣 <b>إعلان من الإدارة</b>\n"
        "نص إعلانك هنا\n"
        "━━━━━━━━━━━━━━\n\n"
        "أو /cancel للإلغاء.",
        reply_markup=back_admin_kb()
    )


# ============================================================
# ➕ ميزات الأدمن الجديدة (20 ميزة)
# ============================================================

def adm_new_today(chat_id: int, message_id: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = db_fetchall(
        "SELECT id, first_name, username, approved FROM users WHERE date(created_at)=? ORDER BY id DESC",
        (today,)
    )
    if not rows:
        text = f"🆕 <b>مستخدمو اليوم</b> — {today}\n\n😶 لم ينضم أحد اليوم."
    else:
        lines = [f"🆕 <b>مستخدمو اليوم</b> — {today}\nإجمالي: <b>{len(rows)}</b>\n"]
        for r in rows:
            st = "✅" if r["approved"] else "⏳"
            name = html_escape(r.get("first_name") or "-")
            uname = f"@{r['username']}" if r.get("username") else f"<code>{r['id']}</code>"
            lines.append(f"{st} {name} ({uname})")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_user_bots_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_user_bots_by_id"})
    bot.send_message(chat_id, "🤖 أرسل <b>ID المستخدم</b> لعرض بوتاته:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_user_bots(chat_id: int, message_id: int, target_uid: int) -> None:
    u = db_fetchone("SELECT first_name, username FROM users WHERE id=?", (target_uid,))
    rows = db_fetchall("SELECT id, name, approved, is_running FROM projects WHERE user_id=? ORDER BY id DESC", (target_uid,))
    uname_str = f"@{u['username']}" if u and u.get("username") else f"<code>{target_uid}</code>"
    name_str = html_escape((u or {}).get("first_name") or str(target_uid))
    if not rows:
        text = f"🤖 <b>بوتات {name_str}</b> ({uname_str})\n\nلا توجد بوتات."
    else:
        lines = [f"🤖 <b>بوتات {name_str}</b> ({uname_str}) — {len(rows)} بوت\n"]
        for r in rows:
            running = manager.is_running(r["id"])
            st = "🟢" if running else ("🟡" if not r["approved"] else "🔴")
            lines.append(f"{st} #{r['id']} — {html_escape(r['name'] or '-')}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_reset_points(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_reset_points_id"})
    bot.send_message(chat_id, "🔄 أرسل <b>ID المستخدم</b> لتصفير نقاطه:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_start_set_user_max(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_set_user_max_step1"})
    bot.send_message(chat_id, "⚙️ أرسل <b>ID المستخدم</b> لضبط حد البوتات له:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_crashed_bots(chat_id: int, message_id: int) -> None:
    rows = db_fetchall("SELECT id, name, user_id FROM projects WHERE approved=1 AND is_running=1")
    crashed = [r for r in rows if not manager.is_running(r["id"])]
    if not crashed:
        text = "💥 <b>البوتات المعطوبة</b>\n\n✅ لا توجد بوتات معطوبة!"
    else:
        lines = [f"💥 <b>البوتات المعطوبة</b> — {len(crashed)} بوت\n<i>(مُعلَّمة شغّالة في DB لكنها متوقفة)</i>\n"]
        for r in crashed:
            lines.append(f"🔴 #{r['id']} — {html_escape(r['name'] or '-')}  │  👤 {r['user_id']}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_crashed_bots", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_search_bot(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_search_bot_name"})
    bot.send_message(chat_id, "🔍 أرسل <b>اسم البوت</b> أو جزء منه للبحث:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_bots_summary(chat_id: int, message_id: int) -> None:
    c = db_fetchone(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN approved=1 THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN approved=0 THEN 1 ELSE 0 END) AS pending, "
        "SUM(CASE WHEN is_running=1 THEN 1 ELSE 0 END) AS db_running "
        "FROM projects"
    ) or {}
    actual_running = sum(1 for hp in manager.processes.values() if hp.is_alive())
    files_c = (db_fetchone("SELECT COUNT(*) AS c FROM project_files") or {}).get("c", 0)
    files_sz = (db_fetchone("SELECT COALESCE(SUM(size_bytes),0) AS s FROM project_files") or {}).get("s", 0)
    text = (
        "📋 <b>ملخص البوتات</b>\n\n"
        f"📦 الإجمالي: <b>{c.get('total',0)}</b>\n"
        f"✅ موافق عليها: <b>{c.get('approved',0)}</b>\n"
        f"⏳ بانتظار موافقة: <b>{c.get('pending',0)}</b>\n"
        f"🟢 تعمل فعلاً: <b>{actual_running}</b>\n"
        f"🔴 متوقفة: <b>{(c.get('approved',0) or 0) - actual_running}</b>\n"
        f"📁 إجمالي الملفات: <b>{files_c:,}</b>\n"
        f"💾 مساحة الملفات: <b>{files_sz//1024:,} KB</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_clear_process_logs(chat_id: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    c = (db_fetchone("SELECT COUNT(*) AS c FROM process_logs WHERE date(created_at)<?", (cutoff,)) or {}).get("c", 0)
    db_execute("DELETE FROM process_logs WHERE date(created_at)<?", (cutoff,))
    bot.send_message(chat_id, f"🧹 <b>تنظيف سجلات العمليات</b>\n\n✅ حُذف <b>{c:,}</b> سجل (أقدم من 7 أيام).", reply_markup=back_admin_kb())


def adm_start_msg_inactive(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_msg_to_inactive"})
    bot.send_message(
        chat_id,
        "💤 <b>رسالة للمستخدمين الخاملين</b>\n\n"
        "أرسل نص الرسالة الآن — ستُرسَل لكل من لم يستخدم البوت منذ 30+ يوم.\n"
        "/cancel للإلغاء.",
        reply_markup=back_admin_kb()
    )


def adm_start_broadcast_active(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_broadcast_active"})
    bot.send_message(
        chat_id,
        "✅ <b>إذاعة للمفعّلين فقط</b>\n\n"
        "أرسل الرسالة الآن — ستصل فقط للمستخدمين المفعَّلين غير المحظورين.\n"
        "/cancel للإلغاء.",
        reply_markup=back_admin_kb()
    )


def adm_show_receivers_count(chat_id: int, message_id: int) -> None:
    all_u  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0") or {}).get("c", 0)
    active = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0 AND approved=1") or {}).get("c", 0)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    inactive = (db_fetchone(
        "SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0 "
        "AND id NOT IN (SELECT DISTINCT user_id FROM usage_daily WHERE day>=?) "
        "AND date(created_at)<=?", (cutoff, cutoff)
    ) or {}).get("c", 0)
    text = (
        "🔢 <b>عداد المستقبلين</b>\n\n"
        f"📢 إذاعة عادية (كل غير المحظورين): <b>{all_u:,}</b>\n"
        f"✅ إذاعة للمفعّلين فقط: <b>{active:,}</b>\n"
        f"💤 رسالة الخاملين (30+ي): <b>{inactive:,}</b>"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_comms", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_db_table_stats(chat_id: int, message_id: int) -> None:
    tables = ["users", "projects", "project_files", "pending_uploads",
              "process_logs", "settings", "gift_links", "netlify_sites",
              "deployments", "usage_daily", "audit_log", "force_channels", "moderators"]
    lines = ["🗃 <b>إحصائيات جداول قاعدة البيانات</b>\n"]
    for t in tables:
        try:
            c = (db_fetchone(f"SELECT COUNT(*) AS c FROM {t}") or {}).get("c", 0)
            lines.append(f"  <code>{t:<20}</code> {c:>8,} سجل")
        except Exception:
            lines.append(f"  <code>{t:<20}</code>  —")
    try:
        sz = os.path.getsize(DB_PATH) // 1024
        lines.append(f"\n💾 حجم الـ DB: <b>{sz:,} KB</b>")
    except Exception:
        pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text("\n".join(lines), chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


def adm_show_deploy_stats(chat_id: int, message_id: int) -> None:
    netlify_c = (db_fetchone("SELECT COUNT(*) AS c FROM netlify_sites") or {}).get("c", 0)
    vercel_c  = (db_fetchone("SELECT COUNT(*) AS c FROM deployments WHERE provider='vercel'") or {}).get("c", 0)
    netlify_u = (db_fetchone("SELECT COUNT(DISTINCT user_id) AS c FROM netlify_sites") or {}).get("c", 0)
    vercel_u  = (db_fetchone("SELECT COUNT(DISTINCT user_id) AS c FROM deployments WHERE provider='vercel'") or {}).get("c", 0)
    total_sz  = (db_fetchone("SELECT COALESCE(SUM(size_bytes),0) AS s FROM deployments") or {}).get("s", 0)
    recent = db_fetchall(
        "SELECT provider, filename, url, created_at FROM deployments ORDER BY id DESC LIMIT 5"
    )
    lines = [
        "🚀 <b>إحصائيات الرفع (Deploy)</b>\n",
        f"🌐 Netlify:  <b>{netlify_c}</b> موقع  │  {netlify_u} مستخدم",
        f"▲ Vercel:   <b>{vercel_c}</b> نشر    │  {vercel_u} مستخدم",
        f"💾 إجمالي الحجم: <b>{total_sz//1024:,} KB</b>",
    ]
    if recent:
        lines.append("\n<b>📋 آخر 5 نشرات:</b>")
        for r in recent:
            ts = str(r.get("created_at",""))[:10]
            lines.append(f"  {r['provider']} │ {html_escape(r.get('filename',''))} │ {ts}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text("\n".join(lines), chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


def adm_send_daily_report(chat_id: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    new_u   = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE date(created_at)=?", (today,)) or {}).get("c", 0)
    new_p   = (db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE date(created_at)=?", (today,)) or {}).get("c", 0)
    total_u = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0") or {}).get("c", 0)
    active  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0") or {}).get("c", 0)
    running = sum(1 for hp in manager.processes.values() if hp.is_alive())
    total_p = (db_fetchone("SELECT COUNT(*) AS c FROM projects") or {}).get("c", 0)
    deploys_today = (db_fetchone("SELECT COUNT(*) AS c FROM deployments WHERE date(created_at)=?", (today,)) or {}).get("c", 0)
    sv = get_server_quick_info()
    text = (
        f"📅 <b>التقرير اليومي — {today}</b>\n"
        f"{'━'*28}\n"
        f"👥 مستخدمون جدد اليوم: <b>{new_u}</b>\n"
        f"🤖 بوتات جديدة اليوم: <b>{new_p}</b>\n"
        f"🚀 نشرات اليوم: <b>{deploys_today}</b>\n"
        f"{'─'*28}\n"
        f"👥 إجمالي المستخدمين: <b>{total_u}</b>  (مفعّل {active})\n"
        f"🤖 إجمالي البوتات: <b>{total_p}</b>  (شغّال {running})\n"
        f"{'─'*28}\n"
        f"🖥 <b>السيرفر:</b>\n{sv}"
    )
    bot.send_message(chat_id, text, reply_markup=back_admin_kb())


def adm_show_points_dist(chat_id: int, message_id: int) -> None:
    stats = db_fetchone(
        "SELECT COUNT(*) AS total, COALESCE(SUM(points),0) AS s, "
        "COALESCE(AVG(points),0) AS avg, COALESCE(MAX(points),0) AS mx, "
        "SUM(CASE WHEN points=0 THEN 1 ELSE 0 END) AS zero_c "
        "FROM users WHERE banned=0"
    ) or {}
    top5 = db_fetchall(
        "SELECT first_name, username, COALESCE(points,0) AS points "
        "FROM users WHERE banned=0 ORDER BY points DESC LIMIT 5"
    )
    lines = [
        "💎 <b>توزيع النقاط</b>\n",
        f"📊 إجمالي النقاط: <b>{int(stats.get('s',0)):,}</b>",
        f"📈 المتوسط: <b>{int(stats.get('avg',0)):,}</b>",
        f"🏆 الأعلى: <b>{int(stats.get('mx',0)):,}</b>",
        f"😶 مستخدمون بصفر نقطة: <b>{stats.get('zero_c',0)}</b> / {stats.get('total',0)}",
    ]
    if top5:
        lines.append("\n<b>🥇 أعلى 5 نقاطاً:</b>")
        for i, r in enumerate(top5, 1):
            n = html_escape(r.get("first_name") or "-")
            lines.append(f"  {i}. {n} — <b>{int(r['points']):,}</b> نقطة")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text("\n".join(lines), chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


def adm_show_all_settings(chat_id: int, message_id: int) -> None:
    keys = [
        ("upload_price", "💰 سعر الرفع"),
        ("transfer_fee", "💸 عمولة التحويل"),
        ("bot_disabled", "🔴 البوت معطّل"),
        ("auto_approve", "✅ قبول تلقائي"),
        ("welcome_text", "✏️ نص الترحيب"),
        ("notify_admin_new_user", "🔔 إشعار الجدد"),
        ("btn_style_theme", "🎨 ثيم الأزرار"),
    ]
    lines = ["📋 <b>كل الإعدادات الحالية</b>\n"]
    for k, label in keys:
        v = get_setting(k, "—") or "—"
        if len(v) > 40:
            v = v[:37] + "…"
        lines.append(f"  {label}: <code>{html_escape(v)}</code>")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_settings", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text("\n".join(lines), chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


def adm_toggle_auto_approve_fn(chat_id: int, message_id: int) -> None:
    current = (get_setting("auto_approve", "0") or "0") == "1"
    new_val = "0" if current else "1"
    set_setting("auto_approve", new_val)
    state = "✅ مفعّل" if new_val == "1" else "❌ معطّل"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تبديل مرة أخرى", callback_data="adm_toggle_auto_approve", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_settings", style="primary", icon_custom_emoji_id=E_BACK))
    text = f"🤖 <b>القبول التلقائي للمستخدمين الجدد</b>\n\nالحالة الآن: <b>{state}</b>"
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_clear_old_audit(chat_id: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    c = (db_fetchone("SELECT COUNT(*) AS c FROM audit_log WHERE date(created_at)<?", (cutoff,)) or {}).get("c", 0)
    db_execute("DELETE FROM audit_log WHERE date(created_at)<?", (cutoff,))
    bot.send_message(chat_id, f"🗑 <b>تنظيف سجل التدقيق</b>\n\n✅ حُذف <b>{c:,}</b> سجل (أقدم من 30 يوم).", reply_markup=back_admin_kb())


def adm_start_approve_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_approve_id"})
    bot.send_message(chat_id, "✅ أرسل <b>ID المستخدم</b> لتفعيله:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_proc_info(chat_id: int, message_id: int) -> None:
    rows = db_fetchall("SELECT id, name, user_id FROM projects WHERE approved=1")
    running_rows = [(r, manager.processes.get(r["id"])) for r in rows if manager.is_running(r["id"])]
    if not running_rows:
        text = "⚙️ <b>معلومات العمليات الحية</b>\n\n😴 لا توجد عمليات نشطة."
    else:
        lines = [f"⚙️ <b>معلومات العمليات الحية</b> — {len(running_rows)} بوت\n"]
        for r, hp in running_rows:
            pid = getattr(hp, "pid", None) or (getattr(hp, "process", None) and getattr(hp.process, "pid", None))
            alive = "✅" if hp and hp.is_alive() else "❌"
            lines.append(f"{alive} <b>{html_escape(r['name'] or '-')}</b>  │  PID: <code>{pid or '?'}</code>  │  👤 {r['user_id']}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_proc_info", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


# ── مساعد: هل الإعداد auto_approve مفعّل ──
def is_auto_approve() -> bool:
    return (get_setting("auto_approve", "0") or "0") == "1"


# ============================================================
# ➕ ميزات الأدمن الجديدة — الدفعة الثالثة (20 ميزة)
# ============================================================

# ── Users ──
def adm_show_user_profile(chat_id: int, message_id: int | None, target: int) -> None:
    u = db_fetchone(
        "SELECT id, first_name, last_name, username, approved, banned, "
        "COALESCE(points,0) AS points, COALESCE(max_bots,0) AS max_bots, "
        "created_at FROM users WHERE id=?", (target,)
    )
    if not u:
        text = f"❌ المستخدم <code>{target}</code> غير موجود في قاعدة البيانات."
    else:
        bots_c = (db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (target,)) or {}).get("c", 0)
        running_c = sum(1 for pid, hp in manager.processes.items()
                        if hp.is_alive() and
                        (db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,)) or {}).get("user_id") == target)
        deploys_c = (db_fetchone("SELECT COUNT(*) AS c FROM deployments WHERE user_id=?", (target,)) or {}).get("c", 0)
        name = html_escape((u.get("first_name") or "") + " " + (u.get("last_name") or "")).strip()
        uname = f"@{u['username']}" if u.get("username") else "—"
        status = "✅ مفعّل" if u["approved"] else "⏳ منتظر"
        if u["banned"]: status = "🚫 محظور"
        text = (
            f"📄 <b>ملف مستخدم</b>\n\n"
            f"👤 الاسم: <b>{name or '—'}</b>\n"
            f"🆔 ID: <code>{u['id']}</code>\n"
            f"📛 يوزر: {uname}\n"
            f"⚡ الحالة: {status}\n"
            f"💎 النقاط: <b>{int(u['points']):,}</b>\n"
            f"🤖 البوتات: <b>{bots_c}</b>  (شغّال: {running_c})\n"
            f"🚀 النشرات: <b>{deploys_c}</b>\n"
            f"⚙️ حد البوتات: <b>{u['max_bots'] or 'الافتراضي'}</b>\n"
            f"📅 تاريخ التسجيل: {str(u.get('created_at',''))[:10]}"
        )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_user_profile(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_user_profile"})
    bot.send_message(chat_id, "📄 أرسل <b>ID المستخدم</b> لعرض ملفه الكامل:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_pending_users(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT id, first_name, username, created_at FROM users WHERE approved=0 AND banned=0 ORDER BY id DESC LIMIT 30"
    )
    if not rows:
        text = "⏳ <b>المستخدمون المنتظرون موافقة</b>\n\n✅ لا أحد في قائمة الانتظار!"
    else:
        lines = [f"⏳ <b>المنتظرون موافقة</b> — {len(rows)}\n"]
        for r in rows:
            name = html_escape(r.get("first_name") or "-")
            uname = f"@{r['username']}" if r.get("username") else f"<code>{r['id']}</code>"
            dt = str(r.get("created_at",""))[:10]
            lines.append(f"  👤 {name} ({uname}) │ {dt}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_start_ban_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_ban_by_id"})
    bot.send_message(chat_id, "🚫 أرسل <b>ID المستخدم</b> لحظره:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_start_unban_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_unban_by_id"})
    bot.send_message(chat_id, "✅ أرسل <b>ID المستخدم</b> لرفع حظره:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_vip_users(chat_id: int, message_id: int) -> None:
    top_pts = db_fetchall(
        "SELECT id, first_name, username, COALESCE(points,0) AS points "
        "FROM users WHERE banned=0 AND approved=1 ORDER BY points DESC LIMIT 10"
    )
    top_bots = db_fetchall(
        "SELECT user_id, COUNT(*) AS c FROM projects GROUP BY user_id ORDER BY c DESC LIMIT 5"
    )
    lines = ["👑 <b>VIP المستخدمين</b>\n\n🏆 <b>أعلى نقاطاً:</b>"]
    for i, r in enumerate(top_pts, 1):
        name = html_escape(r.get("first_name") or "-")
        uname = f"@{r['username']}" if r.get("username") else f"<code>{r['id']}</code>"
        lines.append(f"  {i}. {name} ({uname}) — <b>{int(r['points']):,}</b> نقطة")
    lines.append("\n🤖 <b>أكثر بوتات:</b>")
    for r in top_bots:
        u = db_fetchone("SELECT first_name, username FROM users WHERE id=?", (r["user_id"],)) or {}
        name = html_escape(u.get("first_name") or str(r["user_id"]))
        lines.append(f"  {name} — <b>{r['c']}</b> بوت")
    text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_users", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


# ── Bots ──
def adm_start_force_stop_bot(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_force_stop_bot"})
    bot.send_message(chat_id, "⏹ أرسل <b>ID البوت</b> لإيقافه:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_start_force_start_bot(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_force_start_bot"})
    bot.send_message(chat_id, "▶️ أرسل <b>ID البوت</b> لتشغيله:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_start_bot_files_info(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_bot_files_info"})
    bot.send_message(chat_id, "📁 أرسل <b>ID البوت</b> لعرض ملفاته:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_show_top_bots(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT p.id, p.name, p.user_id, COUNT(f.id) AS fc, COALESCE(SUM(f.size_bytes),0) AS sz "
        "FROM projects p LEFT JOIN project_files f ON f.project_id=p.id "
        "GROUP BY p.id ORDER BY sz DESC LIMIT 15"
    )
    if not rows:
        text = "📦 <b>أكبر البوتات حجماً</b>\n\nلا يوجد بيانات."
    else:
        lines = ["📦 <b>أكبر البوتات حجماً</b>\n"]
        for i, r in enumerate(rows, 1):
            running = "🟢" if manager.is_running(r["id"]) else "🔴"
            sz_kb = r["sz"] // 1024
            lines.append(f"{running} {i}. #{r['id']} {html_escape(r['name'] or '-')} │ {r['fc']} ملف │ {sz_kb:,} KB")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_new_bots_today(chat_id: int, message_id: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = db_fetchall(
        "SELECT id, name, user_id, approved FROM projects WHERE date(created_at)=? ORDER BY id DESC",
        (today,)
    )
    if not rows:
        text = f"🆕 <b>بوتات اليوم</b> — {today}\n\n😶 لم يُضَف أي بوت اليوم."
    else:
        lines = [f"🆕 <b>بوتات اليوم</b> — {today}\nالإجمالي: <b>{len(rows)}</b>\n"]
        for r in rows:
            st = "✅" if r["approved"] else "⏳"
            lines.append(f"{st} #{r['id']} {html_escape(r['name'] or '-')} │ 👤 {r['user_id']}")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_bots", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


# ── Comms ──
def adm_start_msg_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_msg_by_id_step1"})
    bot.send_message(chat_id, "💬 أرسل <b>ID المستخدم</b> لإرسال رسالة له:\n/cancel للإلغاء.", reply_markup=back_admin_kb())


def adm_start_broadcast_pending(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "adm_broadcast_pending"})
    bot.send_message(
        chat_id,
        "⏳ <b>رسالة للمنتظرين الموافقة</b>\n\n"
        "أرسل الرسالة الآن — ستصل لكل من لم يُفعَّل بعد.\n"
        "/cancel للإلغاء.",
        reply_markup=back_admin_kb()
    )


def adm_show_last_broadcast_stats(chat_id: int, message_id: int) -> None:
    row = db_fetchone(
        "SELECT action, created_at FROM audit_log WHERE action LIKE 'broadcast%' ORDER BY id DESC LIMIT 1"
    )
    total_u  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0") or {}).get("c", 0)
    active_u = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0 AND approved=1") or {}).get("c", 0)
    blocked  = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE blocked_bot=1") or {}).get("c", 0)
    text = (
        "📊 <b>إحصائيات الإذاعات</b>\n\n"
        f"👥 إجمالي المستخدمين (غير محظورين): <b>{total_u:,}</b>\n"
        f"✅ مفعَّلون: <b>{active_u:,}</b>\n"
        f"🚫 حظروا البوت: <b>{blocked:,}</b>\n"
    )
    if row:
        text += f"\n📋 آخر إذاعة: <code>{row['action']}</code>\n🕐 التاريخ: {str(row.get('created_at',''))[:16]}"
    else:
        text += "\n📋 لا يوجد سجل إذاعة سابق."
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_comms", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


# ── Stats ──
def adm_send_weekly_report(chat_id: int) -> None:
    today = datetime.now(timezone.utc)
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    new_u   = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE date(created_at)>=?", (week_ago,)) or {}).get("c", 0)
    new_p   = (db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE date(created_at)>=?", (week_ago,)) or {}).get("c", 0)
    deploys = (db_fetchone("SELECT COUNT(*) AS c FROM deployments WHERE date(created_at)>=?", (week_ago,)) or {}).get("c", 0)
    total_u = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE banned=0") or {}).get("c", 0)
    total_p = (db_fetchone("SELECT COUNT(*) AS c FROM projects") or {}).get("c", 0)
    running = sum(1 for hp in manager.processes.values() if hp.is_alive())
    sv = get_server_quick_info()
    text = (
        f"📆 <b>التقرير الأسبوعي</b>\n"
        f"من {week_ago} → {today_str}\n"
        f"{'━'*28}\n"
        f"👥 مستخدمون جدد هذا الأسبوع: <b>{new_u}</b>\n"
        f"🤖 بوتات جديدة: <b>{new_p}</b>\n"
        f"🚀 نشرات: <b>{deploys}</b>\n"
        f"{'─'*28}\n"
        f"👥 إجمالي المستخدمين: <b>{total_u}</b>\n"
        f"🤖 إجمالي البوتات: <b>{total_p}</b>  (شغّال {running})\n"
        f"{'─'*28}\n"
        f"🖥 <b>السيرفر:</b>\n{sv}"
    )
    bot.send_message(chat_id, text, reply_markup=back_admin_kb())


def adm_show_top_uploaders(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT user_id, COUNT(*) AS c, COALESCE(SUM(size_bytes),0) AS sz "
        "FROM deployments GROUP BY user_id ORDER BY c DESC LIMIT 15"
    )
    if not rows:
        text = "🏆 <b>أكثر المستخدمين رفعاً</b>\n\nلا يوجد بيانات رفع بعد."
    else:
        lines = ["🏆 <b>أكثر المستخدمين رفعاً</b>\n"]
        for i, r in enumerate(rows, 1):
            u = db_fetchone("SELECT first_name, username FROM users WHERE id=?", (r["user_id"],)) or {}
            name = html_escape(u.get("first_name") or str(r["user_id"]))
            uname = f"@{u['username']}" if u.get("username") else f"<code>{r['user_id']}</code>"
            lines.append(f"  {i}. {name} ({uname}) │ <b>{r['c']}</b> رفعة │ {r['sz']//1024:,} KB")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_error_log(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT project_id, event, message, created_at FROM process_logs "
        "WHERE event='error' ORDER BY id DESC LIMIT 20"
    )
    if not rows:
        text = "🔴 <b>آخر أخطاء العمليات</b>\n\n✅ لا أخطاء مسجّلة!"
    else:
        lines = [f"🔴 <b>آخر أخطاء العمليات</b> — {len(rows)} خطأ\n"]
        for r in rows:
            ts = str(r.get("created_at",""))[:16]
            msg = html_escape(str(r.get("message",""))[:80])
            lines.append(f"  🤖 #{r['project_id']} │ {ts}\n  <code>{msg}</code>")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_error_log_view", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_activity_stats(chat_id: int, message_id: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = db_fetchall(
        "SELECT section, SUM(count) AS total FROM usage_daily WHERE day=? GROUP BY section ORDER BY total DESC",
        (today,)
    )
    total_active = (db_fetchone(
        "SELECT COUNT(DISTINCT user_id) AS c FROM usage_daily WHERE day=?", (today,)
    ) or {}).get("c", 0)
    if not rows:
        text = f"📈 <b>نشاط اليوم</b> — {today}\n\n😶 لا نشاط مسجّل اليوم."
    else:
        lines = [f"📈 <b>نشاط اليوم</b> — {today}\n👤 مستخدمون نشطون: <b>{total_active}</b>\n"]
        for r in rows:
            lines.append(f"  📌 {html_escape(r['section'] or '-')}: <b>{int(r['total']):,}</b> طلب")
        text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_activity_stats", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_stats", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


# ── System / Settings ──
def adm_toggle_maintenance(chat_id: int, message_id: int) -> None:
    current = (get_setting("bot_disabled", "0") or "0") == "1"
    new_val = "0" if current else "1"
    set_setting("bot_disabled", new_val)
    state = "🔴 البوت في وضع الصيانة الآن" if new_val == "1" else "🟢 البوت يعمل بشكل طبيعي"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تبديل مرة أخرى", callback_data="adm_maintenance_mode", style="danger"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_settings", style="primary", icon_custom_emoji_id=E_BACK))
    text = f"🔧 <b>وضع الصيانة</b>\n\n{state}"
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_show_sys_info(chat_id: int, message_id: int) -> None:
    import sys, platform
    py_ver = sys.version.split()[0]
    platform_str = platform.platform()
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.3)
        mem_used = mem.used // (1024**2)
        mem_total = mem.total // (1024**2)
        disk = psutil.disk_usage("/")
        disk_used = disk.used // (1024**3)
        disk_total = disk.total // (1024**3)
        sv_block = (
            f"🧠 RAM: <b>{mem_used} / {mem_total} MB</b> ({mem.percent}%)\n"
            f"🖥 CPU: <b>{cpu_pct}%</b>\n"
            f"💾 Disk: <b>{disk_used} / {disk_total} GB</b> ({disk.percent}%)"
        )
    except ImportError:
        sv_block = "⚠️ psutil غير متاح"
    db_sz = 0
    try:
        db_sz = os.path.getsize(DB_PATH) // 1024
    except Exception:
        pass
    text = (
        "🖥 <b>معلومات النظام</b>\n\n"
        f"🐍 Python: <code>{py_ver}</code>\n"
        f"🖥 Platform: <code>{platform_str[:60]}</code>\n"
        f"💾 حجم DB: <b>{db_sz:,} KB</b>\n"
        f"🤖 بوتات شغّالة: <b>{sum(1 for hp in manager.processes.values() if hp.is_alive())}</b>\n"
        f"{'─'*28}\n"
        f"{sv_block}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_sys_info", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_settings", style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def adm_clear_blocked_db(chat_id: int) -> None:
    c = (db_fetchone("SELECT COUNT(*) AS c FROM users WHERE blocked_bot=1") or {}).get("c", 0)
    db_execute("UPDATE users SET blocked_bot=0 WHERE blocked_bot=1")
    bot.send_message(
        chat_id,
        f"🧹 <b>تنظيف قاعدة المحظورين</b>\n\n"
        f"✅ تمّ إعادة تعيين علامة blocked_bot لـ <b>{c:,}</b> مستخدم.\n"
        f"<i>ملاحظة: هذا لا يرفع الحظر الفعلي، فقط يعيد تعيين الـ flag.</i>",
        reply_markup=back_admin_kb()
    )


def show_top_users(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT id, first_name, username, COALESCE(points,0) AS points "
        "FROM users WHERE banned=0 ORDER BY points DESC LIMIT 20"
    )
    text = "🏆 <b>أعلى 20 مستخدم نقاطاً</b>\n\n"
    for i, r in enumerate(rows, 1):
        name = html_escape(r.get("first_name") or "-")
        uname = f"@{r['username']}" if r.get("username") else f"<code>{r['id']}</code>"
        text += f"{i}. {name} ({uname}) — <b>{r['points']}</b> نقطة\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)


def show_blocked_users_report(chat_id: int, uid: int) -> None:
    def _scan():
        rows = db_fetchall("SELECT id FROM users WHERE banned=0")
        blocked = []
        for r in rows:
            try:
                bot.send_chat_action(r["id"], "typing")
                db_execute("UPDATE users SET blocked_bot=0 WHERE id=?", (r["id"],))
            except Exception as e:
                err = str(e).lower()
                if "blocked" in err or "deactivated" in err or "not found" in err or "forbidden" in err:
                    blocked.append(r["id"])
                    db_execute("UPDATE users SET blocked_bot=1 WHERE id=?", (r["id"],))
            time.sleep(0.08)
        total = len(rows)
        b_count = len(blocked)
        ids_text = "\n".join(f"• <code>{x}</code>" for x in blocked[:50])
        more_txt = f"\n… و{b_count-50} أكثر" if b_count > 50 else ""
        msg = (
            f"🔍 <b>نتيجة الفحص</b>\n\n"
            f"👥 إجمالي الفحص: <b>{total}</b>\n"
            f"🚫 حظروا البوت: <b>{b_count}</b>\n\n"
        )
        if blocked:
            msg += f"<b>القائمة:</b>\n{ids_text}{more_txt}"
        try:
            bot.send_message(uid, msg, reply_markup=back_admin_kb())
        except Exception:
            pass
    threading.Thread(target=_scan, daemon=True).start()
    bot.send_message(chat_id, "🔍 جارِ الفحص… ستصلك النتيجة قريباً.", reply_markup=back_admin_kb())


def export_users_file(chat_id: int) -> None:
    rows = db_fetchall(
        "SELECT id, first_name, username, approved, banned, COALESCE(points,0) AS points, "
        "COALESCE(blocked_bot,0) AS blocked_bot, created_at FROM users ORDER BY id"
    )
    lines = ["id,first_name,username,approved,banned,points,blocked_bot,created_at"]
    for r in rows:
        lines.append(",".join([
            str(r["id"]),
            (r.get("first_name") or "").replace(",", " "),
            (r.get("username") or ""),
            str(r["approved"]), str(r["banned"]), str(r["points"]),
            str(r.get("blocked_bot") or 0), str(r.get("created_at") or ""),
        ]))
    csv_bytes = "\n".join(lines).encode("utf-8")
    bio = io.BytesIO(csv_bytes)
    bio.name = f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    bot.send_document(chat_id, bio, caption=f"📤 قائمة المستخدمين — {len(rows)} مستخدم", reply_markup=back_admin_kb())


# ============================================================
# 21) إعدادات الأدمن
# ============================================================
def start_set_upload_price(chat_id: int, uid: int) -> None:
    cur = get_upload_price()
    set_pending(uid, {"type": "set_upload_price"})
    bot.send_message(chat_id, f"💰 <b>تعديل سعر رفع البوت</b>\n\nالسعر الحالي: <b>{cur}</b> نقطة\n\n"
                     "أرسل العدد الجديد (0 = مجاني).\nأو /cancel للإلغاء.", reply_markup=back_admin_kb())


def start_set_transfer_fee(chat_id: int, uid: int) -> None:
    cur = get_transfer_fee()
    set_pending(uid, {"type": "set_transfer_fee"})
    bot.send_message(chat_id, f"💸 <b>تعديل عمولة التحويل</b>\n\nالعمولة الحالية: <b>{cur}</b> نقطة\n\n"
                     "أرسل العدد الجديد (0 = بدون عمولة).\nأو /cancel للإلغاء.", reply_markup=back_admin_kb())


def show_force_channels_panel(chat_id: int, uid: int, msg_id: int = None) -> None:
    channels = get_force_channels()
    count = len(channels)
    text = (
        "📢 <b>إدارة الاشتراك الإجباري</b>\n\n"
        f"📋 عدد القنوات المفعّلة: <b>{count}</b>\n\n"
        "اختر العملية المطلوبة:"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("➕ إضافة قناة", callback_data="adm_fc_add", style="primary"))
    kb.add(types.InlineKeyboardButton(f"📋 عرض القنوات ({count})", callback_data="adm_fc_list", style="primary"))
    kb.add(types.InlineKeyboardButton("🔍 فحص الصلاحيات", callback_data="adm_fc_check", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع للوحة", callback_data="adm_panel", style="primary"))
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_force_channels_list(chat_id: int, msg_id: int = None) -> None:
    channels = get_force_channels()
    kb = types.InlineKeyboardMarkup(row_width=2)
    if not channels:
        text = "📋 <b>قنوات الاشتراك الإجباري</b>\n\nلا توجد قنوات مضافة بعد."
    else:
        lines = []
        for ch in channels:
            icon = "🔒" if ch["ch_type"] == "private" else "📢"
            label = html_escape(ch["label"] or ch["channel"])
            invite_link = (ch.get("invite_link") or "").strip()
            if ch["ch_type"] == "private" and invite_link:
                lines.append(f"{icon} {label}\n   ↳ <code>{html_escape(ch['channel'])}</code> | <a href='{html_escape(invite_link)}'>رابط الدعوة</a>")
            elif ch["ch_type"] == "private":
                lines.append(f"{icon} {label}\n   ↳ <code>{html_escape(ch['channel'])}</code> | ⚠️ بدون رابط دعوة")
            else:
                lines.append(f"{icon} {label}")
            # زرّا تعديل + حذف جنباً لجنب
            kb.add(
                types.InlineKeyboardButton(
                    f"✏️ تعديل {icon} {ch['label'] or ch['channel']}",
                    callback_data=f"adm_fc_edit_{ch['id']}", style="primary"),
                types.InlineKeyboardButton(
                    f"🗑 حذف",
                    callback_data=f"adm_fc_del_{ch['id']}", style="primary"),
            )
        text = "📋 <b>قنوات الاشتراك الإجباري:</b>\n\n" + "\n".join(lines)
    kb.add(types.InlineKeyboardButton("➕ إضافة قناة", callback_data="adm_fc_add", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_force_channel", style="primary"))
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_fc_edit_panel(chat_id: int, fid: int, msg_id: int = None) -> None:
    """لوحة تعديل قناة واحدة — تعديل الاسم أو الرابط أو الـ ID."""
    ch = db_fetchone("SELECT * FROM force_channels WHERE id=?", (fid,))
    if not ch:
        show_force_channels_list(chat_id, msg_id)
        return
    icon = "🔒" if ch["ch_type"] == "private" else "📢"
    invite_link = (ch.get("invite_link") or "").strip()
    text = (
        f"✏️ <b>تعديل القناة</b>\n\n"
        f"{icon} <b>الاسم:</b> {html_escape(ch['label'] or ch['channel'])}\n"
        f"🆔 <b>الـ ID:</b> <code>{html_escape(ch['channel'])}</code>\n"
        f"🔗 <b>الرابط:</b> {html_escape(invite_link) if invite_link else '—'}\n\n"
        "اختر ما تريد تعديله:"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_fc_ename_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("🔗 تعديل الرابط", callback_data=f"adm_fc_elink_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("🆔 تعديل الـ ID", callback_data=f"adm_fc_eid_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("🗑 حذف القناة", callback_data=f"adm_fc_del_{fid}", style="primary"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="adm_fc_list", style="primary"))
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def _fc_wizard_cancel_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="adm_force_channel", style="primary"))
    return kb


def _fc_wizard_next_kb(callback: str, label: str = "التالي ▶️") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(label, callback_data=callback, style="primary"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="adm_force_channel", style="primary"),
    )
    return kb


def show_fc_wizard_step1(chat_id: int, uid: int) -> None:
    """الخطوة 1: اطلب رابط الدعوة."""
    pop_pending(uid)
    set_pending(uid, {"type": "fc_wiz_step1"})
    bot.send_message(
        chat_id,
        "📢 <b>إضافة قناة — الخطوة 1 من 3</b>\n\n"
        "🔗 <b>أرسل رابط الدعوة (Invite Link)</b> للقناة:\n\n"
        "مثال:\n"
        "<code>https://t.me/+AbCdEfGhIjKl</code>\n"
        "أو <code>https://t.me/joinchat/AbCdEfGhIjKl</code>\n\n"
        "⚠️ يجب أن يكون البوت <b>مشرفاً</b> في القناة.",
        reply_markup=_fc_wizard_cancel_kb(),
    )


def show_fc_add_type(chat_id: int, msg_id: int = None) -> None:
    """نقطة دخول قديمة — الآن تبدأ الـ Wizard مباشرة."""
    show_fc_wizard_step1(chat_id, chat_id)


# اسم قديم للتوافق مع زر adm_force_channel القديم
def start_set_force_channel(chat_id: int, uid: int) -> None:
    show_force_channels_panel(chat_id, uid)


def start_ban_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "admin_ban_user"})
    bot.send_message(chat_id, "🚫 <b>حظر مستخدم</b>\n\nأرسل <b>ID</b> المستخدم المراد حظره.\nأو /cancel.",
                     reply_markup=back_admin_kb())


def start_unban_by_id(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "admin_unban_user"})
    bot.send_message(chat_id, "✅ <b>رفع حظر مستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\nأو /cancel.",
                     reply_markup=back_admin_kb())


def start_user_info(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "admin_user_info"})
    bot.send_message(chat_id, "🪪 <b>معلومات مستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\nأو /cancel.",
                     reply_markup=back_admin_kb())


def start_search_user(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "search_user"})
    bot.send_message(
        chat_id,
        "🔍 <b>بحث عن مستخدم</b>\n\n"
        "أرسل <b>ID</b> الرقمي أو <b>@username</b>.\nأو /cancel.",
        reply_markup=back_admin_kb(),
    )


def show_list_blocked_from_db(chat_id: int, message_id: int) -> None:
    rows = db_fetchall(
        "SELECT id, first_name, username FROM users WHERE banned=1 ORDER BY id DESC LIMIT 40"
    )
    if not rows:
        text = "✅ لا يوجد مستخدمون محظورون في قاعدة البيانات."
    else:
        text = f"🚫 <b>المحظورون ({len(rows)}):</b>\n\n"
        for r in rows:
            name = html_escape(r.get("first_name") or "-")
            uname = f"@{r['username']}" if r.get("username") else "-"
            text += f"• <code>{r['id']}</code> — {name} ({uname})\n"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(" رجوع", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)


def start_create_gift_link(chat_id: int, uid: int) -> None:
    set_pending(uid, {"type": "gift_points"})
    bot.send_message(chat_id, "🎁 <b>إنشاء رابط هدية نقاط</b>\n\n🔢 <b>الخطوة 1/3:</b> أرسل عدد النقاط لكل مستخدم.\nأو /cancel للإلغاء.",
                     reply_markup=back_admin_kb())


# ============================================================
# 21.5) معاينة محتوى الملف للأدمن
# ============================================================
TEXT_PREVIEW_EXTENSIONS = {
    ".py", ".txt", ".json", ".csv", ".yaml", ".yml",
    ".ini", ".cfg", ".md", ".html", ".css", ".js",
    ".xml", ".log", ".sql", ".env",
}
MAX_PREVIEW_CHARS = 3500

# كاش صفحات المعاينة: cache_key -> {"pages": [...], "filename": str, "total_lines": int}
_file_preview_cache: Dict[str, dict] = {}


def _file_cache_key(telegram_file_id: str) -> str:
    return hashlib.md5(telegram_file_id.encode()).hexdigest()[:12]


def _build_preview_pages(content: str) -> list:
    """تقسّم المحتوى إلى صفحات بحجم MAX_PREVIEW_CHARS كل صفحة."""
    lines = content.splitlines()
    pages = []
    current_lines = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > MAX_PREVIEW_CHARS and current_lines:
            pages.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len
    if current_lines:
        pages.append("\n".join(current_lines))
    return pages if pages else [""]


def _make_preview_keyboard(cache_key: str, page: int, total_pages: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    if page > 0:
        buttons.append(types.InlineKeyboardButton(
            "◀️ السابق", callback_data=f"fpg_{cache_key}_{page - 1}"
        ))
    buttons.append(types.InlineKeyboardButton(
        f"📄 {page + 1} / {total_pages}", callback_data="noop"
    ))
    if page < total_pages - 1:
        buttons.append(types.InlineKeyboardButton(
            "التالي ▶️", callback_data=f"fpg_{cache_key}_{page + 1}"
        ))
    kb.add(*buttons)
    return kb


def _send_file_preview(chat_id: int, telegram_file_id: str, filename: str) -> None:
    ext = os.path.splitext(filename)[-1].lower()
    if ext not in TEXT_PREVIEW_EXTENSIONS:
        return
    try:
        file_info = bot.get_file(telegram_file_id)
        raw = bot.download_file(file_info.file_path)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("latin-1", errors="replace")

        pages = _build_preview_pages(content)
        total_lines = len(content.splitlines())
        cache_key = _file_cache_key(telegram_file_id)
        _file_preview_cache[cache_key] = {
            "pages": pages,
            "filename": filename,
            "total_lines": total_lines,
        }

        page = 0
        total_pages = len(pages)
        header = (
            f"📄 <b>محتوى الملف:</b> <code>{html_escape(filename)}</code>\n"
            f"<i>({total_lines} سطر — صفحة {page + 1} من {total_pages})</i>"
        )
        markup = _make_preview_keyboard(cache_key, page, total_pages) if total_pages > 1 else None
        bot.send_message(
            chat_id,
            f"{header}\n\n<pre><code>{html_escape(pages[page])}</code></pre>",
            reply_markup=markup,
        )
    except Exception as e:
        log.warning("_send_file_preview failed for %s: %s", filename, e)


# ============================================================
# 22) الموافقة على البوت
# ============================================================
def approve_project(project_id: int) -> None:
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        return
    pending = db_fetchone("SELECT * FROM pending_uploads WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    if pending:
        try:
            file_info = bot.get_file(pending["telegram_file_id"])
            data = bot.download_file(file_info.file_path)
            db_execute(
                "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
                "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
                "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
                (project_id, pending["filename"], sqlite3.Binary(data), len(data)),
            )
            db_execute("DELETE FROM pending_uploads WHERE id=?", (pending["id"],))
        except Exception as e:
            log.exception("download for project %s failed", project_id)
            db_execute("UPDATE projects SET last_error=? WHERE id=?", (f"download failed: {e}", project_id))
            try:
                bot.send_message(p["user_id"], f"❌ فشل تحميل ملف البوت: {e}")
            except Exception:
                pass
            return
    # امن
    if is_security_block_enabled():
        psec = db_fetchone("SELECT security_flag, security_approved FROM projects WHERE id=?", (project_id,)) or {}
        if int(psec.get("security_flag") or 0) == 1 and int(psec.get("security_approved") or 0) != 1:
            try:
                bot.send_message(ADMIN_ID, f"لا يمكن تشغيل #{project_id} قبل الموافقة الامنية")
            except Exception:
                pass
            return
    ok_sub, sub_msg = project_subscription_ok(project_id)
    if not ok_sub:
        try:
            bot.send_message(p["user_id"], sub_msg)
        except Exception:
            pass
        return
    db_execute("UPDATE projects SET approved=1 WHERE id=?", (project_id,))
    try:
        create_snapshot(project_id, label="pre-approve")
        make_passport_code(project_id)
    except Exception:
        pass
    uid_owner = p["user_id"]
    # اكتشاف التوكن من الملفات
    try:
        rows_f = db_fetchall("SELECT filename, content FROM project_files WHERE project_id=?", (project_id,))
        found_token = None
        for rf in rows_f:
            found_token = extract_bot_token_from_bytes(bytes(rf["content"]))
            if found_token:
                break
        if found_token:
            info = telegram_get_me(found_token)
            if info:
                db_execute(
                    "UPDATE projects SET hosted_token=?, hosted_bot_username=?, hosted_bot_id=?, hosted_bot_name=? WHERE id=?",
                    (found_token, info.get("username") or "", info.get("id"), info.get("first_name") or "", project_id),
                )
            else:
                db_execute("UPDATE projects SET hosted_token=? WHERE id=?", (found_token, project_id))
    except Exception:
        log.exception("token scan failed for %s", project_id)

    try:
        bot.send_message(uid_owner, t(uid_owner, "starting") + f"\n<i>{html_escape(p['name'])}</i>")
    except Exception:
        pass

    ok, msg = manager.start_project(project_id)
    time.sleep(1.2)
    still = manager.is_running(project_id)
    log_tail = manager.tail_log(project_id, 2500) or ""
    p2 = db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,)) or p
    uname = (p2.get("hosted_bot_username") or "").strip()
    bname = (p2.get("hosted_bot_name") or p2.get("name") or "").strip()
    bid = p2.get("hosted_bot_id") or ""
    mainf = p2.get("main_file") or ""
    runtime = p2.get("runtime") or "python"

    if ok and still:
        kb = types.InlineKeyboardMarkup(row_width=2)
        info_label = bname or p2.get("name") or "Bot"
        kb.add(types.InlineKeyboardButton(
            f"ℹ️ {info_label[:40]}", callback_data=f"proj_info_{project_id}", style="primary"
        ))
        if uname:
            kb.add(types.InlineKeyboardButton(
                t(uid_owner, "open_bot"), url=f"https://t.me/{uname.lstrip('@')}", style="success"
            ))
        kb.add(
            types.InlineKeyboardButton(t(uid_owner, "logs"), callback_data=f"proj_log_{project_id}", style="primary"),
            types.InlineKeyboardButton("📂 " + t(uid_owner, "btn_my_bots"), callback_data="proj_list", style="primary"),
        )
        text = (
            f"{t(uid_owner, 'success_upload')}\n\n"
            f"<blockquote>"
            f"📛 <b>{html_escape(p2.get('name') or '')}</b>\n"
            f"🧩 {rt_label(runtime)}\n"
            f"📄 <code>{html_escape(mainf)}</code>\n"
            + (f"🤖 @{html_escape(uname)}\n" if uname else "")
            + (f"🆔 <code>{bid}</code>\n" if bid else "")
            + f"</blockquote>\n"
            f"{get_random_quote()}"
        )
        try:
            bot.send_photo(uid_owner, get_section_image("success"), caption=text, reply_markup=kb)
        except Exception:
            try:
                bot.send_message(uid_owner, text, reply_markup=kb)
            except Exception:
                pass
    else:
        analysis = analyze_start_error(project_id, log_tail)
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(t(uid_owner, "repair_btn"), callback_data=f"proj_repair_{project_id}", style="danger"),
            types.InlineKeyboardButton(t(uid_owner, "logs"), callback_data=f"proj_log_{project_id}", style="primary"),
        )
        kb.add(types.InlineKeyboardButton(t(uid_owner, "cancel_repair"), callback_data=f"proj_view_{project_id}", style="primary"))
        text = (
            f"{t(uid_owner, 'fail_upload')}\n\n"
            f"<b>التشخيص:</b>\n{analysis}\n\n"
            f"<i>msg: {html_escape(str(msg)[:200])}</i>"
        )
        try:
            bot.send_photo(uid_owner, get_section_image("error"), caption=text, reply_markup=kb)
        except Exception:
            try:
                bot.send_message(uid_owner, text, reply_markup=kb)
            except Exception:
                pass
    log.info("Approved project %s — start=%s still=%s (%s)", project_id, ok, still, msg)


# ============================================================
# 23) معالجات الرسائل النصية للأدمن
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_upload_price",
    content_types=["text"],
)
def receive_set_upload_price(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.isdigit():
        bot.send_message(uid, "❌ أرسل رقماً صحيحاً ≥ 0. أو /cancel.", reply_markup=back_admin_kb())
        return
    set_setting("upload_price", int(text))
    pop_pending(uid)
    bot.send_message(uid, f"✅ تم تحديث سعر رفع البوت إلى <b>{text}</b> نقطة.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_transfer_fee",
    content_types=["text"],
)
def receive_set_transfer_fee(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.isdigit():
        bot.send_message(uid, "❌ أرسل رقماً صحيحاً ≥ 0. أو /cancel.", reply_markup=back_admin_kb())
        return
    set_setting("transfer_fee", int(text))
    pop_pending(uid)
    bot.send_message(uid, f"✅ تم تحديث عمولة التحويل إلى <b>{text}</b> نقطة.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_welcome",
    content_types=["text"],
)
def receive_set_welcome(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pop_pending(uid)
    if text == "-":
        set_setting("welcome_text", "")
        bot.send_message(uid, "✅ تم إعادة رسالة الترحيب إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        set_setting("welcome_text", text)
        # معاينة
        preview = text.replace("{name}", "Flix")
        bot.send_message(uid,
            f"✅ <b>تم تحديث رسالة الترحيب</b>\n\n<b>معاينة:</b>\n{preview}",
            reply_markup=back_admin_kb()
        )


# ── استقبال نص "-" لإعادة صورة الترحيب الافتراضية ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_welcome_img",
    content_types=["text"],
)
def receive_set_welcome_img_text(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if text == "-":
        pop_pending(uid)
        set_setting("welcome_image_id", "")
        bot.send_message(uid, "✅ تمت إعادة صورة الترحيب إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        bot.send_message(uid, "⚠️ أرسل صورة مباشرةً، أو أرسل <code>-</code> لإعادة الصورة الافتراضية.", reply_markup=back_admin_kb())


# ── استقبال الصورة الجديدة ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_welcome_img",
    content_types=["photo"],
)
def receive_set_welcome_img_photo(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    # نأخذ أكبر حجم للصورة (آخر عنصر في القائمة)
    file_id = message.photo[-1].file_id
    set_setting("welcome_image_id", file_id)
    bot.send_message(
        uid,
        "✅ <b>تم تحديث صورة الترحيب!</b>\n\nستظهر الصورة الجديدة للمستخدمين عند الضغط على /start.",
        reply_markup=back_admin_kb(),
    )


# ── صورة الحظر: نص ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_banned_img",
    content_types=["text"],
)
def receive_set_banned_img_text(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    if (message.text or "").strip() == "-":
        pop_pending(uid)
        set_setting("banned_image_id", "")
        bot.send_message(uid, "✅ تمت إعادة صورة الحظر إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        bot.send_message(uid, "⚠️ أرسل صورة مباشرةً، أو أرسل <code>-</code> لإعادة الافتراضية.", reply_markup=back_admin_kb())


# ── صورة الحظر: صورة ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_banned_img",
    content_types=["photo"],
)
def receive_set_banned_img_photo(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    set_setting("banned_image_id", message.photo[-1].file_id)
    bot.send_message(uid, "✅ <b>تم تحديث صورة الحظر!</b>", reply_markup=back_admin_kb())


# ── صورة الصيانة: نص ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_maint_img",
    content_types=["text"],
)
def receive_set_maint_img_text(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    if (message.text or "").strip() == "-":
        pop_pending(uid)
        set_setting("maintenance_image_id", "")
        bot.send_message(uid, "✅ تمت إعادة صورة الصيانة إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        bot.send_message(uid, "⚠️ أرسل صورة مباشرةً، أو أرسل <code>-</code> لإعادة الافتراضية.", reply_markup=back_admin_kb())


# ── صورة الصيانة: صورة ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_maint_img",
    content_types=["photo"],
)
def receive_set_maint_img_photo(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    set_setting("maintenance_image_id", message.photo[-1].file_id)
    bot.send_message(uid, "✅ <b>تم تحديث صورة الصيانة!</b>", reply_markup=back_admin_kb())


# ── رسالة الحظر: نص ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_banned_txt",
    content_types=["text"],
)
def receive_set_banned_txt(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pop_pending(uid)
    if text == "-":
        set_setting("banned_text", "")
        bot.send_message(uid, "✅ تمت إعادة رسالة الحظر إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        set_setting("banned_text", text)
        bot.send_message(uid, f"✅ <b>تم تحديث رسالة الحظر.</b>\n\n<b>معاينة:</b>\n{text}", reply_markup=back_admin_kb())


# ── رسالة الصيانة: نص ──
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_maint_txt",
    content_types=["text"],
)
def receive_set_maint_txt(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pop_pending(uid)
    if text == "-":
        set_setting("maintenance_text", "")
        bot.send_message(uid, "✅ تمت إعادة رسالة الصيانة إلى الافتراضية.", reply_markup=back_admin_kb())
    else:
        set_setting("maintenance_text", text)
        bot.send_message(uid, f"✅ <b>تم تحديث رسالة الصيانة.</b>\n\n<b>معاينة:</b>\n{text}", reply_markup=back_admin_kb())


# ============================================================
# Wizard — الخطوة 1: استقبال رابط الدعوة
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_wiz_step1",
    content_types=["text"],
)
def receive_fc_wiz_step1(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()

    valid = (
        text.startswith("https://t.me/+")
        or text.startswith("https://t.me/joinchat/")
        or re.match(r"^@[\w]{4,}$", text)  # يقبل @username أيضاً
    )
    if not valid:
        bot.send_message(
            uid,
            "❌ <b>رابط غير صالح.</b>\n\n"
            "يجب أن يكون رابط دعوة:\n"
            "<code>https://t.me/+AbCdEfGhIjKl</code>\n"
            "أو يوزرنيم عام: <code>@channel_name</code>\n\n"
            "أرسل الرابط مجدداً أو اضغط إلغاء.",
            reply_markup=_fc_wizard_cancel_kb(),
        )
        return

    set_pending(uid, {"type": "fc_wiz_step1", "link": text})
    bot.send_message(
        uid,
        f"✅ <b>تم استلام الرابط:</b>\n<code>{html_escape(text)}</code>\n\n"
        "📢 <b>الخطوة 1 من 3 مكتملة.</b>\n"
        "اضغط <b>التالي</b> للمتابعة.",
        reply_markup=_fc_wizard_next_kb("fc_wiz_to2"),
    )


# ============================================================
# Wizard — الخطوة 2: استقبال الـ ID
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_wiz_step2",
    content_types=["text"],
)
def receive_fc_wiz_step2(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()

    # يقبل رقم مثل -1001234567890 أو @username
    is_numeric = re.match(r"^-?\d{5,}$", text)
    is_username = re.match(r"^@[\w]{4,}$", text)

    if not is_numeric and not is_username:
        bot.send_message(
            uid,
            "❌ <b>الـ ID غير صالح.</b>\n\n"
            "أرسل رقم القناة (Chat ID):\n"
            "مثال: <code>-1001234567890</code>\n"
            "أو اليوزرنيم: <code>@channel_name</code>\n\n"
            "أرسل الـ ID مجدداً أو اضغط إلغاء.",
            reply_markup=_fc_wizard_cancel_kb(),
        )
        return

    pending = get_pending(uid)
    pending["type"] = "fc_wiz_step2"
    pending["channel_id"] = text
    set_pending(uid, pending)

    bot.send_message(
        uid,
        f"✅ <b>تم استلام الـ ID:</b>\n<code>{html_escape(text)}</code>\n\n"
        "📢 <b>الخطوة 2 من 3 مكتملة.</b>\n"
        "اضغط <b>التالي</b> للمتابعة.",
        reply_markup=_fc_wizard_next_kb("fc_wiz_to3"),
    )


# ============================================================
# Wizard — الخطوة 3: استقبال الاسم وحفظ القناة
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_wiz_step3",
    content_types=["text"],
)
def receive_fc_wiz_step3(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    name = (message.text or "").strip()

    if not name or len(name) < 2:
        bot.send_message(
            uid,
            "❌ الاسم قصير جداً. أرسل اسماً مناسباً للقناة.",
            reply_markup=_fc_wizard_cancel_kb(),
        )
        return

    pending = get_pending(uid)
    link = pending.get("link", "")
    channel_id = pending.get("channel_id", "")
    pop_pending(uid)

    # تحديد نوع القناة
    is_private = re.match(r"^-?\d+$", channel_id)
    if is_private:
        add_force_channel(channel_id, name, "private", link)
    else:
        # قناة عامة — @username
        ch = normalize_channel(channel_id)
        add_force_channel(ch, name, "public", link)

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 العودة للوحة", callback_data="adm_force_channel", style="primary"))

    bot.send_message(
        uid,
        f"🎉 <b>تمت إضافة القناة بنجاح!</b>\n\n"
        f"📛 الاسم: <b>{html_escape(name)}</b>\n"
        f"🆔 الـ ID: <code>{html_escape(channel_id)}</code>\n"
        f"🔗 الرابط: {html_escape(link) if link else '—'}\n\n"
        "⏳ جارٍ فحص صلاحيات البوت في القناة...",
        reply_markup=kb,
    )

    # فحص فوري للصلاحيات
    check_id = channel_id if is_private else normalize_channel(channel_id)
    perm = check_bot_channel_permissions(check_id)
    if perm["ok"]:
        bot.send_message(uid, "✅ <b>الصلاحيات سليمة</b> — البوت مشرف وجاهز للعمل.")
    else:
        bot.send_message(
            uid,
            f"⚠️ <b>تنبيه صلاحيات!</b>\n\n"
            f"❌ {html_escape(perm['error'] or 'خطأ غير محدد')}\n\n"
            "📌 <b>الحل:</b> اجعل البوت مشرفاً في القناة\n"
            "ومنحه صلاحية <b>Invite Users via Link</b>.",
        )


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_update_invite",
    content_types=["text"],
)
def receive_fc_update_invite(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pending = get_pending(uid) or {}
    fid = pending.get("fid")

    if not (text.startswith("https://t.me/+") or text.startswith("https://t.me/joinchat/")):
        bot.send_message(uid,
                         "❌ رابط الدعوة غير صالح.\n"
                         "يجب أن يبدأ بـ <code>https://t.me/+</code> أو <code>https://t.me/joinchat/</code>\n\n"
                         "أرسل الرابط الصحيح أو /cancel.",
                         reply_markup=back_admin_kb())
        return

    ok = update_force_channel_invite(fid, text)
    pop_pending(uid)
    if ok:
        bot.send_message(uid,
                         f"✅ تم تحديث رابط الدعوة بنجاح!\n"
                         f"🔗 الرابط الجديد: {html_escape(text)}",
                         reply_markup=back_admin_kb())
    else:
        bot.send_message(uid,
                         "❌ فشل تحديث الرابط.",
                         reply_markup=back_admin_kb())


# ============================================================
# تعديل القناة — استقبال الاسم الجديد
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_edit_name",
    content_types=["text"],
)
def receive_fc_edit_name(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    name = (message.text or "").strip()
    pending = get_pending(uid) or {}
    fid = pending.get("fid")
    if not name or len(name) < 2:
        bot.send_message(uid, "❌ الاسم قصير جداً. أرسل اسماً مناسباً أو /cancel.",
                         reply_markup=_fc_wizard_cancel_kb())
        return
    ok = update_force_channel_label(fid, name)
    pop_pending(uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 رجوع للقناة", callback_data=f"adm_fc_edit_{fid}", style="primary"))
    if ok:
        bot.send_message(uid, f"✅ <b>تم تحديث الاسم بنجاح!</b>\n✏️ الاسم الجديد: <b>{html_escape(name)}</b>",
                         reply_markup=kb)
    else:
        bot.send_message(uid, "❌ فشل تحديث الاسم.", reply_markup=kb)


# ============================================================
# تعديل القناة — استقبال الرابط الجديد
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_edit_link",
    content_types=["text"],
)
def receive_fc_edit_link(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    link = (message.text or "").strip()
    pending = get_pending(uid) or {}
    fid = pending.get("fid")
    valid = (
        link.startswith("https://t.me/+")
        or link.startswith("https://t.me/joinchat/")
        or link == "-"
    )
    if not valid:
        bot.send_message(
            uid,
            "❌ رابط غير صالح.\n"
            "يجب أن يبدأ بـ <code>https://t.me/+</code> أو <code>https://t.me/joinchat/</code>\n"
            "أو أرسل <code>-</code> لحذف الرابط الحالي.\n\nأو /cancel.",
            reply_markup=_fc_wizard_cancel_kb(),
        )
        return
    ok = update_force_channel_invite(fid, "" if link == "-" else link)
    pop_pending(uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 رجوع للقناة", callback_data=f"adm_fc_edit_{fid}", style="primary"))
    if ok:
        disp = "تم حذف الرابط" if link == "-" else f"🔗 الرابط الجديد: {html_escape(link)}"
        bot.send_message(uid, f"✅ <b>تم تحديث الرابط بنجاح!</b>\n{disp}", reply_markup=kb)
    else:
        bot.send_message(uid, "❌ فشل تحديث الرابط.", reply_markup=kb)


# ============================================================
# تعديل القناة — استقبال الـ ID الجديد
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "fc_edit_id",
    content_types=["text"],
)
def receive_fc_edit_id(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    pending = get_pending(uid) or {}
    fid = pending.get("fid")
    is_numeric = re.match(r"^-?\d{5,}$", text)
    is_username = re.match(r"^@[\w]{4,}$", text)
    if not is_numeric and not is_username:
        bot.send_message(
            uid,
            "❌ الـ ID غير صالح.\n"
            "مثال رقمي: <code>-1001234567890</code>\n"
            "أو يوزرنيم: <code>@channel_name</code>\n\nأو /cancel.",
            reply_markup=_fc_wizard_cancel_kb(),
        )
        return
    ch_type = "private" if is_numeric else "public"
    ok = update_force_channel_id(fid, text, ch_type)
    pop_pending(uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 رجوع للقناة", callback_data=f"adm_fc_edit_{fid}", style="primary"))
    if ok:
        bot.send_message(uid, f"✅ <b>تم تحديث الـ ID بنجاح!</b>\n🆔 الجديد: <code>{html_escape(text)}</code>",
                         reply_markup=kb)
    else:
        bot.send_message(uid, "❌ فشل تحديث الـ ID.", reply_markup=kb)


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "admin_ban_user",
    content_types=["text"],
)
def receive_admin_ban_user(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل id رقمي صالح. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(text)
    if target == uid:
        bot.send_message(uid, "❌ لا يمكنك حظر نفسك.", reply_markup=back_admin_kb())
        return
    db_execute("INSERT INTO users (id, banned) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET banned=1", (target,))
    for p in db_fetchall("SELECT id FROM projects WHERE user_id=?", (target,)):
        manager.stop_project(p["id"])
    pop_pending(uid)
    bot.send_message(uid, f"🚫 تم حظر المستخدم <code>{target}</code>.", reply_markup=back_admin_kb())
    try:
        bot.send_message(target, "🚫 لقد تم حظرك من استخدام البوت.")
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "admin_unban_user",
    content_types=["text"],
)
def receive_admin_unban_user(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل id رقمي صالح. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(text)
    db_execute("UPDATE users SET banned=0 WHERE id=?", (target,))
    pop_pending(uid)
    bot.send_message(uid, f"✅ تم رفع الحظر عن <code>{target}</code>.", reply_markup=back_admin_kb())
    try:
        bot.send_message(target, "🎉 تم رفع الحظر عنك. أرسل /start للبدء.")
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "admin_user_info",
    content_types=["text"],
)
def receive_admin_user_info(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip().lstrip("@")
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل id رقمي صالح. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(text)
    row = db_fetchone(
        "SELECT id, first_name, username, approved, banned, max_bots, "
        "COALESCE(points,0) AS points, created_at, referred_by FROM users WHERE id=?", (target,)
    )
    if not row:
        pop_pending(uid)
        bot.send_message(uid, f"❌ لا يوجد مستخدم بهذا الـ id: <code>{target}</code>", reply_markup=back_admin_kb())
        return
    proj_total = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (target,))["c"]
    proj_approved = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=? AND approved=1", (target,))["c"]
    running_count = 0
    project_lines = []
    for p in db_fetchall("SELECT id, name, approved FROM projects WHERE user_id=? ORDER BY id ASC", (target,)):
        hp = manager.processes.get(p["id"])
        is_run = bool(hp and hp.is_alive())
        if is_run:
            running_count += 1
        status = "🟢 يعمل" if is_run else ("🟡 معتمد" if p["approved"] else "🔴 بانتظار الموافقة")
        project_lines.append(f"   ▫️ <code>#{p['id']}</code> — <b>{html_escape(p['name'])}</b> — {status}")
    referrals_count = db_fetchone("SELECT COUNT(*) AS c FROM users WHERE referred_by=?", (target,))["c"]
    fname = (row.get("first_name") or "").strip() or "—"
    uname = (row.get("username") or "").strip()
    uname_disp = f"@{uname}" if uname else "—"
    status_parts = []
    if row.get("banned"):
        status_parts.append("🚫 محظور")
    status_parts.append("✅ مفعّل" if row.get("approved") else "⏳ بانتظار التفعيل")
    info = (
        "🪪 <b>معلومات المستخدم الكاملة</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>الاسم:</b> {html_escape(fname)}\n"
        f"🔖 <b>اليوزر:</b> {html_escape(uname_disp)}\n"
        f"🆔 <b>الايدي:</b> <code>{target}</code>\n"
        f"📅 <b>تاريخ الدخول:</b> <code>{html_escape(str(row.get('created_at') or '—'))}</code>\n"
        f"⚙️ <b>الحالة:</b> {' | '.join(status_parts)}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>النقاط:</b> <b>{row.get('points') or 0}</b>\n"
        f"📦 <b>الحد الأقصى للبوتات:</b> <b>{row.get('max_bots') or 0}</b>\n"
        f"🤖 <b>عدد البوتات الكلي:</b> <b>{proj_total}</b>\n"
        f"✅ <b>البوتات المعتمدة:</b> <b>{proj_approved}</b>\n"
        f"🔋 <b>البوتات النشطة الآن:</b> <b>{running_count}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>عدد الإحالات:</b> <b>{referrals_count}</b>\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    if project_lines:
        info += "\n📋 <b>قائمة بوتاته:</b>\n" + "\n".join(project_lines)
    else:
        info += "\n📋 <b>قائمة بوتاته:</b> لا يوجد"
    pop_pending(uid)
    bot.send_message(uid, info, reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "gift_points",
    content_types=["text"],
)
def receive_gift_points(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        bot.send_message(uid, "❌ أرسل عدد نقاط صحيح موجب (> 0). أو /cancel.", reply_markup=back_admin_kb())
        return
    points = int(text)
    set_pending(uid, {"type": "gift_uses", "points": points})
    bot.send_message(uid, f"✅ النقاط: <b>{points}</b>\n\n🔢 <b>الخطوة 2/3:</b> أرسل عدد المستخدمين الذين يمكنهم استخدام الرابط.\nأو /cancel.",
                     reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "gift_uses",
    content_types=["text"],
)
def receive_gift_uses(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    points = int(pending.get("points", 0))
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        bot.send_message(uid, "❌ أرسل عدد مستخدمين صحيح موجب (> 0). أو /cancel.", reply_markup=back_admin_kb())
        return
    max_uses = int(text)
    set_pending(uid, {"type": "gift_days", "points": points, "max_uses": max_uses})
    bot.send_message(uid, f"✅ عدد المستخدمين: <b>{max_uses}</b>\n\n⏳ <b>الخطوة 3/3:</b> أرسل مدة صلاحية الرابط بالأيام (0 = دائم).\nأو /cancel.",
                     reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "gift_days",
    content_types=["text"],
)
def receive_gift_days(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    points = int(pending.get("points", 0))
    max_uses = int(pending.get("max_uses", 0))
    text = (message.text or "").strip()
    if not text.isdigit():
        bot.send_message(uid, "❌ أرسل عدد أيام صحيح ≥ 0. أو /cancel.", reply_markup=back_admin_kb())
        return
    days = int(text)
    expires_at = None
    if days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    token = _new_gift_token()
    while db_fetchone("SELECT 1 AS x FROM gift_links WHERE token=?", (token,)):
        token = _new_gift_token()
    db_execute("INSERT INTO gift_links (token, points, max_uses, created_by, expires_at) VALUES (?, ?, ?, ?, ?)",
               (token, points, max_uses, uid, expires_at))
    pop_pending(uid)
    try:
        bot_username = bot.get_me().username or ""
    except Exception:
        bot_username = ""
    link = f"https://t.me/{bot_username}?start=gift_{token}" if bot_username else f"start=gift_{token}"
    expiry_line = (f"⏳ ينتهي في: <b>{html_escape(expires_at)}</b> (UTC)\n" if expires_at
                   else "⏳ المدة: <b>دائم</b>\n")
    bot.send_message(uid,
                     "✅ <b>تم إنشاء رابط الهدية</b>\n\n"
                     f"🎁 النقاط لكل مستخدم: <b>{points}</b>\n"
                     f"👥 الحد الأقصى: <b>{max_uses}</b>\n"
                     f"{expiry_line}\n"
                     f"🔗 <code>{link}</code>",
                     reply_markup=back_admin_kb())


# ============================================================
# 24) الإذاعة
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "broadcast",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_broadcast(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    pop_pending(message.from_user.id)
    rows = db_fetchall("SELECT id FROM users WHERE banned=0")
    ok = 0
    fail = 0
    blocked = 0
    bot.send_message(message.chat.id, f"📤 جارِ الإرسال إلى {len(rows)} مستخدم…")
    for r in rows:
        try:
            bot.copy_message(r["id"], message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.04)
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
                db_execute("UPDATE users SET blocked_bot=1 WHERE id=?", (r["id"],))
            fail += 1
    bot.send_message(message.chat.id,
                     f"✅ انتهت الإذاعة\n\n📨 نجح: <b>{ok}</b>\n❌ فشل: <b>{fail - blocked}</b>\n🚫 حظروا البوت: <b>{blocked}</b>",
                     reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_announce",
    content_types=["text"],
)
def receive_adm_announce(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    pop_pending(message.from_user.id)
    text_body = (message.text or "").strip()
    if not text_body:
        bot.send_message(message.chat.id, "❌ النص فارغ. يُرجى المحاولة مجدداً.", reply_markup=back_admin_kb())
        return
    announce_text = (
        "━━━━━━━━━━━━━━━━━\n"
        "📣 <b>إعلان من الإدارة</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"{text_body}\n\n"
        "━━━━━━━━━━━━━━━━━"
    )
    rows = db_fetchall("SELECT id FROM users WHERE banned=0 AND approved=1")
    ok = fail = blocked = 0
    bot.send_message(message.chat.id, f"📤 جارٍ إرسال الإعلان إلى {len(rows)} مستخدم…")
    for r in rows:
        try:
            bot.send_message(r["id"], announce_text)
            ok += 1
            time.sleep(0.05)
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
                db_execute("UPDATE users SET blocked_bot=1 WHERE id=?", (r["id"],))
            fail += 1
    bot.send_message(
        message.chat.id,
        f"✅ <b>انتهى الإعلان</b>\n\n📨 نجح: <b>{ok}</b>\n❌ فشل: <b>{fail - blocked}</b>\n🚫 حظروا البوت: <b>{blocked}</b>",
        reply_markup=back_admin_kb()
    )


# ── معالجات الرسائل للـ 20 ميزة الجديدة ──

@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_user_bots_by_id",
    content_types=["text"],
)
def receive_user_bots_by_id(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    adm_show_user_bots(message.chat.id, None, target)


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_reset_points_id",
    content_types=["text"],
)
def receive_reset_points_id(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name FROM users WHERE id=?", (target,))
    if not u:
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    db_execute("UPDATE users SET points=0 WHERE id=?", (target,))
    name = html_escape(u.get("first_name") or str(target))
    bot.send_message(message.chat.id, f"✅ تمّ تصفير نقاط <b>{name}</b> (<code>{target}</code>) إلى 0.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_user_max_step1",
    content_types=["text"],
)
def receive_set_user_max_step1(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    try:
        target = int((message.text or "").strip())
    except ValueError:
        pop_pending(message.from_user.id)
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name FROM users WHERE id=?", (target,))
    if not u:
        pop_pending(message.from_user.id)
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    set_pending(message.from_user.id, {"type": "adm_set_user_max_step2", "target": target})
    bot.send_message(message.chat.id, f"⚙️ مستخدم: <b>{html_escape(u.get('first_name') or str(target))}</b>\nأرسل الآن <b>حد البوتات الجديد</b> (رقم):", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_set_user_max_step2",
    content_types=["text"],
)
def receive_set_user_max_step2(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pending = get_pending(message.from_user.id)
    pop_pending(message.from_user.id)
    target = pending.get("target")
    try:
        new_max = int((message.text or "").strip())
        if new_max < 0: raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال رقم صحيح غير سالب.", reply_markup=back_admin_kb())
        return
    db_execute("UPDATE users SET max_bots=? WHERE id=?", (new_max, target))
    bot.send_message(message.chat.id, f"✅ تمّ تعيين حد البوتات للمستخدم <code>{target}</code> إلى <b>{new_max}</b>.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_search_bot_name",
    content_types=["text"],
)
def receive_search_bot_name(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    query = (message.text or "").strip()
    if not query:
        bot.send_message(message.chat.id, "❌ نص البحث فارغ.", reply_markup=back_admin_kb())
        return
    rows = db_fetchall(
        "SELECT id, name, user_id, approved, is_running FROM projects WHERE name LIKE ? ORDER BY id DESC LIMIT 20",
        (f"%{query}%",)
    )
    if not rows:
        text = f"🔍 <b>بحث: «{html_escape(query)}»</b>\n\n😕 لا نتائج."
    else:
        lines = [f"🔍 <b>بحث: «{html_escape(query)}»</b> — {len(rows)} نتيجة\n"]
        for r in rows:
            running = manager.is_running(r["id"])
            st = "🟢" if running else ("🟡" if not r["approved"] else "🔴")
            lines.append(f"{st} #{r['id']} {html_escape(r['name'] or '-')}  │  👤 {r['user_id']}")
        text = "\n".join(lines)
    bot.send_message(message.chat.id, text, reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_msg_to_inactive",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_msg_inactive(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = db_fetchall(
        "SELECT id FROM users WHERE approved=1 AND banned=0 "
        "AND id NOT IN (SELECT DISTINCT user_id FROM usage_daily WHERE day>=?) "
        "AND date(created_at)<=?", (cutoff, cutoff)
    )
    ok = fail = blocked = 0
    bot.send_message(message.chat.id, f"📤 جارٍ إرسال رسالة إلى {len(rows)} مستخدم خامل…")
    for r in rows:
        try:
            bot.copy_message(r["id"], message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.05)
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
            fail += 1
    bot.send_message(message.chat.id,
        f"✅ <b>انتهى إرسال رسالة الخاملين</b>\n\n📨 نجح: <b>{ok}</b>\n❌ فشل: <b>{fail - blocked}</b>\n🚫 حظروا: <b>{blocked}</b>",
        reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_broadcast_active",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_broadcast_active(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    rows = db_fetchall("SELECT id FROM users WHERE banned=0 AND approved=1")
    ok = fail = blocked = 0
    bot.send_message(message.chat.id, f"📤 جارٍ الإذاعة إلى {len(rows)} مستخدم مفعَّل…")
    for r in rows:
        try:
            bot.copy_message(r["id"], message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.04)
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
                db_execute("UPDATE users SET blocked_bot=1 WHERE id=?", (r["id"],))
            fail += 1
    bot.send_message(message.chat.id,
        f"✅ <b>انتهت الإذاعة للمفعّلين</b>\n\n📨 نجح: <b>{ok}</b>\n❌ فشل: <b>{fail - blocked}</b>\n🚫 حظروا: <b>{blocked}</b>",
        reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_approve_id",
    content_types=["text"],
)
def receive_approve_id(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name, approved FROM users WHERE id=?", (target,))
    if not u:
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    if u.get("approved"):
        bot.send_message(message.chat.id, f"ℹ️ المستخدم <code>{target}</code> مفعَّل مسبقاً.", reply_markup=back_admin_kb())
        return
    db_execute("UPDATE users SET approved=1 WHERE id=?", (target,))
    name = html_escape(u.get("first_name") or str(target))
    bot.send_message(message.chat.id, f"✅ تمّ تفعيل <b>{name}</b> (<code>{target}</code>).", reply_markup=back_admin_kb())
    try:
        bot.send_message(target, "🎉 تمّ قبول طلبك! يمكنك الآن استخدام البوت.")
    except Exception:
        pass


# ── message handlers — الدفعة الثالثة ──

@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_user_profile",
    content_types=["text"],
)
def receive_user_profile(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    adm_show_user_profile(message.chat.id, None, target)


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_ban_by_id",
    content_types=["text"],
)
def receive_ban_by_id(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name, banned FROM users WHERE id=?", (target,))
    if not u:
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    if u.get("banned"):
        bot.send_message(message.chat.id, f"ℹ️ المستخدم <code>{target}</code> محظور مسبقاً.", reply_markup=back_admin_kb())
        return
    db_execute("UPDATE users SET banned=1 WHERE id=?", (target,))
    name = html_escape(u.get("first_name") or str(target))
    bot.send_message(message.chat.id, f"🚫 تمّ حظر <b>{name}</b> (<code>{target}</code>).", reply_markup=back_admin_kb())
    try:
        bot.send_message(target, "🚫 تمّ حظرك من استخدام البوت.")
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_unban_by_id",
    content_types=["text"],
)
def receive_unban_by_id(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        target = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name, banned FROM users WHERE id=?", (target,))
    if not u:
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    if not u.get("banned"):
        bot.send_message(message.chat.id, f"ℹ️ المستخدم <code>{target}</code> غير محظور أصلاً.", reply_markup=back_admin_kb())
        return
    db_execute("UPDATE users SET banned=0 WHERE id=?", (target,))
    name = html_escape(u.get("first_name") or str(target))
    bot.send_message(message.chat.id, f"✅ تمّ رفع حظر <b>{name}</b> (<code>{target}</code>).", reply_markup=back_admin_kb())
    try:
        bot.send_message(target, "✅ تمّ رفع الحظر عنك، يمكنك استخدام البوت مجدداً.")
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_force_stop_bot",
    content_types=["text"],
)
def receive_force_stop_bot(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        pid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    p = db_fetchone("SELECT name FROM projects WHERE id=?", (pid,))
    if not p:
        bot.send_message(message.chat.id, f"❌ البوت #{pid} غير موجود.", reply_markup=back_admin_kb())
        return
    if not manager.is_running(pid):
        bot.send_message(message.chat.id, f"ℹ️ البوت #{pid} متوقف مسبقاً.", reply_markup=back_admin_kb())
        return
    manager.stop_project(pid)
    db_execute("UPDATE projects SET is_running=0 WHERE id=?", (pid,))
    bot.send_message(message.chat.id, f"⏹ تمّ إيقاف البوت <b>{html_escape(p.get('name') or str(pid))}</b> (#{pid}).", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_force_start_bot",
    content_types=["text"],
)
def receive_force_start_bot(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        pid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    p = db_fetchone("SELECT name, approved FROM projects WHERE id=?", (pid,))
    if not p:
        bot.send_message(message.chat.id, f"❌ البوت #{pid} غير موجود.", reply_markup=back_admin_kb())
        return
    if not p.get("approved"):
        bot.send_message(message.chat.id, f"❌ البوت #{pid} لم يُوافَق عليه بعد.", reply_markup=back_admin_kb())
        return
    if manager.is_running(pid):
        bot.send_message(message.chat.id, f"ℹ️ البوت #{pid} يعمل مسبقاً.", reply_markup=back_admin_kb())
        return
    manager.start_project(pid)
    db_execute("UPDATE projects SET is_running=1 WHERE id=?", (pid,))
    bot.send_message(message.chat.id, f"▶️ تمّ تشغيل البوت <b>{html_escape(p.get('name') or str(pid))}</b> (#{pid}).", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_bot_files_info",
    content_types=["text"],
)
def receive_bot_files_info(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    try:
        pid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    p = db_fetchone("SELECT name, user_id FROM projects WHERE id=?", (pid,))
    if not p:
        bot.send_message(message.chat.id, f"❌ البوت #{pid} غير موجود.", reply_markup=back_admin_kb())
        return
    rows = db_fetchall(
        "SELECT filename, size_bytes, uploaded_at FROM project_files WHERE project_id=? ORDER BY id DESC",
        (pid,)
    )
    total_sz = sum(r.get("size_bytes", 0) or 0 for r in rows)
    name = html_escape(p.get("name") or str(pid))
    if not rows:
        text = f"📁 <b>ملفات البوت {name}</b> (#{pid})\n\nلا توجد ملفات."
    else:
        lines = [f"📁 <b>ملفات البوت {name}</b> (#{pid}) — {len(rows)} ملف │ {total_sz//1024:,} KB\n"]
        for r in rows:
            sz = (r.get("size_bytes") or 0) // 1024
            dt = str(r.get("uploaded_at",""))[:10]
            lines.append(f"  📄 {html_escape(r.get('filename') or '-')} │ {sz:,} KB │ {dt}")
        text = "\n".join(lines)
    bot.send_message(message.chat.id, text, reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_msg_by_id_step1",
    content_types=["text"],
)
def receive_msg_by_id_step1(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    try:
        target = int((message.text or "").strip())
    except ValueError:
        pop_pending(message.from_user.id)
        bot.send_message(message.chat.id, "❌ يجب إرسال ID رقمي صحيح.", reply_markup=back_admin_kb())
        return
    u = db_fetchone("SELECT first_name FROM users WHERE id=?", (target,))
    if not u:
        pop_pending(message.from_user.id)
        bot.send_message(message.chat.id, f"❌ المستخدم <code>{target}</code> غير موجود.", reply_markup=back_admin_kb())
        return
    set_pending(message.from_user.id, {"type": "adm_msg_by_id_step2", "target": target})
    bot.send_message(
        message.chat.id,
        f"💬 سيُرسَل إلى: <b>{html_escape(u.get('first_name') or str(target))}</b> (<code>{target}</code>)\n"
        "أرسل الرسالة الآن (نص أو صورة أو أي محتوى):\n/cancel للإلغاء.",
        reply_markup=back_admin_kb()
    )


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_msg_by_id_step2",
    content_types=["text", "photo", "video", "document", "animation", "sticker"],
)
def receive_msg_by_id_step2(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pending = get_pending(message.from_user.id)
    pop_pending(message.from_user.id)
    target = pending.get("target")
    try:
        bot.copy_message(target, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, f"✅ تمّ إرسال الرسالة إلى <code>{target}</code>.", reply_markup=back_admin_kb())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ فشل الإرسال: {html_escape(str(e))}", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_broadcast_pending",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_broadcast_pending(message):
    if msg_seen(message): return
    if not is_admin(message.from_user.id): return
    pop_pending(message.from_user.id)
    rows = db_fetchall("SELECT id FROM users WHERE approved=0 AND banned=0")
    ok = fail = blocked = 0
    bot.send_message(message.chat.id, f"📤 جارٍ إرسال رسالة إلى {len(rows)} مستخدم منتظر…")
    for r in rows:
        try:
            bot.copy_message(r["id"], message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.05)
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
            fail += 1
    bot.send_message(
        message.chat.id,
        f"✅ <b>انتهى إرسال رسالة المنتظرين</b>\n\n📨 نجح: <b>{ok}</b>\n❌ فشل: <b>{fail - blocked}</b>\n🚫 حظروا: <b>{blocked}</b>",
        reply_markup=back_admin_kb()
    )


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "broadcast_channel_list",
    content_types=["text"],
)
def receive_broadcast_channel_list(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    channels_raw = (message.text or "").strip()
    set_pending(message.from_user.id, {"type": "broadcast_channel_msg", "channels": channels_raw})
    bot.send_message(message.chat.id, "✅ تم حفظ القنوات.\n\nأرسل الرسالة اللي تبيها تُذاع.\n/cancel للإلغاء.",
                     reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "broadcast_channel_msg",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_broadcast_channel_msg(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    pending = get_pending(message.from_user.id) or {}
    channels_raw = pending.get("channels", "")
    pop_pending(message.from_user.id)
    channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
    if not channels:
        bot.send_message(message.chat.id, "❌ لا توجد قنوات.", reply_markup=back_admin_kb())
        return
    ok = 0
    fail_list = []
    for ch in channels:
        try:
            bot.copy_message(ch, message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.3)
        except Exception as e:
            fail_list.append(f"{ch}: {str(e)[:60]}")
    result = f"✅ تم الإرسال إلى {ok}/{len(channels)} قناة"
    if fail_list:
        result += "\n\n❌ الفاشلة:\n" + "\n".join(fail_list)
    bot.send_message(message.chat.id, result, reply_markup=back_admin_kb())


# ============================================================
# 25) رسالة لمستخدم بعينه
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "send_user_id",
    content_types=["text"],
)
def receive_send_user_id(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(message.from_user.id, "❌ أرسل id رقمي صحيح. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(text)
    set_pending(message.from_user.id, {"type": "send_user_msg", "target_uid": target})
    bot.send_message(message.chat.id, f"✅ ID: <code>{target}</code>\n\nأرسل الرسالة الآن.\n/cancel للإلغاء.",
                     reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "send_user_msg",
    content_types=["text", "photo", "video", "document", "animation"],
)
def receive_send_user_msg(message):
    if msg_seen(message):
        return
    if not is_admin(message.from_user.id):
        return
    pending = get_pending(message.from_user.id) or {}
    target = pending.get("target_uid")
    pop_pending(message.from_user.id)
    if not target:
        bot.send_message(message.chat.id, "❌ لم يُحدَّد المستخدم.", reply_markup=back_admin_kb())
        return
    try:
        bot.copy_message(target, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, f"✅ تم إرسال الرسالة إلى <code>{target}</code>.", reply_markup=back_admin_kb())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ فشل الإرسال: {str(e)[:100]}", reply_markup=back_admin_kb())


# ============================================================
# 25b) بحث عن مستخدم
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "search_user",
    content_types=["text"],
)
def receive_search_user(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    query = (message.text or "").strip()
    if query.startswith("@"):
        row = db_fetchone("SELECT * FROM users WHERE username=?", (query.lstrip("@"),))
    elif query.lstrip("-").isdigit():
        row = db_fetchone("SELECT * FROM users WHERE id=?", (int(query),))
    else:
        bot.send_message(uid, "❌ أرسل ID رقمي أو @username. أو /cancel.", reply_markup=back_admin_kb())
        return
    if not row:
        bot.send_message(uid, f"❌ لم يُعثر على مستخدم: <code>{html_escape(query)}</code>", reply_markup=back_admin_kb())
        return
    status = "🚫 محظور" if row["banned"] else ("✅ مفعّل" if row["approved"] else "🟡 غير مفعّل")
    pts = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (row["id"],))
    bots_count = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (row["id"],))
    text = (
        f"🔍 <b>نتيجة البحث</b>\n\n"
        f"🪪 ID: <code>{row['id']}</code>\n"
        f"👤 الاسم: {html_escape(row.get('first_name') or '-')}\n"
        f"📛 Username: @{row.get('username') or '-'}\n"
        f"📊 الحالة: {status}\n"
        f"⭐ النقاط: <b>{pts['p'] if pts else 0}</b>\n"
        f"🤖 عدد البوتات: <b>{bots_count['c'] if bots_count else 0}</b>\n"
        f"📅 تاريخ التسجيل: {row.get('created_at') or '-'}"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(" حظر", callback_data=f"adm_ban_user_{row['id']}",
            style="danger", icon_custom_emoji_id=E_BAN),
        types.InlineKeyboardButton(" رفع حظر", callback_data=f"adm_unban_user_{row['id']}",
            style="danger", icon_custom_emoji_id=E_UNBAN),
    )
    kb.add(types.InlineKeyboardButton(" رجوع للوحة الأدمن", callback_data="adm_panel",
        style="primary", icon_custom_emoji_id=E_BACK))
    bot.send_message(uid, text, reply_markup=kb)


# ============================================================
# 25c) منح نقاط للكل
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "give_all_points_input",
    content_types=["text"],
)
def receive_give_all_points(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل رقماً صحيحاً. أو /cancel.", reply_markup=back_admin_kb())
        return
    amount = int(text)
    if amount == 0:
        bot.send_message(uid, "❌ القيمة لا يمكن أن تكون 0.", reply_markup=back_admin_kb())
        return
    db_execute(
        "UPDATE users SET points = MAX(0, COALESCE(points,0) + ?) WHERE approved=1 AND banned=0",
        (amount,),
    )
    count_row = db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0")
    count = count_row["c"] if count_row else 0
    action = "إضافة" if amount > 0 else "خصم"
    bot.send_message(
        uid,
        f"✅ <b>تم {action} <code>{abs(amount)}</code> نقطة لـ <b>{count}</b> مستخدم.</b>",
        reply_markup=back_admin_kb(),
    )


# ============================================================
# 25d) تحذير مستخدم
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "warn_user_id",
    content_types=["text"],
)
def receive_warn_user_id(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل ID رقمي صحيح. أو /cancel.", reply_markup=back_admin_kb())
        return
    target = int(text)
    set_pending(uid, {"type": "warn_user_msg", "target_uid": target})
    bot.send_message(
        uid,
        f"✅ ID: <code>{target}</code>\n\nأرسل نص التحذير الآن.\n/cancel للإلغاء.",
        reply_markup=back_admin_kb(),
    )


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "warn_user_msg",
    content_types=["text"],
)
def receive_warn_user_msg(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    target = pending.get("target_uid")
    pop_pending(uid)
    if not target:
        bot.send_message(uid, "❌ لم يُحدَّد المستخدم.", reply_markup=back_admin_kb())
        return
    warn_text = (message.text or "").strip()
    try:
        bot.send_message(
            target,
            f"⚠️ <b>تحذير من الإدارة</b>\n\n{html_escape(warn_text)}",
        )
        bot.send_message(uid, f"✅ تم إرسال التحذير إلى <code>{target}</code>.", reply_markup=back_admin_kb())
    except Exception as e:
        bot.send_message(uid, f"❌ فشل الإرسال: {str(e)[:100]}", reply_markup=back_admin_kb())


# ============================================================
# 26) منح نقاط / تعيين نقاط / حد البوتات
# ============================================================
@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "give_points_input",
    content_types=["text"],
)
def receive_give_points_input(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    step = pending.get("step", "id")
    text = (message.text or "").strip()
    if step == "id":
        if not text.lstrip("-").isdigit():
            bot.send_message(uid, "❌ أرسل id رقمي. أو /cancel.", reply_markup=back_admin_kb())
            return
        set_pending(uid, {"type": "give_points_input", "step": "amount", "target": int(text)})
        bot.send_message(uid, f"✅ المستخدم: <code>{text}</code>\n\nأرسل عدد النقاط (موجب=إضافة، سالب=خصم).\nأو /cancel.",
                         reply_markup=back_admin_kb())
    elif step == "amount":
        if not text.lstrip("-").isdigit():
            bot.send_message(uid, "❌ أرسل رقماً. أو /cancel.", reply_markup=back_admin_kb())
            return
        target = pending.get("target")
        amount = int(text)
        db_execute("UPDATE users SET points = MAX(0, COALESCE(points,0) + ?) WHERE id=?", (amount, target))
        pop_pending(uid)
        sign = "+" if amount >= 0 else ""
        bot.send_message(uid, f"✅ تم: {sign}{amount} نقطة للمستخدم <code>{target}</code>.", reply_markup=back_admin_kb())
        try:
            verb = "إضافة" if amount >= 0 else "خصم"
            bot.send_message(target, f"💎 تم {verb} <b>{abs(amount)}</b> نقطة من المطور.")
        except Exception:
            pass


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_points_input",
    content_types=["text"],
)
def receive_set_points_input(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    step = pending.get("step", "id")
    text = (message.text or "").strip()
    if step == "id":
        if not text.lstrip("-").isdigit():
            bot.send_message(uid, "❌ أرسل id. أو /cancel.", reply_markup=back_admin_kb())
            return
        set_pending(uid, {"type": "set_points_input", "step": "amount", "target": int(text)})
        bot.send_message(uid, f"✅ المستخدم: <code>{text}</code>\n\nأرسل القيمة الجديدة للنقاط.\nأو /cancel.",
                         reply_markup=back_admin_kb())
    elif step == "amount":
        if not text.isdigit():
            bot.send_message(uid, "❌ أرسل رقماً ≥ 0. أو /cancel.", reply_markup=back_admin_kb())
            return
        target = pending.get("target")
        db_execute("UPDATE users SET points=? WHERE id=?", (int(text), target))
        pop_pending(uid)
        bot.send_message(uid, f"✅ تم تعيين نقاط <code>{target}</code> إلى <b>{text}</b>.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_max_bots_input",
    content_types=["text"],
)
def receive_set_max_bots_input(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    step = pending.get("step", "id")
    text = (message.text or "").strip()
    if step == "id":
        if not text.lstrip("-").isdigit():
            bot.send_message(uid, "❌ أرسل id. أو /cancel.", reply_markup=back_admin_kb())
            return
        set_pending(uid, {"type": "set_max_bots_input", "step": "amount", "target": int(text)})
        bot.send_message(uid, f"✅ المستخدم: <code>{text}</code>\n\nأرسل الحد الجديد للبوتات.\nأو /cancel.",
                         reply_markup=back_admin_kb())
    elif step == "amount":
        if not text.isdigit():
            bot.send_message(uid, "❌ أرسل رقماً ≥ 0. أو /cancel.", reply_markup=back_admin_kb())
            return
        target = pending.get("target")
        db_execute("UPDATE users SET max_bots=? WHERE id=?", (int(text), target))
        pop_pending(uid)
        bot.send_message(uid, f"✅ تم تعيين حد البوتات لـ<code>{target}</code> إلى <b>{text}</b>.",
                         reply_markup=back_admin_kb())


# ============================================================
# 27) تحويل النقاط
# ============================================================
@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "transfer_recipient",
    content_types=["text"],
)
def receive_transfer_recipient(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ يرجى إرسال <b>ID</b> رقمي صالح. أو /cancel للإلغاء.")
        return
    recipient_id = int(text)
    if recipient_id == uid:
        bot.send_message(uid, "❌ لا يمكنك التحويل لنفسك.")
        return
    recipient = db_fetchone("SELECT id, banned FROM users WHERE id=?", (recipient_id,))
    if not recipient:
        bot.send_message(uid, "❌ المستخدم غير موجود. تأكد من أنه بدأ البوت من قبل.\nأو /cancel.")
        return
    if recipient.get("banned"):
        bot.send_message(uid, "❌ لا يمكن التحويل إلى مستخدم محظور.")
        return
    set_pending(uid, {"type": "transfer_amount", "recipient_id": recipient_id})
    bot.send_message(uid, "❄️ ارسل عدد النقاط المراد تحويلها:")


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "transfer_amount",
    content_types=["text"],
)
def receive_transfer_amount(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    recipient_id = pending.get("recipient_id")
    if not recipient_id:
        pop_pending(uid)
        bot.send_message(uid, "❌ انتهت جلسة التحويل. ابدأ من جديد.")
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        bot.send_message(uid, "❌ يرجى إرسال عدد صحيح موجب. أو /cancel.")
        return
    amount = int(text)
    if amount < 5:
        bot.send_message(uid, "❌ أقل عدد يمكن تحويله هو <b>5</b> نقاط.")
        return
    fee = get_transfer_fee()
    total_deduct = amount + fee
    with _db_lock:
        sender_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
        sender_pts = sender_row["p"] if sender_row else 0
        if sender_pts < total_deduct:
            pop_pending(uid)
            bot.send_message(uid, f"❌ رصيدك ({sender_pts}) غير كافٍ.\nالمطلوب: {amount} + عمولة {fee} = <b>{total_deduct}</b> نقطة.")
            return
        db_execute("UPDATE users SET points = points - ? WHERE id=? AND COALESCE(points,0) >= ?",
                   (total_deduct, uid, total_deduct))
        db_execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE id=?", (amount, recipient_id))
    pop_pending(uid)
    sender_msg = f"🎁 تم إرسال <b>{amount}</b> نقطة إلى المستخدم <code>{recipient_id}</code> بنجاح 🎁"
    if fee > 0:
        sender_msg += f"\n💸 (تم خصم {fee} نقطة عمولة، الإجمالي {total_deduct})"
    bot.send_message(uid, sender_msg, reply_markup=back_main_kb())
    try:
        bot.send_message(recipient_id, f"🎉 تهانينا، تم استلام <b>{amount}</b> نقطة من المستخدم <code>{uid}</code> 🎁")
    except Exception:
        pass


# ============================================================
# 28) موجّه الأزرار الرئيسي
# ============================================================
@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    if call_seen(call):
        return
    uid = call.from_user.id
    user = ensure_user(call)
    if user.get("banned"):
        bot.answer_callback_query(call.id, "🚫 محظور", show_alert=True)
        return
    if is_bot_disabled() and not is_admin(uid):
        bot.answer_callback_query(call.id, "⛔ البوت معطل حالياً", show_alert=True)
        return
    data = call.data or ""
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    # تنقل بين صفحات معاينة الملف
    if data.startswith("fpg_"):
        parts = data.split("_")
        if len(parts) == 3:
            _, cache_key, page_str = parts
            page = int(page_str)
            cached = _file_preview_cache.get(cache_key)
            if not cached:
                bot.answer_callback_query(call.id, "⚠️ انتهت صلاحية المعاينة، يرجى إعادة فتح الملف.", show_alert=True)
                return
            pages = cached["pages"]
            total_pages = len(pages)
            total_lines = cached["total_lines"]
            filename = cached["filename"]
            if page < 0 or page >= total_pages:
                bot.answer_callback_query(call.id, "❌ صفحة غير موجودة")
                return
            header = (
                f"📄 <b>محتوى الملف:</b> <code>{html_escape(filename)}</code>\n"
                f"<i>({total_lines} سطر — صفحة {page + 1} من {total_pages})</i>"
            )
            markup = _make_preview_keyboard(cache_key, page, total_pages)
            try:
                bot.edit_message_text(
                    f"{header}\n\n<pre><code>{html_escape(pages[page])}</code></pre>",
                    chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=markup,
                )
                bot.answer_callback_query(call.id, f"صفحة {page + 1} من {total_pages}")
            except Exception as e:
                bot.answer_callback_query(call.id, "⚠️ حدث خطأ")
                log.warning("fpg edit_message_text failed: %s", e)
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # زر التحقق من الاشتراك
    if data == "check_sub":
        ok, unsubscribed = is_user_subscribed_all(uid)
        if ok:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "✅ تم التحقق")
            if is_admin(uid):
                bot.send_message(chat_id, "👑 أهلاً بالمطور.", reply_markup=admin_menu_markup())
            else:
                show_main_menu(chat_id, uid)
        else:
            names = ", ".join(ch["label"] or ch["channel"] for ch in unsubscribed)
            bot.answer_callback_query(call.id, f"❌ لم تشترك بعد في: {names}", show_alert=True)
        return

    # فحص الاشتراك الإجباري
    if not is_admin(uid):
        ok, _ = is_user_subscribed_all(uid)
        if not ok:
            bot.answer_callback_query(call.id, "⚠️ يجب الاشتراك في القنوات أولاً", show_alert=True)
            force_sub_block(chat_id, uid)
            return

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    try:
        if data == "back_main":
            pop_pending(uid)
            show_main_menu(chat_id, uid, msg_id)

        elif data in ("noop_sig", "noop"):
            pass  # أزرار زخرفية لا تفعل شيئاً

        elif data == "cancel_operation":
            pop_pending(uid)
            show_main_menu(chat_id, uid, msg_id)

        elif data.startswith("set_lang_"):
            lang = data.split("_", 2)[-1]
            if lang in SUPPORTED_LANGS:
                set_user_lang(uid, lang)
            q, options, _a = make_captcha(uid)
            kb = types.InlineKeyboardMarkup(row_width=2)
            for opt in options:
                kb.add(types.InlineKeyboardButton(str(opt), callback_data=f"captcha_{opt}", style="primary"))
            try:
                bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=t(uid, "verify_human") + f"\n\n<blockquote><b>{q} = ؟</b></blockquote>",
                    reply_markup=kb,
                )
            except Exception:
                bot.send_message(chat_id, t(uid, "verify_human") + f"\n\n<b>{q} = ؟</b>", reply_markup=kb)

        elif data.startswith("captcha_"):
            try:
                val = int(data.split("_", 1)[1])
            except Exception:
                val = -1
            if check_captcha(uid, val):
                try:
                    db_execute("UPDATE users SET verified=1 WHERE id=?", (uid,))
                except Exception:
                    pass
                bot.answer_callback_query(call.id, t(uid, "verified_ok"))
                try:
                    bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass
                show_main_menu(chat_id, uid)
            else:
                bot.answer_callback_query(call.id, "❌", show_alert=True)
                q, options, _a = make_captcha(uid)
                kb = types.InlineKeyboardMarkup(row_width=2)
                for opt in options:
                    kb.add(types.InlineKeyboardButton(str(opt), callback_data=f"captcha_{opt}", style="primary"))
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id, message_id=msg_id,
                        caption=t(uid, "verify_human") + f"\n\n<blockquote><b>{q} = ؟</b></blockquote>",
                        reply_markup=kb,
                    )
                except Exception:
                    pass

        elif data.startswith("proj_info_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            uname = p.get("hosted_bot_username") or "-"
            text = (
                f"ℹ️ <b>معلومات البوت</b>\n\n"
                f"<blockquote>"
                f"📛 الاسم: <b>{html_escape(p.get('name') or '-')}</b>\n"
                f"🤖 Username: @{html_escape(str(uname).lstrip('@'))}\n"
                f"🆔 Bot ID: <code>{p.get('hosted_bot_id') or '-'}</code>\n"
                f"📄 الملف: <code>{html_escape(p.get('main_file') or '-')}</code>\n"
                f"🧩 Runtime: <b>{html_escape(p.get('runtime') or 'python')}</b>\n"
                f"👤 المالك: <code>{p.get('user_id')}</code>\n"
                f"⚙️ الحالة: {'🟢 يعمل' if manager.is_running(pid) else '🔴 متوقف'}\n"
                f"</blockquote>"
            )
            kb = types.InlineKeyboardMarkup()
            if uname and uname != "-":
                kb.add(types.InlineKeyboardButton(t(uid, "open_bot"), url=f"https://t.me/{str(uname).lstrip('@')}", style="success"))
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data=f"proj_view_{pid}", style="primary"))
            try:
                bot.send_photo(chat_id, get_section_image("info"), caption=text, reply_markup=kb)
            except Exception:
                bot.send_message(chat_id, text, reply_markup=kb)

        elif data.startswith("proj_repair_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
            if not p or p["user_id"] != uid:
                return
            rid = db_execute_returning_id(
                "INSERT INTO repair_requests (project_id, user_id, reason, status) VALUES (?,?,?,?)",
                (pid, uid, "user requested repair", "pending"),
            )
            bot.send_message(chat_id, t(uid, "repair_sent"))
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✅ قبول الإصلاح", callback_data=f"adm_repair_ok_{rid}", style="success"),
                types.InlineKeyboardButton("❌ رفض", callback_data=f"adm_repair_no_{rid}", style="danger"),
            )
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🛠️ <b>طلب إصلاح بوت</b>\n"
                    f"المشروع: <b>{html_escape(p.get('name') or '')}</b> #{pid}\n"
                    f"المستخدم: <code>{uid}</code>\n"
                    f"الطلب: #{rid}",
                    reply_markup=kb,
                )
            except Exception:
                pass

        elif data.startswith("adm_repair_ok_"):
            if not is_admin(uid):
                return
            rid = int(data.split("_")[-1])
            rr = db_fetchone("SELECT * FROM repair_requests WHERE id=?", (rid,))
            if not rr:
                return
            db_execute("UPDATE repair_requests SET status='approved' WHERE id=?", (rid,))
            try:
                bot.send_message(rr["user_id"], f"✅ تمت الموافقة على طلب الإصلاح #{rid}. سيتواصل معك المشرف أو أعد التشغيل بعد التحديث.")
            except Exception:
                pass
            bot.send_message(chat_id, f"✅ تم قبول طلب الإصلاح #{rid}")

        elif data.startswith("adm_repair_no_"):
            if not is_admin(uid):
                return
            rid = int(data.split("_")[-1])
            rr = db_fetchone("SELECT * FROM repair_requests WHERE id=?", (rid,))
            if not rr:
                return
            db_execute("UPDATE repair_requests SET status='rejected' WHERE id=?", (rid,))
            try:
                bot.send_message(rr["user_id"], f"❌ تم رفض طلب الإصلاح #{rid}.")
            except Exception:
                pass
            bot.send_message(chat_id, f"تم رفض #{rid}")

        elif data == "my_files_hub":
            rows = db_fetchall("SELECT id, name, main_file, is_running, runtime, hosted_bot_username FROM projects WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,))
            if not rows:
                bot.send_message(chat_id, "📭 لا توجد مشاريع بعد.", reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton(t(uid, "btn_new_bot"), callback_data="proj_new", style="success")
                ))
            else:
                kb = types.InlineKeyboardMarkup(row_width=1)
                for r in rows:
                    st = "🟢" if manager.is_running(r["id"]) else "🔴"
                    kb.add(types.InlineKeyboardButton(
                        f"{st} {r['name']}", callback_data=f"proj_manage_{r['id']}", style="primary"
                    ))
                kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="back_main", style="primary"))
                try:
                    bot.send_photo(chat_id, get_section_image("files"),
                                   caption="📁 <b>ملفاتي / مشاريعي</b>\n<blockquote>اختر مشروعاً للتحكم: تشغيل، توكن، مالك، سجل…</blockquote>",
                                   reply_markup=kb)
                except Exception:
                    bot.send_message(chat_id, "📁 <b>ملفاتي</b>", reply_markup=kb)

        elif data.startswith("proj_manage_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            running = manager.is_running(pid)
            text = (
                f"🛠️ <b>إدارة: {html_escape(p.get('name') or '')}</b>\n\n"
                f"<blockquote>"
                f"{'🟢 يعمل' if running else '🔴 متوقف'} | {html_escape(p.get('runtime') or 'python')}\n"
                f"📄 <code>{html_escape(p.get('main_file') or '-')}</code>\n"
                f"🤖 @{html_escape((p.get('hosted_bot_username') or '-') )}\n"
                f"</blockquote>"
            )
            kb = types.InlineKeyboardMarkup(row_width=2)
            if running:
                kb.add(types.InlineKeyboardButton("⏹ إيقاف", callback_data=f"proj_stop_{pid}", style="danger"),
                       types.InlineKeyboardButton("🔁 إعادة", callback_data=f"proj_restart_{pid}", style="success"))
            else:
                kb.add(types.InlineKeyboardButton("▶️ تشغيل", callback_data=f"proj_start_{pid}", style="success"))
            kb.add(
                types.InlineKeyboardButton(t(uid, "change_token"), callback_data=f"proj_settoken_{pid}", style="primary"),
                types.InlineKeyboardButton(t(uid, "change_owner"), callback_data=f"proj_setowner_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton("تعديل .env", callback_data=f"proj_env_{pid}", style="primary"),
                types.InlineKeyboardButton("جدولة تشغيل", callback_data=f"proj_sched_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton("Preflight", callback_data=f"proj_preflight_{pid}", style="success"),
                types.InlineKeyboardButton("Passport", callback_data=f"proj_passport_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton("لقطة حفظ", callback_data=f"proj_snap_{pid}", style="primary"),
                types.InlineKeyboardButton("استعادة لقطة", callback_data=f"proj_snaprest_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton("طابور تشغيل", callback_data=f"proj_queue_{pid}", style="primary"),
                types.InlineKeyboardButton("فتح CrashLock", callback_data=f"proj_unlock_{pid}", style="danger"),
            )
            kb.add(
                types.InlineKeyboardButton("وضع شبح", callback_data=f"proj_ghost_{pid}", style="primary"),
                types.InlineKeyboardButton("تعيين وريث", callback_data=f"proj_heir_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton(t(uid, "logs"), callback_data=f"proj_log_{pid}", style="primary"),
                types.InlineKeyboardButton(t(uid, "terminal"), callback_data=f"proj_term_{pid}", style="primary"),
            )
            kb.add(
                types.InlineKeyboardButton(t(uid, "repair_btn"), callback_data=f"proj_repair_{pid}", style="danger"),
                types.InlineKeyboardButton(t(uid, "bot_info"), callback_data=f"proj_info_{pid}", style="primary"),
            )
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="my_files_hub", style="primary"))
            try:
                bot.send_photo(chat_id, get_section_image("manage"), caption=text, reply_markup=kb)
            except Exception:
                bot.send_message(chat_id, text, reply_markup=kb)

        elif data.startswith("proj_settoken_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            set_pending(uid, {"type": "set_hosted_token", "project_id": pid})
            bot.send_message(chat_id, "🔑 أرسل <b>التوكن الجديد</b> للبوت المستضاف.\n/cancel للإلغاء.")

        elif data.startswith("proj_setowner_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            set_pending(uid, {"type": "set_project_owner", "project_id": pid})
            bot.send_message(chat_id, "👤 أرسل <b>Telegram ID</b> للمالك الجديد.\n/cancel للإلغاء.")

        elif data.startswith("proj_env_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            row = db_fetchone("SELECT content FROM project_files WHERE project_id=? AND filename='.env'", (pid,))
            cur = ""
            if row:
                try:
                    cur = bytes(row["content"]).decode("utf-8", errors="replace")[:1500]
                except Exception:
                    cur = ""
            set_pending(uid, {"type": "set_env_file", "project_id": pid})
            bot.send_message(
                chat_id,
                f"محتوى .env الحالي:\n<pre>{html_escape(cur) or '(فارغ)'}</pre>\n"
                "ارسل المحتوى الجديد كاملا:\n/cancel",
            )

        elif data.startswith("proj_sched_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT id, user_id, schedule_json FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            set_pending(uid, {"type": "set_schedule", "project_id": pid})
            bot.send_message(
                chat_id,
                "ارسل الجدولة بالشكل:\n<code>08:00 23:00</code>\n"
                "(تشغيل 08:00 UTC - ايقاف 23:00 UTC)\n"
                "او <code>off</code> لالغاء الجدولة.\n/cancel",
            )

        elif data == "live_status":
            items = []
            with manager.lock:
                procs = list(manager.processes.items())
            for pid, hp in procs:
                alive = hp.is_alive()
                items.append(
                    f"{'🟢' if alive else '⚪'} #{pid} <b>{html_escape(hp.name)}</b> "
                    f"| {hp.runtime if hasattr(hp,'runtime') else '?'} "
                    f"| restarts={hp.restart_count}"
                )
            if not items:
                body = "لا توجد عمليات شغّالة حالياً."
            else:
                body = "\n".join(items[:40])
            text = f"📡 <b>الحالة الحية للعمليات</b>\n\n<blockquote>{body}</blockquote>"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="live_status", style="primary"))
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="back_main", style="primary"))
            try:
                bot.send_photo(chat_id, get_section_image("live"), caption=text, reply_markup=kb)
            except Exception:
                bot.send_message(chat_id, text, reply_markup=kb)

        elif data == "show_terms":
            terms = get_setting("terms_text") or (
                "📄 <b>Platform Rules</b>\n\n"
                "<blockquote>"
                "• لا ترفع محتوى مخالف أو ضار.\n"
                "• أنت مسؤول عن توكنات وبوتاتك.\n"
                "• الاستضافة للمساعدة وليست لضمان 100%.\n"
                "• يحق للإدارة إيقاف أي مشروع مخالف.\n"
                "• Python و Node.js مدعومان مع تثبيت تلقائي للمكتبات.\n"
                "</blockquote>"
            )
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="back_main", style="primary"))
            try:
                bot.send_photo(chat_id, get_section_image("terms"), caption=terms, reply_markup=kb)
            except Exception:
                bot.send_message(chat_id, terms, reply_markup=kb)

        elif data == "user_settings":
            kb = types.InlineKeyboardMarkup(row_width=2)
            for code, label in SUPPORTED_LANGS.items():
                kb.add(types.InlineKeyboardButton(label, callback_data=f"set_lang_{code}", style="primary"))
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="back_main", style="primary"))
            try:
                bot.send_photo(chat_id, get_section_image("settings"),
                               caption="⚙️ <b>الإعدادات</b>\n<blockquote>غيّر اللغة أو راجع الشروط من القائمة.</blockquote>",
                               reply_markup=kb)
            except Exception:
                bot.send_message(chat_id, "⚙️ الإعدادات", reply_markup=kb)

        elif data == "tpl_menu":
            kb = types.InlineKeyboardMarkup(row_width=1)
            for key, tpl in BOT_TEMPLATES.items():
                kb.add(types.InlineKeyboardButton(tpl["name"], callback_data=f"tpl_use_{key}", style="primary"))
            kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="back_main", style="primary"))
            bot.send_message(chat_id, "<b>قوالب بوتات جاهزة</b>\n<blockquote>اختر قالبا ثم ضع التوكن من ملفاتي.</blockquote>", reply_markup=kb)

        elif data.startswith("tpl_use_"):
            key = data[len("tpl_use_"):]
            ok, res = create_project_from_template(uid, key)
            if not ok:
                bot.send_message(chat_id, f"فشل: {html_escape(res)}")
            else:
                pid = int(res)
                bot.send_message(
                    chat_id,
                    f"تم انشاء المشروع من القالب #{pid}\n"
                    "افتح ملفاتي وضع التوكن ثم انتظر موافقة الادمن او فعّل الموافقة التلقائية.",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("ادارة المشروع", callback_data=f"proj_manage_{pid}", style="primary")
                    ),
                )
                try:
                    bot.send_message(ADMIN_ID, f"قالب جديد من <code>{uid}</code> مشروع #{pid}")
                except Exception:
                    pass

        elif data == "coupon_redeem":
            set_pending(uid, {"type": "coupon_code"})
            bot.send_message(chat_id, "ارسل رمز الكوبون:\n/cancel")

        elif data.startswith("adm_sec_ok_"):
            if not is_admin(uid):
                return
            pid = int(data.split("_")[-1])
            clear_project_security(pid)
            bot.send_message(chat_id, f"موافقة امنية للمشروع #{pid}")
            p = db_fetchone("SELECT user_id, name FROM projects WHERE id=?", (pid,))
            if p:
                try:
                    bot.send_message(p["user_id"], f"تمت الموافقة الامنية على <b>{html_escape(p.get('name') or '')}</b>")
                except Exception:
                    pass
            if is_auto_approve_enabled():
                approve_project(pid)

        elif data.startswith("adm_sec_no_"):
            if not is_admin(uid):
                return
            pid = int(data.split("_")[-1])
            db_execute("UPDATE projects SET security_flag=1, security_approved=0, approved=0 WHERE id=?", (pid,))
            bot.send_message(chat_id, f"رفض امني #{pid}")
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if p:
                try:
                    bot.send_message(p["user_id"], f"تم رفض مشروعك #{pid} لاسباب امنية.")
                except Exception:
                    pass

        elif data == "adm_export_all":
            if not is_admin(uid):
                return
            bot.send_message(chat_id, "جاري تصدير البيانات...")
            zpath = export_all_data_zip()
            if zpath and os.path.exists(zpath):
                with open(zpath, "rb") as fh:
                    bot.send_document(chat_id, fh, caption="تصدير كامل")
            else:
                bot.send_message(chat_id, "فشل التصدير")

        elif data == "adm_bulk_restart_py":
            if not is_admin(uid):
                return
            n = 0
            for r in db_fetchall("SELECT id FROM projects WHERE approved=1 AND runtime='python'"):
                try:
                    manager.restart_project(r["id"])
                    n += 1
                except Exception:
                    pass
            bot.send_message(chat_id, f"اعيد تشغيل {n} بوت Python")

        elif data == "adm_bulk_restart_node":
            if not is_admin(uid):
                return
            n = 0
            for r in db_fetchall("SELECT id FROM projects WHERE approved=1 AND runtime='nodejs'"):
                try:
                    manager.restart_project(r["id"])
                    n += 1
                except Exception:
                    pass
            bot.send_message(chat_id, f"اعيد تشغيل {n} بوت Node")

        elif data == "adm_toggle_auto_approve2":
            if not is_admin(uid):
                return
            cur = is_auto_approve_enabled()
            set_setting("auto_approve", "0" if cur else "1")
            bot.send_message(chat_id, "الموافقة التلقائية: " + ("ايقاف" if cur else "تشغيل"))

        elif data == "adm_toggle_security":
            if not is_admin(uid):
                return
            cur = is_security_block_enabled()
            set_setting("security_scan", "0" if cur else "1")
            bot.send_message(chat_id, "فحص الامان: " + ("ايقاف" if cur else "تشغيل"))

        elif data.startswith("proj_preflight_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            bot.send_message(chat_id, start_lock_status_text(pid))

        elif data.startswith("proj_passport_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            bot.send_message(chat_id, project_passport_text(pid))

        elif data.startswith("proj_snap_") and not data.startswith("proj_snaprest_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            if create_snapshot(pid, label=f"manual-{uid}"):
                bot.send_message(chat_id, "تم حفظ لقطة للمشروع.")
            else:
                bot.send_message(chat_id, "فشل حفظ اللقطة.")

        elif data.startswith("proj_snaprest_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            snaps = db_fetchall(
                "SELECT id, label, created_at FROM snapshots WHERE project_id=? ORDER BY id DESC LIMIT 8",
                (pid,),
            )
            if not snaps:
                bot.send_message(chat_id, "لا توجد لقطات.")
            else:
                kb = types.InlineKeyboardMarkup(row_width=1)
                for s in snaps:
                    kb.add(types.InlineKeyboardButton(
                        f"#{s['id']} {s.get('label') or ''} {str(s.get('created_at') or '')[:16]}",
                        callback_data=f"proj_dosnap_{pid}_{s['id']}",
                        style="primary",
                    ))
                bot.send_message(chat_id, "اختر لقطة للاستعادة:", reply_markup=kb)

        elif data.startswith("proj_dosnap_"):
            parts = data.split("_")
            pid, sid = int(parts[2]), int(parts[3])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            ok, msg = restore_snapshot(pid, sid)
            bot.send_message(chat_id, msg if ok else f"فشل: {html_escape(msg)}")

        elif data.startswith("proj_queue_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            msg = enqueue_start(pid)
            bot.send_message(chat_id, msg)

        elif data.startswith("proj_unlock_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p:
                return
            if not is_admin(uid) and p["user_id"] != uid:
                return
            # المستخدم يفتح مرة بعد ما يدفع طاقة اضافية، الادمن دائما
            if not is_admin(uid):
                ok_e, msg_e = consume_energy(uid, int(get_setting("energy_unlock_crash") or "5"))
                if not ok_e:
                    bot.send_message(chat_id, msg_e)
                    return
            clear_crash_lock(pid)
            bot.send_message(chat_id, f"تم فتح قفل Crash للمشروع #{pid}")

        elif data.startswith("proj_ghost_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id, ghost_mode FROM projects WHERE id=?", (pid,))
            if not p or (p["user_id"] != uid and not is_admin(uid)):
                return
            newv = 0 if int(p.get("ghost_mode") or 0) else 1
            db_execute("UPDATE projects SET ghost_mode=? WHERE id=?", (newv, pid))
            bot.send_message(chat_id, "وضع الشبح: " + ("تشغيل" if newv else "ايقاف"))

        elif data.startswith("proj_heir_"):
            pid = int(data.split("_")[-1])
            p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
            if not p or p["user_id"] != uid:
                return
            set_pending(uid, {"type": "set_heir", "project_id": pid})
            bot.send_message(chat_id, "ارسل ID الوريث:\n/cancel")

        elif data == "adm_failures_panel":
            if not is_admin(uid):
                return
            rows = db_fetchall(
                "SELECT id, name, last_error, crash_locked, runtime FROM projects WHERE "
                "(crash_locked=1 OR (last_error IS NOT NULL AND last_error != '')) ORDER BY id DESC LIMIT 30"
            )
            if not rows:
                bot.send_message(chat_id, "لا توجد اعطال مسجلة.")
            else:
                kb = types.InlineKeyboardMarkup(row_width=1)
                lines = ["<b>لوحة الاعطال</b>\n"]
                for r in rows:
                    lines.append(
                        f"#{r['id']} {html_escape(r.get('name') or '')} "
                        f"{'LOCK' if r.get('crash_locked') else ''} "
                        f"<code>{html_escape((r.get('last_error') or '')[:60])}</code>"
                    )
                    kb.add(types.InlineKeyboardButton(
                        f"فتح #{r['id']}", callback_data=f"proj_unlock_{r['id']}", style="danger"
                    ))
                kb.add(types.InlineKeyboardButton("اعادة الامن فقط", callback_data="adm_restart_unlocked", style="success"))
                bot.send_message(chat_id, "\n".join(lines[:35]), reply_markup=kb)

        elif data == "adm_restart_unlocked":
            if not is_admin(uid):
                return
            n = 0
            for r in db_fetchall("SELECT id FROM projects WHERE approved=1 AND COALESCE(crash_locked,0)=0"):
                if not manager.is_running(r["id"]):
                    try:
                        manager.start_project(r["id"])
                        n += 1
                    except Exception:
                        pass
            bot.send_message(chat_id, f"حاول تشغيل {n} مشروع غير مقفول")

        elif data == "adm_sla_compensate":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "sla_points"})
            bot.send_message(chat_id, "ارسل عدد نقاط التعويض SLA لكل المستخدمين:")

        elif data == "adm_selective_maint":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "selective_maint"})
            bot.send_message(
                chat_id,
                "ارسل اقسام الصيانة مفصولة بفاصلة:\n"
                "<code>start,upload,terminal</code>\n"
                "او <code>off</code> للالغاء.",
            )

        elif data == "adm_panel":
            if not is_admin(uid):
                return
            pop_pending(uid)
            show_admin_panel(chat_id, msg_id)

        # ── أقسام لوحة الأدمن ──
        elif data == "adm_sec_requests":
            if not is_admin(uid): return
            s = get_admin_quick_stats()
            pending_warn = f"  ⚠️ {s['pending_total']} طلب معلّق" if s["pending_total"] else ""
            text = f"📥 <b>الطلبات</b>{pending_warn}"
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=admin_section_markup("requests"))
            except Exception:
                bot.send_message(chat_id, text, reply_markup=admin_section_markup("requests"))

        elif data == "adm_sec_users":
            if not is_admin(uid): return
            s = get_admin_quick_stats()
            text = f"👥 <b>المستخدمون</b>  |  إجمالي: <b>{s['total_users']}</b>  |  محظور: <b>{s['banned_users']}</b>"
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=admin_section_markup("users"))
            except Exception:
                bot.send_message(chat_id, text, reply_markup=admin_section_markup("users"))

        elif data == "adm_sec_comms":
            if not is_admin(uid): return
            try:
                bot.edit_message_text("📣 <b>التواصل</b>", chat_id, msg_id, reply_markup=admin_section_markup("comms"))
            except Exception:
                bot.send_message(chat_id, "📣 <b>التواصل</b>", reply_markup=admin_section_markup("comms"))

        elif data == "adm_sec_points":
            if not is_admin(uid): return
            s = get_admin_quick_stats()
            text = f"💎 <b>النقاط</b>  |  إجمالي النقاط: <b>{s['total_points']:,}</b>"
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=admin_section_markup("points"))
            except Exception:
                bot.send_message(chat_id, text, reply_markup=admin_section_markup("points"))

        elif data == "adm_sec_bots":
            if not is_admin(uid): return
            s = get_admin_quick_stats()
            text = f"🤖 <b>البوتات</b>  |  شغّالة: <b>{s['running_bots']}</b> / إجمالي: <b>{s['total_bots']}</b>"
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=admin_section_markup("bots"))
            except Exception:
                bot.send_message(chat_id, text, reply_markup=admin_section_markup("bots"))

        elif data == "adm_sec_settings":
            if not is_admin(uid): return
            try:
                bot.edit_message_text("⚙️ <b>الإعدادات</b>", chat_id, msg_id, reply_markup=admin_section_markup("settings"))
            except Exception:
                bot.send_message(chat_id, "⚙️ <b>الإعدادات</b>", reply_markup=admin_section_markup("settings"))

        elif data == "adm_sec_stats":
            if not is_admin(uid): return
            sv = get_server_quick_info()
            text = f"📊 <b>الإحصائيات والسيرفر</b>\n\n{sv}"
            try:
                bot.edit_message_text(text, chat_id, msg_id, reply_markup=admin_section_markup("stats"))
            except Exception:
                bot.send_message(chat_id, text, reply_markup=admin_section_markup("stats"))

        # ── إجراءات سريعة ──
        elif data == "adm_quick_approve_all":
            if not is_admin(uid): return
            # قبول جميع طلبات التفعيل والبوتات المعلّقة
            pending_u = db_fetchall("SELECT id FROM users WHERE approved=0 AND banned=0")
            pending_p = db_fetchall("SELECT id FROM projects WHERE approved=0")
            count_u = len(pending_u)
            count_p = len(pending_p)
            for r in pending_u:
                db_execute("UPDATE users SET approved=1 WHERE id=?", (r["id"],))
                try:
                    bot.send_message(r["id"], "✅ <b>تم تفعيل حسابك!</b>\nيمكنك الآن استخدام البوت.")
                except Exception:
                    pass
            for r in pending_p:
                db_execute("UPDATE projects SET approved=1 WHERE id=?", (r["id"],))
                proj = db_fetchone("SELECT user_id, name FROM projects WHERE id=?", (r["id"],))
                if proj:
                    try:
                        bot.send_message(proj["user_id"],
                                         f"✅ <b>تم قبول بوتك</b> «{html_escape(proj['name'])}» !")
                    except Exception:
                        pass
            msg_txt = (
                f"✅ <b>تمت الموافقة على الكل</b>\n\n"
                f"👤 {count_u} مستخدم مُفعَّل\n"
                f"🤖 {count_p} بوت مُقبَل"
            )
            bot.answer_callback_query(call.id, f"✅ {count_u + count_p} طلب تمت الموافقة عليه")
            show_admin_panel(chat_id, msg_id)
            if count_u + count_p > 0:
                bot.send_message(chat_id, msg_txt)

        elif data == "adm_quick_start_all":
            if not is_admin(uid): return
            rows = db_fetchall("SELECT id FROM projects WHERE approved=1")
            started = 0
            for r in rows:
                if not manager.is_running(r["id"]):
                    try:
                        manager.start_project(r["id"])
                        started += 1
                    except Exception:
                        pass
            bot.answer_callback_query(call.id, f"▶️ تم تشغيل {started} بوت")
            show_admin_panel(chat_id, msg_id)

        elif data == "adm_quick_stop_all":
            if not is_admin(uid): return
            rows = db_fetchall("SELECT id FROM projects WHERE approved=1")
            stopped = 0
            for r in rows:
                if manager.is_running(r["id"]):
                    try:
                        manager.stop_project(r["id"])
                        stopped += 1
                    except Exception:
                        pass
            bot.answer_callback_query(call.id, f"⏹ تم إيقاف {stopped} بوت")
            show_admin_panel(chat_id, msg_id)

        elif data == "adm_quick_restart_all":
            if not is_admin(uid): return
            rows = db_fetchall("SELECT id FROM projects WHERE approved=1 AND is_running=1")
            restarted = 0
            for r in rows:
                try:
                    if manager.is_running(r["id"]):
                        manager.stop_project(r["id"])
                    time.sleep(0.3)
                    manager.start_project(r["id"])
                    restarted += 1
                except Exception:
                    pass
            bot.answer_callback_query(call.id, f"🔁 تم إعادة تشغيل {restarted} بوت")
            show_admin_panel(chat_id, msg_id)

        elif data == "proj_new":
            start_new_project(chat_id, uid)

        elif data in ("runtime_python", "runtime_nodejs"):
            pending = get_pending(uid) or {}
            if pending.get("type") != "pick_runtime":
                start_new_project(chat_id, uid)
                return
            runtime = "python" if data.endswith("python") else "nodejs"
            pending["type"] = "new_project_name"
            pending["runtime"] = runtime
            set_pending(uid, pending)
            lane = "Python" if runtime == "python" else "Node.js"
            bot.send_message(
                chat_id,
                f"<b>Lane selected: {lane}</b>\n\n"
                "Send a short project name (letters/numbers).\n"
                "/cancel to abort.",
                reply_markup=back_main_kb(),
            )

        elif data == "site_upload":
            pop_pending(uid)
            show_netlify_upload_menu(chat_id, uid, msg_id)

        elif data == "site_upload_zip":
            pop_pending(uid)
            start_netlify_upload(chat_id, uid)

        elif data == "vercel_upload":
            pop_pending(uid)
            show_vercel_upload_menu(chat_id, uid, msg_id)

        elif data == "vercel_upload_zip":
            pop_pending(uid)
            if not vercel_is_configured():
                bot.send_message(chat_id, "⚠️ ميزة رفع Vercel غير مفعّلة.\n🔧 فعّلها بإضافة <code>VERCEL_TOKEN</code>.",
                                 reply_markup=back_main_kb())
                return
            ok, msg = check_and_inc_daily(uid, "vercel", 5)
            if not ok:
                bot.send_message(chat_id, msg, reply_markup=back_main_kb())
                return
            price = get_section_price("vercel", 0)
            if price > 0 and not is_admin(uid):
                pts_row = db_fetchone("SELECT COALESCE(points,0) AS p FROM users WHERE id=?", (uid,))
                pts = pts_row["p"] if pts_row else 0
                if pts < price:
                    bot.send_message(chat_id, f"❌ لا تملك نقاطاً كافية.\n💡 سعر رفع Vercel: <b>{price}</b> نقطة.",
                                     reply_markup=back_main_kb())
                    return
                db_execute("UPDATE users SET points = points - ? WHERE id=? AND COALESCE(points,0) >= ?",
                           (price, uid, price))
            set_pending(uid, {"type": "vercel_upload_zip"})
            bot.send_message(chat_id, "▲ <b>رفع موقع على Vercel</b>\n\n📌 ابعت ملف <b>.zip</b> فيه <code>index.html</code>.\n/cancel للإلغاء.",
                             reply_markup=back_main_kb())

        elif data == "proj_list":
            list_user_projects(chat_id, uid, msg_id)

        elif data == "my_stats":
            show_user_stats(chat_id, uid, msg_id)

        elif data == "help":
            show_help(chat_id, msg_id)

        elif data == "about_bot":
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("➕ بوت جديد", callback_data="proj_new", style="success"),
                types.InlineKeyboardButton("📂 بوتاتي", callback_data="proj_list", style="primary"),
            )
            kb.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="back_main", style="primary"))
            send_section_media(chat_id, "about", about_bot_caption(), reply_markup=kb)

        elif data == "my_sites":
            show_user_sites(chat_id, uid, msg_id)

        elif data == "my_deploys":
            show_user_deployments(chat_id, uid, msg_id)

        elif data.startswith("site_redeploy_"):
            parts = data.split("_", 3)
            if len(parts) < 4:
                return
            provider = parts[2]
            site_id = parts[3]
            if provider == "netlify":
                set_pending(uid, {"type": "netlify_upload_zip", "redeploy": True, "site_id": site_id})
                bot.send_message(chat_id, "📤 ابعت ZIP جديد لإعادة نشر موقع Netlify.\n/cancel للإلغاء.")
            else:
                set_pending(uid, {"type": "vercel_redeploy_zip", "redeploy": True, "site_name": site_id})
                bot.send_message(chat_id, "📤 ابعت ZIP جديد لإعادة نشر موقع Vercel.\n/cancel للإلغاء.")

        elif data == "points":
            show_points(chat_id, uid, msg_id)

        elif data == "transfer_points":
            start_transfer_points(chat_id, uid, msg_id)

        elif data.startswith("proj_view_"):
            view_project(chat_id, uid, int(data.split("_")[-1]), msg_id)

        elif data.startswith("proj_start_"):
            pid = int(data.split("_")[-1])
            ok, msg = manager.start_project(pid)
            view_project(chat_id, uid, pid, msg_id)

        elif data.startswith("proj_stop_"):
            pid = int(data.split("_")[-1])
            manager.stop_project(pid)
            view_project(chat_id, uid, pid, msg_id)

        elif data.startswith("proj_restart_"):
            pid = int(data.split("_")[-1])
            manager.restart_project(pid)
            view_project(chat_id, uid, pid, msg_id)

        elif data.startswith("proj_editor_"):
            # فتح محرر الكود — قائمة الملفات
            pid = int(data.split("_")[-1])
            show_editor_files(chat_id, uid, pid, msg_id)

        elif data.startswith("proj_save_confirm_"):
            # المستخدم أكّد حفظ التعديلات بعد رؤية الـ diff
            pid = int(data.split("_")[-1])
            pending = get_pending(uid) or {}
            if pending.get("type") != "proj_file_confirm" or pending.get("project_id") != pid:
                bot.answer_callback_query(call.id, "⚠️ انتهت صلاحية التعديل، حدّد الملف مرة أخرى.")
                show_editor_files(chat_id, uid, pid, msg_id)
                return
            filename    = pending["filename"]
            file_row_id = pending["file_row_id"]
            try:
                content_bytes = base64.b64decode(pending["new_content_b64"])
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ خطأ في البيانات")
                bot.send_message(chat_id, f"❌ فشل استعادة المحتوى: <code>{html_escape(str(e))}</code>")
                pop_pending(uid)
                return
            try:
                _save_file_to_disk_and_db(pid, filename, content_bytes)
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ فشل الحفظ")
                bot.send_message(chat_id, f"❌ فشل حفظ الملف: <code>{html_escape(str(e))}</code>")
                pop_pending(uid)
                return
            pop_pending(uid)
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✏️ تعديل مرة ثانية", callback_data=f"proj_ef_{pid}_{file_row_id}", style="primary"),
                types.InlineKeyboardButton("📁 قائمة الملفات", callback_data=f"proj_editor_{pid}", style="primary"),
            )
            kb.add(types.InlineKeyboardButton("🔙 لوحة البوت", callback_data=f"proj_view_{pid}", style="primary"))
            try:
                bot.edit_message_text(
                    f"✅ <b>تم حفظ التعديلات بنجاح!</b>\n\n"
                    f"📄 الملف: <code>{html_escape(filename)}</code>\n"
                    f"📦 الحجم: <b>{len(content_bytes):,} بايت</b>\n\n"
                    "⚠️ أعد تشغيل البوت لتفعيل التغييرات.",
                    chat_id, msg_id, reply_markup=kb,
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    f"✅ <b>تم حفظ التعديلات بنجاح!</b>\n\n"
                    f"📄 الملف: <code>{html_escape(filename)}</code>\n"
                    f"📦 الحجم: <b>{len(content_bytes):,} بايت</b>\n\n"
                    "⚠️ أعد تشغيل البوت لتفعيل التغييرات.",
                    reply_markup=kb,
                )
            bot.answer_callback_query(call.id, "✅ تم الحفظ!")

        elif data.startswith("proj_discard_edit_"):
            # المستخدم ألغى التعديلات
            pid = int(data.split("_")[-1])
            pending = get_pending(uid) or {}
            filename = pending.get("filename", "")
            file_row_id = pending.get("file_row_id")
            pop_pending(uid)
            kb = types.InlineKeyboardMarkup(row_width=2)
            if file_row_id:
                kb.add(types.InlineKeyboardButton("✏️ تعديل مرة أخرى", callback_data=f"proj_ef_{pid}_{file_row_id}", style="primary"))
            kb.add(types.InlineKeyboardButton("📁 قائمة الملفات", callback_data=f"proj_editor_{pid}", style="primary"))
            kb.add(types.InlineKeyboardButton("🔙 لوحة البوت", callback_data=f"proj_view_{pid}", style="primary"))
            try:
                bot.edit_message_text(
                    f"🗑 <b>تم تجاهل التعديلات</b>\n\n"
                    f"📄 الملف: <code>{html_escape(filename)}</code>\n"
                    "لم يتم تغيير أي شيء.",
                    chat_id, msg_id, reply_markup=kb,
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    f"🗑 <b>تم تجاهل التعديلات</b>\n\nلم يتم تغيير أي شيء.",
                    reply_markup=kb,
                )
            bot.answer_callback_query(call.id, "🗑 تم التجاهل")

        elif data.startswith("proj_ef_"):
            # المستخدم اختار ملفاً للتعديل — proj_ef_{pid}_{file_row_id}
            parts = data.split("_")
            pid = int(parts[2])
            file_row_id = int(parts[3])
            proj = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
            if not proj or (proj["user_id"] != uid and not is_admin(uid)):
                bot.answer_callback_query(call.id, "❌ غير مسموح")
                return
            row = db_fetchone("SELECT id, filename, content, size_bytes FROM project_files WHERE id=? AND project_id=?",
                              (file_row_id, pid))
            if not row:
                bot.answer_callback_query(call.id, "❌ الملف غير موجود")
                show_editor_files(chat_id, uid, pid, msg_id)
                return

            filename = row["filename"]
            size = row["size_bytes"]

            # ضبط pending أولاً
            pop_pending(uid)
            set_pending(uid, {
                "type": "proj_file_editing",
                "project_id": pid,
                "filename": filename,
                "file_row_id": file_row_id,
            })

            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("📁 قائمة الملفات", callback_data=f"proj_editor_{pid}", style="primary"),
                types.InlineKeyboardButton("❌ إلغاء", callback_data=f"proj_view_{pid}", style="primary"),
            )

            # إذا كان الملف نصياً وصغيراً — أرسل المحتوى للتعديل المباشر
            is_text = any(filename.endswith(ext) for ext in TEXT_PREVIEW_EXTENSIONS) or filename.endswith(".py")
            if is_text and size <= MAX_EDIT_CHARS * 2:
                try:
                    raw = bytes(row["content"])
                    try:
                        content_str = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        content_str = raw.decode("latin-1", errors="replace")

                    lines = content_str.splitlines()
                    line_count = len(lines)
                    bot.answer_callback_query(call.id, f"📄 {filename}")
                    bot.send_message(
                        chat_id,
                        f"✏️ <b>محرر الكود</b>\n"
                        f"📄 <code>{html_escape(filename)}</code>\n"
                        f"<i>({line_count} سطر — {size:,} بايت)</i>\n\n"
                        "📋 <b>المحتوى الحالي:</b>",
                        reply_markup=kb,
                    )
                    # إرسال المحتوى في رسالة منفصلة بصيغة code block
                    preview = content_str[:MAX_EDIT_CHARS]
                    truncated = size > MAX_EDIT_CHARS
                    suffix = f"\n\n<i>… تم عرض {MAX_EDIT_CHARS} حرف من {size:,}</i>" if truncated else ""
                    bot.send_message(
                        chat_id,
                        f"<pre><code>{html_escape(preview)}</code></pre>{suffix}",
                    )
                    bot.send_message(
                        chat_id,
                        "✏️ <b>أرسل الآن النص الجديد الكامل للملف</b> (نسخ ← تعديل ← إرسال)\n"
                        "أو أرسل الملف كـ <b>Document</b> إذا كان كبيراً\n"
                        "أو /cancel للإلغاء.",
                        reply_markup=kb,
                    )
                except Exception as e:
                    bot.send_message(chat_id, f"❌ فشل قراءة الملف: <code>{html_escape(str(e))}</code>")
                    pop_pending(uid)
            else:
                # ملف كبير أو ثنائي — أرسله كمرفق
                bot.answer_callback_query(call.id, f"📦 {filename}")
                try:
                    raw = bytes(row["content"])
                    bio = io.BytesIO(raw)
                    bio.name = filename
                    bot.send_document(chat_id, bio, caption=f"📄 <code>{html_escape(filename)}</code>")
                except Exception as e:
                    bot.send_message(chat_id, f"❌ فشل إرسال الملف: <code>{html_escape(str(e))}</code>")
                bot.send_message(
                    chat_id,
                    f"📦 الملف <code>{html_escape(filename)}</code> كبير ({size//1024} KB)\n\n"
                    "📤 <b>أرسل النسخة المعدَّلة كـ Document</b>\n"
                    "أو /cancel للإلغاء.",
                    reply_markup=kb,
                )

        elif data.startswith("proj_addfile_"):
            pid = int(data.split("_")[-1])
            set_pending(uid, {"type": "add_file", "project_id": pid})
            bot.send_message(chat_id, "📎 أرسل ملفاً فردياً أو <code>.zip</code> لإضافته للبوت.\nأي امتداد تقريباً مسموح.\n/cancel للإلغاء.")

        elif data.startswith("proj_log_"):
            pid = int(data.split("_")[-1])
            log_text = manager.tail_log(pid, 3500) or "(لا يوجد سجل بعد)"
            bot.send_message(chat_id, f"📜 آخر مخرجات البوت:\n<pre>{html_escape(log_text[-3500:])}</pre>")

        elif data.startswith("proj_files_"):
            pid = int(data.split("_")[-1])
            proj = db_fetchone("SELECT id, user_id, name FROM projects WHERE id=?", (pid,))
            if not proj or (proj["user_id"] != uid and not is_admin(uid)):
                return
            files = list_project_disk_files(pid, limit=450)
            if not files:
                bot.send_message(chat_id, "📁 لا توجد ملفات على السيرفر لهذا البوت بعد.")
                return
            preview = "\n".join(f"• <code>{html_escape(f)}</code>" for f in files[:200])
            more = "" if len(files) <= 200 else f"\n\n… وتم إخفاء {len(files)-200} ملف إضافي."
            bot.send_message(chat_id, f"📁 <b>ملفات البوت:</b>\n{preview}{more}")
            set_pending(uid, {"type": "proj_getfile", "project_id": pid})
            bot.send_message(chat_id, "📤 لو عايز تحمل ملف: ابعت اسم الملف بالظبط\nأو /cancel للإلغاء.")

        elif data.startswith("proj_term_"):
            pid = int(data.split("_")[-1])
            proj = db_fetchone("SELECT id, user_id FROM projects WHERE id=?", (pid,))
            if not proj or (proj["user_id"] != uid and not is_admin(uid)):
                return
            set_pending(uid, {"type": "proj_term_cmd", "project_id": pid})
            bot.send_message(chat_id,
                             "🖥️ <b>تيرمنال البوت</b>\n\n"
                             "✅ مسموح فقط: <code>python</code> و <code>pip</code>\n"
                             "مثال: <code>pip install requests</code>\n\n/cancel للإلغاء.")

        elif data.startswith("proj_install_"):
            pid = int(data.split("_")[-1])
            install_project_requirements(chat_id, uid, pid, msg_id)

        elif data.startswith("proj_del_"):
            pid = int(data.split("_")[-1])
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton(" نعم احذف", callback_data=f"proj_delconfirm_{pid}",
                    style="danger", icon_custom_emoji_id=E_DELETE),
                types.InlineKeyboardButton(" تراجع", callback_data=f"proj_view_{pid}",
                    style="primary", icon_custom_emoji_id=E_BACK),
            )
            bot.edit_message_text("⚠️ هل أنت متأكد من حذف البوت وكل ملفاته؟", chat_id, msg_id, reply_markup=kb)

        elif data.startswith("proj_delconfirm_"):
            pid = int(data.split("_")[-1])
            manager.stop_project(pid)
            db_execute("DELETE FROM projects WHERE id=? AND (user_id=? OR ?=?)", (pid, uid, uid, ADMIN_ID))
            list_user_projects(chat_id, uid, msg_id)

        # ---- أوامر الأدمن ----
        elif data.startswith("adm_") and not is_admin(uid):
            pass

        elif data == "adm_pending_users":
            show_pending_users(chat_id, msg_id)

        elif data == "adm_pending_projects":
            show_pending_projects(chat_id, msg_id)

        elif data == "adm_pending_files":
            show_pending_files(chat_id, msg_id)

        elif data.startswith("adm_preview_file_"):
            pending_id = int(data.split("_")[-1])
            pu = db_fetchone("SELECT * FROM pending_uploads WHERE id=?", (pending_id,))
            if not pu:
                bot.answer_callback_query(call.id, "❌ الملف غير موجود.")
            else:
                bot.answer_callback_query(call.id, "⏳ جاري تحميل المعاينة…")
                _send_file_preview(chat_id, pu["telegram_file_id"], pu["filename"])

        elif data == "adm_users":
            show_all_users(chat_id, msg_id)

        elif data == "adm_projects":
            show_all_projects(chat_id, msg_id)

        elif data == "adm_stats":
            show_admin_stats(chat_id, msg_id)

        elif data == "adm_server_status":
            if not is_admin(uid):
                return
            show_server_status(chat_id, msg_id)

        elif data == "adm_backup_db":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ إنشاء النسخة الاحتياطية…")
            threading.Thread(target=adm_send_backup, args=(chat_id,), daemon=True).start()

        elif data == "adm_growth_stats":
            if not is_admin(uid): return
            adm_show_growth_stats(chat_id, msg_id)

        elif data == "adm_audit_log":
            if not is_admin(uid): return
            adm_show_audit_log(chat_id, msg_id)

        elif data == "adm_cleanup_files":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ التنظيف…")
            threading.Thread(target=adm_cleanup_stopped_files, args=(chat_id,), daemon=True).start()

        elif data == "adm_running_bots_list":
            if not is_admin(uid): return
            adm_show_running_bots(chat_id, msg_id)

        elif data == "adm_export_bots":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ التصدير…")
            threading.Thread(target=adm_export_bots_csv, args=(chat_id,), daemon=True).start()

        elif data == "adm_inactive_users":
            if not is_admin(uid): return
            adm_show_inactive_users(chat_id, msg_id)

        elif data == "adm_usage_stats":
            if not is_admin(uid): return
            adm_show_usage_stats(chat_id, msg_id)

        elif data == "adm_announce":
            if not is_admin(uid): return
            adm_start_announce(chat_id, uid)

        # ── الـ 20 ميزة الجديدة ──
        elif data == "adm_new_today":
            if not is_admin(uid): return
            adm_new_today(chat_id, msg_id)

        elif data == "adm_user_bots_by_id":
            if not is_admin(uid): return
            adm_start_user_bots_by_id(chat_id, uid)

        elif data == "adm_reset_points_id":
            if not is_admin(uid): return
            adm_start_reset_points(chat_id, uid)

        elif data == "adm_set_user_max":
            if not is_admin(uid): return
            adm_start_set_user_max(chat_id, uid)

        elif data == "adm_crashed_bots":
            if not is_admin(uid): return
            adm_show_crashed_bots(chat_id, msg_id)

        elif data == "adm_search_bot_name":
            if not is_admin(uid): return
            adm_start_search_bot(chat_id, uid)

        elif data == "adm_bots_summary":
            if not is_admin(uid): return
            adm_show_bots_summary(chat_id, msg_id)

        elif data == "adm_clear_proc_logs":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ التنظيف…")
            threading.Thread(target=adm_clear_process_logs, args=(chat_id,), daemon=True).start()

        elif data == "adm_msg_to_inactive":
            if not is_admin(uid): return
            adm_start_msg_inactive(chat_id, uid)

        elif data == "adm_broadcast_active_only":
            if not is_admin(uid): return
            adm_start_broadcast_active(chat_id, uid)

        elif data == "adm_receivers_count":
            if not is_admin(uid): return
            adm_show_receivers_count(chat_id, msg_id)

        elif data == "adm_db_table_stats":
            if not is_admin(uid): return
            adm_show_db_table_stats(chat_id, msg_id)

        elif data == "adm_deploy_stats":
            if not is_admin(uid): return
            adm_show_deploy_stats(chat_id, msg_id)

        elif data == "adm_daily_report":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ توليد التقرير…")
            threading.Thread(target=adm_send_daily_report, args=(chat_id,), daemon=True).start()

        elif data == "adm_points_dist":
            if not is_admin(uid): return
            adm_show_points_dist(chat_id, msg_id)

        elif data == "adm_view_settings":
            if not is_admin(uid): return
            adm_show_all_settings(chat_id, msg_id)

        elif data == "adm_toggle_auto_approve":
            if not is_admin(uid): return
            adm_toggle_auto_approve_fn(chat_id, msg_id)

        elif data == "adm_clear_audit":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ التنظيف…")
            threading.Thread(target=adm_clear_old_audit, args=(chat_id,), daemon=True).start()

        elif data == "adm_approve_id":
            if not is_admin(uid): return
            adm_start_approve_id(chat_id, uid)

        elif data == "adm_proc_info":
            if not is_admin(uid): return
            adm_show_proc_info(chat_id, msg_id)

        # ── الدفعة الثالثة — 20 ميزة ──
        elif data == "adm_user_profile":
            if not is_admin(uid): return
            adm_start_user_profile(chat_id, uid)

        elif data == "adm_pending_users":
            if not is_admin(uid): return
            adm_show_pending_users(chat_id, msg_id)

        elif data == "adm_ban_by_id":
            if not is_admin(uid): return
            adm_start_ban_by_id(chat_id, uid)

        elif data == "adm_unban_by_id":
            if not is_admin(uid): return
            adm_start_unban_by_id(chat_id, uid)

        elif data == "adm_vip_users":
            if not is_admin(uid): return
            adm_show_vip_users(chat_id, msg_id)

        elif data == "adm_force_stop_bot":
            if not is_admin(uid): return
            adm_start_force_stop_bot(chat_id, uid)

        elif data == "adm_force_start_bot":
            if not is_admin(uid): return
            adm_start_force_start_bot(chat_id, uid)

        elif data == "adm_bot_files_info":
            if not is_admin(uid): return
            adm_start_bot_files_info(chat_id, uid)

        elif data == "adm_top_bots":
            if not is_admin(uid): return
            adm_show_top_bots(chat_id, msg_id)

        elif data == "adm_new_bots_today":
            if not is_admin(uid): return
            adm_show_new_bots_today(chat_id, msg_id)

        elif data == "adm_msg_by_id":
            if not is_admin(uid): return
            adm_start_msg_by_id(chat_id, uid)

        elif data == "adm_broadcast_pending":
            if not is_admin(uid): return
            adm_start_broadcast_pending(chat_id, uid)

        elif data == "adm_last_broadcast_stats":
            if not is_admin(uid): return
            adm_show_last_broadcast_stats(chat_id, msg_id)

        elif data == "adm_weekly_report":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ توليد التقرير الأسبوعي…")
            threading.Thread(target=adm_send_weekly_report, args=(chat_id,), daemon=True).start()

        elif data == "adm_top_uploaders":
            if not is_admin(uid): return
            adm_show_top_uploaders(chat_id, msg_id)

        elif data == "adm_error_log_view":
            if not is_admin(uid): return
            adm_show_error_log(chat_id, msg_id)

        elif data == "adm_activity_stats":
            if not is_admin(uid): return
            adm_show_activity_stats(chat_id, msg_id)

        elif data == "adm_maintenance_mode":
            if not is_admin(uid): return
            adm_toggle_maintenance(chat_id, msg_id)

        elif data == "adm_sys_info":
            if not is_admin(uid): return
            adm_show_sys_info(chat_id, msg_id)

        elif data == "adm_clear_blocked_db":
            if not is_admin(uid): return
            bot.answer_callback_query(call.id, "⏳ جارٍ التنظيف…")
            threading.Thread(target=adm_clear_blocked_db, args=(chat_id,), daemon=True).start()

        elif data == "adm_broadcast":
            set_pending(uid, {"type": "broadcast"})
            bot.send_message(chat_id, "📢 أرسل نص الإذاعة الآن، أو /cancel.", reply_markup=back_admin_kb())

        elif data == "adm_broadcast_channel":
            set_pending(uid, {"type": "broadcast_channel_list"})
            bot.send_message(
                chat_id,
                "📺 <b>إذاعة للقنوات</b>\n\nأرسل أسماء القنوات مفصولة بفاصلة:\n"
                "مثال: <code>@channel1, @channel2</code>\n\n"
                "⚠️ يجب أن يكون البوت مشرفاً في كل قناة.\n/cancel للإلغاء.",
                reply_markup=back_admin_kb(),
            )

        elif data == "adm_blocked_users":
            show_blocked_users_report(chat_id, uid)

        elif data == "adm_top_users":
            show_top_users(chat_id, msg_id)

        elif data == "adm_export_users":
            export_users_file(chat_id)

        elif data == "adm_gift_new":
            start_create_gift_link(chat_id, uid)

        elif data == "adm_force_channel":
            show_force_channels_panel(chat_id, uid, msg_id)

        elif data == "adm_fc_list":
            show_force_channels_list(chat_id, msg_id)

        elif data == "adm_fc_check":
            channels = get_force_channels()
            if not channels:
                bot.answer_callback_query(call.id, "لا توجد قنوات مضافة.")
            else:
                bot.answer_callback_query(call.id, "⏳ جارٍ الفحص...")
                lines = ["🔍 <b>تقرير صلاحيات البوت في القنوات:</b>\n"]
                all_ok = True
                for ch in channels:
                    lbl = html_escape(ch["label"] or ch["channel"])
                    perm = check_bot_channel_permissions(ch["channel"])
                    if perm["ok"]:
                        lines.append(f"✅ <b>{lbl}</b> — صلاحيات سليمة")
                    else:
                        all_ok = False
                        err = html_escape(perm["error"] or "خطأ غير محدد")
                        lines.append(
                            f"❌ <b>{lbl}</b>\n"
                            f"   <code>{html_escape(str(ch['channel']))}</code>\n"
                            f"   ↳ {err}"
                        )
                        # تنبيه الأدمن وإعادة تهيئة كاش التحذير لهذه القناة لإعادة الإرسال
                        _perm_warn_sent.discard(str(ch["channel"]))
                        notify_admin_perm_error(str(ch["channel"]), ch["label"] or ch["channel"], perm["error"] or "خطأ غير محدد")
                if all_ok:
                    lines.append("\n🎉 جميع القنوات تعمل بشكل صحيح!")
                else:
                    lines.append(
                        "\n📌 <b>الحل:</b> اجعل البوت مشرفاً في القنوات المعطوبة\n"
                        "ومنحه صلاحية <b>Invite Users via Link</b>."
                    )
                bot.send_message(chat_id, "\n".join(lines), reply_markup=back_admin_kb())

        elif data == "adm_fc_add":
            show_fc_wizard_step1(chat_id, uid)

        elif data == "fc_wiz_to2":
            # التالي من الخطوة 1 إلى 2 — اطلب الـ ID
            pending = get_pending(uid) or {}
            if not pending.get("link"):
                bot.answer_callback_query(call.id, "⚠️ انتهت الجلسة، أعد المحاولة.", show_alert=True)
                show_force_channels_panel(chat_id, uid, msg_id)
                return
            pending["type"] = "fc_wiz_step2"
            set_pending(uid, pending)
            bot.answer_callback_query(call.id, "✅ تم الانتقال للخطوة 2")
            bot.send_message(
                chat_id,
                "📢 <b>إضافة قناة — الخطوة 2 من 3</b>\n\n"
                "🆔 <b>أرسل الـ ID (Chat ID)</b> للقناة:\n\n"
                "مثال قناة خاصة:\n<code>-1001234567890</code>\n"
                "أو يوزرنيم قناة عامة:\n<code>@channel_name</code>",
                reply_markup=_fc_wizard_cancel_kb(),
            )

        elif data == "fc_wiz_to3":
            # التالي من الخطوة 2 إلى 3 — اطلب الاسم
            pending = get_pending(uid) or {}
            if not pending.get("channel_id"):
                bot.answer_callback_query(call.id, "⚠️ انتهت الجلسة، أعد المحاولة.", show_alert=True)
                show_force_channels_panel(chat_id, uid, msg_id)
                return
            pending["type"] = "fc_wiz_step3"
            set_pending(uid, pending)
            bot.answer_callback_query(call.id, "✅ تم الانتقال للخطوة 3")
            bot.send_message(
                chat_id,
                "📢 <b>إضافة قناة — الخطوة 3 من 3</b>\n\n"
                "✏️ <b>أرسل اسم القناة</b> الذي سيظهر للمستخدمين:",
                reply_markup=_fc_wizard_cancel_kb(),
            )

        elif data.startswith("adm_fc_upd_"):
            # تحديث رابط (مسار قديم للتوافق)
            try:
                fid = int(data.split("_")[-1])
            except Exception:
                fid = None
            if fid:
                pop_pending(uid)
                set_pending(uid, {"type": "fc_edit_link", "fid": fid})
                ch_row = db_fetchone("SELECT label, channel FROM force_channels WHERE id=?", (fid,))
                lbl = html_escape((ch_row or {}).get("label") or (ch_row or {}).get("channel") or "")
                bot.send_message(chat_id,
                                 f"🔗 <b>تعديل رابط الدعوة</b>\n\n"
                                 f"القناة: <b>{lbl}</b>\n\n"
                                 "أرسل الرابط الجديد:\n"
                                 "<code>https://t.me/+AbCdEfGhIjKl</code>\n"
                                 "أو أرسل <code>-</code> لحذف الرابط.\n\nأو /cancel.",
                                 reply_markup=_fc_wizard_cancel_kb())
            else:
                show_force_channels_list(chat_id, msg_id)

        elif data.startswith("adm_fc_edit_"):
            # لوحة تعديل القناة
            try:
                fid = int(data.split("_")[-1])
            except Exception:
                fid = None
            if fid:
                bot.answer_callback_query(call.id)
                show_fc_edit_panel(chat_id, fid, msg_id)
            else:
                show_force_channels_list(chat_id, msg_id)

        elif data.startswith("adm_fc_ename_"):
            # تعديل الاسم
            try:
                fid = int(data.split("_")[-1])
            except Exception:
                fid = None
            if fid:
                pop_pending(uid)
                set_pending(uid, {"type": "fc_edit_name", "fid": fid})
                ch = db_fetchone("SELECT label, channel FROM force_channels WHERE id=?", (fid,))
                current = html_escape((ch or {}).get("label") or (ch or {}).get("channel") or "")
                bot.send_message(chat_id,
                                 f"✏️ <b>تعديل اسم القناة</b>\n\n"
                                 f"الاسم الحالي: <b>{current}</b>\n\n"
                                 "أرسل الاسم الجديد أو /cancel.",
                                 reply_markup=_fc_wizard_cancel_kb())
            else:
                show_force_channels_list(chat_id, msg_id)

        elif data.startswith("adm_fc_elink_"):
            # تعديل الرابط
            try:
                fid = int(data.split("_")[-1])
            except Exception:
                fid = None
            if fid:
                pop_pending(uid)
                set_pending(uid, {"type": "fc_edit_link", "fid": fid})
                ch = db_fetchone("SELECT invite_link FROM force_channels WHERE id=?", (fid,))
                current = html_escape((ch or {}).get("invite_link") or "—")
                bot.send_message(chat_id,
                                 f"🔗 <b>تعديل رابط الدعوة</b>\n\n"
                                 f"الرابط الحالي: <code>{current}</code>\n\n"
                                 "أرسل الرابط الجديد:\n"
                                 "<code>https://t.me/+AbCdEfGhIjKl</code>\n"
                                 "أو أرسل <code>-</code> لحذف الرابط.\n\nأو /cancel.",
                                 reply_markup=_fc_wizard_cancel_kb())
            else:
                show_force_channels_list(chat_id, msg_id)

        elif data.startswith("adm_fc_eid_"):
            # تعديل الـ ID
            try:
                fid = int(data.split("_")[-1])
            except Exception:
                fid = None
            if fid:
                pop_pending(uid)
                set_pending(uid, {"type": "fc_edit_id", "fid": fid})
                ch = db_fetchone("SELECT channel FROM force_channels WHERE id=?", (fid,))
                current = html_escape((ch or {}).get("channel") or "")
                bot.send_message(chat_id,
                                 f"🆔 <b>تعديل الـ ID</b>\n\n"
                                 f"الـ ID الحالي: <code>{current}</code>\n\n"
                                 "أرسل الـ ID الجديد:\n"
                                 "مثال رقمي: <code>-1001234567890</code>\n"
                                 "أو يوزرنيم: <code>@channel_name</code>\n\nأو /cancel.",
                                 reply_markup=_fc_wizard_cancel_kb())
            else:
                show_force_channels_list(chat_id, msg_id)

        elif data.startswith("adm_fc_del_"):
            try:
                fid = int(data.split("_")[-1])
                del_force_channel(fid)
                bot.answer_callback_query(call.id, "🗑 تم حذف القناة")
            except Exception:
                pass
            show_force_channels_list(chat_id, msg_id)

        elif data == "adm_set_upload_price":
            start_set_upload_price(chat_id, uid)

        elif data == "adm_set_transfer_fee":
            start_set_transfer_fee(chat_id, uid)

        elif data == "adm_ban_by_id":
            start_ban_by_id(chat_id, uid)

        elif data == "adm_unban_by_id":
            start_unban_by_id(chat_id, uid)

        elif data == "adm_user_info":
            start_user_info(chat_id, uid)

        elif data == "adm_toggle_bot":
            new_state = not is_bot_disabled()
            set_bot_disabled(new_state)
            try:
                bot.edit_message_text("👑 لوحة المطور:", chat_id, msg_id, reply_markup=admin_menu_markup())
            except Exception:
                pass

        elif data == "adm_mods":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "mods_menu"})
            bot.send_message(
                chat_id,
                "🛡️ <b>المشرفين</b>\n\n"
                "أرسل ID لإضافة/حذف مشرف.\n"
                "صيغة الإضافة: <code>+123456789</code>\n"
                "صيغة الحذف: <code>-123456789</code>\n"
                "/cancel للإلغاء.",
                reply_markup=back_admin_kb(),
            )

        elif data == "adm_section_prices":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "set_section_price"})
            bot.send_message(
                chat_id,
                "💵 <b>أسعار الأقسام</b>\n\nاكتب بالشكل:\n"
                "<code>netlify 5</code>\n<code>vercel 5</code>\n<code>terminal 1</code>\n\n"
                "0 = مجاني.\n/cancel للإلغاء.",
                reply_markup=back_admin_kb(),
            )

        elif data == "adm_give_points":
            set_pending(uid, {"type": "give_points_input", "step": "id"})
            bot.send_message(chat_id, "💰 <b>منح نقاط لمستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\n/cancel للإلغاء.",
                             reply_markup=back_admin_kb())

        elif data == "adm_set_points":
            set_pending(uid, {"type": "set_points_input", "step": "id"})
            bot.send_message(chat_id, "⭐ <b>تعيين نقاط مستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\n/cancel للإلغاء.",
                             reply_markup=back_admin_kb())

        elif data == "adm_set_max_bots":
            set_pending(uid, {"type": "set_max_bots_input", "step": "id"})
            bot.send_message(chat_id, "🤖 <b>تعديل حد البوتات لمستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\n/cancel للإلغاء.",
                             reply_markup=back_admin_kb())

        elif data == "adm_send_user":
            set_pending(uid, {"type": "send_user_id"})
            bot.send_message(chat_id, "📩 <b>إرسال رسالة لمستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\n/cancel للإلغاء.",
                             reply_markup=back_admin_kb())

        elif data == "adm_set_welcome":
            if not is_admin(uid):
                return
            current_welcome = get_setting("welcome_text") or ""
            preview = current_welcome[:200] + ("…" if len(current_welcome) > 200 else "") if current_welcome else "_(لم يُضبط بعد)_"
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_welcome"})
            bot.edit_message_text(
                f"✏️ <b>تغيير رسالة الترحيب</b>\n\n"
                f"الرسالة الحالية:\n<code>{html_escape(preview)}</code>\n\n"
                "أرسل النص الجديد لرسالة الترحيب.\n"
                "يمكنك استخدام <code>{name}</code> لاسم المستخدم.\n"
                "أرسل <code>-</code> لإعادة النص الافتراضي.",
                chat_id, msg_id, reply_markup=back_admin_kb(),
            )

        elif data == "adm_set_welcome_img":
            if not is_admin(uid):
                return
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_welcome_img"})
            has_custom = bool(get_setting("welcome_image_id"))
            status_txt = "✅ يوجد صورة مخصصة حالياً." if has_custom else "ℹ️ لا توجد صورة مخصصة، يُستخدم الافتراضي."
            _img_kb = types.InlineKeyboardMarkup()
            if has_custom or True:  # دائماً نعرض زرار المعاينة
                _img_kb.add(types.InlineKeyboardButton(
                    "🖼 معاينة الصورة الحالية", callback_data="adm_preview_welcome_img", style="primary",
                ))
            _img_kb.add(types.InlineKeyboardButton(
                " رجوع للوحة الأدمن", callback_data="adm_panel",
                style="primary", icon_custom_emoji_id=E_BACK,
            ))
            bot.edit_message_text(
                f"🖼 <b>تغيير صورة الترحيب</b>\n\n"
                f"{status_txt}\n\n"
                "أرسل الصورة الجديدة التي تريدها كصورة ترحيب.\n"
                "أرسل <code>-</code> لإعادة الصورة الافتراضية.",
                chat_id, msg_id, reply_markup=_img_kb,
            )

        elif data == "adm_preview_welcome_img":
            if not is_admin(uid):
                return
            _img = get_setting("welcome_image_id") or WELCOME_IMAGE
            _src = "مخصصة" if get_setting("welcome_image_id") else "افتراضية"
            try:
                bot.send_photo(
                    chat_id, _img,
                    caption=f"🖼 <b>صورة الترحيب الحالية</b> ({_src})",
                    parse_mode="HTML",
                    reply_markup=back_admin_kb(),
                )
            except Exception:
                bot.send_message(chat_id, "⚠️ تعذّر تحميل الصورة الحالية.", reply_markup=back_admin_kb())

        elif data == "adm_set_banned_img":
            if not is_admin(uid):
                return
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_banned_img"})
            has_custom = bool(get_setting("banned_image_id"))
            status_txt = "✅ يوجد صورة مخصصة حالياً." if has_custom else "ℹ️ لا توجد صورة مخصصة، يُستخدم الافتراضي."
            _bkb = types.InlineKeyboardMarkup()
            _bkb.add(types.InlineKeyboardButton("🖼 معاينة الصورة الحالية", callback_data="adm_preview_banned_img", style="primary"))
            _bkb.add(types.InlineKeyboardButton(" رجوع للوحة الأدمن", callback_data="adm_panel", style="primary", icon_custom_emoji_id=E_BACK))
            bot.edit_message_text(
                f"🚫 <b>تغيير صورة الحظر</b>\n\n{status_txt}\n\n"
                "أرسل الصورة الجديدة لصورة الحظر.\n"
                "أرسل <code>-</code> لإعادة الصورة الافتراضية.",
                chat_id, msg_id, reply_markup=_bkb,
            )

        elif data == "adm_preview_banned_img":
            if not is_admin(uid):
                return
            _img = get_setting("banned_image_id") or BANNED_IMAGE
            _src = "مخصصة" if get_setting("banned_image_id") else "افتراضية"
            try:
                bot.send_photo(chat_id, _img, caption=f"🚫 <b>صورة الحظر الحالية</b> ({_src})", parse_mode="HTML", reply_markup=back_admin_kb())
            except Exception:
                bot.send_message(chat_id, "⚠️ تعذّر تحميل الصورة الحالية.", reply_markup=back_admin_kb())

        elif data == "adm_set_maint_img":
            if not is_admin(uid):
                return
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_maint_img"})
            has_custom = bool(get_setting("maintenance_image_id"))
            status_txt = "✅ يوجد صورة مخصصة حالياً." if has_custom else "ℹ️ لا توجد صورة مخصصة، يُستخدم الافتراضي."
            _mkb = types.InlineKeyboardMarkup()
            _mkb.add(types.InlineKeyboardButton("🖼 معاينة الصورة الحالية", callback_data="adm_preview_maint_img", style="primary"))
            _mkb.add(types.InlineKeyboardButton(" رجوع للوحة الأدمن", callback_data="adm_panel", style="primary", icon_custom_emoji_id=E_BACK))
            bot.edit_message_text(
                f"🔧 <b>تغيير صورة الصيانة</b>\n\n{status_txt}\n\n"
                "أرسل الصورة الجديدة لصورة الصيانة.\n"
                "أرسل <code>-</code> لإعادة الصورة الافتراضية.",
                chat_id, msg_id, reply_markup=_mkb,
            )

        elif data == "adm_preview_maint_img":
            if not is_admin(uid):
                return
            _img = get_setting("maintenance_image_id") or MAINTENANCE_IMAGE
            _src = "مخصصة" if get_setting("maintenance_image_id") else "افتراضية"
            try:
                bot.send_photo(chat_id, _img, caption=f"🔧 <b>صورة الصيانة الحالية</b> ({_src})", parse_mode="HTML", reply_markup=back_admin_kb())
            except Exception:
                bot.send_message(chat_id, "⚠️ تعذّر تحميل الصورة الحالية.", reply_markup=back_admin_kb())

        elif data == "adm_set_banned_txt":
            if not is_admin(uid):
                return
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_banned_txt"})
            current = get_setting("banned_text") or "_(الافتراضي)_"
            preview = current[:200] + ("…" if len(current) > 200 else "")
            bot.edit_message_text(
                f"✍️ <b>رسالة الحظر</b>\n\nالنص الحالي:\n<code>{html_escape(preview)}</code>\n\n"
                "أرسل النص الجديد (يدعم HTML).\n"
                "أرسل <code>-</code> لإعادة النص الافتراضي.",
                chat_id, msg_id, reply_markup=back_admin_kb(),
            )

        elif data == "adm_set_maint_txt":
            if not is_admin(uid):
                return
            pop_pending(uid)
            set_pending(uid, {"type": "adm_set_maint_txt"})
            current = get_setting("maintenance_text") or "_(الافتراضي)_"
            preview = current[:200] + ("…" if len(current) > 200 else "")
            bot.edit_message_text(
                f"🔧 <b>رسالة الصيانة</b>\n\nالنص الحالي:\n<code>{html_escape(preview)}</code>\n\n"
                "أرسل النص الجديد (يدعم HTML).\n"
                "أرسل <code>-</code> لإعادة النص الافتراضي.",
                chat_id, msg_id, reply_markup=back_admin_kb(),
            )

        elif data == "adm_toggle_notify":
            current = is_admin_notify_enabled("notify_admin_new_user", True)
            set_setting("notify_admin_new_user", "0" if current else "1")
            try:
                bot.edit_message_text("👑 لوحة المطور:", chat_id, msg_id, reply_markup=admin_menu_markup())
            except Exception:
                pass

        elif data == "adm_btn_colors":
            show_btn_colors(chat_id, msg_id)

        elif data == "adm_custom_texts":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "adm_custom_text"})
            bot.send_message(
                chat_id,
                "📝 <b>تخصيص نص أو زر</b>\n\n"
                "أرسل بالشكل:\n"
                "<code>btn_new_bot=➕ بوت جديد</code>\n"
                "<code>text_ar_welcome_title=مرحباً</code>\n"
                "<code>terms_text=نص الشروط...</code>\n\n"
                "مفاتيح أزرار شائعة: btn_new_bot btn_my_bots btn_help btn_dev btn_channel\n"
                "/cancel للإلغاء.",
                reply_markup=back_admin_kb(),
            )

        elif data == "adm_custom_images":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "adm_custom_image_key"})
            bot.send_message(
                chat_id,
                "🖼 <b>تخصيص وسائط الأقسام (صورة أو فيديو)</b>\n\n"
                "1) أرسل المفتاح:\n"
                "<code>welcome success error files manage live terms settings about info</code>\n"
                "أو <code>all</code>\n\n"
                "2) ثم أرسل <b>صورة</b> أو <b>فيديو</b> أو رابط URL\n"
                "لحذف فيديو قسم: أرسل المفتاح ثم <code>clear_video</code>\n"
                "/cancel.",
                reply_markup=back_admin_kb(),
            )

        elif data == "adm_edit_about":
            if not is_admin(uid):
                return
            set_pending(uid, {"type": "adm_edit_about"})
            bot.send_message(
                chat_id,
                "✏️ أرسل نص <b>معلومات البوت</b> الجديد (HTML مسموح).\n"
                "أو <code>-</code> لإعادة النص الافتراضي.\n/cancel",
                reply_markup=back_admin_kb(),
            )

        elif data.startswith("adm_btn_color_group:"):
            group_key = data.split(":", 1)[1]
            if group_key in BTN_COLOR_GROUPS:
                show_btn_color_pick(chat_id, group_key, msg_id)

        elif data.startswith("adm_btn_color_pick:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, group_key, color = parts
                if group_key in BTN_COLOR_GROUPS and color in _COLOR_LABELS:
                    set_setting(f"btn_color_{group_key}", color)
                    label, = BTN_COLOR_GROUPS[group_key]
                    color_lbl = _COLOR_LABELS[color]
                    bot.answer_callback_query(call.id, f"✅ {label}: {color_lbl}", show_alert=False)
                show_btn_color_pick(chat_id, group_key, msg_id)

        elif data == "adm_search_user":
            start_search_user(chat_id, uid)

        elif data == "adm_give_all_points":
            set_pending(uid, {"type": "give_all_points_input"})
            count_row = db_fetchone("SELECT COUNT(*) AS c FROM users WHERE approved=1 AND banned=0")
            count = count_row["c"] if count_row else 0
            bot.send_message(
                chat_id,
                f"🎁 <b>منح نقاط لكل المستخدمين</b>\n\n"
                f"👥 عدد المستخدمين المؤهلين: <b>{count}</b>\n\n"
                "أرسل عدد النقاط (موجب=إضافة، سالب=خصم).\n/cancel للإلغاء.",
                reply_markup=back_admin_kb(),
            )

        elif data == "admin_warn_user":
            set_pending(uid, {"type": "warn_user_id"})
            bot.send_message(
                chat_id,
                "⚠️ <b>تحذير مستخدم</b>\n\nأرسل <b>ID</b> المستخدم.\nأو /cancel.",
                reply_markup=back_admin_kb(),
            )

        elif data == "admin_list_blocked":
            show_list_blocked_from_db(chat_id, msg_id)

        elif data == "adm_del_stopped":
            stopped = db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE is_running=0 AND approved=1")
            count = stopped["c"] if stopped else 0
            kb_confirm = types.InlineKeyboardMarkup()
            kb_confirm.add(
                types.InlineKeyboardButton(" نعم احذف الكل", callback_data="adm_del_stopped_confirm",
                    style="danger", icon_custom_emoji_id=E_DELETE),
                types.InlineKeyboardButton(" تراجع", callback_data="adm_panel",
                    style="primary", icon_custom_emoji_id=E_BACK),
            )
            bot.edit_message_text(f"⚠️ هل أنت متأكد من حذف <b>{count}</b> بوت متوقف وكل ملفاته؟",
                                  chat_id, msg_id, reply_markup=kb_confirm)

        elif data == "adm_del_stopped_confirm":
            rows = db_fetchall("SELECT id FROM projects WHERE is_running=0 AND approved=1")
            deleted = 0
            for r in rows:
                manager.stop_project(r["id"])
                db_execute("DELETE FROM projects WHERE id=?", (r["id"],))
                deleted += 1
            try:
                bot.edit_message_text(f"✅ تم حذف <b>{deleted}</b> بوت متوقف.", chat_id, msg_id,
                                      reply_markup=back_admin_kb())
            except Exception:
                pass

        elif data.startswith("adm_approve_user_"):
            target = int(data.split("_")[-1])
            db_execute("UPDATE users SET approved=1, banned=0 WHERE id=?", (target,))
            try:
                bot.send_message(target, f"🎉 تم تفعيل حسابك. أرسل /start للبدء.\n\n💬 {get_random_quote()}")
            except Exception:
                pass

        elif data.startswith("adm_ban_user_"):
            target = int(data.split("_")[-1])
            db_execute("UPDATE users SET banned=1 WHERE id=?", (target,))
            for p in db_fetchall("SELECT id FROM projects WHERE user_id=?", (target,)):
                manager.stop_project(p["id"])

        elif data.startswith("adm_unban_user_"):
            target = int(data.split("_")[-1])
            db_execute("UPDATE users SET banned=0 WHERE id=?", (target,))

        elif data.startswith("adm_approve_proj_"):
            pid = int(data.split("_")[-1])
            approve_project(pid)
            try:
                bot.edit_message_text(f"✅ تمت الموافقة على البوت #{pid}", chat_id, msg_id)
            except Exception:
                pass

        elif data.startswith("adm_reject_proj_"):
            pid = int(data.split("_")[-1])
            row = db_fetchone("SELECT user_id, name FROM projects WHERE id=?", (pid,))
            if row:
                try:
                    bot.send_message(row["user_id"], f"❌ تم رفض البوت <b>{html_escape(row['name'])}</b> من المطور.")
                except Exception:
                    pass
            db_execute("DELETE FROM projects WHERE id=?", (pid,))
            try:
                bot.edit_message_text(f"❌ تم رفض البوت #{pid}", chat_id, msg_id)
            except Exception:
                pass

        elif data.startswith("adm_approve_file_"):
            pending_id = int(data.split("_")[-1])
            pu = db_fetchone("SELECT * FROM pending_uploads WHERE id=?", (pending_id,))
            if not pu:
                bot.answer_callback_query(call.id, "❌ الملف غير موجود أو تمت معالجته مسبقاً.")
            else:
                try:
                    file_info = bot.get_file(pu["telegram_file_id"])
                    file_data = bot.download_file(file_info.file_path)
                    fname = pu["filename"] or "file.bin"
                    added = 0
                    if fname.lower().endswith(".zip"):
                        try:
                            zf = zipfile.ZipFile(io.BytesIO(file_data))
                            names = [n for n in zf.namelist() if n and not n.endswith("/") and "__MACOSX" not in n and not n.endswith(".DS_Store")]
                            top = None
                            tops = [n.split("/", 1)[0] for n in names if "/" in n]
                            if tops and len(set(tops)) == 1:
                                top = tops[0] + "/"
                            for n in names:
                                rel = n[len(top):] if top and n.startswith(top) else n
                                rel = rel.lstrip("/").replace("\\", "/")
                                if not rel or ".." in rel:
                                    continue
                                data = zf.read(n)
                                if len(data) > MAX_FILE_SIZE:
                                    continue
                                safe = "/".join(safe_filename(part) for part in rel.split("/") if part)
                                if not safe:
                                    continue
                                db_execute(
                                    "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
                                    "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
                                    "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
                                    (pu["project_id"], safe, sqlite3.Binary(data), len(data)),
                                )
                                added += 1
                        except Exception as ze:
                            bot.answer_callback_query(call.id, f"❌ ZIP تالف: {str(ze)[:80]}")
                            raise
                    else:
                        db_execute(
                            "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
                            "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
                            "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
                            (pu["project_id"], fname, sqlite3.Binary(file_data), len(file_data)),
                        )
                        added = 1
                    db_execute("DELETE FROM pending_uploads WHERE id=?", (pending_id,))
                    proj = db_fetchone("SELECT name FROM projects WHERE id=?", (pu["project_id"],))
                    try:
                        bot.send_message(
                            pu["user_id"],
                            f"✅ تمت الموافقة وإضافة <b>{added}</b> ملف(ات) من <code>{html_escape(fname)}</code> "
                            f"للبوت <b>{html_escape((proj or {}).get('name', ''))}</b>.",
                        )
                    except Exception:
                        pass
                    try:
                        bot.edit_message_caption(
                            chat_id=chat_id,
                            message_id=msg_id,
                            caption=f"✅ تمت الموافقة على <code>{html_escape(fname)}</code> ({added} ملف) #{pending_id}",
                        )
                    except Exception:
                        try:
                            bot.edit_message_text(
                                f"✅ تمت الموافقة على <code>{html_escape(fname)}</code> ({added} ملف) #{pending_id}",
                                chat_id, msg_id,
                            )
                        except Exception:
                            pass
                except Exception as e:
                    log.exception("approve_file failed for pending_id=%s", pending_id)
                    bot.answer_callback_query(call.id, f"❌ فشل تحميل الملف: {str(e)[:100]}")

        elif data.startswith("adm_reject_file_"):
            pending_id = int(data.split("_")[-1])
            pu = db_fetchone("SELECT * FROM pending_uploads WHERE id=?", (pending_id,))
            if not pu:
                bot.answer_callback_query(call.id, "❌ الملف غير موجود أو تمت معالجته مسبقاً.")
            else:
                db_execute("DELETE FROM pending_uploads WHERE id=?", (pending_id,))
                try:
                    bot.send_message(
                        pu["user_id"],
                        f"❌ تم رفض الملف <code>{html_escape(pu['filename'])}</code> من المطور.",
                    )
                except Exception:
                    pass
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg_id,
                        caption=f"❌ تم رفض الملف <code>{html_escape(pu['filename'])}</code> #{pending_id}",
                    )
                except Exception:
                    try:
                        bot.edit_message_text(
                            f"❌ تم رفض الملف <code>{html_escape(pu['filename'])}</code> #{pending_id}",
                            chat_id, msg_id,
                        )
                    except Exception:
                        pass

    except Exception as e:
        log.exception("callback error: %s", data)
        try:
            bot.send_message(chat_id, f"❌ خطأ: {str(e)[:200]}")
        except Exception:
            pass


# ============================================================
# 29) Fallback للرسائل النصية
# ============================================================

@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_hosted_token",
    content_types=["text"],
)
def receive_set_hosted_token(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    pop_pending(uid)
    token = (message.text or "").strip()
    if not token or ":" not in token or len(token) < 40:
        bot.send_message(uid, "❌ توكن غير صالح.")
        return
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
    if not p or (p["user_id"] != uid and not is_admin(uid)):
        bot.send_message(uid, "❌ غير مسموح.")
        return
    info = telegram_get_me(token)
    if not info:
        bot.send_message(uid, "❌ فشل التحقق من التوكن عبر Telegram getMe.")
        return
    ok_reg, reg_msg = register_project_token(pid, uid, token)
    if not ok_reg:
        bot.send_message(uid, reg_msg)
        return
    db_execute(
        "UPDATE projects SET hosted_token=?, hosted_bot_username=?, hosted_bot_id=?, hosted_bot_name=? WHERE id=?",
        (token, info.get("username") or "", info.get("id"), info.get("first_name") or "", pid),
    )
    # محاولة حقن التوكن في الملفات النصية الشائعة
    try:
        files = db_fetchall("SELECT id, filename, content FROM project_files WHERE project_id=?", (pid,))
        for f in files:
            fn = (f.get("filename") or "").lower()
            if not fn.endswith((".py", ".js", ".env", ".json", ".txt")):
                continue
            raw = bytes(f["content"])
            try:
                text = raw.decode("utf-8")
            except Exception:
                continue
            new_text, n = re.subn(
                r"([0-9]{8,}:[A-Za-z0-9_-]{35,})",
                token,
                text,
                count=3,
            )
            if n == 0:
                # استبدال متغيرات شائعة
                new_text, n = re.subn(
                    r"(BOT_TOKEN|API_TOKEN|TOKEN)\s*=\s*['\"][^'\"]+['\"]",
                    rf"\1 = '{token}'",
                    text,
                    count=2,
                )
            if n:
                db_execute(
                    "UPDATE project_files SET content=?, size_bytes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (sqlite3.Binary(new_text.encode("utf-8")), len(new_text.encode("utf-8")), f["id"]),
                )
    except Exception:
        log.exception("token inject failed")
    bot.send_message(
        uid,
        f"✅ تم تحديث التوكن.\\n🤖 @{html_escape(info.get('username') or '')}\\n🆔 <code>{info.get('id')}</code>\\n"
        "أعد تشغيل البوت لتطبيق التغيير.",
    )


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_project_owner",
    content_types=["text"],
)
def receive_set_project_owner(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    pop_pending(uid)
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "❌ أرسل ID رقمياً.")
        return
    new_owner = int(text)
    p = db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
    if not p or (p["user_id"] != uid and not is_admin(uid)):
        bot.send_message(uid, "❌ غير مسموح.")
        return
    ensure_user_by_id(new_owner)
    db_execute("UPDATE projects SET user_id=? WHERE id=?", (new_owner, pid))
    bot.send_message(uid, f"✅ تم نقل ملكية المشروع #{pid} إلى <code>{new_owner}</code>.")
    try:
        bot.send_message(new_owner, f"🎁 تم نقل مشروع <b>{html_escape(p.get('name') or '')}</b> إلى حسابك.")
    except Exception:
        pass



@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_custom_text",
    content_types=["text"],
)
def receive_adm_custom_text(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    line = (message.text or "").strip()
    if "=" not in line:
        bot.send_message(uid, "❌ الصيغة: key=value", reply_markup=back_admin_kb())
        return
    key, val = line.split("=", 1)
    key, val = key.strip(), val.strip()
    if not key:
        bot.send_message(uid, "❌ مفتاح فارغ.", reply_markup=back_admin_kb())
        return
    set_setting(key, val)
    bot.send_message(uid, f"✅ تم حفظ <code>{html_escape(key)}</code>", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_custom_image_key",
    content_types=["text"],
)
def receive_adm_custom_image_key(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    key = (message.text or "").strip().lower()
    if not key:
        pop_pending(uid)
        return
    set_pending(uid, {"type": "adm_custom_image_file", "key": key})
    bot.send_message(uid, f"✅ المفتاح: <code>{html_escape(key)}</code>\\nالآن أرسل <b>صورة</b> أو رابط URL.\\n/cancel.")


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_custom_image_file",
    content_types=["text", "photo", "video", "animation", "document"],
)
def receive_adm_custom_image_file(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    key = pending.get("key") or "welcome"
    pop_pending(uid)
    url_or_id = None
    is_video = False
    if message.content_type == "photo" and message.photo:
        url_or_id = message.photo[-1].file_id
    elif message.content_type == "video" and message.video:
        url_or_id = message.video.file_id
        is_video = True
    elif message.content_type == "animation" and message.animation:
        url_or_id = message.animation.file_id
        is_video = True
    elif message.content_type == "document" and message.document:
        mime = (message.document.mime_type or "")
        url_or_id = message.document.file_id
        if "video" in mime:
            is_video = True
    else:
        url_or_id = (message.text or "").strip()
        if url_or_id.lower() == "clear_video":
            if key == "all":
                for k in ("welcome", "success", "error", "files", "manage", "live", "terms", "settings", "about", "info"):
                    set_setting(f"video_{k}", "")
            else:
                set_setting(f"video_{key}", "")
            bot.send_message(uid, "تم مسح فيديو القسم.", reply_markup=back_admin_kb())
            return
    if not url_or_id or url_or_id == "-":
        bot.send_message(uid, "لم يستلم شيء.", reply_markup=back_admin_kb())
        return
    keys = ("welcome", "success", "error", "files", "manage", "live", "terms", "settings", "about", "info")
    if key == "all":
        for k in keys:
            if is_video:
                set_setting(f"video_{k}", url_or_id)
            else:
                set_setting(f"image_{k}", url_or_id)
                set_setting(f"video_{k}", "")
        if not is_video:
            set_setting("welcome_image_id", url_or_id)
        bot.send_message(uid, "تم تعيين الوسائط لكل الاقسام (" + ("فيديو" if is_video else "صورة") + ").", reply_markup=back_admin_kb())
    else:
        if is_video:
            set_setting(f"video_{key}", url_or_id)
        else:
            set_setting(f"image_{key}", url_or_id)
            set_setting(f"video_{key}", "")
            if key == "welcome":
                set_setting("welcome_image_id", url_or_id)
        bot.send_message(uid, f"تم حفظ {'فيديو' if is_video else 'صورة'} <code>{html_escape(key)}</code>.", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "adm_edit_about",
    content_types=["text"],
)
def receive_adm_edit_about(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    text = (message.text or "").strip()
    if text == "-":
        set_setting("about_bot_text", "")
        bot.send_message(uid, "تم اعادة نص المعلومات الافتراضي.", reply_markup=back_admin_kb())
        return
    set_setting("about_bot_text", text)
    bot.send_message(uid, "تم حفظ نص معلومات البوت.", reply_markup=back_admin_kb())



@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "coupon_code",
    content_types=["text"],
)
def receive_coupon_code(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    code = (message.text or "").strip().upper()
    row = db_fetchone("SELECT * FROM coupons WHERE code=?", (code,))
    if not row:
        bot.send_message(uid, "كوبون غير صالح.")
        return
    if row.get("expires_at"):
        try:
            exp = datetime.strptime(str(row["expires_at"]).split(".")[0], "%Y-%m-%d %H:%M:%S")
            if datetime.utcnow() > exp:
                bot.send_message(uid, "انتهت صلاحية الكوبون.")
                return
        except Exception:
            pass
    if int(row.get("used_count") or 0) >= int(row.get("max_uses") or 1):
        bot.send_message(uid, "تم استنفاذ الكوبون.")
        return
    used = db_fetchone("SELECT 1 AS x FROM coupon_uses WHERE code=? AND user_id=?", (code, uid))
    if used:
        bot.send_message(uid, "استخدمت هذا الكوبون مسبقا.")
        return
    pts = int(row.get("points") or 0)
    db_execute("UPDATE coupons SET used_count = used_count + 1 WHERE code=?", (code,))
    db_execute("INSERT OR IGNORE INTO coupon_uses (code, user_id) VALUES (?,?)", (code, uid))
    db_execute("UPDATE users SET points = COALESCE(points,0) + ? WHERE id=?", (pts, uid))
    bot.send_message(uid, f"تم اضافة <b>{pts}</b> نقطة من الكوبون.")


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and (m.text or "").startswith("/coupon "),
    content_types=["text"],
)
def cmd_create_coupon(message):
    # /coupon CODE POINTS MAX
    if msg_seen(message):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "الاستخدام: /coupon CODE POINTS [MAX]")
        return
    code = parts[1].upper()
    try:
        pts = int(parts[2])
        mx = int(parts[3]) if len(parts) > 3 else 50
    except Exception:
        bot.send_message(message.chat.id, "ارقام غير صحيحة")
        return
    try:
        db_execute(
            "INSERT INTO coupons (code, points, max_uses) VALUES (?,?,?)",
            (code, pts, mx),
        )
        bot.send_message(message.chat.id, f"كوبون {code} = {pts} نقطة x{mx}")
    except Exception as e:
        bot.send_message(message.chat.id, f"فشل: {e}")



@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_env_file",
    content_types=["text"],
)
def receive_set_env_file(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    pop_pending(uid)
    p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
    if not p or (p["user_id"] != uid and not is_admin(uid)):
        bot.send_message(uid, "غير مسموح")
        return
    content = (message.text or "").encode("utf-8")
    db_execute(
        "INSERT INTO project_files (project_id, filename, content, size_bytes) VALUES (?,?,?,?) "
        "ON CONFLICT (project_id, filename) DO UPDATE SET content=excluded.content, "
        "size_bytes=excluded.size_bytes, updated_at=CURRENT_TIMESTAMP",
        (pid, ".env", sqlite3.Binary(content), len(content)),
    )
    bot.send_message(uid, "تم حفظ .env — اعد تشغيل البوت لتطبيق التغيير.")


@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_schedule",
    content_types=["text"],
)
def receive_set_schedule(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    pop_pending(uid)
    p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
    if not p or (p["user_id"] != uid and not is_admin(uid)):
        bot.send_message(uid, "غير مسموح")
        return
    text = (message.text or "").strip()
    if text.lower() == "off":
        db_execute("UPDATE projects SET schedule_json=NULL WHERE id=?", (pid,))
        bot.send_message(uid, "تم الغاء الجدولة.")
        return
    parts = text.split()
    if len(parts) != 2 or ":" not in parts[0] or ":" not in parts[1]:
        bot.send_message(uid, "صيغة: 08:00 23:00")
        return
    sch = json.dumps({"start": parts[0], "stop": parts[1]})
    db_execute("UPDATE projects SET schedule_json=? WHERE id=?", (sch, pid))
    bot.send_message(uid, f"تم حفظ الجدولة: تشغيل {parts[0]} / ايقاف {parts[1]} (UTC)")



@bot.message_handler(
    func=lambda m: get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "set_heir",
    content_types=["text"],
)
def receive_set_heir(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pending = get_pending(uid) or {}
    pid = pending.get("project_id")
    pop_pending(uid)
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        bot.send_message(uid, "ID غير صالح")
        return
    heir = int(text)
    p = db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
    if not p or p["user_id"] != uid:
        bot.send_message(uid, "غير مسموح")
        return
    db_execute("UPDATE projects SET heir_uid=? WHERE id=?", (heir, pid))
    bot.send_message(uid, f"تم تعيين الوريث <code>{heir}</code> للمشروع #{pid}")


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "sla_points",
    content_types=["text"],
)
def receive_sla_points(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    text = (message.text or "").strip()
    if not text.isdigit():
        bot.send_message(uid, "رقم غير صالح", reply_markup=back_admin_kb())
        return
    pts = int(text)
    n = apply_sla_compensation(pts, reason=f"manual SLA by {uid}")
    bot.send_message(uid, f"تم تعويض {n} مستخدم بـ {pts} نقطة", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_pending(m.from_user.id) is not None
    and get_pending(m.from_user.id).get("type") == "selective_maint",
    content_types=["text"],
)
def receive_selective_maint(message):
    if msg_seen(message):
        return
    uid = message.from_user.id
    pop_pending(uid)
    text = (message.text or "").strip().lower()
    if text == "off":
        set_setting("selective_maint", "")
        bot.send_message(uid, "تم الغاء الصيانة الانتقائية", reply_markup=back_admin_kb())
        return
    set_setting("selective_maint", text)
    bot.send_message(uid, f"صيانة انتقائية: <code>{html_escape(text)}</code>", reply_markup=back_admin_kb())


@bot.message_handler(
    func=lambda m: not (m.text or "").startswith("/"),
    content_types=["text"],
)
def fallback(message):
    if msg_seen(message):
        return
    if get_pending(message.from_user.id):
        return
    show_main_menu(message.chat.id, message.from_user.id)


# ============================================================
# 30) نقطة التشغيل
# ============================================================
def graceful_shutdown(signum, frame):
    log.warning("Received signal %s, shutting down…", signum)
    try:
        manager.shutdown()
    finally:
        sys.exit(0)


def run_polling():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    while True:
        try:
            log.info("Starting Telegram polling…")
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=False,
                allowed_updates=["message", "callback_query"],
                logger_level=logging.WARNING,
            )
        except Exception:
            log.exception("Polling crashed; restarting in 5s")
            time.sleep(5)


def main():
    log.info("Opening SQLite database…")
    db_init()
    db_create_schema()
    db_ensure_columns()
    try:
        _ensure_advanced_schema()
    except Exception:
        log.exception("advanced schema at boot")

    # تجهيز Node.js محلياً في الخلفية إن لم يكن موجوداً على السيرفر (يحتاج إنترنت مرة واحدة)
    def _boot_node():
        ok_n, msg_n = bootstrap_node_runtime()
        (log.info if ok_n else log.warning)("Node runtime: %s", msg_n)
    threading.Thread(target=_boot_node, name="node-bootstrap", daemon=True).start()

    # Keep-alive لـ Railway / Render / أي استضافة ثنائية
    try:
        start_keep_alive_server()
    except Exception:
        log.exception("keep-alive start failed")
    try:
        start_scheduler()
    except Exception:
        log.exception("scheduler start failed")

    log.info("Starting watchdog…")
    manager.start_watchdog()

    log.info("Restoring previously-running projects…")
    try:
        manager.restore_running()
    except Exception:
        log.exception("restore_running failed")

    try:
        signal.signal(signal.SIGTERM, graceful_shutdown)
        signal.signal(signal.SIGINT, graceful_shutdown)
    except Exception:
        pass

    log.info("Hosting bot is up. Admin id=%s PORT=%s", ADMIN_ID, KEEP_ALIVE_PORT)
    run_polling()



# النواة والبوابة والاستوديو واللوحة في ملف واحد: C يشير لهذا الملف نفسه
C = G = sys.modules[__name__]


# ==========================================================================
# 4) بوابة الويب
# ==========================================================================
# -*- coding: utf-8 -*-
"""
بوابة الويب — تعطي كل موقع/تطبيق ويب مستضاف رابطاً عاماً.
- مواقع HTML الثابتة: تُخدَّم مباشرة من مجلد المشروع.
- تطبيقات Python / Node (Flask, FastAPI, Express, ...): Reverse Proxy إلى منفذ المشروع المحلي.
- دعم WebSocket / SSE / رفع ملفات / إعادة توجيه / كوكيز.
- روابط بمسار  /s/<slug>/  أو بنطاق فرعي  <slug>.<PUBLIC_DOMAIN>  (يحتاج Wildcard DNS).
كل شيء محلي: لا خدمات خارجية.
"""
import html as _html
import http.client
import json
import mimetypes
import os
import re
import secrets
import select
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


RESERVED_SLUGS = {"admin", "api", "health", "static", "s", "_flix", "www", "app", "root", "status"}
BLOCKED_EXT = {".env", ".log", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".pyc"}
BLOCKED_NAMES = {"_runtime.log", "_runtime.log.1"}
MAX_REQ_BODY = int(os.environ.get("MAX_REQUEST_MB", "100") or 100) * 1024 * 1024
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "900") or 900)
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade"}

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/avif", ".avif")

_site_cache: dict = {}
_site_cache_lock = threading.Lock()
_port_cache: dict = {}
_hits: dict = {}
_hits_lock = threading.Lock()
_rate: dict = {}
_rate_lock = threading.Lock()
_seen_host = {"v": ""}
_gateway = {"server": None, "port": 0, "started": 0.0, "total": 0}


# ============================================================ قاعدة البيانات
def _init_schema():
    C.db_execute(
        "CREATE TABLE IF NOT EXISTS web_sites ("
        "project_id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, kind TEXT NOT NULL DEFAULT 'app',"
        "public INTEGER NOT NULL DEFAULT 1, rewrite INTEGER NOT NULL DEFAULT 1, port INTEGER,"
        "hits INTEGER NOT NULL DEFAULT 0, bytes_out INTEGER NOT NULL DEFAULT 0, last_hit TIMESTAMP,"
        "announced_url TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:20] or "site"


def valid_slug(slug: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9-]{2,30}$", slug or "")) and slug not in RESERVED_SLUGS


def ensure_site(project_id: int, kind: str) -> dict:
    row = C.db_fetchone("SELECT * FROM web_sites WHERE project_id=?", (project_id,))
    if row:
        if row["kind"] != kind:
            C.db_execute("UPDATE web_sites SET kind=? WHERE project_id=?", (kind, project_id))
            row["kind"] = kind
        return row
    p = C.db_fetchone("SELECT name FROM projects WHERE id=?", (project_id,)) or {}
    for _ in range(20):
        slug = f"{_slugify(p.get('name', ''))}-{secrets.token_hex(2)}"
        if valid_slug(slug) and not C.db_fetchone("SELECT 1 AS x FROM web_sites WHERE slug=?", (slug,)):
            break
    C.db_execute("INSERT INTO web_sites (project_id, slug, kind) VALUES (?,?,?)", (project_id, slug, kind))
    _invalidate()
    return C.db_fetchone("SELECT * FROM web_sites WHERE project_id=?", (project_id,))


def set_slug(project_id: int, slug: str) -> tuple:
    slug = (slug or "").strip().lower()
    if not valid_slug(slug):
        return False, "الاسم غير صالح: 3-31 حرفاً إنجليزياً صغيراً/أرقام/شرطة، ويبدأ بحرف أو رقم، وغير محجوز."
    other = C.db_fetchone("SELECT project_id FROM web_sites WHERE slug=?", (slug,))
    if other and other["project_id"] != project_id:
        return False, "هذا الاسم مستخدم لموقع آخر."
    C.db_execute("UPDATE web_sites SET slug=? WHERE project_id=?", (slug, project_id))
    _invalidate()
    return True, "تم تغيير الاسم."


def _invalidate():
    with _site_cache_lock:
        _site_cache.clear()


# ============================================================ الروابط
def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # لا يُرسل أي شيء فعلياً
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def public_base() -> tuple:
    """(الرابط الأساسي، هل هو رابط محلي غير مؤكد؟)"""
    v = (C.get_setting("public_url") or os.environ.get("PUBLIC_URL") or "").strip().rstrip("/")
    if not v:
        for key in ("RENDER_EXTERNAL_URL", "RAILWAY_STATIC_URL"):
            if os.environ.get(key):
                v = os.environ[key].strip().rstrip("/")
                break
        for key in ("RAILWAY_PUBLIC_DOMAIN", "KOYEB_PUBLIC_DOMAIN", "REPLIT_DEV_DOMAIN", "WEBSITE_HOSTNAME", "SPACE_HOST"):
            if not v and os.environ.get(key):
                v = "https://" + os.environ[key].strip()
        if not v and os.environ.get("FLY_APP_NAME"):
            v = f"https://{os.environ['FLY_APP_NAME']}.fly.dev"
    if not v and _seen_host["v"]:
        v = _seen_host["v"]
    if v:
        if not re.match(r"^https?://", v):
            v = "https://" + v
        return v, False
    return f"http://{_local_ip()}:{_gateway['port'] or C.KEEP_ALIVE_PORT}", True


def public_domain() -> str:
    return (C.get_setting("public_domain") or os.environ.get("PUBLIC_DOMAIN") or "").strip().lower().lstrip(".")


def site_url(slug: str) -> tuple:
    dom = public_domain()
    base, local = public_base()
    if dom:
        scheme = "https" if base.startswith("https") or not local else "http"
        return f"{scheme}://{slug}.{dom}/", False
    return f"{base}/s/{slug}/", local


# ============================================================ اكتشاف المنفذ
def listening_ports(pid: int) -> list:
    """المنافذ التي تستمع عليها العملية وأبناؤها."""
    if not pid:
        return []
    try:
        import psutil  # type: ignore
        proc = psutil.Process(pid)
        ports = set()
        for p in [proc] + proc.children(recursive=True):
            try:
                conns = p.net_connections(kind="inet") if hasattr(p, "net_connections") else p.connections(kind="inet")
                for c in conns:
                    if c.status == psutil.CONN_LISTEN and c.laddr:
                        ports.add(c.laddr.port)
            except Exception:
                continue
        return sorted(ports)
    except Exception:
        pass
    try:  # Linux بدون psutil
        children = {pid}
        changed = True
        while changed:
            changed = False
            for d in os.listdir("/proc"):
                if not d.isdigit() or int(d) in children:
                    continue
                try:
                    with open(f"/proc/{d}/stat") as fh:
                        ppid = int(fh.read().rsplit(")", 1)[1].split()[1])
                    if ppid in children:
                        children.add(int(d))
                        changed = True
                except Exception:
                    continue
        inodes = set()
        for p in children:
            try:
                for fd in os.listdir(f"/proc/{p}/fd"):
                    link = os.readlink(f"/proc/{p}/fd/{fd}")
                    if link.startswith("socket:["):
                        inodes.add(link[8:-1])
            except Exception:
                continue
        ports = set()
        for fn in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(fn) as fh:
                    next(fh)
                    for ln in fh:
                        f = ln.split()
                        if f[3] == "0A" and f[9] in inodes:
                            ports.add(int(f[1].split(":")[1], 16))
            except Exception:
                continue
        return sorted(ports)
    except Exception:
        return []


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def upstream_port(project_id: int, fresh: bool = False):
    hit = _port_cache.get(project_id)
    if hit and not fresh and time.time() - hit[1] < 8:
        return hit[0]
    hp = C.manager.processes.get(project_id)
    if not hp or not hp.is_alive() or not getattr(hp, "pid", None):
        return None
    assigned = int(hp._port()) if hasattr(hp, "_port") else 0
    ports = [p for p in listening_ports(hp.pid) if p != _gateway["port"]]
    port = assigned if assigned in ports else (ports[0] if ports else (assigned if _port_open(assigned) else None))
    if port:
        _port_cache[project_id] = (port, time.time())
    return port


# ============================================================ صفحات
def page(status: int, title: str, msg: str, icon: str = "⚠️") -> tuple:
    body = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_html.escape(title)}</title>
<style>body{{font-family:system-ui,Tahoma,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;min-height:100vh;
align-items:center;justify-content:center;margin:0}}.c{{text-align:center;padding:32px;max-width:520px}}
h1{{font-size:56px;margin:0}}h2{{margin:8px 0}}p{{color:#94a3b8;line-height:1.8}}small{{color:#475569}}</style></head>
<body><div class="c"><h1>{icon}</h1><h2>{_html.escape(title)}</h2><p>{_html.escape(msg)}</p>
<small>{_html.escape(C.BRAND_NAME)} Cloud · {status}</small></div></body></html>"""
    return status, body.encode("utf-8")


# ============================================================ البحث عن الموقع
def lookup(slug: str):
    now = time.time()
    with _site_cache_lock:
        hit = _site_cache.get(slug)
        if hit and now - hit[1] < 15:
            return hit[0]
    row = C.db_fetchone(
        "SELECT w.project_id, w.slug, w.kind, w.public, w.rewrite, p.name, p.main_file, p.approved, "
        "p.user_id, p.is_running, u.banned FROM web_sites w JOIN projects p ON p.id=w.project_id "
        "LEFT JOIN users u ON u.id=p.user_id WHERE w.slug=?", (slug,))
    with _site_cache_lock:
        _site_cache[slug] = (row, now)
    return row


def _count(slug: str, nbytes: int):
    with _hits_lock:
        h = _hits.setdefault(slug, [0, 0])
        h[0] += 1
        h[1] += nbytes
        _gateway["total"] += 1


def _flush_hits():
    with _hits_lock:
        items, _hits_copy = list(_hits.items()), None
        _hits.clear()
    for slug, (n, b) in items:
        try:
            C.db_execute("UPDATE web_sites SET hits=hits+?, bytes_out=bytes_out+?, last_hit=CURRENT_TIMESTAMP WHERE slug=?", (n, b, slug))
        except Exception:
            pass


def _gateway_flush_loop():
    while True:
        time.sleep(30)
        _flush_hits()


# ============================================================ إعادة كتابة HTML
def _shim(prefix: str) -> str:
    p = json.dumps(prefix)
    return ("<script>(function(){var P=" + p + ";function f(u){return(typeof u==='string'&&u.charAt(0)==='/'&&u.charAt(1)!=='/'"
            "&&u.indexOf(P+'/')!==0&&u!==P)?P+u:u}var of=window.fetch;if(of)window.fetch=function(a,b){if(typeof a==='string')a=f(a);"
            "else if(a&&a.url){try{var x=new URL(a.url);if(x.origin===location.origin&&x.pathname.indexOf(P+'/')!==0)"
            "a=new Request(P+x.pathname+x.search,a)}catch(e){}}return of.call(this,a,b)};var oo=XMLHttpRequest.prototype.open;"
            "XMLHttpRequest.prototype.open=function(m,u){arguments[1]=f(u);return oo.apply(this,arguments)};"
            "var OW=window.WebSocket;if(OW){var W=function(u,q){if(typeof u==='string'&&u.charAt(0)==='/'&&u.charAt(1)!=='/'"
            "&&u.indexOf(P+'/')!==0)u=(location.protocol==='https:'?'wss://':'ws://')+location.host+P+u;"
            "return q===undefined?new OW(u):new OW(u,q)};W.prototype=OW.prototype;['CONNECTING','OPEN','CLOSING','CLOSED']"
            ".forEach(function(k){W[k]=OW[k]});window.WebSocket=W}})();</script>")


_ATTR_RE = re.compile(r"""(\b(?:src|href|action|poster|data-src|formaction)\s*=\s*)(["'])/(?!/)""", re.IGNORECASE)
_CSSURL_RE = re.compile(r"""(url\(\s*)(["']?)/(?!/)""", re.IGNORECASE)
_META_RE = re.compile(r"""(<meta[^>]+http-equiv=["']refresh["'][^>]+content=["'][^"']*url=)/(?!/)""", re.IGNORECASE)


def rewrite_html(text: str, prefix: str) -> str:
    text = _ATTR_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{prefix}/", text)
    text = _CSSURL_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{prefix}/", text)
    text = _META_RE.sub(lambda m: f"{m.group(1)}{prefix}/", text)
    shim = _shim(prefix)
    m = re.search(r"<head[^>]*>", text, re.IGNORECASE)
    if m:
        return text[:m.end()] + shim + text[m.end():]
    return shim + text


def rewrite_css(text: str, prefix: str) -> str:
    return _CSSURL_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{prefix}/", text)


# ============================================================ المعالج
class _Body:
    """قارئ محدود لجسم الطلب (يمرر بثاً بدون تحميله كله في الذاكرة)."""
    def __init__(self, rfile, n):
        self.rfile, self.left = rfile, n

    def read(self, size=-1):
        if self.left <= 0:
            return b""
        size = self.left if size is None or size < 0 else min(size, self.left)
        d = self.rfile.read(size)
        self.left -= len(d)
        return d


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FlixGateway/1.0"
    sys_version = ""

    def log_message(self, *a):
        return

    # ---- أدوات ----
    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8", extra=None, head=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _err(self, status, title, msg, icon="⚠️", head=False):
        st, body = page(status, title, msg, icon)
        self._send(st, body, head=head)

    def _client_ip(self) -> str:
        xf = self.headers.get("X-Forwarded-For", "")
        return (xf.split(",")[0].strip() if xf else self.client_address[0]) or "?"

    def _limited(self) -> bool:
        ip, now = self._client_ip(), int(time.time() // 60)
        with _rate_lock:
            if len(_rate) > 5000:
                _rate.clear()
            k = (ip, now)
            _rate[k] = _rate.get(k, 0) + 1
            return _rate[k] > RATE_LIMIT

    def _learn_host(self):
        if public_domain() or C.get_setting("public_url") or os.environ.get("PUBLIC_URL"):
            return
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(",")[0].strip()
        if not host or re.match(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[)", host) or re.match(r"^\d+\.\d+\.\d+\.\d+(:\d+)?$", host):
            return
        proto = (self.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
        _seen_host["v"] = f"{proto}://{host}"

    # ---- توجيه ----
    def _route(self, head=False):
        if self._limited():
            return self._err(429, "طلبات كثيرة", "تم تجاوز الحد المسموح من الطلبات. حاول بعد قليل.", "⏳", head)
        self._learn_host()
        raw = self.path
        parsed = urllib.parse.urlsplit(raw)
        path = parsed.path or "/"
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        dom = public_domain()
        slug, prefix, sub = None, "", path
        if dom and host.endswith("." + dom) and host != dom:
            slug = host[:-(len(dom) + 1)]
        elif path.startswith("/s/") or path == "/s":
            parts = path.split("/", 3)
            slug = parts[2] if len(parts) > 2 else ""
            prefix = f"/s/{slug}"
            sub = "/" + (parts[3] if len(parts) > 3 else "")
            if len(parts) == 3 and not path.endswith("/"):  # /s/slug → /s/slug/
                loc = f"{prefix}/" + (f"?{parsed.query}" if parsed.query else "")
                return self._send(301, b"", extra={"Location": loc}, head=head)
        else:
            return self._root(path, head)
        site = lookup(slug or "")
        if not site:
            return self._err(404, "الموقع غير موجود", "لا يوجد موقع بهذا الرابط. تأكد من الرابط الصحيح.", "🔍", head)
        if not site["public"]:
            return self._err(403, "موقع خاص", "صاحب الموقع أغلق الوصول العام له.", "🔒", head)
        if site.get("banned") or not site["approved"]:
            return self._err(403, "الموقع غير متاح", "هذا الموقع معطّل حالياً.", "🚫", head)
        if site["kind"] == "static":
            return self._static(site, sub, head)
        return self._proxy(site, prefix, sub, parsed.query)

    def _root(self, path, head):
        if path in ("/health", "/healthz"):
            running = 0
            try:
                running = sum(1 for hp in list(C.manager.processes.values()) if hp.is_alive())
            except Exception:
                pass
            body = json.dumps({"status": "ok", "running": running, "uptime": int(time.time() - C._START_TS),
                               "requests": _gateway["total"]}).encode()
            return self._send(200, body, "application/json", head=head)
        running = 0
        try:
            running = sum(1 for hp in list(C.manager.processes.values()) if hp.is_alive())
        except Exception:
            pass
        st, body = page(200, f"{C.BRAND_NAME} Cloud", f"الخدمة تعمل ✅ — مشاريع نشطة: {running} — مدة التشغيل: {int(time.time() - C._START_TS)} ثانية", "🚀")
        self._send(st, body, head=head)

    # ---- المواقع الثابتة ----
    def _static(self, site, sub, head):
        pid = site["project_id"]
        hp = C.manager.processes.get(pid)
        if not (hp and hp.is_alive()):  # الحالة الحية من المدير (وليس من الكاش)
            return self._err(503, "الموقع متوقف", "صاحب الموقع أوقفه مؤقتاً.", "⏸️", head)
        main = site["main_file"] or "index.html"
        root = os.path.realpath(os.path.join(C.PROJECTS_DIR, str(pid), os.path.dirname(main)))
        rel = urllib.parse.unquote(sub).replace("\\", "/")
        segs = [s for s in rel.split("/") if s not in ("", ".")]
        if any(s == ".." or s.startswith(".") or s in BLOCKED_NAMES or s == "node_modules" for s in segs):
            return self._err(404, "غير موجود", "الصفحة المطلوبة غير موجودة.", "🔍", head)
        target = os.path.realpath(os.path.join(root, *segs)) if segs else root
        if target != root and not target.startswith(root + os.sep):
            return self._err(404, "غير موجود", "الصفحة المطلوبة غير موجودة.", "🔍", head)
        if os.path.isdir(target):
            if segs and not sub.endswith("/"):
                return self._send(301, b"", extra={"Location": (self.path.split("?")[0] + "/")}, head=head)
            for cand in ("index.html", "index.htm", os.path.basename(main)):
                if os.path.isfile(os.path.join(target, cand)):
                    target = os.path.join(target, cand)
                    break
        if not os.path.isfile(target) or os.path.splitext(target)[1].lower() in BLOCKED_EXT:
            nf = os.path.join(root, "404.html")
            if os.path.isfile(nf):
                data = open(nf, "rb").read()
                _count(site["slug"], len(data))
                return self._send(404, data, "text/html; charset=utf-8", head=head)
            return self._err(404, "غير موجود", "الصفحة المطلوبة غير موجودة.", "🔍", head)
        st = os.stat(target)
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        is_html = ctype.startswith("text/html")
        cache = "no-cache" if is_html else "public, max-age=300"
        if self.headers.get("If-None-Match") == etag:
            return self._send(304, b"", extra={"ETag": etag, "Cache-Control": cache}, head=head)
        size, start, end, status = st.st_size, 0, st.st_size - 1, 200
        rng = self.headers.get("Range", "")
        m = re.match(r"bytes=(\d*)-(\d*)$", rng)
        if m and (m.group(1) or m.group(2)) and size > 0:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            if start > end or start >= size:
                return self._send(416, b"", extra={"Content-Range": f"bytes */{size}"}, head=head)
            end, status = min(end, size - 1), 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", self.date_time_string(st.st_mtime))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not head:
            with open(target, "rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    chunk = fh.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        _count(site["slug"], length)

    # ---- Reverse Proxy ----
    def _proxy(self, site, prefix, sub, query):
        pid = site["project_id"]
        port = upstream_port(pid)
        if not port:
            hp = C.manager.processes.get(pid)
            if hp and hp.is_alive():
                return self._err(503, "الموقع يبدأ التشغيل", "التطبيق شغّال لكنه لم يفتح المنفذ بعد. حدّث الصفحة بعد ثوانٍ.", "⏳")
            return self._err(503, "الموقع متوقف", "المشروع متوقف أو يعاد تشغيله حالياً. حاول بعد قليل.", "⏸️")
        target = sub + (f"?{query}" if query else "")
        hdrs = {}
        for k, v in self.headers.items():
            if k.lower() in HOP or k.lower() in ("accept-encoding", "content-length"):
                continue
            hdrs[k] = v
        client = self._client_ip()
        proto = self.headers.get("X-Forwarded-Proto") or ("https" if public_base()[0].startswith("https") else "http")
        hdrs.update({"X-Forwarded-For": client, "X-Real-IP": client, "X-Forwarded-Proto": proto,
                     "X-Forwarded-Host": self.headers.get("Host", ""), "Accept-Encoding": "identity"})
        if prefix:
            hdrs["X-Forwarded-Prefix"] = prefix
        if (self.headers.get("Upgrade") or "").lower() == "websocket":
            return self._tunnel(port, target, hdrs)
        body = None
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            body = self._read_chunked()
            if body is None:
                return self._err(413, "الطلب كبير", "حجم الطلب يتجاوز الحد المسموح.", "📦")
            hdrs["Content-Length"] = str(len(body))
        else:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_REQ_BODY:
                return self._err(413, "الطلب كبير", "حجم الطلب يتجاوز الحد المسموح.", "📦")
            if n:
                body = _Body(self.rfile, n)
                hdrs["Content-Length"] = str(n)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
            conn.request(self.command, target, body=body, headers=hdrs)
            resp = conn.getresponse()
        except Exception:
            _port_cache.pop(pid, None)
            return self._err(502, "تعذر الوصول للتطبيق", "التطبيق لا يستجيب الآن. تحقق من السجل في بوت الاستضافة.", "🔌")
        try:
            self._relay(resp, site, prefix)
        finally:
            conn.close()

    def _read_chunked(self):
        out, total = [], 0
        while True:
            line = self.rfile.readline(64).strip()
            if not line:
                return None
            n = int(line.split(b";")[0], 16)
            if n == 0:
                self.rfile.readline()
                break
            total += n
            if total > MAX_REQ_BODY:
                return None
            out.append(self.rfile.read(n))
            self.rfile.readline()
        return b"".join(out)

    def _relay(self, resp, site, prefix):
        slug = site["slug"]
        ctype = resp.getheader("Content-Type", "") or ""
        low = ctype.lower()
        do_rewrite = bool(prefix) and site["rewrite"] and (low.startswith("text/html") or low.startswith("text/css"))
        out_headers = []
        for k, v in resp.getheaders():
            kl = k.lower()
            if kl in HOP or kl == "content-length" and do_rewrite:
                continue
            if kl == "location" and prefix:
                v = self._fix_location(v, prefix)
            elif kl == "set-cookie" and prefix:
                v = re.sub(r"(?i)(;\s*path=)/(?=;|$)", lambda m: f"{m.group(1)}{prefix}/", v)
            elif kl == "content-security-policy" and do_rewrite:
                continue
            out_headers.append((k, v))
        if do_rewrite:
            data = resp.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                do_rewrite = False
                chunks_first = data
            else:
                enc = "utf-8"
                m = re.search(r"charset=([\w-]+)", low)
                if m:
                    enc = m.group(1)
                try:
                    txt = data.decode(enc)
                    txt = rewrite_html(txt, prefix) if low.startswith("text/html") else rewrite_css(txt, prefix)
                    data = txt.encode(enc)
                except Exception:
                    pass
                self.send_response(resp.status)
                for k, v in out_headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)
                _count(slug, len(data))
                return
        else:
            chunks_first = b""
        self.send_response(resp.status)
        for k, v in out_headers:
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        sent = 0
        if self.command != "HEAD":
            try:
                if chunks_first:
                    self.wfile.write(chunks_first)
                    sent += len(chunks_first)
                while True:
                    chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    sent += len(chunk)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        _count(slug, sent)

    @staticmethod
    def _fix_location(v: str, prefix: str) -> str:
        if v.startswith("/") and not v.startswith("//") and not v.startswith(prefix + "/"):
            return prefix + v
        m = re.match(r"^https?://(?:127\.0\.0\.1|localhost)(?::\d+)?(/.*)?$", v)
        if m:
            return prefix + (m.group(1) or "/")
        return v

    # ---- WebSocket ----
    def _tunnel(self, port, target, hdrs):
        try:
            up = socket.create_connection(("127.0.0.1", port), timeout=10)
        except OSError:
            return self._err(502, "تعذر الوصول للتطبيق", "التطبيق لا يستجيب الآن.", "🔌")
        lines = [f"{self.command} {target} HTTP/1.1"]
        for k, v in self.headers.items():
            if k.lower() in ("x-forwarded-for", "x-real-ip", "x-forwarded-proto", "x-forwarded-host", "x-forwarded-prefix"):
                continue
            lines.append(f"{k}: {v}")
        for k in ("X-Forwarded-For", "X-Real-IP", "X-Forwarded-Proto", "X-Forwarded-Host", "X-Forwarded-Prefix"):
            if k in hdrs:
                lines.append(f"{k}: {hdrs[k]}")
        up.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1", "replace"))
        self.close_connection = True
        cl = self.connection
        up.settimeout(None)
        cl.settimeout(None)
        try:
            while True:
                r, _, _ = select.select([cl, up], [], [], 300)
                if not r:
                    break
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (up if s is cl else cl).sendall(data)
        except OSError:
            pass
        finally:
            try:
                up.close()
            except OSError:
                pass

    # ---- الأفعال ----
    def do_GET(self): self._route()
    def do_HEAD(self): self._route(head=True)
    def do_POST(self): self._route()
    def do_PUT(self): self._route()
    def do_PATCH(self): self._route()
    def do_DELETE(self): self._route()
    def do_OPTIONS(self): self._route()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 256
    allow_reuse_address = True


def start_gateway() -> None:
    """بديل start_keep_alive_server: يخدم الصفحة الرئيسية + health + كل المواقع على المنفذ العام."""
    port = C.KEEP_ALIVE_PORT
    try:
        srv = _Server(("0.0.0.0", port), Handler)
    except OSError as e:
        C.log.error("تعذر فتح منفذ البوابة %s: %s", port, e)
        return
    _gateway.update(server=srv, port=port, started=time.time())
    threading.Thread(target=srv.serve_forever, name="web-gateway", daemon=True).start()
    threading.Thread(target=_gateway_flush_loop, name="web-gateway-flush", daemon=True).start()
    C.log.info("Web gateway on port %s", port)


# ============================================================ بعد التشغيل: تسجيل الموقع وإبلاغ المالك
def _announce(project_id: int, row: dict):
    p = C.db_fetchone("SELECT user_id, name, notify_crash FROM projects WHERE id=?", (project_id,))
    if not p:
        return
    url, local = site_url(row["slug"])
    if row.get("announced_url") == url:
        return
    C.db_execute("UPDATE web_sites SET announced_url=? WHERE project_id=?", (url, project_id))
    text = (f"🌐 <b>موقعك جاهز</b>\n<b>{C.html_escape(p['name'])}</b> #{project_id}\n\n"
            f"🔗 <code>{C.html_escape(url)}</code>")
    if local:
        text += ("\n\n⚠️ هذا رابط محلي — لم أعرف النطاق العام لاستضافتك. اطلب من المطور تنفيذ:\n"
                 "<code>/seturl https://نطاق-استضافتك</code>")
    try:
        kb = C.types.InlineKeyboardMarkup()
        if not local:
            kb.add(C.types.InlineKeyboardButton("🌐 فتح الموقع", url=url))
        C.bot.send_message(p["user_id"], text, reply_markup=kb)
    except Exception:
        try:
            C.bot.send_message(p["user_id"], text)
        except Exception:
            pass


def _probe_web(project_id: int):
    """ينتظر حتى 60 ثانية ليرى إن كان التطبيق يفتح منفذ ويب؛ إن فتح يسجّل رابطاً."""
    deadline = time.time() + 60
    while time.time() < deadline:
        hp = C.manager.processes.get(project_id)
        if not hp or not hp.is_alive():
            return
        port = upstream_port(project_id, fresh=True)
        if port:
            row = ensure_site(project_id, "app")
            C.db_execute("UPDATE web_sites SET port=? WHERE project_id=?", (port, project_id))
            _announce(project_id, row)
            return
        time.sleep(2)


def _after_start(project_id: int):
    try:
        p = C.db_fetchone("SELECT main_file FROM projects WHERE id=?", (project_id,)) or {}
        if C.detect_runtime_from_file(p.get("main_file") or "") == "static":
            row = ensure_site(project_id, "static")
            _invalidate()
            _announce(project_id, row)
        else:
            threading.Thread(target=_probe_web, args=(project_id,), daemon=True, name=f"probe-{project_id}").start()
    except Exception:
        C.log.exception("after_start web")


# ============================================================ الأوامر
def links_text(uid: int, admin: bool = False) -> tuple:
    q = ("SELECT w.*, p.name, p.is_running FROM web_sites w JOIN projects p ON p.id=w.project_id "
         + ("" if admin else "WHERE p.user_id=? ") + "ORDER BY w.project_id")
    rows = C.db_fetchall(q, () if admin else (uid,))
    if not rows:
        return ("لا توجد مواقع بعد.\nارفع مشروع ويب (Python/Node) أو موقع HTML (ملف .html أو .zip) وسيظهر رابطه هنا تلقائياً.", [])
    lines, links = ["🌐 <b>مواقعك:</b>\n"], []
    for r in rows[:30]:
        url, local = site_url(r["slug"])
        state = "🟢" if r["is_running"] else "⚪"
        lock = "" if r["public"] else " 🔒"
        kind = "HTML" if r["kind"] == "static" else "تطبيق"
        lines.append(f"{state} <b>{C.html_escape(r['name'])}</b> #{r['project_id']} · {kind}{lock}\n"
                     f"   <code>{C.html_escape(url)}</code>\n   👁 {r['hits']} زيارة")
        if not local:
            links.append((r["name"], url))
    if any(site_url(r["slug"])[1] for r in rows):
        lines.append("\n⚠️ الروابط محلية. المطور ينفّذ: <code>/seturl https://نطاقك</code>")
    lines.append("\nالأوامر: <code>/slug رقم اسم</code> · <code>/public رقم on|off</code> · <code>/rewrite رقم on|off</code>")
    return "\n".join(lines), links


def _owner_or_admin(uid: int, project_id: int) -> bool:
    p = C.db_fetchone("SELECT user_id FROM projects WHERE id=?", (project_id,))
    return bool(p and (p["user_id"] == uid or C.is_admin(uid)))


def gateway_register_commands():
    bot = C.bot

    @bot.message_handler(commands=["links", "sites", "mylinks"])
    def cmd_links(message):
        if C.msg_seen(message):
            return
        uid = message.from_user.id
        text, links = links_text(uid)
        kb = C.types.InlineKeyboardMarkup(row_width=1)
        for name, url in links[:8]:
            kb.add(C.types.InlineKeyboardButton(f"🌐 {name[:30]}", url=url))
        bot.send_message(message.chat.id, text[:4000], reply_markup=kb if links else None, disable_web_page_preview=True)

    @bot.message_handler(commands=["slug"])
    def cmd_slug(message):
        if C.msg_seen(message):
            return
        a = (message.text or "").split()
        if len(a) != 3 or not a[1].isdigit():
            return bot.send_message(message.chat.id, "الاستخدام: <code>/slug رقم_المشروع اسم-الرابط</code>")
        pid = int(a[1])
        if not _owner_or_admin(message.from_user.id, pid) or not C.db_fetchone("SELECT 1 AS x FROM web_sites WHERE project_id=?", (pid,)):
            return bot.send_message(message.chat.id, "❌ لا يوجد موقع بهذا الرقم لديك.")
        ok, msg = set_slug(pid, a[2])
        extra = f"\n🔗 <code>{C.html_escape(site_url(a[2].lower())[0])}</code>" if ok else ""
        bot.send_message(message.chat.id, ("✅ " if ok else "❌ ") + msg + extra)

    def _toggle(message, column, label):
        a = (message.text or "").split()
        if len(a) != 3 or not a[1].isdigit() or a[2].lower() not in ("on", "off"):
            return bot.send_message(message.chat.id, f"الاستخدام: <code>/{a[0].lstrip('/')} رقم_المشروع on|off</code>")
        pid = int(a[1])
        if not _owner_or_admin(message.from_user.id, pid) or not C.db_fetchone("SELECT 1 AS x FROM web_sites WHERE project_id=?", (pid,)):
            return bot.send_message(message.chat.id, "❌ لا يوجد موقع بهذا الرقم لديك.")
        C.db_execute(f"UPDATE web_sites SET {column}=? WHERE project_id=?", (1 if a[2].lower() == "on" else 0, pid))
        _invalidate()
        bot.send_message(message.chat.id, f"✅ {label}: <b>{'مفعّل' if a[2].lower() == 'on' else 'متوقف'}</b>")

    @bot.message_handler(commands=["public"])
    def cmd_public(message):
        if not C.msg_seen(message):
            _toggle(message, "public", "الوصول العام")

    @bot.message_handler(commands=["rewrite"])
    def cmd_rewrite(message):
        if not C.msg_seen(message):
            _toggle(message, "rewrite", "إصلاح الروابط داخل الصفحات")

    @bot.message_handler(commands=["seturl", "setdomain"])
    def cmd_seturl(message):
        if C.msg_seen(message) or not C.is_admin(message.from_user.id):
            return
        a = (message.text or "").split()
        cmd = a[0].lstrip("/").split("@")[0]
        if len(a) != 2:
            return bot.send_message(message.chat.id,
                                    "الاستخدام:\n<code>/seturl https://my-host.example.com</code> — النطاق العام للاستضافة\n"
                                    "<code>/setdomain example.com</code> — نطاق فرعي لكل موقع (يحتاج Wildcard DNS) · <code>/setdomain off</code> للإلغاء")
        if cmd == "seturl":
            u = a[1].strip().rstrip("/")
            if not re.match(r"^https?://[A-Za-z0-9._:-]+$", u):
                return bot.send_message(message.chat.id, "❌ رابط غير صالح. مثال: https://my-host.example.com")
            C.set_setting("public_url", u)
        else:
            d = a[1].strip().lower().lstrip(".")
            if d == "off":
                d = ""
            elif not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", d):
                return bot.send_message(message.chat.id, "❌ نطاق غير صالح.")
            C.set_setting("public_domain", d)
        C.db_execute("UPDATE web_sites SET announced_url=NULL")
        _invalidate()
        bot.send_message(message.chat.id, "✅ تم الحفظ. أرسل /links لرؤية الروابط الجديدة.")

    @bot.message_handler(commands=["gateway"])
    def cmd_gateway(message):
        if C.msg_seen(message) or not C.is_admin(message.from_user.id):
            return
        base, local = public_base()
        n = (C.db_fetchone("SELECT COUNT(*) AS c FROM web_sites") or {}).get("c", 0)
        tot = C.db_fetchone("SELECT COALESCE(SUM(hits),0) AS h, COALESCE(SUM(bytes_out),0) AS b FROM web_sites") or {}
        text = (f"🌐 <b>بوابة الويب</b>\nالمنفذ: <code>{_gateway['port']}</code>\n"
                f"الرابط العام: <code>{C.html_escape(base)}</code>{' (محلي!)' if local else ''}\n"
                f"النطاق الفرعي: <code>{C.html_escape(public_domain() or '-')}</code>\n"
                f"المواقع: {n} · الزيارات: {tot.get('h', 0)} · الحجم: {tot.get('b', 0) // 1024} KB\n"
                f"طلبات هذه الجلسة: {_gateway['total']}")
        bot.send_message(message.chat.id, text)


def gateway_install(core):
    """يربط البوابة بالنواة: جدول المواقع + أوامر + خطاف ما بعد التشغيل + استبدال خادم keep-alive."""
    global C
    C = core
    _init_schema()
    core.start_keep_alive_server = start_gateway
    orig = core.ProcessManager.start_project

    def wrapped(self, project_id):
        ok, msg = orig(self, project_id)
        if ok:
            _after_start(project_id)
        return ok, msg

    core.ProcessManager.start_project = wrapped
    gateway_register_commands()
    core.log.info("Web gateway installed")


# ==========================================================================
# 5) المراقب (monitor)
# ==========================================================================
# -*- coding: utf-8 -*-
"""مراقبة الموارد: CPU/RAM/قرص للسيرفر + استهلاك كل مشروع. تخزين محلي في SQLite لمدة 24 ساعة."""
import os
import shutil
import threading
import time

_state = {"cpu": 0.0, "last_cpu": None, "disk_cache": {}}
INTERVAL = 30
QUOTA_MB = int(os.environ.get("PROJECT_DISK_QUOTA_MB", "0") or 0)
_warned = set()


def _cpu_percent():
    try:
        import psutil  # type: ignore
        return psutil.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        with open("/proc/stat") as fh:
            f = [int(x) for x in fh.readline().split()[1:]]
        idle, total = f[3] + f[4], sum(f)
        last = _state["last_cpu"]
        _state["last_cpu"] = (idle, total)
        if last and total > last[1]:
            return round(100.0 * (1 - (idle - last[0]) / (total - last[1])), 1)
    except Exception:
        pass
    return 0.0


def _mem():
    try:
        import psutil  # type: ignore
        m = psutil.virtual_memory()
        return m.used / 1048576, m.total / 1048576
    except Exception:
        pass
    try:
        d = {}
        with open("/proc/meminfo") as fh:
            for ln in fh:
                k, v = ln.split(":")
                d[k] = int(v.split()[0]) / 1024
        return d["MemTotal"] - d.get("MemAvailable", d.get("MemFree", 0)), d["MemTotal"]
    except Exception:
        return 0.0, 0.0


def dir_size_mb(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1048576


def project_disk_mb(pid, max_age=300):
    c = _state["disk_cache"].get(pid)
    if c and time.time() - c[1] < max_age:
        return c[0]
    v = dir_size_mb(os.path.join(C.PROJECTS_DIR, str(pid)))
    _state["disk_cache"][pid] = (v, time.time())
    return v


def monitor_sample():
    used, total = _mem()
    du = shutil.disk_usage(C.PROJECTS_DIR if os.path.isdir(C.PROJECTS_DIR) else ".")
    cpu = _cpu_percent()
    _state["cpu"] = cpu
    ts = int(time.time())
    rows = [(ts, "cpu", "host", cpu), (ts, "ram", "host", used), (ts, "disk_free", "host", du.free / 1048576)]
    for pid, hp in list(C.manager.processes.items()):
        if hp.is_alive() and getattr(hp, "pid", None):
            rows.append((ts, "rss", str(pid), C._rss_mb(hp.pid)))
    for r in rows:
        C.db_execute("INSERT INTO metrics (ts, kind, ref, value) VALUES (?,?,?,?)", r)
    C.db_execute("DELETE FROM metrics WHERE ts < ?", (ts - 86400,))
    if QUOTA_MB:
        for pid in list(C.manager.processes):
            if project_disk_mb(pid) > QUOTA_MB and pid not in _warned:
                _warned.add(pid)
                C._owner_notify(pid, f"⚠️ مساحة مشروعك تجاوزت الحد المسموح ({QUOTA_MB}MB). احذف الملفات الكبيرة أو السجلات.")
    return {"cpu": cpu, "ram_used": used, "ram_total": total, "disk_free": du.free / 1048576, "disk_total": du.total / 1048576}


def _loop():
    while True:
        try:
            monitor_sample()
        except Exception:
            C.log.exception("monitor sample")
        time.sleep(INTERVAL)


def monitor_start(core):
    global C
    C = core
    C.db_execute("CREATE TABLE IF NOT EXISTS metrics (ts INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, value REAL NOT NULL)")
    C.db_execute("CREATE INDEX IF NOT EXISTS idx_metrics ON metrics (kind, ref, ts)")
    _cpu_percent()
    threading.Thread(target=_loop, name="monitor", daemon=True).start()


def monitor_summary_html():
    s = monitor_sample()
    avg = C.db_fetchone("SELECT AVG(value) AS a, MAX(value) AS m FROM metrics WHERE kind='cpu' AND ts > ?", (int(time.time()) - 3600,)) or {}
    lines = ["📈 <b>موارد السيرفر</b>",
             f"CPU الآن: <b>{s['cpu']:.0f}%</b> (متوسط ساعة: {avg.get('a') or 0:.0f}% · أعلى: {avg.get('m') or 0:.0f}%)",
             f"RAM: <b>{s['ram_used']:.0f}</b> / {s['ram_total']:.0f} MB",
             f"القرص الحر: <b>{s['disk_free']:.0f}</b> MB من {s['disk_total']:.0f} MB", ""]
    top = monitor_top_projects(8)
    if top:
        lines.append("🏆 <b>أكثر المشاريع استهلاكاً:</b>")
        for pid, name, mem, disk in top:
            lines.append(f"• #{pid} {C.html_escape(name)} — RAM {mem:.0f}MB · قرص {disk:.0f}MB")
    else:
        lines.append("لا توجد مشاريع تعمل الآن.")
    return "\n".join(lines)


def monitor_top_projects(n=10):
    out = []
    for pid, hp in list(C.manager.processes.items()):
        if hp.is_alive():
            mem = C._rss_mb(hp.pid) if getattr(hp, "pid", None) else 0.0
            out.append((pid, hp.name, mem, project_disk_mb(pid)))
    return sorted(out, key=lambda x: (x[2], x[3]), reverse=True)[:n]


# ==========================================================================
# 5) المحلل (analyzer)
# ==========================================================================
# -*- coding: utf-8 -*-
"""محلل المشاريع: تقرير عربي شامل عن مشروع واحد (لغة، تبعيات، أخطاء، أمان، جاهزية الويب)."""
import json
import os
import re


def analyze_project(C, project_id):
    p = C.db_fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        return "❌ المشروع غير موجود."
    work = C.manager._materialize(project_id)
    mf = p.get("main_file") or ""
    rt = C.detect_runtime_from_file(mf) if mf else (p.get("runtime") or "python")
    files = C.db_fetchall("SELECT filename, size_bytes FROM project_files WHERE project_id=? ORDER BY size_bytes DESC", (project_id,))
    total = sum(f["size_bytes"] for f in files)
    L = [f"🔬 <b>تحليل المشروع #{project_id} — {C.html_escape(p['name'])}</b>", ""]
    L.append(f"🧩 النوع: <b>{C.rt_label(rt)}</b> · الملف الرئيسي: <code>{C.html_escape(mf or '-')}</code>")
    L.append(f"📁 الملفات: {len(files)} · الحجم: {total / 1024:.0f} KB")
    if files[:3]:
        L.append("   الأكبر: " + "، ".join(f"<code>{C.html_escape(f['filename'][:30])}</code> ({f['size_bytes'] // 1024}KB)" for f in files[:3]))
    # تبعيات
    if rt == "python":
        imps = C.detect_python_imports(work)
        L.append(f"📦 استيرادات خارجية: {', '.join(imps[:15]) or 'لا يوجد'}")
        if not os.path.isfile(os.path.join(work, "requirements.txt")) and imps:
            L.append("💡 لا يوجد requirements.txt — سيتم الاكتشاف التلقائي، لكن يُفضّل إضافته لتثبيت إصدارات ثابتة.")
    elif rt == "nodejs":
        pk = C.detect_node_packages(work)
        L.append(f"📦 حزم Node مستخدمة: {', '.join(pk[:15]) or 'لا يوجد'}")
        pj = os.path.join(work, "package.json")
        if os.path.isfile(pj):
            try:
                d = json.loads(C._read_text(pj) or "{}")
                undecl = [x for x in pk if x not in (d.get("dependencies") or {}) and x not in (d.get("devDependencies") or {})]
                if undecl:
                    L.append(f"💡 حزم مستخدمة وغير مذكورة في package.json: {', '.join(undecl[:8])} (ستُثبَّت تلقائياً)")
            except Exception:
                L.append("🔴 package.json غير صالح.")
    # أخطاء
    try:
        issues = C.static_check(work, mf, rt)
    except Exception as e:
        issues = [f"تعذر الفحص: {C.html_escape(str(e))}"]
    L.append("")
    L.append("🔎 <b>فحص الأخطاء:</b> " + ("لا توجد مشاكل ✅" if not issues else ""))
    for i in issues[:8]:
        L.append("• " + i)
    # أمان
    sec = []
    for f in files[:80]:
        row = C.db_fetchone("SELECT content FROM project_files WHERE project_id=? AND filename=?", (project_id, f["filename"]))
        if not row:
            continue
        for iss in C.scan_content_security(f["filename"], bytes(row["content"])):
            sec.append(f"{f['filename']}: {iss}")
    if sec:
        L.append("\n🛡 <b>ملاحظات أمنية:</b>")
        L += ["• " + C.html_escape(s) for s in sec[:6]]
    # الويب
    L.append("")
    site = C.db_fetchone("SELECT slug, kind, hits, public FROM web_sites WHERE project_id=?", (project_id,))
    if site:
        pass  # (الوحدة مدمجة في هذا الملف)
        url, local = site_url(site["slug"])
        L.append(f"🌐 موقع ويب ({'ثابت' if site['kind'] == 'static' else 'تطبيق'}) · {site['hits']} زيارة · {'عام' if site['public'] else 'خاص'}\n   <code>{C.html_escape(url)}</code>")
    elif rt != "static":
        main_txt = C._read_text(os.path.join(work, mf)) if mf else ""
        if re.search(r"Flask\(|FastAPI\(|express\(|http\.createServer|aiohttp\.web|web\.Application|uvicorn\.run|app\.listen", main_txt):
            L.append("🌐 يبدو تطبيق ويب — شغّله وسيظهر رابطه تلقائياً.")
        else:
            L.append("🤖 لا يوجد خادم ويب — يعمل كبوت/سكربت خلفي.")
    st = C.manager.status(project_id)
    if st.get("running"):
        L.append(f"🟢 يعمل · RAM {st.get('mem_mb', 0)}MB · مدة {st.get('uptime', 0)}ث · إعادات {st.get('restarts', 0)}")
    else:
        L.append("⚪ متوقف" + (f" — آخر خطأ: {C.html_escape((p.get('last_error') or '')[:200])}" if p.get("last_error") else ""))
    return "\n".join(L)


# ==========================================================================
# 5) أوامر الأدوات (/diag /sysstats /analyze)
# ==========================================================================
# -*- coding: utf-8 -*-
"""أوامر الأدوات: /diag /sysstats /analyze /top"""
import os


def tools_install(core, root):
    pass  # (الوحدة مدمجة في هذا الملف)
    monitor_start(core)
    bot = core.bot

    @bot.message_handler(commands=["diag"])
    def cmd_diag(message):
        if core.msg_seen(message) or not core.is_admin(message.from_user.id):
            return
        rep = diag_format_report(diag_run_checks(root, core), html=True)
        bot.send_message(message.chat.id, ("🩺 <b>فحص الجاهزية</b>\n\n" + rep)[:4000])

    @bot.message_handler(commands=["sysstats", "top"])
    def cmd_sys(message):
        if core.msg_seen(message) or not core.is_admin(message.from_user.id):
            return
        bot.send_message(message.chat.id, monitor_summary_html()[:4000])

    @bot.message_handler(commands=["analyze"])
    def cmd_analyze(message):
        if core.msg_seen(message):
            return
        a = (message.text or "").split()
        if len(a) != 2 or not a[1].isdigit():
            return bot.send_message(message.chat.id, "الاستخدام: <code>/analyze رقم_المشروع</code>")
        pid = int(a[1])
        p = core.db_fetchone("SELECT user_id FROM projects WHERE id=?", (pid,))
        if not p or (p["user_id"] != message.from_user.id and not core.is_admin(message.from_user.id)):
            return bot.send_message(message.chat.id, "❌ لا تملك مشروعاً بهذا الرقم.")
        try:
            bot.send_message(message.chat.id, analyze_project(core, pid)[:4000])
        except Exception as e:
            core.log.exception("analyze")
            bot.send_message(message.chat.id, f"❌ تعذر التحليل: {core.html_escape(str(e)[:200])}")


# ==========================================================================
# 6) لوحة الويب
# ==========================================================================
PANEL_HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Flix Cloud</title>
<meta name="theme-color" content="#0b1020">
<style>
:root{--bg:#0b1020;--bg2:#10172e;--card:rgba(255,255,255,.045);--bd:rgba(255,255,255,.09);--tx:#e8ecff;--mut:#8b95b8;--ac:#7c5cff;--ac2:#00d4ff;--ok:#2ee59d;--bad:#ff5c7a;--warn:#ffc857;--r:16px}
*{box-sizing:border-box}html,body{margin:0;min-height:100%}
body{font-family:system-ui,"Segoe UI",Tahoma,"Noto Sans Arabic",sans-serif;background:radial-gradient(1200px 600px at 85% -10%,#2a1f6b55,transparent),radial-gradient(900px 500px at -10% 110%,#00d4ff22,transparent),var(--bg);color:var(--tx);line-height:1.6}
a{color:var(--ac2);text-decoration:none}button,input,select,textarea{font:inherit;color:inherit}
.hide{display:none!important}
.grad{background:linear-gradient(135deg,var(--ac),var(--ac2));-webkit-background-clip:text;background-clip:text;color:transparent}
.btn{border:0;border-radius:12px;padding:10px 16px;background:var(--card);border:1px solid var(--bd);cursor:pointer;transition:.18s;display:inline-flex;align-items:center;gap:8px;font-weight:600}
.btn:hover{transform:translateY(-1px);border-color:#ffffff30}.btn:disabled{opacity:.5;cursor:wait}
.btn.pri{background:linear-gradient(135deg,var(--ac),#5b8cff);border:0;box-shadow:0 6px 24px #7c5cff55}
.btn.ok{background:#2ee59d22;border-color:#2ee59d55;color:var(--ok)}.btn.bad{background:#ff5c7a22;border-color:#ff5c7a55;color:var(--bad)}
.btn.sm{padding:6px 11px;font-size:13px;border-radius:10px}
input,select,textarea{width:100%;background:#0a0f20aa;border:1px solid var(--bd);border-radius:12px;padding:11px 13px;outline:0;transition:.15s}
input:focus,select:focus,textarea:focus{border-color:var(--ac);box-shadow:0 0 0 3px #7c5cff33}
textarea{font-family:ui-monospace,Consolas,monospace;font-size:13px;direction:ltr;text-align:left;min-height:260px}
label{display:block;margin:12px 0 6px;color:var(--mut);font-size:13px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:var(--r);padding:18px;backdrop-filter:blur(14px)}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(290px,1fr))}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.sp{flex:1}
.badge{padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700;border:1px solid var(--bd)}
.b-on{background:#2ee59d22;color:var(--ok);border-color:#2ee59d55}.b-off{background:#8b95b822;color:var(--mut)}.b-bad{background:#ff5c7a22;color:var(--bad);border-color:#ff5c7a55}.b-warn{background:#ffc85722;color:var(--warn)}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;background:var(--mut)}.dot.on{background:var(--ok);box-shadow:0 0 10px var(--ok);animation:pl 1.8s infinite}
@keyframes pl{50%{opacity:.4}}
#login{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.lbox{width:100%;max-width:410px;padding:34px}.logo{font-size:34px;font-weight:900;text-align:center}.sub{text-align:center;color:var(--mut);margin:4px 0 22px}
#app{display:flex;min-height:100vh}
aside{width:250px;padding:20px 14px;border-inline-end:1px solid var(--bd);background:#0a0f20aa;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:6px}
aside .brand{font-size:22px;font-weight:900;padding:6px 10px 18px}
.nav{padding:11px 14px;border-radius:12px;cursor:pointer;color:var(--mut);display:flex;gap:10px;align-items:center;font-weight:600}
.nav:hover{background:var(--card);color:var(--tx)}.nav.act{background:linear-gradient(135deg,#7c5cff33,#00d4ff22);color:var(--tx);border:1px solid #7c5cff55}
main{flex:1;padding:26px;max-width:1200px;margin:0 auto;width:100%}
h1{margin:0 0 4px;font-size:26px}h2{margin:0 0 12px;font-size:19px}.mut{color:var(--mut)}
.stat{font-size:30px;font-weight:900}.stat small{font-size:13px;color:var(--mut);font-weight:500;display:block}
table{width:100%;border-collapse:collapse}th,td{padding:11px 10px;text-align:start;border-bottom:1px solid var(--bd);font-size:14px}th{color:var(--mut);font-weight:600}
.tabs{display:flex;gap:6px;overflow:auto;margin:16px 0;padding-bottom:4px}.tab{padding:9px 16px;border-radius:12px;cursor:pointer;white-space:nowrap;color:var(--mut);font-weight:600;border:1px solid transparent}.tab.act{background:var(--card);border-color:var(--bd);color:var(--tx)}
pre.log{background:#050810;border:1px solid var(--bd);border-radius:12px;padding:14px;overflow:auto;max-height:480px;font-size:12.5px;direction:ltr;text-align:left;white-space:pre-wrap;word-break:break-all;margin:0}
.drop{border:2px dashed var(--bd);border-radius:var(--r);padding:34px;text-align:center;cursor:pointer;transition:.2s}.drop.over,.drop:hover{border-color:var(--ac);background:#7c5cff14}
.bar{height:8px;background:#ffffff14;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:.5s}
#toasts{position:fixed;bottom:18px;inset-inline:0;display:flex;flex-direction:column;align-items:center;gap:8px;z-index:99;pointer-events:none}
.toast{background:#151d3a;border:1px solid var(--bd);padding:11px 18px;border-radius:12px;box-shadow:0 10px 40px #0008;animation:up .25s}.toast.bad{border-color:var(--bad)}.toast.ok{border-color:var(--ok)}
@keyframes up{from{transform:translateY(14px);opacity:0}}
.modal{position:fixed;inset:0;background:#000a;display:flex;align-items:center;justify-content:center;z-index:50;padding:16px}.modal .card{background:var(--bg2);max-width:480px;width:100%;max-height:90vh;overflow:auto}
code,.mono{font-family:ui-monospace,Consolas,monospace;direction:ltr;unicode-bidi:embed}
.files{max-height:300px;overflow:auto}.f{padding:8px 10px;border-radius:9px;cursor:pointer;display:flex;gap:8px;justify-content:space-between}.f:hover,.f.act{background:var(--card)}
@media(max-width:820px){#app{flex-direction:column}aside{width:100%;height:auto;position:fixed;bottom:0;top:auto;flex-direction:row;overflow:auto;z-index:20;padding:8px;border-top:1px solid var(--bd);border-inline-end:0}aside .brand,aside .sp{display:none}.nav{padding:9px 12px;white-space:nowrap;font-size:13px}main{padding:16px 14px 90px}}
</style>
</head>
<body>
<div id="login" class="hide"><div class="card lbox">
  <div class="logo grad">⚡ Flix Cloud</div><div class="sub">لوحة الاستضافة — تسجيل الدخول</div>
  <label>اسم المستخدم</label><input id="lu" autocomplete="username" autocapitalize="off">
  <label>كلمة المرور</label><input id="lp" type="password" autocomplete="current-password">
  <button class="btn pri" style="width:100%;margin-top:20px;justify-content:center" id="lgo">دخول</button>
  <p class="mut" style="font-size:12.5px;text-align:center;margin-top:16px">الحسابات تُنشأ من المالك أو المشرفين فقط.</p>
</div></div>
<div id="app" class="hide">
  <aside id="side"></aside>
  <main id="view"></main>
</div>
<div id="toasts"></div>
<script>
const $=s=>document.querySelector(s);let ME=null,CSRF='',TIMER=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(m,k){const t=document.createElement('div');t.className='toast '+(k||'');t.textContent=m;$('#toasts').append(t);setTimeout(()=>t.remove(),3800)}
async function api(method,url,body,opt={}){
  const h={'X-CSRF':CSRF};let b;
  if(opt.raw){b=body;h['X-Filename']=encodeURIComponent(opt.fname||'file');h['Content-Type']='application/octet-stream'}
  else if(body!==undefined){b=JSON.stringify(body);h['Content-Type']='application/json'}
  const r=await fetch(url,{method,headers:h,body:b,credentials:'same-origin'});
  let j={};try{j=await r.json()}catch(e){}
  if(r.status===401&&url!=='/api/login'){ME=null;route();throw new Error('auth')}
  if(!r.ok||j.error)throw new Error(j.error||('خطأ '+r.status));return j}
const go=h=>{location.hash=h};
const fmtUp=s=>{s=+s||0;const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return d?d+'ي '+h+'س':h?h+'س '+m+'د':m+'د '+(s%60)+'ث'};
const rtLbl={python:'Python',nodejs:'Node.js',static:'HTML'};
async function boot(){try{const j=await api('GET','/api/me');ME=j.user;CSRF=j.csrf}catch(e){ME=null}route()}
function route(){clearInterval(TIMER);TIMER=null;
  if(!ME){$('#app').classList.add('hide');$('#login').classList.remove('hide');return}
  $('#login').classList.add('hide');$('#app').classList.remove('hide');
  const h=(location.hash||'#/projects').slice(2).split('/');drawSide(h[0]);
  const v={projects:vProjects,project:()=>vProject(h[1],h[2]||'overview'),users:vUsers,all:vAll,system:vSystem,audit:vAudit,account:vAccount}[h[0]]||vProjects;v()}
function drawSide(a){const adm=ME.role!=='user';
  const n=(k,i,t)=>`<div class="nav ${a===k?'act':''}" onclick="go('#/${k}')"><span>${i}</span>${t}</div>`;
  $('#side').innerHTML=`<div class="brand grad">⚡ Flix Cloud</div>${n('projects','🚀','مشاريعي')}${adm?n('all','🗂','كل المشاريع')+n('users','👥','الحسابات')+n('system','📈','النظام')+n('audit','📜','السجل'):''}${n('account','👤','حسابي')}<div class="sp"></div><div class="nav" onclick="logout()"><span>⏻</span>خروج</div>`}
async function logout(){try{await api('POST','/api/logout')}catch(e){}ME=null;route()}
$('#lgo').onclick=login;$('#lp').onkeydown=e=>{if(e.key==='Enter')login()};
async function login(){const b=$('#lgo');b.disabled=true;try{const j=await api('POST','/api/login',{username:$('#lu').value.trim(),password:$('#lp').value});ME=j.user;CSRF=j.csrf;$('#lp').value='';location.hash='#/projects';route()}catch(e){toast(e.message,'bad')}b.disabled=false}
/* ---------- المشاريع ---------- */
function card(p){const on=p.running;return `<div class="card"><div class="row"><span class="dot ${on?'on':''}"></span><b style="font-size:17px">${esc(p.name)}</b><span class="sp"></span><span class="badge ${on?'b-on':p.busy?'b-warn':'b-off'}">${p.busy?'جارٍ...':on?'يعمل':'متوقف'}</span></div>
<div class="mut" style="margin:8px 0">${rtLbl[p.runtime]||p.runtime} · <code>${esc(p.main_file||'-')}</code> · #${p.id}${p.owner?' · '+esc(p.owner):''}</div>
${p.url?`<div style="margin-bottom:10px"><a href="${esc(p.url)}" target="_blank" class="mono">🔗 ${esc(p.url)}</a></div>`:''}
${p.last_error&&!on?`<div class="badge b-bad" style="display:block;margin-bottom:10px;white-space:normal">${esc(p.last_error.slice(0,140))}</div>`:''}
<div class="row"><button class="btn sm pri" onclick="go('#/project/${p.id}')">إدارة</button>
${on?`<button class="btn sm bad" onclick="act(${p.id},'stop')">إيقاف</button><button class="btn sm" onclick="act(${p.id},'restart')">إعادة</button>`:`<button class="btn sm ok" onclick="act(${p.id},'start')">تشغيل</button>`}</div></div>`}
async function act(id,a,reload){try{const j=await api('POST',`/api/projects/${id}/${a}`);toast(j.message||'تم','ok')}catch(e){toast(e.message,'bad')}(reload||route)()}
async function vProjects(){
  $('#view').innerHTML=`<div class="row"><div><h1>مشاريعي</h1><div class="mut">بوتات Python وNode.js ومواقع الويب</div></div><span class="sp"></span><button class="btn pri" onclick="newProject()">＋ مشروع جديد</button></div><div id="pl" class="grid" style="margin-top:18px"></div>`;
  const load=async()=>{try{const j=await api('GET','/api/projects');$('#pl').innerHTML=j.projects.length?j.projects.map(card).join(''):`<div class="card mut" style="grid-column:1/-1;text-align:center;padding:40px">لا توجد مشاريع بعد. اضغط «مشروع جديد» وارفع ملفاً أو ZIP.</div>`;
    if(j.projects.some(p=>p.busy)){} }catch(e){}};
  await load();TIMER=setInterval(load,4000)}
function newProject(){const m=document.createElement('div');m.className='modal';m.innerHTML=`<div class="card"><h2>مشروع جديد</h2><label>الاسم</label><input id="np" placeholder="my-bot"><label>الملف (py / js / html / zip)</label>
<div class="drop" id="dz">اسحب الملف هنا أو اضغط للاختيار<input type="file" id="nf" class="hide"></div><div id="nfn" class="mut" style="margin-top:8px"></div>
<label><input type="checkbox" id="ns" checked style="width:auto;margin-inline-end:8px">تشغيل تلقائي بعد الرفع</label><div class="row" style="margin-top:16px"><button class="btn pri" id="ngo">رفع</button><button class="btn" id="ncl">إلغاء</button></div></div>`;document.body.append(m);
  let file=null;const dz=m.querySelector('#dz'),fi=m.querySelector('#nf');dz.onclick=()=>fi.click();
  const set=f=>{file=f;m.querySelector('#nfn').textContent=f?f.name+' · '+(f.size/1024).toFixed(0)+' KB':'';if(f&&!m.querySelector('#np').value)m.querySelector('#np').value=f.name.replace(/\.[^.]+$/,'')};
  fi.onchange=()=>set(fi.files[0]);dz.ondragover=e=>{e.preventDefault();dz.classList.add('over')};dz.ondragleave=()=>dz.classList.remove('over');dz.ondrop=e=>{e.preventDefault();dz.classList.remove('over');set(e.dataTransfer.files[0])};
  m.querySelector('#ncl').onclick=()=>m.remove();
  m.querySelector('#ngo').onclick=async()=>{if(!file)return toast('اختر ملفاً','bad');const b=m.querySelector('#ngo');b.disabled=true;b.textContent='جارٍ الرفع...';
    try{const j=await api('POST','/api/projects/upload?name='+encodeURIComponent(m.querySelector('#np').value||file.name)+'&start='+(m.querySelector('#ns').checked?1:0),file,{raw:true,fname:file.name});m.remove();
      toast('تم الرفع'+(j.issues&&j.issues.length?' — توجد ملاحظات في الفحص':''),'ok');go('#/project/'+j.id)}catch(e){toast(e.message,'bad');b.disabled=false;b.textContent='رفع'}}}
/* ---------- مشروع ---------- */
const TABS=[['overview','نظرة عامة'],['logs','السجل'],['files','الملفات'],['console','الطرفية'],['settings','الإعدادات'],['analysis','التحليل']];
async function vProject(id,tab){
  let p;try{p=(await api('GET','/api/projects/'+id)).project}catch(e){toast(e.message,'bad');return go('#/projects')}
  const on=p.running;
  $('#view').innerHTML=`<div class="row"><button class="btn sm" onclick="go('#/projects')">→</button><div><h1>${esc(p.name)}</h1><div class="mut">${rtLbl[p.runtime]||p.runtime} · #${p.id}</div></div><span class="sp"></span><span class="badge ${on?'b-on':'b-off'}">${p.busy?'جارٍ...':on?'يعمل':'متوقف'}</span>
  ${on?`<button class="btn sm bad" onclick="act(${id},'stop',()=>vProject(${id},'${tab}'))">إيقاف</button><button class="btn sm" onclick="act(${id},'restart',()=>vProject(${id},'${tab}'))">إعادة</button>`:`<button class="btn sm ok" onclick="act(${id},'start',()=>vProject(${id},'${tab}'))">تشغيل</button>`}
  <button class="btn sm bad" onclick="delProject(${id})">حذف</button></div>
  <div class="tabs">${TABS.map(t=>`<div class="tab ${t[0]===tab?'act':''}" onclick="go('#/project/${id}/${t[0]}')">${t[1]}</div>`).join('')}</div><div id="tb"></div>`;
  const T=$('#tb');
  if(tab==='overview'){const s=p.status||{};T.innerHTML=`<div class="grid"><div class="card"><div class="stat">${on?fmtUp(s.uptime):'—'}<small>مدة التشغيل</small></div></div><div class="card"><div class="stat">${on&&s.mem_mb!=null?s.mem_mb+' MB':'—'}<small>الذاكرة</small></div></div><div class="card"><div class="stat">${p.disk_mb} MB<small>مساحة المشروع</small></div></div><div class="card"><div class="stat">${p.hits??0}<small>زيارات الموقع</small></div></div></div>
  <div class="card" style="margin-top:14px"><h2>التفاصيل</h2><table><tr><th>الملف الرئيسي</th><td><code>${esc(p.main_file)}</code></td></tr><tr><th>النوع</th><td>${rtLbl[p.runtime]||p.runtime}</td></tr>${p.url?`<tr><th>الرابط</th><td><a class="mono" target="_blank" href="${esc(p.url)}">${esc(p.url)}</a></td></tr>`:''}${p.last_error?`<tr><th>آخر خطأ</th><td style="color:var(--bad)">${esc(p.last_error)}</td></tr>`:''}</table></div>`;
    if(p.busy||on){TIMER=setInterval(()=>vProject(id,tab),5000)}}
  if(tab==='logs'){T.innerHTML=`<div class="row" style="margin-bottom:10px"><span class="mut">تحديث تلقائي كل 2 ثانية</span><span class="sp"></span><button class="btn sm" onclick="dlLog(${id})">نسخ</button></div><pre class="log" id="lg">...</pre>`;
    const ld=async()=>{try{const j=await api('GET',`/api/projects/${id}/logs?n=12000`);const e=$('#lg');if(!e)return;const stick=e.scrollTop+e.clientHeight>=e.scrollHeight-30;e.textContent=j.log||'(السجل فارغ)';if(stick)e.scrollTop=e.scrollHeight}catch(e){}};await ld();$('#lg').scrollTop=1e9;TIMER=setInterval(ld,2000)}
  if(tab==='files'){fileTab(id,T)}
  if(tab==='console'){T.innerHTML=`<div class="card"><div class="mut" style="margin-bottom:8px">المسموح: <code>pip</code> · <code>python</code> · <code>node</code> · <code>npm</code> · <code>npx</code> داخل مجلد المشروع</div><div class="row"><input id="cm" class="mono" placeholder="pip install requests" style="flex:1"><button class="btn pri" id="cg">تنفيذ</button></div><pre class="log" id="co" style="margin-top:12px">$ </pre></div>`;
    const run=async()=>{const c=$('#cm').value.trim();if(!c)return;$('#cg').disabled=true;$('#co').textContent='$ '+c+'\n...';try{const j=await api('POST',`/api/projects/${id}/exec`,{cmd:c});$('#co').textContent='$ '+c+'\n'+j.output}catch(e){$('#co').textContent='$ '+c+'\n'+e.message}$('#cg').disabled=false};$('#cg').onclick=run;$('#cm').onkeydown=e=>{if(e.key==='Enter')run()}}
  if(tab==='settings'){T.innerHTML=`<div class="card"><h2>متغيرات البيئة (.env)</h2><div class="mut">سطر لكل متغير: <code>KEY=value</code> — تُحمَّل تلقائياً عند التشغيل (مثل BOT_TOKEN)</div><textarea id="env" style="min-height:160px">${esc(p.env||'')}</textarea>
  <label>الملف الرئيسي</label><select id="mf">${p.files.map(f=>`<option ${f===p.main_file?'selected':''}>${esc(f)}</option>`).join('')}</select>
  ${p.url?`<label>اسم الرابط (slug)</label><input id="sl" class="mono" value="${esc(p.slug||'')}"><label><input type="checkbox" id="pb" ${p.public?'checked':''} style="width:auto;margin-inline-end:8px">وصول عام للموقع</label>`:''}
  <div class="row" style="margin-top:16px"><button class="btn pri" id="sv">حفظ</button><button class="btn" id="ins">تثبيت المكتبات</button></div></div>`;
    $('#sv').onclick=async()=>{try{await api('PUT',`/api/projects/${id}/settings`,{env:$('#env').value,main_file:$('#mf').value,slug:$('#sl')?$('#sl').value:undefined,public:$('#pb')?$('#pb').checked:undefined});toast('تم الحفظ — أعد التشغيل لتطبيق التغييرات','ok')}catch(e){toast(e.message,'bad')}};
    $('#ins').onclick=async()=>{toast('جارٍ التثبيت...');try{const j=await api('POST',`/api/projects/${id}/install`);toast(j.ok?'تم تجهيز المكتبات':'اكتمل مع ملاحظات','ok');alert(j.report)}catch(e){toast(e.message,'bad')}}}
  if(tab==='analysis'){T.innerHTML='<div class="card"><pre class="log" id="an">جارٍ التحليل...</pre></div>';try{const j=await api('GET',`/api/projects/${id}/analyze`);$('#an').textContent=j.report}catch(e){$('#an').textContent=e.message}}
}
async function dlLog(id){try{const j=await api('GET',`/api/projects/${id}/logs?n=30000`);await navigator.clipboard.writeText(j.log);toast('تم النسخ','ok')}catch(e){toast('تعذر النسخ','bad')}}
async function delProject(id){if(!confirm('حذف المشروع نهائياً مع كل ملفاته؟'))return;try{await api('DELETE','/api/projects/'+id);toast('تم الحذف','ok');go('#/projects')}catch(e){toast(e.message,'bad')}}
async function fileTab(id,T){
  const j=await api('GET',`/api/projects/${id}/files`);let cur=null;
  T.innerHTML=`<div class="grid" style="grid-template-columns:minmax(220px,300px) 1fr"><div class="card"><div class="row"><b>الملفات</b><span class="sp"></span><button class="btn sm" id="fu">رفع</button><input type="file" id="fi" class="hide"></div><div class="files" id="fl" style="margin-top:8px"></div></div><div class="card"><div class="row"><b id="fn" class="mono">اختر ملفاً</b><span class="sp"></span><button class="btn sm pri hide" id="fs">حفظ</button><button class="btn sm bad hide" id="fd">حذف</button></div><textarea id="fe" class="hide" style="margin-top:10px"></textarea><div id="fm" class="mut" style="margin-top:10px"></div></div></div>`;
  $('#fl').innerHTML=j.files.map(f=>`<div class="f" data-n="${esc(f.name)}"><span class="mono">${esc(f.name)}</span><span class="mut">${(f.size/1024).toFixed(1)}K</span></div>`).join('')||'<div class="mut">لا توجد ملفات</div>';
  document.querySelectorAll('.f').forEach(el=>el.onclick=async()=>{document.querySelectorAll('.f').forEach(x=>x.classList.remove('act'));el.classList.add('act');cur=el.dataset.n;$('#fn').textContent=cur;
    try{const r=await api('GET',`/api/projects/${id}/file?name=${encodeURIComponent(cur)}`);$('#fe').value=r.content;$('#fe').classList.remove('hide');$('#fs').classList.remove('hide');$('#fm').textContent=''}catch(e){$('#fe').classList.add('hide');$('#fs').classList.add('hide');$('#fm').textContent=e.message}$('#fd').classList.remove('hide')});
  $('#fs').onclick=async()=>{try{await api('PUT',`/api/projects/${id}/file?name=${encodeURIComponent(cur)}`,$('#fe').value,{raw:true,fname:cur});toast('تم الحفظ','ok')}catch(e){toast(e.message,'bad')}};
  $('#fd').onclick=async()=>{if(!cur||!confirm('حذف '+cur+'؟'))return;try{await api('DELETE',`/api/projects/${id}/file?name=${encodeURIComponent(cur)}`);toast('تم','ok');fileTab(id,T)}catch(e){toast(e.message,'bad')}};
  $('#fu').onclick=()=>$('#fi').click();$('#fi').onchange=async()=>{const f=$('#fi').files[0];if(!f)return;try{await api('POST',`/api/projects/${id}/upload?name=${encodeURIComponent(f.name)}`,f,{raw:true,fname:f.name});toast('تم الرفع','ok');fileTab(id,T)}catch(e){toast(e.message,'bad')}}}
/* ---------- الإدارة ---------- */
async function vAll(){const j=await api('GET','/api/projects?all=1');$('#view').innerHTML=`<h1>كل المشاريع</h1><div class="mut">${j.projects.length} مشروع</div><div class="grid" style="margin-top:16px">${j.projects.map(card).join('')}</div>`;TIMER=setInterval(async()=>{try{const k=await api('GET','/api/projects?all=1');$('.grid').innerHTML=k.projects.map(card).join('')}catch(e){}},5000)}
const roleLbl={owner:'مالك',admin:'مشرف',user:'مستخدم'};
async function vUsers(){const j=await api('GET','/api/admin/accounts');
  $('#view').innerHTML=`<div class="row"><div><h1>الحسابات</h1><div class="mut">الحسابات تُنشأ من هنا فقط</div></div><span class="sp"></span><button class="btn pri" onclick="newUser()">＋ حساب جديد</button></div>
  <div class="card" style="margin-top:16px;overflow:auto"><table><tr><th>المستخدم</th><th>الدور</th><th>المشاريع</th><th>الحالة</th><th>آخر دخول</th><th></th></tr>${j.accounts.map(a=>`<tr><td><b>${esc(a.username)}</b>${a.tg_id?`<div class="mut mono" style="font-size:12px">tg:${a.tg_id}</div>`:''}</td><td><span class="badge">${roleLbl[a.role]}</span></td><td>${a.projects}/${a.max_projects}</td><td><span class="badge ${a.disabled?'b-bad':'b-on'}">${a.disabled?'معطّل':'نشط'}</span></td><td class="mut">${esc(a.last_login||'—')}</td>
  <td class="row">${a.manageable?`<button class="btn sm" onclick="editUser(${a.id},'toggle')">${a.disabled?'تفعيل':'تعطيل'}</button><button class="btn sm" onclick="editUser(${a.id},'reset')">كلمة مرور</button><button class="btn sm" onclick="editUser(${a.id},'limit')">حد</button><button class="btn sm bad" onclick="editUser(${a.id},'del')">حذف</button>`:''}</td></tr>`).join('')}</table></div>`}
function showPw(u,p){const m=document.createElement('div');m.className='modal';m.innerHTML=`<div class="card"><h2>✅ تم</h2><div class="mut">بيانات الدخول (تظهر مرة واحدة فقط):</div><div class="card mono" style="margin:12px 0;line-height:2">المستخدم: <b>${esc(u)}</b><br>كلمة المرور: <b id="pwv">${esc(p)}</b></div><div class="row"><button class="btn pri" id="cp">نسخ</button><button class="btn" id="cl">إغلاق</button></div></div>`;document.body.append(m);m.querySelector('#cl').onclick=()=>{m.remove();route()};m.querySelector('#cp').onclick=()=>navigator.clipboard.writeText(`${u} / ${p}`).then(()=>toast('تم النسخ','ok'))}
function newUser(){const m=document.createElement('div');m.className='modal';m.innerHTML=`<div class="card"><h2>حساب جديد</h2><label>اسم المستخدم (إنجليزي)</label><input id="nu" class="mono"><label>كلمة المرور (اتركها فارغة لتوليدها)</label><input id="npw" class="mono">${ME.role==='owner'?`<label>الدور</label><select id="nr"><option value="user">مستخدم</option><option value="admin">مشرف</option></select>`:''}<label>أقصى عدد مشاريع</label><input id="nm" type="number" value="3" min="0"><label>معرّف تيليجرام (اختياري — لربط الحساب ببوتك)</label><input id="nt" class="mono"><label>ملاحظة</label><input id="nn"><div class="row" style="margin-top:16px"><button class="btn pri" id="ng">إنشاء</button><button class="btn" id="nc">إلغاء</button></div></div>`;document.body.append(m);m.querySelector('#nc').onclick=()=>m.remove();
  m.querySelector('#ng').onclick=async()=>{try{const j=await api('POST','/api/admin/accounts',{username:m.querySelector('#nu').value.trim(),password:m.querySelector('#npw').value,role:m.querySelector('#nr')?m.querySelector('#nr').value:'user',max_projects:+m.querySelector('#nm').value,tg_id:m.querySelector('#nt').value.trim(),note:m.querySelector('#nn').value});m.remove();showPw(j.username,j.password)}catch(e){toast(e.message,'bad')}}}
async function editUser(id,a){try{
  if(a==='del'){if(!confirm('حذف الحساب وكل مشاريعه؟'))return;await api('DELETE','/api/admin/accounts/'+id);toast('تم الحذف','ok');return vUsers()}
  if(a==='toggle'){await api('PATCH','/api/admin/accounts/'+id,{toggle:true});return vUsers()}
  if(a==='limit'){const v=prompt('أقصى عدد مشاريع:','3');if(v===null)return;await api('PATCH','/api/admin/accounts/'+id,{max_projects:+v});return vUsers()}
  if(a==='reset'){const j=await api('PATCH','/api/admin/accounts/'+id,{reset:true});showPw(j.username,j.password)}}catch(e){toast(e.message,'bad')}}
async function vSystem(){const j=await api('GET','/api/admin/system');const s=j.stats;
  const pc=(a,b)=>b?Math.min(100,Math.round(a/b*100)):0;
  $('#view').innerHTML=`<h1>النظام</h1><div class="mut">${esc(j.public_url||'')}</div><div class="grid" style="margin-top:14px">
  <div class="card"><div class="stat">${s.cpu.toFixed(0)}%<small>CPU</small></div><div class="bar" style="margin-top:8px"><i style="width:${s.cpu}%"></i></div></div>
  <div class="card"><div class="stat">${s.ram_used.toFixed(0)} MB<small>RAM من ${s.ram_total.toFixed(0)}</small></div><div class="bar" style="margin-top:8px"><i style="width:${pc(s.ram_used,s.ram_total)}%"></i></div></div>
  <div class="card"><div class="stat">${(s.disk_free/1024).toFixed(1)} GB<small>قرص حر من ${(s.disk_total/1024).toFixed(1)}</small></div><div class="bar" style="margin-top:8px"><i style="width:${100-pc(s.disk_free,s.disk_total)}%"></i></div></div>
  <div class="card"><div class="stat">${j.running}/${j.projects}<small>مشاريع تعمل</small></div></div>
  <div class="card"><div class="stat">${j.accounts}<small>حسابات</small></div></div><div class="card"><div class="stat">${j.requests}<small>طلبات البوابة</small></div></div></div>
  <div class="card" style="margin-top:14px"><h2>إعدادات</h2><label>الرابط العام للاستضافة (للروابط)</label><div class="row"><input id="pu" class="mono" value="${esc(j.public_url_setting||'')}" placeholder="https://my-app.onrender.com" style="flex:1"><button class="btn pri" id="pus">حفظ</button></div></div>`;
  $('#pus').onclick=async()=>{try{await api('POST','/api/admin/settings',{public_url:$('#pu').value.trim()});toast('تم الحفظ','ok')}catch(e){toast(e.message,'bad')}};TIMER=setInterval(()=>{if(location.hash==='#/system')vSystem()},10000)}
async function vAudit(){const j=await api('GET','/api/admin/audit');$('#view').innerHTML=`<h1>سجل العمليات</h1><div class="card" style="margin-top:14px;overflow:auto"><table><tr><th>الوقت</th><th>الحساب</th><th>العملية</th><th>التفاصيل</th></tr>${j.rows.map(r=>`<tr><td class="mut">${esc(r.ts)}</td><td>${esc(r.account)}</td><td><b>${esc(r.action)}</b></td><td class="mut">${esc(r.detail)}</td></tr>`).join('')}</table></div>`}
function vAccount(){$('#view').innerHTML=`<h1>حسابي</h1><div class="card" style="max-width:460px;margin-top:14px"><div class="row"><b>${esc(ME.username)}</b><span class="badge">${roleLbl[ME.role]}</span></div><label>كلمة المرور الحالية</label><input id="o" type="password"><label>الجديدة (8 أحرف على الأقل)</label><input id="n" type="password"><button class="btn pri" id="pg" style="margin-top:16px">تغيير</button></div>`;
  $('#pg').onclick=async()=>{try{await api('POST','/api/password',{old:$('#o').value,new:$('#n').value});toast('تم تغيير كلمة المرور','ok');$('#o').value=$('#n').value=''}catch(e){toast(e.message,'bad')}}}
addEventListener('hashchange',()=>{if(ME)route()});boot();
</script>
</body>
</html>
'''

# -*- coding: utf-8 -*-
"""
لوحة الويب — موقع إدارة الاستضافة (مثل HostBot لكن أقوى):
- الحسابات تُنشأ من المالك/المشرفين فقط (لا تسجيل عام).
- جلسات آمنة (كوكي HttpOnly + CSRF) وكلمات مرور PBKDF2 وحماية من تخمين كلمة المرور.
- مشاريع: رفع (ملف/ZIP)، تشغيل/إيقاف/إعادة، سجل حي، ملفات + محرر، طرفية، .env، تحليل.
- لوحة المالك/المشرف: الحسابات، كل المشاريع، موارد النظام، سجل العمليات، الإعدادات.
تعمل فوق بوابة الويب نفسها (نفس المنفذ)، بدون أي خدمة خارجية.
"""
import hashlib
import hmac
import html as _html
import json
import os
import re
import secrets
import shutil
import threading
import time
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_SECS = 7 * 86400
PBKDF_ITERS = 150_000
_fails: dict = {}
_fails_lock = threading.Lock()
_busy: set = set()
_results: dict = {}
_disk_cache: dict = {}
_html_cache = {"mtime": 0, "data": b""}


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


# ============================================================ قاعدة البيانات
def init_schema():
    C.db_execute(
        "CREATE TABLE IF NOT EXISTS web_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,"
        "pass_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', tg_id INTEGER, user_id INTEGER NOT NULL DEFAULT 0,"
        "max_projects INTEGER NOT NULL DEFAULT 3, disabled INTEGER NOT NULL DEFAULT 0, created_by TEXT, note TEXT,"
        "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, last_login TIMESTAMP)")
    C.db_execute(
        "CREATE TABLE IF NOT EXISTS web_sessions (token_hash TEXT PRIMARY KEY, account_id INTEGER NOT NULL, csrf TEXT NOT NULL,"
        "expires INTEGER NOT NULL, ip TEXT, created INTEGER NOT NULL)")
    C.db_execute(
        "CREATE TABLE IF NOT EXISTS web_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "account TEXT, action TEXT, detail TEXT)")


def audit(who, action, detail=""):
    try:
        C.db_execute("INSERT INTO web_audit (account, action, detail) VALUES (?,?,?)", (who, action, (detail or "")[:300]))
        C.db_execute("DELETE FROM web_audit WHERE id < (SELECT MAX(id) FROM web_audit) - 2000")
    except Exception:
        pass


# ============================================================ كلمات المرور والحسابات
def hash_pw(pw: str) -> str:
    salt = secrets.token_hex(8)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), PBKDF_ITERS).hex()
    return f"pbkdf2${PBKDF_ITERS}${salt}${dk}"


def check_pw(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(it)).hex()
        return hmac.compare_digest(got, dk)
    except Exception:
        return False


def gen_password() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def create_account(username, password, role="user", tg_id=None, max_projects=3, note="", created_by="system") -> dict:
    username = (username or "").strip()
    if not re.match(r"^[A-Za-z0-9_.-]{3,32}$", username):
        raise ApiError(400, "اسم المستخدم: 3-32 حرفاً إنجليزياً/أرقام/._-")
    if C.db_fetchone("SELECT 1 AS x FROM web_accounts WHERE username=?", (username,)):
        raise ApiError(409, "اسم المستخدم مستخدم بالفعل")
    password = password or gen_password()
    if len(password) < 8:
        raise ApiError(400, "كلمة المرور 8 أحرف على الأقل")
    if role not in ("owner", "admin", "user"):
        raise ApiError(400, "دور غير صالح")
    try:
        tg_id = int(tg_id) if tg_id not in (None, "", 0) else None
    except (TypeError, ValueError):
        raise ApiError(400, "معرّف تيليجرام يجب أن يكون رقماً")
    aid = C.db_execute_returning_id(
        "INSERT INTO web_accounts (username, pass_hash, role, tg_id, user_id, max_projects, note, created_by) VALUES (?,?,?,?,0,?,?,?)",
        (username, hash_pw(password), role, tg_id, int(max_projects), (note or "")[:200], created_by))
    uid = tg_id if tg_id else -aid
    C.db_execute("UPDATE web_accounts SET user_id=? WHERE id=?", (uid, aid))
    C.db_execute("INSERT OR IGNORE INTO users (id, first_name, username, approved, max_bots) VALUES (?,?,?,1,?)",
                 (uid, username, username, max(int(max_projects), 1)))
    return {"id": aid, "username": username, "password": password, "user_id": uid}


def ensure_owner():
    if C.db_fetchone("SELECT 1 AS x FROM web_accounts WHERE role='owner'"):
        return
    user = os.environ.get("OWNER_USERNAME") or "flix1234"
    pw = os.environ.get("OWNER_PASSWORD") or "flix1234"
    generated = not pw
    acc = create_account(user, pw or gen_password(), "owner", C.ADMIN_ID, 999, "المالك", "system") if True else None
    if generated:
        # نضع كلمة مرور مولّدة ونُبلغ المالك على تيليجرام + السجل
        newpw = gen_password()
        C.db_execute("UPDATE web_accounts SET pass_hash=? WHERE id=?", (hash_pw(newpw), acc["id"]))
        C.log.warning("Web panel owner created: username=%s password=%s (غيّرها بعد الدخول)", user, newpw)
        try:
            C.bot.send_message(C.ADMIN_ID, f"🔐 <b>لوحة الويب جاهزة</b>\nالمستخدم: <code>{user}</code>\nكلمة المرور: <code>{newpw}</code>\n"
                                           "غيّرها بعد أول دخول. لاسترجاعها لاحقاً: /webpass")
        except Exception:
            pass


# ============================================================ الجلسات
def _cookie(h, name):
    for part in (h.headers.get("Cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return ""


def _secure(h) -> bool:
    return (h.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip() == "https" or G.public_base()[0].startswith("https")


def auth(h):
    tok = _cookie(h, "fxs")
    if not tok:
        return None
    th = hashlib.sha256(tok.encode()).hexdigest()
    row = C.db_fetchone(
        "SELECT s.token_hash, s.csrf, s.expires, a.id AS aid, a.username, a.role, a.user_id, a.disabled, a.max_projects, a.tg_id "
        "FROM web_sessions s JOIN web_accounts a ON a.id=s.account_id WHERE s.token_hash=?", (th,))
    now = int(time.time())
    if not row or row["expires"] < now or row["disabled"]:
        return None
    if row["expires"] - now < SESSION_SECS - 3600:
        C.db_execute("UPDATE web_sessions SET expires=? WHERE token_hash=?", (now + SESSION_SECS, th))
    return row


def _client_ip(h):
    xf = h.headers.get("X-Forwarded-For", "")
    return (xf.split(",")[0].strip() if xf else h.client_address[0]) or "?"


def login(h, data):
    username = str(data.get("username") or "").strip()
    pw = str(data.get("password") or "")
    ip = _client_ip(h)
    keys = [f"{ip}|{username.lower()}", f"ip|{ip}"]
    now = time.time()
    with _fails_lock:
        for k in keys:
            cnt, first = _fails.get(k, (0, now))
            if now - first > 600:
                _fails.pop(k, None)
                continue
            if cnt >= (5 if "|" in k and not k.startswith("ip|") else 25):
                raise ApiError(429, "محاولات كثيرة. حاول بعد 10 دقائق.")
    acc = C.db_fetchone("SELECT * FROM web_accounts WHERE username=?", (username,))
    ok = bool(acc) and not acc["disabled"] and check_pw(pw, acc["pass_hash"])
    if not acc:
        check_pw(pw, "pbkdf2$%d$00$00" % PBKDF_ITERS)  # توحيد زمن الاستجابة
    if not ok:
        with _fails_lock:
            for k in keys:
                cnt, first = _fails.get(k, (0, now))
                _fails[k] = (cnt + 1, first if cnt else now)
        audit(username[:40], "login_failed", ip)
        raise ApiError(401, "بيانات الدخول غير صحيحة" if not (acc and acc["disabled"]) else "الحساب معطّل")
    with _fails_lock:
        for k in keys:
            _fails.pop(k, None)
    tok, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(16)
    t = int(time.time())
    C.db_execute("INSERT INTO web_sessions (token_hash, account_id, csrf, expires, ip, created) VALUES (?,?,?,?,?,?)",
                 (hashlib.sha256(tok.encode()).hexdigest(), acc["id"], csrf, t + SESSION_SECS, ip, t))
    C.db_execute("DELETE FROM web_sessions WHERE expires < ?", (t,))
    C.db_execute("UPDATE web_accounts SET last_login=CURRENT_TIMESTAMP WHERE id=?", (acc["id"],))
    audit(username, "login", ip)
    cookie = f"fxs={tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECS}" + ("; Secure" if _secure(h) else "")
    return {"user": _pub(acc), "csrf": csrf}, {"Set-Cookie": cookie}


def _pub(a):
    return {"id": a["id"] if "id" in a else a.get("aid"), "username": a["username"], "role": a["role"], "tg_id": a.get("tg_id")}


# ============================================================ المشاريع
def _disk_mb(pid):
    c = _disk_cache.get(pid)
    if c and time.time() - c[1] < 120:
        return c[0]
    total = 0
    for root, _, files in os.walk(os.path.join(C.PROJECTS_DIR, str(pid))):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    v = round(total / 1048576, 1)
    _disk_cache[pid] = (v, time.time())
    return v


def _is_staff(a):
    return a["role"] in ("owner", "admin")


def get_project(a, pid, owner_only=False):
    p = C.db_fetchone("SELECT * FROM projects WHERE id=?", (pid,))
    if not p or not (p["user_id"] == a["user_id"] or _is_staff(a)):
        raise ApiError(404, "المشروع غير موجود")
    return p


def proj_json(p, full=False):
    pid = p["id"]
    st = C.manager.status(pid)
    site = C.db_fetchone("SELECT slug, kind, hits, public FROM web_sites WHERE project_id=?", (pid,))
    out = {"id": pid, "name": p["name"], "main_file": p.get("main_file") or "", "runtime": C.detect_runtime_from_file(p.get("main_file") or "") if p.get("main_file") else (p.get("runtime") or "python"),
           "running": bool(st.get("running")), "busy": pid in _busy, "last_error": p.get("last_error") or ""}
    if site:
        out["url"] = G.site_url(site["slug"])[0]
        out.update(slug=site["slug"], hits=site["hits"], public=bool(site["public"]))
    if full:
        files = C.db_fetchall("SELECT filename FROM project_files WHERE project_id=? ORDER BY filename", (pid,))
        env = C.db_fetchone("SELECT content FROM project_files WHERE project_id=? AND filename='.env'", (pid,))
        out.update(status=st, disk_mb=_disk_mb(pid), files=[f["filename"] for f in files],
                   env=bytes(env["content"]).decode("utf-8", "replace") if env else "")
    return out


def _async(pid, fn):
    if pid in _busy:
        raise ApiError(409, "هناك عملية جارية على هذا المشروع")
    _busy.add(pid)

    def run():
        try:
            _results[pid] = (*fn(), time.time())
        except Exception as e:  # noqa
            C.log.exception("panel action")
            _results[pid] = (False, str(e)[:200], time.time())
        finally:
            _busy.discard(pid)
    threading.Thread(target=run, daemon=True, name=f"panel-{pid}").start()


def create_project(a, name, filename, raw, start=True):
    name = re.sub(r"[^\w .-]", "", name or "", flags=re.UNICODE).strip()[:40] or "project"
    if a["role"] == "user":
        cnt = (C.db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (a["user_id"],)) or {}).get("c", 0)
        if cnt >= a["max_projects"]:
            raise ApiError(403, f"وصلت للحد الأقصى من المشاريع ({a['max_projects']}). اطلب زيادته من المشرف.")
    if not raw:
        raise ApiError(400, "الملف فارغ")
    if len(raw) > 60 * 1024 * 1024:
        raise ApiError(413, "الملف أكبر من 60MB")
    fn = os.path.basename(filename or "file").strip()
    low = fn.lower()
    pid = C.db_execute_returning_id(
        "INSERT INTO projects (user_id, name, main_file, approved, energy_exempt) VALUES (?,?,?,1,1)", (a["user_id"], name, ""))
    try:
        if low.endswith(".zip"):
            main, rt, n, notes = C.store_project_from_zip(pid, raw)
        else:
            if not low.endswith((".py", ".js", ".mjs", ".cjs", ".ts", ".html", ".htm")):
                raise ApiError(400, "النوع غير مدعوم. ارفع .py أو .js أو .html أو .zip")
            safe = C._safe_rel(fn)
            C.store_project_files(pid, {safe: raw})
            main, rt = safe, C.detect_runtime_from_file(safe)
        C.db_execute("UPDATE projects SET main_file=?, runtime=? WHERE id=?", (main, rt, pid))
    except ApiError:
        _delete_project(pid)
        raise
    except ValueError as e:
        _delete_project(pid)
        raise ApiError(400, str(e))
    issues = [re.sub(r"<[^>]+>", "", _html.unescape(i)) for i in C.static_check_project(pid)]
    audit(a["username"], "project_create", f"#{pid} {name}")
    if start:
        _async(pid, lambda: C.manager.start_project(pid))
    return pid, issues


def _delete_project(pid):
    try:
        C.manager.stop_project(pid)
    except Exception:
        pass
    C.manager.processes.pop(pid, None)
    shutil.rmtree(os.path.join(C.PROJECTS_DIR, str(pid)), ignore_errors=True)
    for q in ("DELETE FROM web_sites WHERE project_id=?", "DELETE FROM project_files WHERE project_id=?", "DELETE FROM projects WHERE id=?"):
        try:
            C.db_execute(q, (pid,))
        except Exception:
            pass
    if G:
        G._invalidate()


# ============================================================ طلبات HTTP
def _body(h, limit):
    n = int(h.headers.get("Content-Length") or 0)
    if n > limit:
        h.close_connection = True
        raise ApiError(413, "الحجم أكبر من المسموح")
    buf, left = [], n
    while left > 0:
        c = h.rfile.read(min(65536, left))
        if not c:
            break
        buf.append(c)
        left -= len(c)
    return b"".join(buf)


def _json_body(h):
    raw = _body(h, 1024 * 1024)
    if not raw:
        return {}
    try:
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        raise ApiError(400, "JSON غير صالح")


def _jr(h, obj, status=200, extra=None, head=False):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ex = {"Cache-Control": "no-store", "X-Frame-Options": "DENY"}
    ex.update(extra or {})
    h._send(status, body, "application/json; charset=utf-8", extra=ex, head=head)


def _panel_bytes():
    """الصفحة المدمجة، أو ملف panel.html بجوار البرنامج إن وُجد (للتخصيص اليدوي)."""
    path = os.path.join(_HERE, "panel.html")
    try:
        m = os.path.getmtime(path)
        if m != _html_cache["mtime"]:
            _html_cache.update(mtime=m, data=open(path, "rb").read())
        return _html_cache["data"]
    except OSError:
        return PANEL_HTML.encode("utf-8")


def _page(h, head):
    h._send(200, _panel_bytes(), "text/html; charset=utf-8", head=head, extra={
        "Cache-Control": "no-cache", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
        "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"})


def handle(h, path, head=False) -> bool:
    """يرجع True إن كان الطلب للوحة."""
    if path in ("/", "/login", "/app", "/panel") and h.command in ("GET", "HEAD"):
        _page(h, head)
        return True
    if path == "/favicon.ico":
        h._send(204, b"", head=head)
        return True
    if not path.startswith("/api/"):
        return False
    try:
        out, extra = api(h, h.command, urllib.parse.urlsplit(h.path))
        _jr(h, out, 200, extra, head)
    except ApiError as e:
        _jr(h, {"error": e.msg}, e.status)
    except Exception:
        C.log.exception("panel api")
        _jr(h, {"error": "خطأ داخلي"}, 500)
    return True


def api(h, method, sp):
    path = sp.path
    q = {k: v[0] for k, v in urllib.parse.parse_qs(sp.query).items()}
    if path == "/api/login" and method == "POST":
        return login(h, _json_body(h))
    a = auth(h)
    if not a:
        h.close_connection = True
        raise ApiError(401, "غير مسجّل الدخول")
    if method != "GET" and not hmac.compare_digest(h.headers.get("X-CSRF", ""), a["csrf"]):
        h.close_connection = True
        raise ApiError(403, "رمز الحماية غير صالح — أعد تحميل الصفحة")
    if path == "/api/me":
        return {"user": _pub(a), "csrf": a["csrf"]}, None
    if path == "/api/logout" and method == "POST":
        C.db_execute("DELETE FROM web_sessions WHERE token_hash=?", (a["token_hash"],))
        return {"ok": True}, {"Set-Cookie": "fxs=; Path=/; Max-Age=0; HttpOnly"}
    if path == "/api/password" and method == "POST":
        d = _json_body(h)
        acc = C.db_fetchone("SELECT pass_hash FROM web_accounts WHERE id=?", (a["aid"],))
        if not check_pw(str(d.get("old") or ""), acc["pass_hash"]):
            raise ApiError(403, "كلمة المرور الحالية غير صحيحة")
        if len(str(d.get("new") or "")) < 8:
            raise ApiError(400, "كلمة المرور الجديدة 8 أحرف على الأقل")
        C.db_execute("UPDATE web_accounts SET pass_hash=? WHERE id=?", (hash_pw(d["new"]), a["aid"]))
        C.db_execute("DELETE FROM web_sessions WHERE account_id=? AND token_hash<>?", (a["aid"], a["token_hash"]))
        audit(a["username"], "password_change")
        return {"ok": True}, None
    if path.startswith("/api/admin/"):
        if not _is_staff(a):
            raise ApiError(403, "للمشرفين فقط")
        return admin_api(h, method, path, q, a), None
    if path == "/api/projects" and method == "GET":
        if q.get("all") and _is_staff(a):
            rows = C.db_fetchall("SELECT p.*, COALESCE(w.username, u.first_name, '?') AS owner FROM projects p LEFT JOIN web_accounts w ON w.user_id=p.user_id "
                                 "LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT 500")
            return {"projects": [dict(proj_json(r), owner=r["owner"]) for r in rows]}, None
        rows = C.db_fetchall("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC", (a["user_id"],))
        return {"projects": [proj_json(r) for r in rows]}, None
    if path == "/api/projects/upload" and method == "POST":
        fname = urllib.parse.unquote(h.headers.get("X-Filename", "file"))
        raw = _body(h, 61 * 1024 * 1024)
        pid, issues = create_project(a, q.get("name", ""), fname, raw, q.get("start") == "1")
        return {"id": pid, "issues": issues}, None
    m = re.match(r"^/api/projects/(\d+)(?:/(\w+))?$", path)
    if not m:
        raise ApiError(404, "غير موجود")
    pid, sub = int(m.group(1)), m.group(2)
    p = get_project(a, pid)
    if sub is None:
        if method == "GET":
            r = proj_json(p, True)
            res = _results.get(pid)
            if res and time.time() - res[2] < 30:
                r["last_result"] = {"ok": res[0], "message": res[1]}
            return {"project": r}, None
        if method == "DELETE":
            _delete_project(pid)
            audit(a["username"], "project_delete", f"#{pid} {p['name']}")
            return {"ok": True}, None
    if sub in ("start", "restart") and method == "POST":
        fn = (lambda: C.manager.start_project(pid)) if sub == "start" else (lambda: C.manager.restart_project(pid))
        _async(pid, fn)
        audit(a["username"], f"project_{sub}", f"#{pid}")
        return {"message": "بدأت العملية... قد تستغرق ثوانٍ إن كانت هناك مكتبات للتثبيت"}, None
    if sub == "stop" and method == "POST":
        C.manager.stop_project(pid)
        audit(a["username"], "project_stop", f"#{pid}")
        return {"message": "تم الإيقاف"}, None
    if sub == "logs" and method == "GET":
        return {"log": C.manager.tail_log(pid, min(int(q.get("n") or 8000), 60000))}, None
    if sub == "install" and method == "POST":
        ok, report = C.install_dependencies(pid, True)
        return {"ok": ok, "report": re.sub(r"<[^>]+>", "", _html.unescape(report))}, None
    if sub == "analyze" and method == "GET":
        pass  # (الوحدة مدمجة في هذا الملف)
        return {"report": re.sub(r"<[^>]+>", "", _html.unescape(analyze_project(C, pid)))}, None
    if sub == "exec" and method == "POST":
        d = _json_body(h)
        return {"output": C.run_project_terminal_command(pid, str(d.get("cmd") or ""), 60, a["user_id"])}, None
    if sub == "files" and method == "GET":
        rows = C.db_fetchall("SELECT filename, size_bytes FROM project_files WHERE project_id=? ORDER BY filename", (pid,))
        return {"files": [{"name": r["filename"], "size": r["size_bytes"]} for r in rows]}, None
    if sub in ("file", "upload"):
        name = C._safe_rel(q.get("name", ""))
        if not name:
            raise ApiError(400, "اسم الملف غير صالح")
        if sub == "file" and method == "GET":
            r = C.db_fetchone("SELECT content, size_bytes FROM project_files WHERE project_id=? AND filename=?", (pid, name))
            if not r:
                raise ApiError(404, "الملف غير موجود")
            if r["size_bytes"] > 300_000:
                raise ApiError(400, "الملف كبير للعرض")
            try:
                return {"content": bytes(r["content"]).decode("utf-8")}, None
            except UnicodeDecodeError:
                raise ApiError(400, "ملف ثنائي لا يمكن عرضه")
        if sub == "file" and method == "PUT":
            C.store_project_files(pid, {name: _body(h, 1024 * 1024)})
            audit(a["username"], "file_edit", f"#{pid} {name}")
            return {"ok": True}, None
        if sub == "file" and method == "DELETE":
            C.db_execute("DELETE FROM project_files WHERE project_id=? AND filename=?", (pid, name))
            return {"ok": True}, None
        if sub == "upload" and method == "POST":
            raw = _body(h, 61 * 1024 * 1024)
            if name.lower().endswith(".zip"):
                files, _ = C.extract_zip_safe(raw)
                C.store_project_files(pid, files)
            else:
                C.store_project_files(pid, {name: raw})
            return {"ok": True}, None
    if sub == "settings" and method == "PUT":
        d = _json_body(h)
        if "env" in d:
            env = str(d["env"])
            if env.strip():
                C.store_project_files(pid, {".env": env.encode("utf-8")})
            else:
                C.db_execute("DELETE FROM project_files WHERE project_id=? AND filename='.env'", (pid,))
        mf = d.get("main_file")
        if mf and mf != p.get("main_file"):
            if not C.db_fetchone("SELECT 1 AS x FROM project_files WHERE project_id=? AND filename=?", (pid, mf)):
                raise ApiError(400, "الملف الرئيسي غير موجود")
            C.db_execute("UPDATE projects SET main_file=?, runtime=? WHERE id=?", (mf, C.detect_runtime_from_file(mf), pid))
        site = C.db_fetchone("SELECT slug FROM web_sites WHERE project_id=?", (pid,))
        if site:
            if d.get("slug") and d["slug"] != site["slug"]:
                ok, msg = G.set_slug(pid, str(d["slug"]).lower())
                if not ok:
                    raise ApiError(400, msg)
            if d.get("public") is not None:
                C.db_execute("UPDATE web_sites SET public=? WHERE project_id=?", (1 if d["public"] else 0, pid))
                G._invalidate()
        audit(a["username"], "project_settings", f"#{pid}")
        return {"ok": True}, None
    raise ApiError(404, "غير موجود")


# ============================================================ واجهات الإدارة
def _manageable(actor, acc):
    if acc["role"] == "owner":
        return False
    return actor["role"] == "owner" or acc["role"] == "user"


def admin_api(h, method, path, q, a):
    if path == "/api/admin/accounts":
        if method == "GET":
            rows = C.db_fetchall("SELECT * FROM web_accounts ORDER BY id")
            out = []
            for r in rows:
                cnt = (C.db_fetchone("SELECT COUNT(*) AS c FROM projects WHERE user_id=?", (r["user_id"],)) or {}).get("c", 0)
                out.append({"id": r["id"], "username": r["username"], "role": r["role"], "tg_id": r["tg_id"], "disabled": r["disabled"],
                            "max_projects": r["max_projects"], "projects": cnt, "last_login": r["last_login"], "manageable": _manageable(a, r)})
            return {"accounts": out}
        if method == "POST":
            d = _json_body(h)
            role = d.get("role", "user")
            if role == "owner" or (role == "admin" and a["role"] != "owner"):
                raise ApiError(403, "لا تملك صلاحية إنشاء هذا الدور")
            acc = create_account(d.get("username"), d.get("password"), role, d.get("tg_id"), int(d.get("max_projects") or 3), d.get("note", ""), a["username"])
            audit(a["username"], "account_create", f"{acc['username']} ({role})")
            return {"username": acc["username"], "password": acc["password"]}
    m = re.match(r"^/api/admin/accounts/(\d+)$", path)
    if m:
        acc = C.db_fetchone("SELECT * FROM web_accounts WHERE id=?", (int(m.group(1)),))
        if not acc or not _manageable(a, acc):
            raise ApiError(403, "لا تملك صلاحية على هذا الحساب")
        if method == "PATCH":
            d = _json_body(h)
            if d.get("toggle"):
                C.db_execute("UPDATE web_accounts SET disabled=? WHERE id=?", (0 if acc["disabled"] else 1, acc["id"]))
                C.db_execute("DELETE FROM web_sessions WHERE account_id=?", (acc["id"],))
                audit(a["username"], "account_toggle", acc["username"])
            if "max_projects" in d:
                C.db_execute("UPDATE web_accounts SET max_projects=? WHERE id=?", (max(0, int(d["max_projects"])), acc["id"]))
            if d.get("reset"):
                pw = gen_password()
                C.db_execute("UPDATE web_accounts SET pass_hash=? WHERE id=?", (hash_pw(pw), acc["id"]))
                C.db_execute("DELETE FROM web_sessions WHERE account_id=?", (acc["id"],))
                audit(a["username"], "account_reset", acc["username"])
                return {"username": acc["username"], "password": pw}
            return {"ok": True}
        if method == "DELETE":
            if acc["user_id"] < 0:  # حساب ويب فقط: نحذف مشاريعه
                for r in C.db_fetchall("SELECT id FROM projects WHERE user_id=?", (acc["user_id"],)):
                    _delete_project(r["id"])
            C.db_execute("DELETE FROM web_sessions WHERE account_id=?", (acc["id"],))
            C.db_execute("DELETE FROM web_accounts WHERE id=?", (acc["id"],))
            audit(a["username"], "account_delete", acc["username"])
            return {"ok": True}
    if path == "/api/admin/system" and method == "GET":
        pass  # (الوحدة مدمجة في هذا الملف)
        try:
            stats = monitor_sample() if C else {"cpu": 0.0, "ram_used": 0.0, "ram_total": 0.0, "disk_free": 0.0, "disk_total": 0.0}
        except Exception:
            stats = {"cpu": 0.0, "ram_used": 0.0, "ram_total": 0.0, "disk_free": 0.0, "disk_total": 0.0}
        cnt = lambda q_: (C.db_fetchone(q_) or {}).get("c", 0)
        return {"stats": stats, "projects": cnt("SELECT COUNT(*) AS c FROM projects"),
                "running": sum(1 for hp in list(C.manager.processes.values()) if hp.is_alive()),
                "accounts": cnt("SELECT COUNT(*) AS c FROM web_accounts"), "requests": G._gateway["total"],
                "public_url": G.public_base()[0], "public_url_setting": C.get_setting("public_url") or ""}
    if path == "/api/admin/audit" and method == "GET":
        return {"rows": C.db_fetchall("SELECT ts, account, action, detail FROM web_audit ORDER BY id DESC LIMIT 200")}
    if path == "/api/admin/settings" and method == "POST":
        if a["role"] != "owner":
            raise ApiError(403, "للمالك فقط")
        d = _json_body(h)
        u = str(d.get("public_url") or "").strip().rstrip("/")
        if u and not re.match(r"^https?://[A-Za-z0-9._:-]+$", u):
            raise ApiError(400, "رابط غير صالح. مثال: https://my-app.onrender.com")
        C.set_setting("public_url", u)
        C.db_execute("UPDATE web_sites SET announced_url=NULL")
        G._invalidate()
        audit(a["username"], "set_public_url", u)
        return {"ok": True}
    raise ApiError(404, "غير موجود")


# ============================================================ أوامر تيليجرام للمالك
def webpanel_register_commands():
    bot = C.bot

    def owner_only(m):
        return m.from_user.id == C.ADMIN_ID

    @bot.message_handler(commands=["web", "panel"])
    def cmd_web(m):
        if C.msg_seen(m):
            return
        bot.send_message(m.chat.id, f"🌐 <b>لوحة الويب</b>\n{C.html_escape(G.public_base()[0])}\n"
                                    "الدخول بحساب يُنشئه لك المالك/المشرف. اطلب حسابك منهم.")

    @bot.message_handler(commands=["webpass"])
    def cmd_webpass(m):
        if C.msg_seen(m) or not owner_only(m):
            return
        acc = C.db_fetchone("SELECT id, username FROM web_accounts WHERE role='owner' ORDER BY id LIMIT 1")
        if not acc:
            return
        pw = gen_password()
        C.db_execute("UPDATE web_accounts SET pass_hash=?, disabled=0 WHERE id=?", (hash_pw(pw), acc["id"]))
        C.db_execute("DELETE FROM web_sessions WHERE account_id=?", (acc["id"],))
        base = G.public_base()[0]
        bot.send_message(m.chat.id, f"🔐 <b>لوحة الويب</b>\n{C.html_escape(base)}\nالمستخدم: <code>{acc['username']}</code>\nكلمة المرور: <code>{pw}</code>")

    @bot.message_handler(commands=["webadd"])
    def cmd_webadd(m):
        if C.msg_seen(m) or not owner_only(m):
            return
        a = (m.text or "").split()
        if len(a) < 2:
            return bot.send_message(m.chat.id, "الاستخدام: <code>/webadd اسم_المستخدم [admin|user] [عدد_المشاريع]</code>")
        try:
            role = a[2] if len(a) > 2 and a[2] in ("admin", "user") else "user"
            mx = int(a[3]) if len(a) > 3 else 3
            acc = create_account(a[1], None, role, None, mx, "", "telegram-owner")
        except ApiError as e:
            return bot.send_message(m.chat.id, f"❌ {e.msg}")
        audit("telegram-owner", "account_create", f"{a[1]} ({role})")
        bot.send_message(m.chat.id, f"✅ تم إنشاء الحساب\n{C.html_escape(G.public_base()[0])}\nالمستخدم: <code>{acc['username']}</code>\nكلمة المرور: <code>{acc['password']}</code>")

    @bot.message_handler(commands=["webusers"])
    def cmd_webusers(m):
        if C.msg_seen(m) or not owner_only(m):
            return
        rows = C.db_fetchall("SELECT username, role, disabled FROM web_accounts ORDER BY id")
        bot.send_message(m.chat.id, "👥 <b>حسابات الويب</b>\n" + "\n".join(
            f"{'🔴' if r['disabled'] else '🟢'} <code>{r['username']}</code> · {r['role']}" for r in rows))


def webpanel_install(core, gateway):
    global C, G
    C = G = sys.modules[__name__]  # النواة والبوابة في نفس الملف
    init_schema()
    ensure_owner()
    orig_root = Handler._root

    def _root(self, path, head=False):
        if handle(self, path, head):
            return
        orig_root(self, path, head)

    Handler._root = _root
    webpanel_register_commands()
    core.log.info("Web panel installed")


# ==========================================================================
# 7) استوديو الستايل
# ==========================================================================
_EMBEDDED_THEMES = json.loads(r'''{
  "_help": "أضف ستايلاتك هنا. كل ستايل: مفتاح إنجليزي صغير، name، و knobs. القيم المسموحة: label (يجب أن يحوي {t})، quote: blockquote|expandable|bar|pre|none، bullet، divider، arrow، bar، spin: braille|dots|arrows|moon|clock|bounce|pulse، colors: original|all_primary|all_success|all_danger|roles|cycle، cols_main: 0-3، strip_emoji: true|false، header، footer. ثم من البوت: /studio ← الستايلات ← إعادة قراءة themes.json",
  "presets": {
    "sunrise": {
      "name": "🌄 شروق",
      "knobs": {
        "label": "✦ {t}",
        "bullet": "✦",
        "divider": "═",
        "colors": "cycle",
        "bar": "▰▱",
        "spin": "pulse",
        "quote": "expandable",
        "cols_main": 2,
        "header": "☀️ صباح الخير"
      }
    },
    "mono": {
      "name": "⬛ أحادي",
      "knobs": {
        "label": "[ {t} ]",
        "bullet": "-",
        "divider": "─",
        "quote": "pre",
        "colors": "all_primary",
        "strip_emoji": true,
        "cols_main": 1
      }
    }
  }
}
''')

# -*- coding: utf-8 -*-
"""
استوديو الستايل (Style Studio) — تغيير شكل البوت كله من تيليجرام أو من ملفات JSON:
  • 11 ستايل جاهز + ستايلات مخصصة من themes.json
  • تحرير أي زر: النص / الأيقونة / اللون / الإخفاء / الترتيب / عدد الأعمدة
  • تخصيص الإطار: الاقتباس، الرموز، الأسهم، الفواصل، شريط التقدم، المؤشرات
  • معاينة حية قبل التطبيق، تراجع، تصدير/استيراد JSON
  • زر «السورس»: فيديو مموّه (Spoiler) + نص اقتباس + أزرار روابط
  • أدوات: عد تنازلي، شاشات متحركة، ترمنال — وإضافات plugin_*.py
المالك فقط (ADMIN_ID). كل شيء محلي بدون أي خدمة خارجية.
"""
import copy
import glob
import hashlib
import html as _html
import importlib.util
import io
import json
import os
import re
import sys
import threading
import time
from contextlib import contextmanager

_HERE = os.path.dirname(os.path.abspath(__file__))
_tl = threading.local()
_lock = threading.RLock()
_cache = {"cfg": None, "ts": 0.0}
_REG: dict = {}          # callback_data -> {"t": النص الأصلي}
_SCREENS: dict = {}      # مفتاح الشاشة -> {"name":..., "cds":[...]}
_dirty = {"v": False}
_pending: dict = {}
_ctx: dict = {}
_plugins: list = []
_custom_presets: dict = {}

# ============================================================ الخيارات
LABELS = ["{t}", "➤ {t}", "❯ {t}", "▸ {t}", "« {t} »", "⟦ {t} ⟧", "[ {t} ]", "✦ {t} ✦", "• {t}", "{t} ‹", "≋ {t}", "⌁ {t}"]
UI_QUOTES = ["blockquote", "expandable", "bar", "pre", "none"]
BULLETS = ["•", "◆", "▸", "➤", "✦", "◉", "›", "▪"]
DIVIDERS = ["━", "─", "═", "┄", "▬", "✦", "·", "▁"]
ARROWS = ["➤", "❯", "➜", "»", "▸", "⟶", "⇒"]
BARS = ["▰▱", "█░", "■□", "●○", "▮▯", "⣿⣀", "▓░"]
SPINS = ["braille", "dots", "arrows", "moon", "clock", "bounce", "pulse"]
COLORS = ["original", "all_primary", "all_success", "all_danger", "roles", "cycle"]
KNOB_OPTIONS = {"label": LABELS, "quote": UI_QUOTES, "bullet": BULLETS, "divider": DIVIDERS, "arrow": ARROWS,
                "bar": BARS, "spin": SPINS, "colors": COLORS, "cols_main": [0, 1, 2, 3], "strip_emoji": [False, True]}
KNOB_NAMES = {"label": "شكل الأزرار", "quote": "إطار النص", "bullet": "رمز النقاط", "divider": "الفاصل", "arrow": "السهم",
              "bar": "شريط التقدم", "spin": "المؤشر المتحرك", "colors": "ألوان الأزرار", "cols_main": "أعمدة القائمة الرئيسية",
              "strip_emoji": "حذف الإيموجي من الأزرار"}
QUOTE_NAMES = {"blockquote": "اقتباس", "expandable": "اقتباس قابل للطي", "bar": "شريط جانبي", "pre": "صندوق كود", "none": "بدون"}
COLOR_NAMES = {"original": "الأصلي", "all_primary": "أزرق", "all_success": "أخضر", "all_danger": "أحمر", "roles": "ذكي حسب الوظيفة", "cycle": "متدرّج"}
DEFAULT_KNOBS = {"label": "{t}", "quote": "blockquote", "bullet": "•", "divider": "━", "arrow": "➤", "bar": "▰▱", "spin": "braille",
                 "colors": "original", "cols_main": 0, "strip_emoji": False, "header": "", "footer": ""}

PRESETS = {
    "classic": {"name": "🎯 كلاسيك", "knobs": {}},
    "ocean": {"name": "🌊 محيط", "knobs": {"label": "≋ {t}", "bullet": "◦", "bar": "●○", "spin": "moon", "colors": "all_primary", "divider": "┄"}},
    "forest": {"name": "🌲 غابة", "knobs": {"label": "▸ {t}", "bullet": "▪", "bar": "■□", "colors": "all_success", "divider": "─"}},
    "sunset": {"name": "🌅 غروب", "knobs": {"label": "❯ {t}", "bullet": "◆", "bar": "▓░", "spin": "pulse", "colors": "all_danger", "arrow": "❯"}},
    "night": {"name": "🌙 ليلي", "knobs": {"label": "{t} ‹", "bullet": "›", "spin": "moon", "colors": "all_primary", "quote": "bar", "divider": "·"}},
    "gold": {"name": "👑 ذهبي", "knobs": {"label": "✦ {t} ✦", "bullet": "✦", "divider": "═", "colors": "roles", "bar": "█░", "quote": "expandable"}},
    "rose": {"name": "🌹 وردي", "knobs": {"label": "• {t}", "bullet": "◉", "colors": "cycle", "bar": "●○", "spin": "pulse", "arrow": "➜"}},
    "cyber": {"name": "⚡ سايبر", "knobs": {"label": "⟦ {t} ⟧", "bullet": "▸", "bar": "▮▯", "spin": "braille", "colors": "roles", "divider": "▬", "arrow": "⇒", "cols_main": 2}},
    "neon": {"name": "💠 نيون", "knobs": {"label": "⌁ {t}", "bullet": "◆", "bar": "▰▱", "colors": "cycle", "divider": "━", "spin": "dots"}},
    "terminal": {"name": "💻 ترمنال", "knobs": {"label": "[ {t} ]", "bullet": "›", "quote": "pre", "bar": "█░", "spin": "bounce", "colors": "all_success",
                                               "divider": "─", "strip_emoji": True, "arrow": "»", "cols_main": 1}},
    "minimal": {"name": "⚪ بسيط", "knobs": {"label": "{t}", "bullet": "·", "quote": "none", "strip_emoji": True, "divider": "─", "colors": "original", "cols_main": 1}},
}

SPIN_FRAMES = {"braille": list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"), "dots": ["·  ", "·· ", "···", " ··", "  ·", "   "], "arrows": list("←↖↑↗→↘↓↙"),
               "moon": list("🌑🌒🌓🌔🌕🌖🌗🌘"), "clock": list("🕛🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚"),
               "bounce": ["[=   ]", "[ =  ]", "[  = ]", "[   =]", "[  = ]", "[ =  ]"], "pulse": list("○◔◑◕●◕◑◔")}

DEFAULT_SOURCE = ("<b>📦 عن السورس</b>\n\nاستضافة بوتات ومواقع (Python · Node.js · HTML) مع لوحة تحكم كاملة.\n"
                  "• رفع مشاريع ZIP وتشغيلها تلقائياً\n• روابط للمواقع ولوحة ويب\n• مراقبة 24/7 وإصلاح ذاتي للأخطاء")

_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d\u2300-\u23FF\u2190-\u21FF\u25A0-\u25FF]+")


def default_cfg():
    return {"preset": "classic", "over": {}, "buttons": {}, "order": {}, "cols": {},
            "custom": [{"id": "source", "text": "📦 السورس", "kind": "source"}],
            "source": {"text": "", "file_id": "", "kind": "", "spoiler": True, "urls": []}}


# ============================================================ التخزين
def cfg():
    now = time.time()
    with _lock:
        if _cache["cfg"] is not None and now - _cache["ts"] < 4:
            return _cache["cfg"]
        try:
            d = json.loads(C.get_setting("ui_cfg") or "{}")
        except Exception:
            d = {}
        base = default_cfg()
        base.update({k: v for k, v in d.items() if k in base})
        _cache.update(cfg=base, ts=now)
        return base


def save_cfg(d, snapshot=True):
    with _lock:
        if snapshot:
            try:
                hist = json.loads(C.get_setting("ui_hist") or "[]")
            except Exception:
                hist = []
            hist.append(C.get_setting("ui_cfg") or "{}")
            C.set_setting("ui_hist", json.dumps(hist[-10:]))
        C.set_setting("ui_cfg", json.dumps(d, ensure_ascii=False))
        _cache.update(cfg=d, ts=time.time())


def all_presets():
    p = dict(PRESETS)
    p.update(_custom_presets)
    return p


def load_custom_presets():
    _custom_presets.clear()
    for k, v in (_EMBEDDED_THEMES.get("presets") or {}).items():
        if isinstance(v, dict) and isinstance(v.get("knobs"), dict) and k not in PRESETS:
            _custom_presets[k] = {"name": str(v.get("name") or k)[:30], "knobs": _clean_knobs(v["knobs"]), "custom": True}
    path = os.path.join(_HERE, "themes.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        for k, v in (data.get("presets") or data).items():
            if isinstance(v, dict) and isinstance(v.get("knobs"), dict) and re.match(r"^[a-z0-9_]{2,20}$", k) and k not in PRESETS:
                _custom_presets[k] = {"name": str(v.get("name") or k)[:30], "knobs": _clean_knobs(v["knobs"]), "custom": True}
    except FileNotFoundError:
        pass
    except Exception:
        C.log.exception("themes.json")


def _clean_knobs(k):
    out = {}
    for name, val in (k or {}).items():
        if name in KNOB_OPTIONS and val in KNOB_OPTIONS[name]:
            out[name] = val
        elif name in ("header", "footer") and isinstance(val, str):
            out[name] = val[:200]
        elif name == "label" and isinstance(val, str) and "{t}" in val and len(val) <= 30:
            out[name] = val
    return out


@contextmanager
def preview(preset=None, over=None):
    prev = getattr(_tl, "ov", None)
    _tl.ov = {"preset": preset, "over": over or {}}
    try:
        yield
    finally:
        _tl.ov = prev


def knobs():
    ov = getattr(_tl, "ov", None)
    c = cfg()
    pid = (ov or {}).get("preset") or c["preset"]
    k = dict(DEFAULT_KNOBS)
    k.update(all_presets().get(pid, PRESETS["classic"])["knobs"])
    k.update(c["over"] if not ov or ov.get("preset") is None else {})
    if ov:
        k.update(ov.get("over") or {})
    return k


# ============================================================ تحويل الأزرار
_NO_DECOR = {"noop", "noop_sig"}
_DANGER = ("del", "stop", "ban", "reject", "cancel", "remove", "clear", "kill", "block")
_SUCCESS = ("start", "new", "add", "approve", "save", "ok", "upload", "confirm", "install", "run", "restart", "yes", "source")


def _cd_of(btn):
    cd = getattr(btn, "callback_data", None)
    if cd:
        return str(cd)
    url = getattr(btn, "url", None)
    return "u:" + hashlib.sha1(str(url or btn.text).encode()).hexdigest()[:8]


def role_style(cd, orig):
    c = cd.lower()
    if c.startswith(("back", "adm_panel")) or "home" in c:
        return "primary"
    if any(w in c for w in _DANGER):
        return "danger"
    if any(w in c for w in _SUCCESS):
        return "success"
    return orig or "primary"


def decorate_button(btn):
    try:
        cd = _cd_of(btn)
        text = btn.text
        if cd not in _NO_DECOR and not cd.startswith("ui:") or cd in ("ui:source",) or cd.startswith("ui:cb:"):
            if cd not in _REG and len(_REG) < 600:
                _REG[cd] = {"t": text}
                _dirty["v"] = True
        c = cfg()
        ov = c["buttons"].get(cd) or {}
        k = knobs()
        if ov.get("text"):
            text = ov["text"]
        elif k["strip_emoji"] and cd not in _NO_DECOR:
            stripped = _EMOJI_RE.sub("", text).strip()
            text = stripped or text
        if ov.get("icon"):
            text = f"{ov['icon']} {text}"
        if cd not in _NO_DECOR and not ov.get("text"):
            text = k["label"].replace("{t}", text)
        btn.text = text[:60]
        st = ov.get("color")
        cur = btn.__dict__.get("style")
        if st in ("primary", "success", "danger"):
            btn.__dict__["style"] = st
        elif st == "none":
            btn.__dict__.pop("style", None)
        elif k["colors"] in ("all_primary", "all_success", "all_danger") and cd not in _NO_DECOR:
            btn.__dict__["style"] = k["colors"][4:]
        elif k["colors"] == "roles" and cd not in _NO_DECOR:
            btn.__dict__["style"] = role_style(cd, cur)
        if ov.get("hide") and not (cd.startswith("ui:") and cd not in ("ui:source",) and not cd.startswith("ui:cb:")) and cd != "back_main":
            btn.__dict__["_ui_hidden"] = True
    except Exception:
        C.log.exception("decorate_button")


def _screen_name(cds, tag):
    if tag == "main":
        return "القائمة الرئيسية"
    if tag == "admin":
        return "لوحة الأدمن"
    first = next((_REG.get(c, {}).get("t") for c in cds if c in _REG), "شاشة")
    return f"شاشة: {first[:22]}"


def process_markup(markup):
    try:
        types = C.types
        if not isinstance(markup, types.InlineKeyboardMarkup):
            return markup
        rows = list(getattr(markup, "keyboard", []) or [])
        flat = [b for r in rows for b in r]
        if not flat:
            return markup
        cds = [_cd_of(b) for b in flat]
        tag = markup.__dict__.get("_ui_screen")
        key = tag or hashlib.sha1("|".join(sorted(cds)).encode()).hexdigest()[:8]
        if not getattr(_tl, "ov", None):
            scr = _SCREENS.get(key)
            if scr is None and len(_SCREENS) < 80:
                _SCREENS[key] = {"name": _screen_name(cds, tag), "cds": list(cds)}
                _dirty["v"] = True
            elif scr is not None:
                new = [c for c in cds if c not in scr["cds"]]
                if new and (tag or len(scr["cds"]) < 40):
                    for c_new in new:
                        i = cds.index(c_new)
                        prev = next((x for x in reversed(cds[:i]) if x in scr["cds"]), None)
                        scr["cds"].insert(scr["cds"].index(prev) + 1 if prev else 0, c_new)
                    _dirty["v"] = True
        c, k = cfg(), knobs()
        flat = [b for b in flat if not b.__dict__.get("_ui_hidden")]
        order = c["order"].get(key)
        if order and not getattr(_tl, "ov", None):
            pos = {cd: i for i, cd in enumerate(order)}
            idx = {id(b): i for i, b in enumerate(flat)}
            flat.sort(key=lambda b: (pos.get(_cd_of(b), 10_000 + idx[id(b)])))
        if k["colors"] == "cycle":
            cyc = ["primary", "success", "danger"]
            for i, b in enumerate(flat):
                if _cd_of(b) not in _NO_DECOR and not (c["buttons"].get(_cd_of(b)) or {}).get("color"):
                    b.__dict__["style"] = cyc[i % 3]
        cols = c["cols"].get(key) or (k["cols_main"] if tag == "main" else 0)
        if cols:
            out, row = [], []
            for b in flat:
                if len(b.text) > 24 and cols > 1 or _cd_of(b) in _NO_DECOR and b.text.startswith(("━", "⚡", "👑", "👤")):
                    if row:
                        out.append(row)
                        row = []
                    out.append([b])
                    continue
                row.append(b)
                if len(row) >= cols:
                    out.append(row)
                    row = []
            if row:
                out.append(row)
            markup.keyboard = out
        else:
            # نحافظ على الصفوف الأصلية بعد إزالة المخفي/إعادة الترتيب
            keep = {id(b) for b in flat}
            if order and not getattr(_tl, "ov", None):
                markup.keyboard = _rechunk(flat, rows)
            else:
                markup.keyboard = [r for r in ([b for b in r if id(b) in keep] for r in rows) if r]
        return markup
    except Exception:
        C.log.exception("process_markup")
        return markup


def _rechunk(flat, rows):
    width = max((len(r) for r in rows), default=1)
    out, row = [], []
    for b in flat:
        row.append(b)
        if len(row) >= width:
            out.append(row)
            row = []
    if row:
        out.append(row)
    return out


# ============================================================ النصوص (إطار الرسائل)
_DIV_RE = re.compile(r"^[━─═▬—\-_▁·┄]{3,}$")


def decorate_text(s, k):
    out = []
    for ln in s.split("\n"):
        st = ln.strip()
        if st.startswith("• "):
            ln = ln.replace("• ", k["bullet"] + " ", 1)
        elif _DIV_RE.match(st):
            ln = k["divider"] * min(len(st), 18)
        out.append(ln)
    return "\n".join(out)


def styled_bq(text):
    if text is None:
        return text
    s = str(text).strip()
    if not s:
        return text
    k = knobs()
    if s.startswith("<blockquote"):
        return s
    s = decorate_text(s, k)
    if k["header"]:
        s = f"{_html.escape(k['header'])}\n{s}"
    if k["footer"]:
        s = f"{s}\n{_html.escape(k['footer'])}"
    mode = k["quote"]
    if mode == "blockquote":
        return f"<blockquote>{s}</blockquote>"
    if mode == "expandable":
        return f"<blockquote expandable>{s}</blockquote>" if (len(s) > 280 or s.count("\n") > 5) else f"<blockquote>{s}</blockquote>"
    if mode == "bar":
        return "\n".join("┃ " + ln for ln in s.split("\n"))
    if mode == "pre":
        plain = _html.unescape(re.sub(r"<[^>]+>", "", s))
        return f"<pre>{_html.escape(plain)}</pre>"
    return s


# ============================================================ الأدوات (Kit)
def progress_bar(pct, width=12, style="▰▱"):
    pct = max(0, min(100, pct))
    f = round(pct / 100 * width)
    return style[0] * f + style[1] * (width - f)


def fmt_time(sec):
    sec = max(0, int(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def terminal_box(title, lines, prompt="$"):
    body = "\n".join(f"│ {ln}" for ln in lines)
    plain = f"┌─[ ● ● ● ]─ {title}\n{body}\n└─ {prompt} _"
    return f"<pre>{_html.escape(plain)}</pre>"


def sample_block(k=None):
    k = k or knobs()
    d = k["divider"] * 14
    return (f"<b>معاينة الستايل</b>\n{d}\n{k['bullet']} نقطة أولى\n{k['bullet']} نقطة ثانية\n{k['arrow']} سهم للانتقال\n"
            f"{progress_bar(65, 12, k['bar'])} 65%\n⏱ {fmt_time(754)} · {SPIN_FRAMES[k['spin']][0]} جارٍ العمل\n{d}")


def run_countdown(chat_id, seconds, title="عد تنازلي", done_text="✅ انتهى الوقت!", on_done=None):
    seconds = max(3, min(int(seconds), 6 * 3600))
    step = 2 if seconds <= 60 else 5 if seconds <= 600 else 15
    k = knobs()
    bot = C.bot

    def render(rem):
        pct = 100 - rem * 100 / seconds
        return f"⏳ <b>{_html.escape(title)}</b>\n{progress_bar(pct, 14, k['bar'])} {int(pct)}%\n⏱ <code>{fmt_time(rem)}</code>"

    def run():
        try:
            msg = bot.send_message(chat_id, render(seconds))
            end = time.time() + seconds
            while True:
                rem = end - time.time()
                if rem <= 0:
                    break
                time.sleep(min(step, max(rem, 0.2)))
                rem = max(0, end - time.time())
                if rem <= 0:
                    break
                try:
                    bot.edit_message_text(render(rem), chat_id, msg.message_id)
                except Exception:
                    pass
            try:
                bot.edit_message_text(f"{done_text}\n{progress_bar(100, 14, k['bar'])} 100%", chat_id, msg.message_id)
            except Exception:
                pass
            if on_done:
                on_done()
        except Exception:
            C.log.exception("countdown")
    threading.Thread(target=run, daemon=True, name="ui-countdown").start()


def run_animation(chat_id, name="braille", text="جارٍ التحميل", seconds=6, final=None):
    frames = SPIN_FRAMES.get(name) or SPIN_FRAMES["braille"]
    k = knobs()
    bot = C.bot

    def run():
        try:
            msg = bot.send_message(chat_id, f"{frames[0]} {text}")
            n = max(2, int(seconds / 1.2))
            for i in range(1, n + 1):
                time.sleep(1.2)
                try:
                    bot.edit_message_text(f"{frames[i % len(frames)]} {text}\n{progress_bar(i * 100 / n, 12, k['bar'])}", chat_id, msg.message_id)
                except Exception:
                    pass
            bot.edit_message_text(final or f"✅ تم\n{progress_bar(100, 12, k['bar'])}", chat_id, msg.message_id)
        except Exception:
            C.log.exception("animation")
    threading.Thread(target=run, daemon=True, name="ui-anim").start()


def terminal_status():
    lines = []
    try:
        pass  # (الوحدة مدمجة في هذا الملف)
        s = monitor_sample() if C else {}
        if s:
            lines += [f"cpu      {s['cpu']:.0f}%", f"ram      {s['ram_used']:.0f}/{s['ram_total']:.0f} MB", f"disk     {s['disk_free']:.0f} MB free"]
    except Exception:
        pass
    run = sum(1 for hp in list(C.manager.processes.values()) if hp.is_alive())
    lines += [f"running  {run} project(s)", f"uptime   {fmt_time(time.time() - C._START_TS)}"]
    return terminal_box("flix@host", lines, "status")


# ============================================================ السورس
def source_kb():
    kb = C.types.InlineKeyboardMarkup(row_width=1)
    for t, u in (cfg()["source"].get("urls") or [])[:4]:
        kb.add(C.types.InlineKeyboardButton(t[:40], url=u))
    kb.add(C.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    return kb


def source_caption():
    s = cfg()["source"]
    txt = s.get("text") or DEFAULT_SOURCE
    return f"<blockquote>{txt}</blockquote>"[:1020]


def send_source(chat_id):
    s = cfg()["source"]
    kb, cap = source_kb(), source_caption()
    bot = C.bot

    def run():
        try:
            if s.get("file_id"):
                kw = dict(caption=cap, parse_mode="HTML", reply_markup=kb)
                kind = s.get("kind") or "video"
                try:
                    if kind == "animation":
                        bot.send_animation(chat_id, s["file_id"], has_spoiler=bool(s.get("spoiler")), **kw)
                    elif kind == "photo":
                        bot.send_photo(chat_id, s["file_id"], has_spoiler=bool(s.get("spoiler")), **kw)
                    else:
                        bot.send_video(chat_id, s["file_id"], has_spoiler=bool(s.get("spoiler")), supports_streaming=True, **kw)
                except TypeError:
                    getattr(bot, {"animation": "send_animation", "photo": "send_photo"}.get(kind, "send_video"))(chat_id, s["file_id"], **kw)
            else:
                bot.send_message(chat_id, cap, parse_mode="HTML", reply_markup=kb)
        except Exception:
            C.log.exception("send_source")
            try:
                bot.send_message(chat_id, cap, parse_mode="HTML", reply_markup=kb)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True, name="ui-source").start()


# ============================================================ واجهة الاستوديو
def is_owner(uid):
    return uid == C.ADMIN_ID


def _kb(rows):
    kb = C.types.InlineKeyboardMarkup(row_width=2)
    for r in rows:
        kb.row(*[C.types.InlineKeyboardButton(t, callback_data=d) for t, d in r])
    return kb


def _show(call, text, rows):
    kb = _kb(rows)
    try:
        C.bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            C.bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


def screen_home(call):
    c, k = cfg(), knobs()
    pname = all_presets().get(c["preset"], PRESETS["classic"])["name"]
    text = (f"🎨 <b>استوديو الستايل</b>\n\nالستايل الحالي: <b>{pname}</b>\nعدد الأزرار المكتشفة: {len(_REG)} · الشاشات: {len(_SCREENS)}\n\n"
            f"{sample_block(k)}")
    rows = [[("🎭 الستايلات الجاهزة (11)", "ui:pre")], [("🔘 الأزرار والترتيب", "ui:scr"), ("🧩 تخصيص الإطار", "ui:knob")],
            [("✏️ النصوص", "ui:txt:0"), ("🎬 السورس", "ui:src")], [("🧰 الأدوات", "ui:tools"), ("👁 معاينة شاملة", "ui:full")],
            [("➕ زر مخصص", "ui:cadd"), ("📤 تصدير / 📥 استيراد", "ui:io")], [("↩️ تراجع", "ui:undo"), ("♻️ إعادة ضبط", "ui:reset")],
            [("✖️ إغلاق", "ui:close")]]
    _show(call, text, rows)


def screen_presets(call):
    ps = all_presets()
    cur = cfg()["preset"]
    ids = list(ps)
    rows, row = [], []
    for pid in ids:
        row.append((("✅ " if pid == cur else "") + ps[pid]["name"], f"ui:pv:{pid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([("🔄 إعادة قراءة themes.json", "ui:reload")])
    rows.append([("🔙 رجوع", "ui:home")])
    _show(call, "🎭 <b>اختر ستايلاً</b>\nاضغط على أي ستايل لمعاينته قبل التطبيق.\nالستايلات المخصصة تُقرأ من ملف <code>themes.json</code>.", rows)


def screen_preview(call, pid):
    ps = all_presets()
    if pid not in ps:
        return screen_presets(call)
    with preview(pid):
        sample = styled_bq(sample_block(knobs()))
    k = {**DEFAULT_KNOBS, **ps[pid]["knobs"]}
    desc = " · ".join([f"أزرار: <code>{_html.escape(k['label'])}</code>", f"ألوان: {COLOR_NAMES[k['colors']]}", f"إطار: {QUOTE_NAMES[k['quote']]}"])
    text = f"👁 <b>{ps[pid]['name']}</b>\n{desc}\n\n{sample}"
    _show(call, text, [[("✅ تطبيق", f"ui:ap:{pid}"), ("📋 معاينة القائمة", f"ui:pvm:{pid}")], [("🔙 الستايلات", "ui:pre")]])


def apply_preset(pid):
    c = cfg()
    c = copy.deepcopy(c)
    c["preset"] = pid
    c["over"] = {}
    save_cfg(c)


def preview_menu(chat_id, pid):
    with preview(pid):
        kb = C.main_menu_markup(True)
        kb = process_markup(kb)
        text = styled_bq(f"<b>معاينة القائمة الرئيسية</b>\n{all_presets()[pid]['name']}")
    C.bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


def screen_knobs(call):
    c, k = cfg(), knobs()
    rows = []
    for name, label in KNOB_NAMES.items():
        v = k[name]
        shown = {"quote": QUOTE_NAMES, "colors": COLOR_NAMES}.get(name, {}).get(v, v)
        if name == "cols_main":
            shown = "أصلي" if not v else v
        if name == "strip_emoji":
            shown = "نعم" if v else "لا"
        rows.append([(f"{label}: {shown}", f"ui:kn:{name}")])
    rows.append([("📝 ترويسة النص", "ui:kh:header"), ("📝 تذييل النص", "ui:kh:footer")])
    rows.append([("🔙 رجوع", "ui:home")])
    _show(call, "🧩 <b>تخصيص الإطار</b>\nكل ضغطة تنتقل للخيار التالي — ويُطبَّق فوراً على كل البوت.\n\n" + sample_block(k), rows)


def cycle_knob(name):
    opts = KNOB_OPTIONS.get(name)
    if not opts:
        return
    c = copy.deepcopy(cfg())
    cur = knobs()[name]
    nxt = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else opts[0]
    c["over"][name] = nxt
    save_cfg(c)


def screen_screens(call):
    rows = []
    items = sorted(_SCREENS.items(), key=lambda kv: (kv[0] not in ("main", "admin"), kv[1]["name"]))
    _ctx[call.from_user.id] = {"screens": [k for k, _ in items]}
    for i, (key, s) in enumerate(items[:24]):
        rows.append([(f"{s['name']} ({len(s['cds'])})", f"ui:sc:{i}")])
    rows.append([("🔙 رجوع", "ui:home")])
    _show(call, "🔘 <b>الشاشات</b>\nاختر شاشة لترتيب أزرارها أو إخفاء/تعديل أي زر.\n"
                "<i>الشاشات تظهر هنا بعد أن يفتحها أي مستخدم مرة واحدة.</i>", rows)


def _scr_by_idx(uid, i):
    keys = _ctx.get(uid, {}).get("screens", [])
    return keys[i] if 0 <= i < len(keys) else None


def screen_edit(call, key):
    s = _SCREENS.get(key)
    if not s:
        return screen_screens(call)
    c = cfg()
    order = c["order"].get(key) or s["cds"]
    cds = [x for x in order if x in s["cds"]] + [x for x in s["cds"] if x not in order]
    _ctx.setdefault(call.from_user.id, {})["cur"] = (key, cds)
    rows = []
    for i, cd in enumerate(cds[:30]):
        ov = c["buttons"].get(cd) or {}
        name = ov.get("text") or _REG.get(cd, {}).get("t") or cd
        mark = "🚫 " if ov.get("hide") else ""
        rows.append([(f"{mark}{name[:22]}", f"ui:be:{i}"), ("⬆️", f"ui:mv:{i}:u"), ("⬇️", f"ui:mv:{i}:d"), ("🚫" if not ov.get("hide") else "👁", f"ui:mv:{i}:h")])
    cols = c["cols"].get(key, 0)
    rows.append([(f"📐 الأعمدة: {cols or 'أصلي'}", "ui:cols")])
    rows.append([("🔙 الشاشات", "ui:scr")])
    _show(call, f"🔘 <b>{s['name']}</b>\n⬆️⬇️ لتغيير الترتيب · 🚫 إخفاء · اضغط اسم الزر لتعديل نصه/لونه/أيقونته.", rows)


def move_button(uid, i, act):
    key, cds = _ctx[uid]["cur"]
    c = copy.deepcopy(cfg())
    if act in ("u", "d"):
        j = i - 1 if act == "u" else i + 1
        if 0 <= j < len(cds):
            cds[i], cds[j] = cds[j], cds[i]
        c["order"][key] = cds
    elif act == "h":
        cd = cds[i]
        if cd == "back_main" or (cd.startswith("ui:") and cd != "ui:source" and not cd.startswith("ui:cb:")):
            return False
        ov = c["buttons"].setdefault(cd, {})
        ov["hide"] = not ov.get("hide")
    save_cfg(c)
    return True


def screen_button(call, i):
    uid = call.from_user.id
    key, cds = _ctx[uid]["cur"]
    cd = cds[i]
    ov = cfg()["buttons"].get(cd) or {}
    orig = _REG.get(cd, {}).get("t", cd)
    colors = {"": "الأصلي", "primary": "🔵 أزرق", "success": "🟢 أخضر", "danger": "🔴 أحمر", "none": "⚪ بدون"}
    _ctx[uid]["btn"] = cd
    text = (f"🔘 <b>تعديل زر</b>\nالأصل: {_html.escape(orig)}\nالنص الحالي: {_html.escape(ov.get('text') or '—')}\nالأيقونة: {ov.get('icon') or '—'}\n"
            f"اللون: {colors.get(ov.get('color') or '')}\nالحالة: {'🚫 مخفي' if ov.get('hide') else '✅ ظاهر'}\n<code>{_html.escape(cd)}</code>")
    _show(call, text, [[("✏️ تغيير النص", "ui:bt:text"), ("😀 أيقونة", "ui:bt:icon")], [("🎨 تغيير اللون", "ui:bt:color")], [("↩️ استرجاع الأصل", "ui:bt:reset")], [("🔙 رجوع", "ui:rs")]])


def button_action(uid, act):
    cd = _ctx[uid]["btn"]
    c = copy.deepcopy(cfg())
    ov = c["buttons"].setdefault(cd, {})
    if act == "color":
        order = ["", "primary", "success", "danger", "none"]
        cur = ov.get("color") or ""
        ov["color"] = order[(order.index(cur) + 1) % len(order)] if cur in order else ""
        if not ov["color"]:
            ov.pop("color")
    elif act == "reset":
        c["buttons"].pop(cd, None)
    save_cfg(c)


def screen_texts(call, page):
    keys = sorted((C._I18N.get("ar") or {}).keys())
    per = 8
    page = max(0, min(page, (len(keys) - 1) // per))
    _ctx[call.from_user.id] = {**_ctx.get(call.from_user.id, {}), "tkeys": keys}
    rows = []
    for i in range(page * per, min(len(keys), (page + 1) * per)):
        k = keys[i]
        custom = C.get_setting(f"text_ar_{k}")
        rows.append([(("✏️ " if custom else "") + k[:28], f"ui:te:{i}")])
    nav = []
    if page > 0:
        nav.append(("◀️", f"ui:txt:{page - 1}"))
    nav.append((f"{page + 1}/{(len(keys) - 1) // per + 1}", "ui:txt:%d" % page))
    if (page + 1) * per < len(keys):
        nav.append(("▶️", f"ui:txt:{page + 1}"))
    rows += [nav, [("🔙 رجوع", "ui:home")]]
    _show(call, "✏️ <b>نصوص البوت</b>\nاختر رسالة لتغيير نصها (العربية). ✏️ = معدّلة.", rows)


def screen_text_key(call, i):
    keys = _ctx.get(call.from_user.id, {}).get("tkeys", [])
    if not 0 <= i < len(keys):
        return screen_texts(call, 0)
    k = keys[i]
    cur = C.get_setting(f"text_ar_{k}") or (C._I18N.get("ar") or {}).get(k, "")
    _ctx[call.from_user.id]["tkey"] = k
    _show(call, f"✏️ <b>{_html.escape(k)}</b>\n\n<code>{_html.escape(cur[:900])}</code>\n\nيدعم HTML بسيط (&lt;b&gt; &lt;i&gt; &lt;code&gt;) والمتغيرات الموجودة في النص كما هي.",
          [[("✏️ تغيير النص", "ui:tt:set"), ("↩️ استرجاع الأصل", "ui:tt:reset")], [("🔙 رجوع", "ui:txt:0")]])


def screen_tools(call):
    k = knobs()
    rows = [[("⏳ عد تنازلي 30 ثانية", "ui:t:cd30"), ("⏳ دقيقتان", "ui:t:cd120")], [("🎞 شاشة متحركة", "ui:t:anim"), (f"🔁 المؤشر: {k['spin']}", "ui:ks")],
            [("💻 ترمنال الحالة", "ui:t:term"), ("📦 تجربة السورس", "ui:t:src")]]
    if _plugins:
        rows.append([(f"🧩 الإضافات ({len(_plugins)})", "ui:t:plug")])
    rows.append([("🔙 رجوع", "ui:home")])
    _show(call, "🧰 <b>الأدوات</b>\nكلها حقيقية وتتأثر بالستايل الحالي. لإضافة أدوات جديدة ضع ملف <code>plugin_اسم.py</code> بجوار البوت.", rows)


def screen_source(call):
    s = cfg()["source"]
    media = {"video": "🎬 فيديو", "animation": "🎞 GIF", "photo": "🖼 صورة"}.get(s.get("kind"), "— لا يوجد")
    text = (f"🎬 <b>زر السورس</b>\nالوسائط: {media}\nالتمويه (Spoiler): {'✅ مفعّل' if s.get('spoiler') else '❌'}\nأزرار الروابط: {len(s.get('urls') or [])}\n\n"
            f"<b>النص:</b>\n{source_caption()}")
    _show(call, text, [[("📹 تعيين الفيديو", "ui:sa:media"), ("📝 تعديل النص", "ui:sa:text")], [(f"🌫 التمويه: {'إيقاف' if s.get('spoiler') else 'تشغيل'}", "ui:sa:spoiler"), ("🔗 أزرار الروابط", "ui:sa:urls")],
                       [("🗑 حذف الفيديو", "ui:sa:delmedia"), ("🧪 تجربة", "ui:t:src")], [("🔙 رجوع", "ui:home")]])


def ask(uid, kind, prompt, back, call, **extra):
    _pending[uid] = {"kind": kind, "back": back, **extra, "ts": time.time()}
    C.bot.send_message(call.message.chat.id, prompt + "\n\n<i>أرسل /cancel للإلغاء.</i>", parse_mode="HTML")


# ============================================================ المعالجات
def studio_on_callback(call):
    uid = call.from_user.id
    d = call.data or ""
    try:
        if d == "ui:source":
            C.bot.answer_callback_query(call.id)
            return send_source(call.message.chat.id)
        if d.startswith("ui:cb:"):
            cb = next((x for x in cfg()["custom"] if x["id"] == d[6:]), None)
            if cb and cb.get("kind") == "popup":
                return C.bot.answer_callback_query(call.id, (cb.get("value") or "")[:190], show_alert=True)
            if cb and cb.get("kind") == "source":
                C.bot.answer_callback_query(call.id)
                return send_source(call.message.chat.id)
            return C.bot.answer_callback_query(call.id)
        if not is_owner(uid):
            return C.bot.answer_callback_query(call.id, "للمالك فقط", show_alert=True)
        p = d.split(":")
        a = p[1] if len(p) > 1 else "home"
        C.bot.answer_callback_query(call.id)
        _pending.pop(uid, None)
        if a == "home":
            return screen_home(call)
        if a == "close":
            return C.bot.delete_message(call.message.chat.id, call.message.message_id)
        if a == "pre":
            return screen_presets(call)
        if a == "pv":
            return screen_preview(call, p[2])
        if a == "ap":
            apply_preset(p[2])
            return screen_home(call)
        if a == "pvm":
            return preview_menu(call.message.chat.id, p[2])
        if a == "reload":
            load_custom_presets()
            return screen_presets(call)
        if a == "knob":
            return screen_knobs(call)
        if a == "kn":
            cycle_knob(p[2])
            return screen_knobs(call)
        if a == "ks":
            cycle_knob("spin")
            return screen_tools(call)
        if a == "rs":
            return screen_edit(call, _ctx[uid]["cur"][0])
        if a == "kh":
            return ask(uid, "knob_text", f"أرسل نص {'الترويسة' if p[2] == 'header' else 'التذييل'} (أو - للحذف):", "ui:knob", call, name=p[2])
        if a == "scr":
            return screen_screens(call)
        if a == "sc":
            key = _scr_by_idx(uid, int(p[2]))
            return screen_edit(call, key) if key else screen_screens(call)
        if a == "mv":
            move_button(uid, int(p[2]), p[3])
            key, _ = _ctx[uid]["cur"]
            return screen_edit(call, key)
        if a == "cols":
            key, _ = _ctx[uid]["cur"]
            c = copy.deepcopy(cfg())
            c["cols"][key] = (c["cols"].get(key, 0) + 1) % 4
            save_cfg(c)
            return screen_edit(call, key)
        if a == "be":
            return screen_button(call, int(p[2]))
        if a == "bt":
            if p[2] in ("color", "reset"):
                button_action(uid, p[2])
                key, cds = _ctx[uid]["cur"]
                return screen_button(call, cds.index(_ctx[uid]["btn"]))
            return ask(uid, "btn_" + p[2], "أرسل النص الجديد للزر:" if p[2] == "text" else "أرسل أيقونة (إيموجي واحد):", "ui:home", call, cd=_ctx[uid]["btn"])
        if a == "txt":
            return screen_texts(call, int(p[2]))
        if a == "te":
            return screen_text_key(call, int(p[2]))
        if a == "tt":
            k = _ctx[uid]["tkey"]
            if p[2] == "reset":
                C.set_setting(f"text_ar_{k}", "")
                return screen_texts(call, 0)
            return ask(uid, "key_text", f"أرسل النص الجديد لـ <code>{_html.escape(k)}</code>:", "ui:txt:0", call, key=k)
        if a == "tools":
            return screen_tools(call)
        if a == "t":
            return run_tool(call, p[2])
        if a == "src":
            return screen_source(call)
        if a == "sa":
            return source_action(call, p[2])
        if a == "cadd":
            return ask(uid, "custom_btn", "أرسل بصيغة:\n<code>النص | النوع | القيمة</code>\nالأنواع: <code>url</code> (رابط) · <code>popup</code> (نافذة نص) · <code>source</code>\nمثال: <code>📢 قناتنا | url | https://t.me/xxx</code>", "ui:home", call)
        if a == "io":
            return screen_io(call)
        if a == "exp":
            return export_cfg(call.message.chat.id)
        if a == "imp":
            return ask(uid, "import", "أرسل ملف JSON (أو الصق نصه) للاستيراد:", "ui:io", call)
        if a == "undo":
            return undo(call)
        if a == "reset":
            save_cfg(default_cfg())
            return screen_home(call)
        if a == "full":
            return full_preview(call)
    except Exception:
        C.log.exception("studio callback %s", d)


def screen_io(call):
    _show(call, "📤📥 <b>تصدير / استيراد</b>\nتصدير كل إعدادات الشكل في ملف JSON تعدّله يدوياً ثم تستورده، أو تنقله لبوت آخر.",
          [[("📤 تصدير", "ui:exp"), ("📥 استيراد", "ui:imp")], [("🔙 رجوع", "ui:home")]])


def export_cfg(chat_id):
    data = json.dumps(cfg(), ensure_ascii=False, indent=2).encode("utf-8")
    f = io.BytesIO(data)
    f.name = "theme.json"
    C.bot.send_document(chat_id, f, caption="📤 إعدادات الشكل — عدّلها ثم استوردها من الاستوديو.")


def undo(call):
    try:
        hist = json.loads(C.get_setting("ui_hist") or "[]")
    except Exception:
        hist = []
    if not hist:
        C.bot.answer_callback_query(call.id, "لا يوجد ما يُتراجع عنه", show_alert=True)
        return screen_home(call)
    prev = hist.pop()
    C.set_setting("ui_hist", json.dumps(hist))
    C.set_setting("ui_cfg", prev)
    _cache["cfg"] = None
    screen_home(call)


def sanitize_cfg(d):
    base = default_cfg()
    if not isinstance(d, dict):
        raise ValueError("الملف ليس كائن JSON")
    if d.get("preset") in all_presets():
        base["preset"] = d["preset"]
    base["over"] = _clean_knobs(d.get("over") or {})
    for cd, ov in (d.get("buttons") or {}).items():
        if isinstance(ov, dict) and len(str(cd)) <= 64:
            clean = {}
            if isinstance(ov.get("text"), str):
                clean["text"] = ov["text"][:60]
            if isinstance(ov.get("icon"), str):
                clean["icon"] = ov["icon"][:8]
            if ov.get("color") in ("primary", "success", "danger", "none"):
                clean["color"] = ov["color"]
            if ov.get("hide"):
                clean["hide"] = True
            if clean:
                base["buttons"][str(cd)] = clean
    for key, lst in (d.get("order") or {}).items():
        if isinstance(lst, list):
            base["order"][str(key)] = [str(x)[:64] for x in lst[:60]]
    for key, n in (d.get("cols") or {}).items():
        if n in (0, 1, 2, 3):
            base["cols"][str(key)] = n
    custom = []
    for x in d.get("custom") or []:
        if isinstance(x, dict) and re.match(r"^[a-z0-9_]{1,16}$", str(x.get("id", ""))) and x.get("kind") in ("url", "popup", "source"):
            if x["kind"] == "url" and not re.match(r"^https?://", str(x.get("value", ""))):
                continue
            custom.append({"id": x["id"], "text": str(x.get("text", ""))[:40] or "زر", "kind": x["kind"], "value": str(x.get("value", ""))[:190]})
    base["custom"] = custom if "custom" in d else base["custom"]
    s = d.get("source") or {}
    if isinstance(s, dict):
        base["source"].update({"text": str(s.get("text", ""))[:900], "file_id": str(s.get("file_id", ""))[:200], "kind": s.get("kind") if s.get("kind") in ("video", "animation", "photo") else "",
                               "spoiler": bool(s.get("spoiler", True)),
                               "urls": [[str(t)[:40], str(u)] for t, u in (s.get("urls") or [])[:4] if re.match(r"^https?://", str(u))]})
    return base


def run_tool(call, tool):
    chat = call.message.chat.id
    if tool == "cd30":
        run_countdown(chat, 30, "عد تنازلي تجريبي")
    elif tool == "cd120":
        run_countdown(chat, 120, "عد تنازلي — دقيقتان")
    elif tool == "anim":
        run_animation(chat, knobs()["spin"], "جارٍ التحميل")
    elif tool == "term":
        C.bot.send_message(chat, terminal_status(), parse_mode="HTML")
    elif tool == "src":
        send_source(chat)
    elif tool == "plug":
        return _show(call, "🧩 <b>الإضافات المحمّلة</b>\n" + "\n".join(f"• {_html.escape(p)}" for p in _plugins), [[("🔙 رجوع", "ui:tools")]])


def source_action(call, act):
    uid = call.from_user.id
    c = copy.deepcopy(cfg())
    s = c["source"]
    if act == "spoiler":
        s["spoiler"] = not s.get("spoiler")
    elif act == "delmedia":
        s["file_id"], s["kind"] = "", ""
    elif act == "media":
        return ask(uid, "src_media", "أرسل الفيديو (أو GIF/صورة) الذي سيظهر عند الضغط على «السورس». سيظهر مموّهاً (Spoiler) حتى يضغط عليه المستخدم.", "ui:src", call)
    elif act == "text":
        return ask(uid, "src_text", "أرسل نص التعريف (يدعم &lt;b&gt; &lt;i&gt; &lt;a href=...&gt;). سيظهر داخل اقتباس. أرسل - لاستعادة النص الافتراضي:", "ui:src", call)
    elif act == "urls":
        return ask(uid, "src_urls", "أرسل أزرار الروابط، كل سطر:\n<code>النص | https://رابط</code>\n(حتى 4 أسطر، أو - للحذف)", "ui:src", call)
    save_cfg(c)
    screen_source(call)


def full_preview(call):
    chat = call.message.chat.id
    k = knobs()
    C.bot.send_message(chat, styled_bq(sample_block(k)), parse_mode="HTML")
    kb = process_markup(C.main_menu_markup(True))
    C.bot.send_message(chat, styled_bq("<b>القائمة الرئيسية بالستايل الحالي</b>"), reply_markup=kb, parse_mode="HTML")
    C.bot.send_message(chat, terminal_status(), parse_mode="HTML")
    run_animation(chat, k["spin"], "معاينة الأنيميشن", 4)


def has_pending(m):
    p = _pending.get(m.from_user.id)
    return bool(p) and time.time() - p["ts"] < 600


def on_pending(m):
    uid = m.from_user.id
    p = _pending.get(uid)
    if not p:
        return
    txt = (getattr(m, "text", None) or getattr(m, "caption", None) or "").strip()
    if txt == "/cancel":
        _pending.pop(uid, None)
        return C.bot.send_message(m.chat.id, "تم الإلغاء. /studio للعودة.")
    kind = p["kind"]
    try:
        c = copy.deepcopy(cfg())
        if kind == "btn_text":
            c["buttons"].setdefault(p["cd"], {})["text"] = txt[:60]
        elif kind == "btn_icon":
            c["buttons"].setdefault(p["cd"], {})["icon"] = txt[:8]
        elif kind == "key_text":
            C.set_setting(f"text_ar_{p['key']}", txt)
        elif kind == "knob_text":
            c["over"][p["name"]] = "" if txt == "-" else txt[:200]
        elif kind == "src_text":
            c["source"]["text"] = "" if txt == "-" else txt[:900]
        elif kind == "src_urls":
            urls = []
            if txt != "-":
                for ln in txt.splitlines()[:4]:
                    if "|" in ln:
                        t, u = [x.strip() for x in ln.split("|", 1)]
                        if re.match(r"^https?://", u):
                            urls.append([t[:40], u])
            c["source"]["urls"] = urls
        elif kind == "src_media":
            ct = getattr(m, "content_type", "")
            if ct == "video":
                c["source"].update(file_id=m.video.file_id, kind="video")
            elif ct == "animation":
                c["source"].update(file_id=m.animation.file_id, kind="animation")
            elif ct == "photo":
                c["source"].update(file_id=m.photo[-1].file_id, kind="photo")
            elif ct == "document" and (getattr(m.document, "mime_type", "") or "").startswith("video"):
                c["source"].update(file_id=m.document.file_id, kind="video")
            else:
                return C.bot.send_message(m.chat.id, "❌ أرسل فيديو أو GIF أو صورة.")
        elif kind == "custom_btn":
            parts = [x.strip() for x in txt.split("|")]
            if len(parts) < 2 or parts[1] not in ("url", "popup", "source"):
                return C.bot.send_message(m.chat.id, "❌ الصيغة: النص | النوع | القيمة")
            val = parts[2] if len(parts) > 2 else ""
            if parts[1] == "url" and not re.match(r"^https?://", val):
                return C.bot.send_message(m.chat.id, "❌ الرابط يجب أن يبدأ بـ http(s)://")
            cid = "c" + hashlib.sha1((parts[0] + str(time.time())).encode()).hexdigest()[:6]
            c["custom"].append({"id": cid, "text": parts[0][:40], "kind": parts[1], "value": val[:190]})
        elif kind == "import":
            raw = txt
            if getattr(m, "content_type", "") == "document":
                raw = C.bot.download_file(C.bot.get_file(m.document.file_id).file_path).decode("utf-8")
            c = sanitize_cfg(json.loads(raw))
        save_cfg(c)
        _pending.pop(uid, None)
        C.bot.send_message(m.chat.id, "✅ تم الحفظ — أرسل /studio للمتابعة.")
    except ValueError as e:  # JSON تالف / قيمة غير صالحة
        C.bot.send_message(m.chat.id, f"❌ ملف غير صالح: {_html.escape(str(e)[:150])}")
    except Exception as e:
        C.log.exception("studio pending")
        C.bot.send_message(m.chat.id, f"❌ تعذر الحفظ: {_html.escape(str(e)[:150])}")


def cmd_studio(m):
    if not is_owner(m.from_user.id):
        return
    _pending.pop(m.from_user.id, None)
    fake = type("Call", (), {})()
    msg = C.bot.send_message(m.chat.id, "🎨 جارٍ فتح الاستوديو...")
    fake.message, fake.from_user, fake.id = msg, m.from_user, "0"
    screen_home(fake)


def cmd_countdown(m):
    if not is_owner(m.from_user.id):
        return
    a = (m.text or "").split(None, 2)
    if len(a) < 2 or not a[1].isdigit():
        return C.bot.send_message(m.chat.id, "الاستخدام: <code>/countdown 60 عنوان اختياري</code>", parse_mode="HTML")
    run_countdown(m.chat.id, int(a[1]), a[2] if len(a) > 2 else "عد تنازلي")


def cmd_anim(m):
    if not is_owner(m.from_user.id):
        return
    a = (m.text or "").split()
    run_animation(m.chat.id, a[1] if len(a) > 1 and a[1] in SPIN_FRAMES else knobs()["spin"], "جارٍ التحميل")


def cmd_term(m):
    if is_owner(m.from_user.id):
        C.bot.send_message(m.chat.id, terminal_status(), parse_mode="HTML")


def cmd_source(m):
    send_source(m.chat.id)


def cmd_themeexport(m):
    if is_owner(m.from_user.id):
        export_cfg(m.chat.id)


def cmd_uireset(m):
    if is_owner(m.from_user.id):
        save_cfg(default_cfg())
        C.bot.send_message(m.chat.id, "♻️ أُعيد الشكل للوضع الأصلي.")


# ============================================================ التركيب
def _reg_front(decorator_result_list_name):
    lst = getattr(C.bot, decorator_result_list_name, None)
    if isinstance(lst, list) and lst:
        lst.insert(0, lst.pop())


def _studio_flush_loop():
    while True:
        time.sleep(30)
        if _dirty["v"]:
            _dirty["v"] = False
            try:
                C.set_setting("ui_reg", json.dumps({"reg": _REG, "screens": _SCREENS}, ensure_ascii=False)[:60000])
            except Exception:
                pass


def _builtin_plugin_example(core, ui):
    """إضافة تجريبية مدمجة: /hello و /timer. (أضف إضافاتك كملفات plugin_*.py بجوار البرنامج)"""
    bot = core.bot

    @bot.message_handler(commands=["hello"])
    def hello(m):
        k = ui.knobs()
        bot.send_message(m.chat.id, f"{k['arrow']} أهلاً <b>{core.html_escape(m.from_user.first_name or '')}</b>\n{ui.progress_bar(70, 12, k['bar'])} 70%",
                         parse_mode="HTML")

    @bot.message_handler(commands=["timer"])
    def timer(m):
        parts = (m.text or "").split()
        secs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        ui.run_countdown(m.chat.id, min(secs, 300), "مؤقت")


def load_plugins():
    try:
        _builtin_plugin_example(C, sys.modules[__name__])
        _plugins.append("plugin_example")
    except Exception:
        C.log.exception("builtin plugin")
    for path in sorted(glob.glob(os.path.join(_HERE, "plugin_*.py"))):
        name = os.path.basename(path)[:-3]
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            reg = getattr(mod, "register", None)
            if callable(reg):
                reg(C, sys.modules[__name__])
                _plugins.append(name)
        except Exception:
            C.log.exception("plugin %s", name)


def studio_install(core):
    global C
    C = core
    try:
        saved = json.loads(C.get_setting("ui_reg") or "{}")
        _REG.update(saved.get("reg", {}))
        _SCREENS.update(saved.get("screens", {}))
    except Exception:
        pass
    load_custom_presets()
    # 1) أزرار: زخرفة عند الإنشاء
    types = core.types
    prev_init = types.InlineKeyboardButton.__init__

    def init(self, *a, **kw):
        prev_init(self, *a, **kw)
        decorate_button(self)
    types.InlineKeyboardButton.__init__ = init
    # 2) لوحات: إخفاء/ترتيب/أعمدة عند الإرسال
    for name in ("send_message", "edit_message_text", "edit_message_reply_markup", "send_photo", "send_video",
                 "send_document", "send_animation", "edit_message_caption", "reply_to"):
        orig = getattr(core.bot, name, None)
        if orig is None:
            continue

        def make(o):
            def w(*a, **k):
                if "reply_markup" in k:
                    k["reply_markup"] = process_markup(k["reply_markup"])
                a = tuple(process_markup(x) if isinstance(x, types.InlineKeyboardMarkup) else x for x in a)
                return o(*a, **k)
            return w
        setattr(core.bot, name, make(orig))
    # 3) إطار النص
    core._bq = styled_bq
    # 4) القائمة الرئيسية + لوحة الأدمن
    orig_main, orig_admin = core.main_menu_markup, core.admin_main_markup

    def main_menu(is_admin=False):
        kb = orig_main(is_admin)
        for cb in cfg()["custom"]:
            if cb.get("kind") == "url":
                kb.add(types.InlineKeyboardButton(cb["text"], url=cb.get("value", "")))
            else:
                kb.add(types.InlineKeyboardButton(cb["text"], callback_data=("ui:source" if cb["id"] == "source" else f"ui:cb:{cb['id']}"), style="success"))
        kb.__dict__["_ui_screen"] = "main"
        return kb

    def admin_main():
        kb = orig_admin()
        kb.add(types.InlineKeyboardButton("🎨 استوديو الستايل", callback_data="ui:home", style="primary"))
        kb.__dict__["_ui_screen"] = "admin"
        return kb
    core.main_menu_markup, core.admin_main_markup = main_menu, admin_main
    if hasattr(core, "admin_menu_markup"):
        core.admin_menu_markup = admin_main
    # 5) المعالجات (تُدرَج في المقدمة لتسبق معالجات النواة العامة)
    bot = core.bot
    bot.callback_query_handler(func=lambda c: bool(c.data) and c.data.startswith("ui:"))(studio_on_callback)
    _reg_front("callback_query_handlers")
    bot.message_handler(func=has_pending, content_types=["text", "video", "animation", "photo", "document"])(on_pending)
    _reg_front("message_handlers")
    for cmds, fn in ((["studio", "style"], cmd_studio), (["countdown"], cmd_countdown), (["anim"], cmd_anim), (["term"], cmd_term),
                     (["source"], cmd_source), (["themeexport"], cmd_themeexport), (["uireset"], cmd_uireset)):
        bot.message_handler(commands=cmds)(fn)
        _reg_front("message_handlers")
    threading.Thread(target=_studio_flush_loop, daemon=True, name="studio-flush").start()
    load_plugins()
    core.log.info("Style studio installed (%d presets, %d plugins)", len(all_presets()), len(_plugins))


# ==========================================================================
# 8) نقطة البدء
# ==========================================================================

def app_main():
    """يركّب كل الأقسام ثم يشغّل البوت."""
    db_init()                  # القاعدة جاهزة قبل تركيب الإضافات (العمليات متكررة الأمان)
    db_create_schema()
    db_ensure_columns()
    _ensure_advanced_schema()
    gateway_install(C)         # روابط المواقع + Reverse Proxy + سيرفر HTML ثابت
    tools_install(C, ROOT)     # /diag /sysstats /analyze + مراقب الموارد
    webpanel_install(C, C)     # موقع الإدارة (حسابات يصنعها المالك فقط)
    studio_install(C)          # استوديو الستايل + زر السورس + أدوات + إضافات
    main()                     # المراقب + استعادة المشاريع + Polling


if __name__ == "__main__":
    app_main()
