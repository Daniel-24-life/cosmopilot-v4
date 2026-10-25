'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kindLabels = {verified:'已核对事实',buyer_report:'买家自述',inference:'系统推断'};
const feedbackLabels = {adopt_as_is:'原样采纳',adopt_edited:'改写采纳',rejected:'拒绝建议'};
let state = {sessions:[],feedback:[]}, selected = null, connected = false, busy = false, revision = 0;
const drafts = new Map();
const current = () => drafts.get(selected);
function blank() { return {analysis:null,text:'',dirty:false,checks:[],key:crypto.randomUUID()}; }
async function request(path, body, key) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(),8000);
  try {
    const options = {signal:controller.signal};
    if(body) Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json',...(key?{'Idempotency-Key':key}:{})},body:JSON.stringify(body)});
    const response = await fetch(path,options);
    const data = await response.json();
    if(!response.ok) throw new Error(`${data.error}：${data.message || '本地请求失败'}`);
    return data;
  } finally { clearTimeout(timer); }
}
function reportError(error) {
  $('error').textContent = `${error.name==='AbortError'?'本地请求超时':error.message}。草稿仍保留，请重试连接或重新分析。`;
}
function controls() {
  const item = current(), analysis = item?.analysis;
  const reviewed = analysis && analysis.required_checks.every(check => item.checks.includes(check));
  $('analyze').disabled = busy || !connected || !selected;
  $('cutoff').disabled = busy || !connected || !selected;
  $('draft').disabled = !analysis;
  $('replace').disabled = busy || !analysis;
  $('adopt').disabled = busy || !connected || !analysis || !reviewed || !item.text.trim();
  $('reject').disabled = busy || !connected || !analysis;
  $('copy').disabled = busy || !connected || !analysis || !reviewed || !item.text.trim();
  $('retry').hidden = connected;
}
function renderSessions() {
  const query = $('search').value.trim();
  const focusedId = document.activeElement?.dataset.sid;
  $('sessions').innerHTML = state.sessions.filter(item => `${item.title}${item.service}${item.id}`.includes(query)).map(item => `<button class="session" data-sid="${esc(item.id)}" aria-pressed="${item.id===selected}"><span class="session-meta"><span>${esc(item.service)}</span><span>${esc(item.id)}</span></span><strong>${esc(item.title)}</strong><small>${esc(item.risk)} · 源工单${esc(item.source_ticket)}</small></button>`).join('') || '<p>没有匹配会话，请调整关键词。</p>';
  if(focusedId) [...$('sessions').querySelectorAll('[data-sid]')].find(button=>button.dataset.sid===focusedId)?.focus();
}
function renderAnalysis() {
  const item=current(), result=item?.analysis;
  if(!result) return;
  $('messages').innerHTML=result.messages.map(message=>`<article class="bubble ${message.speaker==='客服'?'service':''}"><strong>${esc(message.speaker)} · 消息 ${message.seq}</strong><p>${esc(message.text)}</p></article>`).join('');
  $('draft').value=item.text;
  $('draft-status').textContent=item.dirty?'人工草稿已保留；当前分析不会自动覆盖输入。':'当前候选待人工核对，尚未发送。';
  $('review-checks').hidden=!result.required_checks.length;
  $('check-evidence').checked=item.checks.includes('evidence');
  $('check-safe').checked=item.checks.includes('safe_text');
  $('decision-summary').textContent=`${result.service} · 本地规则 · ${result.verifier==='pass'?'示例校验通过':'已阻断'}`;
  $('evidence').innerHTML=result.evidence.map(row=>`<article class="evidence-card ${esc(row.kind)}"><strong>${esc(row.id)} · ${kindLabels[row.kind]} · 消息 ${row.available_seq} 起可见</strong><p>${esc(row.text)}</p></article>`).join('');
  $('gaps').innerHTML=result.missing.map(gap=>`<li>${esc(gap)}</li>`).join('');
  $('trace').innerHTML=result.trace.map(row=>`<li>${esc(row.step)}<span>${esc(row.elapsed_ms)} ms · 本地规则</span></li>`).join('');
  $('states').innerHTML=[['源工单',result.source_ticket],['本地反馈',state.feedback.find(row=>row.sid===selected)?feedbackLabels[state.feedback.find(row=>row.sid===selected).kind]:'未记录'],['发送状态','未发送'],['模型调用','0 次'],['数据身份','公开合成样例']].map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('');
  $('history').innerHTML=state.feedback.map(row=>`<div class="history-item">${esc(row.sid)} · ${feedbackLabels[row.kind]}</div>`).join('') || '<p class="help">尚无本地反馈。</p>';
  $('json').textContent=JSON.stringify(result,null,2);
  controls();
}
async function analyze() {
  if(!connected || busy || !selected) return;
  const sid=selected, token=++revision, item=current(); busy=true; controls(); $('error').textContent=''; $('message').textContent='';
  try {
    const upto=Number($('cutoff').value);
    const result=await request('/api/analyze',{sid,upto_seq:upto});
    if(token!==revision || sid!==selected) return;
    item.analysis=result; item.checks=[]; item.key=crypto.randomUUID();
    if(!item.dirty) item.text=result.draft;
    renderAnalysis();
  } catch(error) { if(sid===selected) {
    if(item.analysis) $('cutoff').value=item.analysis.upto_seq;
    connected=false; $('connection').textContent='分析不可用 · 保留上次结果'; reportError(error);
  } }
  finally { busy=false; controls(); }
}
async function select(sid) {
  if(busy) return;
  selected=sid; ++revision;
  if(!drafts.has(sid)) drafts.set(sid,blank());
  const sample=state.sessions.find(item=>item.id===sid);
  $('case-id').textContent=`${sample.id} / ${sample.service}`; $('case-title').textContent=sample.title;
  $('risk').textContent=sample.risk; $('risk').className=`badge ${sample.risk==='高风险'?'high':''}`;
  const count=sid==='DEMO-006'?3:2;
  $('cutoff').innerHTML=Array.from({length:count},(_,index)=>`<option value="${index+1}">第 ${index+1} 条消息之后</option>`).join('');
  $('cutoff').value=current().analysis?.upto_seq || count;
  $('message').textContent=''; $('error').textContent=''; renderSessions();
  // Clear the previous case before any request can fail; never show cross-case evidence.
  $('messages').innerHTML='<p>正在读取本地合成会话…</p>'; $('evidence').replaceChildren(); $('gaps').replaceChildren(); $('trace').replaceChildren(); $('states').replaceChildren(); $('json').textContent='尚未分析';
  $('draft').value=current().text; $('review-checks').hidden=true;
  if(current().analysis) { renderAnalysis(); controls(); } else { controls(); await analyze(); }
}
async function connect() {
  if(busy) return;
  busy=true; connected=false; controls(); $('connection').textContent='连接本地服务中…';
  try {
    const result=await request('/api/state');
    if(result.synthetic!==true || !Array.isArray(result.sessions) || !Array.isArray(result.feedback)) throw new Error('状态格式无效');
    state=result; connected=true; $('connection').textContent='本地服务已连接 · 默认离线'; $('error').textContent=''; renderSessions();
  } catch(error) { $('connection').textContent='连接不可用 · 保留旧结果'; reportError(error); }
  finally { busy=false; controls(); }
  if(connected && !selected) await select(state.sessions[0].id);
  else if(connected) await analyze();
}
async function feedback(decision) {
  const item=current(); if(busy || !connected || !item?.analysis) return;
  busy=true; controls(); $('error').textContent=''; $('message').textContent='';
  try {
    const result=await request('/api/feedback',{analysis_id:item.analysis.analysis_id,decision,final_text:item.text,checks:item.checks},item.key);
    $('message').textContent=`${feedbackLabels[result.kind]}已保存在本地；未发送，源工单状态未改变。`;
    const fresh=await request('/api/state'); state=fresh;
    item.key=crypto.randomUUID(); renderAnalysis();
  } catch(error) { reportError(error); if(!error.message.includes('：')) {connected=false;$('connection').textContent='连接不可用 · 保留旧结果';} }
  finally { busy=false; controls(); }
}
$('sessions').addEventListener('click',event=>{const button=event.target.closest('[data-sid]'); if(button) select(button.dataset.sid);});
$('search').addEventListener('input',renderSessions);
$('retry').addEventListener('click',connect); $('analyze').addEventListener('click',analyze); $('cutoff').addEventListener('change',analyze);
$('draft').addEventListener('input',()=>{ const item=current(); if(!item)return;item.text=$('draft').value;item.dirty=true;item.checks=[];item.key=crypto.randomUUID();$('check-evidence').checked=false;$('check-safe').checked=false;$('draft-status').textContent='人工草稿已保留；修改后需重新核对。';controls(); });
$('replace').addEventListener('click',()=>{const item=current();item.text=item.analysis.draft;item.dirty=false;item.checks=[];item.key=crypto.randomUUID();renderAnalysis();});
for(const [id,name] of [['check-evidence','evidence'],['check-safe','safe_text']]) $(id).addEventListener('change',()=>{const item=current();item.checks=item.checks.filter(check=>check!==name);if($(id).checked)item.checks.push(name);item.key=crypto.randomUUID();controls();});
$('adopt').addEventListener('click',()=>feedback('adopt')); $('reject').addEventListener('click',()=>feedback('reject'));
$('copy').addEventListener('click',async()=>{if($('copy').disabled)return;try{await navigator.clipboard.writeText(current().text);$('message').textContent='草稿已复制到本机剪贴板，未发送。';}catch{$('error').textContent='剪贴板不可用，请从文本框手动复制；未发送。';}});
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(peer=>peer.setAttribute('aria-pressed',String(peer===button)));for(const view of ['evidence','trace','state'])$(`${view}-view`).hidden=button.dataset.view!==view;}));
connect();
