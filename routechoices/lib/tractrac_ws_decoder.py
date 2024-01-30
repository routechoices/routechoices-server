import json
import ssl
import struct
from uuid import UUID

import websocket


class TracTracWSReader:
    def get_int32(self):
        d = self.result[self.offset : self.offset + 4]
        self.offset += 4
        if not d:
            return None
        return struct.unpack(">i", d)[0]

    def get_int64(self):
        d = self.result[self.offset : self.offset + 8]
        self.offset += 8
        if not d:
            return None
        return struct.unpack(">q", d)[0]

    def get_uuid(self):
        d = self.result[self.offset : self.offset + 16]
        self.offset += 16
        if not d:
            return None
        return str(UUID(bytes=d))

    def read_data(self, url):
        ws = websocket.create_connection(
            url, sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=5
        )
        comp_data = {}
        while True:
            try:
                self.result = ws.recv()
                self.offset = 0
                if not self.result:
                    continue
                message_type = self.get_int32()
                if message_type == 103:
                    i = self.get_int32()
                    ws.send(json.dumps({"type": 103, "sequenceType": i, "sequence": 0}))
                elif message_type in (18, 19):
                    while message_type in (18, 19):
                        self.get_int64()
                        ts = self.get_int64()
                        comp_id = self.get_uuid()
                        pos_longitude = self.get_int32() / 1e7
                        pos_latitude = self.get_int32() / 1e7
                        pos_timestamp = int(ts / 1e3)
                        if not comp_data.get(comp_id):
                            comp_data[comp_id] = []
                        comp_data[comp_id].append(
                            (pos_timestamp, pos_latitude, pos_longitude)
                        )
                        self.result = self.result[52 + (message_type == 19) * 8 :]
                        self.offset = 0
                        message_type = self.get_int32()

            except (KeyboardInterrupt, websocket._exceptions.WebSocketTimeoutException):
                break
        ws.close()
        return comp_data
