"""فحص صحي لمحرك التوليد الموجّه (S9) — أداء وجودة الناجين."""
import time

from core.goalgen import GoalSpec, generate_toward_goal

ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"
DICLOFENAC = "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl"

for seed in (ASPIRIN, DICLOFENAC):
    t0 = time.time()
    r = generate_toward_goal(seed, rounds=3, pool_per_round=40, top_keep=5)
    dt = time.time() - t0
    print(f"seed={seed[:20]}... engine={r.engine} reason={r.reason} "
          f"rounds={r.rounds_run} pool={r.pool_size} survivors={len(r.survivors)} "
          f"({dt:.1f}s)")
    for c in r.survivors[:5]:
        print(f"   {c.smiles[:55]:57s} MW={c.mw:6.1f} logP={c.logp:5.2f} "
              f"TPSA={c.tpsa:5.1f} QED={c.qed:.2f} sim={c.sim:.2f} R={c.reward:.2f}")

# بذرة فاسدة
bad = generate_toward_goal("NOT_SMILES", top_keep=5)
print("invalid ->", bad.reason, len(bad.survivors))

# هدف صارم (تشابه 0.95) — يفترض لا ناجين
strict = generate_toward_goal(ASPIRIN, goal=GoalSpec(sim_floor=0.95), top_keep=5)
print("strict ->", strict.reason, len(strict.survivors), "pool=", strict.pool_size)
