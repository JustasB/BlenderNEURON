"""Import a live NEURON model and render voltage activity without a display.

Blender runs this file with its own Python interpreter. model.py stays alive in
NEURON's Python interpreter; BlenderNEURON connects the two over local XML-RPC.
"""
import json
import os
import shutil
from pathlib import Path
import sys

# Official Blender distributions do not necessarily honor PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bpy
from mathutils import Vector
import blenderneuron
from blenderneuron.blender.blendernode import BlenderNode
from blenderneuron.blender.utils import COLOR_RAMP_NAME

def progress(message):
    # run.py forwards these lines to the terminal. Flush immediately because
    # Blender writes to a log file rather than an interactive terminal.
    print('[example] ' + message, flush=True)


output = Path(os.environ['BLENDERNEURON_OUTPUT_DIR'])
settings = json.loads((output / 'settings.json').read_text())

# Register the addon in this temporary Blender session. Its GUI startup handler
# is unnecessary here: this script creates and controls the node explicitly.
progress('Blender started. Registering BlenderNEURON and connecting to NEURON...')
blenderneuron.register()
if blenderneuron.auto_start in bpy.app.handlers.depsgraph_update_post:
    bpy.app.handlers.depsgraph_update_post.remove(blenderneuron.auto_start)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Rendering and scene changes happen on Blender's main thread. There is no GUI
# event loop, so do not start a background thread to service Blender commands.
class HeadlessNode(BlenderNode):
    def setup_server(self, service_queue=True):
        super().setup_server(service_queue=False)


