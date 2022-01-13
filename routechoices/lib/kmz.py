from defusedxml import minidom

from routechoices.lib.helpers import compute_corners_from_kml_latlonbox


class BadKMLException(Exception):
    pass


def extract_ground_overlay_info(kml):
    doc = minidom.parseString(kml)
    for go in doc.getElementsByTagName("GroundOverlay"):
        try:
            name = doc.getElementsByTagName("name")[0].firstChild.nodeValue
            icon = go.getElementsByTagName("Icon")[0]
            href = icon.getElementsByTagName("href")[0].firstChild.nodeValue
            latlon_box_nodes = go.getElementsByTagName("LatLonBox")
            latlon_quad_nodes = go.getElementsByTagNameNS("*", "LatLonQuad")
            if len(latlon_box_nodes) > 0:
                latlon_box = latlon_box_nodes[0]
                north = float(
                    latlon_box.getElementsByTagName("north")[0].firstChild.nodeValue
                )
                east = float(
                    latlon_box.getElementsByTagName("east")[0].firstChild.nodeValue
                )
                south = float(
                    latlon_box.getElementsByTagName("south")[0].firstChild.nodeValue
                )
                west = float(
                    latlon_box.getElementsByTagName("west")[0].firstChild.nodeValue
                )
                rot = float(
                    latlon_box.getElementsByTagName("rotation")[0].firstChild.nodeValue
                )
                nw, ne, se, sw = compute_corners_from_kml_latlonbox(
                    north, east, south, west, rot
                )
                corners_coords = (
                    f"{nw[0]},{nw[1]},{ne[0]},{ne[1]},{se[0]},{se[1]},{sw[0]},{sw[1]}"
                )
            elif len(latlon_quad_nodes) > 0:
                latlon_quad = latlon_quad_nodes[0]
                sw, se, ne, nw = (
                    latlon_quad.getElementsByTagName("coordinates")[0]
                    .firstChild.nodeValue.strip()
                    .split(" ")
                )
                nw = nw.split(",")[::-1]
                ne = ne.split(",")[::-1]
                se = se.split(",")[::-1]
                sw = sw.split(",")[::-1]
                corners_coords = (
                    f"{nw[0]},{nw[1]},{ne[0]},{ne[1]},{se[0]},{se[1]},{sw[0]},{sw[1]}"
                )
            else:
                raise Exception("Invalid GroundOverlay")
        except Exception:
            raise BadKMLException("Could not find proper GroundOverlay.")
        return name, href, corners_coords
