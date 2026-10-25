"""Small offline reference for V4.0 concepts, not the private production chain."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from time import perf_counter
from samples import CASES


class Rejected(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_draft(text):
    # Deliberately narrow public illustration, not a comprehensive safety verifier.
    blocked = ("保证退款", "立即到账", "已退款", "包治", "治愈", "100%有效")
    return [word for word in blocked if word in text]


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, sid TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS contexts(sid TEXT PRIMARY KEY, analysis_id TEXT);
                CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, sid TEXT, analysis_id TEXT, kind TEXT, text TEXT);
                CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, fingerprint TEXT, response TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def analyze(self, sid, upto=None):
        trace = []
        def step(name, action):
            started = perf_counter()
            result = action()
            trace.append({"step": name, "elapsed_ms": round((perf_counter()-started)*1000, 3), "source": "local_rules"})
            return result

        item = next((item for item in CASES if item["id"] == sid), None)
        if not item:
            raise Rejected("NOT_FOUND", "请选择公开合成会话。", 404)
        limit = len(item["messages"]) if upto is None else upto
        if type(limit) is not int or not 1 <= limit <= len(item["messages"]):
            raise Rejected("INVALID_CUTOFF", "消息时点超出当前会话范围。")
        messages = step("读取白名单输入", lambda: [dict(message) for message in item["messages"] if message["seq"] <= limit])
        evidence = step("筛选时点证据", lambda: [dict(row) for row in item["evidence"] if row["available_seq"] <= limit])
        service = step("选择服务路径", lambda: item["service"])
        gaps = step("列出核验缺口", lambda: list(item["missing"]))
        draft = step("准备候选草稿", lambda: item["draft"] if limit == len(item["messages"]) else "已记录当前问题。现有时点资料不足，请先核对记录，再由人工确认下一步。")
        problems = step("校验公开示例规则", lambda: validate_draft(draft))
        # Hash covers visible context, independent of transient measured timings.
        context = {"sid": sid, "upto_seq": limit, "messages": messages, "evidence": evidence, "draft": draft, "version": "4.0-public-reference"}
        analysis_id = digest(context)[:24]
        result = {**context, "analysis_id": analysis_id, "service": service, "risk": item["risk"],
                  "missing": gaps, "trace": trace, "verifier": "blocked" if problems else "pass",
                  "required_checks": ["evidence", "safe_text"] if item["risk"] == "高风险" else [],
                  "source_ticket": item["source_ticket"], "local_only": True, "synthetic": True,
                  "no_execution": True, "model_calls": 0, "delivery_status": "not_sent"}
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO analyses VALUES(?,?,?)", (analysis_id, sid, encoded(result)))
            db.execute("INSERT OR REPLACE INTO contexts VALUES(?,?)", (sid, analysis_id))
        return result

    def feedback(self, key, request):
        if not isinstance(key, str) or not key.strip() or len(key) > 160:
            raise Rejected("KEY_REQUIRED", "反馈必须提供有效幂等键。")
        if not isinstance(request, dict):
            raise Rejected("INVALID_REQUEST", "请求必须是 JSON 对象。")
        fingerprint = digest(request)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT fingerprint,response FROM requests WHERE key=?", (key,)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise Rejected("IDEMPOTENCY_CONFLICT", "同一请求标识已用于不同内容，请重新确认。", 409)
                return {**json.loads(previous[1]), "replayed": True}
            row = db.execute("SELECT sid,payload FROM analyses WHERE id=?", (request.get("analysis_id"),)).fetchone()
            if not row:
                raise Rejected("ANALYSIS_REQUIRED", "请先完成本地分析。", 409)
            sid, analysis = row[0], json.loads(row[1])
            current = db.execute("SELECT analysis_id FROM contexts WHERE sid=?", (sid,)).fetchone()[0]
            if current != analysis["analysis_id"]:
                raise Rejected("STALE_CONTEXT", "上下文已经变化，请核对新分析；输入草稿不会被覆盖。", 409)
            decision = request.get("decision")
            text = request.get("final_text", "")
            if not isinstance(text, str) or len(text) > 8000:
                raise Rejected("INVALID_TEXT", "草稿必须是 8000 字以内的文本。")
            text = normalize(text)
            if decision == "adopt":
                checks = request.get("checks", [])
                if not isinstance(checks, list) or not all(check in checks for check in analysis["required_checks"]):
                    raise Rejected("REVIEW_REQUIRED", "高风险草稿需先核对证据和措辞。", 422)
                if not text.strip() or validate_draft(text):
                    raise Rejected("UNSAFE_DRAFT", "草稿为空或包含示例拦截词，请检查承诺与措辞。", 422)
                kind = "adopt_as_is" if text == normalize(analysis["draft"]) else "adopt_edited"
            elif decision == "reject":
                kind = "rejected"
            else:
                raise Rejected("INVALID_DECISION", "请选择采纳或拒绝。")
            db.execute("INSERT INTO feedback(sid,analysis_id,kind,text) VALUES(?,?,?,?)", (sid,analysis["analysis_id"],kind,text))
            result = {"kind": kind, "sid": sid, "analysis_id": analysis["analysis_id"], "local_only": True,
                      "delivery_status": "not_sent", "source_ticket": analysis["source_ticket"], "replayed": False}
            db.execute("INSERT INTO requests VALUES(?,?,?)", (key, fingerprint, encoded(result)))
        return result

    def summary(self):
        with self.connect() as db:
            feedback = [{"sid": sid, "kind": kind} for sid,kind in db.execute("SELECT sid,kind FROM feedback ORDER BY id DESC LIMIT 12")]
        return {"version": "4.0-public-reference", "synthetic": True, "no_execution": True,
                "sessions": [{key: item[key] for key in ("id","title","service","risk","source_ticket")} for item in CASES], "feedback": feedback}
