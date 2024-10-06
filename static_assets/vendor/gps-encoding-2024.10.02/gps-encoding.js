/* gps-encoding.js 2023-04-13 */
// Depends on BN.js, https://github.com/indutny/bn.js
var intValCodec = (function () {
  var decodeUnsignedValueFromString = function (encoded, offset) {
      const enc_len = encoded.length;
      let i = 0;
      let s = 0;
      let result = 0;
      let b = 0x20;
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
      const r = decodeUnsignedValueFromString(encoded, offset);
      if (r[2]) {
        const result = new BN(r[0], 10);
        if (result.and(new BN(1, 10)).toString() === "1") {
          return [
            parseInt(result.shrn(1).add(new BN(1)).neg().toString(), 10),
            r[1],
          ];
        } else {
          return [parseInt(result.shrn(1).toString(), 10), r[1], true];
        }
      }
      const result = r[0];
      if (result & 1) {
        return [~(result >>> 1), r[1]];
      } else {
        return [result >>> 1, r[1]];
      }
    },
    decodeLargeUnsignedValueFromString = function (encoded, offset) {
      const enc_len = encoded.length;
      let i = 0;
      let s = 0;
      let result = new BN(0, 10);
      let b = 0x20;
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

const positionTowardAtTimestamp = function(a, b, timestamp) {
  const r = (timestamp - a[0]) / (b[0] - a[0]);
  const r_ = 1 - r;
  return [timestamp, b[1] * r + r_ * a[1], b[2] * r + r_ * a[2]];
}

distance = function (a, c) {
  const C = Math.PI / 180;
  const dlat = a[1] - c[1];
  const dlon = a[2] - c[2];
  const d = Math.sin((C * dlat) / 2) * Math.sin((C * dlat) / 2) + Math.cos(C * a[1]) * Math.cos(C * c[1]) * Math.sin((C * dlon) / 2) * Math.sin((C * dlon) / 2);
  return 12756274 * Math.atan2(Math.sqrt(d), Math.sqrt(1 - d));
};

const PositionArchive = function () {
  let positions = [];
  const _locationOf = function (element, start, end) {
      start = typeof start !== "undefined" ? start : 0;
      end = typeof end !== "undefined" ? end : positions.length - 1;
      const pivot = Math.floor(start + (end - start) / 2);
      if (end - start < 0) {
        return start;
      }
      if (positions[start][0] >= element) {
        return start;
      }
      if (positions[end][0] <= element) {
        return end + 1;
      }
      if (positions[pivot][0] == element) {
        return pivot;
      }
      if (end - start <= 1) {
        return start + 1;
      }
      if (element > positions[pivot][0]) {
        return _locationOf(element, pivot, end);
      } else {
        return _locationOf(element, start, pivot - 1);
      }
  };
  this.slice = function(start, end) {
    return (new PositionArchive()).setData(positions.slice(start, end));
  }
  this.setData = function(d) {
    positions = d;
    return this;
  }
  this.add = function (pos) {
    if (pos === null) {
      return;
    }
    const index = _locationOf(pos[0]);
    if (
      positions.length > 0 &&
      index < positions.length &&
      positions[index][0] === pos[0]
    ) {
      positions[index] = pos;
    } else if (
      positions.length > 0 &&
      index >= positions.length &&
      positions[positions.length - 1][0] === pos[0]
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
    positions[i] = pos;
  };
  this.setLength = function (l) {
    positions = positions.slice(0, l);
  };

  this.eraseInterval = function (start, end) {
    let indexS = _locationOf(start);
    let indexE = _locationOf(end);
    while (indexS > 0 && positions[indexS - 1][0] >= start) {
      indexS--;
    }
    while (
      indexE < positions.length - 1 &&
      positions[indexE][0] <= end
    ) {
      indexE++;
    }
    positions.splice(indexS, indexE - indexS + 1);
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
    const index = _locationOf(t);
    if (index === 0) {
      return positions[0];
    }
    if (index > positions.length - 1) {
      return positions[positions.length - 1];
    }
    if (positions[index][0] === t) {
      return positions[index];
    } else {
      return positionTowardAtTimestamp(
        positions[index - 1],
        positions[index],
        t
      );
    }
  };
  this.extractInterval = function (t1, t2) {
    let index = _locationOf(t1);
    let i1;
    let i2;
    let result;
    let i1B = false;
    let i2B = false;
    if (index === 0) {
      i1 = 0;
    } else if (index > positions.length - 1) {
      i1 = positions.length - 1;
    } else if (positions[index][0] === t1) {
      i1 = index;
    } else {
      i1B = true;
      i1 = index;
    }
    index = _locationOf(t2);
    if (index === 0) {
      i2 = 0;
    } else if (index > positions.length - 1) {
      i2 = positions.length - 1;
    } else if (positions[index][0] === t2) {
      i2 = index;
    } else {
      i2B = true;
      i2 = index - 1;
    }

    result = this.slice(i1, i2 + 1);
    if (i1B) {
      result.add(
        positionTowardAtTimestamp(
          positions[i1 - 1],
          positions[i1],
          t1
        )
      );
    }
    if (i2B) {
      result.add(
        positionTowardAtTimestamp(
          positions[i2],
          positions[i2 + 1],
          t2
        )
      );
    }
    return result;
  };
  this.hasPointInInterval = function (t1, t2) {
    const i1 = _locationOf(t1);
    const i2 = _locationOf(t2);
    return i1 !== i2;
  };
  this.getDuration = function () {
    if (positions.length <= 1) {
      return 0;
    } else {
      return positions[positions.length - 1][0] - positions[0][0];
    }
  };
  this.getAge = function (now) {
    now = now === null ? +new Date() : now;
    if (positions.length === 0) {
      return 0;
    } else {
      return now - positions[0][0];
    }
  };
  this.distanceUntil = function (t) {
    let result = 0;
    if (this.getPositionsCount() === 0) {
      return 0;
    }
    const npositions = this.extractInterval(positions[0][0], +t);
    const nn = npositions.getPositionsCount();
    for (let i = 0; i < nn - 1; i++) {
      result += distance(npositions.getByIndex(i), npositions.getByIndex(i + 1));
    }
    return result;
  };
};

PositionArchive.fromEncoded = function (encoded) {
  const YEAR2010 = 1262304000; // = Date.parse("2010-01-01T00:00:00Z")/1e3,
  const vals = [];
  const prev_vals = [YEAR2010, 0, 0];
  const enc_len = encoded.length;
  const pts = new PositionArchive();
  let r;
  let is_first = true;
  let offset = 0;

  while (offset < enc_len) {
    for (let i = 0; i < 3; i++) {
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
      const new_val = prev_vals[i] + r[0];
      vals[i] = new_val;
      prev_vals[i] = new_val;
    }
    pts.push([vals[0] * 1e3, vals[1] / 1e5, vals[2] / 1e5]);
  }
  return pts;
};
