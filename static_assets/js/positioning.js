/* Positioning.js 2018-03-21 */
var intValCodec = (function() {
    var decodeUnsignedValueFromString = function (encoded) {
            var enc_len = encoded.length,
                i=0,
                shift = 0,
                result = 0,
                b = 0x20;
            while(b >= 0x20 && i<enc_len){
                  b = encoded.charCodeAt(i) - 63;
                  i += 1;
                  result |= (b & 0x1f) << shift;
                  shift += 5;
            }
            return [result, encoded.slice(i)];
        },
        decodeSignedValueFromString = function (encoded) {
            var r = decodeUnsignedValueFromString(encoded),
                result = r[0],
                left_encoded = r[1];
            if (result & 1) {
                return [~(result>>>1), left_encoded];
            } else {
                return [result>>>1, left_encoded];
            }
        },
        encodeUnsignedNumber = function (num) {
            var encoded = '';
            while (num >= 0x20) {
                encoded += String.fromCharCode((0x20 | (num & 0x1f)) + 63);
                num = num >>> 5;
            }
            encoded += String.fromCharCode((num + 63));
            return encoded;
        },
        encodeSignedNumber = function(num) {
            var sgn_num = num << 1;
            if(num < 0){
                sgn_num = ~(sgn_num);
            }
            return encodeUnsignedNumber(sgn_num);
        };
    return {
        encodeUnsignedNumber: encodeUnsignedNumber,
        encodeSignedNumber: encodeSignedNumber,
        decodeUnsignedValueFromString: decodeUnsignedValueFromString,
        decodeSignedValueFromString: decodeSignedValueFromString
    };
})();

var Coordinates = function(c){
    if (!(this instanceof Coordinates)) return new Coordinates(c);
    this.latitude = c.latitude;
    this.longitude = c.longitude;
    this.accuracy = c.accuracy;
    this.distance = function(c) {
        var C = Math.PI/180,
            dlat = this.latitude - c.latitude,
            dlon = this.longitude - c.longitude,
            a = Math.pow(Math.sin(C*dlat / 2), 2) + Math.cos(C*this.latitude) * Math.cos(C*c.latitude) * Math.pow(Math.sin(C*dlon / 2), 2);
        return 12756274 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };
    this.distanceAccuracy = function(c){
        return this.accuracy + c.accurracy;
    };
};

var Position = function(l) {
    if (!(this instanceof Position)) return new Position(l);
    this.timestamp = l.timestamp;
    this.coords = new Coordinates(l.coords);
    this.distance = function(p) {
        return this.coords.distance(p.coords);
    };
    this.distanceAccuracy = function(p) {
        return this.coords.distanceAccuracy(p.coords);
    };
    this.speed = function(p) {
        return this.distance(p) / Math.abs(this.timestamp - p.timestamp);
    };
    this.positionTowardAtTimestamp = function(p, timestamp) {
        var $t = this,
            $tc = $t.coords, pc = p.coords,
            r = (timestamp - $t.timestamp) / (p.timestamp - $t.timestamp),
            r_ = 1 - r;
        return new Position({
            timestamp: timestamp,
            coords:{
                latitude: pc.latitude * r + r_ * $tc.latitude,
                longitude: pc.longitude * r + r_ * $tc.longitude,
                accuracy: pc.accuracy * r + r_ * $tc.accuracy
            }
        });
    };
};

