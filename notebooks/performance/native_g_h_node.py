"""Native Blender BN-node worker: serve tasks on Blender's main thread."""
import ctypes
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from blenderneuron.blender.blendernode import BlenderNode
import render_figures_g_h as bench


def current_rss_mib():
    """Current macOS resident memory, not the process lifetime high-water mark."""
    library = ctypes.CDLL('/usr/lib/libSystem.B.dylib')
    task = ctypes.c_uint.in_dll(library, 'mach_task_self_').value
    info = (ctypes.c_uint32 * 12)()
    count = ctypes.c_uint32(12)
    status = library.task_info(task, 20, ctypes.byref(info), ctypes.byref(count))
    if status != 0:
        raise RuntimeError(f'mach_task_basic_info failed: {status}')
    return ctypes.c_uint64.from_buffer(info, 8).value / (1024 * 1024)


def measure():
    scene = bpy.context.scene
    assert scene['benchmark_camera_verified']
    assert scene.render.resolution_percentage == 100
    assert scene.eevee.taa_render_samples == 64
    assert scene.frame_end == 250
    scene.frame_set(66)
    bpy.context.view_layer.update()
    group = SimpleNamespace(activity=SimpleNamespace(
        times=range(scene['benchmark_animation_samples'])))
    result = bench.measure_render_scene(scene['benchmark_cells'],
        scene['benchmark_animation_granularity'], group, True, current_rss_mib)
    result.update(platform='native_macos', control='authenticated_BN_node',
                  source_blend=bpy.data.filepath, process_id=os.getpid(),
                  memory_api='mach_task_basic_info.resident_size')
    return result


class MainThreadNode(BlenderNode):
    def setup_server(self, service_queue=True):
        return super().setup_server(service_queue=False)


if __name__ == '__main__':
    # A private config directory avoids touching the user's open Blender node.
    node = MainThreadNode()
    bpy.types.Object.BlenderNEURON_node = node
    deadline = time.monotonic() + 900
    try:
        while time.monotonic() < deadline:
            node.work_on_queue_tasks()
            time.sleep(0.01)
    finally:
        node.stop_server()
