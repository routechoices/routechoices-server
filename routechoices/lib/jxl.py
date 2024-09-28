from io import BytesIO

from PIL import Image, ImageFile
from pillow_jxl import Decoder, Encoder

_VALID_JXL_MODES = {"RGB", "RGBA", "L", "LA"}


def _accept(data):
    return (
        data[:2] == b"\xff\x0a"
        or data[:12] == b"\x00\x00\x00\x0c\x4a\x58\x4c\x20\x0d\x0a\x87\x0a"
        or data[4:7] == b"JXL"
    )


class JXLImageFile(ImageFile.ImageFile):
    format = "JXL"
    format_description = "Jpeg XL image"
    __loaded = -1
    __frame = 0

    def _open(self):
        self.fc = self.fp.read()
        self._decoder = Decoder()

        self.jpeg, self._jxlinfo, self._data, icc_profile = self._decoder(self.fc)
        if self.jpeg:
            with Image.open(BytesIO(self._data)) as im:
                self._data = im.tobytes()
        self._size = (self._jxlinfo.width, self._jxlinfo.height)
        self.rawmode = self._jxlinfo.mode
        self.info["icc_profile"] = icc_profile
        self._mode = self.rawmode
        self.tile = []

    def load(self):
        if self.__loaded != self.__frame:
            if self._data is None:
                EOFError("no more frames")

            self.__loaded = self.__frame

            if self.fp and self._exclusive_fp:
                self.fp.close()
            self.fp = BytesIO(self._data)
            self.tile = [("raw", (0, 0) + self.size, 0, self.rawmode)]

        return super().load()

    # may be defined for contained formats
    def load_seek(self, pos):
        pass

    # may be defined for blocked formats (e.g. PNG)
    # def load_read(self, bytes):
    #     pass

    def tell(self):
        return self.__frame


def _save(im, fp, filename, save_all=False):
    if im.mode not in _VALID_JXL_MODES:
        raise NotImplementedError("Only RGB, RGBA, L, LA are supported.")

    info = im.encoderinfo.copy()

    # default quality is 90
    lossless = info.get("lossless", False)
    quality = 100 if lossless else info.get("quality", 90)

    decoding_speed = info.get("decoding_speed", 0)
    effort = info.get("effort", 7)
    use_container = info.get("use_container", False)
    use_original_profile = info.get("use_original_profile", False)

    enc = Encoder(
        mode=im.mode,
        lossless=lossless,
        quality=quality,
        decoding_speed=decoding_speed,
        effort=effort,
        use_container=use_container,
        use_original_profile=use_original_profile,
    )
    metadata = {
        "exif": None,
        "jumb": None,
        "xmp": None,
    }
    data = enc(im.tobytes(), im.width, im.height, jpeg_encode=False, **metadata)
    fp.write(data)


def register_jxl_opener():
    Image.register_open(JXLImageFile.format, JXLImageFile, _accept)
    Image.register_save(JXLImageFile.format, _save)
    Image.register_mime(JXLImageFile.format, "image/jxl")
    Image.register_extension(JXLImageFile.format, ".jxl")
