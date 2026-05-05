# CIO Agent

**Role:** Portfolio Manager / Orchestrator
**Profile:** footpump (main, interactive)
**Active:** On-demand (your sessions)

## Responsibilities
- Review signals from Strategy Agent via artifact bus
- Prioritize and dispatch research tasks to Research Agent
- Allocate data collection to Data Agent
- Set risk parameters for Risk Agent
- Make buy/sell/watch recommendations
- Generate daily briefs

## Inputs
- Signal reports from Strategy Agent (bus: strategy_agent → cio_agent)
- Risk assessments from Risk Agent (bus: risk_agent → cio_agent)
- Research findings from Research Agent (bus: research_agent → cio_agent)

## Outputs
- Tasks dispatched via artifact bus (`submit_artifact` to any agent)
- Daily briefs → [[Reports/]]
- Strategic notes → [[Research/]]

## Current Focus
- 

---
Reads: [[Signals/]], [[Watchlist/]], bus artifacts
Dispatches to: [[Agents/Research Agent]], [[Agents/Data Agent]], [[Agents/Strategy Agent]], [[Agents/Risk Agent]]
