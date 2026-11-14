"""Publication closeout: certificate accounting integrity."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.mpc_central.publication_closeout import audit_certificate_accounting


def test_publish_records_post_decision_accepted():
    store = CertificateStore()
    obs = Observation(
        time=0.0,
        vehicles=(VehicleView("v1", "idle", "D", 10.0, 0.0, (), Anchor("D", 0.0, 10.0, 0.0, frozenset()), None),),
        released_open=("C1",),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
    )
    routes = {"v1": [Visit("C1", "service")]}
    store.publish(routes, obs, ["C1"], accepted=frozenset({"C1"}))
    assert store.current is not None
    assert "C1" in store.current.accepted


def test_audit_certificate_accounting_passes():
    report = audit_certificate_accounting(seed=7)
    assert report["certified_verify_failures"] == 0
    assert report["publish_accepted_mismatches"] == 0
    assert report["pass_accounting"] is True
    assert report["replay_ok"] is True
