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
    :param pin: the GPIO pin that is driven"""
    def __init__(self, location, pin):
        self.location = location
        self.pin = pin


class UltrasonicDriver:
    """The single object driver for all the GPIO pins.

    :param targets: Transducers to be driven.
    :param focus_fn: A function which will be passed location and focal point, and will to return the required delay."""
    v_sound = 343
    frames_per_second = 1000000
    frames_per_loop = 25
    frames_high = 12

    enable_pin = 14  # "TXD"
    drive_pins = [17, 27, 22, 5, 6, 13, 19, 26, 18, 23, 24, 25, 12, 16, 20, 21]

    def __init__(self, targets, focus_fn):
        # check the targets for validity
        used_pins = set(UltrasonicDriver.drive_pins)
        for target in targets:
            if target.pin not in used_pins:
                raise ValueError("Pin is either invalid or has been used already.")
            used_pins.remove(target.pin)

        # OK
        self.targets = targets
        self.focus = (0, 0, 0.050)  # centre is 0,0 and assume we are focussing 50mm up
        self.focus_fn = focus_fn

        # wake the GPIO, initially set the enabled pin to off
        self.gpio = pigpio.pi()
        self.gpio.set_mode(UltrasonicDriver.enable_pin, pigpio.OUTPUT)
        self.gpio.write(UltrasonicDriver.enable_pin, 0)
        for pin in UltrasonicDriver.drive_pins:
            self.gpio.set_mode(pin, pigpio.OUTPUT)

        # do the thing
        self.recalculate()

    def stop(self):
        self.gpio.write(UltrasonicDriver.enable_pin, 0)
        self.gpio.wave_tx_stop()

    def recalculate(self):
        """Recalculate the wave trains and start them streaming."""
        # create up/down events just as a wishlist
        events = []
        for target in self.targets:
            # find the delay
            delay = self.focus_fn(target.location, self.focus)  # find the delay for this target
            if delay < 0:
                raise ValueError("Delay function returned a negative value")
            delay_frames = delay * UltrasonicDriver.frames_per_second  # express it in frames

            # create events of form (on/off, frame) modulo'd to the length of one loop
            events.append(SwitchEvent(target, True, delay_frames))
            events.append(SwitchEvent(target, False, (delay_frames + UltrasonicDriver.frames_high)))

        # sort the wishlist into a coherent whole
        ordered_events = sorted(events)

        # assemble a series of pulse events with null sleeps in between...
        current_frame = 0
        pulses = []
        for event in ordered_events:
            # is there a pause before this event?
            if event.frame != current_frame:
                pulses.append(pigpio.pulse(0, 0, event.frame - current_frame))
                current_frame = event.frame
            # add the event
            if event.on:
                pulses.append(pigpio.pulse(1 << event.target.pin, 0, 0))
            else:
                pulses.append(pigpio.pulse(0, 1 << event.target.pin, 0))
        # ensure the loop has the right length
        pulses.append(pigpio.pulse(0, 0, UltrasonicDriver.frames_per_loop - current_frame))

        # finally send this to the daemon that sends the waveforms
        self.gpio.wave_clear()
        self.gpio.wave_add_generic(pulses)
        this_wave = self.gpio.wave_create()
        self.gpio.wave_send_repeat(this_wave)


class SwitchEvent:
    def __init__(self, target, on, frame):
        self.target = target
        self.on = on
        self.frame = int(frame) % UltrasonicDriver.frames_per_loop

    def __lt__(self, other):
        return self.frame < other.frame

    def __repr__(self):
        return "SwitchEvent for pin %d: at %d frames, switch %s" % \
               (self.target.pin, self.frame, "on" if self.on else "off")
