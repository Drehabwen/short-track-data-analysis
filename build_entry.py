# -*- coding: utf-8 -*-
"""训练数据录入页（平板优先，单文件 HTML）

数据源：blood.db 的 athletes 表（内嵌运动员名单）。
产出：最大摄氧量/训练数据录入.html
数据存储：浏览器 localStorage（key: stss_train_v1），支持导出 JSON/CSV、粘贴导入。
"""

import json
import os
import sqlite3

import pandas as pd

from entry_component import ENTRY_HTML, ENTRY_JS

ROOT = r"D:\DEV\blood"
DB = os.path.join(ROOT, "blood.db")
OUT = os.path.join(ROOT, "最大摄氧量", "训练数据录入.html")


def main():
    con = sqlite3.connect(DB)
    ath = pd.read_sql_query(
        "SELECT name, coach FROM athletes ORDER BY name", con)
    con.close()
    athletes = [{"name": r["name"], "coach": r["coach"]} for _, r in ath.iterrows()]

    html = (HTML
            .replace("__ATHLETES__", json.dumps(athletes, ensure_ascii=False))
            .replace("__ENTRY_HTML__", ENTRY_HTML)
            .replace("__ENTRY_JS__", ENTRY_JS))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>训练数据录入</title>
<style>
:root{
  --ink:#0b1e2d; --panel:#122b3d; --panel2:#0f2636; --ice:#eaf4fa; --frost:#9fb8c8;
  --line:#1e3b4f; --cyan:#38c3e0; --amber:#f2a93b; --red:#e05b4f; --ok:#4ec58b;
  --mono:'Cascadia Mono','Consolas','Courier New',monospace;
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{height:100%}
body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;background:var(--ink);color:var(--ice);
  background-image:radial-gradient(900px 400px at 90% -10%,rgba(56,195,224,.08),transparent 60%);
  min-height:100%;padding-bottom:env(safe-area-inset-bottom)}
