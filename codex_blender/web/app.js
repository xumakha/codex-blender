import {initAssetGenerator} from './assetgen.js';
import {api} from './api.js';
import {renderETA} from './render-eta.js';
import {createPreferences} from './preferences.js';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const assetURL = path => `/api/assets/file?path=${encodeURIComponent(path)}`;
const jobURL = (id, name) => `/api/jobs/${id}/${name}`;
const S = {project:null, assets:[], projects:[], voices:[], page:'studio', tab:'script', kind:'all', voiceMode:'none', poll:null, dirty:false, fileCategory:'images', fileHandler:null};
let toastTimer;
const preferences=createPreferences({$,api,toast,dimensions,getVoiceMode:()=>S.voiceMode});
function toast(message, error=false) { $('toast').textContent=message; $('toast').classList.toggle('error',error); $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,error?7000:3500); }
const safe = fn => async (...args) => { try {await fn(...args);} catch(error) {toast(error.message,true);} };
const numeric=['fps','samples','rate','voice-volume','music-volume'];
const fields=['title','prompt','fps','samples','voice-id','voice-file','narration','rate','voice-volume','music','music-volume','duck-music','subtitles','font'];
function key(id){return id.replaceAll('-','_');}
function markDirty(){ S.dirty=true; $('save-state').textContent='Chưa lưu'; renderAssetPreparation(); }
function dimensions(){
  const aspect=$('aspect').value, res=$('resolution').value;
  if(res==='custom'&&S.project)return [S.project.draft.width,S.project.draft.height];
  const map={'9:16':{draft:[540,960],hd:[720,1280],full:[1080,1920]},'16:9':{draft:[960,540],hd:[1280,720],full:[1920,1080]},'1:1':{draft:[540,540],hd:[720,720],full:[1080,1080]}};
  return map[aspect][res];
}
function readForm(){
  const draft=structuredClone(S.project.draft);
  for(const id of fields){ const el=$(id); draft[key(id)]=el.type==='checkbox'?el.checked:numeric.includes(id)?Number(el.value):el.value; }
  draft.script="";
  draft.voice_mode=S.voiceMode;
  for(const name of ['voice_file','music','font']) if(!draft[name]) draft[name]=null;
  [draft.width,draft.height]=dimensions();
  if($('scene-json').value.trim()) draft.scene=JSON.parse($('scene-json').value); else draft.scene=null;
  draft.references=S.project.draft.references;
  draft.selected_assets=[];draft.style='';
  return draft;
}
function setForm(project){
  S.project=project;
  const d=project.draft;
  populateAssetSelects();
  for(const id of ['fps','samples']){
    if(![...$(id).options].some(o=>o.value===String(d[id]))){const o=new Option(`${d[id]} ${id==='fps'?'FPS':'samples'} · tùy chỉnh`,String(d[id]));$(id).add(o);}
  }
  for(const id of fields){const el=$(id); if(el.type==='checkbox')el.checked=d[key(id)];else el.value=d[key(id)]??'';}
  $('prompt').value=[d.prompt,d.script].filter(v=>v?.trim()).join('\n\n');
  S.voiceMode=d.voice_mode;
  const ratio=d.width/d.height;
  $('aspect').value=ratio>.9&&ratio<1.1?'1:1':ratio>1?'16:9':'9:16';
  const side=Math.min(d.width,d.height);
  $('resolution').value=side>=1080?'full':side>=720?'hd':'draft';
  const [presetW,presetH]=dimensions();
  if(presetW!==d.width||presetH!==d.height){let custom=[...$('resolution').options].find(o=>o.value==='custom');if(!custom){custom=new Option('Tùy chỉnh','custom');$('resolution').add(custom);}custom.textContent=`${d.width} × ${d.height} · từ cảnh`;$('resolution').value='custom';}
  $('scene-json').value=d.scene?JSON.stringify(d.scene,null,2):'';
  S.dirty=false;$('save-state').textContent='Đã lưu';
  renderReferences();updateAudio();updateMetrics();updateProjectStatus();renderRecent();
}
async function saveDraft(){
  if(!S.project) return;
  const saved=await api(`/api/projects/${S.project.id}`,{method:'PUT',body:readForm()});
  S.project={...S.project,...saved}; S.dirty=false;$('save-state').textContent='Đã lưu';
  S.projects=await api('/api/projects');renderRecent();
}
async function openProject(id){
  if(S.dirty && S.project && !busy()) await saveDraft();
  setForm(await api(`/api/projects/${id}`)); showPage('studio');
}
async function newProject(template){
  await preferences.flush();
  if(S.dirty && S.project && !busy()) await saveDraft();
  const project=await api('/api/projects',{method:'POST',body:template?{template}:{}});
  S.projects=await api('/api/projects');setForm(preferences.restore(project));showPage('studio');showTab('script');
  toast(template?'Đã nạp cảnh mẫu. Bạn có thể render ngay.':'Đã tạo dự án mới');
}
function busy(){ const p=S.project;return p&&(['planning','preparing_audio','exporting'].includes(p.state)||['queued','rendering','encoding','pausing','paused'].includes(p.job?.state)); }
function renderRecent(){ $('recent-projects').innerHTML=S.projects.slice(0,8).map(p=>`<button data-project="${p.id}" class="${p.id===S.project?.id?'active':''}" title="${esc(p.title)}">${esc(p.title)}</button>`).join('')||'<p class="helper" style="padding:0 14px">Chưa có dự án</p>'; }
function showTab(tab){ S.tab=tab;for(const node of document.querySelectorAll('[data-tab]')){const on=node.dataset.tab===tab;node.classList.toggle('active',on);node.setAttribute('aria-selected',on);}for(const t of ['script','audio','output'])$(`tab-${t}`).hidden=t!==tab; }
function showPage(page){
  S.page=page;for(const p of ['studio','assetgen','library','history','settings'])$(`page-${p}`).hidden=p!==page;
  document.querySelectorAll('#nav [data-page]').forEach(n=>n.classList.toggle('active',n.dataset.page===page));
  $('breadcrumb').textContent={studio:'Video studio',assetgen:'Tạo asset từ ảnh',library:'Thư viện assets',history:'Lịch sử render',settings:'Cài đặt'}[page];
  if(page==='assetgen')safe(assetGenerator.load)();
  if(page==='library')safe(loadLibrary)(); if(page==='history')safe(loadHistory)();
}
function updateMetrics(){
  const [w,h]=dimensions(), p=S.project, timing=p?.prompt_timing;
  const current=!S.dirty&&p?.scene_current!==false;
  const duration=S.dirty?null:current?p?.draft.scene?.duration:p?.screenplay?.duration??timing?.duration;
  const range=!S.dirty&&timing?.duration_range;
  const label=duration?`${duration} giây${range?` · yêu cầu ${range[0]}–${range[1]} giây`:''}`:range?`${range[0]}–${range[1]} giây theo prompt`:'Tự động theo prompt';
  const fps=Number($('fps').value);
  $('preview-format').textContent=`${w} × ${h}`;$('preview-aspect').textContent=$('aspect').value;$('preview-duration').textContent=`${label} · ${fps} FPS`;
  $('render-estimate').textContent=`${duration?`${Math.round(duration*fps).toLocaleString('vi-VN')} khung hình · `:''}${w} × ${h}. Phân cảnh, thời lượng và lời thoại được lấy từ prompt. Thời gian render phụ thuộc cảnh và máy.`;
  $('prompt-count').textContent=`${$('prompt').value.length.toLocaleString('vi-VN')} ký tự`;
  $('voice-volume-value').textContent=`${Math.round(Number($('voice-volume').value)*100)}%`;
  $('music-volume-value').textContent=`${Math.round(Number($('music-volume').value)*100)}%`;
}
function setSelect(id, entries, blank){ const el=$(id),current=el.value; el.innerHTML=`<option value="">${esc(blank)}</option>`+entries.map(a=>`<option value="${esc(a.path)}">${esc(a.name)}</option>`).join('');el.value=current; }
function populateAssetSelects(){
  const audio=S.assets.filter(a=>a.kind==='audio');setSelect('voice-file',audio,'Chọn file giọng đọc…');setSelect('music',audio,'Tự tạo một nhạc nền');
  setSelect('font',S.assets.filter(a=>a.kind==='font'),'Chọn font hỗ trợ tiếng Việt…');
  setSelect('existing-reference',S.assets.filter(a=>a.kind==='image'&&!a.internal),'Chọn ảnh trong thư viện…');
}
function updateAudio(){
  $('duck-music').checked=false;$('duck-music').closest('label').hidden=true;
  $('voice-upload').hidden=S.voiceMode!=='upload';$('voice-tts').hidden=S.voiceMode!=='tts';
  $('voice-options').hidden=!['auto','tts'].includes(S.voiceMode);
  const voice=S.voices.find(v=>v.id===$('voice-id').value);
  $('voice-provider-note').textContent=voice?.provider==='elevenlabs'
    ?'ElevenLabs CLI dùng key trên máy để tạo voice. Giọng đã chọn cần được tài khoản cho phép sử dụng; dùng Nghe thử giọng để kiểm tra.'
    :voice?.provider==='voicestudio'
    ?'Giọng clone VoiceStudio chạy trên máy, không cần API key. Tạo voice có thể mất vài phút; phụ đề dùng mốc từ ước tính. Model hiện tại chỉ dùng phi thương mại.'
    :'Giọng Microsoft Edge cần Internet và gửi lời đọc tới dịch vụ Microsoft Edge.';
  document.querySelectorAll('[data-voice]').forEach(n=>n.classList.toggle('active',n.dataset.voice===S.voiceMode));
  for(const [selector,player] of [['voice-file','uploaded-voice-player'],['music','music-player']]){const path=$(selector).value;$(player).hidden=!path;if(path&&$(player).dataset.path!==path){$(player).src=assetURL(path);$(player).dataset.path=path;}}
}
function renderReferences(){
  $('reference-grid').innerHTML=(S.project?.draft.references||[]).map((path,i)=>`<div class="reference"><img src="${assetURL(path)}" alt="Ảnh phong cách ${i+1}"><button class="icon-button" data-remove-ref="${i}" aria-label="Bỏ ảnh tham khảo ${i+1}">${icon('close')}</button></div>`).join('');
  $('upload-references').disabled=busy()||(S.project?.draft.references?.length||0)>=4;
}
function renderAssetPreparation(){
  const inventory=S.dirty?null:S.project?.asset_preparation;
  $('asset-preparation-panel').hidden=!inventory;
  if(!inventory)return;
  const items=inventory.requirements||[];
  $('asset-preparation-title').textContent=`Bộ assets: ${items.length} vật thể/bối cảnh · ${inventory.ready?'Đã đủ':inventory.generation_state==='generating'?'Đang tự dựng phần còn thiếu':'Đang chuẩn bị'}`;
  const names=new Map(S.assets.map(a=>[a.path,a.name]));
  $('prepared-assets').innerHTML=items.map(r=>{const paths=[...new Set((r.objects||[]).filter(o=>o.kind==='model').map(o=>o.asset))];return `<p><strong>${esc(r.label)} × ${r.count}</strong><br>${r.missing?`Sẽ tự dựng: ${esc(r.missing)}`:paths.map(path=>esc(names.get(path)||path)).join(' · ')}<br><small>${esc(r.reason)}</small></p>`;}).join('');
}
function mediaSource(element,url){if(element.dataset.source!==url){element.src=url;element.dataset.source=url;}}
function updateProjectStatus(){
  const p=S.project;if(!p)return;renderAssetPreparation();
  const isBusy=busy();document.body.classList.toggle('busy',isBusy);
  for(const el of document.querySelectorAll('.editor input,.editor textarea,.editor select')) el.disabled=!!isBusy;
  for(const id of ['save-project','generate','import-script','upload-voice','upload-music','upload-font','add-reference'])$(id).disabled=!!isBusy;
  $('render-preview').disabled=isBusy||!p.draft.scene;$('render-video').disabled=isBusy||!p.draft.scene;
  $('generate').querySelector('span').textContent=p.state==='planning'?'Đang đọc prompt…':p.draft.scene?'Tạo lại video':'Tạo video';
  const activeScene=p.scene_current!==false?p.draft.scene:null;
  const screenplay=activeScene||p.screenplay;
  const shots=screenplay?.shots||[];
  $('scene-label').textContent=shots.length?`${shots.length} phân cảnh · ${screenplay.duration} giây · Theo prompt`:activeScene?`${activeScene.objects.length} đối tượng · Cảnh đã sẵn sàng`:p.prompt_timing?.duration?`Thời lượng theo prompt: ${p.prompt_timing.duration} giây`:'Bắt đầu với ý tưởng của bạn';
  const storyboard=shots.map((shot,i)=>`<details><summary>${i+1}. ${esc(shot.title)} · ${shot.start}–${shot.end}s</summary><p>${esc(shot.setting)}</p>${shot.elements?.length?`<strong>Chi tiết cần có trong cảnh</strong><ul>${shot.elements.map(element=>`<li><strong>${esc(element.label)}</strong> · ${esc(element.appearance)}${element.parts?.length?`<p class="helper">${element.parts.map(part=>`${part.count} ${esc(part.name)}`).join(' · ')}</p>`:''}</li>`).join('')}</ul>`:''}<ul>${shot.actions.map(action=>`<li>${esc(action)}</li>`).join('')}</ul>${shot.narration.map(cue=>`<p><strong>${cue.start}–${cue.end}s:</strong> ${esc(cue.text)}</p>`).join('')}</details>`).join('');
  $('storyboard').hidden=!shots.length;
  const warnings=screenplay?.warnings||[];
  $('screenplay-warnings').hidden=!warnings.length;
  $('screenplay-warnings').textContent=warnings.length?'Lưu ý khi tạo video: '+warnings.join(' '):'';
  if($('storyboard').dataset.content!==storyboard){$('storyboard').innerHTML=`<h2>Phân cảnh theo prompt</h2>${storyboard}`;$('storyboard').dataset.content=storyboard;}
  const job=p.job;
  $('retry-actions').hidden=isBusy||job?.state!=='failed';
  $('retry-render').disabled=!!isBusy;
  if(job)$('render-log').href=jobURL(job.id,'render.log');
  const working=['planning','preparing_audio','exporting'].includes(p.state)?p.state:job?.state;
  const labels={planning:'Codex đang lên cảnh',preparing_audio:'Đang tạo giọng đọc',exporting:'Đang lưu asset Blender',queued:'Đang chờ render',rendering:'Blender đang render',encoding:'Đang ghép âm thanh & xuất MP4',completed:job?.mode==='video'?'Video đã hoàn tất':'Preview đã sẵn sàng',failed:'Render chưa hoàn tất'};
  $('status-card').hidden=!working||working==='idle'||working==='ready'||working==='error';
  Object.assign(labels,{pausing:'Đang chờ tạm dừng',paused:'Đã tạm dừng render'});
  $('status-title').textContent=labels[working]||'';
  $('status-card').classList.toggle('done',working==='completed');
  $('status-card').classList.toggle('paused',['pausing','paused','failed'].includes(working));
  const determinate=['rendering','pausing','paused','encoding','failed','completed'].includes(working)&&job?.mode==='video';
  const percent=working==='completed'?100:Math.min(100,Math.max(0,Math.floor((job?.frames_rendered||0)/Math.max(1,job?.frames_total||1)*100)));
  $('progress-track').classList.toggle('indeterminate',!determinate&&working!=='completed'&&working!=='failed');
  if(['pausing','paused'].includes(working))$('progress-track').classList.remove('indeterminate');
  $('progress-bar').style.width=`${determinate||working==='completed'?percent:0}%`;
  if(determinate||working==='completed')$('progress-track').setAttribute('aria-valuenow',percent);
  else $('progress-track').removeAttribute('aria-valuenow');
  $('progress-count').textContent=determinate?`${percent}% · ${job.frames_rendered} / ${job.frames_total} khung hình`:working==='completed'?'100%':'';
  const eta=renderETA(job,working);
  $('progress-eta').hidden=!eta;
  $('progress-eta').textContent=eta;
  $('progress-eta').title='Ước tính theo tốc độ các khung hình gần đây, không tính thời gian tạm dừng. Bước ghép âm thanh và xuất MP4 có thể cần thêm thời gian.';
  $('pause-render').hidden=!['queued','rendering','pausing','paused'].includes(working);
  $('pause-render').disabled=!!S.controlPending;
  $('pause-render').textContent=['pausing','paused'].includes(working)?'Tiếp tục':'Tạm dừng';
  const descriptions={planning:'Đang đọc kịch bản, ảnh tham khảo và chọn tài nguyên phù hợp.',preparing_audio:'Dịch vụ giọng đọc online đang xử lý phần thuyết minh.',exporting:'Tạo GLB và ảnh thumbnail trong thư viện cố định.',rendering:'Bạn có thể chuyển sang thư viện; render tiếp tục chạy trên máy.',queued:'Tác vụ chạy nền. Tiến độ sẽ tự cập nhật.',encoding:'Ghép voice, nhạc nền và phụ đề theo cấu hình đã chọn.',completed:'Kết quả được lưu trên máy và có thể tải về bên dưới.'};
  Object.assign(descriptions,{pausing:'Blender sẽ tạm dừng sau khi hoàn tất khung hình đang xử lý.',paused:'Các khung hình đã render được giữ lại. Bấm Tiếp tục để dựng tiếp.'});
  $('status-detail').textContent=(p.state==='planning'?p.planning_detail:null)||descriptions[working]||'';
  const error=p.error||job?.error;$('project-error').hidden=!error;$('project-error').textContent=error||'';
  const hasVideo=p.scene_current!==false&&job?.state==='completed'&&job?.artifacts?.['video.mp4'];
  const hasPreview=p.scene_current!==false&&job?.artifacts?.['preview.png'];
  $('preview-video').hidden=!hasVideo;$('preview-image').hidden=!!hasVideo||!hasPreview;$('preview-empty').hidden=!!hasVideo||!!hasPreview;
  if(hasVideo)mediaSource($('preview-video'),jobURL(job.id,'video.mp4'));
  else if(hasPreview)mediaSource($('preview-image'),jobURL(job.id,'preview.png'));
  $('result-actions').hidden=job?.state!=='completed'||p.scene_current===false;$('download-video').hidden=!hasVideo;
  if(job){$('download-video').href=jobURL(job.id,'video.mp4')+'?download=1';$('download-video').download='video.mp4';$('download-blend').href=jobURL(job.id,'scene.blend')+'?download=1';}
  $('export-asset').disabled=isBusy;renderReferences();
}
async function poll(){
  if(!S.project)return;
  try{
    const id=S.project.id,wasState=S.project.state,wasJob=S.project.job?.state;
    const fresh=await api(`/api/projects/${id}`);
    if(S.project?.id!==id)return;
    if((wasState==='planning'&&fresh.state!=='planning')||wasState==='exporting'&&fresh.state!=='exporting'){
      setForm(fresh);await loadLibrary();if(fresh.state==='ready')toast(wasState==='exporting'?'Asset đã được lưu vào thư viện':fresh.job?.mode==='video'?'Đã dựng cảnh, đang tạo video.':'Cảnh đã sẵn sàng.');
    }else{S.project={...fresh,draft:S.dirty?S.project.draft:fresh.draft};updateMetrics();updateProjectStatus();}
    if(fresh.job?.state==='completed'&&wasJob!=='completed'){
      await loadLibrary();
      toast(fresh.job.mode==='video'?'Video đã xuất xong':'Ảnh preview đã sẵn sàng');
    }
  }catch(error){console.warn('Không cập nhật được tiến độ',error.message);}
}
async function loadLibrary(){
  const data=await api('/api/library');S.assets=data.assets;S.settings=data.settings;
  $('asset-count').textContent=S.assets.filter(a=>a.kind==='model'&&!a.internal).length;
  $('sidebar-folder').textContent=data.settings.assets_directory;$('sidebar-folder').title=data.settings.assets_directory;
  $('library-path').textContent=data.settings.assets_directory;$('assets-directory').value=data.settings.assets_directory;
  populateAssetSelects();renderLibrary();assetGenerator.images();
}
function bytes(value){return value>1024*1024?`${(value/1024/1024).toFixed(1)} MB`:`${Math.max(1,Math.round(value/1024))} KB`;}
function renderLibrary(){
  const q=$('asset-search').value.trim().toLocaleLowerCase('vi');
  const assets=S.assets.filter(a=>!a.internal&&(S.kind==='all'||a.kind===S.kind)&&`${a.name} ${a.description} ${a.tags.join(' ')}`.toLocaleLowerCase('vi').includes(q));
  const names={model:'MÔ HÌNH 3D',image:'HÌNH ẢNH',audio:'ÂM THANH',font:'FONT CHỮ'};
  $('library-grid').innerHTML=assets.map(a=>{
    const picture=a.preview||(a.kind==='image'?a.path:null);
    return `<article class="asset-card"><div class="asset-visual">${picture?`<img class="${a.kind==='model'?'model-thumb':''}" src="${assetURL(picture)}" loading="lazy" alt="${esc(a.name)}">`:icon({model:'cube',audio:'music',font:'grid',image:'image'}[a.kind])}<span class="asset-badge">${a.source==='blender'?'BLENDER ASSET':names[a.kind]}</span></div><div class="asset-details"><h3 title="${esc(a.name)}">${esc(a.name)}</h3><p>${esc(a.description||a.tags.join(' · ')||a.path)}</p>${a.kind==='audio'?`<audio controls preload="none" src="${assetURL(a.path)}"></audio>`:''}<div class="asset-footer"><small>${bytes(a.bytes)}</small>${a.kind==='model'?`<a class="text-button" href="${assetURL(a.path)}" target="_blank" rel="noopener">Mở GLB</a>`:a.kind==='image'?`<button class="text-button" data-use-ref="${esc(a.path)}">Dùng làm tham khảo</button>`:`<a class="text-button" href="${assetURL(a.path)}" target="_blank" rel="noopener">Mở file</a>`}</div></div></article>`;
  }).join('')||'<div class="empty-state">Chưa có tài nguyên phù hợp.<br>Tải file lên hoặc lưu các đối tượng từ một cảnh đã render.</div>';
}
async function uploadFile(file,category){
  const form=new FormData();form.append('file',file);form.append('category',category);
  toast(`Đang tải ${file.name}…`);
  const result=await api('/api/uploads',{method:'POST',body:form});S.assets=result.assets;populateAssetSelects();renderLibrary();return result.path;
}
function chooseFile(category,handler,multiple=false){
  S.fileCategory=category;S.fileHandler=handler;
  const accept={references:'.png,.jpg,.jpeg',images:'.png,.jpg,.jpeg',models:'.glb',music:'.mp3,.wav,.ogg,.m4a',voices:'.mp3,.wav,.ogg,.m4a',fonts:'.ttf,.otf'};
  $('file-input').accept=accept[category];$('file-input').multiple=multiple;$('file-input').value='';$('file-input').click();
}
async function addReference(path){
  if(busy())throw new Error('Chờ tác vụ hiện tại hoàn tất');
  const refs=S.project.draft.references;if(refs.includes(path))return;if(refs.length>=4)throw new Error('Tối đa 4 ảnh tham khảo');
  refs.push(path);markDirty();renderReferences();
}
async function loadHistory(){
  const jobs=await api('/api/jobs');
  $('history-grid').innerHTML=jobs.map(j=>`<article class="asset-card"><div class="asset-visual">${j.artifacts['preview.png']?`<img src="${jobURL(j.id,'preview.png')}" alt="${esc(j.title)}" loading="lazy">`:icon('cube')}<span class="asset-badge">${esc(j.state==='completed'?'HOÀN TẤT':j.state==='failed'?'THẤT BẠI':'ĐANG XỬ LÝ')}</span></div><div class="asset-details"><h3>${esc(j.title)}</h3><p>${j.mode==='video'?'Video':'Preview'} · ${esc(new Date(j.created).toLocaleString('vi-VN'))}</p><div class="asset-footer"><button class="text-button" data-import-job="${j.id}">Mở như dự án</button>${j.artifacts['video.mp4']?`<a class="text-button" href="${jobURL(j.id,'video.mp4')}?download=1">Tải MP4</a>`:''}</div></div></article>`).join('')||'<div class="empty-state">Chưa có bản render. Bắt đầu với một cảnh mẫu trong Studio.</div>';
}
async function openExport(){
  const job=S.project.job;if(!job||job.state!=='completed')return;
  const scene=await fetch(jobURL(job.id,'scene.json')).then(r=>r.json());
  const objects=scene.shots?.length?scene.shots.flatMap((shot,i)=>shot.objects.map(o=>({...o,name:`S${String(i+1).padStart(2,'0')}_${o.name}`,kind:shot.title}))):scene.objects;
  $('export-objects').innerHTML=objects.map(o=>`<label><input type="checkbox" value="${esc(o.name)}">${esc(o.name)} <span class="muted">· ${esc(o.kind)}</span></label>`).join('');
  $('asset-name').value='';$('asset-description').value='';$('asset-tags').value='';$('export-dialog').showModal();
}
function showElevenlabsStatus(data){
  $('elevenlabs-key-status').textContent=data.warning||(data.configured?(data.source==='project-env'?'Đang dùng key từ .env do ElevenLabs CLI cấu hình.':data.source==='saved'?'Đang dùng API key đã lưu trong Cài đặt.':'Đang dùng API key từ biến môi trường.'):'Chưa cấu hình API key.');
  $('delete-elevenlabs-key').disabled=!data.saved;
}
$('save-elevenlabs-key').onclick=safe(async()=>{
  const field=$('elevenlabs-api-key');
  const button=$('save-elevenlabs-key');button.disabled=true;
  try {showElevenlabsStatus(await api('/api/credentials/elevenlabs',{method:'POST',body:{api_key:field.value}}));field.value='';toast('Đã lưu API key ElevenLabs');}
  finally {button.disabled=false;}
});
$('delete-elevenlabs-key').onclick=safe(async()=>{
  showElevenlabsStatus(await api('/api/credentials/elevenlabs',{method:'DELETE'}));$('elevenlabs-api-key').value='';toast('Đã xóa key đã lưu');
});
async function boot(){
  await preferences.load();
  showElevenlabsStatus(await api('/api/credentials/elevenlabs'));
  const data=await api('/api/bootstrap');Object.assign(S,{assets:data.assets,projects:data.projects,settings:data.settings,voices:data.voices});
  $('connection-dot').classList.toggle('ready',data.blender_ready);$('connection-label').textContent=data.blender_ready?'Blender sẵn sàng':'Blender chưa sẵn sàng';
  $('health-cards').innerHTML=`<div class="health-card">Blender<small>${data.blender_ready?'Sẵn sàng render':esc(data.blender_error)}</small></div><div class="health-card">Codex CLI<small>${data.codex_available?'Đã tìm thấy CLI trên máy':'Chưa tìm thấy — hãy cài Codex CLI'}</small></div>`;
  $('voice-id').innerHTML=data.voices.map(v=>`<option value="${esc(v.id)}" ${v.disabled?'disabled':''}>${[v.name,v.disabled?(v.status==='verification'?'Chờ xác minh':'Chưa clone'):v.language,v.gender].filter(Boolean).map(esc).join(' · ')}</option>`).join('');
  const pendingVoices=data.voices.filter(v=>v.disabled);
  $('voice-clone-notice').hidden=!pendingVoices.length;
  $('voice-clone-notice').textContent=pendingVoices.map(v=>`${v.name}: ${v.status_message||'Giọng clone chưa sẵn sàng.'}`).join(' ');
  await loadLibrary();
  const stored=localStorage.getItem('frame-project'), found=data.projects.find(p=>p.id===stored)||data.projects[0];
  if(found)setForm(preferences.restore(await api(`/api/projects/${found.id}`)));else setForm(await api('/api/projects',{method:'POST',body:{}}));
  preferences.restoreUI();assetGenerator.images();
  S.projects=await api('/api/projects');renderRecent();
  const page=location.hash.slice(1);if(['studio','assetgen','library','history','settings'].includes(page))showPage(page);
  S.poll=setInterval(poll,2500);
}
for(const id of fields){$(id).addEventListener('input',()=>{markDirty();updateMetrics();if(['music','voice-file','voice-id'].includes(id))updateAudio();});}
$('scene-json').addEventListener('input',markDirty);
for(const id of ['aspect','resolution'])$(id).addEventListener('change',()=>{if(id==='aspect'&&$('resolution').value==='custom')$('resolution').value='draft';markDirty();updateMetrics();});
$('new-project').onclick=safe(()=>newProject());
$('save-project').onclick=safe(async()=>{await saveDraft();toast('Dự án đã được lưu');});
$('generate').onclick=safe(async()=>{await saveDraft();setForm(await api(`/api/projects/${S.project.id}/plan`,{method:'POST',body:{auto_render:true}}));});
$('pause-render').onclick=safe(async()=>{
  if(S.controlPending)return;
  const id=S.project.id, action=['pausing','paused'].includes(S.project.job?.state)?'resume':'pause';
  S.controlPending=true;updateProjectStatus();
  try{
    const project=await api(`/api/projects/${id}/control/${action}`,{method:'POST',body:{}});
    if(S.project?.id===id)S.project=project;
  }finally{S.controlPending=false;updateProjectStatus();}
});
$('retry-render').onclick=safe(async()=>{
  S.project=await api(`/api/projects/${S.project.id}/retry`,{method:'POST',body:{}});
  updateProjectStatus();toast('Đang tiếp tục render các khung hình còn thiếu.');
});
for(const [id,mode] of [['render-preview','preview'],['render-video','video']])$(id).onclick=safe(async()=>{await saveDraft();S.project=await api(`/api/projects/${S.project.id}/render`,{method:'POST',body:{mode}});updateProjectStatus();});
$('upload-references').onclick=()=>chooseFile('references',async path=>{await addReference(path);renderReferences();},true);
$('add-reference').onclick=safe(()=>{if(!$('existing-reference').value)throw new Error('Chọn một ảnh trong thư viện');return addReference($('existing-reference').value);});
for(const [id,category,select] of [['upload-voice','voices','voice-file'],['upload-music','music','music'],['upload-font','fonts','font']])$(id).onclick=()=>chooseFile(category,async path=>{S.project.draft[key(select)]=path;$(select).value=path;preferences.capture(select);markDirty();updateAudio();});
$('file-input').onchange=safe(async()=>{
  const category=S.fileCategory,handler=S.fileHandler;
  try{for(const file of [...$('file-input').files]){const path=await uploadFile(file,category);if(handler)await handler(path);}toast('Đã thêm tài nguyên');$('upload-dialog').close();await loadLibrary();}
  finally{$('file-input').value='';}
});
$('import-script').onclick=()=>$('script-file-input').click();
$('script-file-input').onchange=safe(async()=>{const file=$('script-file-input').files[0];if(!file)return;if(file.size>200000)throw new Error('Kịch bản tối đa 200 KB');$('prompt').value=await file.text();markDirty();updateMetrics();$('script-file-input').value='';});
$('preview-voice').onclick=safe(async()=>{
  const button=$('preview-voice');button.disabled=true;
  try{toast('Đang tạo đoạn nghe thử…');const result=await api('/api/voice-preview',{method:'POST',body:{voice:$('voice-id').value,rate:Number($('rate').value),text:$('narration').value||'Xin chào! Đây là giọng đọc cho video của bạn.'}});$('tts-player').src=assetURL(result.path);$('tts-player').hidden=false;await $('tts-player').play();}finally{button.disabled=false;}
});
$('library-upload').onclick=()=>$('upload-dialog').showModal();
$('choose-library-file').onclick=()=>chooseFile($('upload-category').value,null);
$('asset-search').oninput=renderLibrary;
$('refresh-history').onclick=safe(loadHistory);
$('pick-folder').onclick=safe(async()=>{const button=$('pick-folder');button.disabled=true;try{const result=await api('/api/folder-picker',{method:'POST',body:{}});if(result.path)$('assets-directory').value=result.path;}finally{button.disabled=false;}});
$('save-settings').onclick=safe(async()=>{await api('/api/settings',{method:'POST',body:{assets_directory:$('assets-directory').value}});await loadLibrary();toast('Đã lưu thư mục thư viện');});
$('fullscreen').onclick=safe(()=>$('preview-stage').requestFullscreen());
$('export-asset').onclick=safe(openExport);
$('select-all-objects').onclick=()=>{const boxes=[...$('export-objects').querySelectorAll('input')],select=boxes.some(b=>!b.checked);boxes.forEach(b=>b.checked=select);};
$('confirm-export').onclick=safe(async()=>{
  const names=[...$('export-objects').querySelectorAll('input:checked')].map(e=>e.value);
  if(!names.length)throw new Error('Chọn ít nhất một đối tượng');
  await api(`/api/projects/${S.project.id}/export`,{method:'POST',body:{job_id:S.project.current_job,name:$('asset-name').value,names,description:$('asset-description').value,tags:$('asset-tags').value.split(',').map(t=>t.trim()).filter(Boolean)}});
  $('export-dialog').close();S.project=await api(`/api/projects/${S.project.id}`);updateProjectStatus();
});
document.addEventListener('click',safe(async event=>{
  const el=event.target.closest('[data-page],[data-go],[data-tab],[data-project],[data-template],[data-voice],[data-remove-ref],[data-kind],[data-use-ref],[data-import-job]');if(!el)return;
  if(el.dataset.page||el.dataset.go){showPage(el.dataset.page||el.dataset.go);return;}
  if(el.dataset.tab){showTab(el.dataset.tab);return;}
  if(el.dataset.project){await openProject(el.dataset.project);localStorage.setItem('frame-project',el.dataset.project);return;}
  if(el.dataset.template){await newProject(el.dataset.template);return;}
  if(el.dataset.voice){if(busy())return;S.voiceMode=el.dataset.voice;preferences.capture('voice-mode');markDirty();updateAudio();return;}
  if(el.dataset.removeRef!==undefined){if(busy())return;S.project.draft.references.splice(Number(el.dataset.removeRef),1);markDirty();renderReferences();return;}
  if(el.dataset.kind){S.kind=el.dataset.kind;document.querySelectorAll('[data-kind]').forEach(b=>b.classList.toggle('active',b===el));renderLibrary();return;}
  if(el.dataset.useRef){await addReference(el.dataset.useRef);showPage('studio');showTab('script');return;}
  if(el.dataset.importJob){if(S.dirty&&!busy())await saveDraft();setForm(await api('/api/import-job',{method:'POST',body:{job_id:el.dataset.importJob}}));S.projects=await api('/api/projects');renderRecent();showPage('studio');return;}
}));
window.addEventListener('beforeunload',event=>{if(S.dirty){event.preventDefault();event.returnValue='';}});
const assetGenerator=initAssetGenerator({$,api,esc,icon,safe,toast,chooseFile,assetURL,loadLibrary,getAssets:()=>S.assets,useAsset:async path=>{
  if(busy())throw new Error('Chờ dự án hiện tại hoàn tất tác vụ');
  showPage('studio');showTab('script');toast('Asset đã có trong thư viện. AI sẽ dùng khi phù hợp với prompt.');
}});
boot().catch(error=>{$('connection-label').textContent='Không kết nối được máy chủ';toast(error.message,true);});
