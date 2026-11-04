
import MDAnalysis as mda
from MDAnalysis.analysis import align, rms
import numpy as np
import matplotlib.pyplot as plt

# Load atomic coordinates and trajectory
u = mda.Universe("initial.pdb", "trajectory.dcd")
ref = mda.Universe("initial.pdb")

protein = u.select_atoms("protein")
ca = u.select_atoms("protein and name CA")
ref_ca = ref.select_atoms("protein and name CA")

# Align protein across all frames to remove
# overall translation and rotation
align.AlignTraj(
    u, ref,
    select="protein and name CA",
    in_memory=True
).run()

reference_xyz = ref_ca.positions.copy()

times = []
rmsd_values = []
rg_values = []

for frame in u.trajectory:
    times.append(frame.time / 1000)  # ns

    displacement = ca.positions - reference_xyz
    rmsd_values.append(
        np.sqrt(np.mean(np.sum(displacement**2, axis=1)))
    )

    rg_values.append(protein.radius_of_gyration())

# Per-residue fluctuation, after alignment
rmsf_values = rms.RMSF(ca).run().results.rmsf

# Generate scientific plots
fig, axes = plt.subplots(3, 1, figsize=(10, 10))

axes[0].plot(times, rmsd_values)
axes[0].set_ylabel("RMSD (Å)")
axes[0].set_xlabel("Time (ns)")
axes[0].set_title("Protein Structural Deviation")

axes[1].plot(ca.resids, rmsf_values)
axes[1].set_ylabel("RMSF (Å)")
axes[1].set_xlabel("Residue")
axes[1].set_title("Residue Flexibility")

axes[2].plot(times, rg_values)
axes[2].set_ylabel("Radius of Gyration (Å)")
axes[2].set_xlabel("Time (ns)")
axes[2].set_title("Protein Compactness")

plt.tight_layout()
plt.savefig("trajectory_analysis.png", dpi=200)

print(f"Frames analyzed: {len(times)}")
print(f"Average RMSD: {np.mean(rmsd_values):.3f} Å")
print(f"Maximum RMSD: {np.max(rmsd_values):.3f} Å")
print(f"Average Rg: {np.mean(rg_values):.3f} Å")
print("Saved: trajectory_analysis.png")

mid = len(rmsd_values) // 2

print("\nSTRUCTURAL DIAGNOSTICS")

print(
    "RMSD first half:",
    f"{np.mean(rmsd_values[:mid]):.3f} Å"
)

print(
    "RMSD second half:",
    f"{np.mean(rmsd_values[mid:]):.3f} Å"
)

print(
    "Rg range:",
    f"{np.min(rg_values):.3f} - {np.max(rg_values):.3f} Å"
)

print("\nMOST FLEXIBLE RESIDUES")

for i in np.argsort(rmsf_values)[-5:][::-1]:
    atom = ca[i]
    print(
        f"{atom.resname}{atom.resid}: "
        f"{rmsf_values[i]:.3f} Å"
    )

# Store each residue's RMSF in the PDB B-factor field
if not hasattr(u.atoms, "tempfactors"):
    u.add_TopologyAttr("tempfactors")

for atom, value in zip(ca, rmsf_values):
    atom.residue.atoms.tempfactors = float(value)

# Export protein alone, excluding water
u.trajectory[-1]
protein.write("crambin_rmsf.pdb")

print("Saved: crambin_rmsf.pdb")
