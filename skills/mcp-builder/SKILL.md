---
name: mcp-builder
type: knowledge
description: "Guide for creating MCP (Model Context Protocol) servers to integrate external services with Claude. Use when: (1) Integrating external APIs (HuggingFace, [FRAMEWORK] Hub, etc), (2) Creating custom tools for [PROJECT_NAME], (3) Building workflow automation servers"
keywords: mcp, server, api, integration, external service, protocol
auto_activate: true
---

# MCP Server Development Guide

**Purpose**: Create high-quality MCP servers for integrating external services with Claude.

**Auto-activates when**: Keywords like "mcp", "server", "api integration", "external service" appear.

---

## What is MCP?

**Model Context Protocol (MCP)**: Standard protocol for connecting Claude to external data sources and tools.

**Use cases for [PROJECT_NAME]**:
- Integrate HuggingFace API for model discovery
- Connect to [FRAMEWORK] model hub
- Create custom training monitoring tools
- Build data pipeline tools

---

## Four-Phase Development

### Phase 1: Research & Planning (30 min)

**Agent-Centric Design Principles**:
1. **Build workflows, not wrappers**: Combine related operations into single tools
2. **Optimize for context**: Return high-signal data, not raw dumps
3. **Actionable errors**: Error messages guide toward correct usage
4. **Natural subdivisions**: Tools match how humans think about tasks

**Research Steps**:
```markdown
1. Read MCP docs: https://modelcontextprotocol.io/llms-full.txt
2. Study target API documentation thoroughly
3. Map common workflows to tool design
4. Plan error handling and edge cases
```

**Example for HuggingFace Integration**:
```
Workflow: "Find best LoRA model for Llama"

❌ BAD (wrapper-style):
- list_models(filter="lora")  → Returns 1000s of models
- get_model_details(id)       → Call 1000 times
- User does filtering manually

✅ GOOD (workflow-style):
- search_lora_models(
    base_model="llama",
    min_downloads=100,
    sort_by="trending"
  ) → Returns top 10 relevant models with key metrics
```

### Phase 2: Implementation

**Choose SDK**:
- **Python**: FastMCP (recommended for [PROJECT_NAME])
- **TypeScript**: MCP SDK

**Python Example** (FastMCP):
```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("[PROJECT_NAME] [FRAMEWORK] Integration")

class ModelSearchParams(BaseModel):
    """Parameters for searching [FRAMEWORK] models."""
    query: str = Field(description="Search query (e.g., 'llama lora')")
    min_downloads: int = Field(default=100, description="Minimum downloads")
    limit: int = Field(default=10, description="Max results to return")

@mcp.tool()
def search_mlx_models(params: ModelSearchParams) -> dict:
    """Search for [FRAMEWORK]-compatible models on HuggingFace.

    Returns models with key metrics: downloads, likes, tags, size.
    Optimized for finding training-ready models.
    """
    # Implementation here
    results = api.search_models(
        query=params.query,
        filter="library:[framework]",
        min_downloads=params.min_downloads,
        limit=params.limit
    )

    # Return high-signal data only
    return {
        "models": [
            {
                "id": m.id,
                "downloads": m.downloads,
                "likes": m.likes,
                "size_gb": m.size / 1e9,
                "tags": m.tags[:5]  # Top 5 tags only
            }
            for m in results
        ],
        "total_found": len(results),
        "search_query": params.query
    }
```

**Tool Annotations** (Important!):
```python
@mcp.tool(
    readOnlyHint=True,      # Doesn't modify external state
    idempotentHint=True,    # Same input → same output
    openWorldHint=False     # Closed set of inputs
)
def search_mlx_models(...):
    ...
```

### Phase 3: Review & Refine

**Quality Checklist**:
- [ ] DRY: No duplicated code
- [ ] Composability: Shared utilities extracted
- [ ] Error handling: All failure modes covered
- [ ] Type safety: Full Pydantic coverage
- [ ] Documentation: Comprehensive docstrings
- [ ] Testing: Key workflows tested

**Error Handling Example**:
```python
from fastmcp import MCPError

@mcp.tool()
def download_model(model_id: str) -> dict:
    """Download [FRAMEWORK] model from HuggingFace."""
    try:
        result = api.download(model_id)
        return {"status": "success", "path": result.path}

    except AuthenticationError:
        raise MCPError(
            "Authentication failed. Set HF_TOKEN environment variable:\n"
            "  export HF_TOKEN='your_token_here'\n"
            "  Get token at: https://huggingface.co/settings/tokens"
        )

    except ModelNotFoundError:
        raise MCPError(
            f"Model '{model_id}' not found.\n"
            f"Search for models: use search_mlx_models() tool\n"
            f"Or browse: https://huggingface.co/models?library=[framework]"
        )

    except InsufficientDiskSpace as e:
        raise MCPError(
            f"Insufficient disk space. Need {e.required_gb}GB, have {e.available_gb}GB.\n"
            f"Free up space or use smaller model variant."
        )
```

