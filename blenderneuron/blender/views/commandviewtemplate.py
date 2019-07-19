from neuron import h

# Create a section lookup by section name
# Note: this assumes each section has a unique name
name2section = dict([(sec.name(), sec) for sec in h.allsec()])

# This will store the new section coordinates
section_coords = { }

def set_coords(sec_name):
    # Lookup the section
    nrn_section = name2section[sec_name]

    # Lookup its new coords
    new_coords = section_coords[sec_name]

    # Use 3D points as section L and diam sources
    h.pt3dconst(1, sec=nrn_section)

    # Clear the existing points - and allocate room for the incoming points
    h.pt3dclear(len(new_coords["diam"]), sec=nrn_section)

    # Use vectorization to add the points to section
    xvec = h.Vector(new_coords["x"])
    yvec = h.Vector(new_coords["y"])
    zvec = h.Vector(new_coords["z"])
    dvec = h.Vector(new_coords["diam"])

    h.pt3dadd(xvec, yvec, zvec, dvec, sec=nrn_section)

def set_all():
    for sec_name in section_coords.keys():
        set_coords(sec_name)

section_coords = {
[SECTION_COORDS]
}

set_all()