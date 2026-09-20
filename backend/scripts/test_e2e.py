# -*- coding: utf-8 -*-
"""三角色端到端联调（临时脚本）。"""
import json
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:8000"


def call(method, path, token=None, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:120]


def login(u, p):
    s, r = call("POST", "/api/auth/login", data={"username": u, "password": p})
    assert s == 200, f"登录失败 {u}: {r}"
    return r["access_token"]


print("════ 三角色端到端联调 ════")

# ── 运动员视角 ──
at = login("athlete", "athlete123")
s, r = call("GET", "/api/tracking/Z05", at)
print(f"[运动员] tracking Z05: {s} | 恢复={r.get('recovery', {}).get('level')}")
s, r = call("GET", "/api/dashboard/overview", at)
print(f"[运动员] overview: {s} | 运动员数={r.get('participant_count')}")
s, r = call("GET", "/api/analytes/exceedance", at)
print(f"[运动员] exceedance: {s} (登录可读)")
s, _ = call("POST", "/api/participants", at, {"participant_id": "X01"})
print(f"[运动员] 创建运动员: {s} (应403)")
s, _ = call("POST", "/api/import/seed", at)
print(f"[运动员] 导入数据: {s} (应403)")

# ── 教练视角 ──
co = login("coach", "coach123")
s, r = call("GET", "/api/participants", co)
print(f"[教练] participants: {s} | 共{len(r)}人")
s, r = call("GET", "/api/analytes/exceedance", co)
print(f"[教练] exceedance: {s} | 指标数={len(r)}")
s, r = call("GET", "/api/stats/longitudinal", co)
print(f"[教练] longitudinal: {s} | CK p={r.get('肌酸激酶 CK', {}).get('friedman', {}).get('p')}")
s, r = call("PATCH", "/api/samples/1", co, {"review_note": "coach联调测试"})
print(f"[教练] 编辑样本: {s} (应200)")
# 还原
call("PATCH", "/api/samples/1", co, {"review_note": ""})

# ── 管理员视角 ──
ad = login("admin", "admin123")
s, r = call("GET", "/api/analytes/exceedance", ad)
print(f"[管理员] exceedance: {s} | 指标数={len(r)}")
ck = next((x for x in r if x["code"] == "creatine_kinase_U_L"), None)
print(f"[管理员] CK 超标: 总数={ck['total']} 偏高={ck['high']} 偏高率={ck['high_rate']}")
s, r = call("GET", "/api/analytes/reference", ad)
print(f"[管理员] reference: {s} | 配置数={len(r)}")
s, _ = call("GET", "/api/auth/me", ad)
print(f"[管理员] me: {s} | role={r[0]['name'] if r else '?'}")

print("════ 联调完成 ════")