### Phase 4: Deploy & Test

**Testing**:
```bash
# Syntax check
python -m py_compile mcp_server.py

# Run server
python mcp_server.py

# Test with Claude Desktop
# Add to claude_desktop_config.json:
{
  "mcpServers": {
    "[project_name]-[framework]": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

---

## Best Practices for [PROJECT_NAME]

### 1. ML-Specific Tool Design

**Good tool patterns for ML workflows**:
```python
# ✅ Workflow-oriented
@mcp.tool()
def prepare_training_data(
    content_type: str,  # "tweets", "articles", etc.
    target_belief: str,
    num_samples: int
) -> dict:
    """End-to-end data preparation for belief tuning.

    Combines: content extraction → variation generation → formatting
    Returns: Ready-to-use training data + quality metrics
    """
    # Combines multiple steps into one workflow
    pass

# ❌ Too granular
@mcp.tool()
def extract_content(...): pass
@mcp.tool()
def generate_variations(...): pass
@mcp.tool()
def format_for_training(...): pass
# User has to orchestrate 3 separate calls
```

### 2. Return Format Optimization

**For training metrics**:
```python
# ✅ High-signal summary
return {
    "final_accuracy": 0.89,
    "improvement_over_baseline": "+12%",
    "best_epoch": 15,
    "status": "converged",
    "warnings": ["Learning rate adjusted at epoch 8"]
}

# ❌ Raw dump (wastes tokens)
return {
    "all_epochs": [0.45, 0.52, 0.61, ...],  # 100 values
    "all_losses": [...],  # 100 values
    "all_timestamps": [...],  # 100 values
    # 1000s of tokens of raw data
}
```

### 3. Error Messages for ML Context

**Helpful ML error messages**:
```python
raise MCPError(
    "Model architecture mismatch:\n"
    "  Expected: Llama architecture\n"
    "  Got: Mistral architecture\n"
    "\n"
    "Solution: Use base_model='mistralai/Mistral-7B-v0.1' instead\n"
    "Or search compatible models: search_mlx_models(query='llama lora')"
)
```

---

## Example MCP Servers for [PROJECT_NAME]

### 1. HuggingFace [FRAMEWORK] Integration

**Tools**:
- `search_mlx_models()` - Find [FRAMEWORK]-compatible models
- `get_model_info()` - Detailed model metadata
- `download_model()` - Download with progress tracking
- `list_downloaded_models()` - Local model inventory

### 2. Training Monitor

**Tools**:
- `get_training_status()` - Current training state
- `get_metrics_summary()` - Latest metrics
- `pause_training()` - Pause long-running training
- `export_checkpoint()` - Save current state

### 3. Data Curator Integration

**Tools**:
- `extract_content()` - From URLs/files
- `generate_variations()` - Create training variations
- `validate_dataset()` - Check data quality
- `export_for_training()` - Format for [PROJECT_NAME]

---

## Quick Reference

**When to create MCP server**:
- Integrating external API (HuggingFace, wandb, etc.)
- Recurring workflow needs automation
- Need to access external data sources
- Building custom tool suite

**When NOT to use MCP**:
- One-off scripts (just write Python)
- Internal functions (use normal imports)
- Simple utilities (not worth overhead)

**Tool design checklist**:
- [ ] Workflow-oriented (not just API wrapper)
- [ ] Returns high-signal data (not raw dumps)
- [ ] Actionable error messages
- [ ] Proper type hints (Pydantic)
- [ ] Tool annotations (readOnly, idempotent, etc.)
- [ ] Comprehensive docstrings

---

## Resources

**MCP Documentation**:
- Full docs: https://modelcontextprotocol.io/llms-full.txt
- FastMCP (Python): https://github.com/jlowin/fastmcp
- MCP SDK (TypeScript): https://github.com/modelcontextprotocol/sdk

**[PROJECT_NAME] Integration Ideas**:
- HuggingFace model search
- Weights & Biases experiment tracking
- [FRAMEWORK] Hub integration
- Dataset repositories (HF Datasets)
- GPU monitoring (nvidia-smi)

---

**This skill helps you build professional MCP servers that integrate [PROJECT_NAME] with external ML services.**
