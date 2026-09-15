# -*- coding: utf-8 -*-
"""训练数据录入组件（共用）

被 build_entry.py（独立平板页）与 build_dashboard.py（仪表盘内嵌）共同使用。
"""

ENTRY_HTML = """
  <div class="tabs">
    <div class="tab on" data-t="ice">冰上计时</div>
    <div class="tab" data-t="physical">陆地素质</div>
    <div class="tab" data-t="session">技术训练课</div>
    <div class="tab" data-t="note">快速记录</div>
  </div>
  <div class="form" id="f-ice">
    <div class="grid2">
      <div class="fld"><label>项目</label>
        <select id="iceProj">
          <option>500m</option><option>1000m</option><option>1500m</option>
          <option>单圈</option><option>起跑反应</option><option>自定义</option>
        </select></div>
      <div class="fld"><label>成绩 / 时间 (分:秒.毫秒)</label>
        <input id="iceTime" placeholder="如 0:48.62" inputmode="decimal"></div>
      <div class="fld"><label>分段 / 圈数</label>
        <input id="iceSplit" placeholder="如 4圈 / 8.2-8.5-8.4-8.3"></div>
      <div class="fld"><label>出发反应 (秒, 可选)</label>
        <input id="iceReact" placeholder="如 0.28" inputmode="decimal"></div>
      <div class="fld full"><label>备注</label>
        <input id="iceNote" placeholder="摔倒/犯规/起跑问题/状态等（可选）"></div>
    </div>
    <button class="save" data-save="ice">保存冰上计时</button>
  </div>
  <div class="form" id="f-physical" style="display:none">
    <div class="grid2">
      <div class="fld"><label>测试项</label>
        <input id="phTest" list="phList" placeholder="CMJ / 立定跳 / 30m / 六边形跳…">
        <datalist id="phList">
          <option>CMJ纵跳</option><option>立定跳远</option><option>30m冲刺</option>
          <option>六边形跳</option><option>引体向上</option><option>仰卧起坐</option>
          <option>YBT平衡</option><option>坐位体前屈</option>
        </datalist></div>
      <div class="fld"><label>数值</label>
        <input id="phVal" inputmode="decimal" placeholder="如 42.5"></div>
      <div class="fld"><label>单位</label>
        <select id="phUnit"><option>cm</option><option>m</option><option>s</option>
          <option>次</option><option>kg</option><option>分</option></select></div>
      <div class="fld"><label>备注 (可选)</label>
        <input id="phNote" placeholder="左右差异/完成情况等"></div>
    </div>
    <button class="save" data-save="physical">保存陆地素质</button>
  </div>
  <div class="form" id="f-session" style="display:none">
    <div class="grid2">
      <div class="fld"><label>教练</label>
        <input id="sCoach" placeholder="如 张利增" list="coachList">
        <datalist id="coachList"><option>张利增</option><option>陈鑫</option><option>李国锋</option><option>姚忠华</option></datalist></div>
      <div class="fld"><label>训练内容（可多选）</label>
        <div class="chips" id="sChips">
          <span class="chip" data-c="起跑">起跑</span>
          <span class="chip" data-c="弯道">弯道</span>
          <span class="chip" data-c="超越">超越</span>
          <span class="chip" data-c="滑行技术">滑行技术</span>
          <span class="chip" data-c="体能">体能</span>
          <span class="chip" data-c="放松恢复">放松恢复</span>
        </div></div>
      <div class="fld"><label>完成组数</label>
        <input id="sSets" type="number" min="0" placeholder="如 8"></div>
      <div class="fld"><label>完成质量</label>
        <div class="stars" id="sStars"><span data-v="1">★</span><span data-v="2">★</span><span data-v="3">★</span><span data-v="4">★</span><span data-v="5">★</span></div></div>
      <div class="fld full"><label>备注</label>
        <input id="sNote" placeholder="完成情况 / 需要改进点（可选）"></div>
    </div>
    <button class="save" data-save="session">保存训练课</button>
  </div>
  <div class="form" id="f-note" style="display:none">
    <div class="fld"><label>记录内容</label>
      <textarea id="nText" rows="4" placeholder="今天训练中观察到的情况、需要注意的队员…"></textarea></div>
    <button class="save" data-save="note">保存记录</button>
  </div>
  <div class="sec-title">已录入 <b id="cnt">0</b> 条 <span style="color:#5d7889;font-weight:400;font-size:11px">· 可筛选运动员/日期</span></div>
  <div class="list" id="entryList"></div>
"""

