import itertools
import io
import numpy as np
import pytest
from dnhacksbio.expression_design import load_arrays, validate_arrays, normalized_scores
from dnhacksbio.pathway_evalue import paired_randomization, score_pathway


def arrays(n=12, genes=3):
    return {'X': np.tile([[1., 2., 3.], [3., 2., 1.]], (n, 1))[:, :genes],
            'genes': np.array(['A', 'B', 'C'][:genes]),
            'sample_ids': np.array([f's{i}' for i in range(2*n)]),
            'unit_ids': np.repeat([f'u{i}' for i in range(n)], 2),
            'pair_ids': np.repeat([f'p{i}' for i in range(n)], 2),
            'condition': np.tile(['control', 'treatment'], n), 'batch': np.repeat('b1', 2*n)}


def protocol():
    return {'input_scale': 'TPM', 'assignment': 'randomized-pairs', 'assignment_justification': 'Independent fair randomization within each donor pair',
            'min_pairs': 2, 'min_targets': 2, 'direction': 1, 'exact_limit': 65536, 'seed': 42}


def test_ceiling_and_ties():
    result = paired_randomization(np.ones(12))
    assert result['p'] == 1/4096
    assert result['e'] == 63
    assert paired_randomization(np.zeros(12))['p'] == 1
    assert paired_randomization(-np.ones(12))['e'] == 0


@pytest.mark.parametrize('magnitudes', [[1, 2, 3], [0, 1, 1], [0, 0, 0], [0.01, 20, 3, 2]])
def test_full_null_orbit(magnitudes):
    results = [paired_randomization(np.array(magnitudes)*s) for s in itertools.product((-1, 1), repeat=len(magnitudes))]
    assert np.mean([r['e'] for r in results]) <= 1 + 1e-12
    for alpha in (.05, .125, .25, .5):
        assert np.mean([r['p'] <= alpha for r in results]) <= alpha


def test_mc_reproducible():
    r = paired_randomization([1, 2, 3], exact_limit=1, seed=42)
    assert r == paired_randomization([1, 2, 3], exact_limit=1, seed=42)
    assert not r['exact'] and r['p'] >= .0001
    assert r['p'] == pytest.approx(.125, abs=.02)


def test_weighted_scale_reference():
    a = arrays()
    result = score_pathway(a, protocol(), {'weights': {'A': 2., 'C': -1., 'absent': 5.}})
    assert result['effect'] == pytest.approx(3*np.log(2))
    assert result['missing_targets'] == ['absent']
    assert result['e'] == 63
    assert normalized_scores(np.array([[1, 3], [2, 6]]), 'counts')[0] == pytest.approx(np.log1p([250000, 750000]))
    assert score_pathway(a, {**protocol(), 'min_targets': 4}, {'weights': {'A': 1.}})['status'] == 'unavailable'
    assert score_pathway(a, {**protocol(), 'assignment': 'matched-only'}, {'weights': {'A': 1.}})['status'] == 'unavailable'


@pytest.mark.parametrize('field,value', [('unit_ids', ['u0']*24), ('pair_ids', ['p0']*24), ('sample_ids', ['s']*24), ('condition', ['control']*24)])
def test_invalid_identity(field, value):
    a = arrays(); a[field] = np.array(value)
    with pytest.raises(ValueError): validate_arrays(a, 'TPM')


def test_counts_and_npz():
    a = arrays(); a['X'][0, 0] = .5
    with pytest.raises(ValueError): validate_arrays(a, 'counts')
    a['X'][0, 0] = np.nan
    with pytest.raises(ValueError): validate_arrays(a, 'TPM')
    stream = io.BytesIO(); np.savez(stream, **arrays())
    loaded = load_arrays(stream.getvalue())
    assert len(validate_arrays(loaded, 'TPM')) == 12
    bad = arrays(); bad['genes'] = np.array(['A', 'B', 'C'], dtype=object)
    stream = io.BytesIO(); np.savez(stream, **bad)
    with pytest.raises(ValueError): load_arrays(stream.getvalue())


def test_decoupler_reference():
    dc = pytest.importorskip('decoupler')
    import pandas as pd
    z = normalized_scores(arrays(2)['X'], 'TPM')
    net = pd.DataFrame({'source': ['fixed']*3, 'target': ['A', 'B', 'C'], 'weight': [2., 0.5, -1.]})
    result = dc.mt.waggr(pd.DataFrame(z, columns=['A', 'B', 'C']), net, fun='wsum', times=0, tmin=1, empty=False)
    np.testing.assert_allclose(result[0].values[:, 0], z @ [2., .5, -1.], rtol=1e-6)


def test_aggregation_is_donor_level():
    from dnhacksbio.expression_design import aggregate_counts
    a = arrays(2)
    repeat = {k: np.repeat(v, 2, axis=0) if k != 'genes' else v for k, v in a.items()}
    repeat['X'] = repeat['X'].astype(int)
    repeat['sample_ids'] = np.array([f'cell{i}' for i in range(8)])
    out = aggregate_counts(**repeat, cell_types=np.repeat('CAF', 8), selected_cell_type='CAF')
    assert len(validate_arrays(out, 'counts')) == 2
    np.testing.assert_array_equal(out['X'], a['X'] * 2)
    with pytest.raises(ValueError): aggregate_counts(**repeat, cell_types=np.repeat('CAF', 8))


def test_forged_npy_shape_rejected_before_allocation():
    import zipfile
    a = arrays(2)
    stream = io.BytesIO(); np.savez(stream, **a)
    source = zipfile.ZipFile(io.BytesIO(stream.getvalue()))
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as target:
        for name in source.namelist():
            raw = source.read(name)
            if name == 'X.npy':
                header = io.BytesIO()
                np.lib.format.write_array_header_1_0(header, {'descr': '<f8', 'fortran_order': False, 'shape': (10**12, 3)})
                raw = header.getvalue() + b'0'*24
            target.writestr(name, raw)
    with pytest.raises(ValueError, match='Invalid array storage'):
        load_arrays(output.getvalue())
