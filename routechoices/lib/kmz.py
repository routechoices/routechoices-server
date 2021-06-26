from defusedxml import minidom
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
    doc = minidom.parseString(kml)
    for go in doc.getElementsByTagName('GroundOverlay'):
        try:
            name = doc.getElementsByTagName('name')[0].firstChild.nodeValue
            icon = go.getElementsByTagName('Icon')[0]
            href = icon.getElementsByTagName('href')[0].firstChild.nodeValue
            latlon_box_nodes = go.getElementsByTagName('LatLonBox')
            latlon_quad_nodes = go.getElementsByTagNameNS('*', 'LatLonQuad')
            if len(latlon_box_nodes) > 0:
                latlon_box = latlon_box_nodes[0]
                north = float(
                    latlon_box.getElementsByTagName('north')[0].firstChild.nodeValue
                )
                east = float(
                    latlon_box.getElementsByTagName('east')[0].firstChild.nodeValue
                )
                south = float(
                    latlon_box.getElementsByTagName('south')[0].firstChild.nodeValue
                )
                west = float(
                    latlon_box.getElementsByTagName('west')[0].firstChild.nodeValue
                )
                rot = float(
                    latlon_box.getElementsByTagName('rotation')[0].firstChild.nodeValue
                )
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
            elif len(latlon_quad_nodes) > 0:
                latlon_quad = latlon_quad_nodes[0]
                sw, se, ne, nw = latlon_quad.getElementsByTagName('coordinates')[0] \
                    .firstChild.nodeValue.strip().split(' ')
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
            else:
                raise Exception('Invalid GroundOverlay')
        except Exception:
            raise BadKMLException('Could not find proper GroundOverlay.')
        return name, href, corners_coords
