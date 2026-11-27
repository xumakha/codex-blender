export async function api(url, options={}) {
  const headers={'X-Studio-Request':'1',...options.headers};
  const request={...options,headers,cache:'no-store'};
  if(request.body && !(request.body instanceof FormData)) {
    headers['Content-Type']='application/json';request.body=JSON.stringify(request.body);
  }
  let response;
  try{response=await fetch(url,request);}
  catch{throw new Error('Không kết nối được Studio. Chạy start-studio.cmd rồi thử lại.');}
  let body;
  try{body=JSON.parse(await response.text());}
  catch{
    if(response.status===404)throw new Error('Server Studio chưa có chức năng này. Chạy lại start-studio.cmd để cập nhật.');
    throw new Error(`Studio trả về phản hồi không hợp lệ (HTTP ${response.status}). Chạy lại start-studio.cmd; nếu còn lỗi, xem studio-data/server.log.`);
  }
  if(body===null||typeof body!=='object')throw new Error(`Studio trả về dữ liệu không đúng định dạng (HTTP ${response.status}).`);
  if(!response.ok)throw new Error(typeof body.error==='string'?body.error:`Yêu cầu thất bại (HTTP ${response.status}).`);
  return body;
}
