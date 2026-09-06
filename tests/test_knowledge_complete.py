"""Complete graph projection retains all disconnected endpoints beyond the legacy cap."""
import hashlib

from dnhacksbio.litmap.store import KGStore
from dnhacksbio.webui import data, server


def test_complete_graph_dispatch_has_no_cap_or_status_priority(tmp_path, monkeypatch):
    path = tmp_path / 'kg.duckdb'
    store = KGStore(path)
    store.con.execute("""insert into claims (claim_id,subject_curie,subject_label,object_curie,object_label,predicate,polarity)
        select 'a-' || lpad(i::varchar,4,'0'), 'root', 'Root', 'target-' || i, 'Target ' || i, 'increases', 1
        from range(901) t(i)""")
    store.con.execute("insert into claims (claim_id,subject_curie,subject_label,object_curie,object_label,predicate,polarity) values ('z-loop','solo','Solo','solo','Solo','regulates',0)")
    store.con.execute("insert into claim_status values ('z-loop','disputed','opposite_sign')")
    store.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(data, 'kg_sources', lambda: {'fixture': path})
    handler = object.__new__(server.Handler)
    handler._send_json = lambda payload: payload
    handler._error = lambda status, message: (status, message)
    graph = handler._kg({'source':['fixture'], 'complete':['1']})
    assert graph['complete'] is True
    assert graph['shown'] == graph['matched'] == graph['total_claims'] == 902
    assert len({e['claim_id'] for e in graph['edges']}) == 902
    assert graph['loaded_entities'] == len({n['id'] for n in graph['nodes']}) == 903
    assert graph['summary']['entities'] == 903
    assert graph['edges'][0]['claim_id'] == 'a-0000'
    assert graph['edges'][-1]['claim_id'] == 'z-loop'
    assert graph['edges'][-1]['status'] == 'disputed'
    filtered = handler._kg({'source':['fixture'], 'complete':['1'], 'status':['disputed']})
    assert filtered['shown'] == filtered['matched'] == 1
    assert [n['id'] for n in filtered['nodes']] == ['solo']
    assert data.kg_graph('fixture', complete=True, q='Target 900')['shown'] == 1
    bounded = data.kg_graph('fixture', limit=800)
    assert bounded['shown'] == 800 and bounded['complete'] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
