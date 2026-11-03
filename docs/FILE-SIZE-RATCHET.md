# File-size ratchet

StaxLine carries a file-size ratchet from its first day, so the
project begins structured and stays structured.

## The rule

1. `.file-size-ratchet.json` at the repository root records a
   baseline line count for every tracked text file.
2. On every check, each tracked text file is compared to its
   baseline:
   - **Same size or smaller: pass.** Shrinking is always welcome.
   - **Larger than baseline: fail**, unless the baseline has been
     deliberately updated in the same change (see below).
   - **Not in the baseline: recorded as new.** A new file passes its
     first check and joins the baseline when the baseline is next
     updated, so new work is possible without weakening the rule
     for existing files.
3. **Hard cap:** no source file may exceed **1,000 lines** without
   an explicit exception recorded in `.file-size-ratchet.json`.
   Files imported from `inkstax-sms` that were already over the cap
   are listed there as `legacy_over_cap` exceptions at exactly
   their imported size — for those files the ratchet is stricter:
   they may only shrink, never grow, exception or not.
4. Binary files are not line-counted. They are listed by path only
   so a new large binary is a visible, deliberate addition.

## Deliberate growth

Growth is sometimes right. Make it deliberate:

```sh
scripts/check-file-size-ratchet.sh --update
```

That rewrites the baseline to current sizes. Commit the baseline
change together with the code change, and state the reason for the
growth in the commit message. A reviewer should be able to tell,
from the baseline diff alone, exactly which files grew and by how
much.

Never update the baseline just to make a failing check pass without
being able to say why the file needed to grow. Prefer splitting the
file instead.

## Running the check

```sh
scripts/check-file-size-ratchet.sh          # check only, exit 1 on violation
scripts/check-file-size-ratchet.sh --update # rewrite baseline to current sizes
```

Requirements: `git`, `python3`. No network, no dependencies.

CI runs the check-only form on every push and pull request via
`.github/workflows/file-size-ratchet.yml`.

## Why

Large files are where this codebase family has repeatedly hurt:
they hide coupling, slow review, and make agent-assisted work
unreliable. The ratchet makes growth a conscious decision and
shrinking the path of least resistance — files never get bigger
by drift, things only get cleaner by default.
