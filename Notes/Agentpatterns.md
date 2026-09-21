# Agentic Harness Patterns

## 1. ReAct Agent Loop

Use case: Dynamic reasoning and tool calling.

Description: Agent reasons, selects tools, observes results, and repeats.

When to use: Tasks requiring dynamic decisions.

When not to use: Fully predictable workflows with fixed steps.

⸻

## 2. Plan-and-Execute

Use case: Multi-step task execution.

Description: Planner creates a task plan, and executor performs each step.

When to use: Complex workflows requiring structured planning.

When not to use: Simple tasks with 1–2 tool calls.

⸻

## 3. Router Pattern

Use case: Request classification and agent selection.

Description: Routes requests to specialized agents or workflows.

When to use: Multiple domains or specialized capabilities.

When not to use: Single-domain applications with minimal routing logic.

⸻

## 4. Supervisor–Worker

Use case: Multi-agent collaboration.

Description: Supervisor delegates tasks to specialized worker agents and combines results.

When to use: Parallel investigations or domain-specific processing.

When not to use: Simple tasks where a single agent is sufficient.

⸻

## 5. Reflection / Critic

Use case: Output review and improvement.

Description: A critic evaluates the agent’s output and requests revisions.

When to use: Code generation, report creation, and quality-sensitive tasks.

When not to use: Real-time, latency-sensitive tasks where additional review adds little value.

⸻

## 6. Tool-Gated Execution

Use case: Secure tool execution.

Description: Validates permissions, parameters, and risk before executing tools.

When to use: Production systems, sensitive data, and external actions.

When not to use: Never omit basic validation in production; use lighter controls for low-risk internal tools.

⸻

## 7. Human-in-the-Loop

Use case: Human approval for agent actions.

Description: Pauses execution until a human approves or rejects a proposed action.

When to use: Financial transactions, production changes, and high-impact decisions.

When not to use: High-volume, low-risk tasks where human approval creates unnecessary bottlenecks.

⸻

## 8. Stateful / Durable Execution

Use case: Workflow recovery and persistence.

Description: Saves execution state and resumes workflows after interruptions.

When to use: Long-running tasks, background jobs, and distributed workflows.

When not to use: Short-lived, stateless requests where recovery provides little benefit.

⸻

## 9. State Machine Workflow

Use case: Controlled workflow transitions.

Description: Defines explicit states, transitions, and conditions for agent execution.

When to use: Predictable business processes and enterprise workflows.

When not to use: Highly exploratory tasks where rigid states limit useful flexibility.

⸻

## 10. Retry & Backoff

Use case: Handling transient failures.

Description: Retries failed operations using controlled delays and retry limits.

When to use: Temporary network failures, rate limits, and service unavailability.

When not to use: Non-retryable errors, invalid requests, or non-idempotent operations without safeguards.

⸻

## 11. Context Management

Use case: Managing LLM context and token usage.

Description: Selects, compresses, and prioritizes relevant information for the agent.

When to use: Long conversations, large documents, and multi-step investigations.

When not to use: Very small prompts where context optimization adds unnecessary complexity.

⸻

## 12. Memory Pattern

Use case: Retaining information across interactions.

Description: Stores and retrieves relevant short-term or long-term information.

When to use: Personalized assistants and recurring workflows.

When not to use: Tasks requiring strict isolation or where retaining information creates privacy risks.

⸻

## 13. Guardrails

Use case: Input, output, and action safety.

Description: Enforces rules for content, data validation, and permitted behavior.

When to use: Production AI applications and sensitive domains.

When not to use: Never completely omit essential safety controls; avoid unnecessarily restrictive rules for low-risk tasks.

⸻

## 14. Checkpointing

Use case: Saving intermediate progress.

Description: Persists workflow state at defined execution points.

When to use: Long-running workflows and failure recovery.

When not to use: Simple, short-lived operations where restarting is inexpensive.

⸻

## 15. Evaluator–Optimizer

Use case: Iterative output improvement.

Description: An evaluator assesses results against defined criteria, and an optimizer improves them.

When to use: Quality-sensitive generation and structured outputs.

When not to use: When evaluation is unreliable or improvement costs exceed the expected benefit.

⸻

## 16. Parallel Agent Execution

Use case: Concurrent task processing.

Description: Runs independent agent tasks simultaneously and aggregates results.

When to use: Independent investigations, data retrieval, and parallel analysis.

When not to use: Tasks with strict sequential dependencies or limited downstream capacity.

⸻

## 17. Human Escalation

Use case: Handling uncertainty or failure.

Description: Transfers tasks to a human when confidence, policy, or execution limits are not met.

When to use: Ambiguous requests, repeated failures, and high-risk scenarios.

When not to use: Routine tasks with reliable automated handling.

⸻

## 18. Cost & Budget Control

Use case: Managing AI spending.

Description: Limits tokens, model calls, tool invocations, and execution time.

When to use: Production applications with usage or cost constraints.

When not to use: Never ignore cost monitoring in production; apply proportional controls for prototypes.
