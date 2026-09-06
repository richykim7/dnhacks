from pathlib import Path
import runpy
import pytest

audit=runpy.run_path(str(Path(__file__).parents[1]/'scripts/audit_protein_apgi.py'))['apgi_counts']


def fixture(path,duplicate=False):
    values=[('Poorly differentiated',42),('Undifferentiated',4),('Well/moderately differentiated',69),('PDA',97),('Mucinous',9),('Others',9)]
    if duplicate:values.append(values[0])
    rows=''.join(f'<tr><td>{k}</td><td>{v} (10%)</td></tr>' for k,v in values)
    path.write_text('<article><table-wrap><caption>Clinical characteristics of the study cohort</caption><table>'+rows+'</table></table-wrap></article>')


def test_aggregate_ceiling_does_not_claim_individual_eligibility(tmp_path):
    path=tmp_path/'article.xml';fixture(path);result=audit(path)
    assert result['analyzed_patients']==115
    assert result['grade_pair_upper_bound']==42
    assert result['verified_eligible_pairs'] is None


def test_duplicate_categories_fail_closed(tmp_path):
    path=tmp_path/'article.xml';fixture(path,duplicate=True)
    with pytest.raises(ValueError,match='Duplicated'):audit(path)
