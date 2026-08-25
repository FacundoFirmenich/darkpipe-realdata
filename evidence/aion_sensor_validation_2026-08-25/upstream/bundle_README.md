# Data and code for "A Prototype Differential Atom Interferometer for Fundamental Physics"

**10.5281/zenodo.19592552**

_Data and plots curated by Charles Baynham <c.baynham@imperial.ac.uk> - for authorship contributions see [the paper](https://arxiv.org/abs/2504.09158)._

Reproducible figure-generation code for the Differential Atom Interferometry (DAI) paper from the AION experiment at Imperial College London.

This repository contains the data and figure scripts for [arXiv:2504.09158](https://arxiv.org/abs/2504.09158).

## Figures

| Notebook | Description |
|----------|-------------|
| `Figure 1.ipynb` | Black-hole merger sensitivity projections |
| `Figure 4.ipynb` | Composite figure: Allan deviation, signal recovery, and noise analysis |
| `Figure 5a.ipynb` | Maximum-likelihood frequency scan results |
| `Figure 5b.ipynb` | Amplitude histogram analysis across signal strengths |

## Repository Structure

```
├── pyproject.toml            # Python dependencies
├── uv.lock                   # Pinned dependency lockfile
├── utilities/                # Stripped-down analysis utilities
│   ├── plots.py              # Plotting helpers and styles
│   ├── adevtools.py          # Allan deviation tools
│   ├── datasets/paths.py     # Data path resolution (local paths)
│   └── analysis/
│       └── signal_extraction.py
├── data/                     # All data bundled (no network access needed)
│   ├── intermediate_data/    # Pre-processed experimental data (CSVs, NPYs)
│   ├── precomputed_true_signals/  # Pre-computed signal extraction results (NPZs)
│   ├── 2026-01-20-DAI-Analysis/  # Monte Carlo and timeseries data
│   ├── 2026-02-24-Amplitude-DAI-MC/ # Amplitude Monte Carlo results
│   └── 2025-02-12-black-holes-plot/ # Black hole merger sensitivity data
├── figures/                  # Notebooks and generated outputs
│   ├── Figure 1.ipynb
│   ├── Figure 4.ipynb
│   ├── Figure 5a.ipynb
│   └── Figure 5b.ipynb
└── icl_experiments/          # Trimmed ARTIQ experiment repository
    ├── repository/           # Experiment code (DifferentialClockInterferometryWithNoiseAndSignalFrag)
    ├── device_db_config/     # Device database configuration
    ├── hdf5_data/            # Raw ARTIQ HDF5 datasets
    └── pyproject.toml        # Experiment dependencies
```

## Running the Notebooks

Dependencies are managed with [uv](https://docs.astral.sh/uv/). The `uv.lock` file pins every transitive dependency to exact versions.

1. Download this repository and extract the files.

2. Open a terminal in the extracted directory.

3. Install uv if you don't have it:

   - **macOS / Linux:**
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```
   - **Windows (PowerShell):**
     ```powershell
     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
     ```

   For more options, see the [UV installation guide](https://docs.astral.sh/uv/getting-started/installation/).

4. Create a virtual environment and install all dependencies:

   ```bash
   uv sync
   ```

5. Open any notebook in `figures/`:

   ```bash
   uv run jupyter notebook
   ```

To update or add dependencies, edit `pyproject.toml` and run `uv lock` to regenerate the lockfile.

All data is bundled in `data/` — no network access or external data stores are required.

## Data Provenance

Experimental data was collected using the ARTIQ control system on the [AION strontium cold-atom interferometer at Imperial College London](https://www.hep.ph.ic.ac.uk/AION-Project/). Raw datasets are stored on the ICL Research Data Store (RDS) and were pre-processed into the CSV/NPY/NPZ files included here.

- **intermediate_data/**: Excitation fraction timeseries extracted from ARTIQ HDF5 datasets, plus MLE fitting results. The CSV filenames encode the 5-digit run IDs (RIDs) of the source HDF5 files.
- **precomputed_true_signals/**: Frequency and phase extraction results computed via `NDScanDataset.from_rid()` and `extract_frequency_and_phase()` — bundled as NPZ files to remove the ARTIQ/RDS dependency
- **2026-01-20-DAI-Analysis/**: Monte Carlo Allan deviation results and residual timeseries
- **2026-02-24-Amplitude-DAI-MC/**: Monte Carlo simulation results for three signal amplitude levels
- **2025-02-12-black-holes-plot/**: Gravitational wave sensitivity curves and black hole merger population data
- **icl_experiments/**: Trimmed ARTIQ experiment repository retaining only the code needed to run `DifferentialClockInterferometryWithNoiseAndSignalFrag`. Raw HDF5 datasets are stored in `icl_experiments/hdf5_data/`.
