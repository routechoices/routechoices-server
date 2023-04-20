from django.db.models import Prefetch
from django.http import HttpResponse
from django.http.response import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.timezone import now
from django.views.decorators.http import condition

from routechoices.core.models import (
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    Event,
    MapAssignation,
)
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import safe64encodedsha
from routechoices.lib.streaming_response import StreamingHttpRangeResponse

GLOBAL_MERCATOR = GlobalMercator()


def common_wms(function):
    def wrap(request, *args, **kwargs):
        get_params = {}
        for key in request.GET.keys():
            get_params[key.lower()] = request.GET[key]

        if get_params.get("service", "").lower() != "wms":
            return HttpResponseBadRequest("Service must be WMS")

        if get_params.get("request", "").lower() == "getmap":
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
            bbox_raw = get_params.get("bbox")
            width_raw = get_params.get("width")
            heigth_raw = get_params.get("height")
            if not layers_raw or not bbox_raw or not width_raw or not heigth_raw:
                return HttpResponseBadRequest("missing mandatory parameters")

            try:
                out_w, out_h = int(width_raw), int(heigth_raw)
            except Exception:
                return HttpResponseBadRequest("invalid size parameters")

            srs = get_params.get("srs")
            try:
                if srs in ("CRS:84", "EPSG:4326"):
                    min_lat, min_lon, max_lat, max_lon = (
                        float(x) for x in bbox_raw.split(",")
                    )
                    if srs == "EPSG:4326":
                        min_lon, min_lat, max_lon, max_lat = (
                            min_lat,
                            min_lon,
                            max_lat,
                            max_lon,
                        )
                    min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": min_lat, "lon": min_lon}
                    )
                    min_x = min_xy["x"]
                    min_y = min_xy["y"]
                    max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": max_lat, "lon": max_lon}
                    )
                    max_x = max_xy["x"]
                    max_y = max_xy["y"]
                elif srs == "EPSG:3857":
                    min_x, min_y, max_x, max_y = (float(x) for x in bbox_raw.split(","))
                else:
                    return HttpResponseBadRequest("SRS not supported")
            except Exception:
                return HttpResponseBadRequest("invalid bound parameters")

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
    if get_params.get("request", "").lower() == "getmap":
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
    return None


@common_wms
@condition(etag_func=tile_etag)
def wms_service(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    if get_params.get("request", "").lower() == "getmap":
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

    elif get_params.get("request", "").lower() == "getcapabilities":
        max_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": 89.9, "lon": 180})
        min_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": -89.9, "lon": -180})

        events = (
            Event.objects.filter(privacy=PRIVACY_PUBLIC)
            .filter(start_date__lte=now())
            .select_related("club", "map")
            .prefetch_related(
                Prefetch(
                    "map_assignations",
                    queryset=MapAssignation.objects.select_related("map"),
                )
            )
        )

        layers = []
        for event in events:
            if event.map:
                layers.append(
                    {
                        "id": event.aid,
                        "event": event,
                        "title": event.map_title if event.map_title else "Main map",
                        "map": event.map,
                    }
                )
                count_layer = 1
                for layer in event.map_assignations.all():
                    count_layer += 1
                    layers.append(
                        {
                            "id": f"{event.aid}/{count_layer}",
                            "event": event,
                            "title": layer.title,
                            "map": layer.map,
                        }
                    )
        return render(
            request,
            "wms/index.xml",
            {"layers": layers, "min_xy": min_xy, "max_xy": max_xy},
            content_type="text/xml",
        )
    return HttpResponse(status=501)
