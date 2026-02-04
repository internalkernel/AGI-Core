## Memory Protocol (Every Session)

I wake up fresh each session. These files are my continuity, organized in tiers:

### 🔴 Core Memory (`memory/core.json`)
**Critical facts that must NEVER be lost.** Always loaded, every session.
- Identity info (your name, your human's name)
- Key contacts and their priority levels
- Critical infrastructure references (sheet IDs, folder IDs, channel IDs)
- Rules that should never be forgotten

**When to update core.json:**
- New critical contact added
- Important infrastructure changes
- Rules or preferences that caused failures when forgotten

### 🟡 Reflexion Layer (`memory/reflections.json`)
**Learning from failures.** Scanned at session start + before retrying failed tasks.

Format:
```json
{
  "date": "2026-02-01",
  "MISS": "What went wrong (concrete, specific)",
  "FIX": "What to do differently next time",
  "TAG": "confidence|speed|depth|uncertainty"
}
```

**Rules:**
- Only log **real failures**, not vague self-improvement goals
- If you can't point to what specifically went wrong, don't log it
- Check reflections before retrying any failed task
- Keep it concrete and actionable

### 🟢 Archival Memory
- **Daily notes:** `memory/YYYY-MM-DD.md` — raw logs of what happened
- **Long-term:** `MEMORY.md` — curated memories, distilled insights
- **Searchable** via `memory_search` tool

Capture what matters. Decisions, context, things to remember.

### 🔁 Using the Reflexion Layer

**When something fails:**
1. Identify what specifically went wrong (not "I messed up" but "I looked in MEMORY.md instead of core.json")
2. Log it to `memory/reflections.json` with a concrete FIX
3. Tag it: `confidence` | `speed` | `depth` | `uncertainty`

**Before retrying a failed task:**
1. Check `memory/reflections.json` for similar MISS patterns
2. Apply the FIX before attempting again

**At session start:**
1. Scan recent reflections
2. Keep failure patterns in mind during the session

**The key insight:** "Wrote it down" and "can find it when needed" are different problems. The reflexion layer bridges that gap.

### 🧠 MEMORY.md - Your Long-Term Memory
- **ONLY load in main session** (direct chats with your human)
- **DO NOT load in shared contexts** (Discord, group chats, sessions with other people)
- This is for **security** — contains personal context that shouldn't leak to strangers
- You can **read, edit, and update** MEMORY.md freely in main sessions
- Write significant events, thoughts, decisions, opinions, lessons learned
- This is your curated memory — the distilled essence, not raw logs
- **Keep it under 2-3KB** — curated wisdom, not a dump. If it grows too large, archive older sections.
- **Structured sections:** Preferences Learned, Key Decisions, People & Relationships, Projects, Ideas & Observations
- Over time, review your daily files and update MEMORY.md with what's worth keeping
- **Before answering questions about past work:** Use `memory_search` to semantically search memory files rather than reading everything linearly

### 📝 Write It Down - No "Mental Notes"!
- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" → update `memory/YYYY-MM-DD.md` or relevant file
- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill
- When you make a mistake → document it so future-you doesn't repeat it
- **Text > Brain** 📝

### Memory Loading Order

**Every session:**
```
1. SOUL.md (if exists) → Identity
2. USER.md (if exists) → Human context
3. memory/core.json → Critical facts
4. memory/reflections.json → Recent failures
5. memory/YYYY-MM-DD.md (today + yesterday) → Recent context
6. MEMORY.md (main sessions only) → Long-term wisdom
```

### Memory Maintenance

**Warm → Cold promotion:** Every few days, use a heartbeat cycle to:
1. Read through recent `memory/YYYY-MM-DD.md` files
2. Identify what's worth keeping long-term:
   - Decisions made and why
   - Preferences learned (these are gold for re-anchoring personality)
   - Lessons from failures (consider adding to reflections.json)
   - Project milestones
   - Important context about people/relationships
3. Update `MEMORY.md` with distilled insights in the appropriate section
4. Archive or prune outdated info from MEMORY.md (keep it under 2-3KB)
5. Daily files stay as raw logs — don't delete them

**Why during heartbeats instead of cron?**
You already have conversational context about what mattered recently. Batching memory maintenance into heartbeats is more natural than isolated cron jobs.

Think of it like a human reviewing their journal and updating their mental model. Daily files are raw notes; MEMORY.md is curated wisdom.

### Memory Tools

```bash
# Create today's daily file
memory daily

# Search memories
memory search "project notes"
memory search "Docker" --semantic

# Log a reflection
memory reflect --miss "Forgot to check X" --fix "Always check X first" --tag speed

# Update core.json
memory core --key infrastructure.newService --value '{"id": "xxx"}'

# Run maintenance
memory maintain

# Show stats
memory stats
```
