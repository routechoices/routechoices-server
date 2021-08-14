import base64
import secrets
import struct
import subprocess
import requests
import numpy

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware

from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.random_strings import generate_random_string

from user_sessions.templatetags.user_sessions import device as device_name


def get_device_name(ua):
    if ua in ('Teltonika', 'Queclink'):
        return ua
    if ua.startswith('Traccar'):
        return ua
    if ua.startswith('Routechoices-ios-tracker'):
        return 'iOS'
    return device_name(ua)


def get_aware_datetime(date_str):
    ret = parse_datetime(date_str)
    if not is_aware(ret):
        ret = make_aware(ret)
    return ret


def random_key():
    rand_bytes = bytes(struct.pack('Q', secrets.randbits(64)))
    b64 = base64.b64encode(rand_bytes).decode('utf-8')
    b64 = b64[:11]
    b64 = b64.replace('+', '-')
    b64 = b64.replace('/', '_')
    return b64


def short_random_key():
    alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    return generate_random_string(alphabet, 6)


def short_random_slug():
    alphabet = '23456789abcdefghijkmnopqrstuvwxyz'
    return generate_random_string(alphabet, 6)


def get_country_from_coords(lat, lon):
    api_url = "http://api.geonames.org/countryCode"
    values = {
        'type': 'json',
        'lat': lat,
        'lng': lon,
        'username': 'rphl',
        'radius': 1
    }
    try:
        response = requests.get(api_url, params=values)
        return response.json().get('countryCode')
    except Exception:
        return None


def solve_affine_matrix(r1, s1, t1, r2, s2, t2, r3, s3, t3):
    a = (((t2 - t3) * (s1 - s2)) - ((t1 - t2) * (s2 - s3))) \
        / (((r2 - r3) * (s1 - s2)) - ((r1 - r2) * (s2 - s3)))
    b = (((t2 - t3) * (r1 - r2)) - ((t1 - t2) * (r2 - r3))) \
        / (((s2 - s3) * (r1 - r2)) - ((s1 - s2) * (r2 - r3)))
    c = t1 - (r1 * a) - (s1 * b)
    return [a, b, c]


def derive_affine_transform(a1, b1, c1, a0, b0, c0):
    e = 1e-15
    a0['x'] -= e
    a0['y'] += e
    b0['x'] += e
    b0['y'] -= e
    a1['x'] += e
    a1['y'] += e
    b1['x'] -= e
    b1['y'] -= e
    x = solve_affine_matrix(
        a0['x'], a0['y'], a1['x'],
        b0['x'], b0['y'], b1['x'],
        c0['x'], c0['y'], c1['x']
    )
    y = solve_affine_matrix(
        a0['x'], a0['y'], a1['y'],
        b0['x'], b0['y'], b1['y'],
        c0['x'], c0['y'], c1['y']
    )
    return tuple(x + y)


def three_point_calibration_to_corners(calibration_string, width, height):
    cal_pts_raw = calibration_string.split('|')
    cal_pts = [
     {
         'lon': float(cal_pts_raw[0]), 'lat': float(cal_pts_raw[1]),
         'x': float(cal_pts_raw[2]), 'y': float(cal_pts_raw[3])
     },
     {
         'lon': float(cal_pts_raw[4]), 'lat': float(cal_pts_raw[5]),
         'x': float(cal_pts_raw[6]), 'y': float(cal_pts_raw[7])
     },
     {
         'lon': float(cal_pts_raw[8]), 'lat': float(cal_pts_raw[9]),
         'x': float(cal_pts_raw[10]), 'y': float(cal_pts_raw[11])
     }
    ]
    proj = GlobalMercator()
    cal_pts_meter = [
      proj.latlon_to_meters(cal_pts[0]),
      proj.latlon_to_meters(cal_pts[1]),
      proj.latlon_to_meters(cal_pts[2])
    ]
    xy_to_coords_coeffs = derive_affine_transform(*cal_pts_meter, *cal_pts)

    def map_xy_to_latlon(xy):
        x = xy['x'] * xy_to_coords_coeffs[0] + xy['y'] \
            * xy_to_coords_coeffs[1] + xy_to_coords_coeffs[2]
        y = xy['x'] * xy_to_coords_coeffs[3] + xy['y'] \
            * xy_to_coords_coeffs[4] + xy_to_coords_coeffs[5]
        return proj.meters_to_latlon({'x': x, 'y': y})

    corners = [
      map_xy_to_latlon({'x': 0, 'y': 0}),
      map_xy_to_latlon({'x': width, 'y': 0}),
      map_xy_to_latlon({'x': width, 'y': height}),
      map_xy_to_latlon({'x': 0, 'y': height}),
    ]
    return [
        round(corners[0]['lat'], 5), round(corners[0]['lon'], 5),
        round(corners[1]['lat'], 5), round(corners[1]['lon'], 5),
        round(corners[2]['lat'], 5), round(corners[2]['lon'], 5),
        round(corners[3]['lat'], 5), round(corners[3]['lon'], 5),
    ]


