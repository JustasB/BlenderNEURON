import os
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase

from blenderneuron.commnode import CommNode

test_hoc_file = 'tests/TestCell.hoc'

class BlenderNEURONProcess:
    executable = None

    def __init__(self, keep=False, cmd_args=None, sleep=1):
        """
        Starts blender is a separate process. Use as `with Blender():`. Stops the process after end of `with`
        :param keep: When true, Blender process is not closed
        :param cmd_args: Any arguments to pass to the blender executable see: `blender --help` for options
        :param sleep: Number of seconds to delay further execution to allow Blender to finish initializing
        """
        self.keep = keep
        self.cmd_args = " " + (self.cmd_args if cmd_args is None else cmd_args)
        self.sleep = sleep
        self.process = Process(target=self.start_Blender)
        self.process.daemon = True

    def start_Blender(self):
        os.system(self.executable+' '+self.cmd_args) # repo root should have an installation of Blender

    def __enter__(self):
        self.process.start()
        sleep(self.sleep)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            #os.system("pkill -9 " + self.executable) # Kill Blender if it did not quit already
            # self.process.terminate()
            self.process.join()
            os.system('tset')


class Blender(BlenderNEURONProcess):
    executable = 'blender'

    # Start blender without audio support
    cmd_args = "-noaudio -p 300 200 1024 600"

    def __enter__(self):
        self.process.start()

        waited = 0
        while waited < 10:
            with CommNode("Control-Blender") as bcn:
                if bcn.client is not None and bcn.client.ping() == 1:
                    break
                else:
                    sleep(0.5)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            os.system('pkill -9 blender')
            self.process.join()

class NEURON(BlenderNEURONProcess):
    executable = "nrniv"
    cmd_args = "-python -i -c 'from blenderneuron import neuronstart'"

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            os.system('pkill -9 nrn*')
            self.process.join()
            os.system('tset')



class BlenderTestCase(TestCase):
    def in_separate_process(self, function):
        '''Run the test in separate process because there is no way to unload NEURON once it is loaded'''

        def func_with_exception(result):
            try:
                result.put([function(), None])

            except Exception as e:
                import traceback
                traceback.print_exc()
                result.put([-1, e])

        result = Queue()
        p = Process(target=func_with_exception, args=(result,))
        p.start()
        result_value, error = result.get()
        p.join()

        if error:
            raise error