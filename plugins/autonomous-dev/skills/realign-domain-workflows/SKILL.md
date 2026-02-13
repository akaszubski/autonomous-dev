---
name: realign-domain-workflows
version: 1.0.0
type: knowledge
auto_activate: false
keywords: dpo, rlvr, srf, source, persona, antihallucination, realignment, preference data, reward model, factuality, citation
---

# Realignment Domain Workflows

Domain-specific realignment training workflows. Each section covers a specific training methodology with its unique stages, metrics, and common issues. For shared pipeline structure and performance optimization, see `realign-meta-framework`.

## DPO (Direct Preference Optimization)

### Domain-Specific Stages
1. Preference data generation with chosen/rejected pairs
2. DPO loss optimization with beta parameter tuning
3. Reference model KL divergence monitoring

### Key Metrics
- Win rate against reference model: target > 60%
- KL divergence: keep < 0.5 nats
- Preference accuracy on held-out set: target > 75%

### Common Issues
- Reward hacking: model exploits surface patterns
- Mode collapse: reduced response diversity
- Length bias: model learns to prefer longer responses

## RLVR (Reinforcement Learning with Verifiable Rewards)

### Domain-Specific Stages
1. Verifiable task design with automated verification
2. Reward signal construction from verification outcomes
3. GRPO/PPO training with verifiable reward signals

### Key Metrics
- Verification pass rate: target > 85%
- Task completion accuracy: target > 90%
- Reward signal reliability: correlation > 0.8

### Common Issues
- Reward gaming: model finds shortcuts past verifiers
- Sparse rewards: insufficient training signal
- Verifier coverage gaps: untested edge cases

## SRF (Supervised Reward Fine-tuning)

### Domain-Specific Stages
1. Reward model training on human preference data
2. Reward model validation against held-out preferences
3. SRF optimization using trained reward model

### Key Metrics
- Reward model accuracy: target > 80%
- Reward-output correlation: target > 0.7
- Human preference alignment: target > 75%

### Common Issues
- Reward model miscalibration
- Distribution shift between reward training and policy training
- Over-optimization of reward signal

## Source Attribution

### Domain-Specific Stages
1. Source data preparation with attribution labels
2. Citation training with source verification
3. Attribution accuracy evaluation

### Key Metrics
- Citation accuracy: target > 90%
- Source recall: target > 85%
- Attribution precision: target > 88%

### Common Issues
- Hallucinated citations
- Missing attributions for paraphrased content
- Over-citation reducing readability

## Persona Alignment

### Domain-Specific Stages
1. Persona definition with behavioral specifications
2. Consistency data generation across contexts
3. Persona evaluation with multi-turn consistency checks

### Key Metrics
- Persona consistency score: target > 90%
- Cross-context stability: target > 85%
- Style adherence: target > 88%

### Common Issues
- Persona drift across long conversations
- Inconsistency between persona traits
- Over-rigid persona blocking helpfulness

## Antihallucination Training

### Domain-Specific Stages
1. Factuality data collection with verified claims
2. Hallucination detection training
3. Confidence calibration and abstention training

### Key Metrics
- Factuality score: target > 95%
- Hallucination detection rate: target > 90%
- Appropriate abstention rate: 5-15%

### Common Issues
- Over-conservative abstention
- False positive hallucination detection
- Domain-specific factuality gaps
