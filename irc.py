"""Continuous-time IRC benchmark; normalized displacement-equivalent signals.

Rounded modal coefficients come from sysID.md, not a new identification run.
No actuator voltage calibration, nonlinearities, or sampled controller assumed.
"""
import numpy as np
from scipy import io, signal
from scipy.linalg import block_diag

# numerator, s coefficient, constant denominator coefficient; lowest mode first
MODES = np.array([[9.87e6, 55.29, 9.87e6], [1.578e6, 502.4, 1.579e8],
                  [1.253e6, 997., 6.316e8], [7.22e5, 1644., 1.935e9]])


def measured_response(path):
    data = io.loadmat(path)
    hz = np.asarray(data['Freq']).reshape(-1)
    response = np.asarray(data['MagR']).reshape(-1)
    if hz.shape != response.shape or not np.all(np.isfinite(response)):
        raise ValueError('Invalid frequency-response data')
    if not np.all(np.isfinite(hz)) or np.any(hz < 0) or np.any(np.diff(hz) <= 0):
        raise ValueError('Frequencies must be finite, nonnegative and increasing')
    return hz, response


def plant(frequency_scale=1., damping_scale=1.):
    """Scale all modal frequencies and damping ratios; preserve modal DC gains."""
    if frequency_scale <= 0 or damping_scale <= 0:
        raise ValueError('Scales must be positive')
    blocks, inputs, outputs = [], [], []
    for numerator, damping, stiffness in MODES:
        wn = np.sqrt(stiffness) * frequency_scale
        # States [modal displacement, velocity / wn] avoid polynomial expansion.
        blocks.append([[0., wn], [-wn, -damping*frequency_scale*damping_scale]])
        inputs.extend([0., wn])
        outputs.extend([numerator/stiffness, 0.])
    return signal.StateSpace(block_diag(*blocks), np.array(inputs)[:, None],
                             np.array(outputs)[None, :], [[0.]])


def design():
    numerator, _, stiffness = MODES[0]
    d = -2 * numerator / stiffness
    wn = np.sqrt(stiffness)
    kd = wn / abs(d) * np.sqrt(wn / np.sqrt(stiffness + numerator/d))
    # A conservative starting point from the historical single-mode expression.
    # This is NOT a full-order robust-stability certificate; test actual poles.
    product_bound = -(numerator + d*stiffness) / d**2
    kt = 0.2 * product_bound / kd
    return d, kd, kt


def loop(p, mode='tracking', gains=None):
    """Inputs: reference, additive plant-input disturbance, sensor noise.

    Outputs: physical y, total plant input u. Damping: zdot=kd*(r+y+n+d*z).
    Tracking: zdot=kd*(q+y+n+d*z), qdot=kt*(r-y-n), u=z+w.
    The artificial feedthrough d*z is never part of physical output y.
    """
    if mode not in ('open', 'damping', 'tracking'):
        raise ValueError('Unknown loop mode')
    d, kd, kt = design() if gains is None else gains
    a, b, c = p.A, p.B[:, 0], p.C[0]
    n = len(b)
    extra = {'open': 0, 'damping': 1, 'tracking': 2}[mode]
    A = np.zeros((n+extra, n+extra)); A[:n, :n] = a
    B = np.zeros((n+extra, 3)); B[:n, 1] = b
    C = np.zeros((2, n+extra)); C[0, :n] = c
    D = np.zeros((2, 3)); D[1, 1] = 1
    if mode == 'open':
        B[:n, 0] = b; D[1, 0] = 1
    else:
        A[:n, n] = b; A[n, :n] = kd*c; A[n, n] = kd*d
        B[n, 2] = kd; C[1, n] = 1
        if mode == 'damping':
            B[n, 0] = kd
        else:
            A[n, n+1] = kd; A[n+1, :n] = -kt*c
            B[n+1, 0] = kt; B[n+1, 2] = -kt
    return signal.StateSpace(A, B, C, D)


def response(system, hz, input_index=0, output_index=0):
    """Evaluate in state space without ill-conditioned polynomial conversion."""
    eye = np.eye(system.A.shape[0])
    return np.array([system.C[output_index] @ np.linalg.solve(
        2j*np.pi*f*eye-system.A, system.B[:, input_index])
        + system.D[output_index, input_index] for f in np.asarray(hz)])


def simulate(system, sample_rate=200000, frequency=40., cycles=12):
    count = int(round(cycles/frequency*sample_rate))
    t = np.arange(count+1)/sample_rate
    reference = 1e-9*signal.sawtooth(2*np.pi*frequency*t, width=0.5)
    inputs = np.column_stack((reference, np.zeros_like(t), np.zeros_like(t)))
    _, out, _ = signal.lsim(system, inputs, t)
    # Last four cycles exclude startup from periodic-error measurements.
    mask = t >= (cycles-4)/frequency
    error_nm = (reference[mask]-out[mask, 0])*1e9
    metrics = {'rms_error_nm': float(np.sqrt(np.mean(error_nm**2))),
               'peak_error_nm': float(np.max(np.abs(error_nm))),
               'peak_input_equivalent_nm': float(np.max(np.abs(out[mask, 1]))*1e9)}
    return t, reference, out, metrics
