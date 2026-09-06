#!/usr/bin/env python3
"""Vector rendering of the engine's architecture: corpus graph, recursive agent
sessions, acceptance gate. Drawn rather than illustrated so every element on the
cover corresponds to a real part of the system."""
from __future__ import annotations
import math, random
from deck_style import line, dot, text, rect, GREEN, AMBER, PAPER, MUTED, INK, MONO, DARKGREEN


def _tree(s, x, y, spread, depth, colour, pruned_at, path=(), out=None):
    """Recursive fork tree. Returns leaf points that reach the gate."""
    if out is None:
        out = []
    if depth == 0:
        out.append((x, y, colour))
        return out
    step = spread
    kids = [(x + 0.86, y - step), (x + 0.86, y + step)]
    for i, (kx, ky) in enumerate(kids):
        branch = path + (i,)
        dead = branch in pruned_at
        c = "3F5750" if dead else colour
        line(s, x, y, kx, ky, c, 2.4 if not dead else 1.2)
        if dead:
            dot(s, kx, ky, .035, "3F5750")
            continue
        dot(s, kx, ky, .052 if depth > 1 else .072, c)
        _tree(s, kx, ky, step * .55, depth - 1, colour, pruned_at, branch, out)
    return out


def architecture_art(s, x, y, w, h, labels=True, chaos=False):
    """Corpus graph on the left, recursive sessions in the middle, gate on the right."""
    rng = random.Random(7 if not chaos else 19)
    cx, cy = x + w * .13, y + h * .5

    # 1. the literature graph: a dense claim cloud that resolves onto a few hubs.
    #    chaos=True renders the untidier version used on the cover: more claims,
    #    uneven density and long-range links across the field.
    count = 176 if chaos else 118
    pts = []
    for _ in range(count):
        a = rng.random() * math.tau
        r = rng.uniform(.02, 1.0) ** (.42 if chaos else .55)
        jx = rng.uniform(-.035, .035) * w if chaos else 0.
        jy = rng.uniform(-.05, .05) * h if chaos else 0.
        pts.append((cx + math.cos(a) * r * w * .165 + jx, cy + math.sin(a) * r * h * .46 + jy))
    for i, a in enumerate(pts):
        near = sorted(range(len(pts)), key=lambda k: math.dist(a, pts[k]))[1:(5 if chaos else 4)]
        for k in near:
            if k > i:
                line(s, *a, *pts[k], "33453E", .55)
    if chaos:
        for _ in range(22):  # the literature does not cluster tidily
            a, b = rng.choice(pts), rng.choice(pts)
            if math.dist(a, b) > w * .06:
                line(s, *a, *b, "2B3A35", .5)
    for i, (px, py) in enumerate(pts):
        dot(s, px, py, .015 if i % 4 else .029, "5E8571")

    # hubs sit on the right edge of the cloud so the funnel never crosses it
    edge = sorted(pts, key=lambda p: -p[0])[:26]
    hubs, taken = [], []
    for px, py in edge:
        if all(abs(py - ty) > h * .12 for ty in taken):
            hubs.append((px, py)); taken.append(py)
        if len(hubs) == 4:
            break

    # 2. the funnel: the graph is what aims the agent
    root = (x + w * .385, cy)
    for px, py in hubs:
        line(s, px, py, *root, GREEN, 1.3)
    for px, py in hubs:
        dot(s, px, py, .066, INK, GREEN)
        dot(s, px, py, .030, GREEN)
    dot(s, *root, .092, GREEN)

    # 3. recursive agent sessions, with pruned branches left visible
    leaves = _tree(s, root[0], root[1], h * .225, 3, GREEN, {(0, 1), (1, 0, 0), (0, 0, 1)})

    # 4. the acceptance gate: only reviewed work crosses
    gx = x + w * .955
    line(s, gx, y + h * .06, gx, y + h * .94, AMBER, 2.2, dash=True)
    for i, (lx, ly, _) in enumerate(sorted(leaves, key=lambda p: p[1])):
        if i % 2:
            continue
        line(s, lx, ly, gx, ly, AMBER, 1.9)
        dot(s, gx, ly, .068, AMBER)

    if labels:
        for lx, t in [(x + w * .02, 'LITERATURE GRAPH'), (x + w * .40, 'RECURSIVE SESSIONS'), (x + w * .80, 'HUMAN GATE')]:
            text(s, t, lx, y + h + .06, w * .26, .24, 9.5, MUTED, True, MONO)


def session_tree(s, x, y, w, h):
    """The recursive session tree on its own: checkpoints, pruning, allocation."""
    root = (x + w * .07, y + h * .47)
    dot(s, *root, .085, GREEN)
    text(s, 'ROOT', root[0] - .30, root[1] + .16, 1.0, .24, 9.5, MUTED, True, MONO)
    leaves = _tree(s, root[0], root[1], h * .215, 3, GREEN, {(0, 1), (1, 0, 0), (0, 0, 1)})
    for i, (lx, ly, _) in enumerate(sorted(leaves, key=lambda p: p[1])):
        if i % 2 == 0:
            dot(s, lx, ly, .040, AMBER)
    ly = y + h - .10
    for j, (c, t) in enumerate([(GREEN, 'ACTIVE BRANCH'), ("3F5750", 'PRUNED'), (AMBER, 'SUBMITTED')]):
        lx = x + .10 + j * (w / 3.0)
        dot(s, lx, ly + .07, .045, c)
        text(s, t, lx + .16, ly - .02, w / 3.0 - .2, .24, 9.5, MUTED, True, MONO)
