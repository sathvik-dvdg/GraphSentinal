# [WSL2]
"""The inference service's /contract must match the backend's validated card.

At boot, main.py treats a MISMATCHED contract as fatal (ContractError) and an
UNREACHABLE service as deferred (InferenceUnavailable). A reachable service that
serves something other than a card object used to fall between the two:
`.get` raised AttributeError and the boot died with a raw traceback. It is a
mismatch and must refuse the boot as one.

DATA: the served payload is the real ML/model_card.json, altered only to build
the mismatch cases.
"""
from __future__ import annotations

import copy
import json

import pytest

from app.config import settings
from app.services.inference_v2 import InferenceV2State, verify_service_contract
from app.services.mitigation_policy import build_policy
from app.services.model_contract import ContractError, load_contract


@pytest.fixture(scope="module")
def state_and_card():
    model_dir = settings.resolved_gs2_model_dir
    contract = load_contract(model_dir)
    card = json.loads((model_dir / "model_card.json").read_bytes().decode("utf-8"))
    state = InferenceV2State(enabled=True, contract=contract, policy=build_policy(contract))
    return state, card


def test_matching_card_is_accepted(state_and_card):
    state, card = state_and_card
    verify_service_contract(state, copy.deepcopy(card))


@pytest.mark.parametrize("served", [[], "model_card", 2, None])
def test_non_object_contract_is_a_contract_error_not_a_crash(state_and_card, served):
    state, _ = state_and_card
    with pytest.raises(ContractError):
        verify_service_contract(state, served)


def test_non_object_outputs_is_a_contract_error_not_a_crash(state_and_card):
    state, card = state_and_card
    served = copy.deepcopy(card)
    served["outputs"] = ["BENIGN"]
    with pytest.raises(ContractError):
        verify_service_contract(state, served)


def test_reordered_served_classes_are_refused(state_and_card):
    state, card = state_and_card
    served = copy.deepcopy(card)
    served["outputs"]["classes"] = list(reversed(served["outputs"]["classes"]))
    with pytest.raises(ContractError):
        verify_service_contract(state, served)
