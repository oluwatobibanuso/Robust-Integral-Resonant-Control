# Integral Resonant Control for Nanopositioning

A reproducible, continuous-time study of resonant damping and position tracking
for a piezoelectric nanopositioning platform. The repository includes measured
frequency-response data, a four-mode model, an IRC damping loop and an integral
tracking loop.

**Status:** the Python baseline is executable and numerically checked. It is a
linear simulation study, not a hardware-validated controller or a proof of
robustness. Hysteresis, creep and actuator limits are not modeled.

## Quick start

Use Python 3.12. From the repository root:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest -v
python run_analysis.py --output results
```

The runner creates CSV/JSON results and three figures under `results/`. No
MATLAB installation is required. The optional `sysID.ipynb` can be opened with
your preferred Jupyter installation; it inspects the measured response, while
the script runs the complete benchmark.

## Verified baseline and tradeoffs

For a 40 Hz triangular reference of amplitude **1 equivalent nm**, with errors
measured over the final four of twelve periods:

| Configuration | RMS error (equiv. nm) | Peak error (equiv. nm) | 2% step settling (s) |
| --- | ---: | ---: | ---: |
| Open loop | 0.05045 | 0.09557 | 0.14103 |
| IRC damping | 0.09203 | 0.15865 | 0.00563 |
| IRC + conservative tracking | 0.42624 | 0.56986 | 0.01271 |

**Damping substantially shortens settling, but this conservative tracking gain
increases 40 Hz triangle error.** Unity DC gain does not imply good dynamic
tracking. These results establish an honest baseline for gain tuning, not an
optimized controller. Step settling is relative to each configuration's own
final value, so it does not measure its reference offset.

- Fixed gains: `d = -2`, `kd = 1868.0396`, `kt = 264.1807`.
- All internal poles are stable for the nominal configurations and all 15
  illustrative tracking-loop parameter cases.
- The rounded model's relative complex response error against the included
  measurement is about **0.1906%**. This is not independent validation or the
  original MATLAB fit statistic.
- The 200 kHz and 400 kHz simulation grids agree within 0.001 equivalent nm
  for aligned output samples and the reported error/input metrics.

The measurement's physical calibration is not documented. Input and output
are treated as normalized displacement-equivalent quantities; **these are not
verified nanometre positioning accuracy or actuator voltage measurements**.

See [controller derivation, methodology and limitations](docs/controller.md)
and the [recorded numerical result](docs/baseline.json). CI runs the tests and
benchmark and uploads regenerated results.

## Repository guide

| File | Purpose |
| --- | --- |
| `platform_resp.mat` | Original `Freq` and complex `MagR` measurements; includes DC |
| `irc.py` | Modal plant, explicit feedback states, simulation and response helpers |
| `run_analysis.py` | Model comparison, tracking metrics, convergence and parameter sweep |
| `test_irc.py` | Independent transfer-equation, stability, data and convergence checks |
| `sysID.ipynb` | Measured-response exploration; corrected Hz-to-rad/s conversion |
| `sysID.md`, `controlAnalysis.md` | Historical MATLAB exports, retained with notices |

The original work addresses resonance-induced vibration in nanopositioning
applications such as scanning probe microscopy and nanomachining. The next
experimental steps are to document calibration, obtain independent measurements,
justify uncertainty ranges, tune the tracking/noise/control-effort tradeoff,
and evaluate saturation, hysteresis, creep and digital implementation effects.
