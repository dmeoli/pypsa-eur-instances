# SMS++ instances from PyPSA networks

The generators of the instances that the batches of the SMS++ tests run
(`tests/UCBlock/batches/batch-pypsa`, `batch-nuclear`,
`tests/InvestmentBlock/batches/batch-pypsa` and the stochastic ones), each
network being converted by pypsa2smspp and its reference value being the
optimum PyPSA computes on it. They are scripts, not tests: each one writes a
family of instances and prints their references in the format of the REF_OBJ
entries of the batch files.

Several of them build their networks from the Excel test networks of
pypsa2smspp, or read the networks that the references of pypsa2smspp write
under `test/output`; the environment variable `PYPSA2SMSPP_TEST` names the
`test` directory of a pypsa2smspp checkout (see `_pypsa2smspp.py`), e.g.

```
export PYPSA2SMSPP_TEST=~/pypsa2smspp/test
python instance_generator.py <UCBlock output> <InvestmentBlock output>
```

| script | what it writes |
|---|---|
| `instance_generator.py` | every Excel test network, in both the UCBlock and the InvestmentBlock form, from one seeded build (the InvestmentBlock form with `config/smspp/InvestmentBlock-BS2`) |
| `pollutant_generator.py` | one of them with the global constraints of PyPSA on the dispatch, which pypsa2smspp translates into the pollutant budgets of UCBlock |
| `tree_instance_generator.py` | the scenario trees of the stochastic batches, from the networks `gen_tree_instance.py` of pypsa2smspp writes |
| `nuclear_generator.py` | a single-bus network whose nuclear generator is written as a ThermalUnitBlock and then as a NuclearUnitBlock with one family of operating rules at a time; PyPSA has no such rules, so the reference is the optimum of SMS++ itself |
| `references/gen_pypsaeur_nuclear.py` | the same from a PyPSA-Eur network |
| `references/gen_modular_tssb.py`, `emit_modular_tssb.py`, `solve_modular_tssb.py` | a two-stage family whose first stage builds whole modules of solar and wind, its conversion and its PyPSA reference |
| `references/extensive_thermal_tssb.py` | the deterministic equivalent of the thermal two-stage family of pypsa2smspp (`gen_thermal_tssb.py`), solved by PyPSA |
| `test_design_bounds.py` | a check, run with pytest, of the bounds below |

## The bounds of the extendable assets

An extendable asset with no bound makes some Lagrangian subproblem unbounded,
and a bound picked out of thin air (the former 1e7 and 1e8) is worse than
none, since the design is bang-bang and the master of the bundle is left with
coefficients its quadratic term cannot be compared with. The generators give
an extendable asset with no bound one read off the demand
(`bound_extendable_assets` of pypsa2smspp, `SMSPP_DESIGN_BOUNDS` choosing
among `physical`, `none` and `sentinel`), which is a scale and not a valid
bound: an intermittent generator produces its capacity times its
availability, and may have to be built well beyond the peak of the load.
`verify_extendable_bounds` therefore solves the network and doubles every
bound whose multiplier says it cuts the optimum, until none does, which is
exact for a linear network; the reference is taken from that solution.
