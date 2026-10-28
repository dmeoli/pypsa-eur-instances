# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

# The stochastic instances of the generator of plan4res/resilient: a network of
# the European power system in 2030 per case of config["resilient"]["cases"],
# solved by the solvers of solving.solver as the networks of PyPSA-Eur are, see
# config/instances/resilient/.


rule retrieve_resilient_generator:
    output:
        directory("data/resilient/generator"),
    params:
        url=config_provider("resilient", "generator", "url"),
        commit=config_provider("resilient", "generator", "commit"),
    log:
        "logs/retrieve_resilient_generator.log",
    shell:
        "(git clone --quiet {params.url} {output} && "
        "git -C {output} checkout --quiet {params.commit}) > {log} 2>&1"


rule build_resilient_network:
    input:
        generator="data/resilient/generator",
    output:
        network=resources("networks/resilient_{case}.nc"),
    params:
        case=lambda w: config["resilient"]["cases"][w.case],
    log:
        python=RESULTS + "logs/build_resilient_network/resilient_{case}_python.log",
    benchmark:
        RESULTS + "benchmarks/build_resilient_network/resilient_{case}"
    threads: 1
    resources:
        mem_mb=16000,
    message:
        "Building the stochastic network of the resilient case {wildcards.case}"
    script:
        scripts("build_resilient_network.py")


rule solve_resilient_network:
    input:
        network=resources("networks/resilient_{case}.nc"),
    output:
        network=RESULTS + "networks/resilient_{case}_{solver}.nc",
        config=RESULTS + "configs/config.resilient_{case}_{solver}.yaml",
        model=(
            RESULTS + "models/resilient_{case}_{solver}.nc"
            if config["solving"]["options"]["store_model"]
            else []
        ),
    log:
        solver=normpath(
            RESULTS + "logs/solve_network/resilient_{case}_{solver}_solver.log"
        ),
        memory=RESULTS + "logs/solve_network/resilient_{case}_{solver}_memory.log",
        python=RESULTS + "logs/solve_network/resilient_{case}_{solver}_python.log",
    benchmark:
        RESULTS + "benchmarks/solve_network/resilient_{case}_{solver}"
    shadow:
        shadow_config
    threads: solver_threads
    resources:
        mem_mb=config_provider("solving", "mem_mb"),
        runtime=config_provider("solving", "runtime", default="6h"),
    params:
        solving=solving_for_solver,
        smspp_benchmark=RESULTS
        + "benchmarks/solve_network/resilient_{case}_{solver}.smspp",
        foresight=config_provider("foresight"),
        co2_sequestration_potential=config_provider(
            "sector", "co2_sequestration_potential", default=200
        ),
        custom_extra_functionality=input_custom_extra_functionality,
    message:
        "Solving the resilient case {wildcards.case} with {wildcards.solver}"
    script:
        scripts("solve_network.py")


rule solve_resilient_all:
    input:
        lambda w: expand(
            RESULTS + "networks/resilient_{case}_{solver}.nc",
            case=config["resilient"]["cases"],
            solver=solver_names(),
        ),
