from pathlib import Path
import sys

current = Path.cwd()
while current != current.parent:
    if (current / '.git').exists() or (current / '.claude').exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

lib_path = project_root / 'plugins/autonomous-dev/lib'
if lib_path.exists():
    sys.path.insert(0, str(lib_path))
    try:
        from agent_tracker import AgentTracker
        AgentTracker.save_agent_checkpoint('implementer', 'Implementation complete - All 46 tests pass')
        print('✅ Checkpoint saved')
    except ImportError:
        print('ℹ️ Checkpoint skipped (user project)')
