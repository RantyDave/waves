import time
from driver import Transducer, UltrasonicDriver


def focus_delay(src_location, focal_point):
    return 0 if src_location[0] == 0 else 0.000007


transducer1 = Transducer((0, 0), 21)
transducer2 = Transducer((0.016, 0), 20)

driver = UltrasonicDriver([transducer1, transducer2], focus_delay)
time.sleep(2)
driver.stop()
