"""Resume a failed refrigerator project using Studio's saved checkpoint."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex_blender import studio

if len(sys.argv) != 2:
    raise SystemExit('Usage: python scripts/retry_food_asset.py PROJECT_ID')

pid = sys.argv[1]
studio.retry_render(pid)
while True:
    project = studio.read_project(pid)
    job = project.get('job', {})
    if project['state'] == 'error' or (project['state'] == 'ready' and job.get('state') == 'failed'):
        raise SystemExit(project.get('error') or job.get('error'))
    if project['state'] == 'ready' and job.get('state') in {None, 'completed'}:
        print(job.get('artifacts', {}) or {'project': pid, 'generation': project.get('generation')})
        break
    time.sleep(2)
