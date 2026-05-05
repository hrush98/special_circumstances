# Risk Agent

**Role:** Risk management & position guarding
**Profile:** footpump-risk (cron)
**Schedule:** Every 5 minutes
**Active:** Continuous monitoring

## Responsibilities
- Monitor portfolio exposure and concentration
- Set position size limits based on volatility
- Detect anomalous risk patterns (liquidity drops, whale exits)
- Validate signal recommendations against risk parameters
- Halt/recommend against signals that exceed risk thresholds
- Push risk assessments to CIO Agent via bus

## Inputs
- Signal reports from Strategy Agent (bus: strategy_agent → risk_agent)
- Portfolio state from CIO Agent
- On-chain liquidity data

## Outputs
- Risk assessments → CIO Agent via bus (risk_agent → cio_agent)
- Exposure reports → [[Risk/]]
- Halt signals (when risk thresholds breached)

## Current Status
- Active limits: 
- Current exposure: 
- Signals blocked today: 

---
Template: [[Templates/Signal Report]]
Never overrides a hard risk limit. Escalate, don't bypass.
