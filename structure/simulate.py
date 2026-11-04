"""Solvate a PDB structure and run Langevin MD on the GPU (OpenMM, AMBER14/TIP3P, 300 K, 2 fs).

Defaults reproduce experiment 002 (crambin, 1 ns). Experiment 001 was --steps 10000 --dcd-interval 1000.
Reads the PDB from the working directory; writes initial.pdb, trajectory.dcd and final.pdb there.
"""

import argparse
import sys
from openmm import Platform, LangevinMiddleIntegrator
from openmm.app import (
    PDBFile, ForceField, Modeller, Simulation,
    PME, HBonds, DCDReporter, StateDataReporter
)
from openmm.unit import nanometer, kelvin, picosecond

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--pdb", default="1crn.pdb")
parser.add_argument("--steps", type=int, default=500000, help="2 fs each; 500000 = 1 ns")
parser.add_argument("--dcd-interval", type=int, default=5000, help="steps between trajectory frames")
parser.add_argument("--platform", default="CUDA")
args = parser.parse_args()

# Load real experimental protein structure
pdb = PDBFile(args.pdb)

# Molecular physics model
forcefield = ForceField("amber14-all.xml", "amber14/tip3p.xml")

# Prepare protein and water environment
modeller = Modeller(pdb.topology, pdb.positions)
modeller.addHydrogens(forcefield)
modeller.addSolvent(forcefield, padding=1.0 * nanometer)

system = forcefield.createSystem(
    modeller.topology,
    nonbondedMethod=PME,
    nonbondedCutoff=1.0 * nanometer,
    constraints=HBonds
)

# 300 Kelvin, 2 femtosecond timestep
integrator = LangevinMiddleIntegrator(
    300 * kelvin,
    1 / picosecond,
    0.002 * picosecond
)

# NVIDIA GPU by default
platform = Platform.getPlatformByName(args.platform)
simulation = Simulation(
    modeller.topology, system, integrator,
    platform, {"Precision": "mixed"} if args.platform in ("CUDA", "OpenCL") else {}
)

simulation.context.setPositions(modeller.positions)
print("Platform:", simulation.context.getPlatform().getName())
print("Atoms:", system.getNumParticles())

# Relax and initialize system
simulation.minimizeEnergy(maxIterations=500)
simulation.context.setVelocitiesToTemperature(300 * kelvin)

# Save starting structure, including water
with open("initial.pdb", "w") as f:
    PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )

# Record motion and performance
simulation.reporters.append(
    DCDReporter("trajectory.dcd", args.dcd_interval)
)
simulation.reporters.append(
    StateDataReporter(
        sys.stdout, 1000,
        step=True,
        potentialEnergy=True,
        temperature=True,
        speed=True
    )
)

simulation.step(args.steps)

with open("final.pdb", "w") as f:
    PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )

print("Simulation complete.")
