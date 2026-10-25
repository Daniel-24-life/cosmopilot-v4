import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import handler
from core import Store, Rejected, validate_draft
from samples import CASES


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/"test.sqlite"
        self.store = Store(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def payload(self, sid="DEMO-001", **changes):
        result = self.store.analyze(sid)
        return {"analysis_id":result["analysis_id"],"decision":"adopt","final_text":result["draft"],"checks":result["required_checks"],**changes}

    def assert_rejected(self, code, action):
        with self.assertRaises(Rejected) as error:
            action()
        self.assertEqual(error.exception.code,code)

    def test_six_synthetic_cases_cover_five_services(self):
        self.assertEqual(len(CASES),6)
        self.assertEqual(len({row["service"] for row in CASES}),5)
        self.assertTrue(all(row["synthetic"] for row in CASES))

    def test_all_cases_have_no_model_or_execution(self):
        for item in CASES:
            result=self.store.analyze(item["id"])
            self.assertEqual(result["model_calls"],0)
            self.assertTrue(result["no_execution"])
            self.assertEqual(result["delivery_status"],"not_sent")
            self.assertEqual(result["verifier"],"pass")

    def test_trace_has_six_measured_local_steps(self):
        result=self.store.analyze("DEMO-001")
        self.assertEqual(len(result["trace"]),6)
        self.assertTrue(all(row["elapsed_ms"]>=0 and row["source"]=="local_rules" for row in result["trace"]))

    def test_three_evidence_kinds_remain_distinct(self):
        result=self.store.analyze("DEMO-001")
        self.assertEqual({row["kind"] for row in result["evidence"]},{"verified","buyer_report","inference"})

    def test_future_evidence_and_messages_are_excluded(self):
        result=self.store.analyze("DEMO-006",2)
        self.assertNotIn("E4",[row["id"] for row in result["evidence"]])
        self.assertEqual(len(result["messages"]),2)
        self.assertNotIn("新增合成签收",result["draft"])
        self.assertIn("E4",[row["id"] for row in self.store.analyze("DEMO-006",3)["evidence"]])

    def test_cutoff_and_unknown_sessions_fail(self):
        for value in (0,-1,5,True,"2"):
            self.assert_rejected("INVALID_CUTOFF",lambda:self.store.analyze("DEMO-001",value))
        self.assert_rejected("NOT_FOUND",lambda:self.store.analyze("unknown"))

    def test_stable_analysis_id_ignores_timing(self):
        self.assertEqual(self.store.analyze("DEMO-001")["analysis_id"],self.store.analyze("DEMO-001")["analysis_id"])

    def test_original_adoption_is_local_and_does_not_close_ticket(self):
        result=self.store.feedback("request-1",self.payload())
        self.assertEqual(result["kind"],"adopt_as_is")
        self.assertEqual(result["source_ticket"],"开放")
        self.assertEqual(result["delivery_status"],"not_sent")

    def test_one_character_change_is_edited(self):
        request=self.payload()
        request["final_text"]+="。"
        self.assertEqual(self.store.feedback("edited",request)["kind"],"adopt_edited")

    def test_line_endings_normalize_without_stripping_other_changes(self):
        request=self.payload()
        request["final_text"]+=" "
        self.assertEqual(self.store.feedback("space",request)["kind"],"adopt_edited")

    def test_high_risk_requires_all_checks(self):
        request=self.payload("DEMO-002",checks=[])
        self.assert_rejected("REVIEW_REQUIRED",lambda:self.store.feedback("unsafe",request))
        request["checks"]=["evidence"]
        self.assert_rejected("REVIEW_REQUIRED",lambda:self.store.feedback("unsafe",request))
        request["checks"].append("safe_text")
        self.assertEqual(self.store.feedback("safe",request)["kind"],"adopt_as_is")

    def test_final_text_is_rechecked(self):
        request=self.payload(final_text="保证退款，立即到账")
        self.assert_rejected("UNSAFE_DRAFT",lambda:self.store.feedback("bad",request))

    def test_empty_draft_is_not_adopted(self):
        self.assert_rejected("UNSAFE_DRAFT",lambda:self.store.feedback("empty",self.payload(final_text=" ")))

    def test_reject_is_separate_from_adopt(self):
        self.assertEqual(self.store.feedback("reject",self.payload(decision="reject",final_text=""))["kind"],"rejected")

    def test_idempotent_replay_does_not_duplicate(self):
        request=self.payload()
        self.store.feedback("same",request)
        self.assertTrue(self.store.feedback("same",request)["replayed"])
        self.assertEqual(len(self.store.summary()["feedback"]),1)

    def test_idempotency_key_cannot_change_payload(self):
        request=self.payload()
        self.store.feedback("same",request)
        request["final_text"]+="改"
        self.assert_rejected("IDEMPOTENCY_CONFLICT",lambda:self.store.feedback("same",request))

    def test_stale_analysis_is_not_adopted(self):
        result=self.store.analyze("DEMO-006",2)
        self.store.analyze("DEMO-006",3)
        self.assert_rejected("STALE_CONTEXT",lambda:self.store.feedback("old",{"analysis_id":result["analysis_id"],"decision":"adopt","final_text":result["draft"]}))

    def test_restart_preserves_feedback(self):
        self.store.feedback("saved",self.payload())
        self.assertEqual(len(Store(self.path).summary()["feedback"]),1)

    def test_key_is_required(self):
        self.assert_rejected("KEY_REQUIRED",lambda:self.store.feedback("",self.payload()))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),handler(Store(Path(cls.directory.name)/"api.sqlite")))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.directory.cleanup()

    def post(self,path,body,headers=None):
        data=json.dumps(body).encode()
        request=Request(self.base+path,data=data,headers={"Content-Type":"application/json",**(headers or {})})
        try:
            with urlopen(request) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)

    def test_http_pages_and_state(self):
        for path in ("/","/app.js","/styles.css","/api/state"):
            with urlopen(self.base+path) as response:self.assertEqual(response.status,200)

    def test_files_outside_whitelist_are_not_served(self):
        for path in ("/core.py","/samples.py","/.runtime/demo.sqlite","/../core.py"):
            with self.assertRaises(HTTPError) as error:urlopen(self.base+path)
            self.assertEqual(error.exception.code,404)

    def test_foreign_origin_cannot_write(self):
        status,_=self.post("/api/analyze",{"sid":"DEMO-001"},{"Origin":"https://untrusted.invalid"})
        self.assertEqual(status,403)

    def test_invalid_host_is_refused(self):
        request=Request(self.base+"/api/state",headers={"Host":"untrusted.invalid"})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)

    def test_malformed_json_is_an_error(self):
        request=Request(self.base+"/api/analyze",data=b'{',headers={"Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,400)

    def test_http_analysis_and_feedback(self):
        status,result=self.post("/api/analyze",{"sid":"DEMO-001"})
        self.assertEqual(status,200)
        status,feedback=self.post("/api/feedback",{"analysis_id":result["analysis_id"],"decision":"adopt","final_text":result["draft"]},{"Idempotency-Key":"http"})
        self.assertEqual(status,200)
        self.assertEqual(feedback["delivery_status"],"not_sent")


if __name__=="__main__":unittest.main()
