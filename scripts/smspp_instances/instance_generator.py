# -*- coding: utf-8 -*-
"""
Generator of the SMS++ instances translated from the PyPSA test networks.

Each Excel test network is built once and written in both the forms the
conversion supports: the UCBlock one, where the design variables are those of
the UCBlock itself (`capacity_expansion_ucblock=True`), and the
InvestmentBlock one, where an InvestmentBlock wraps it
(`capacity_expansion_ucblock=False`). Both are written from the same network
and are held to the same reference, the objective value PyPSA computes on it,
which is printed in the format of the REF_OBJ entries of the SMS++ batch
files `tests/UCBlock/batches/batch-pypsa` and
`tests/InvestmentBlock/batches/batch-pypsa`.

The demand and the hydro inflow of a test network are drawn from a normal
distribution [see add_demand() and add_hydro_inflow() of NetworkDefinition],
so two builds of the same Excel file give two different networks; the seed of
each case is therefore fixed here, which makes the instances reproducible and
the two forms of a case the same problem.

With --carriers, each network whose buses are not all electric is also
written with the buses of each carrier in a carrier of the UCBlock
(`multi_carrier=True` of the conversion), in both forms and held to the same
reference, as smspp_<case>_carriers.nc.

Usage:
    python instance_generator.py <UCBlock output directory>
                                 <InvestmentBlock output directory>
                                 [--carriers] [case ...]

with no case, every Excel test network is written.
"""

import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _pypsa2smspp import TEST  # noqa: E402, the test networks of pypsa2smspp

from conftest import create_test_config, test_cases
from network_definition import NetworkDefinition
from pypsa2smspp.transformation import Transformation
from pypsa2smspp.network_correction import (add_slack_unit,
                                            clean_ciclicity_storage)
from pypsa2smspp.utils import ELECTRIC_BUS_CARRIERS


# the seed of each case, so that its network is always the same one
SEED = 20260918

OUT = HERE / "output" / "instances"

# the InvestmentBlock is written here with the configuration of the
# BundleSolver 2.0, the one every instance of the set is solved by; what the
# package uses by default is the configuration the released SMS++ reads, the
# BundleSolver being 1.0 there [see config/smspp/InvestmentBlock-BS2/README.md]
IB_CONFIG = (HERE.parents[1] / "config" / "smspp" / "InvestmentBlock-BS2" /
             "BSPar_2.0.txt")


# the Excel cases that give a network another case already gives: their
# instances came out byte for byte the same, so they are written no more
DUPLICATES = {"inv_1n_1c_1g_ext": "1n_1c_1gext",
              "inv_2n_1c_1g_1b_ext": "2n_1c_1gext_1bext_2l"}

# the Excel cases that carry a global constraint, which the tests of this
# package run: the instances with a pollutant budget of the SMS++ batches are
# written by pollutant_generator.py from a network of its own
NOT_INSTANCES = ("co2_",)


def build(xlsx_path):
    """Builds the network of a case, always the same one."""
    np.random.seed(SEED)
    parser = create_test_config(xlsx_path)
    n = NetworkDefinition(parser).n
    n = clean_ciclicity_storage(n)
    if "sector" not in xlsx_path.name:
        n = add_slack_unit(n)
    return n, getattr(parser, "solver_name", "highs")


def has_carriers(n):
    """True if some bus of n is not electric, i.e. n has a carrier form."""
    kinds = set(n.buses.carrier.fillna("").astype(str))
    return not kinds <= set(ELECTRIC_BUS_CARRIERS)


def write(n, case_name, ucblock, out_dir, multi_carrier=False):
    """
    Writes one form of a case, returning the objective value SMS++ computes,
    None if it gives none.

    The file `Transformation.run()` hands to SMS++ is the instance, hence it
    is moved into out_dir under the name of the case; whether the run then
    solves it is another matter, the batch being what holds the instance to
    its reference, so an answer SMS++ refuses to give is reported and no
    more.
    """
    transformation = Transformation(
        capacity_expansion_ucblock=ucblock,
        multi_carrier=multi_carrier,
        workdir=OUT,
        name=case_name,
        overwrite=True,
        fp_temp="smspp_{name}_temp.nc",
        fp_log="smspp_{name}_log.txt",
        fp_solution="smspp_{name}_solution.nc",
        configfile="auto" if ucblock else IB_CONFIG,
        pysmspp_options={},
    )
    value = None
    try:
        transformation.run(n.copy(), verbose=False)
        value = float(transformation.result.objective_value)
    except Exception as error:
        print(f"    [{case_name}] SMS++ gave no answer: {error}", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(OUT / f"smspp_{case_name}_temp.nc",
                out_dir / f"smspp_{case_name}.nc")

    return value


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1

    uc_dir = Path(argv[1]).resolve()
    inv_dir = Path(argv[2]).resolve()
    carriers = "--carriers" in argv[3:]
    wanted = set(argv[3:]) - {"--carriers"}

    cases = [(p, i) for p, i in zip(test_cases["xlsx_paths"], test_cases["ids"])
             if ( (not wanted) or (Path(p).stem in wanted) )
             and ( Path(p).stem not in DUPLICATES )
             and ( not Path(p).stem.startswith(NOT_INSTANCES) )]

    uc_refs, inv_refs = [], []

    for xlsx_path, _ in cases:
        case_name = Path(xlsx_path).stem
        n, solver_name = build(Path(xlsx_path))

        # the reference is the objective value of PyPSA on the same network,
        # solved as a copy, PyPSA not copying a network it has solved
        reference = n.copy()
        reference.optimize(solver_name=solver_name)
        obj_pypsa = float(reference.objective +
                          getattr(reference, "objective_constant", 0.0))

        names = [(case_name, False)]
        if carriers and has_carriers(n):
            names.append((f"{case_name}_carriers", True))
        for name, multi_carrier in names:
            obj_uc = write(n, name, True, uc_dir, multi_carrier)
            obj_inv = write(n, name, False, inv_dir, multi_carrier)

            smspp = ["no answer" if v is None else f"{v:.9e}"
                     for v in (obj_uc, obj_inv)]
            print(f"{name}: PyPSA = {obj_pypsa:.9e}  "
                  f"UCBlock = {smspp[0]}  InvestmentBlock = {smspp[1]}",
                  flush=True)

            uc_refs.append(f"REF_OBJ[smspp_{name}.nc]={obj_pypsa:.9e}")
            inv_refs.append(f"REF_OBJ[smspp_{name}.nc]={obj_pypsa:.9e}")

    print("\n# UCBlock/batches/batch-pypsa")
    print("\n".join(uc_refs))
    print("\n# InvestmentBlock/batches/batch-pypsa")
    print("\n".join(inv_refs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
