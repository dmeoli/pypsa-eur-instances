# -*- coding: utf-8 -*-
"""
The bounds given to the extendable assets whose bound is infinite.

bound_extendable_assets() reads a bound off the demand, which is a scale and
not a valid bound: here an intermittent generator whose p_max_pu never
exceeds 0.45 has to be built beyond twice the peak of the load to replace an
expensive unit, so the physical bound cuts the optimum, and
verify_extendable_bounds() has to enlarge it until the optimum is the one of
the network with no bound. No SMS++ is needed.
"""
import numpy as np
import pypsa
import pytest

from pypsa2smspp.network_correction import (bound_extendable_assets,
                                            verify_extendable_bounds)


SNAPSHOTS = 24
PEAK = 100.0


def network() -> pypsa.Network:
    """One bus, a flat load, an expensive gas unit and cheap extendable wind."""
    n = pypsa.Network()
    n.set_snapshots(range(SNAPSHOTS))
    n.add("Bus", "bus")
    n.add("Carrier", ["gas", "wind", "battery"])
    # the demand is read off loads_t.p_set, hence a series
    n.add("Load", "load", bus="bus", p_set=np.full(SNAPSHOTS, PEAK))
    n.add("Generator", "gas", bus="bus", carrier="gas", p_nom=2 * PEAK,
          marginal_cost=200.0)
    n.add("Generator", "wind", bus="bus", carrier="wind",
          p_nom_extendable=True, capital_cost=100.0,
          p_max_pu=0.25 + 0.2 * np.sin(2.0 * np.pi * np.arange(SNAPSHOTS) / SNAPSHOTS))
    n.add("StorageUnit", "battery", bus="bus", carrier="battery",
          p_nom_extendable=True, capital_cost=10.0, max_hours=12.0,
          cyclic_state_of_charge=True)
    return n


def solve(n):
    n.optimize(solver_name="highs")


def objective(n):
    return float(n.objective + getattr(n, "objective_constant", 0.0))


def test_the_physical_bound_cuts_this_network():
    unbounded = network()
    solve(unbounded)
    assert unbounded.generators.p_nom_opt["wind"] > 2 * PEAK

    bounded = bound_extendable_assets(network(), "physical")
    assert bounded.generators.p_nom_max["wind"] == pytest.approx(2 * PEAK)
    solve(bounded)
    assert objective(bounded) > objective(unbounded) * (1 + 1e-3)


def test_the_bounds_the_optimum_reaches_are_enlarged():
    unbounded = network()
    solve(unbounded)

    n = bound_extendable_assets(network(), "physical")
    assert n.meta["bounded_extendable_assets"] == {
        "generators": ["wind"], "storage_units": ["battery"]}

    n, solved = verify_extendable_bounds(n, solve)

    assert objective(solved) == pytest.approx(objective(unbounded), rel=1e-9)
    # the bound of the wind generator is doubled until it no longer cuts
    wind = n.generators.p_nom_max["wind"]
    assert wind > 2 * PEAK
    assert wind >= unbounded.generators.p_nom_opt["wind"] * (1 - 1e-9)
    assert np.log2(wind / (2 * PEAK)) == pytest.approx(round(np.log2(wind / (2 * PEAK))))


def test_a_bound_that_is_not_reached_is_left_as_it_is():
    n = bound_extendable_assets(network(), "physical")
    n.generators.at["wind", "capital_cost"] = 1e6  # wind is not worth building
    before = n.generators.p_nom_max["wind"]

    n, solved = verify_extendable_bounds(n, solve)

    assert n.generators.p_nom_max["wind"] == before
    assert solved.generators.p_nom_opt["wind"] < before
