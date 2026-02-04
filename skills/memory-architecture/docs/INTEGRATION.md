# Integration Guide

How to integrate the Memory System into your OpenClaw agent.

## Session Start Routine

Add this loading protocol to your agent's session initialization:

### Python Example

```python
import json
from pathlib import Path
from datetime import datetime

def load_memory_stack():
    """Load the cognitive memory stack on session start."""
    memory = {}
    
    # Tier 1 — Always load
    memory['core'] = json.load(open('memory/core.json'))
    memory['reflections'] = json.load(open('memory/reflections.json'))
    
    # Tier 2 — Context
    today = datetime.now().strftime('%Y-%m-%d')
    daily_file = Path(f'memory/{today}.md')
    if daily_file.exists():
        memory['today'] = daily_file.read_text()
    
    # Check if main session (direct chat with human)
    is_main_session = check_if_main_session()  # Your logic here
    if is_main_session:
        memory['long_term'] = Path('MEMORY.md').read_text()
    
    return memory

def check_reflections_before_retry(task_type: str):
    """Check reflections.json before retrying a failed task."""
    reflections = json.load(open('memory/reflections.json'))
    
    for entry in reflections.get('reflections', []):
        if task_type.lower() in entry['MISS'].lower():
            print(f"⚠️  Found previous failure: {entry['MISS']}")
            print(f"💡 Fix: {entry['FIX']}")
            return entry['FIX']
    
    return None
```

### JavaScript/Node.js Example

```javascript
const fs = require('fs');
const path = require('path');

class MemoryLoader {
  constructor(memoryDir = './memory') {
    this.memoryDir = memoryDir;
  }

  loadStack(isMainSession = false) {
    const memory = {};
    
    // Tier 1 — Always load
    memory.core = JSON.parse(
      fs.readFileSync(path.join(this.memoryDir, 'core.json'), 'utf8')
    );
    memory.reflections = JSON.parse(
      fs.readFileSync(path.join(this.memoryDir, 'reflections.json'), 'utf8')
    );
    
    // Tier 2 — Context
    const today = new Date().toISOString().split('T')[0];
    const dailyPath = path.join(this.memoryDir, `${today}.md`);
    if (fs.existsSync(dailyPath)) {
      memory.today = fs.readFileSync(dailyPath, 'utf8');
    }
    
    // Main session only
    if (isMainSession) {
      memory.longTerm = fs.readFileSync('MEMORY.md', 'utf8');
    }
    
    return memory;
  }
}

module.exports = { MemoryLoader };
```

## Writing to Memory

### Log a Daily Entry

```python
from datetime import datetime

def log_daily(section: str, content: str):
    """Append content to today's daily file."""
    today = datetime.now().strftime('%Y-%m-%d')
    daily_path = f'memory/{today}.md'
    
    # Read existing or create new
    if Path(daily_path).exists():
        existing = Path(daily_path).read_text()
    else:
        existing = f"# {today} - {datetime.now().strftime('%A')}\n\n"
    
    # Find section and append
    lines = existing.split('\n')
    section_idx = None
    for i, line in enumerate(lines):
        if line.startswith(f'## {section}'):
            section_idx = i
            break
    
    if section_idx is not None:
        # Insert after section header
        lines.insert(section_idx + 1, f"- {content}")
        Path(daily_path).write_text('\n'.join(lines))
```

### Log a Reflection

```python
import json
from datetime import datetime

def log_reflection(miss: str, fix: str, tag: str = "uncertainty"):
    """Log a MISS/FIX entry to reflections.json."""
    reflections_path = 'memory/reflections.json'
    
    with open(reflections_path, 'r') as f:
        data = json.load(f)
    
    entry = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "MISS": miss,
        "FIX": fix,
        "TAG": tag
    }
    
    data['reflections'].insert(0, entry)
    data['_meta']['lastUpdated'] = datetime.now().strftime('%Y-%m-%d')
    
    with open(reflections_path, 'w') as f:
        json.dump(data, f, indent=2)
```

### Update Core Memory

