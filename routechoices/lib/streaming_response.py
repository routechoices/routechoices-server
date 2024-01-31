import os
import re
from io import BytesIO
from wsgiref.util import FileWrapper

import magic
from django.http import StreamingHttpResponse
from rest_framework import status

range_re = re.compile(r"bytes\s*=\s*(\d+)\s*-\s*(\d*)", re.I)


class RangeFileWrapper:
    def __init__(self, filelike, blksize=8192, offset=0, length=None):
        self.filelike = filelike
        self.filelike.seek(offset, os.SEEK_SET)
        self.remaining = length
        self.blksize = blksize

    def close(self):
        if hasattr(self.filelike, "close"):
            self.filelike.close()

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining is None:
            # If remaining is None, we're reading the entire file.
            data = self.filelike.read(self.blksize)
            if data:
                return data
            raise StopIteration()
        if self.remaining <= 0:
            raise StopIteration()
        data = self.filelike.read(min(self.remaining, self.blksize))
        if not data:
            raise StopIteration()
        self.remaining -= len(data)
        return data


def StreamingHttpRangeResponse(request, data, **kwargs):
    size = len(data)
    content_type = kwargs.pop("content_type", None)
    if not content_type:
        content_type = magic.from_buffer(data, mime=True) or "application/octet-stream"

    range_header = request.META.get("HTTP_RANGE", "").strip()
    range_match = range_re.match(range_header)

    if request.method == "HEAD":
        fileIO = BytesIO(b"")
    else:
        fileIO = BytesIO(data)

    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else size - 1
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1
        resp = StreamingHttpResponse(
            (
                FileWrapper(fileIO)
                if request.method == "HEAD"
                else RangeFileWrapper(fileIO, offset=first_byte, length=length)
            ),
            status=status.HTTP_206_PARTIAL_CONTENT,
            content_type=content_type,
            **kwargs,
        )
        resp["Content-Length"] = str(length)
        resp["Content-Range"] = f"bytes {first_byte}-{last_byte}/{size}"
    else:
        resp = StreamingHttpResponse(
            FileWrapper(fileIO), content_type=content_type, **kwargs
        )
        resp["Content-Length"] = str(size)
    resp["Accept-Ranges"] = "bytes"
    return resp
