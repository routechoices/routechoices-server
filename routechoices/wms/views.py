import hashlib

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import HttpResponse
from django.http.response import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.http import etag, last_modified
from django_hosts.resolvers import reverse

from routechoices.core.models import (
    PRIVACY_PRIVATE,
    PRIVACY_PUBLIC,
    Event,
    MapAssignation,
)
from routechoices.lib.globalmaptiles import GlobalMercator
from routechoices.lib.helpers import safe64encode
from routechoices.lib.streaming_response import StreamingHttpRangeResponse

GLOBAL_MERCATOR = GlobalMercator()


def common_wms(function):
    def wrap(request, *args, **kwargs):
        get_params = {}
        for key in request.GET.keys():
            get_params[key.lower()] = request.GET[key]

        if get_params.get("service") != "WMS":
            return HttpResponseBadRequest("Service must be WMS")

        if get_params.get("request") == "GetMap":
            layers_raw = get_params.get("layers")
            bbox_raw = get_params.get("bbox")
            width_raw = get_params.get("width")
            heigth_raw = get_params.get("height")

            http_accept = request.META.get("HTTP_ACCEPT", "")
            better_mime = None
            if "image/avif" in http_accept.split(","):
                better_mime = "image/avif"
            elif "image/webp" in http_accept.split(","):
                better_mime = "image/webp"

            asked_mime = get_params.get("format")
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

            if not layers_raw or not bbox_raw or not width_raw or not heigth_raw:
                return HttpResponseBadRequest("missing mandatory parameters")

            try:
                out_w, out_h = int(width_raw), int(heigth_raw)
            except Exception:
                return HttpResponseBadRequest("invalid size parameters")

            try:
                min_lon, min_lat, max_lon, max_lat = (
                    float(x) for x in bbox_raw.split(",")
                )
                srs = get_params.get("srs")
                if srs in ("CRS:84", "EPSG:4326"):
                    min_lat, min_lon, max_lat, max_lon = (
                        float(x) for x in bbox_raw.split(",")
                    )
                    if srs == "EPSG:4326":
                        min_lon, min_lat, max_lon, max_lat = (
                            float(x) for x in bbox_raw.split(",")
                        )
                    min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": min_lat, "lon": min_lon}
                    )
                    max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                        {"lat": max_lat, "lon": max_lon}
                    )
                    min_lat = min_xy["y"]
                    min_lon = min_xy["x"]
                    max_lat = max_xy["y"]
                    max_lon = max_xy["x"]
                elif srs != "EPSG:3857":
                    return HttpResponseBadRequest("SRS not supported")
            except Exception:
                return HttpResponseBadRequest("invalid bound parameters")

            try:
                if "/" in layers_raw:
                    layer_id, map_index = layers_raw.split("/")
                    map_index = int(map_index)
                    if map_index < 0:
                        raise ValueError()
                else:
                    layer_id = layers_raw
                    map_index = 0
            except Exception:
                return HttpResponseBadRequest("invalid parameters")

            event_qs = Event.objects.select_related("club")
            if map_index == 0:
                event_qs = event_qs.select_related("map")
            elif map_index > 0:
                event_qs = event_qs.prefetch_related(
                    Prefetch(
                        "map_assignations",
                        queryset=MapAssignation.objects.select_related("map"),
                    )
                )

            event = get_object_or_404(event_qs, aid=layer_id)

            if (
                not event
                or (map_index == 0 and not event.map_id)
                or (map_index > 0 and map_index > event.map_assignations.all().count())
            ):
                raise Http404

            if event.privacy == PRIVACY_PRIVATE and not request.user.is_superuser:
                if (
                    not request.user.is_authenticated
                    or not event.club.admins.filter(id=request.user.id).exists()
                ):
                    raise PermissionDenied()
            if map_index == 0:
                raster_map = event.map
            else:
                raster_map = event.map_assignations.all()[int(map_index) - 1].map
            request.event = event
            request.raster_map = raster_map
            request.image_request = {
                "mime": img_mime,
                "width": out_w,
                "height": out_h,
            }
            request.bound = {
                "min_lat": min_lat,
                "max_lat": max_lat,
                "min_lon": min_lon,
                "max_lon": max_lon,
            }
        return function(request, *args, **kwargs)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def tile_etag(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    if get_params.get("request") == "GetMap":
        etag = request.raster_map.tile_cache_key(
            request.image_request["width"],
            request.image_request["height"],
            request.bound["min_lat"],
            request.bound["max_lat"],
            request.bound["min_lon"],
            request.bound["max_lon"],
            request.image_request["mime"],
        )
        h = hashlib.sha256()
        h.update(etag.encode("utf-8"))
        return safe64encode(h.digest())
    return None


def tile_latest_modification(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    if get_params.get("request") == "GetMap":
        return max(
            request.raster_map.modification_date, request.event.modification_date
        )
    return None


@common_wms
@etag(tile_etag)
@last_modified(tile_latest_modification)
def wms_service(request):
    get_params = {}
    for key in request.GET.keys():
        get_params[key.lower()] = request.GET[key]
    if get_params.get("request") == "GetMap":
        data_out = request.raster_map.create_tile(
            request.image_request["width"],
            request.image_request["height"],
            request.bound["min_lat"],
            request.bound["max_lat"],
            request.bound["min_lon"],
            request.bound["max_lon"],
            request.image_request["mime"],
        )
        headers = None
        if request.event.privacy == PRIVACY_PRIVATE:
            headers = {"Cache-Control": "Private"}
        return StreamingHttpRangeResponse(
            request,
            data_out,
            content_type=request.image_request["mime"],
            headers=headers,
        )

    elif get_params.get("request") == "GetCapabilities":
        max_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": 89.9, "lon": 180})
        min_xy = GLOBAL_MERCATOR.latlon_to_meters({"lat": -89.9, "lon": -180})

        events = (
            Event.objects.filter(privacy=PRIVACY_PUBLIC)
            .select_related("club", "map")
            .prefetch_related("map_assignations")
        )
        layers_xml = ""

        def add_layer_xml(layer_id, event, name, layer):
            min_lon = min(
                layer.bound["topLeft"]["lon"],
                layer.bound["bottomLeft"]["lon"],
                layer.bound["bottomRight"]["lon"],
                layer.bound["topRight"]["lon"],
            )
            max_lon = max(
                layer.bound["topLeft"]["lon"],
                layer.bound["bottomLeft"]["lon"],
                layer.bound["bottomRight"]["lon"],
                layer.bound["topRight"]["lon"],
            )
            min_lat = min(
                layer.bound["topLeft"]["lat"],
                layer.bound["bottomLeft"]["lat"],
                layer.bound["bottomRight"]["lat"],
                layer.bound["topRight"]["lat"],
            )
            max_lat = max(
                layer.bound["topLeft"]["lat"],
                layer.bound["bottomLeft"]["lat"],
                layer.bound["bottomRight"]["lat"],
                layer.bound["topRight"]["lat"],
            )
            l_max_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {"lat": max_lat, "lon": max_lon}
            )
            l_min_xy = GLOBAL_MERCATOR.latlon_to_meters(
                {"lat": min_lat, "lon": min_lon}
            )
            # TODO: Use templates
            return f"""<Layer queryable="0" opaque="0" cascaded="0">
  <Name>{layer_id}</Name>
  <Title>{name} of {event.name} by {event.club}</Title>
    <SRS>EPSG:3857</SRS>
    <SRS>EPSG:4326</SRS>
    <SRS>CRS:84</SRS>
    <EX_GeographicBoundingBox>
      <westBoundLongitude>{min_lon}</westBoundLongitude>
      <eastBoundLongitude>{max_lon}</eastBoundLongitude>
      <southBoundLatitude>{min_lon}</southBoundLatitude>
      <northBoundLatitude>{max_lat}</northBoundLatitude>
    </EX_GeographicBoundingBox>
    <LatLonBoundingBox minx="{min_lat}" miny="{min_lon}" maxx="{max_lat}" maxy="{max_lon}"/>
    <BoundingBox SRS="EPSG:3857" minx="{l_min_xy['x']}" miny="{l_min_xy['y']}" maxx="{l_max_xy['x']}" maxy="{l_max_xy['y']}"/>
    <BoundingBox SRS="EPSG:4326" minx="{min_lat}" miny="{min_lon}" maxx="{max_lat}" maxy="{max_lon}"/>
    <BoundingBox SRS="CRS:84" minx="{min_lon}" miny="{min_lat}" maxx="{max_lon}" maxy="{max_lat}"/>
  </Layer>"""

        for event in events:
            if event.map:
                layers_xml += add_layer_xml(
                    event.aid,
                    event,
                    event.map_title if event.map_title else "Main map",
                    event.map,
                )
                count_layer = 0
                for layer in event.map_assignations.all():
                    count_layer += 1
                    layers_xml += add_layer_xml(
                        f"{event.aid}/{count_layer}", event, layer.title, layer.map
                    )
        data_xml = f"""<?xml version='1.0' encoding="UTF-8" standalone="no" ?>
<!DOCTYPE WMT_MS_Capabilities SYSTEM "http://schemas.opengis.net/wms/1.1.1/WMS_MS_Capabilities.dtd"
 [
 <!ELEMENT VendorSpecificCapabilities EMPTY>
 ]>  <!-- end of DOCTYPE declaration -->
<WMT_MS_Capabilities version="1.1.1">
<Service>
  <Name>OGC:WMS</Name>
  <Title>Routechoices - WMS</Title>
  <Abstract>Routechoices WMS server</Abstract>
  <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href=""/>
  <Fees>none</Fees>
  <AccessConstraints>none</AccessConstraints>
  <MaxWidth>10000</MaxWidth>
  <MaxHeight>10000</MaxHeight>
</Service>
<Capability>
  <Request>
    <GetCapabilities>
      <Format>application/vnd.ogc.wms_xml</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{reverse('wms_service', host='wms', scheme=request.scheme)}?"/></Get>
        </HTTP>
      </DCPType>
    </GetCapabilities>
    <GetMap>
      <Format>image/jpeg</Format>
      <Format>image/png</Format>
      <Format>image/avif</Format>
      <Format>image/webp</Format>
      <DCPType>
        <HTTP>
          <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="{reverse('wms_service', host='wms', scheme=request.scheme)}?"/></Get>
        </HTTP>
      </DCPType>
    </GetMap>
  </Request>
  <Exception>
    <Format>application/vnd.ogc.se_xml</Format>
  </Exception>
  <Layer>
    <Name>all</Name>
    <Title>Routechoices Maps</Title>
    <SRS>EPSG:3857</SRS>
    <SRS>EPSG:4326</SRS>
    <SRS>CRS:84</SRS>
    <EX_GeographicBoundingBox>
      <westBoundLongitude>-180</westBoundLongitude>
      <eastBoundLongitude>180</eastBoundLongitude>
      <southBoundLatitude>-90</southBoundLatitude>
      <northBoundLatitude>90</northBoundLatitude>
    </EX_GeographicBoundingBox>
    <LatLonBoundingBox minx="-180" miny="-85.0511287798" maxx="180" maxy="85.0511287798" />
    <BoundingBox SRS="EPSG:3857" minx="{min_xy['x']}" miny="{min_xy['y']}" maxx="{max_xy['x']}" maxy="{max_xy['y']}"/>
    <BoundingBox SRS="EPSG:4326" minx="-180.0" miny="-85.0511287798" maxx="180.0" maxy="85.0511287798" />
    <BoundingBox SRS="CRS:84" minx="-90" miny="-180" maxx="90" maxy="-180"/>
    {layers_xml}
  </Layer>
</Capability>
</WMT_MS_Capabilities>
"""
        return HttpResponse(data_xml, content_type="text/xml")
    return HttpResponse(status=501)
