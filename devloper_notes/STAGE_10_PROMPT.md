# System Prompt: Stage 10 - Advanced Agent Routing (Multi-Agent Architecture)

## Context

You are implementing **Stage 10** of the VIB project. The previous stages are **already complete**:

- ✅ Stages 0-4: MVP (single unified agent)
- ✅ Stage 5: Mobile app with idempotency
- ✅ Stage 6: Internal calendar
- ✅ Stage 7: Google Calendar sync
- ✅ Stage 8: Passkey authentication
- ✅ Stage 9: Location reminders (optional)

## Your Mission: Stage 10

Evolve from **single unified agent** to **multi-agent architecture** with:
- **Specialist agents**: Dedicated agents for Reminders, Notes, Knowledge Base, Calendar
- **Router agent**: Intelligently routes user queries to appropriate specialist
- **Tool orchestration**: Specialists can call tools directly without round-tripping through main agent
- **A/B testing framework**: Measure single vs multi-agent performance

## ⚠️ CRITICAL DECISION GATE

**DO NOT PROCEED** unless ALL conditions are met:

- [ ] **6+ months of usage data**: You have comprehensive logs showing failure patterns
- [ ] **Single agent accuracy <80%**: Current unified agent makes frequent mistakes on specific task types
- [ ] **Clear specialization need**: You can identify 3+ distinct task categories that benefit from specialized prompts
- [ ] **A/B testing infrastructure**: You can measure impact (don't just guess it's better)
- [ ] **Complexity acceptance**: Multi-agent adds significant complexity for marginal gains

**Why this is PREMATURE for most users**:

1. **Modern LLMs are good generalists**: Claude 3.5 Sonnet, GPT-4, Gemini Pro handle diverse tasks well
2. **Native function calling works**: LLMs are trained to select correct tools without routing layer
3. **Complexity cost**: Multi-agent = more prompts to maintain, more failure modes, harder debugging
4. **Latency**: Extra routing step adds 1-2 seconds per query
5. **Cost**: Router LLM call + specialist LLM call = 2x token usage

**When multi-agent DOES make sense**:

- You have very specialized domains (medical, legal, technical) where generic prompts fail
- You want to use different models per task (e.g., fast cheap model for simple tasks, expensive smart model for complex)
- You're hitting context limits and need to isolate task-specific knowledge

---

## Deliverables (If Proceeding Despite Warnings)

### 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Message                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  Router Agent (Claude)                  │
│  "Classify intent: reminder, note, kb_search, calendar" │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
   ┌─────────┐     ┌─────────┐   ┌──────────┐    ┌──────────┐
   │Reminder │     │  Note   │   │    KB    │    │ Calendar │
   │ Agent   │     │ Agent   │   │  Agent   │    │  Agent   │
   └────┬────┘     └────┬────┘   └────┬─────┘    └────┬─────┘
        │               │             │               │
        └───────────────┴─────────────┴───────────────┘
                         │
                         ▼
               ┌─────────────────────┐
               │    Tool Execution   │
               │ (create_reminder,   │
               │  search_notes, etc) │
               └─────────────────────┘
```

**Key Differences from MVP**:

| Aspect | MVP (Single Agent) | Stage 10 (Multi-Agent) |
|--------|-------------------|----------------------|
| Agent count | 1 unified agent | 1 router + 4 specialists |
| Prompt management | 1 system prompt | 5 specialized prompts |
| Routing | LLM decides tool | Router classifies intent |
| Latency | 1 LLM call | 2 LLM calls (router + specialist) |
| Cost | 1x tokens | 2x tokens |
| Complexity | Low | High |

---

### 2. Database Schema

Create `migrations/008_add_agent_routing.sql`:

```sql
-- Stage 10: Multi-agent routing analytics