.top{display:flex;align-items:center;gap:12px;padding:14px 18px;position:sticky;top:0;z-index:20;
  background:rgba(11,30,45,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.top h1{font-size:17px;letter-spacing:2px;font-weight:800}
.top h1 em{font-style:normal;color:var(--cyan)}
.top .sp{flex:1}
.top .btn{background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  font-size:12.5px;padding:9px 16px;border-radius:9px;font-family:inherit;cursor:pointer}
.top .btn.primary{background:rgba(56,195,224,.16);color:var(--cyan);border-color:rgba(56,195,224,.5)}
.wrap{max-width:860px;margin:0 auto;padding:16px 16px 40px}
.selbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.selbar .fld{flex:1;min-width:180px}
.fld label{display:block;font-size:11px;color:var(--frost);letter-spacing:1px;margin-bottom:5px}
.fld input,.fld select,.fld textarea{width:100%;background:var(--panel);border:1px solid var(--line);
  color:var(--ice);border-radius:10px;padding:12px 14px;font-size:15px;font-family:inherit;outline:none}
.fld input:focus,.fld select:focus,.fld textarea:focus{border-color:var(--cyan)}
.fld input[type="date"]{color-scheme:dark}
.tabs{display:flex;gap:6px;margin-bottom:16px;overflow-x:auto;padding-bottom:4px}
.tab{flex:1;min-width:130px;text-align:center;padding:13px 8px;border-radius:10px;cursor:pointer;
  background:var(--panel2);border:1px solid var(--line);color:var(--frost);font-size:13.5px;font-weight:600;letter-spacing:1px}
.tab.on{background:rgba(56,195,224,.16);color:var(--cyan);border-color:rgba(56,195,224,.5)}
.form{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.full{grid-column:1/-1}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:13px;padding:9px 15px;border-radius:20px;background:var(--panel2);border:1px solid var(--line);
  color:var(--frost);cursor:pointer;user-select:none}
.chip.on{background:rgba(56,195,224,.16);color:var(--cyan);border-color:rgba(56,195,224,.5)}
.stars{display:flex;gap:8px;font-size:26px;cursor:pointer}
.stars span{color:#2a4a60;transition:color .1s}
.stars span.on{color:var(--amber)}
.save{width:100%;background:var(--cyan);color:#0b1e2d;border:none;border-radius:12px;
  font-size:17px;font-weight:800;letter-spacing:3px;padding:15px;cursor:pointer;font-family:inherit;margin-top:4px}
.save:active{transform:scale(.98)}
.sec-title{font-size:13px;color:var(--ice);letter-spacing:2px;margin:18px 0 8px;font-weight:700}
.sec-title b{color:var(--cyan);font-family:var(--mono)}
.list{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.row{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid rgba(30,59,79,.5);font-size:13px}
.row:last-child{border-bottom:none}
.row .bd{flex:1;min-width:0}
.row .bd .t{font-weight:700;color:var(--ice)}
.row .bd .s{font-size:11px;color:var(--frost);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .del{background:transparent;border:1px solid rgba(224,91,79,.5);color:#ff8b7f;border-radius:8px;
  padding:8px 12px;font-size:12px;cursor:pointer;flex:none}
.row .ty{font-size:10px;color:#0b1e2d;border-radius:5px;padding:2px 7px;font-weight:700;flex:none}
.ty.i{background:var(--cyan)} .ty.p{background:var(--ok)} .ty.s{background:var(--amber)} .ty.n{background:#8aa4b5}
.empty{color:#5d7889;text-align:center;padding:30px;font-size:13px}
.toast{position:fixed;left:50%;bottom:40px;transform:translateX(-50%);background:var(--ice);color:var(--ink);
  padding:11px 22px;border-radius:20px;font-size:13.5px;font-weight:700;z-index:99;opacity:0;transition:opacity .2s;pointer-events:none}
.modal{position:fixed;inset:0;background:rgba(5,15,23,.9);z-index:50;display:none;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal .box{background:var(--panel);border:1px solid var(--line);border-radius:14px;width:100%;max-width:560px;padding:18px}
.modal h3{font-size:14px;margin-bottom:10px;color:var(--ice)}
.modal textarea{width:100%;height:180px;background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  border-radius:10px;padding:12px;font-size:12px;font-family:var(--mono);resize:vertical;outline:none}
.modal .row2{display:flex;gap:10px;margin-top:12px}
.modal .btn{flex:1;text-align:center;padding:11px;border-radius:10px;cursor:pointer;font-size:13.5px;font-family:inherit}
.m-ok{background:var(--cyan);color:#0b1e2d;font-weight:700;border:none}
.m-no{background:var(--panel2);color:var(--frost);border:1px solid var(--line)}
@media (max-width:560px){ .grid2{grid-template-columns:1fr} }
@media (prefers-reduced-motion:reduce){ *{transition:none!important} }
</style>
</head><body>
<div class="top">
  <h1>训练数据<em>录入</em></h1>
  <span class="sp"></span>
  <button class="btn" id="btnImport">导入</button>
  <button class="btn" id="btnCopy">复制</button>
  <button class="btn primary" id="btnExport">导出</button>
</div>
<div class="wrap">
  <div class="selbar">
    <div class="fld" style="flex:2">
      <label>运动员</label>
      <input id="athSearch" placeholder="搜索姓名…" autocomplete="off">
    </div>
    <div class="fld" style="flex:2">
      <label>选择</label>
      <select id="athSel"></select>
    </div>
    <div class="fld" style="flex:1">
      <label>日期</label>
      <input type="date" id="recDate">
    </div>
  </div>

  __ENTRY_HTML__
</div>

<div class="modal" id="modal">
  <div class="box">
    <h3 id="modalTitle">导出数据</h3>
    <textarea id="modalText" readonly></textarea>
    <div class="row2">
      <button class="btn m-no" id="modalNo">关闭</button>
      <button class="btn m-ok" id="modalCopy">复制</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
window.__ENTRY_ATHLETES__ = __ATHLETES__;
__ENTRY_JS__

// 导出 / 复制 / 导入
function openModal(title, text, readonly){
  document.getElementById("modalTitle").textContent = title;
  var ta = document.getElementById("modalText");
  ta.value = text; ta.readOnly = readonly;
  document.getElementById("modal").classList.add("show");
}
document.getElementById("modalNo").onclick = function(){ document.getElementById("modal").classList.remove("show"); };
document.getElementById("modalCopy").onclick = function(){
  var ta = document.getElementById("modalText");
  ta.select();
  var ok = false;
  try{ ok = document.execCommand("copy"); }catch(e){}
  if(navigator.clipboard){ navigator.clipboard.writeText(ta.value).then(function(){ toast("已复制"); }); return; }
  toast(ok ? "已复制" : "复制失败，请手动选择复制");
};
document.getElementById("btnExport").onclick = function(){
  var all = Eload();
  if(!all.length){ toast("暂无数据可导出"); return; }
  var json = JSON.stringify(all, null, 1);
  var a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff"+json], {type:"application/json"}));
  a.download = "训练数据导出_"+Etoday()+".json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 800);
  toast("已导出 "+all.length+" 条");
};
document.getElementById("btnCopy").onclick = function(){
  var all = Eload();
  if(!all.length){ toast("暂无数据"); return; }
  openModal("复制数据（粘贴发回，即可入库）", JSON.stringify(all), true);
};
document.getElementById("btnImport").onclick = function(){
  openModal("粘贴数据以合并（JSON 文本）", "", false);
  document.getElementById("modalCopy").textContent = "合并导入";
  document.getElementById("modalCopy").onclick = function(){
    try{
      var arr = JSON.parse(document.getElementById("modalText").value);
      if(!Array.isArray(arr)) throw 0;
      var all = Eload(), seen = {};
      all.forEach(function(r){ seen[r.id]=1; });
      var added = 0;
      arr.forEach(function(r){ if(r && r.id && !seen[r.id]){ all.push(r); seen[r.id]=1; added++; } });
      EsaveAll(all); ErenderList(); EupdateCnt();
      document.getElementById("modal").classList.remove("show");
      toast("合并 "+added+" 条");
    }catch(e){ toast("格式不对，请检查 JSON"); }
    document.getElementById("modalCopy").textContent = "复制";
  };
};

</script>
</body></html>
"""


if __name__ == "__main__":
    main()
