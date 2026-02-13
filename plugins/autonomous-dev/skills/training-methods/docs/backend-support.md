# Backend Support Details

Detailed backend comparison for all 8 training methods across MLX, PyTorch, and Cloud platforms.

---

## Backend Overview

| Backend | Hardware | Best For | Limitations |
|---------|----------|----------|-------------|
| **MLX** | Apple Silicon (M1/M2/M3) | Mac users, efficient training | Limited ecosystem |
| **PyTorch** | NVIDIA GPUs | Maximum flexibility, research | Higher memory usage |
| **Cloud** | Managed (OpenAI, Anthropic) | Easy setup, no hardware | Cost, API limits |

---

## MLX (Apple Silicon)

### Supported Methods

| Method | Support Level | Implementation | Notes |
|--------|---------------|----------------|-------|
| **LoRA** | ✅ Full | MLX-LM | Efficient 4-bit training |
| **DPO** | ✅ Full | MLX-LM | Reference model support |
| **ORPO** | ⚠️ Experimental | Custom | Unstable, needs testing |
| **GRPO** | ✅ Full | MLX-LM | Group advantage calculation |
| **CPO** | ❌ Not available | - | No implementation |
| **RLVR** | ✅ Full | MLX-LM | Step verification support |
| **Abliteration** | ❌ Not available | - | Requires PyTorch |
| **Activation Steering** | ❌ Not available | - | Requires PyTorch |

### MLX Strengths

- **Unified memory**: CPU and GPU share memory (no transfers)
- **4-bit quantization**: Train 7B models on 16GB RAM
- **Power efficiency**: Lower power than NVIDIA GPUs
- **Native Apple**: Optimized for M1/M2/M3 chips

### MLX Limitations

- **Ecosystem**: Fewer libraries than PyTorch
- **Compatibility**: Apple Silicon only (no NVIDIA)
- **Tool support**: Limited third-party integrations
- **Community**: Smaller than PyTorch

### MLX Setup

```bash
# Install MLX-LM
pip install mlx-lm

# Train LoRA
mlx_lm.lora \
    --model meta-llama/Llama-3.2-1B-Instruct \
    --data data/sft.jsonl \
    --train

# Train DPO
mlx_lm.dpo \
    --model meta-llama/Llama-3.2-1B-Instruct \
    --data data/dpo.jsonl \
    --train
```

---

## PyTorch (NVIDIA GPUs)

### Supported Methods

| Method | Support Level | Implementation | Notes |
|--------|---------------|----------------|-------|
| **LoRA** | ✅ Full | HuggingFace PEFT | Gold standard |
| **DPO** | ✅ Full | HuggingFace TRL | Production-ready |
| **ORPO** | ✅ Full | HuggingFace TRL | Stable implementation |
| **GRPO** | ✅ Full | HuggingFace TRL | DeepSeek-R1 hyperparameters |
| **CPO** | ✅ Full | HuggingFace TRL | Conservative preference |
| **RLVR** | ❌ Not available | - | Use MLX or custom |
| **Abliteration** | ✅ Full | Custom | Refusal removal |
| **Activation Steering** | ✅ Full | Custom | Vector-based control |

### PyTorch Strengths

- **Ecosystem**: Largest library support (HuggingFace, DeepSpeed)
- **Flexibility**: Full control over training loop
- **Community**: Largest user base, most resources
- **Performance**: Optimized CUDA kernels

### PyTorch Limitations

- **Memory**: Higher usage than MLX (separate CPU/GPU)
- **Setup**: More complex installation (CUDA, cuDNN)
- **Cost**: NVIDIA GPUs expensive
- **Power**: Higher power consumption

### PyTorch Setup

```bash
# Install dependencies
pip install torch transformers peft trl

# Train LoRA
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, TrainingArguments

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-1B-Instruct")
lora_config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"])
model = get_peft_model(model, lora_config)

# Train DPO
from trl import DPOTrainer, DPOConfig

dpo_config = DPOConfig(beta=0.1, learning_rate=1e-5)
trainer = DPOTrainer(model, ref_model, dpo_config, train_dataset)
trainer.train()
```