node = HeadlessNode()
bpy.types.Object.BlenderNEURON_node = node
try:
    if node.client is None:
        raise RuntimeError('Could not connect to the running NEURON model')
    scene = bpy.context.scene
    scene.BlenderNEURON.simulator_settings.from_neuron()
    # Thirty milliseconds fill the animation. More frames increase temporal
    # resolution without changing the underlying simulation or recording rate.
    scene.BlenderNEURON.simulator_settings.frames_per_ms = (settings['frames'] - 1) / 30
    group = node.add_group('Three cells')
    group.record_activity = True
    group.recording_granularity = 'Section'
    group.recording_period = 0.1  # milliseconds; independent of rendered FPS
    group.interaction_granularity = 'Cell'
    group.animation_range_low = -80
    group.animation_range_high = 40
    group.animate_brightness = True
    group.max_brightness = 3
    group.default_brightness = 1
    ramp = group.color_ramp_material.node_tree.nodes[COLOR_RAMP_NAME].color_ramp
    ramp.elements[0].color = (0.015, 0.06, 0.5, 1)
    ramp.elements[1].color = (1, 0.12, 0.01, 1)

    # This live request sends the recording settings to NEURON, runs its model,
    # and receives morphology plus recorded voltages. No offline import is used.
    progress('Connected. Running the 30 ms simulation and transferring morphology and voltage...')
    node.import_groups_from_neuron([group])
    node.display_groups()

    # Save the received data for inspection. Check each soma really spiked so
    # an empty animation cannot be mistaken for a successful demonstration.
    payload = group.to_dict(include_activity=True, include_root_children=True,
                            include_coords_and_radii=True)
    (output / 'activity.json').write_text(json.dumps(payload))
    peaks = {root.name: max(root.activity.values) for root in group.roots.values()}
    if len(peaks) != 3 or any(peak <= 0 for peak in peaks.values()):
        raise RuntimeError('Expected an action potential above 0 mV in each soma: %r' % peaks)

    progress('Live transfer complete. All three cells spiked (soma peaks: %s mV).' %
             ', '.join('%.1f' % peak for peak in peaks.values()))
    progress('Setting up the orthographic camera, voltage colors, and neon glare...')

    # All cells lie in XY. Look directly down Z with an orthographic camera,
    # framing the combined geometry with a margin on every side. Compute bounds
    # before adding labels so changing the model still gives sensible framing.
    bpy.context.view_layer.update()
    objects = [obj for obj in scene.objects if obj.type in {'CURVE', 'MESH'}]
    if not objects:
        raise RuntimeError('The live import produced no cell geometry')
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    lower = Vector(tuple(min(p[i] for p in corners) for i in range(3)))
    upper = Vector(tuple(max(p[i] for p in corners) for i in range(3)))
    center = (lower + upper) / 2
    aspect = settings['width'] / settings['height']
    # Blender's orthographic scale describes the width for landscape images,
    # and the height for portrait images. Fit both axes, with room for captions.
    span_x, span_y = upper.x - lower.x, upper.y - lower.y
    scale = max(span_x, span_y * aspect) if aspect >= 1 else max(span_y, span_x / aspect)
    camera_data = bpy.data.cameras.new('Camera')
    camera = bpy.data.objects.new('Camera', camera_data)
    scene.collection.objects.link(camera)
    camera.location = (center.x, center.y, upper.z + 500)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = scale * 1.4
    camera_data.clip_end = 2000
    scene.camera = camera  # zero rotation looks along local -Z, with +Y up

    # Emission materials make voltage colors visible without placing lights.
    # Cycles on CPU works with neither a GPU nor an X/VNC display server.
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = settings['samples']
    scene.cycles.use_denoising = False
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    # Use the addon's built-in compositor setup, just as its UI button does.
    # This glare filter is saved in the .blend along with the camera.
    bpy.ops.blenderneuron.add_neon_effect()
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = settings['width']
    scene.render.resolution_y = settings['height']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.fps = settings['fps']
    scene.frame_start, scene.frame_end = 0, settings['frames'] - 1

    # A small caption gives simulation time and a voltage key in every frame.
    # Text faces +Z, toward the camera; it sits above the cell geometry.
    text_material = bpy.data.materials.new('Caption')
    text_material.use_nodes = True
    nodes = text_material.node_tree.nodes
    nodes.clear()
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1)
    # Stay below the neon filter's threshold so letters do not grow streaks.
    emission.inputs['Strength'].default_value = 0.1
    surface = nodes.new('ShaderNodeOutputMaterial')
    text_material.node_tree.links.new(emission.outputs[0], surface.inputs['Surface'])
    vertical_span = camera_data.ortho_scale / aspect if aspect >= 1 else camera_data.ortho_scale
    horizontal_span = vertical_span * aspect
    font = bpy.data.curves.new('Caption', 'FONT')
    font.size = min(horizontal_span / 32, vertical_span / 12)
    caption = bpy.data.objects.new('Caption', font)
    scene.collection.objects.link(caption)
    caption.location = (center.x - horizontal_span * 0.46, center.y - vertical_span * 0.38, upper.z + 10)
    font.materials.append(text_material)

    def update_caption(frame):
        # Match the voltage animation's frame-to-time mapping. Movie FPS only
        # changes playback speed; this label always shows simulation time.
        milliseconds = frame * 30 / (settings['frames'] - 1)
        font.body = 't = %.1f ms\nVoltage: blue -80 / red +40 mV' % milliseconds

    update_caption(0)
    scene.frame_set(0)
    # The imported materials have baked color/brightness keyframes, so the
    # saved scene can be scrubbed without a running NEURON process. Open in
    # camera view, with material colors visible even in the solid viewport.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.color_type = 'MATERIAL'
    scene.render.filepath = '//frames/frame_'
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'scene.blend'))
    progress('Saved scene.blend. Rendering %d frames on CPU...' % settings['frames'])
    frames = output / 'frames'
    frames.mkdir()
    for frame in range(settings['frames']):
        scene.frame_set(frame)
        update_caption(frame)
        # Number PNGs from 1 to match the movie's image sequence.
        scene.render.filepath = str(frames / ('frame_%04d.png' % (frame + 1)))
        bpy.ops.render.render(write_still=True)
        # Report about ten milestones, plus the first and last frame.
        completed = frame + 1
        interval = max(1, settings['frames'] // 10)
        if completed == 1 or completed % interval == 0 or completed == settings['frames']:
            progress('Rendered frame %d/%d (%d%%).' %
                     (completed, settings['frames'], completed * 100 / settings['frames']))
    # Pick the frame nearest the first soma's voltage peak for a useful preview.
    # This is copied from the animation so preview and movie use identical settings.
    first = next(iter(group.roots.values()))
    peak_index = max(range(len(first.activity.values)), key=lambda i: first.activity.values[i])
    peak_time = first.activity.times[peak_index]
    preview_frame = min(settings['frames'] - 1, max(0, round(peak_time * (settings['frames'] - 1) / 30)))
    shutil.copyfile(frames / ('frame_%04d.png' % (preview_frame + 1)), output / 'preview.png')

    progress('Saved preview.png. Encoding activity.mp4 from the rendered frames...')

    # Blender's video sequencer can encode the PNGs itself. Reuse the existing
    # runtime image: no separate ffmpeg executable or tutorial image is needed.
    # This second scene contains only an image strip, so it does not rerender
    # the cells. Keep the original saved scene focused on the editable model.
    movie = bpy.data.scenes.new('Movie encoding')
    editor = movie.sequence_editor_create()
    strips = editor.strips if hasattr(editor, 'strips') else editor.sequences
    strip = strips.new_image('Rendered frames', str(frames / 'frame_0001.png'),
                             channel=1, frame_start=1)
    for frame in range(2, settings['frames'] + 1):
        strip.elements.append('frame_%04d.png' % frame)
    movie.frame_start, movie.frame_end = 1, settings['frames']
    movie.render.resolution_x = settings['width']
    movie.render.resolution_y = settings['height']
    movie.render.resolution_percentage = 100
    movie.render.fps = settings['fps']
    movie.render.image_settings.file_format = 'FFMPEG'
    movie.render.ffmpeg.format = 'MPEG4'
    movie.render.ffmpeg.codec = 'H264'
    movie.render.filepath = str(output / 'activity.mp4')
    bpy.ops.render.render(animation=True, scene=movie.name)
    summary = {'soma_peak_mV': peaks, 'blender_version': bpy.app.version_string,
               'frames': settings['frames'], 'simulation_duration_ms': 30,
               'transfer': 'live XML-RPC', 'render_engine': 'Cycles CPU'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))
    progress('Video encoding complete. Saved activity.mp4 and summary.json.')
finally:
    node.stop_server()
