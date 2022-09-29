L.Util.extend(L.LineUtil, {
  // Checks to see if two line segments intersect. Does not handle degenerate cases.
  // http://compgeom.cs.uiuc.edu/~jeffe/teaching/373/notes/x06-sweepline.pdf
  segmentsIntersect: function (p, p1, p2, p3) {
    return (
      this._checkCounterclockwise(p, p2, p3) !==
        this._checkCounterclockwise(p1, p2, p3) &&
      this._checkCounterclockwise(p, p1, p2) !==
        this._checkCounterclockwise(p, p1, p3)
    );
  },
  // check to see if points are in counterclockwise order
  _checkCounterclockwise: function (p, p1, p2) {
    return (p2.y - p.y) * (p1.x - p.x) > (p1.y - p.y) * (p2.x - p.x);
  },
});
