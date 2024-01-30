import struct
from uuid import UUID


class MtbDecoder:
    def __init__(self, file_pointer):
        self.device_map = {}
        self.fp = file_pointer

    def get_float(self):
        d = self.fp.read(4)
        if not d:
            return None
        return struct.unpack(">f", d)[0]

    def get_double(self):
        d = self.fp.read(8)
        if not d:
            return None
        return struct.unpack(">d", d)[0]

    def get_int16(self):
        d = self.fp.read(2)
        if not d:
            return None
        return struct.unpack(">h", d)[0]

    def get_int32(self):
        d = self.fp.read(4)
        if not d:
            return None
        return struct.unpack(">i", d)[0]

    def get_int64(self):
        d = self.fp.read(8)
        if not d:
            return None
        return struct.unpack(">q", d)[0]

    def get_uuid(self):
        d = self.fp.read(16)
        return str(UUID(bytes=d))

    def get_string_nn(self):
        string_len = self.get_int32()
        return self.fp.read(string_len)

    def skip_uuid(self):
        self.fp.read(16)

    def skip_int32(self):
        self.fp.read(4)

    def skip_int64(self):
        self.fp.read(8)

    def skip_bytes(self, n):
        self.fp.read(n)

    def decode(self):
        while True:
            self.current_size = self.get_int32()
            t = self.get_int32()
            if t == 1:
                self.read_event_latest_type()
            elif t == 2:
                self.read_event_sequence_type()
            elif t == 5:
                self.read_race_latest_type()
            elif t == 6:
                self.read_race_sequence_type()
            elif not t:
                break
            else:
                raise Exception("Bad Format")
        return self.device_map

    def read_event_latest_type(self):
        self.skip_uuid()
        t = self.get_int32()
        if t == 36:
            self.fp.read(44)
        elif t == 37:
            self.fp.read(self.current_size - 20)
        else:
            raise Exception("Bad format")

    def read_event_sequence_type(self):
        self.skip_uuid()
        t = self.get_int32()
        if t == 20:
            a = self.current_size - 36
            while a > 0:
                self.skip_int32()
                a -= 4
                e = self.fp.read(1)
                a -= 1
                if e in (b"\x01", b"\x03"):
                    self.get_int32()
                    a -= 4
                else:
                    self.get_int64()
                    a -= 8
                if e in (b"\x02", b"\x03"):
                    self.get_int32()
                    a -= 4
                else:
                    self.get_int64()
                    a -= 8
                self.skip_bytes(36)
        else:
            raise Exception("Bad Format")

    def read_race_latest_type(self):
        self.skip_bytes(32)
        t = self.get_int32()
        if t == 34:
            c = self.current_size - 36
            while c > 0:
                t = self.get_int32()
                c -= 28
                self.skip_bytes(24)
                r = (t - 24) / 24
                a = 0
                while a < r:
                    a += 1
                    self.skip_bytes(24)
                    c -= 24
        elif t == 35:
            e = self.current_size - 36
            while e > 0:
                e -= self.read_route()
        elif t == 36:
            self.skip_bytes(44)
        elif t == 37:
            self.skip_bytes(self.current_size - 36)
        elif t == 39:
            c = self.current_size - 36
            while c > 0:
                t = self.get_int32()
                c -= 28
                self.skip_bytes(24)
                i = (t - 24) / 16
                h = 0
                while h < i:
                    h += 1
                    self.skip_bytes(16)
                    c -= 16
        else:
            raise Exception("Bad Format")

    def read_route(self):
        c = 0
        s = (self.get_int32() - 24) / 16
        c += 28
        self.skip_bytes(24)
        t = 0
        while t < s:
            t += 1
            self.skip_uuid()
            c += 16
        return c

    def read_race_sequence_type(self):
        self.skip_bytes(32)
        t = self.get_int32()
        if t == 18:
            self.read_competitor_data(False)
        elif t == 19:
            self.read_competitor_data(True)
        elif t == 23:
            # sensor data aka Trash
            n = self.current_size - 36
            self.skip_bytes(32)
            n -= 32
            while n > 0:
                i = self.get_int32()
                n -= 4
                r = n
                t = self.fp.read(1)
                n -= 1
                if t in (b"\x01", b"\x03"):
                    self.get_int32()
                    n -= 4
                else:
                    self.get_int64()
                    n -= 8
                if t in (b"\x02", b"\x03"):
                    self.get_int32()
                    n -= 4
                else:
                    self.get_int64()
                    n -= 8
                self.skip_bytes(28)
                n -= 28
                h = self.get_string_nn()
                n -= len(h) + 4
                self.get_int16()
                n -= (2,)
                self.skip_bytes(i - (r - n))
                n -= i - (r - n)
        else:
            raise Exception("Bad Format")

    def read_competitor_data(self, t):
        h = self.current_size - 36
        self.fp.read(32)
        h -= 32
        while h > 0:
            self.get_int32()
            h -= 4
            s = self.fp.read(1)
            h -= 1
            if s in (b"\x01", b"\x03"):
                r = self.get_int32() + 2147483648
                h -= 4
            else:
                r = self.get_int64()
                h -= 8
            if s in (b"\x02", b"\x03"):
                a = 1e3 * (self.get_int32() + 2147483648)
                h -= 4
            else:
                a = self.get_int64()
                h -= 8
            i = self.get_uuid()
            h -= 16
            e = self.read_position(a, t)
            h -= 16
            if t:
                h -= 8
            self.add_position(i, r, e)

    def read_position(self, t, e):
        s = {
            "longitude": self.get_int32() / 1e7,
            "latitude": self.get_int32() / 1e7,
            "height": self.get_float(),
            "speed": self.get_int16() / 10,
            "direction": self.get_int16() / 10,
            "m": None,
            "timestamp": int(t / 1e3),
        }
        s["m"] = self.get_double() if e else None
        return s

    def add_position(self, id, t, p):
        self.device_map.setdefault(id, [])
        self.device_map[id].append((p["timestamp"], p["latitude"], p["longitude"]))
