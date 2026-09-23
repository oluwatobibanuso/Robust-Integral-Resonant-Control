"""Run with: python run_analysis.py --output results"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from irc import design, loop, measured_response, plant, response, simulate


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    hz, measured = measured_response(Path(__file__).parent/'platform_resp.mat')
    nominal = plant()
    predicted = response(nominal, hz)
    positive = hz > 0  # Retain DC for model-error calculation; omit on log axes.
    fig, axes = plt.subplots(2, 1, sharex=True)
    for values, label in [(measured, 'Measured'), (predicted, 'Rounded modal model')]:
        axes[0].semilogx(hz[positive], 20*np.log10(np.abs(values[positive])), label=label)
        axes[1].semilogx(hz[positive], np.unwrap(np.angle(values[positive]))*180/np.pi)
    axes[0].set_ylabel('Magnitude (dB)'); axes[0].legend()
    axes[1].set_ylabel('Phase (degrees)'); axes[1].set_xlabel('Frequency (Hz)')
    fig.tight_layout(); fig.savefig(output/'model_response.png'); plt.close(fig)

    rows, traces, convergence = [], {}, {}
    for mode in ('open', 'damping', 'tracking'):
        system = loop(nominal, mode)
        poles = np.linalg.eigvals(system.A)
        if np.max(poles.real) >= 0:
            raise RuntimeError(f'{mode} is unstable')
        t, reference, trace, metrics = simulate(system)
        _, _, fine, fine_metrics = simulate(system, sample_rate=400000)
        delta = float(np.max(np.abs(trace[:, 0]-fine[::2, 0]))*1e9)
        metric_delta = max(abs(metrics[key]-fine_metrics[key]) for key in metrics)
        if max(delta, metric_delta) > 0.001:
            raise RuntimeError(f'{mode}: timestep convergence failed: {delta} nm')
        convergence[mode] = {'max_output_difference_nm': delta,
                             'max_metric_difference_nm': metric_delta,
                             'fine_rms_error_nm': fine_metrics['rms_error_nm']}
        grid = np.geomspace(0.01, 1e5, 5000)
        gain = np.abs(response(system, grid))
        dc = float(response(system, [0])[0].real)
        below = np.flatnonzero(gain <= abs(dc)/np.sqrt(2))
        # First downward threshold crossing relative to DC, approximate grid value.
        bandwidth = float(grid[below[0]]) if len(below) else None
        step_time = np.linspace(0, 0.5, 100001)
        _, step_out, _ = signal.lsim(system, np.column_stack((
            np.ones_like(step_time), np.zeros_like(step_time), np.zeros_like(step_time))), step_time)
        outside = np.flatnonzero(np.abs(step_out[:, 0]-dc) > 0.02*abs(dc))
        settled = not len(outside) or outside[-1] < len(step_time)-1
        settling = float(step_time[outside[-1]+1]) if len(outside) and settled else (0. if not len(outside) else None)
        rows.append({'mode': mode, **metrics, 'dc_gain': dc,
                     'bandwidth_hz': bandwidth, 'settling_2pct_s': settling,
                     'max_pole_real_per_s': float(np.max(poles.real))})
        traces[mode] = trace
    with (output/'metrics.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    fig, axes = plt.subplots(2, 1, sharex=True)
    mask = t >= 0.25
    axes[0].plot(t[mask], reference[mask]*1e9, 'k--', label='Reference')
    for mode, trace in traces.items():
        axes[0].plot(t[mask], trace[mask, 0]*1e9, label=mode)
        axes[1].plot(t[mask], (reference[mask]-trace[mask, 0])*1e9, label=mode)
    axes[0].set_ylabel('Equivalent displacement (nm)'); axes[0].legend()
    axes[1].set_ylabel('Error (nm)'); axes[1].set_xlabel('Time (s)')
    fig.tight_layout(); fig.savefig(output/'tracking.png'); plt.close(fig)

    # Illustrative sensitivity grid, not measured uncertainty or a robustness proof.
    sweep = []
    for frequency_scale in (0.8, 0.9, 1., 1.1, 1.2):
        for damping_scale in (0.5, 1., 1.5):
            system = loop(plant(frequency_scale, damping_scale))
            worst = float(np.max(np.linalg.eigvals(system.A).real))
            row = {'frequency_scale': frequency_scale, 'damping_scale': damping_scale,
                   'max_pole_real_per_s': worst, 'stable': worst < 0}
            if worst < 0:
                row.update(simulate(system, sample_rate=100000)[-1])
            sweep.append(row)
    fig, axes = plt.subplots(2, 1, sharex=True)
    grid = np.geomspace(0.1, 20000, 1000)
    for mode in ('open', 'damping', 'tracking'):
        system = loop(nominal, mode)
        for ax, channel in zip(axes, (1, 2)):
            values = np.abs(response(system, grid, input_index=channel))
            ax.semilogx(grid, 20*np.log10(np.maximum(values, 1e-15)), label=mode)
    axes[0].set_ylabel('Input disturbance to y (dB)'); axes[0].legend()
    axes[1].set_ylabel('Sensor noise to y (dB)'); axes[1].set_xlabel('Frequency (Hz)')
    fig.tight_layout(); fig.savefig(output/'disturbance_noise.png'); plt.close(fig)
    result = {'gains': dict(zip(('d', 'kd', 'kt'), map(float, design()))),
              'model_relative_complex_l2_error': float(np.linalg.norm(predicted-measured)/np.linalg.norm(measured)),
              'metrics': rows, 'convergence_200khz_vs_400khz': convergence,
              'illustrative_parameter_sweep': sweep,
              'limitations': ['Rounded historical model; no new system identification.',
                              'Normalized displacement-equivalent input, not calibrated voltage.',
                              'Continuous-time linear simulation; no hardware validation.',
                              'Sweep ranges are illustrative, not measured uncertainty.',
                              'No saturation, hysteresis, creep or digital delay model.']}
    (output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results'))
    main(parser.parse_args().output)