-- Agent invocations (for analytics)
CREATE TABLE agent_invocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    message_id UUID REFERENCES messages(id),
    agent_type TEXT NOT NULL,  -- router, reminder, note, kb, calendar
    intent TEXT,  -- Classified intent from router
    confidence NUMERIC(3, 2),  -- Router confidence (0.0-1.0)
    tools_called TEXT[],  -- Array of tool names used
    success BOOLEAN,
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- A/B test assignments (for controlled experiments)
CREATE TABLE ab_test_assignments (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    variant TEXT NOT NULL,  -- single_agent, multi_agent
    assigned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_agent_invocations_user ON agent_invocations(user_id, created_at);
CREATE INDEX idx_agent_invocations_agent ON agent_invocations(agent_type);
CREATE INDEX idx_agent_invocations_success ON agent_invocations(success);
```

---

### 3. Agent Implementations

#### A. Router Agent

**File**: `app/agents/router.py`

```python
from enum import Enum
from pydantic import BaseModel

class AgentType(str, Enum):
    REMINDER = "reminder"
    NOTE = "note"
    KB_SEARCH = "kb_search"
    CALENDAR = "calendar"
    GENERAL = "general"

class RoutingDecision(BaseModel):
    agent: AgentType
    confidence: float
    reasoning: str

ROUTER_SYSTEM_PROMPT = """
You are a routing assistant for VIB. Your ONLY job is to classify user messages into categories.

Categories:
- **reminder**: User wants to create, update, list, or cancel reminders. Time-based or location-based.
  Examples: "Remind me to call mom tomorrow", "What are my reminders?", "Cancel the dentist reminder"

- **note**: User wants to create, update, search, or organize notes.
  Examples: "Add a note about visa rules", "Find my notes on travel", "Update the project planning note"

- **kb_search**: User wants to search documents or ask questions about uploaded files.
  Examples: "What does the PDF say about fees?", "Summarize my research papers", "Search documents for 'contract terms'"

- **calendar**: User wants to create, view, or manage calendar events.
  Examples: "Create event next Monday at 2pm", "Show my calendar for this week", "Reschedule the team meeting"

- **general**: Conversational, greetings, help requests, or unclear intent.
  Examples: "Hello", "How does VIB work?", "What can you do?"

Respond ONLY with valid JSON:
{
  "agent": "reminder|note|kb_search|calendar|general",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}

Be decisive. If unsure, use "general" agent.
"""

async def route_message(message: str, user_id: UUID) -> RoutingDecision:
    """
    Route user message to appropriate specialist agent.
    """

    # Call LLM with routing prompt
    response = await llm.chat(
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        temperature=0.3,  # Lower temperature for consistent routing
        max_tokens=200,
    )

    # Parse routing decision
    try:
        decision_json = json.loads(response.content)
        decision = RoutingDecision(**decision_json)
    except Exception as e:
        logger.error("router_parse_error", extra={"error": str(e), "response": response.content})
        # Fallback to general agent
        decision = RoutingDecision(
            agent=AgentType.GENERAL,
            confidence=0.5,
            reasoning="Failed to parse router response"
        )

    # Log routing decision
    await db.log_agent_invocation(
        user_id=user_id,
        agent_type="router",
        intent=decision.agent,
        confidence=decision.confidence,
    )

    return decision
```

#### B. Reminder Specialist Agent

**File**: `app/agents/reminder_agent.py`

```python
REMINDER_AGENT_PROMPT = """
You are the Reminder Specialist for VIB. Your expertise is creating, managing, and organizing reminders.

Available tools:
- create_reminder: Create time-based or location-based reminder
- update_reminder: Modify existing reminder
- list_reminders: Show user's reminders
- cancel_reminder: Delete a reminder
- snooze_reminder: Postpone reminder

Capabilities:
- Parse natural language time: "tomorrow at 5pm", "next Monday", "in 2 hours"
- Support recurring reminders: "every Monday", "daily at 9am"
- Smart defaults: If no time specified, suggest appropriate time based on context
- Link reminders to calendar events or notes when relevant

Best practices:
- Always confirm reminder details before creating
- If time is ambiguous, ask for clarification
- For recurring reminders, explain the RRULE in plain English
- Use timezone from user profile (default: UTC)

Examples:
User: "Remind me to call mom tomorrow"
You: I'll create a reminder to call mom tomorrow. What time works best? (Default: 5pm)

User: "Every Monday at 9am remind me about standup"
You: *calls create_reminder with RRULE: FREQ=WEEKLY;BYDAY=MO* Done! You'll be reminded every Monday at 9am about standup.
"""

async def reminder_agent_execute(message: str, user_id: UUID, conversation_history: list):
    """
    Execute reminder specialist agent.
    """

    # Build messages with agent prompt
    messages = [
        {"role": "system", "content": REMINDER_AGENT_PROMPT},
        *conversation_history,
        {"role": "user", "content": message}
    ]

    # Get available tools (only reminder-related)
    tools = [
        create_reminder,
        update_reminder,
        list_reminders,
        cancel_reminder,
        snooze_reminder,
    ]

    # Call LLM with tools
    response = await llm.chat_with_tools(
        messages=messages,
        tools=tools,
        temperature=0.7,
    )

    return response
```

#### C. Knowledge Base Specialist Agent

**File**: `app/agents/kb_agent.py`

```python
KB_AGENT_PROMPT = """
You are the Knowledge Base Specialist for VIB. Your expertise is searching and synthesizing information from user's notes and documents.

Available tools:
- search_knowledge_base: Semantic search across notes and documents
- get_document_context: Retrieve full context from a specific document

Capabilities:
- Multi-document synthesis: Combine information from multiple sources
- Structured citations: Always cite sources with [Title, location]
- Relevance filtering: Only return highly relevant results (score >0.7)
- Follow-up questions: Ask clarifying questions to narrow search

Best practices:
- Always provide citations for claims
- If search returns no results, suggest reformulating query
- Summarize long documents concisely
- Distinguish between notes and uploaded documents in responses

Citation format:
Answer: [Claim] [Source, p.X]

Example:
User: "What are the visa requirements?"
You: *searches knowledge_base for "visa requirements"*
Based on your documents:
- Valid passport required [VisaRules.pdf, p.3]
- Application fee: $50 [ConsulateGuide.pdf, p.12]
- Processing time: 5-7 business days [YourNotes.md]
"""

async def kb_agent_execute(message: str, user_id: UUID, conversation_history: list):
    """
    Execute KB specialist agent.
    """

    messages = [
        {"role": "system", "content": KB_AGENT_PROMPT},
        *conversation_history,
        {"role": "user", "content": message}
    ]

    tools = [
        search_knowledge_base,
        get_document_context,
    ]

    response = await llm.chat_with_tools(
        messages=messages,
        tools=tools,
        temperature=0.5,
    )

    return response
```

#### D. Orchestrator (Main Entry Point)

**File**: `app/api/routers/chat.py` (modify existing)

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user = Depends(get_current_user),
):
    """
    Main chat endpoint with multi-agent routing.
    """

    # Check A/B test assignment
    ab_variant = await db.get_ab_test_variant(current_user.id)

    if ab_variant == "multi_agent":
        # Use multi-agent architecture
        return await multi_agent_chat(request.message, current_user.id)
    else:
        # Use single unified agent (MVP approach)
        return await single_agent_chat(request.message, current_user.id)


async def multi_agent_chat(message: str, user_id: UUID):
    """
    Multi-agent chat with routing.
    """

    start_time = datetime.utcnow()

    # Step 1: Route to specialist
    routing = await route_message(message, user_id)

    logger.info("agent_routing", extra={
        "user_id": str(user_id),
        "agent": routing.agent,
        "confidence": routing.confidence,
    })

    # Step 2: Execute specialist agent
    conversation_history = await db.get_conversation_history(user_id, limit=10)

    if routing.agent == AgentType.REMINDER:
        response = await reminder_agent_execute(message, user_id, conversation_history)
    elif routing.agent == AgentType.NOTE:
        response = await note_agent_execute(message, user_id, conversation_history)
    elif routing.agent == AgentType.KB_SEARCH:
        response = await kb_agent_execute(message, user_id, conversation_history)
    elif routing.agent == AgentType.CALENDAR:
        response = await calendar_agent_execute(message, user_id, conversation_history)
    else:
        response = await general_agent_execute(message, user_id, conversation_history)

    # Step 3: Log invocation
    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

    await db.log_agent_invocation(
        user_id=user_id,
        agent_type=routing.agent,
        intent=routing.agent,
        confidence=routing.confidence,
        tools_called=response.tools_called,
        success=response.success,
        latency_ms=latency_ms,
    )

    return response
```

---

### 4. A/B Testing Framework

**File**: `app/services/ab_testing.py`

```python
import random

async def assign_ab_test_variant(user_id: UUID) -> str:
    """
    Assign user to A/B test variant.
    50/50 split: single_agent vs multi_agent.
    """

    existing = await db.get_ab_test_variant(user_id)
    if existing:
        return existing

    # Random assignment
    variant = random.choice(["single_agent", "multi_agent"])

    await db.create_ab_test_assignment(
        user_id=user_id,
        variant=variant,
    )

    logger.info("ab_test_assigned", extra={
        "user_id": str(user_id),
        "variant": variant,
    })

    return variant


async def get_ab_test_metrics():
    """
    Calculate A/B test metrics.

    Metrics:
    - Success rate: % of invocations that succeed
    - Latency: p50, p95, p99
    - Tool accuracy: % of tool calls that return success=true
    - User satisfaction: (requires explicit user feedback)
    """

    query = """
    SELECT
        u.variant,
        COUNT(*) as total_invocations,
        AVG(CASE WHEN ai.success THEN 1 ELSE 0 END) as success_rate,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ai.latency_ms) as p50_latency,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ai.latency_ms) as p95_latency,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ai.latency_ms) as p99_latency
    FROM agent_invocations ai
    JOIN ab_test_assignments u ON ai.user_id = u.user_id
    WHERE ai.created_at > NOW() - INTERVAL '7 days'
    GROUP BY u.variant
    """

    results = await db.fetchall(query)

    return {
        row['variant']: {
            'total_invocations': row['total_invocations'],
            'success_rate': float(row['success_rate']),
            'p50_latency': float(row['p50_latency']),
            'p95_latency': float(row['p95_latency']),
            'p99_latency': float(row['p99_latency']),
        }
        for row in results
    }
```

---

### 5. Analytics Dashboard

**File**: `app/web/pages/admin/ab-testing.tsx`

```typescript
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export default function ABTestingDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['ab-test-metrics'],
    queryFn: async () => {
      const response = await api.get('/admin/ab-test-metrics');
      return response.data;
    },
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) return <div>Loading metrics...</div>;

  const singleAgent = data.single_agent;
  const multiAgent = data.multi_agent;

  return (
    <div className="ab-testing-dashboard">
      <h1>A/B Test: Single Agent vs Multi-Agent</h1>

      <div className="metrics-grid">
        <MetricCard
          title="Success Rate"
          singleAgent={`${(singleAgent.success_rate * 100).toFixed(1)}%`}
          multiAgent={`${(multiAgent.success_rate * 100).toFixed(1)}%`}
          winner={singleAgent.success_rate > multiAgent.success_rate ? 'single' : 'multi'}
        />

        <MetricCard
          title="P95 Latency"
          singleAgent={`${singleAgent.p95_latency.toFixed(0)}ms`}
          multiAgent={`${multiAgent.p95_latency.toFixed(0)}ms`}
          winner={singleAgent.p95_latency < multiAgent.p95_latency ? 'single' : 'multi'}
        />

        <MetricCard
          title="Total Invocations"
          singleAgent={singleAgent.total_invocations}
          multiAgent={multiAgent.total_invocations}
        />
      </div>

      <div className="agent-breakdown">
        <h2>Multi-Agent Routing Breakdown</h2>
        <RoutingChart data={data.routing_breakdown} />
      </div>
    </div>
  );
}

function MetricCard({ title, singleAgent, multiAgent, winner }) {
  return (
    <div className="metric-card">
      <h3>{title}</h3>
      <div className={winner === 'single' ? 'winner' : ''}>
        Single Agent: {singleAgent}
      </div>
      <div className={winner === 'multi' ? 'winner' : ''}>
        Multi-Agent: {multiAgent}
      </div>
    </div>
  );
}
```

---

## Acceptance Criteria

### Router Agent

- [ ] Classifies "Remind me tomorrow" → `AgentType.REMINDER` with confidence >0.9
- [ ] Classifies "Add a note about..." → `AgentType.NOTE` with confidence >0.9
- [ ] Classifies "What does the PDF say..." → `AgentType.KB_SEARCH` with confidence >0.9
- [ ] Ambiguous queries → routed to `AgentType.GENERAL`
- [ ] Routing latency: <500ms (p95)

### Specialist Agents

- [ ] Reminder agent successfully creates reminders from natural language
- [ ] Note agent creates notes and searches correctly
- [ ] KB agent returns answers with structured citations
- [ ] Calendar agent creates events with RRULE
- [ ] Specialist agents have access to appropriate tools only (security isolation)

### A/B Testing

- [ ] Users randomly assigned 50/50 to single vs multi-agent
- [ ] Metrics tracked: success rate, latency, tool accuracy
- [ ] Dashboard shows real-time comparison
- [ ] Statistical significance calculated (need 100+ invocations per variant)

### Performance

- [ ] Multi-agent latency: <2s for simple queries (p95)
- [ ] Single agent latency: <1s for simple queries (p95)
- [ ] Multi-agent success rate: ≥ single agent success rate (if lower, multi-agent is worse!)

---

## Testing Strategy

### Manual Testing

**Test 1: Router Accuracy**

```bash
# Send 100 test messages, verify routing correctness

TEST_MESSAGES = [
    ("Remind me to call John tomorrow", "reminder"),
    ("Add a note about project X", "note"),
    ("What does the contract say about fees?", "kb_search"),
    ("Create event Monday at 2pm", "calendar"),
    ("Hello", "general"),
    # ... 95 more
]

for message, expected_agent in TEST_MESSAGES:
    routing = await route_message(message, user_id)
    assert routing.agent == expected_agent, f"Failed: {message}"
```

**Test 2: End-to-End Multi-Agent**

1. User: "Remind me to buy milk tomorrow at 5pm"
2. Verify:
   - Router classifies as `reminder`
   - Reminder agent called
   - `create_reminder` tool executed
   - Reminder created in database
   - User receives confirmation

**Test 3: A/B Test Assignment**

1. Create 10 new users
2. Verify: ~5 assigned to single_agent, ~5 to multi_agent
3. Check: Each user consistently gets same variant

---

## Performance Benchmarks

Run for 1 week with 100+ users:

| Metric | Single Agent (Goal) | Multi-Agent (Goal) | Winner |
|--------|--------------------|--------------------|--------|
| Success rate | >90% | >90% | Tie |
| P95 latency | <1000ms | <2000ms | Single (expected) |
| Tool accuracy | >95% | >95% | Tie |
| Cost (tokens) | 1x | 2x | Single |

**Decision rule**:
- If multi-agent success rate ≤ single agent: **Don't deploy multi-agent**
- If multi-agent success rate significantly better (>10% improvement): **Deploy multi-agent**
- If marginal (<5% improvement): **Probably not worth complexity**

---

## Rollout Plan

### Phase 1: Shadow Mode (Week 1)

- Deploy multi-agent architecture
- ALL users use single agent (default)
- Multi-agent runs in background, logs metrics
- Compare offline: would multi-agent have done better?

### Phase 2: Limited A/B Test (Week 2-3)

- Assign 10% of users to multi-agent
- Monitor closely: error rate, latency, user feedback
- Roll back immediately if error rate >5%

### Phase 3: Full A/B Test (Week 4-6)

- Assign 50% of users to multi-agent
- Collect statistical significance (need 100+ invocations per variant)
- Analyze metrics, make decision

### Phase 4: Winner Rollout (Week 7+)

- Deploy winning variant to 100% of users
- Deprecate losing variant
- Document learnings

---

## Risk Checklist

- [ ] **Routing errors**: Router misclassifies intent → wrong specialist → tool failure
- [ ] **Latency**: Extra LLM call adds 1-2s → user perceives slowness
- [ ] **Cost**: 2x token usage → higher monthly OpenAI/Anthropic bill
- [ ] **Complexity**: 5 prompts to maintain vs 1 → harder to debug
- [ ] **Failure modes**: More points of failure (router, routing decision, specialist)

---

## When to Roll Back

Roll back to single agent if:

- [ ] Multi-agent success rate <90% (worse than single agent)
- [ ] P95 latency >3s (too slow)
- [ ] >10 user complaints about "confused responses"
- [ ] Cost increase >50% without corresponding quality improvement

---

## Alternative: Prompt Routing (Simpler)

If multi-agent too complex, try **prompt routing** instead:

```python
# Simpler: Use same LLM, different prompts based on keyword matching

if any(word in message.lower() for word in ["remind", "reminder", "remember"]):
    system_prompt = REMINDER_FOCUSED_PROMPT
elif any(word in message.lower() for word in ["note", "write down", "save"]):
    system_prompt = NOTE_FOCUSED_PROMPT
else:
    system_prompt = UNIFIED_PROMPT

response = await llm.chat(messages=[...], system=system_prompt)
```

**Benefits**:
- No extra LLM call (no latency cost)
- Simpler implementation
- Still gets specialization benefits

**Tradeoffs**:
- Less sophisticated than LLM-based routing
- Keyword matching can be brittle

---

## Success Metrics

After 6 weeks of A/B testing:

- **Clear winner**: One variant has >10% better success rate
- **User satisfaction**: Explicit feedback collected (thumbs up/down)
- **Cost analysis**: ROI calculated (improvement vs cost increase)
- **Decision made**: Deploy winner, deprecate loser, document learnings

---

## Conclusion

**Multi-agent architecture is an optimization, not a necessity.**

Most VIB users will be perfectly satisfied with the MVP's single unified agent. Only implement Stage 10 if you have DATA showing the single agent is failing for specific task types.

Remember: **Complexity is a tax.** Make sure the benefits justify the cost.

---

## Remember

**Do NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

Good luck! 🚀
