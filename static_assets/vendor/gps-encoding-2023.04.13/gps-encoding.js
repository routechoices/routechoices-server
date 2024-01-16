/* gps-encoding.js 2023-04-13 */
// Depends on BN.js, https://github.com/indutny/bn.js
var intValCodec = (function () {
  var decodeUnsignedValueFromString = function (encoded, offset) {
      var enc_len = encoded.length,
        i = 0,
        s = 0,
        result = 0,
        b = 0x20;
      while (b >= 0x20 && i + offset < enc_len) {
        b = encoded.charCodeAt(i + offset) - 63;
        i += 1;
        if (s === 30) {
          return decodeLargeUnsignedValueFromString(encoded, offset);
        }
        result |= (b & 0x1f) << s;
        s += 5;
      }
      return [result, i];
    },
    decodeSignedValueFromString = function (encoded, offset) {
      var r = decodeUnsignedValueFromString(encoded, offset);
      if (r[2]) {
        var result = new BN(r[0], 10);
        if (result.and(new BN(1, 10)).toString() === "1") {
          return [
            parseInt(result.shrn(1).add(new BN(1)).neg().toString(), 10),
            r[1],
          ];
        } else {
          return [parseInt(result.shrn(1).toString(), 10), r[1], true];
        }
      }
      var result = r[0];
      if (result & 1) {
        return [~(result >>> 1), r[1]];
      } else {
        return [result >>> 1, r[1]];
      }
    },
    decodeLargeUnsignedValueFromString = function (encoded, offset) {
      var enc_len = encoded.length,
        i = 0,
        s = 0,
        result = new BN(0, 10),
        b = 0x20;
      while (b >= 0x20 && i + offset < enc_len) {
        b = encoded.charCodeAt(i + offset) - 63;
        i += 1;
        result = result.or(new BN(b & 0x1f, 10).shln(s));
        s += 5;
      }
      return [parseInt(result.toString(), 10), i, true];
    };
  return {
    decodeUnsignedValueFromString: decodeUnsignedValueFromString,
    decodeSignedValueFromString: decodeSignedValueFromString,
  };
})();

var Coordinates = function (lat, lon) {
  this.latitude = lat;
  this.longitude = lon;
  this.distance = function (c) {
    var C = Math.PI / 180,
      dlat = this.latitude - c.latitude,
      dlon = this.longitude - c.longitude,
      a =
        Math.sin((C * dlat) / 2) * Math.sin((C * dlat) / 2) +
        Math.cos(C * this.latitude) *
          Math.cos(C * c.latitude) *
          Math.sin((C * dlon) / 2) * Math.sin((C * dlon) / 2);
    return 12756274 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };
};

var Position = function (t, lat, lon) {
  this.timestamp = t;
  this.coords = new Coordinates(lat, lon);
  this.distance = function (p) {
    return this.coords.distance(p.coords);
  };
  this.speed = function (p) {
    return this.distance(p) / Math.abs(this.timestamp - p.timestamp);
  };
  this.positionTowardAtTimestamp = function (p, timestamp) {
    var $t = this,
      $tc = $t.coords,
      pc = p.coords,
      r = (timestamp - $t.timestamp) / (p.timestamp - $t.timestamp),
      r_ = 1 - r;
    return new Position(timestamp, Math.round((pc.latitude * r + r_ * $tc.latitude) * 1e6) / 1e6, Math.round((pc.longitude * r + r_ * $tc.longitude) * 1e6) / 1e6);
  };
};

