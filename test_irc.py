import unittest
from pathlib import Path
import numpy as np
from irc import MODES, design, loop, measured_response, plant, response, simulate


class ControllerTests(unittest.TestCase):
    def test_modal_response_matches_independent_formula(self):
        hz = np.geomspace(1, 20000, 101)
        s = 2j*np.pi*hz
        expected = sum(n/(s*s+b*s+k) for n, b, k in MODES)
        np.testing.assert_allclose(response(plant(), hz), expected, rtol=1e-10)

    def test_physical_output_feedback_equations(self):
        hz = np.geomspace(0.1, 20000, 101)
        s = 2j*np.pi*hz; g = response(plant(), hz)
        d, kd, kt = design()
        inner = (kd/s)*g/(1-(kd/s)*(g+d))
        expected = (kt/s)*inner/(1+(kt/s)*inner)
        np.testing.assert_allclose(response(loop(plant(), 'damping'), hz), inner, rtol=1e-9)
        np.testing.assert_allclose(response(loop(plant()), hz), expected, rtol=1e-9)

    def test_internal_stability_and_tracking_dc(self):
        for f in (0.8, 1., 1.2):
            for z in (0.5, 1., 1.5):
                for mode in ('open', 'damping', 'tracking'):
                    self.assertLess(np.max(np.linalg.eigvals(loop(plant(f, z), mode).A).real), 0)
        self.assertAlmostEqual(response(loop(plant()), [0])[0].real, 1., places=10)

    def test_sensor_noise_dc_and_input_disturbance_rejection(self):
        closed = loop(plant())
        self.assertAlmostEqual(response(closed, [0], input_index=1)[0].real, 0., places=10)
        self.assertAlmostEqual(response(closed, [0], input_index=2)[0].real, -1., places=10)

    def test_timestep_convergence(self):
        system = loop(plant())
        coarse = simulate(system, sample_rate=100000)[2]
        fine = simulate(system, sample_rate=200000)[2]
        self.assertLess(np.max(np.abs(coarse[:, 0]-fine[::2, 0]))*1e9, 0.001)

    def test_repository_measurements(self):
        hz, values = measured_response(Path(__file__).parent/'platform_resp.mat')
        self.assertGreater(len(hz), 100)
        self.assertEqual(hz.shape, values.shape)
        self.assertEqual(hz[0], 0)  # The measured data includes a valid DC sample.


if __name__ == '__main__':
    unittest.main()
