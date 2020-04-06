import pickle
import threading
import time
import logging
import math
import itertools
import Queue
from collections import deque
from matplotlib import pyplot as plt
from itertools import count
from matplotlib.animation import FuncAnimation
import argparse
plt.style.use('fivethirtyeight')

logging.basicConfig(level=logging.INFO,
                    format='(%(threadName)-9s) %(message)s' ,)

# Inputs
parser = argparse.ArgumentParser()
parser.add_argument("--num_elements", help="number of elements in the array, defaults to 3", default=3)
parser.add_argument("--beam_steering", help="angle of beam steering in degrees, defaults to 0.3 degrees", default=0.3)
parser.add_argument("--frequency", help="transmitter frequency of qpsk signal, used to determine array element spacing, default 30 Ghz for Ka band", default=30e9)
args = parser.parse_args()

BUF_SIZE = 100000 # buffer size for queues
NUM_ELEMENTS = int(args.num_elements) # how many elements in phased array
DATA_RATE = 100.0 # how many data points per second
PLOTTING_WINDOW_SIZE = 150
c = 299792458.0
FREQUENCY = float(args.frequency) # Ka band frequency
BEAM_STEERING = float(args.beam_steering) # In degrees

# Initializing queues
tx_queues = []
rx_queues = []
for i in range(NUM_ELEMENTS):
    tx_queues.append(Queue.Queue(BUF_SIZE))
    rx_queues.append(Queue.Queue(BUF_SIZE))
tx_plotting_queue = Queue.Queue(BUF_SIZE)

with open("qpsk_sample.pkl", "rb") as f:
    qpsk = pickle.load(f)

# Initializing all plotting vectors
tx_x_vals = deque([])
tx_y_vals = deque([])
rx_x_vals = [deque([]) for _ in range(NUM_ELEMENTS)]
rx_y_vals = [deque([]) for _ in range(NUM_ELEMENTS)]
tx_counts = count()
rx_counts = count()

class Transmitter():
    """
    Class for transmitter simulation, starts and terminates transmitter thread,
    sends transmission data to transmission queues
    """
    def __init__(self, waveform):
        self.waveform = waveform
        self.thread = None

    def start(self, run):
        assert run.is_set() is True
        self.thread = threading.Thread(target=self.transmit_signal, name="transmitter_thread",
                                     args=(self.waveform, 1.0 / DATA_RATE, run))
        time.sleep(3)
        self.thread.start()
        return self.thread

    def join_thread(self, run):
        assert run.is_set() is False and self.thread is not None
        self.thread.join()

    @staticmethod
    def transmit_signal(signal, sleep, run):
        for s in itertools.cycle(signal):
            if run.is_set():
                time.sleep(sleep)
                logging.debug('Transmitting signal ' + str(str(round(s, 2)) + ' to transmission queues'))
                for idx, tx_queue in enumerate(tx_queues):
                    if not tx_queue.full():
                        tx_queue.put(s)
                    else:
                        logging.warning("Transmission buffer is full, waiting...")
                        time.sleep(sleep*5)

            else:
                return


class PhasedArrayElement():
    """
    Class for a single element of the phased array, capable of generating time shift in degrees
    """
    def __init__(self, frequency, element_number):
        self.frequency = frequency
        self.wavelength = c / frequency
        self.spacing = self.wavelength / 2.0
        self.element_number = element_number
        self.thread = None

    def generate_phase_shift(self, beam_steering):
        shift = abs((360*self.spacing*math.sin(beam_steering)/self.wavelength)*self.element_number)
        while shift > 360:
            shift -= 360
        return shift