```python
def update_core(key_path: str, value):
    """Update core.json with a dot-notation path."""
    import json
    
    with open('memory/core.json', 'r') as f:
        core = json.load(f)
    
    keys = key_path.split('.')
    current = core
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value
    core['_meta']['lastUpdated'] = datetime.now().strftime('%Y-%m-%d')
    
    with open('memory/core.json', 'w') as f:
        json.dump(core, f, indent=2)

# Example: update_core('infrastructure.newService', {'id': 'xxx'})
```

## Searching Memory

### Using the Python Module

```python
import subprocess

def search_memory(query: str, method='semantic'):
    """Search memory using available methods."""
    if method == 'semantic':
        result = subprocess.run(
            ['python', 'memory/memory_embed.py', 'search', query],
            capture_output=True,
            text=True
        )
        return result.stdout
    elif method == 'decay':
        result = subprocess.run(
            ['node', 'memory/memory-search.js', query],
            capture_output=True,
            text=True
        )
        return result.stdout
    else:
        # Fallback to simple search
        from memory.utils.memory_cli import MemorySystem
        mem = MemorySystem()
        return mem.search(query)
```

### Using the CLI

```python
import subprocess

def memory_cli(*args):
    """Call the memory CLI."""
    result = subprocess.run(
        ['python', 'memory/memory_cli.py'] + list(args),
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr

# Examples
memory_cli('search', 'project notes', '--semantic')
memory_cli('reflect', '--miss', 'Forgot X', '--fix', 'Always check X')
memory_cli('maintain')
```

## Automated Maintenance

### Heartbeat Integration

Add to your `HEARTBEAT.md` or heartbeat handler:

```python
import json
from datetime import datetime, timedelta

def run_memory_maintenance():
    """Run during heartbeat every few days."""
    state_file = 'memory/heartbeat-state.json'
    
    # Load state
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {'lastMemoryMaintenance': None}
    
    # Check if maintenance needed (every 3 days)
    if state['lastMemoryMaintenance']:
        last = datetime.fromisoformat(state['lastMemoryMaintenance'])
        if datetime.now() - last < timedelta(days=3):
            return  # Skip this time
    
    # Run maintenance
    import subprocess
    subprocess.run(['python', 'memory/memory_cli.py', 'maintain'])
    
    # Update state
    state['lastMemoryMaintenance'] = datetime.now().isoformat()
    with open(state_file, 'w') as f:
        json.dump(state, f)
```

### Cron Job

```bash
# Run maintenance every 3 days at 2 AM
0 2 */3 * * cd /root/clawd && python memory/memory_cli.py maintain
```

## Best Practices

### 1. Always Load Core First

```python
# Good: Load core before making decisions
core = json.load(open('memory/core.json'))
if 'critical_rule' in core.get('rules', {}):
    apply_rule(core['rules']['critical_rule'])
```

### 2. Check Reflections Before Retrying

```python
# Before retrying a failed task
def retry_task(task_type):
    fix = check_reflections_before_retry(task_type)
    if fix:
        print(f"Applying previous fix: {fix}")
    # ... retry logic
```

### 3. Write Significant Events Immediately

```python
def make_decision(decision, rationale):
    log_daily('Decisions Made', f"{decision} because {rationale}")
    # ... proceed with decision
```

### 4. Search Before Asking

```python
def answer_question(question):
    # Search memory first
    context = search_memory(question)
    if context:
        return generate_answer(question, context)
    # Fall back to other methods
```

### 5. Security: Don't Load MEMORY.md in Shared Contexts

```python
def load_memory(is_direct_chat):
    memory = load_core_and_reflections()
    if is_direct_chat:
        memory['long_term'] = load_long_term_memory()
    return memory
```

## Troubleshooting

### Memory Not Persisting

Check:
- Files are being written to correct path
- `memory/` directory is in your workspace
- Files are committed to git (if using version control)

### Search Not Working

Check:
- For semantic search: Ollama is running (`curl http://localhost:11434/api/tags`)
- Index is built: `python memory_embed.py index`
- Node.js is available for decay search: `node --version`

### Large MEMORY.md

Run maintenance regularly:
```bash
python memory/memory_cli.py maintain
```

Consider archiving old sections to separate files.
