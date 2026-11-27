import assert from 'node:assert/strict';
import {api} from '../codex_blender/web/api.js';

const originalFetch=globalThis.fetch;
try{
  globalThis.fetch=async()=>new Response('Not Found',{status:404});
  await assert.rejects(api('/api/asset-generations'),/server|Server/);
  globalThis.fetch=async()=>new Response('<html>Error</html>',{status:500});
  await assert.rejects(api('/api/library'),/HTTP 500/);
  globalThis.fetch=async()=>new Response('<html>Unexpected page</html>',{status:200});
  await assert.rejects(api('/api/library'),/HTTP 200/);
  globalThis.fetch=async()=>new Response('null',{status:200});
  await assert.rejects(api('/api/library'),/định dạng/);
  globalThis.fetch=async()=>new Response(JSON.stringify({error:'A useful error'}),{status:400});
  await assert.rejects(api('/api/library'),/A useful error/);
  globalThis.fetch=async()=>new Response(JSON.stringify({id:'project',error:'previous job failed'}));
  assert.equal((await api('/api/projects/project')).id,'project');
  const options={method:'POST',body:{name:'asset'}};
  globalThis.fetch=async(url,request)=>{
    assert.equal(request.cache,'no-store');
    assert.equal(request.headers['X-Studio-Request'],'1');
    assert.equal(JSON.parse(request.body).name,'asset');
    return new Response('{"id":"job"}');
  };
  assert.equal((await api('/api/asset-generations',options)).id,'job');
  assert.deepEqual(options.body,{name:'asset'});
  globalThis.fetch=async()=>{throw new TypeError('Failed to fetch');};
  await assert.rejects(api('/api/library'),/Không kết nối/);
  console.log('API client regression checks: 8 passed');
}finally{globalThis.fetch=originalFetch;}
