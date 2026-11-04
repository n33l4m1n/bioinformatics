# Structure: molecular dynamics

GPU molecular dynamics with [OpenMM](https://openmm.org/) and trajectory analysis with
[MDAnalysis](https://www.mdanalysis.org/). Part of the [bioinformatics verticals](../README.md).

| File | Does |
| --- | --- |
| `simulate.py` | Solvates a PDB structure (AMBER14, TIP3P, 1.0 nm padding), minimizes, then runs Langevin MD at 300 K with a 2 fs step. Writes `initial.pdb`, `trajectory.dcd`, `final.pdb`. |
| `analyze.py` | Aligns the trajectory on Cα, then reports RMSD, per-residue RMSF and radius of gyration; writes `trajectory_analysis.png` and `crambin_rmsf.pdb` (RMSF in the B-factor column). |
| `crambin-1ns.toml` | The whole run as a [biorun](../engine/README.md) pipeline: environment capture, pinned PDB download, simulation, analysis. |

## Run it

Needs an NVIDIA GPU with CUDA and a Python environment with OpenMM, MDAnalysis and Matplotlib.
Measured on a GTX 1660 SUPER (6 GB) with OpenMM 8.6.1 (CUDA 12, mixed precision) and MDAnalysis 2.10:
the 7,509-atom solvated crambin system ran at about 535 ns/day.

```sh
python -m openmm.testInstallation        # confirms the CUDA platform
biorun run structure/crambin-1ns.toml --workdir runs/crambin-1ns
```

`simulate.py --steps 10000 --dcd-interval 1000` is the 20 ps smoke test; `--platform CPU` runs without a GPU
(slowly). Outputs land in the work directory, never in the repository.

## Results so far (crambin, 1 ns, single replica)

Average Cα RMSD 0.64 Å (max 1.08 Å), radius of gyration stable at 9.6–10.0 Å, most flexible region around
residues 37–38. **Preliminary:** 1 ns, no separate equilibration phase, no barostat, one trajectory, no
experimental comparison. Next: explicit equilibration, energy and temperature series, seeded replicas, longer runs.
