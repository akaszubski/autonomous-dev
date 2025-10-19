# ReAlign MLX - Apple Silicon LLM Training Extensions

**MLX-specific extensions for LLM training on Apple Silicon**

Extends the autonomous-dev plugin with MLX patterns, system monitoring, and training-specific tools.

## Quick Install

```bash
# First install the base plugin
/plugin install autonomous-dev

# Then install MLX extensions
/plugin install realign-mlx
```

## What You Get

### 📚 7 MLX-Specific Skills

| Skill | Domain |
|-------|--------|
| **mlx-patterns** | MLX framework best practices (Apple Silicon optimization) |
| **pattern-curator** | Learn and validate engineering patterns from codebase |
| **requirements-analyzer** | Extract ACTUAL requirements from code (evidence-based) |
| **doc-migrator** | Migrate docs into .claude/ structure |
| **architecture-patterns** | Architectural decision records (ADRs) |
| **github-sync** | GitHub issue tracking, PR automation |
| **mcp-builder** | Build MCP servers for API integrations |

### ⚡ 2 Additional Hooks

| Hook | Event | Action |
|------|-------|--------|
| **auto_align_filesystem.py** | Commit | Validate project structure alignment |
| **validate_standards.py** | Commit | Check type hints, docstrings, standards |

## MLX Critical Patterns

### Nested Layer Structure
```python
# ✅ CORRECT
layer_output = model.model.layers[layer_idx](hidden_states)

# ❌ WRONG - AttributeError!
layer_output = model.layers[layer_idx](hidden_states)
```

### Memory Management
```python
import mlx.core as mx

result = model(input_ids)
mx.eval(result)              # Force computation
mx.metal.clear_cache()       # Clear GPU memory
```

### Error Messages
```python
raise ValueError(
    f"Invalid: {value}\n"
    f"Expected: <format>\n"
    f"See: docs/guides/xyz.md"
)
```

## Use Cases

**This plugin is for you if:**
- Training LLMs on Apple Silicon (M1/M2/M3/M4)
- Using MLX framework
- Building ReAlign or similar training systems
- Need system health monitoring
- Want CI/CD monitoring agents

**Not for you if:**
- Generic Python development → use autonomous-dev only
- NVIDIA GPUs → use autonomous-dev + PyTorch
- Cloud training → use autonomous-dev + cloud tools

## Requirements

- **Claude Code**: 2.0.0+
- **Python**: 3.11+
- **MLX**: Latest version
- **Base Plugin**: autonomous-dev (installed automatically)

## Architecture

ReAlign MLX provides extensions to autonomous-dev:

```
autonomous-dev (base)          realign-mlx (extensions)
├── 7 core agents              (no additional agents)
├── 6 core skills          +   ├── 7 MLX-specific skills
└── 8 automation hooks     +   └── 2 validation hooks
```

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Main Project**: [ReAlign Repository](https://github.com/akaszubski/realign)
- **MLX Docs**: [MLX Documentation](https://ml-explore.github.io/mlx/)

## License

MIT License

## Version

**v3.0.0** (2025-10-19)

Matches ReAlign v3.0.0 production release.

---

**🤖 Powered by Claude Code** | **Optimized for Apple Silicon**
