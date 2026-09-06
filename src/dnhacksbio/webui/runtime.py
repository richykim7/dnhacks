"""Scoped runtime API, independent of legacy trace presentation."""
from __future__ import annotations

import json
import re
import subprocess
import time

from dnhacksbio.explorer.runtime import Journal, process_identity, process_namespace, redact
from . import data, projects


def journal():
    return Journal(data.PROCESSED, create=False)


def reconcile(j: Journal, root: str):
    """Only kernel process-identity evidence ends an abandoned attempt, never elapsed time."""
    for run in j.snapshot(root)["runs"].values():
        if run.get("lifecycle") not in {"queued", "running", "reporting"}:
            continue
        owner = run.get("process_identity")
        pid = run.get("pid")
        if owner and (len(owner.split("|")) != 4 or owner.split("|")[1] != process_namespace()):
            continue  # another PID namespace cannot be inspected here; liveness remains unknown
        if owner and pid and process_identity(pid) != owner:
            j.append(run["run_id"], run["attempt_id"], "lifecycle",
                     {"lifecycle": "failed", "reason": "Worker exited without recording an outcome"},
                     producer="supervisor", event_id=f"interrupted-{run['attempt_id']}")


def register_terminal(j: Journal, run_id: str, attempt_id: str, *, socket: str, pane: str):
    """Trusted launcher integration only; no browser API accepts pane/socket identifiers.

    Caller must own this run and its real dedicated pane. SDK branches do not register.
    Pin pane process identity to avoid reusing a disappeared/replaced pane.
    """
    j.manifest(run_id)
    if not re.fullmatch(r"%\d+", pane):
        raise ValueError("Invalid pane")
    result = subprocess.run(["tmux", "-S", socket, "display-message", "-p", "-t", pane,
                             "#{pane_pid}"], capture_output=True, text=True, timeout=2, check=True)
    pid = int(result.stdout.strip())
    j.append(run_id, attempt_id, "terminal.registered", {"socket": socket, "pane": pane,
             "pane_pid": pid, "pane_identity": process_identity(pid)})


def terminal(j, run_id):
    run = j.snapshot(data.LIN.root(run_id))["runs"].get(run_id, {})
    records = [e for e in run.get("history", []) if e["kind"] == "terminal.registered"
               and e["attempt_id"] == run.get("attempt_id")]
    if not records:
        return {"available": False, "reason": "Terminal unavailable for this agent. SDK branches have no dedicated pane."}
    p = records[-1]["payload"]
    if not p.get("pane_identity") or process_identity(p["pane_pid"]) != p["pane_identity"]:
        return {"available": False, "reason": "The registered terminal is no longer available."}
    try:
        pid = subprocess.run(["tmux", "-S", p["socket"], "display-message", "-p", "-t", p["pane"],
                              "#{pane_pid}"], capture_output=True, text=True, timeout=2, check=True)
        if int(pid.stdout.strip()) != p["pane_pid"]:
            raise ValueError("Pane was replaced")
        capture = subprocess.run(["tmux", "-S", p["socket"], "capture-pane", "-p", "-t", p["pane"],
                                  "-S", "-120", "-E", "-"], capture_output=True, text=True, timeout=2, check=True)
        text = re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", "", capture.stdout)
        return {"available": True, "captured_at": time.time(), "text": redact(text[-24000:]),
                "notice": "Read-only screen snapshot, not a complete log. Sensitive-output redaction is best-effort."}
    except (subprocess.SubprocessError, OSError, ValueError):
        return {"available": False, "reason": "The registered terminal could not be captured."}


