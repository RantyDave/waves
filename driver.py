# Copyright (c) 2018 David Preece, All rights reserved.
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# http://abyz.me.uk/rpi/pigpio/python.html
# ensure the server is running

# sudo apt install pigpio
# sudo systemctl enable pigpiod.service
# sudo systemctl start pigpiod.service

# I also used raspi-config to disable lots of serial protocols - I2C, SPIO etc.
# https://www.raspberrypi.org/documentation/usage/gpio/
import pigpio


class Transducer:
    """A representation of a transducer to be driven.

    :param location: the location in metres where (0, 0) is the centre.
    :param pins: the GPIO pins to be driven"""
    def __init__(self, id, location, pins):
        self.id = id
        self.location = location
        self.pins = pins


class UltrasonicDriver:
    """The single object driver for all the GPIO pins.

    :param targets: Transducers to be driven.
    :param focus_fn: A function which will be passed location and focal point, and will to return the required delay.
    :param phase_diff_fn: A function which will be passed location and will return a phase offset as a fraction."""
    v_sound = 343
    frames_per_second = 1000000
    frames_per_loop = 25
    frames_high = 12
    frames_low = 13
    transducer_latency = 11  # a fairly arbitrary number to set a zero baseline that works

    sync_pin = 4
    drive_pins = [(17, 27), (22, 5), (6, 8), (19, 26), (18, 23), (24, 25), (7, 16), (20, 21)]

    def __init__(self, targets, focus_fn, phase_diff_fn, focus=(0, 0)):
        # check the targets for validity
        used_pins = set(UltrasonicDriver.drive_pins)
        for target in targets:
            if target.pins not in used_pins:
                raise ValueError("Pin pair is either invalid or has been used already.")
            used_pins.remove(target.pins)

        # OK
        self.targets = targets
        self.focus = focus
        self.focus_fn = focus_fn
        self.phase_diff_fn = phase_diff_fn

        # wake the GPIO
        self.gpio = pigpio.pi()
        self.gpio.set_mode(UltrasonicDriver.sync_pin, pigpio.OUTPUT)
        for pins in UltrasonicDriver.drive_pins:
            self.gpio.set_mode(pins[0], pigpio.OUTPUT)
            self.gpio.set_mode(pins[1], pigpio.OUTPUT)
        self.gpio.set_pad_strength(0, 1)  # lowering strength reduces ringing
        self.stop()  # sets pins low to start

        # do the thing
        self.recalculate()

    def stop(self):
        self.gpio.wave_tx_stop()
        for pins in UltrasonicDriver.drive_pins:
            self.gpio.write(pins[0], 0)
            self.gpio.write(pins[1], 0)

    def recalculate(self):
        """Recalculate the wave trains and start them streaming."""
        # create the trigger signal (debugging) and ensure the loop is the right length
        self.gpio.wave_clear()
        sp = UltrasonicDriver.sync_pin
        self.gpio.wave_add_generic([pigpio.pulse(1 << sp, 0, 1),
                                    pigpio.pulse(0, 1 << sp, UltrasonicDriver.frames_per_loop - 1)])

        for target in self.targets:
            # find the delay
            delay = self.focus_fn(target, self.focus)  # find the delay for this target
            delay_frames = delay * UltrasonicDriver.frames_per_second  # express it in frames

            # find the phase (fraction)
            phase = self.phase_diff_fn(target)
            delay_frames += phase * UltrasonicDriver.frames_per_loop

            # add the transducer latency
            delay_frames += UltrasonicDriver.transducer_latency

            # create events of form (on/off, frame) modulo'd to the length of one loop
            on_pulse_time = int(delay_frames) % UltrasonicDriver.frames_per_loop
            off_pulse_time = int(delay_frames + UltrasonicDriver.frames_high) % UltrasonicDriver.frames_per_loop
            on_remainder = UltrasonicDriver.frames_per_loop - (on_pulse_time + UltrasonicDriver.frames_high)
            off_remainder = UltrasonicDriver.frames_per_loop - (off_pulse_time + UltrasonicDriver.frames_low)
            if on_pulse_time < off_pulse_time:
                pulses = [pigpio.pulse(0, 1 << target.pins[0], on_pulse_time),
                          pigpio.pulse(1 << target.pins[0], 0, UltrasonicDriver.frames_high),
                          pigpio.pulse(0, 1 << target.pins[0], on_remainder),
                          ]
                invrse = [pigpio.pulse(1 << target.pins[1], 0, on_pulse_time),
                          pigpio.pulse(0, 1 << target.pins[1], UltrasonicDriver.frames_high),
                          pigpio.pulse(1 << target.pins[1], 0, on_remainder)
                          ]
            else:
                pulses = [pigpio.pulse(1 << target.pins[0], 0, off_pulse_time),
                          pigpio.pulse(0, 1 << target.pins[0], UltrasonicDriver.frames_low),
                          pigpio.pulse(1 << target.pins[0], 0, off_remainder),
                          ]
                invrse = [pigpio.pulse(0, 1 << target.pins[1], off_pulse_time),
                          pigpio.pulse(1 << target.pins[1], 0, UltrasonicDriver.frames_low),
                          pigpio.pulse(0, 1 << target.pins[1], off_remainder)
                          ]
            self.gpio.wave_add_generic(pulses)
            self.gpio.wave_add_generic(invrse)

        # finally send this to the daemon that sends the waveforms
        this_wave = self.gpio.wave_create()
        self.gpio.wave_send_repeat(this_wave)