var PositionArchive = function (k) {
  var positions = new Array(k),
    _locationOf = function (element, start, end) {
      start = typeof start !== "undefined" ? start : 0;
      end = typeof end !== "undefined" ? end : positions.length - 1;
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
      if (end - start <= 1) {
        return start + 1;
      }
      if (element.timestamp > positions[pivot].timestamp) {
        return _locationOf(element, pivot, end);
      } else {
        return _locationOf(element, start, pivot - 1);
      }
    };
  this.slice = function(start, end) {
    return (new PositionArchive(0)).setData(positions.slice(start, end));
  }
  this.setData = function(d) {
    positions = d;
    return this;
  }
  this.add = function (pos) {
    if (pos.timestamp === null) {
      return;
    }
    var index = _locationOf(pos);
    if (
      positions.length > 0 &&
      index < positions.length &&
      positions[index].timestamp === pos.timestamp
    ) {
      positions[index] = pos;
    } else if (
      positions.length > 0 &&
      index >= positions.length &&
      positions[positions.length - 1].timestamp === pos.timestamp
    ) {
      positions[positions.length - 1] = pos;
    } else {
      positions.splice(index, 0, pos);
    }
    return this;
  };

  this.push = function (pos) {
    positions.push(pos);
  };
  this.setIndex = function (i, pos) {
    positions[i]= pos;
  };
  this.setLength = function (l) {
    positions.length = l;
  };

  this.eraseInterval = function (start, end) {
    var index_s = _locationOf({ timestamp: start }),
      index_e = _locationOf({ timestamp: end });
    while (index_s > 0 && positions[index_s - 1].timestamp >= start) {
      index_s--;
    }
    while (
      index_e < positions.length - 1 &&
      positions[index_e].timestamp <= end
    ) {
      index_e++;
    }
    positions.splice(index_s, index_e - index_s + 1);
    return this;
  };
  this.getByIndex = function (i) {
    return positions[i];
  };
  this.getPositionsCount = function () {
    return positions.length;
  };
  this.getLastPosition = function() {
    return positions[positions.length - 1];
  }
  this.getArray = function () {
    return positions;
  };
  this.getByTime = function (t) {
    var index = _locationOf({ timestamp: t });
    if (index === 0) {
      return positions[0];
    }
    if (index > positions.length - 1) {
      return positions[positions.length - 1];
    }
    if (positions[index].timestamp === t) {
      return positions[index];
    } else {
      return positions[index - 1].positionTowardAtTimestamp(
        positions[index],
        t
      );
    }
  };
  this.extractInterval = function (t1, t2) {
    var index = _locationOf({ timestamp: t1 }),
      i1,
      i2,
      result,
      i1B = false,
      i2B = false;
    if (index === 0) {
      i1 = 0;
    } else if (index > positions.length - 1) {
      i1 = positions.length - 1;
    } else if (positions[index].timestamp === t1) {
      i1 = index;
    } else {
      i1B = true;
      i1 = index;
    }
    index = _locationOf({ timestamp: t2 });
    if (index === 0) {
      i2 = 0;
    } else if (index > positions.length - 1) {
      i2 = positions.length - 1;
    } else if (positions[index].timestamp === t2) {
      i2 = index;
    } else {
      i2B = true;
      i2 = index - 1;
    }

    result = this.slice(i1, i2 + 1);
    if (i1B) {
      result.add(
        positions[i1 - 1].positionTowardAtTimestamp(positions[i1], t1)
      );
    }
    if (i2B) {
      result.add(
        positions[i2].positionTowardAtTimestamp(positions[i2 + 1], t2)
      );
    }
    return result;
  };
  this.hasPointInInterval = function (t1, t2) {
    var i1 = _locationOf({ timestamp: t1 }),
      i2 = _locationOf({ timestamp: t2 });
    return i1 !== i2;
  };
  this.getDuration = function () {
    if (positions.length <= 1) {
      return 0;
    } else {
      return positions[positions.length - 1].timestamp - positions[0].timestamp;
    }
  };
  this.getAge = function (now) {
    now = now === null ? +new Date() : now;
    if (positions.length === 0) {
      return 0;
    } else {
      return now - positions[0].timestamp;
    }
  };
  this.distanceUntil = function (t) {
    var result = 0;
    if (this.getPositionsCount() === 0) {
      return 0;
    }
    var npositions = this.extractInterval(positions[0].timestamp, +t);
    var nn = npositions.getPositionsCount();
    for (var i = 0; i < nn - 1; i++) {
      result += npositions.getByIndex(i).distance(npositions.getByIndex(i + 1));
    }
    return result;
  };
};

PositionArchive.fromEncoded = function (encoded) {
  var YEAR2010 = 1262304000, // = Date.parse("2010-01-01T00:00:00Z")/1e3,
    vals = [],
    prev_vals = [YEAR2010, 0, 0],
    enc_len = encoded.length,
    pts = new PositionArchive(Math.floor(enc_len/3)),
    r,
    is_first = true,
    offset = 0,
    k = 0;

  while (offset < enc_len) {
    for (var i = 0; i < 3; i++) {
      if (i === 0) {
        if (is_first) {
          is_first = false;
          r = intValCodec.decodeSignedValueFromString(encoded, offset);
        } else {
          r = intValCodec.decodeUnsignedValueFromString(encoded, offset);
        }
      } else {
        r = intValCodec.decodeSignedValueFromString(encoded, offset);
      }
      offset += r[1];
      var new_val = prev_vals[i] + r[0];
      vals[i] = new_val;
      prev_vals[i] = new_val;
    }
    pts.setIndex(k, new Position(vals[0] * 1e3, vals[1] / 1e5, vals[2] / 1e5));
    k++;
  }
  pts.setLength(k)
  return pts;
};
