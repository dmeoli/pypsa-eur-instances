"""Turn a network of gen_modular_tssb.py into a TwoStageStochasticBlock.

    python emit_modular_tssb.py mod_t168_s50_b1 [form]

The same network can be written in several forms, which SMS++ then solves in
different ways, and `form` chooses among them:

- `ucblock` (default): the design is a Variable of each unit, integer for the
  modular assets (the number of modules), replicated in every scenario and
  tied by the non-anticipativity Constraint; this is the extensive form, which
  a :MILPSolver solves as it is, a LagrangianDualSolver decomposes by
  scenario, and BendersDecompositionSolver takes in its Benders form;
- `design_cost_outside`: the same, with the cost of the design stated once
  outside the units, which is what a generic Benders solver reads the sign of
  its cuts from;
- `investment_outside`: the design stated once, in an InvestmentBlock over the
  whole stochastic Block, i.e., the ad hoc Benders form; the design of an
  InvestmentBlock is a capacity, so the modules are relaxed to a continuous
  capacity in this form.

The file is written as `output/modular_tssb/smspp/smspp_<name>_<form>.nc4`.
"""

import os
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "output" / "modular_tssb"
sys.path.insert(0, str(HERE.parent))
from _pypsa2smspp import TEST  # noqa: E402
os.chdir(TEST)

import pypsa
from pypsa2smspp.transformation import Transformation

FORMS = ("ucblock", "design_cost_outside", "investment_outside")

name = sys.argv[1] if len(sys.argv) > 1 else "mod_t168_s20_b1"
form = sys.argv[2] if len(sys.argv) > 2 else "ucblock"
if form not in FORMS:
    raise SystemExit(f"form must be one of {FORMS}")

WORK = DATA / "smspp"
WORK.mkdir(parents=True, exist_ok=True)

n = pypsa.Network(str(DATA / f"{name}_flat.nc"))
if form == "investment_outside":
    # the InvestmentBlock has a continuous design: the modules are relaxed
    for frame in (n.generators, n.storage_units):
        frame["p_nom_mod"] = 0.0

t = Transformation(
    name=f"{name}_{form}",
    configfile="TSSBlock/TSSBSCfg.txt",
    capacity_expansion_ucblock=(form != "investment_outside"),
    intermittent_carriers=["solar", "wind"],
    workdir=str(WORK),
    stochastic_parameters={
        "stochastic_type": "tssb",
        "parameters": ["demand", "renewable_maxpower"],
        "design_cost_outside": form == "design_cost_outside",
        # the cost stated outside the units is stated in an InvestmentBlock
        # above them, which the converter writes when either form is asked
        "investment_outside": form in ("investment_outside",
                                       "design_cost_outside"),
        },
    overwrite=True,
    fp_temp="smspp_{name}_temp.nc",
)
t.create_model(n, verbose=False)
target = WORK / f"smspp_{name}_{form}.nc4"
t.sms_network.to_netcdf(str(target), force=True)
print("[written]", target)
