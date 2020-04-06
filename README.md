# Phased array antenna basic simulation
## Overview
The code simulates a single-dimensional phased array by creating a transmitter thread and N array element threads for each phase shifter of the array. The phase shifters calculate the shift in degrees based on beam angle (input), transmission frequency (determines array spacing), and number of array elements. 

The phase shift is converted to a delay value and applied inside element threads on data stream.
The waveform at each element after application of phase shift is plotted real-time as the rf data is streamed from transmitter. The chosen data sample is a single period of QPSK-modulated signal.

## Inputs

 - num_elements - number of phased array elements, defaults to 3.
 - beam_angle - the desired beam direction in degrees. Defaults to 10 degrees.
 - frequency - the transmission frequency determines how far away the elements are spaced (optimal lambda/2). Defaults to 30 GHz, which is Ka-band.

## Outputs

 - Optimal array element spacing.
 - Phase shift in degrees for each element, and the corresponding delay value.
 - Real time plot of the waveform for each element after application of the delay.

## Usage
Python 2.7 interpreter only.

Inside your virtual environment:

    pip install -r requirements.txt

Running the code:

    python phased_array.py --num_elements 3 --beam_angle 0.5 --frequency 30e9
