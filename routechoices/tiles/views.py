from django.http.response import HttpResponseBadRequest
from django.views.decorators.http import condition

from routechoices.core.models import PRIVACY_PRIVATE, Event
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import safe64encodedsha
from routechoices.lib.slippy_tiles import tile_xy_to_north_west_latlon
from routechoices.lib.streaming_response import StreamingHttpRangeResponse

GLOBAL_MERCATOR = GlobalMercator()


def common_tile(function):
    def wrap(request, *args, **kwargs):
        get_params = {}
        for key in request.GET.keys():
            get_params[key.lower()] = request.GET[key]

        http_accept = request.META.get("HTTP_ACCEPT", "")
        better_mime = None
        if "image/avif" in http_accept.split(","):
            better_mime = "image/avif"
        elif "image/webp" in http_accept.split(","):
            better_mime = "image/webp"

        asked_mime = get_params.get("format", "image/png").lower()
        if asked_mime in ("image/apng", "image/png", "image/webp", "image/avif"):
            img_mime = asked_mime
            if img_mime == "image/apng":
                img_mime = "image/png"
        elif asked_mime == "image/jpeg" and not better_mime:
            img_mime = "image/jpeg"
        elif better_mime:
            img_mime = better_mime
        else:
            return HttpResponseBadRequest("invalid image format")

        layers_raw = get_params.get("layers")
        x_raw = get_params.get("x")
        y_raw = get_params.get("y")
        z_raw = get_params.get("z")
        if not layers_raw or not x_raw or not y_raw or not z_raw:
            return HttpResponseBadRequest("missing mandatory parameters")

        out_w, out_h = 256, 256

        try:
            tile_x = int(x_raw)
            tile_y = int(y_raw)
            tile_z = int(z_raw)
        except Exception:
            return HttpResponseBadRequest("invalid tile indexes")

        max_lat, min_lon = tile_xy_to_north_west_latlon(tile_x, tile_y, tile_z)
        min_lat, max_lon = tile_xy_to_north_west_latlon(tile_x + 1, tile_y + 1, tile_z)

        min_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": min_lat, "lon": min_lon})
        min_x = min_xy["x"]
        min_y = min_xy["y"]
        max_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": max_lat, "lon": max_lon})
        max_x = max_xy["x"]
        max_y = max_xy["y"]

        try:
            if "/" in layers_raw:
                event_id, map_index = layers_raw.split("/")
                map_index = int(map_index)
                if map_index <= 0:
                    raise ValueError()
            else:
                event_id = layers_raw
                map_index = 1
        except Exception:
            return HttpResponseBadRequest("invalid parameters")

        event, raster_map = Event.get_public_map_at_index(
            request.user, event_id, map_index
        )

        request.event = event
        request.raster_map = raster_map
        request.image_request = {
            "mime": img_mime,
            "width": out_w,
            "height": out_h,
        }
        request.bound = {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        }
        return function(request, *args, **kwargs)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def tile_etag(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    key = request.raster_map.tile_cache_key(
        request.image_request["width"],
        request.image_request["height"],
        request.image_request["mime"],
        request.bound["min_x"],
        request.bound["max_x"],
        request.bound["min_y"],
        request.bound["max_y"],
    )
    return safe64encodedsha(key)


@common_tile
@condition(etag_func=tile_etag)
def serve_tile(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    data_out, cache_hit = request.raster_map.create_tile(
        request.image_request["width"],
        request.image_request["height"],
        request.image_request["mime"],
        request.bound["min_x"],
        request.bound["max_x"],
        request.bound["min_y"],
        request.bound["max_y"],
    )
    headers = {"X-Cache-Hit": cache_hit}
    if request.event.privacy == PRIVACY_PRIVATE:
        headers = {"Cache-Control": "Private"}
    return StreamingHttpRangeResponse(
        request,
        data_out,
        content_type=request.image_request["mime"],
        headers=headers,
    )
