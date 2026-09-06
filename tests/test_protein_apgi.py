from pathlib import Path
import runpy
import pytest
import io

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


def test_embedded_projection_discards_protein_values_and_dates():
    functions=runpy.run_path(str(Path(__file__).parents[1]/'scripts/audit_protein_apgi.py'))
    text='PatientID,Grade,Histology,T_or_N,Q12345,Date of Diagnosis\na,3 - Poorly differentiated,Pancreatic Ductal Adenocarcinoma,Tumour,SECRET_PROTEIN,SECRET_DATE\na,3 - Poorly differentiated,Pancreatic Ductal Adenocarcinoma,Normal,OTHER,DATE\nb,Well/Moderate differentiation,Pancreatic Ductal Adenocarcinoma,Tumour,VALUE,DATE\n'
    rows=functions['clinical_projection'](io.StringIO(text))
    assert len(rows[0]['PatientID'])==64 and rows[0]['PatientID']!='a'
    assert 'SECRET' not in str(rows) and 'Q12345' not in str(rows)
    result=functions['embedded_counts'](rows)
    assert result['clinical_grade_pairs']==1
    assert result['unique_patients']==result['unique_tumor_patients']==2
    assert result['verified_confirmation_pairs'] is None
    with pytest.raises(ValueError,match='Repeated tumor'):
        functions['embedded_counts'](rows+[rows[0]])


def test_conflicting_same_patient_grades_rejected():
    functions=runpy.run_path(str(Path(__file__).parents[1]/'scripts/audit_protein_apgi.py'))
    rows=[{'PatientID':'a','Grade':grade,'Histology':'Pancreatic Ductal Adenocarcinoma','T_or_N':kind}
          for grade,kind in [('3 - Poorly differentiated','Tumour'),('Well/Moderate differentiation','Normal')]]
    with pytest.raises(ValueError,match='Conflicting'):
        functions['embedded_counts'](rows)