def handle(handler, rest: str, qs: dict):
    parts = rest.split("/")
    run_id = parts[0]
    project = handler._project_arg(qs)
    j = journal()
    action = parts[1] if len(parts) > 1 else "snapshot"
    if action in {"snapshot", "events", "stream", "blob"}:
        manifest = j.manifest(run_id)
        if not projects.matches_run_scope(manifest.get("project_id"), project):
            raise FileNotFoundError("Run not in this project")
    else:
        manifest = j.manifest(run_id, project)
    root = manifest["investigation_id"]
    if action == "terminal":
        return handler._send_json(terminal(j, run_id))
    through = int(qs["through"][0]) if "through" in qs else None
    if through is not None and through < 0:
        raise ValueError("Invalid playback cursor")
    if action == 'inhibitor' and len(parts) == 3:
        from dnhacksbio.inhibitor.service import Workbench
        wb=Workbench(j,run_id,parts[2],project,through)
        if 'bundle' in qs:
            return handler._send_json(wb.bundle(qs['bundle'][0]))
        if 'file' in qs:
            key=qs['file'][0]
            permitted=set()
            for artifact in wb.bundles():
                permitted.update(wb.bundle(artifact['storage_key']).get('files',{}).values())
            for e in wb.history():
                if e['kind']=='scene.capture': permitted.add(e['payload']['image_hash'])
            if key not in permitted: raise FileNotFoundError('File outside experiment/cursor')
            raw=j.read_blob(key)
            return handler._send_bytes(raw,'image/png' if raw.startswith(b'\x89PNG') else 'application/octet-stream')
        return handler._send_json(wb.describe(qs.get('source_hash',[None])[0]))
    if action in {"blob", "geometry", "tissue"} and len(parts) == 3:
        # A digest is not authority: it must be referenced by this exact run at this cursor.
        key = parts[2]
        state = j.snapshot(root, through)
        run = state["runs"].get(run_id, {})
        refs = []
        for e in run.get("history", []):
            p = e["payload"]
            if e['kind']=='tissue.capture' and e['producer']=='scene-service':
                refs.append({'storage_key':p.get('image_sha256'),'kind':'scene_capture'})
            field = {"experiment.queued": "code", "experiment.started": "code", "tool.started": "inputs", "tool.ended": "observation",
                     "instructions.delivered": "content", "scene.recipe": "recipe", "scene.review": "review"}.get(e["kind"])
            if field:
                refs.append(p.get(field, {}))
            if e["kind"] == "experiment.finished":
                refs.extend([p.get("stdout", {}), p.get("stderr", {})])
            if e["kind"] == "feedback.delivered":
                refs.extend(item.get("version", {}) for item in p.get("items", []))
            if e["kind"] == "artifact" and e["producer"] == "collector" and p.get("status") == "available":
                refs.append(p)
                if p.get("kind") in {"scene_capture","scene_movie"}:refs.append(p.get("snapshot", {}))
        if not any(ref.get("storage_key") == key for ref in refs):
            raise FileNotFoundError("Artifact not available for this researcher at this point")
        if action == "tissue":
            from dnhacksbio.tissue.artifacts import read_frame, frame_parts
            artifact = next((ref for ref in refs if ref.get("storage_key") == key and ref.get("kind") == "tissue_simulation"), None)
            if artifact is None:
                raise FileNotFoundError("Not a tissue artifact")
            part=qs.get('part',['frame'])[0]
            if part in {'metadata','field'}:
                frame,raw=frame_parts(j,key,int(qs.get('condition',['0'])[0]),int(qs.get('frame',['0'])[0]))
                return handler._send_json(frame) if part=='metadata' else handler._send_bytes(raw,'application/octet-stream')
            if part!='frame':raise ValueError('Unknown tissue frame part')
            return handler._send_json(read_frame(j, key, int(qs.get("condition", ["0"])[0]), int(qs.get("frame", ["0"])[0])))
        if action == "geometry":
            from dnhacksbio.inhibitor import normalize, define_pocket, measure, audit_pose, preparation_audit
            artifact = next((ref for ref in refs if ref.get("storage_key") == key
                             and ref.get("kind") == "molecular_structure"), None)
            if artifact is None:
                raise FileNotFoundError("Not a molecular artifact")
            geometry = normalize(j.read_blob(key), artifact["format"], key)
            operation = qs.get("operation", ["describe"])[0]
            if operation == "measure":
                result = measure(geometry, qs.get("atom", []))
            elif operation == "pocket":
                result = define_pocket(geometry, qs.get("residue", [""])[0], float(qs.get("margin", ["5"])[0]))
            elif operation == "contacts":
                result = audit_pose(geometry, qs.get("residue", [""])[0])
            elif operation == "preparation":
                result = preparation_audit(geometry)
            elif operation == "describe":
                result = geometry
            else:
                raise ValueError("Unknown geometry operation")
            return handler._send_json(result)
        media = "image/png" if any(ref.get("storage_key") == key and ref.get("kind") == "scene_capture" for ref in refs) else "text/plain; charset=utf-8"
        if any(ref.get("storage_key") == key and ref.get("kind") == "scene_movie" for ref in refs):media="video/webm"
        return handler._send_bytes(j.read_blob(key), media)
    if action == "snapshot":
        if through is None:
            reconcile(j, root)
        return handler._send_json(j.snapshot(root, through))
    if action == "events":
        if through is None:
            reconcile(j, root)
        after = int(qs.get("after", ["0"])[0])
        return handler._send_json({"events": j.events(root, after, through), "after": after})
    if action != "stream":
        raise FileNotFoundError("Unknown runtime route")
    after = int(handler.headers.get("Last-Event-ID") or qs.get("after", ["0"])[0])
    if after < 0:
        raise ValueError("Invalid event cursor")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True
    # Periodic reconnect bounds request lifetime; EventSource resumes with Last-Event-ID.
    for _ in range(120):
        if _ % 10 == 0:
            reconcile(j, root)
        batch = j.events(root, after)
        if batch:
            for event in batch:
                handler.wfile.write(f"id: {event['sequence']}\nevent: runtime\ndata: {json.dumps(event)}\n\n".encode())
                after = event["sequence"]
        else:
            handler.wfile.write(b": transport heartbeat (not worker liveness)\n\n")
        handler.wfile.flush()
        time.sleep(0.5)
