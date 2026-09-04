"""Tests for ``upwork_cli.contracts``.

The payload unwrapping tested here used to sit inline in a Click callback,
where four fallback shapes and a bare-dict special case had no direct
coverage at all.
"""

import pytest

from tests.fakes import FakeUpworkClient, engagement_node, milestone_node
from upwork_cli import contracts


class TestListContracts:
    def test_the_nested_envelope(self):
        client = FakeUpworkClient(
            engagements={"engagements": {"engagement": [engagement_node("a")]}}
        )
        assert [c.id for c in contracts.list_contracts(client)] == ["a"]

    def test_the_flat_envelope(self):
        client = FakeUpworkClient(engagements={"engagement": [engagement_node("b")]})
        assert [c.id for c in contracts.list_contracts(client)] == ["b"]

    def test_a_bare_dict_becomes_one_contract(self):
        client = FakeUpworkClient(engagements={"engagement": engagement_node("c")})
        assert [c.id for c in contracts.list_contracts(client)] == ["c"]

    def test_an_empty_payload_is_no_contracts(self):
        assert contracts.list_contracts(FakeUpworkClient(engagements={})) == []

    def test_api_failure_raises(self):
        client = FakeUpworkClient(engagements=RuntimeError("upstream 503"))
        with pytest.raises(contracts.ContractsError, match="Failed to fetch contracts"):
            contracts.list_contracts(client)

    def test_fields_survive_the_trip(self):
        client = FakeUpworkClient(
            engagements={"engagement": [engagement_node(title="API work")]}
        )
        contract = contracts.list_contracts(client)[0]
        assert contract.title == "API work"
        assert contract.client_name == "Acme Inc"
        assert contract.hourly_rate == 85.0


class TestGetContract:
    def test_the_enveloped_payload(self):
        client = FakeUpworkClient(
            engagement={"engagement": engagement_node(title="Backend")}
        )
        assert contracts.get_contract(client, "eng-1").contract.title == "Backend"

    def test_a_payload_with_no_envelope(self):
        client = FakeUpworkClient(engagement=engagement_node(title="Unwrapped"))
        assert contracts.get_contract(client, "eng-1").contract.title == "Unwrapped"

    def test_milestones_come_back_as_a_list(self):
        client = FakeUpworkClient(
            engagement=engagement_node(
                milestones=[milestone_node("One"), milestone_node("Two")]
            )
        )
        detail = contracts.get_contract(client, "eng-1")
        assert [m.description for m in detail.milestones] == ["One", "Two"]

    def test_one_milestone_arrives_as_a_bare_dict(self):
        client = FakeUpworkClient(
            engagement=engagement_node(milestones=milestone_node("Only"))
        )
        detail = contracts.get_contract(client, "eng-1")
        assert [m.description for m in detail.milestones] == ["Only"]

    def test_no_milestones_is_an_empty_list(self):
        client = FakeUpworkClient(engagement=engagement_node())
        assert contracts.get_contract(client, "eng-1").milestones == []

    def test_api_failure_raises(self):
        client = FakeUpworkClient(engagement=RuntimeError("gone"))
        with pytest.raises(contracts.ContractsError, match="Failed to fetch contract"):
            contracts.get_contract(client, "eng-1")


class TestSubmitWork:
    def test_a_message_is_sent_as_comments(self):
        client = FakeUpworkClient()
        contracts.submit_work(client, "eng-1", "all done")
        assert client.submitted == [
            {"engagement__reference": "eng-1", "comments": "all done"}
        ]

    def test_no_message_sends_no_comments_key(self):
        client = FakeUpworkClient()
        contracts.submit_work(client, "eng-1")
        assert client.submitted == [{"engagement__reference": "eng-1"}]

    def test_api_failure_raises(self, monkeypatch):
        client = FakeUpworkClient()
        monkeypatch.setattr(
            client, "submit_work", lambda params: (_ for _ in ()).throw(OSError("no"))
        )
        with pytest.raises(contracts.ContractsError, match="Failed to submit work"):
            contracts.submit_work(client, "eng-1")
