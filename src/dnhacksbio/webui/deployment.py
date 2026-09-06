"""Linux advisory leases shared by HTTP mutations, jobs and the manual deployer."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path


class Busy(RuntimeError):
    pass


@contextmanager
def lease(*, exclusive=False, path=None):
    configured = path or os.environ.get("DNHACKS_DEPLOY_LOCK")
    if not configured:
        yield None  # ordinary development server; never accepted by the deployer
        return
    target = Path(configured)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy("Deployment or research is active; retry after it finishes") from None
        yield fd
    finally:
        # Do not LOCK_UN: a job may inherit this open-file description. Closing the
        # parent's descriptor must leave the child's research lease held until exit.
        os.close(fd)
