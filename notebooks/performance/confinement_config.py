"""Shared, versioned setup for live review and final confinement figures."""

SETUP = {
    'version': 'tilt80-50-soma-xminus200-z10-slab100-labels-v8',
    'axis': 2,
    'slab_um': [0., 100.],
    'target_um': [0., 100.],
    'height_fractions': [0., 1.],
    'plane_size_um': 600.,
    'source_soma_center_um': [5., 0., 0.],
    'soma_center_um': [-200., 0., 10.],
    'cell_z_rotation_degrees': 80.,
    'cell_y_rotation_degrees': 50.,
    'section_pattern': '*dend*',
    'cell_rgba': [.015, .12, .55, 1.],
    'world_rgba': [1., 1., 1., 1.],
    'target_rgba': [.88, .88, .88, 1.],
    'camera_location_um': [0., -1200., 210.],
    'camera_target_um': [0., 0., 210.],
    'camera_type': 'ORTHO',
    'camera_width_um': 680.,
    'resolution': [1200, 900],
    'view_transform': 'Standard',
    'look': 'None',
    'inset_camera_location_um': [-60., 0., 1200.],
    'inset_camera_target_um': [-60., 0., 0.],
    'inset_width_um': 400.,
    'inset_resolution': [400, 400],
}


# Presentation-only changes do not invalidate the underlying 3D measurements.
FIGURE_LAYOUT = {
    'crop_top_fraction': .30,
    'crop_right_fraction': .20,
    'inset_bounds': [.16, .59, .24, .35],
}


# Shared representative conditions for the four-image comparison and final figure.
EXAMPLES = ((5, 100, 'Low flexibility'), (10, 75, 'Intermediate'),
            (15, 50, 'High flexibility'))


PANEL_SPECS = (
    ('A', 'before_confinement', 'A_baseline.png', 'Baseline'),
    ('B', 'confined_5deg_100um', 'B_5deg_100um.png', '5° / 100 µm'),
    ('C', 'confined_10deg_75um', 'C_10deg_75um.png', '10° / 75 µm'),
    ('D', 'confined_15deg_50um', 'D_15deg_50um.png', '15° / 50 µm'),
)


def cell_pose_matrix():
    """Source +X to +Z, then world Z=80°, world Y=+50°, around soma center.

    Positive Y rotation moves the upward trunk toward +X (image right).
    """
    import math
    az = math.radians(SETUP['cell_z_rotation_degrees'])
    ay = math.radians(SETUP['cell_y_rotation_degrees'])
    cz, sz, cy, sy = math.cos(az), math.sin(az), math.cos(ay), math.sin(ay)
    rotation = [[sy, -cy*sz, -cy*cz], [0., cz, -sz], [cy, sy*sz, sy*cz]]
    pivot = SETUP['source_soma_center_um']
    center = SETUP['soma_center_um']
    return [row+[center[i]-sum(row[j]*pivot[j] for j in range(3))]
            for i, row in enumerate(rotation)]+[[0., 0., 0., 1.]]


def orient_neuron_cell():
    """Apply the shared rigid starting pose to the original source morphology."""
    from neuron import h
    matrix = cell_pose_matrix()
    for sec in h.allsec():
        points = [(h.x3d(i, sec=sec), h.y3d(i, sec=sec), h.z3d(i, sec=sec), h.diam3d(i, sec=sec))
                  for i in range(int(h.n3d(sec=sec)))]
        for i, (x, y, z, diameter) in enumerate(points):
            point = (x, y, z, 1.)
            posed = [sum(row[j]*point[j] for j in range(4)) for row in matrix[:3]]
            h.pt3dchange(i, *posed, diameter, sec=sec)


def image_extent():
    """X/Z world coordinates of the fixed front orthographic image."""
    width = SETUP['camera_width_um']
    height = width * SETUP['resolution'][1] / SETUP['resolution'][0]
    x, _, z = SETUP['camera_target_um']
    return (x-width/2, x+width/2, z-height/2, z+height/2)
