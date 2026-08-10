## What changed

<!-- Describe the focused change. -->

## Why

<!-- State the observable problem and the owning boundary. -->

## Safety and compatibility

- [ ] Existing unmarked guidance remains user-owned.
- [ ] Unsafe or ambiguous states still skip instead of overwrite.
- [ ] The scanner does not execute repository code or access the network.
- [ ] Public behavior and both READMEs are updated when required.
- [ ] No secrets, private paths, proprietary fixtures, or generated noise are included.

## Verification

```text
make check-changed BASE=origin/main
```

<!-- Replace with exact commands run. Use make check only when a full-suite trigger applies. -->

## Remaining risk

<!-- State material residual risk, or write None. -->