---

## Cloud (OpenAI, Anthropic)

### Supported Methods

| Method | Support Level | Implementation | Notes |
|--------|---------------|----------------|-------|
| **LoRA** | ✅ Full | OpenAI fine-tuning API | SFT only |
| **DPO** | ✅ Full | OpenAI RLHF API | Preference-based |
| **ORPO** | ✅ Full | Custom via API | Simulated reference |
| **GRPO** | ✅ Full | Custom via API | Multi-response generation |
| **CPO** | ✅ Full | Custom via API | Conservative tuning |
| **RLVR** | ❌ Not available | - | Requires local control |
| **Abliteration** | ❌ Not available | - | No direct access |
| **Activation Steering** | ❌ Not available | - | Inference-only |

### Cloud Strengths

- **No hardware**: No GPU needed
- **Easy setup**: API-based, quick start
- **Managed**: Updates, scaling handled
- **Compliance**: SOC 2, HIPAA (enterprise)

### Cloud Limitations

- **Cost**: Per-token pricing ($0.001-0.01/1K tokens)
- **API limits**: Rate limits, token limits
- **Control**: Limited hyperparameter access
- **Data privacy**: External processing

### Cloud Setup

```python
# OpenAI fine-tuning API
import openai

# Upload training file
file = openai.File.create(
    file=open("data/sft.jsonl"),
    purpose="fine-tune"
)

# Create fine-tuning job
job = openai.FineTuningJob.create(
    training_file=file.id,
    model="gpt-3.5-turbo"
)

# Monitor job
status = openai.FineTuningJob.retrieve(job.id)
```

---

## Backend Comparison Matrix

### Performance (1B Model, 1000 Examples)

| Backend | LoRA Time | DPO Time | Memory | Cost |
|---------|-----------|----------|--------|------|
| **MLX (M2 Ultra)** | 30 min | 2 hours | 8 GB | Free (hardware owned) |
| **PyTorch (RTX 3090)** | 20 min | 1.5 hours | 12 GB | $0.50/hour (cloud GPU) |
| **Cloud (OpenAI)** | 1-2 hours | 3-4 hours | N/A | $10-50 (API costs) |

### Feature Support

| Feature | MLX | PyTorch | Cloud |
|---------|-----|---------|-------|
| **Custom training loop** | ✅ Yes | ✅ Yes | ❌ No |
| **4-bit quantization** | ✅ Yes | ✅ Yes | ❌ No |
| **Distributed training** | ❌ No | ✅ Yes | ✅ Yes |
| **Custom architectures** | ✅ Yes | ✅ Yes | ❌ No |
| **Data privacy** | ✅ Local | ✅ Local | ⚠️ External |
| **Gradient accumulation** | ✅ Yes | ✅ Yes | ⚠️ Limited |

---

## Choosing a Backend

### Decision Tree

```
Do you have Apple Silicon (M1/M2/M3)?
├─ YES: Use MLX
│   └─ Exceptions: Need Abliteration/Steering → Use PyTorch
│
└─ NO: Have NVIDIA GPU?
    ├─ YES: Use PyTorch (most flexible)
    │
    └─ NO: Budget/privacy concerns?
        ├─ Budget OK + Privacy OK → Use Cloud
        └─ Budget/Privacy critical → Rent GPU (RunPod, Vast.ai)
```

### Use Case Recommendations

| Use Case | Recommended Backend | Reason |
|----------|---------------------|--------|
| **Mac user** | MLX | Native, efficient |
| **Research** | PyTorch | Maximum flexibility |
| **Quick experiment** | Cloud | No setup needed |
| **Production training** | PyTorch + DeepSpeed | Best performance |
| **Budget-constrained** | MLX (if Mac) or Rent GPU | Lower cost |
| **Privacy-critical** | MLX or PyTorch (local) | Data stays local |

---

## Migration Guide

### MLX → PyTorch

```python
# MLX code
import mlx.core as mx
from mlx_lm import load, generate

model, tokenizer = load("meta-llama/Llama-3.2-1B-Instruct")
response = generate(model, tokenizer, prompt)

# PyTorch equivalent
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-1B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.2-1B-Instruct")
inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs)
response = tokenizer.decode(outputs[0])
```

