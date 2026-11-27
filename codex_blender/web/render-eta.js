export function renderETA(job, state){
  if(job?.mode!=='video'||!['queued','rendering','pausing','paused','encoding','completed'].includes(state))return '';
  if(state==='completed')return 'Đã hoàn tất';
  if(state==='paused')return 'Đã tạm dừng';
  if(state==='pausing')return 'Đang chờ tạm dừng';
  if(state==='encoding'||(state==='rendering'&&job.frames_rendered>=job.frames_total))return 'Đang hoàn tất MP4…';
  if(typeof job.eta_seconds!=='number'||!Number.isFinite(job.eta_seconds)||job.eta_seconds<=0)return 'Đang ước tính…';
  const seconds=Math.ceil(job.eta_seconds);
  if(seconds<60)return `Còn khoảng ${seconds} giây`;
  const minutes=Math.ceil(seconds/60);
  if(minutes<60)return `Còn khoảng ${minutes} phút`;
  const hours=Math.floor(minutes/60),rest=minutes%60;
  return `Còn khoảng ${hours} giờ${rest?` ${rest} phút`:''}`;
}
