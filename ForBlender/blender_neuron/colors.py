from mathutils import Color


def get_distinct(count, hue_start=0.5, hue_end=0.17):
    result = []
    hue_step = (hue_end-hue_start)/(count-1)
    for n in range(count):
        c = Color()
        c.hsv = (hue_start+n*hue_step, 1, 0.85)
        result.append((c.r,c.g,c.b))
    return result
