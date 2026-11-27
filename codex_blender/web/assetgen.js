export function initAssetGenerator({$,api,esc,icon,safe,toast,chooseFile,assetURL,loadLibrary,getAssets,useAsset}){
  const G={references:[],jobs:[],selected:null,timer:null,loading:false,posting:false};
  const fileURL=(id,name,item)=>`/api/asset-generations/${id}${item?`/items/${encodeURIComponent(item)}`:''}/files/${name}`;
  const active=()=>G.jobs.some(j=>['planning','exporting'].includes(j.state));
  const results=j=>j.mode==='multiple'?(j.items||[]).filter(i=>i.result).map(i=>({...i.result,id:i.id})):j.result?[j.result]:[];
  const labels={inventory:'Đang nhận diện các đồ vật trong ảnh',pending:'Đang chờ dựng',planning:'Codex đang phân tích ảnh và dựng hình khối',rendering:'Blender đang dựng mô hình và render preview',exporting:'Đang xuất GLB và lưu vào thư viện',completed:'Đã lưu vào thư viện',failed:'Chưa tạo được asset'};
  function modeUI(){
    const batch=$('assetgen-mode').value==='multiple';
    $('assetgen-batch-options').hidden=!batch;
    $('assetgen-image-count').textContent=batch?'1 ảnh chứa nhiều đồ vật':'1–4 ảnh';
    $('assetgen-image-hint').textContent=batch?'PNG hoặc JPG · một ảnh tổng hợp nhiều đồ vật':'PNG hoặc JPG · thêm nhiều góc nhìn của cùng đối tượng';
    $('assetgen-generate').innerHTML=icon('spark')+(batch?'Dựng và lưu từng asset':'Dựng và lưu asset');
    $('assetgen-prompt').placeholder=batch?'Có thể chỉ rõ các món muốn lấy, ví dụ: bàn, ghế, đèn. Để trống để nhận diện các đồ vật riêng trong ảnh.':'Chỉ rõ đối tượng muốn lấy từ ảnh, màu sắc, bộ phận cần giữ hoặc cần bỏ.';
  }
  function images(){
    modeUI();
    const selected=$('assetgen-existing-image').value;
    $('assetgen-existing-image').innerHTML='<option value="">Chọn ảnh trong thư viện…</option>'+getAssets().filter(a=>a.kind==='image'&&!a.internal).map(a=>`<option value="${esc(a.path)}">${esc(a.name)}</option>`).join('');
    $('assetgen-existing-image').value=selected;
    $('assetgen-references').innerHTML=G.references.map((path,i)=>`<div class="assetgen-thumb"><img src="${assetURL(path)}" alt="Ảnh tham khảo ${i+1}"><button class="icon-button" data-remove-assetgen-ref="${i}" aria-label="Bỏ ảnh ${i+1}">${icon('close')}</button></div>`).join('');
    $('assetgen-generate').disabled=active()||G.posting;
  }
  async function addImage(path){
    if(!path||G.references.includes(path))return;
    const batch=$('assetgen-mode').value==='multiple';
    if(G.references.length>=(batch?1:4))throw new Error(batch?'Chế độ nhiều asset chỉ dùng một ảnh. Bỏ ảnh cũ để chọn ảnh khác.':'Tối đa 4 ảnh của cùng một đối tượng');
    G.references.push(path);images();
  }
  function resultCard(job,result){
    const url=name=>fileURL(job.id,name,result.id),name=result.name||job.name;
    return `<article class="assetgen-preview"><img src="${url('preview.png')}" alt="Mô hình ${esc(name)}"><div class="asset-details"><h3>${esc(name)}</h3><p>${esc(result.description||'Mô hình Blender đã lưu.')}</p></div><div class="result-actions"><button class="button primary small" data-use-generated-asset="${job.id}" ${result.id?`data-generated-item="${esc(result.id)}"`:''}>Dùng trong dự án</button><a class="button secondary small" href="${url('model.glb')}?download=1">Tải GLB</a><a class="text-button" href="${url('scene.blend')}?download=1">File Blender</a></div></article>`;
  }
  function render(){
    images();
    const job=G.jobs.find(j=>j.id===G.selected)||G.jobs[0],batch=job?.mode==='multiple',saved=job?results(job):[];
    $('assetgen-status').hidden=!job;
    $('assetgen-error').hidden=!job?.error;
    $('assetgen-error').textContent=job?.error||'';
    if(job){
      const failed=(job.items||[]).filter(i=>i.state==='failed').length;
      const progress=batch&&job.items?.length?`<p>Đã lưu ${saved.length}/${job.items.length} asset${failed?` · ${failed} món lỗi`:''}${job.current_item?` · Đang dựng: ${esc(job.current_item)}`:''}</p>`:'';
      $('assetgen-status').innerHTML=`<div class="status-row">${['planning','exporting'].includes(job.state)?'<span class="spinner"></span>':icon(job.state==='ready'?'check':'cube')}<strong>${esc(job.name)}</strong></div><p>${esc(labels[job.stage]||job.stage)}</p>${progress}${job.notes?`<p>${esc(job.notes)}</p>`:''}<a class="text-button" href="${fileURL(job.id,'planning.log')}" target="_blank" rel="noopener">Xem log dựng mô hình</a>${job.error?` <button class="text-button" data-retry-assetgen="${job.id}">Dùng lại đầu vào</button>`:''}`;
    }
    $('assetgen-result').hidden=!(saved.length||(batch&&job.items?.length));
    $('assetgen-result').className=batch?'assetgen-batch-grid':'';
    $('assetgen-result').innerHTML=batch?(job.items||[]).map(item=>item.result?resultCard(job,{...item.result,id:item.id}):`<article class="assetgen-preview assetgen-pending"><h3>${esc(item.name)}</h3><p>${esc(labels[item.stage]||item.stage)}</p>${item.error?`<div class="error-box">${esc(item.error)}</div>`:''}</article>`).join(''):saved.map(r=>resultCard(job,r)).join('');
    $('assetgen-history').innerHTML=G.jobs.map(j=>{
      const list=results(j),first=list[0],badge=j.mode==='multiple'?`${list.length}/${j.items?.length||'?'} ASSETS`:j.stage==='completed'?'BLENDER ASSET':j.state==='error'?'THỬ LẠI':'ĐANG DỰNG';
      return `<article class="asset-card"><div class="asset-visual">${first?`<img class="model-thumb" src="${fileURL(j.id,'preview.png',first.id)}" alt="${esc(j.name)}" loading="lazy">`:icon('cube')}<span class="asset-badge">${esc(badge)}</span></div><div class="asset-details"><h3>${esc(j.name)}</h3><p>${esc(labels[j.stage]||j.stage)}</p><div class="asset-footer"><button class="text-button" data-select-assetgen="${j.id}">Xem chi tiết</button></div></div></article>`;
    }).join('')||'<div class="empty-state">Chưa có asset từ ảnh. Thêm ảnh để dựng mô hình đầu tiên.</div>';
  }
  async function load(){
    if(G.loading)return;
    G.loading=true;
    try{
      const previous=new Set(G.jobs.flatMap(results).map(r=>r.path));
      G.jobs=await api('/api/asset-generations');render();
      if(G.jobs.flatMap(results).some(r=>!previous.has(r.path)))await loadLibrary();
      clearTimeout(G.timer);
      if(active())G.timer=setTimeout(()=>safe(load)(),2500);
    }finally{G.loading=false;}
  }
  $('assetgen-mode').onchange=images;
  $('assetgen-upload').onclick=()=>chooseFile('references',addImage,$('assetgen-mode').value!=='multiple');
  $('assetgen-add-image').onclick=safe(()=>addImage($('assetgen-existing-image').value));
  $('refresh-asset-generations').onclick=safe(load);
  $('assetgen-generate').onclick=safe(async()=>{
    const body={name:$('assetgen-name').value.trim(),prompt:$('assetgen-prompt').value.trim(),style:$('assetgen-style').value,references:[...G.references],mode:$('assetgen-mode').value,max_assets:Number($('assetgen-limit').value)};
    if(!body.name)throw new Error('Nhập tên asset hoặc bộ assets');
    if(!body.references.length)throw new Error('Thêm ít nhất một ảnh tham khảo');
    if(body.mode==='multiple'&&body.references.length!==1)throw new Error('Chế độ nhiều asset cần đúng một ảnh. Bỏ các ảnh thừa trước khi tạo.');
    G.posting=true;images();
    try{const job=await api('/api/asset-generations',{method:'POST',body});G.selected=job.id;await load();toast('Đã bắt đầu dựng asset từ ảnh');}
    finally{G.posting=false;images();}
  });
  $('page-assetgen').addEventListener('click',safe(async event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.dataset.removeAssetgenRef!==undefined){G.references.splice(Number(button.dataset.removeAssetgenRef),1);images();}
    if(button.dataset.selectAssetgen){G.selected=button.dataset.selectAssetgen;render();$('assetgen-status').scrollIntoView({block:'center',behavior:'smooth'});}
    if(button.dataset.retryAssetgen){
      const job=G.jobs.find(j=>j.id===button.dataset.retryAssetgen);G.references=[...job.references];$('assetgen-name').value=job.name;$('assetgen-prompt').value=job.prompt;$('assetgen-mode').value=job.mode||'single';$('assetgen-limit').value=String(job.max_assets||20);if(job.style&&Array.from($('assetgen-style').options).some(o=>o.value===job.style))$('assetgen-style').value=job.style;images();$('assetgen-name').focus();
    }
    if(button.dataset.useGeneratedAsset){
      const job=G.jobs.find(j=>j.id===button.dataset.useGeneratedAsset),result=results(job).find(r=>(r.id||'')===(button.dataset.generatedItem||''));
      await loadLibrary();
      if(!getAssets().some(a=>a.path===result.path))throw new Error('Asset nằm trong thư viện trước đó. Chọn lại thư mục trong Cài đặt để dùng.');
      await useAsset(result.path);
    }
  }));
  modeUI();
  return {load,images};
}