ENTRY_JS = """
(function(){
var KEY = "stss_train_v1";
var ATHLETES = window.__ENTRY_ATHLETES__ || [];
var ECUR = {t:"ice", athlete:null, chips:{}, stars:0};
var TYPES = {ice:"冰上计时", physical:"陆地素质", session:"训练课", note:"记录"};
var TY_CLS = {ice:"i", physical:"p", session:"s", note:"n"};

function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];}); }
function toast(m){ var el=document.getElementById("toast"); el.textContent=m; el.style.opacity="1";
  clearTimeout(el._t); el._t=setTimeout(function(){ el.style.opacity="0"; },1800); }
function today(){ var d=new Date(); return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0"); }
function uid(){ return Date.now().toString(36)+Math.random().toString(36).slice(2,7); }
function fmtVal(e){ return e.value.trim(); }
function fillAthletes(){
  var sel = document.getElementById("athSel");
  if(!sel) return;
  sel.innerHTML = '<option value="">— 选择运动员 —</option>' +
    ATHLETES.map(function(a){ return '<option value="'+esc(a.name)+'">'+esc(a.name)+(a.coach?"（"+esc(a.coach)+"）":"")+'</option>'; }).join("");
  var last = localStorage.getItem("stss_last_ath");
  if(last){ sel.value = last; }
}
function bindSearch(){
  var s = document.getElementById("athSearch"); if(!s) return;
  s.oninput = function(){
    var kw = this.value.trim(), sel = document.getElementById("athSel");
    var opts = ATHLETES.filter(function(a){ return a.name.indexOf(kw)>=0 || (a.coach||"").indexOf(kw)>=0; });
    sel.innerHTML = '<option value="">— 选择运动员 —</option>' +
      opts.map(function(a){ return '<option value="'+esc(a.name)+'">'+esc(a.name)+(a.coach?"（"+esc(a.coach)+"）":"")+'</option>'; }).join("");
  };
}
function bindEntry(){
  var root = document.getElementById("entryView") || document;
  document.querySelectorAll(".tab").forEach(function(t){
    t.onclick = function(){
      ECUR.t = t.getAttribute("data-t");
      document.querySelectorAll(".tab").forEach(function(x){ x.classList.toggle("on", x==t); });
      ["f-ice","f-physical","f-session","f-note"].forEach(function(id){ document.getElementById(id).style.display = (id=="f-"+ECUR.t)?"block":"none"; });
    };
  });
  var sc = document.getElementById("sChips");
  if(sc) sc.onclick = function(e){
    var c = e.target.closest(".chip"); if(!c) return;
    c.classList.toggle("on");
    var k = c.getAttribute("data-c");
    if(ECUR.chips[k]) delete ECUR.chips[k]; else ECUR.chips[k]=1;
  };
  var ss = document.getElementById("sStars");
  if(ss) ss.onclick = function(e){
    var s = e.target.closest("span"); if(!s) return;
    ECUR.stars = +s.getAttribute("data-v");
    document.querySelectorAll("#sStars span").forEach(function(x){
      x.classList.toggle("on", +x.getAttribute("data-v") <= ECUR.stars);
    });
  };
  document.querySelectorAll(".save").forEach(function(b){
    b.onclick = function(){
      var rec = collect(); if(!rec) return;
      var all = Eload(); all.unshift(rec); EsaveAll(all);
      localStorage.setItem("stss_last_ath", rec.athlete);
      toast("已保存"); EclearForm(); ErenderList(); EupdateCnt();
      if(window.__onEntrySaved__) window.__onEntrySaved__(rec);
    };
  });
  var lst = document.getElementById("entryList");
  if(lst) lst.onclick = function(e){
    var b = e.target.closest(".del"); if(!b) return;
    if(!confirm("删除这条记录？")) return;
    var all = Eload().filter(function(r){ return r.id != b.getAttribute("data-id"); });
    EsaveAll(all); ErenderList(); EupdateCnt(); toast("已删除");
  };
  var sel = document.getElementById("athSel");
  var rd = document.getElementById("recDate");
  if(sel) sel.onchange = function(){ ErenderList(); };
  if(rd) rd.onchange = function(){ ErenderList(); };
}
function collect(){
  var name = document.getElementById("athSel").value;
  var date = document.getElementById("recDate").value || today();
  if(!name){ toast("请先选择运动员"); return null; }
  var rec = {id:uid(), type:ECUR.t, athlete:name, date:date, ts:Date.now()};
  if(ECUR.t=="ice"){
    var t = fmtVal(document.getElementById("iceTime"));
    if(!t){ toast("请填写成绩"); return null; }
    rec.project = document.getElementById("iceProj").value;
    rec.time = t; rec.split = fmtVal(document.getElementById("iceSplit"));
    rec.react = fmtVal(document.getElementById("iceReact"));
    rec.note = fmtVal(document.getElementById("iceNote"));
  } else if(ECUR.t=="physical"){
    var v = fmtVal(document.getElementById("phVal"));
    if(!v){ toast("请填写数值"); return null; }
    rec.test = fmtVal(document.getElementById("phTest"));
    rec.value = v; rec.unit = document.getElementById("phUnit").value;
    rec.note = fmtVal(document.getElementById("phNote"));
  } else if(ECUR.t=="session"){
    rec.coach = fmtVal(document.getElementById("sCoach"));
    rec.contents = Object.keys(ECUR.chips);
    rec.sets = fmtVal(document.getElementById("sSets"));
    rec.rating = ECUR.stars;
    rec.note = fmtVal(document.getElementById("sNote"));
  } else {
    var n = fmtVal(document.getElementById("nText"));
    if(!n){ toast("请填写内容"); return null; }
    rec.note = n;
  }
  return rec;
}
function clearForm(){
  ["iceTime","iceSplit","iceReact","iceNote","phTest","phVal","phNote","sCoach","sSets","sNote","nText"]
    .forEach(function(id){ var el=document.getElementById(id); if(el) el.value=""; });
  ECUR.chips = {}; ECUR.stars = 0;
  document.querySelectorAll("#sChips .chip").forEach(function(c){ c.classList.remove("on"); });
  document.querySelectorAll("#sStars span").forEach(function(s){ s.classList.remove("on"); });
}
function ErenderList(){
  var all = Eload(), el = document.getElementById("entryList");
  if(!el) return;
  var name = document.getElementById("athSel").value;
  var date = document.getElementById("recDate").value;
  var rows = all.filter(function(r){
    if(name && r.athlete != name) return false;
    if(date && r.date != date) return false;
    return true;
  });
  el.innerHTML = rows.length ? rows.map(function(r){
    var s = "";
    if(r.type=="ice") s = r.project+" · "+r.time+(r.split?" · "+r.split:"");
    else if(r.type=="physical") s = r.test+" · "+r.value+r.unit;
    else if(r.type=="session") s = (r.contents||[]).join("/")+" · "+r.sets+"组 · "+(r.rating?("★".repeat(r.rating)):"-");
    else s = r.note;
    return '<div class="row"><span class="ty '+TY_CLS[r.type]+'">'+TYPES[r.type]+'</span>'+
      '<div class="bd"><div class="t">'+esc(r.athlete)+' · '+esc(r.date)+'</div>'+
      '<div class="s">'+esc(s)+(r.note&&r.type!="note"?" · "+esc(r.note):"")+'</div></div>'+
      '<button class="del" data-id="'+r.id+'">删除</button></div>';
  }).join("") : '<div class="empty">暂无记录 · 上面录入后自动出现在这里</div>';
}
function EupdateCnt(){ var el=document.getElementById("cnt"); if(el) el.textContent = Eload().length; }
function Eload(){ try{ return JSON.parse(localStorage.getItem(KEY)) || []; }catch(e){ return []; } }
function EsaveAll(a){ localStorage.setItem(KEY, JSON.stringify(a)); }
function Ecollect(){ return collect(); }
function EclearForm(){ clearForm(); }
function ErenderAll(){ ErenderList(); EupdateCnt(); }
function initEntry(){
  fillAthletes(); bindSearch(); bindEntry();
  var rd = document.getElementById("recDate");
  if(rd) rd.value = today();
  ErenderList(); EupdateCnt();
}
if(document.readyState==="loading"){ document.addEventListener("DOMContentLoaded", initEntry); }
else{ initEntry(); }
window.Eload = Eload; window.EsaveAll = EsaveAll; window.ErenderList = ErenderList;
window.EupdateCnt = EupdateCnt; window.Ecollect = Ecollect; window.EclearForm = EclearForm;
window.ErenderAll = ErenderAll; window.Etoday = today; window.Etoast = toast;
})();
"""
