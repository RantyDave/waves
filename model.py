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

import numpy as np
import math


class VoxelData:
    def __init__(self, size, scale):
        """Create voxel data.

        :param size: A (x, y, z) tuple of raw data size.
        :param scale: A scalar describing the size of each voxel cube."""
        self.data = np.empty(size, dtype=np.float32)
        self.size = size
        self.scale = scale

    def real_world_coords(self, x, y, z):
        """Return real world coordinates for an (x, y, z) tuple.

        :param voxel_coord: an x, y, z for the required location.
        :return: an x, y, z in real world coordinates."""
        return x * self.scale, y * self.scale, z * self.scale

    def fill_from(self, funcs):
        """Fill the voxel data with sum of results from a collection of functions.

        :param funcs: a list of functions to call with real world coordinates - ((x, y, z)) -> float"""
        for z in range(0, self.size[2]):
            for y in range(0, self.size[1]):
                for x in range(0, self.size[0]):
                    passed_coords = self.real_world_coords(x, y, z)
                    result = 0
                    for func in funcs:
                        result += func(passed_coords)
                    self.data[z, y, x] = result

    def save(self, filename):
        """Save the data in raw voxel format.

        :param filename: Name of the file, will append the extension.

        Your best bet with this is to open it in Paraview (https://www.paraview.org/) and...
        * confirm that it is raw
        * set it as float data that's little endian
        * there's only one channel (pressure)
        * and the extents are 0-63 in all three directions.

        Add a contour and create isosurfaces at (say) 0.02 (i.e. 2% additional pressure over atmospheric)."""
        with open(filename + '.raw', 'wb') as f:
            self.data.tofile(f)


class PixelData:
    z_plane = 0.04

    def __init__(self, size, scale):
        self.data = np.empty(size, dtype=np.float32)
        self.size = size
        self.scale = scale

    def real_world_coords(self, x, y):
        return x * self.scale, y * self.scale, PixelData.z_plane

    def fill_from(self, funcs):
        for y in range(0, self.size[1]):
            for x in range(0, self.size[0]):
                passed_coords = self.real_world_coords(x, y)
                result = 0
                for func in funcs:
                    result += func(passed_coords)
                self.data[y, x] = result

    def save(self, filename):
        with open(filename + '.raw', 'wb') as f:
            self.data.tofile(f)


class SoundPressureField:
    v_sound = 343.0
    max_pressure = 0.2
    min_pressure = -0.2

    def __init__(self, location, frequency, amplitude):
        """A function representing a sound pressure field created by a sinusoidal wave.

        :param location: an (x, y, z) tuple representing the centre of the field in metres.
        :param frequency: the frequency.
        :param amplitude: a scalar pressure relative to atmosphere."""
        self.location = np.array(location, dtype=np.float32)
        self.duration = 1.0 / frequency
        self.wavelength = self.duration * SoundPressureField.v_sound
        self.amplitude = amplitude

    def pressure_at(self, coords):
        """Return the sound pressure level at this location, clamped to +-20%.

        :param coords: (x, y, z) coords of the location relative to the origin in metres."""
        diff = coords - self.location
        distance_squared = diff[0] * diff[0] + diff[1] * diff[1] + diff[2] * diff[2]
        distance = math.sqrt(distance_squared)

        # bail out now if we're going to have a division by zero
        if distance_squared == 0:
            return SoundPressureField.max_pressure

        # calculate phase difference due to distance (in radians)
        phase = (distance / self.wavelength) * 2 * math.pi
        rtn = (math.sin(phase) * (self.amplitude / distance_squared))
        return max(SoundPressureField.min_pressure, min(rtn, SoundPressureField.max_pressure))


# actual thing is 0.064m across, we're using 0.001m voxels
# voxels = VoxelData((64, 64, 64), scale=0.001)
pixels = PixelData((64, 64), scale=0.001)

pressure_fields = list()
for x in range(0, 4):
    for y in range(0, 4):
        pressure_fields.append(SoundPressureField((0.008 + x*0.016, 0.008 + y*0.016, 0), 40000, 0.00001))

functions = list()
for field in pressure_fields:
    functions.append(field.pressure_at)

pixels.fill_from(functions)
pixels.save('pressure_field')
