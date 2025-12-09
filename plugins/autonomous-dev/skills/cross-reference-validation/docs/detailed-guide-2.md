# Cross Reference Validation - Detailed Guide

## Integration with File Move Hook

When files are moved, trigger cross-reference validation:

```bash
# Post-file-move hook
OLD_PATH="$1"
NEW_PATH="$2"

# Find all references to old path
REFERENCES=$(grep -r "$OLD_PATH" --include="*.md" .)

if [ -n "$REFERENCES" ]; then
  echo "📝 Found $(echo "$REFERENCES" | wc -l) references to moved file"
  echo ""
  echo "Auto-update? [Y/n]"
  read RESPONSE

  if [[ "$RESPONSE" =~ ^[Yy] ]]; then
    # Update all references
    find . -name "*.md" -exec sed -i "s|$OLD_PATH|$NEW_PATH|g" {} \;
    echo "✅ Updated all references"
  fi
fi
```

---

## Success Criteria

After validation:
- ✅ All file path references checked for existence
- ✅ All markdown links verified or flagged
- ✅ File:line references validated against actual line count
- ✅ Code examples checked for accurate imports
- ✅ Auto-fix suggestions provided for broken references
- ✅ Completes in < 15 seconds for medium projects

---

## Edge Cases
