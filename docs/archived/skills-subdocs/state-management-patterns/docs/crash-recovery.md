# Crash Recovery Patterns

Design state to enable recovery after crashes.

## Principles

1. State includes progress tracking
2. Support "resume from checkpoint"
3. Validate state on load
4. Handle schema migrations

## Example

```python
@dataclass
class RecoverableState:
    task_id: str
    items: List[str]
    current_index: int = 0
    completed: List[str] = field(default_factory=list)

    def get_next(self) -> Optional[str]:
        while self.current_index < len(self.items):
            item = self.items[self.current_index]
            if item not in self.completed:
                return item
            self.current_index += 1
        return None
```

See: `examples/crash-recovery-example.py`
