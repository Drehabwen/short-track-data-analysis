# -*- coding: utf-8 -*-
"""认证与权限测试脚本（临时）。"""
import json
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"


def post(path, data, token=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, token=None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__status__": e.code, "__body__": e.read().decode("utf-8")[:100]}


def raw(method, path, token, data=None):
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


print("1. 未登录访问 overview:", get("/api/dashboard/overview").get("__status__", "允许(异常)"))
print("2. 未登录访问 samples:", get("/api/samples").get("__status__", "允许(异常)"))

tokens = {}
for u, p in [("admin", "admin123"), ("coach", "coach123"), ("athlete", "athlete123")]:
    r = post("/api/auth/login", {"username": u, "password": p})
    tokens[u] = r.get("access_token")
    print(f"3. 登录 {u}: token={'有' if tokens[u] else '无'} role={r['user']['role']}")

me = get("/api/auth/me", tokens["athlete"])
print("4. athlete /me:", me.get("username"), me.get("role"), "athlete_id=", me.get("athlete_id"))

code = raw("PATCH", "/api/samples/1", tokens["athlete"], {"review_note": "x"})
print("5. athlete PATCH 编辑样本:", code, "(应403)")

code = raw("POST", "/api/participants", tokens["coach"], {"participant_id": "TEST01", "name": "测试"})
if code == 200:
    raw("DELETE", "/api/participants/TEST01", tokens["coach"])
print("6. coach 创建运动员:", code, "(应200)")

code = raw("POST", "/api/import/seed", tokens["athlete"])
print("6b. athlete 导入数据:", code, "(应403)")

exc = get("/api/analytes/exceedance", tokens["admin"])
print("7. 超标统计指标数:", len(exc))
for item in exc[:5]:
    print(f"   {item['name']}: 总数{item['total']} 偏高{item['high']} 偏低{item['low']} 超标率{item['high_rate']}")

ref = get("/api/analytes/reference", tokens["admin"])
print("8. 参考区间配置数:", len(ref))
print("测试完成")
