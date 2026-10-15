// purpose: Remember each flag's variant at first observation (the healthy state baselines are learned in)
// algorithm: -
UNWIND $flags AS fl
MERGE (f:FeatureFlag {id: fl.id})
SET f.variant = fl.variant, f.baseline_variant = coalesce(f.baseline_variant, fl.variant)
