export function createPreferences({$,api,toast,dimensions,getVoiceMode}){
  const key='frame-pending-preferences';
  const fields=['fps','samples','font','music','music-volume','voice-id','voice-file','rate','voice-volume','duck-music'];
  const uiFields=['aspect','resolution','assetgen-mode','assetgen-limit','assetgen-style'];
  let pending;try{pending=JSON.parse(localStorage.getItem(key)||'{}');}catch{pending={};}
  let value={video:{},ui:{}},timer,queue=Promise.resolve(),serverAvailable=true;
  const remember=()=>localStorage.setItem(key,JSON.stringify(pending));
  function flush(){
    clearTimeout(timer);
    queue=queue.catch(()=>{}).then(async()=>{
      if(!serverAvailable)return;
      if(!Object.values(pending).some(section=>Object.keys(section).length))return;
      const patch=structuredClone(pending);
      await api('/api/preferences',{method:'POST',body:patch,keepalive:true});
      for(const [section,items] of Object.entries(patch))for(const [id,v] of Object.entries(items)){
        if(JSON.stringify(pending[section]?.[id])===JSON.stringify(v))delete pending[section][id];
      }
      remember();
    }).catch(error=>{toast('Cài đặt đã giữ trên trình duyệt, chưa đồng bộ với máy chủ: '+error.message,true);});
    return queue;
  }
  function capture(id){
    const patch={video:{},ui:{}};
    if(fields.includes(id)){
      const el=$(id),name=id.replaceAll('-','_');
      patch.video[name]=el.type==='checkbox'?el.checked:['fps','samples','music-volume','rate','voice-volume'].includes(id)?Number(el.value):el.value||null;
    }else if(id==='voice-mode')patch.video.voice_mode=getVoiceMode();
    else if(uiFields.includes(id)){
      patch.ui[id]=$(id).value;
      if(['aspect','resolution'].includes(id)){
        [patch.video.width,patch.video.height]=dimensions();
        patch.ui.aspect=$('aspect').value;patch.ui.resolution=$('resolution').value;
      }
    }else return;
    for(const section of ['video','ui']){
      Object.assign(value[section],patch[section]);pending[section]={...pending[section],...patch[section]};
    }
    remember();clearTimeout(timer);timer=setTimeout(flush,200);
  }
  async function load(){
    // A running older server may finish its current render before it can restart.
    // Pending choices remain durable in the browser during that transition.
    let saved={video:{},ui:{}};
    try{saved=await api('/api/preferences');}catch(error){
      if(!/Server Studio chưa có chức năng này|API không có trong server/.test(error.message))throw error;
      serverAvailable=false;
    }
    value={video:{...saved.video,...pending.video},ui:{...saved.ui,...pending.ui}};
    if(Object.keys(pending).length)await flush();
  }
  function restore(project){
    const result=structuredClone(project);
    // Migrate the last project's choices once; later AI/project updates never replace defaults.
    if(!Object.keys(value.video).length){
      const names=[...fields.map(id=>id.replaceAll('-','_')),'width','height','voice_mode'];
      for(const name of names)if(result.draft[name]!==undefined)value.video[name]=result.draft[name];
      pending.video={...value.video,...pending.video};remember();timer=setTimeout(flush,200);
    }
    const changed=Object.entries(value.video).some(([k,v])=>JSON.stringify(result.draft[k])!==JSON.stringify(v));
    Object.assign(result.draft,value.video);
    if(changed)result.scene_current=false;
    return result;
  }
  function restoreUI(){for(const id of uiFields)if(value.ui[id]!==undefined&&[...$(id).options].some(o=>o.value===value.ui[id]))$(id).value=value.ui[id];}
  document.addEventListener('input',e=>capture(e.target.id));
  document.addEventListener('change',e=>capture(e.target.id));
  window.addEventListener('pagehide',()=>{flush();});
  return {load,restore,restoreUI,capture,flush};
}
