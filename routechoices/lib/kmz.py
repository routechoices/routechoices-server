from lxml import html
from math import pi, cos, sin


class BadKMLException(Exception):
    pass


def deg2rad(deg):
    return deg * pi / 180


def compute_corners_from_kml_latlonbox(n, e, s, w, rot):
    a = (e + w) / 2
    b = (n + s) / 2
    squish = cos(deg2rad(b))
    x = squish * (e - w) / 2
    y = (n - s) / 2

    ne = (
        b + x * sin(deg2rad(rot)) + y * cos(deg2rad(rot)),
        a + (x * cos(deg2rad(rot)) - y * sin(deg2rad(rot))) / squish,
    )
    nw = (
        b - x * sin(deg2rad(rot)) + y * cos(deg2rad(rot)),
        a - (x * cos(deg2rad(rot)) + y * sin(deg2rad(rot))) / squish,
    )
    sw = (
        b - x * sin(deg2rad(rot)) - y * cos(deg2rad(rot)),
        a - (x * cos(deg2rad(rot)) - y * sin(deg2rad(rot))) / squish,
    )
    se = (
        b + x * sin(deg2rad(rot)) - y * cos(deg2rad(rot)),
        a + (x * cos(deg2rad(rot)) + y * sin(deg2rad(rot))) / squish,
    )
    return nw, ne, se, sw


def extract_ground_overlay_info(kml):
    doc = html.fromstring(kml)
    for go in doc.cssselect('GroundOverlay'):
        try:
            name = doc.cssselect('name')[0].text_content()
            href = go.cssselect('Icon href')[0].text_content()
            latlon_box = go.cssselect('LatLonBox')
            if len(latlon_box) > 0:
                north = float(latlon_box.cssselect('north')[0].text_content())
                east = float(latlon_box.cssselect('east')[0].text_content())
                south = float(latlon_box.cssselect('south')[0].text_content())
                west = float(latlon_box.cssselect('west')[0].text_content())
                rot = float(latlon_box.cssselect('rotation')[0].text_content())
                nw, ne, se, sw = compute_corners_from_kml_latlonbox(
                    north,
                    east,
                    south,
                    west,
                    rot
                )
                corners_coords = ','.join((
                    '{},{}'.format(*nw),
                    '{},{}'.format(*ne),
                    '{},{}'.format(*se),
                    '{},{}'.format(*sw),
                ))
            else:
                latlon_quad = go.cssselect('LatLonQuad')[0]
                sw, se, ne, nw = latlon_quad.cssselect('coordinates')[0] \
                    .text_content().strip().split(' ')
                nw = nw.split(',')[::-1]
                ne = ne.split(',')[::-1]
                se = se.split(',')[::-1]
                sw = sw.split(',')[::-1]
                corners_coords = ','.join((
                    '{},{}'.format(*nw),
                    '{},{}'.format(*ne),
                    '{},{}'.format(*se),
                    '{},{}'.format(*sw),
                ))
        except Exception:
            raise BadKMLException('Could not find proper GroundOverlay')

        return name, href, corners_coords
