# Expected answer format

## Short conclusion
One or two sentences: what was found and how confident the answer is.

## Found objects
- Object: `<1C object full name>`
- Type: document/catalog/common module/form/etc.
- Why relevant: `<matching names, metadata links, code references>`

## Evidence
- File path: `C:\1c-ai-workbench\generated\index\source-mirror\...`
- Module: `<module name if known>`
- Procedure/function: `<name if found>`
- Code fragment:

```bsl
// 5-20 lines maximum, enough to verify
```

## Confidence
- Level: high / medium / low
- Reason: exact metadata match, text match, procedure call graph, or weak keyword match.

## Manual verification
1. Open the configuration copy in Configurator or EDT.
2. Navigate to the object/module named above.
3. Search for the procedure/function or code fragment.
4. Confirm the business meaning with a 1C developer before changing anything.
