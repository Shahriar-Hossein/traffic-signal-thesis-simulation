"""Validate FPS observations and compare their actual elapsed intervals."""
import math

MIN_COVERAGE = 0.95
ROUNDING_SEC = 0.01


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def fps_intervals(meta):
    values, bounds = meta.get('fps_windows'), meta.get('fps_window_bounds')
    result = {'intervals': [], 'errors': [], 'missing': [], 'coverage': None}
    if not isinstance(values, list) or not values:
        result['missing'].append('no FPS series')
        return result
    if any(not finite(value) or value <= 0 for value in values):
        result['errors'].append('FPS series has nonpositive or nonfinite values')
        return result
    if bounds is None or bounds == []:
        result['missing'].append('FPS window boundaries missing')
        return result
    if not isinstance(bounds, list) or len(bounds) != len(values):
        result['errors'].append('FPS boundaries do not match the series length')
        return result
    duration = meta.get('duration_sec')
    if not finite(duration) or duration <= 0:
        result['errors'].append('run duration missing or invalid')
        return result
    previous_end = 0.0
    for value, bound in zip(values, bounds):
        if (not isinstance(bound, (list, tuple)) or len(bound) != 2
                or not all(finite(item) for item in bound)):
            result['errors'].append('malformed FPS interval')
            return result
        start, end = bound
        if start < previous_end or end <= start or end > duration + ROUNDING_SEC:
            result['errors'].append('FPS intervals overlap, run backwards, or exceed the run')
            return result
        result['intervals'].append((start, end, value))
        previous_end = end
    covered = sum(end - start for start, end, _ in result['intervals'])
    result['coverage'] = covered / duration
    reported = meta.get('fps_covered_sec')
    if reported is not None and (not finite(reported)
                                or abs(reported - covered) > ROUNDING_SEC):
        result['errors'].append('reported FPS coverage contradicts interval boundaries')
    if covered + ROUNDING_SEC < MIN_COVERAGE * duration:
        result['errors'].append('FPS intervals cover less than 95% of the run')
    return result


def compare_fps(base_meta, other_meta):
    base, other = fps_intervals(base_meta), fps_intervals(other_meta)
    result = {'comparable': False, 'gaps': [], 'common_coverage': None}
    if any(item['errors'] or item['missing'] for item in (base, other)):
        return result
    horizon = min(base_meta['duration_sec'], other_meta['duration_sec'])
    i = j = 0
    covered = 0.0
    while i < len(base['intervals']) and j < len(other['intervals']):
        a, b = base['intervals'][i], other['intervals'][j]
        start, end = max(a[0], b[0]), min(a[1], b[1], horizon)
        if end > start:
            covered += end - start
            result['gaps'].append(abs(b[2] - a[2]) / a[2])
        if a[1] <= b[1]:
            i += 1
        else:
            j += 1
    result['common_coverage'] = covered / horizon
    result['comparable'] = covered + ROUNDING_SEC >= MIN_COVERAGE * horizon
    return result
