# Robot profiles

Per-robot tuning (gains / limits / button). The SDK ships sensible defaults
**inside the installed package** — you only add a file when a specific robot
needs something different.

## Files here

- **`MILLY_SAMPLE.yaml`** — template. Copy it to `<YOUR_PRODUCT_ID>.yaml` (the ID
  engraved on the arm, e.g. `MILLY_A1B2`) and edit only the keys you want to
  change. Everything you omit is inherited.
- **`MILLY_DEFAULT.yaml`** — the base values every robot inherits, for reference.
  ⚠️ **Editing this copy has no effect** — the real default is loaded from the
  installed package. It's here so you can see what you're overriding.

The safety/gravity "canonical" profile is **locked inside the package** and is
not user-editable.

## How tuning resolves (3-tier, key-by-key merge)

```
canonical (package, locked)  +  MILLY_DEFAULT (package)  +  <YOUR_ID>.yaml (yours)
```

A key you omit in your file is **inherited**, not dropped — so safety features
never silently disappear. Only whitelisted keys are allowed; a typo or an
out-of-range value is a load-time error.

## Where to put your `<YOUR_ID>.yaml`

Point the SDK at a directory of your robot files with `MOTOMIND_CONFIG_DIR`:

```bash
export MOTOMIND_CONFIG_DIR=~/.config/motomind/robots
mkdir -p "$MOTOMIND_CONFIG_DIR"
cp MILLY_SAMPLE.yaml "$MOTOMIND_CONFIG_DIR/MILLY_A1B2.yaml"   # then edit
```

Without `MOTOMIND_CONFIG_DIR`, the SDK looks in the installed package's
`profiles/` dir. See `SDK_guide_user.md` §2 (profiles) and §10 (safety).
