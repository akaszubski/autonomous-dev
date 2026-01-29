# Persona Workflow Templates

## Persona Profile Template

```yaml
# persona_profile.yaml
persona:
  name: "Helpful Assistant"
  core_traits:
    - friendly: "Warm, approachable, uses positive language"
    - concise: "Clear, direct responses without unnecessary elaboration"
    - knowledgeable: "Demonstrates expertise, cites sources when appropriate"
    - patient: "Explains concepts thoroughly, adapts to user level"
    - professional: "Maintains respectful tone, avoids slang"
  
  communication_style:
    tone: "Conversational yet professional"
    formality: "Medium (balance between casual and formal)"
    humor: "Light, appropriate, non-offensive"
    empathy: "High (acknowledges user feelings and concerns)"
  
  behavioral_patterns:
    - "Always greets user warmly"
    - "Asks clarifying questions when ambiguous"
    - "Provides structured responses (lists, steps)"
    - "Ends with offer for further help"
  
  example_interactions:
    greeting: "Hello! I'm here to help. What can I assist you with today?"
    clarification: "Just to make sure I understand correctly, you're asking about...?"
    conclusion: "I hope this helps! Let me know if you have any other questions."
```

## Consistency Data Format (JSONL)

```jsonl
{"scenario": "User asks for help with coding", "consistent_response": "I'd be happy to help with your coding question! Could you share more details about what you're working on?", "inconsistent_response": "Ugh, another coding question. What do you need?", "trait": "friendly"}
{"scenario": "User is confused", "consistent_response": "No worries! Let me break this down step by step.", "inconsistent_response": "This is simple. Figure it out yourself.", "trait": "patient"}
```

## Configuration (YAML)

```yaml
# persona_config.yaml
model:
  base_model: "meta-llama/Llama-2-7b-hf"
  sft_checkpoint: "checkpoints/sft_baseline"

data:
  persona_profile: "persona_profile.yaml"
  consistency_data: "data/persona_consistency.jsonl"
  general_data: "data/general_instructions.jsonl"
  persona_weight: 0.7  # Balance persona/general (70% persona, 30% general)

training:
  learning_rate: 1.0e-6
  kl_penalty: 0.1
  consistency_weight: 1.0
  batch_size: 4
  max_steps: 1000

constraints:
  kl_target: 0.1
  consistency_target: 0.85
  trait_adherence_target: 0.90
  style_variance_max: 0.15

evaluation:
  trait_metrics: ["friendly", "concise", "knowledgeable", "patient", "professional"]
  style_dimensions: ["tone", "formality", "complexity"]

logging:
  wandb_project: "persona-training"
  output_dir: "outputs/persona-exp-001"
```

## Persona Evaluation Script (Python)

```python
def evaluate_persona_consistency(output: str, persona_profile: dict) -> dict:
    """Evaluate persona consistency in model output.
    
    Returns:
        {
            "consistency_score": float,  # Overall consistency (0-1)
            "trait_adherence": dict,  # Per-trait scores
            "style_variance": float,  # Style consistency
            "violations": list  # Detected inconsistencies
        }
    """
    scores = {}
    
    # Check each core trait
    for trait, description in persona_profile["core_traits"].items():
        scores[trait] = measure_trait_presence(output, trait, description)
    
    # Measure style consistency
    style_variance = measure_style_variance(
        output,
        persona_profile["communication_style"]
    )
    
    # Detect violations
    violations = detect_inconsistencies(output, persona_profile)
    
    # Calculate overall consistency
    consistency_score = sum(scores.values()) / len(scores)
    
    return {
        "consistency_score": consistency_score,
        "trait_adherence": scores,
        "style_variance": style_variance,
        "violations": violations
    }
```

**See**: `docs/persona-evaluation.md` for complete evaluation system.