var PositionArchive = function(){
    if (!(this instanceof PositionArchive)) return new PositionArchive();
    var positions = [],
        _locationOf = function(element, start, end) {
            start = typeof(start) !== "undefined"? start: 0;
            end = typeof(end) !== "undefined" ? end: (positions.length-1);
            var pivot = Math.floor(start + (end - start) / 2);
            if (end - start < 0) {
                return start;
            }
            if (positions[start].timestamp >= element.timestamp) {
                return start;
            }
            if (positions[end].timestamp <= element.timestamp) {
                return end + 1;
            }
            if (positions[pivot].timestamp == element.timestamp) {
                return pivot;
            }
            if (end-start <= 1){
                return start + 1;
            }
            if (element.timestamp > positions[pivot].timestamp) {
                return _locationOf(element, pivot, end);
            } else {
                return _locationOf(element, start, pivot-1);
            }
        };
    this.add = function(pos) {
        if(pos.timestamp === null){
            return;
        }
        var index = _locationOf(pos);
        if (positions.length > 0 && index < positions.length && positions[index].timestamp === pos.timestamp) {
            positions[index] = pos;
        } else if (positions.length > 0 && index >= positions.length && positions[positions.length-1].timestamp === pos.timestamp) {
            positions[positions.length-1] = pos;
        } else {
            positions.splice(index, 0, pos);
        }
        return this;
    };
    this.eraseInterval = function(start, end){
        var index_s=_locationOf({timestamp: start}),
            index_e=_locationOf({timestamp: end});
        while (index_s>0 && positions[index_s-1].timestamp>=start) {
            index_s--;
        }
        while (index_e < positions.length-1 && positions[index_e].timestamp <= end) {
            index_e++;
        }
        positions.splice(index_s, index_e-index_s+1);
        return this;
    };
    this.getByIndex = function(i) {
        return positions[i];
    };
    this.getPositionsCount = function() {
        return positions.length;
    };
    this.getArray = function() {
        return positions;
    };
    this.getByTime = function(t) {
        var index = _locationOf({timestamp: t});
        if (index === 0) {
            return positions[0];
        }
        if (index > positions.length - 1) {
            return positions[positions.length-1];
        }
        if (positions[index].timestamp === t) {
            return positions[index];
        } else {
            return positions[index-1].positionTowardAtTimestamp(positions[index], t);
        }
    };
    this.extractInterval = function(t1, t2){
        var index=_locationOf({timestamp:t1}),
            i1, i2,
            result = new PositionArchive();
        if (index === 0) {
            i1 = 0;
        } else if (index > positions.length-1) {
            i1 = positions.length-1;
        } else if(positions[index].timestamp === t1) {
            i1 = index;
        } else {
            result.add(positions[index-1].positionTowardAtTimestamp(positions[index], t1));
            i1 = index;
        }
        index = _locationOf({timestamp: t2});
        if (index === 0) {
            i2 = 0;
        } else if(index > positions.length - 1) {
            i2 = positions.length - 1;
        } else if (positions[index].timestamp === t2) {
            i2 = index;
        } else {
            result.add(positions[index-1].positionTowardAtTimestamp(positions[index], t2));
            i2 = index - 1;
        }
        for (var i = i1; i <= i2; i++) {
            result.add(positions[i]);
        }
        return result;
    };
    this.getDuration = function() {
        if(positions.length <= 1) {
            return 0;
        } else {
            return positions[positions.length-1].timestamp-positions[0].timestamp;
        }
    };
    this.getAge = function(now) {
        now = now === null ? +new Date(): now;
        if (positions.length === 0) {
            return 0;
        } else {
            return now-positions[0].timestamp;
        }
    };
    this.exportCSV = function() {
        var raw_csv = 'timestamp, latitude, longitude, accuracy\n',
            l, lc, i;
        for (i=0;i<positions.length;i++) {
            l = positions[i];
            lc = l.coords;
            raw_csv += [l.timestamp, lc.latitude, lc.longitude, lc.accuracy].join(', ');
            raw_csv += '\n';
        }
        return raw_csv;
    };
    this.exportTks = function() {
        if (positions.length===0) {
            return '';
        }
        var YEAR2010=1262304000000, // = Date.parse("2010-01-01T00:00:00Z"),
            prev_pos = new Position({
                timestamp:YEAR2010,
                coords:{latitude:0, longitude:0, accuracy:0}
            }),
            raw="",
            mround = Math.round,
            _1e5=1e5,
            _1e3=1e3,
            k, kc, pc,
            dt, dlat, dlon,
            last_skipped_t=null, p_len = positions.length;
        for (var i = 0; i < p_len; i++) {
            k = positions[i];
            kc = k.coords;
            pc = prev_pos.coords;
            dt = k.timestamp-prev_pos.timestamp;
            dlat = kc.latitude-pc.latitude;
            dlon = kc.longitude-pc.longitude;
            if ( mround(dlat*_1e5)===0 && mround(dlon*_1e5)===0 && i!=p_len-1) {
                last_skipped_t = k.timestamp;
            } else {
                if(last_skipped_t!==null && i!=p_len-1){
                    dt = last_skipped_t-prev_pos.timestamp;
                    raw += intValCodec.encodeUnsignedNumber(mround(dt/_1e3)) +
                        intValCodec.encodeSignedNumber(0) +
                        intValCodec.encodeSignedNumber(0);
                    prev_pos.timestamp=prev_pos.timestamp+mround(dt/_1e3)*_1e3;
                    dt = k.timestamp-prev_pos.timestamp;
                    last_skipped_t=null;
                }
                raw += intValCodec.encodeUnsignedNumber(mround(dt/_1e3)) +
                    intValCodec.encodeSignedNumber(mround(dlat*_1e5)) +
                    intValCodec.encodeSignedNumber(mround(dlon*_1e5));
                prev_pos = new Position(
                {
                    timestamp: prev_pos.timestamp+mround(dt/_1e3)*_1e3,
                    coords: {
                        latitude: pc.latitude+mround(dlat*_1e5)/_1e5,
                        longitude: pc.longitude+mround(dlon*_1e5)/_1e5,
                        accuracy: 0
                    }
                });
            }
        }
        return raw;
    };
};

PositionArchive.fromTks = function(encoded) {
    var YEAR2010=1262304000000, // = Date.parse("2010-01-01T00:00:00Z"),
        vals = [],
        prev_vals = [YEAR2010/1e3, 0, 0],
        enc_len = encoded.length,
        pts = new PositionArchive(),
        r;

    while (enc_len > 0) {
        for(var i = 0; i < 3; i++) {
            if(i === 0) {
                r = intValCodec.decodeUnsignedValueFromString(encoded);
            } else {
                r = intValCodec.decodeSignedValueFromString(encoded);
            }
            vals[i] = prev_vals[i] + r[0];
            encoded = r[1];
            prev_vals[i] = prev_vals[i] + r[0];
        }
        pts.add(new Position({
            'timestamp': vals[0]*1e3,
            'coords': {'latitude':vals[1]/1e5, 'longitude': vals[2]/1e5, 'accuracy': 0}
        }));
        enc_len = encoded.length;
    }
    return pts;
};
