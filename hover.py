import time
import math
from driver import Transducer, UltrasonicDriver


def focus_delay(transducer, focal_point):
    return 0


def phase_diff_fn(transducer):
    return 0


transducers = []
radius = 0.050
for n in range(0, 8):
    x = math.sin(math.pi * n * 0.25) * radius
    y = math.cos(math.pi * n * 0.25) * radius
    transducers.append(Transducer(n, (x, y), UltrasonicDriver.drive_pins[n]))

driver = None
try:
    driver = UltrasonicDriver(transducers, focus_delay, phase_diff_fn, (0, 0))
    time.sleep(600)
finally:
    driver.stop()