def adjugate_matrix(m):
    return [
        m[4] * m[8] - m[5] * m[7], m[2] * m[7] - m[1] * m[8],
        m[1] * m[5] - m[2] * m[4],
        m[5] * m[6] - m[3] * m[8], m[0] * m[8] - m[2] * m[6],
        m[2] * m[3] - m[0] * m[5],
        m[3] * m[7] - m[4] * m[6], m[1] * m[6] - m[0] * m[7],
        m[0] * m[4] - m[1] * m[3]
    ]


def multiply_matrices(a, b):
    c = [0]*9
    for i in range(3):
        for j in range(3):
            for k in range(3):
                c[3 * i + j] += a[3 * i + k] * b[3 * k + j]
    return c


def multiply_matrix_vector(m, v):
    return [
        m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
        m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
        m[6] * v[0] + m[7] * v[1] + m[8] * v[2]
    ]


def basis_to_points(x1, y1, x2, y2, x3, y3, x4, y4):
    m = [
        x1, x2, x3,
        y1, y2, y3,
        1, 1, 1
    ]
    v = multiply_matrix_vector(adjugate_matrix(m), [x4, y4, 1])
    return multiply_matrices(m, [
        v[0], 0, 0,
        0, v[1], 0,
        0, 0, v[2]
    ])


def general_2d_projection(x1s, y1s, x1d, y1d, x2s, y2s, x2d, y2d, x3s, y3s,
                          x3d, y3d, x4s, y4s, x4d, y4d):
    s = basis_to_points(x1s, y1s, x2s, y2s, x3s, y3s, x4s, y4s)
    d = basis_to_points(x1d, y1d, x2d, y2d, x3d, y3d, x4d, y4d)
    return multiply_matrices(d, adjugate_matrix(s))


def project(m, x, y):
    v = multiply_matrix_vector(m, [x, y, 1])
    return v[0] / v[2], v[1] / v[2]


def initial_of_name(name):
    """Converts a name to initials and surname.

    Ensures all initials are capitalised, even if the
    first names aren't.

    Examples:

      >>> initial_of_name('Ram Chandra Giri')
      'R.C.Giri'
      >>> initial_of_name('Ram chandra Giri')
      'R.C.Giri'

    """
    parts = name.split()
    initials = [part[0].upper() for part in parts[:-1]]
    return '.'.join(initials + [parts[-1]])


def check_records(domain):
    if not domain:
        return
    verification_string = subprocess.Popen(["dig", "-t", "txt", domain, '+short'], stdout=subprocess.PIPE).communicate()[0]
    return ('full-speed-no-mistakes' in str(verification_string))


def find_coeffs(pa, pb):
    '''Find coefficients for perspective transformation. From http://stackoverflow.com/a/14178717/4414003.'''
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])
    A = numpy.matrix(matrix, dtype=numpy.float)
    B = numpy.array(pb).reshape(8)
    res = numpy.dot(numpy.linalg.inv(A.T * A) * A.T, B)
    return numpy.array(res).reshape(8)