class PhasedArray():
    """
    class for the whole phased array. Starts threads of individual phased arrays, performs phase shifts
    on array elements
    """
    def __init__(self, num_elements, frequency, beam_steering):
        self.num_elements = num_elements
        self.element_range = range(num_elements)
        self.threads = []
        self.elements = []
        self.beam_steering = beam_steering
        for element_id in self.element_range:
            self.elements.append(PhasedArrayElement(frequency, element_number=element_id))
        self.spacing = self.elements[0].spacing

    def generate_phase_delays(self, period_length):
        phase_delays = []
        phase_shift_angles = []
        for element in self.elements:
            phase_shift_angle = element.generate_phase_shift(beam_steering=self.beam_steering)
            phase_delay = abs(int(phase_shift_angle*period_length/360))

            phase_delays.append(phase_delay)
            phase_shift_angles.append(phase_shift_angle)
        return phase_delays, phase_shift_angles

    def start(self, phase_delays, run):
        for element_id in self.element_range:
            thread = threading.Thread(target=self.phase_shift_signal,
                                           name="phased_array_element_" + str(element_id),
                                           args=(tx_queues[element_id], rx_queues[element_id], phase_delays[element_id], 1.0 / DATA_RATE, run))
            self.threads.append(thread)
            assert run.is_set() is True
            logging.info("Starting thread for element " + str(element_id))
            thread.start()

    def join_threads(self, run):
        assert run.is_set() is False and len(self.threads) > 0
        for thread in self.threads:
            thread.join()

    @staticmethod
    def phase_shift_signal(tx_queue, rx_queue, delay, sleep, run):
        buffer = deque([])
        while run.is_set():
            if not tx_queue.empty():
                item = tx_queue.get()
                logging.debug('Getting signal from transmitter: ' + str(item)
                              + ' : ' + str(tx_queue.qsize()) + ' values in queue')

                logging.debug("delay buffer length " + str(len(buffer)) + " : delay set to " + str(delay))
                if len(buffer) > delay:
                    logging.debug("inserting buffer[0] into receiver queue and clearing buffer")
                    rx_queue.put(buffer[0])
                    buffer.popleft()
                else:
                    buffer.append(item)
                    continue

            time.sleep(sleep)


def _crop_plotting_window(x, y):
    if len(x) > PLOTTING_WINDOW_SIZE and len(y) > PLOTTING_WINDOW_SIZE:
        x.popleft()
        y.popleft()


def _animate_rx_plotting(i):
    plt.cla()
    next_count = next(tx_counts)
    for idx, rx_queue in enumerate(rx_queues):
        s = rx_queue.get()
        rx_x_vals[idx].append(next_count)
        rx_y_vals[idx].append(s)
        if len(set([len(x) for x in rx_y_vals])) != len(set([len(x) for x in rx_x_vals])):
            continue
        _crop_plotting_window(rx_x_vals[idx], rx_y_vals[idx])
    for idx, (x, y) in enumerate(zip(rx_x_vals, rx_y_vals)):
        plt.plot(x, y, label="Element " + str(idx), linewidth=0.6)
    plt.legend(loc='upper right')
    plt.tight_layout()


if __name__ == '__main__':
    run = threading.Event()
    run.set()
    phased_array = PhasedArray(num_elements=NUM_ELEMENTS, frequency=FREQUENCY, beam_steering=BEAM_STEERING)
    logging.info("Phased array element separation (lambda/2) = " + str(round(phased_array.spacing, 5)) + " meters")

    logging.info("Generating phase delays for beam steering angle of " + str(BEAM_STEERING) + " degrees...")
    phase_delays, phase_shift_angles = phased_array.generate_phase_delays(period_length=len(qpsk))
    for i, (delay, angle) in enumerate(zip(phase_delays, phase_shift_angles)):
        logging.info("Phase shift for element " + str(i) + " is " + str(round(angle, 2)) + " degrees, translating to delay of " + str(delay) + " datapoints.")

    logging.info("Starting phased array thread")
    phased_array.start(phase_delays, run)
    time.sleep(3)
    logging.info("Starting transmitter thread")
    transmitter = Transmitter(waveform=qpsk)
    transmitter.start(run)

    logging.info("All threads started, waiting 5 seconds...")
    time.sleep(10)
    logging.info("Starting plotting...")
    try:
        plt.figure(1)
        rx_ani = FuncAnimation(plt.gcf(), _animate_rx_plotting, interval=1.0/DATA_RATE*1000)
        plt.show()
        while 1:
            time.sleep(1)
    except KeyboardInterrupt:
        run.clear()
        logging.info("Terminating array elements threads")
        phased_array.join_threads(run)
        logging.info("Terminating transmitter thread")
        transmitter.join_thread(run)
        logging.info("All threads terminated.")