### PyTorch → Cloud

```python
# PyTorch training
trainer = Trainer(model, train_dataset, training_args)
trainer.train()

# Cloud equivalent (OpenAI API)
import openai

file = openai.File.create(file=open("train.jsonl"), purpose="fine-tune")
job = openai.FineTuningJob.create(training_file=file.id, model="gpt-3.5-turbo")
```

---

## Ecosystem Tools

### MLX Ecosystem

| Tool | Purpose | URL |
|------|---------|-----|
| **MLX-LM** | LoRA, DPO, GRPO, RLVR | github.com/ml-explore/mlx-examples |
| **MLX-VLM** | Vision-language models | github.com/Blaizzy/mlx-vlm |
| **MLXLLM** | LLM inference | github.com/riccardomusmeci/mlx-llm |

### PyTorch Ecosystem

| Tool | Purpose | URL |
|------|---------|-----|
| **HuggingFace Transformers** | Pre-trained models | huggingface.co/transformers |
| **HuggingFace PEFT** | LoRA, prefix tuning | github.com/huggingface/peft |
| **HuggingFace TRL** | DPO, GRPO, PPO | github.com/huggingface/trl |
| **Axolotl** | Training framework | github.com/OpenAccess-AI-Collective/axolotl |
| **Unsloth** | Efficient training | github.com/unslothai/unsloth |
| **DeepSpeed** | Distributed training | github.com/microsoft/DeepSpeed |

### Cloud Platforms

| Platform | Strengths | Pricing |
|----------|-----------|---------|
| **OpenAI** | Easy API, gpt-3.5/4 | $0.008/1K tokens training |
| **Anthropic** | Claude 3 fine-tuning | Custom pricing |
| **Cohere** | Embed + chat models | $1/1K examples |
| **Together AI** | Open-source models | $0.0008/1K tokens |

---

## Hardware Requirements

### Minimum Requirements

| Backend | CPU | RAM | GPU/Accelerator | Storage |
|---------|-----|-----|-----------------|---------|
| **MLX** | Apple Silicon | 16 GB | M1/M2/M3 | 50 GB |
| **PyTorch** | x86_64 | 32 GB | NVIDIA 3060+ (12GB VRAM) | 100 GB |
| **Cloud** | Any | Any | N/A | Minimal |

### Recommended Requirements

| Backend | CPU | RAM | GPU/Accelerator | Storage |
|---------|-----|-----|-----------------|---------|
| **MLX** | M2 Pro/Max/Ultra | 32+ GB | M2 Pro+ | 100 GB |
| **PyTorch** | x86_64 | 64+ GB | NVIDIA 3090/4090 (24GB VRAM) | 500 GB |
| **Cloud** | Any | Any | N/A | Minimal |

---

## Cost Analysis

### Training Cost (1B Model, 1000 Examples, 3 Epochs)

| Backend | Hardware Cost | Training Time | Energy Cost | Total Cost |
|---------|---------------|---------------|-------------|------------|
| **MLX (M2 Ultra)** | $0 (owned) | 2 hours | $0.10 (30W) | $0.10 |
| **PyTorch (RTX 3090)** | $0.50/hour (cloud) | 1.5 hours | $0.50 (350W) | $1.75 |
| **Cloud (OpenAI)** | N/A | 2 hours (queue) | $0 | $20-50 |

### Long-Term Cost (100 Training Runs)

| Backend | Total Cost | Notes |
|---------|------------|-------|
| **MLX** | $10 (energy) | Hardware owned, minimal ongoing cost |
| **PyTorch (cloud)** | $175 | Rent GPU on-demand |
| **PyTorch (owned)** | $50 (energy) | $1500 GPU upfront, then energy only |
| **Cloud** | $2000-5000 | Per-token pricing, scales linearly |

**Recommendation**: MLX (if Mac) or owned PyTorch GPU for frequent training. Cloud for occasional experiments.

---

**See**: Main skill file for method selection guide and cross-references.
