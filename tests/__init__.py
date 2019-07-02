import os
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase

test_hoc_file = 'tests/TestCell.hoc'


class Blender:
    def __init__(self, keep=False, cmd_args=None, sleep=1):
        """
        Starts blender is a separate process. Use as `with Blender():`. Stops the process after end of `with`
        :param keep: When true, Blender process is not closed
        :param cmd_args: Any arguments to pass to the blender executable see: `blender --help` for options
        :param sleep: Number of seconds to delay further execution to allow Blender to finish initializing
        """
        self.keep = keep
        self.cmd_args = " " + ("" if cmd_args is None else cmd_args)
        self.sleep = sleep
        self.blender = Process(target=self.start_Blender)

    def start_Blender(self):
        os.system("blender/blender"+self.cmd_args) # repo root should have an installation of Blender

    def __enter__(self):
        self.blender.start()
        sleep(self.sleep)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            os.system("pkill -9 blender") # This is a crude but potent way of stopping Blender
            self.blender.join()


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
        p = Process(target=func_with_exception, args=(result,));
        p.start();
        result_value, error = result.get()
        p.join();

        if error:
            raise error