"""Bound display frames without changing scientific trajectories or selected geometry."""
from __future__ import annotations
from .protocol import canonical, digest
from .bundle import MAX_POINTS, validate


def display_stream(bundle: dict, *, max_bytes=20*1024*1024, max_points=MAX_POINTS) -> dict:
    """Keep first/last frames and all runs, poles, fibers and motor fields per sample.

    Sampling is temporal only and deterministic. No fiber thinning or interpolation
    can hide a pole or detach a bound motor from its source filament.
    """
    raw = canonical(bundle)
    validate(raw, scientific=True)
    source_hash = digest(raw)
    def fits(candidate, encoded):
        return len(encoded) <= max_bytes and sum(len(f['points']) for r in candidate['runs']
                for frame in r['frames'] for f in frame['filaments']) <= max_points
    if fits(bundle, raw):
        validate(raw)
        return bundle
    longest = max(len(r['frames']) for r in bundle['runs'])
    stride = 2
    while True:
        indices = [sorted(set(range(0, len(r['frames']), stride)) | {len(r['frames'])-1}) for r in bundle['runs']]
        candidate = {**bundle, 'runs': [{**run, 'frames': [run['frames'][i] for i in selected]}
                                       for run, selected in zip(bundle['runs'], indices)],
                     'display_sampling': {'schema': 'spindle_display_sampling.v1',
                         'source_trajectory_sha256': source_hash, 'method': 'saved temporal subsampling; no geometry interpolation',
                         'source_frame_counts': [len(r['frames']) for r in bundle['runs']],
                         'source_frame_indices': indices}}
        encoded = canonical(candidate)
        if fits(candidate, encoded):
            validate(encoded)
            return candidate
        if stride >= longest:
            raise ValueError('First/last frames exceed display budget; reduce declared experiment density')
        stride = min(stride * 2, longest)
