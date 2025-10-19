---
name: mlx-patterns
type: knowledge
description: MLX framework patterns and best practices. Use when working with MLX code, training, or Apple Silicon optimization.
keywords: mlx, apple silicon, gpu, metal, training, model, layers, memory
---

# MLX Patterns Skill

Critical patterns for working with MLX (Apple's ML framework).

## When This Activates
- MLX-related code
- Apple Silicon optimization
- Model training/inference
- GPU memory management
- Keywords: "mlx", "metal", "gpu", "model", "training", "layers"

## Critical Pattern #1: Nested Layer Access

### THE PROBLEM
MLX models have a nested structure that causes AttributeError if accessed incorrectly.

### THE SOLUTION
```python
# ✅ CORRECT: model.model.layers[i]
layer_output = model.model.layers[layer_idx](hidden_states)

# ❌ WRONG: model.layers[i] - AttributeError!
layer_output = model.layers[layer_idx](hidden_states)
```

### WHY
MLX-LM models wrap the base model in an additional layer:
```
model (ModelContainer)
└── model (ActualModel)
    └── layers (List[Layer])
```

### CODE EXAMPLES
```python
import mlx.core as mx
from mlx_lm import load


# Loading and accessing layers
model, tokenizer = load("mlx-community/Llama-3.2-1B-Instruct-4bit")

# ✅ Correct layer access
for i, layer in enumerate(model.model.layers):
    print(f"Layer {i}: {layer}")

# ✅ Modifying specific layer
def modify_layer(model, layer_idx: int):
    original_layer = model.model.layers[layer_idx]
    # Modify layer...
    model.model.layers[layer_idx] = modified_layer
    return model

# ✅ Getting layer count
num_layers = len(model.model.layers)
```

## Critical Pattern #2: Lazy Evaluation

### THE PROBLEM
MLX uses lazy evaluation - operations aren't computed until explicitly evaluated.

### THE SOLUTION
```python
import mlx.core as mx

# ✅ CORRECT: Force evaluation with mx.eval()
result = model(input_ids)
mx.eval(result)  # Computation happens HERE

# ❌ WRONG: Assuming immediate computation
result = model(input_ids)
# result is not yet computed!
```

### WHEN TO USE mx.eval()
```python
# 1. After forward pass
output = model(input_ids)
mx.eval(output)

# 2. After computing gradients
loss = compute_loss(output, labels)
grads = mx.grad(loss)
mx.eval(grads)

# 3. Before accessing values
logits = model(input_ids)
mx.eval(logits)
prediction = mx.argmax(logits, axis=-1)
mx.eval(prediction)

# 4. After parameter updates
optimizer.update(model, grads)
mx.eval(model.parameters())
```

## Critical Pattern #3: GPU Memory Management

### THE PROBLEM
MLX Metal (GPU) cache can grow unbounded causing OOM errors.

### THE SOLUTION
```python
import mlx.core as mx

# ✅ CORRECT: Clear cache after large operations
def train_step(model, data):
    try:
        output = model(data["input_ids"])
        loss = compute_loss(output, data["labels"])
        mx.eval(loss)
        return loss
    finally:
        mx.metal.clear_cache()  # Always clean up


# ✅ CORRECT: Clear in context manager
from contextlib import contextmanager

@contextmanager
def mlx_context():
    """Context manager for MLX operations."""
    try:
        yield
    finally:
        mx.metal.clear_cache()

# Usage
with mlx_context():
    result = model(input_ids)
    mx.eval(result)
# Cache automatically cleared
```

### WHEN TO CLEAR CACHE
```python
# 1. After each training step
for batch in dataloader:
    loss = train_step(model, batch)
    mx.metal.clear_cache()  # Clear after each batch

# 2. After large model operations
model = load_large_model()
output = model(large_input)
mx.eval(output)
mx.metal.clear_cache()  # Free GPU memory

# 3. In test teardown
def test_model_inference():
    result = model(input_ids)
    assert result is not None
    mx.metal.clear_cache()  # Clean up after test
```

## Pattern #4: Array Operations

### Creating Arrays
```python
import mlx.core as mx

# Zeros
hidden_states = mx.zeros((batch_size, seq_len, hidden_dim))

# Ones
attention_mask = mx.ones((batch_size, seq_len))

# From Python list
data = mx.array([1, 2, 3, 4, 5])

# Random
weights = mx.random.normal((input_dim, output_dim))
```

### Array Manipulation
```python
# Reshaping
x = mx.array([[1, 2], [3, 4]])
x_flat = mx.reshape(x, (-1,))  # [1, 2, 3, 4]

# Concatenation
x1 = mx.array([1, 2])
x2 = mx.array([3, 4])
combined = mx.concatenate([x1, x2])  # [1, 2, 3, 4]

# Slicing
x = mx.array([1, 2, 3, 4, 5])
first_three = x[:3]  # [1, 2, 3]
mx.eval(first_three)
```

## Pattern #5: Model Loading & Saving

### Loading Models
```python
from mlx_lm import load


# From HuggingFace (MLX-quantized)
model, tokenizer = load("mlx-community/Llama-3.2-1B-Instruct-4bit")

# With custom cache directory
cache_dir = Path.home() / ".cache" / "realign" / "models"
model, tokenizer = load(
    "mlx-community/model-name",
    cache_dir=str(cache_dir)
)
```

### Saving Models
```python
import mlx.core as mx

# Save model weights
weights = model.parameters()
mx.save_safetensors("model_weights.safetensors", dict(weights))

# Save full model (architecture + weights)
model.save_weights("checkpoint.npz")

# Load weights back
model.load_weights("checkpoint.npz")
mx.eval(model.parameters())
```

## Pattern #6: Training Loop

```python
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim


def training_loop(
    model: nn.Module,
    train_data: list,
    num_epochs: int = 3,
    learning_rate: float = 1e-4
):
    """Standard MLX training loop with proper patterns.

    Args:
        model: MLX model
        train_data: Training dataset
        num_epochs: Number of training epochs
        learning_rate: Learning rate

    Returns:
        Trained model
    """
    # Setup optimizer
    optimizer = optim.Adam(learning_rate=learning_rate)

    # Loss and gradient function
    def loss_fn(model, batch):
        output = model(batch["input_ids"])
        loss = nn.losses.cross_entropy(
            output.reshape(-1, output.shape[-1]),
            batch["labels"].reshape(-1)
        )
        return loss

    loss_and_grad_fn = nn.value_and_grad(model, loss_fn)

    # Training loop
    for epoch in range(num_epochs):
        total_loss = 0.0

        for batch_idx, batch in enumerate(train_data):
            try:
                # Forward + backward
                loss, grads = loss_and_grad_fn(model, batch)
                mx.eval(loss)
                mx.eval(grads)

                # Update parameters
                optimizer.update(model, grads)
                mx.eval(model.parameters())

                total_loss += float(loss)

                if batch_idx % 10 == 0:
                    print(f"Epoch {epoch}, Batch {batch_idx}, Loss: {loss:.4f}")

            finally:
                # CRITICAL: Clear GPU cache
                mx.metal.clear_cache()

        avg_loss = total_loss / len(train_data)
        print(f"Epoch {epoch} complete. Avg loss: {avg_loss:.4f}")

    return model
```

## Pattern #7: Tokenization

```python
# Tokenize text
text = "Hello, world!"
tokens = tokenizer.encode(text)

# Add batch dimension
input_ids = mx.array([tokens])
mx.eval(input_ids)

# Generate
output = model.generate(input_ids, max_tokens=50)
mx.eval(output)

# Decode
generated_text = tokenizer.decode(output[0].tolist())
```

## Pattern #8: LoRA (Low-Rank Adaptation)

```python
from mlx.nn import LoRALinear


def add_lora_layers(model, rank: int = 8, alpha: float = 16.0):
    """Add LoRA layers to model.

    Args:
        model: Base model
        rank: LoRA rank
        alpha: LoRA alpha scaling

    Returns:
        Model with LoRA layers
    """
    # Freeze base model
    model.freeze()

    # Add LoRA to attention layers
    for layer_idx, layer in enumerate(model.model.layers):  # Nested!
        # Replace linear layers with LoRA
        layer.self_attn.q_proj = LoRALinear(
            layer.self_attn.q_proj,
            rank=rank,
            alpha=alpha
        )
        layer.self_attn.v_proj = LoRALinear(
            layer.self_attn.v_proj,
            rank=rank,
            alpha=alpha
        )

    # Only LoRA parameters are trainable
    trainable_params = [
        p for p in model.parameters()
        if p.requires_grad
    ]

    return model, trainable_params
```

## Common Errors & Solutions

### Error: AttributeError: 'Model' object has no attribute 'layers'
```python
# ❌ WRONG
output = model.layers[0](input)

# ✅ CORRECT
output = model.model.layers[0](input)
```

### Error: MLX arrays not being computed
```python
# ❌ WRONG - No evaluation
result = model(input)
value = float(result)  # Error!

# ✅ CORRECT - Evaluate first
result = model(input)
mx.eval(result)
value = float(result)  # Works
```

### Error: METAL GPU out of memory
```python
# ❌ WRONG - No cache clearing
for batch in large_dataset:
    output = model(batch)
    # Memory keeps growing...

# ✅ CORRECT - Clear cache
for batch in large_dataset:
    try:
        output = model(batch)
        mx.eval(output)
    finally:
        mx.metal.clear_cache()
```

## Testing MLX Code

```python
import mlx.core as mx
import pytest


def test_model_forward_pass():
    """Test model forward pass with cleanup."""
    try:
        # Setup
        model = load_test_model()
        input_ids = mx.array([[1, 2, 3, 4]])

        # Forward pass
        output = model(input_ids)
        mx.eval(output)

        # Assertions
        assert output.shape[0] == 1
        assert output.shape[1] == 4

    finally:
        # Always cleanup
        mx.metal.clear_cache()


@pytest.fixture(autouse=True)
def cleanup_mlx():
    """Auto cleanup after each test."""
    yield
    mx.metal.clear_cache()
```

## Performance Optimization

### Batch Processing
```python
# Process in batches to avoid OOM
def process_in_batches(data, batch_size=32):
    results = []

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]

        try:
            # Process batch
            output = model(batch)
            mx.eval(output)
            results.append(output)
        finally:
            mx.metal.clear_cache()

    return results
```

### Gradient Accumulation
```python
def train_with_accumulation(model, data, accumulation_steps=4):
    optimizer = optim.Adam(learning_rate=1e-4)
    accumulated_grads = None

    for step, batch in enumerate(data):
        # Compute gradients
        loss, grads = loss_and_grad_fn(model, batch)
        mx.eval(loss, grads)

        # Accumulate gradients
        if accumulated_grads is None:
            accumulated_grads = grads
        else:
            accumulated_grads = [
                ag + g for ag, g in zip(accumulated_grads, grads)
            ]

        # Update every N steps
        if (step + 1) % accumulation_steps == 0:
            optimizer.update(model, accumulated_grads)
            mx.eval(model.parameters())
            accumulated_grads = None
            mx.metal.clear_cache()
```

## Key Takeaways

1. **Always use `model.model.layers[i]`** (nested access)
2. **Always call `mx.eval()`** after operations
3. **Always call `mx.metal.clear_cache()`** after large ops
4. **Use context managers** for automatic cleanup
5. **Batch processing** to avoid OOM
6. **Test with cleanup** (pytest fixtures)

## References
- MLX Documentation: https://ml-explore.github.io/mlx/
- MLX Examples: https://github.com/ml-explore/mlx-examples
- ReAlign MLX Guides: docs/guides/mlx-patterns.md
