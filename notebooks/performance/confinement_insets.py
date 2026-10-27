"""Compose scripted front/top Blender renders into print-ready inset figures.

Run on the host after render_confinement_examples.py inside Docker:
python notebooks/performance/confinement_insets.py
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from confinement_config import SETUP, PANEL_SPECS, FIGURE_LAYOUT, image_extent


def crop_main_image(image):
    height, width = image.shape[:2]
    top = round(height*FIGURE_LAYOUT['crop_top_fraction'])
    right = round(width*(1-FIGURE_LAYOUT['crop_right_fraction']))
    return image[top:, :right]


def cropped_image_extent():
    xmin, xmax, zmin, zmax = image_extent()
    return (xmin, xmin+(xmax-xmin)*(1-FIGURE_LAYOUT['crop_right_fraction']),
            zmin, zmax-(zmax-zmin)*FIGURE_LAYOUT['crop_top_fraction'])


def add_top_inset(ax, path):
    inset = ax.inset_axes(FIGURE_LAYOUT['inset_bounds'])
    half = SETUP['inset_width_um']/2
    cx, cy, _ = SETUP['inset_camera_target_um']
    inset.imshow(plt.imread(str(path)), extent=(cx-half, cx+half, cy-half, cy+half))
    inset.set_xlim(cx-half, cx+half)
    inset.set_ylim(cy-half, cy+half)
    inset.set_facecolor('white')
    inset.set_title('Top view (−Z)', fontsize=8, pad=3)
    inset.set_xticks([-100, 0, 100])
    inset.set_yticks([-100, 0, 100])
    inset.tick_params(labelsize=6, length=2, pad=1)
    inset.set_xlabel('X (µm)', fontsize=6, labelpad=1)
    inset.set_ylabel('Y (µm)', fontsize=6, labelpad=1)
    for spine in inset.spines.values():
        spine.set_color('.5')
        spine.set_linewidth(.6)
    return inset


def main():
    root = Path(__file__).resolve().parent
    directory = root/'results/confinement_panels'
    output = root/'figures/confinement_panels'
    output.mkdir(parents=True, exist_ok=True)
    records = json.loads((directory/'results.json').read_text())['records']
    if any(r.get('setup') != SETUP for r in records):
        raise ValueError('Panel measurements do not match the current setup')
    manifest = dict(setup=SETUP, layout=FIGURE_LAYOUT, seed=0, panels=[])
    for letter, name, filename, label in PANEL_SPECS:
        main_image = crop_main_image(plt.imread(str(directory/(name+'.png'))))
        height, width = main_image.shape[:2]
        fig = plt.figure(figsize=(width/100., height/100.), dpi=100, facecolor='white')
        ax = fig.add_axes([0, 0, 1, 1])
        ax.imshow(main_image)
        ax.set_axis_off()
        add_top_inset(ax, directory/(name+'_top.png'))
        fig.savefig(str(output/filename), dpi=100, facecolor='white')
        plt.close(fig)
        manifest['panels'].append(dict(panel=letter, label=label, file=filename,
            front=name+'.png', top=name+'_top.png',
            sha256=hashlib.sha256((output/filename).read_bytes()).hexdigest()))
        print('Saved', output/filename)
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
