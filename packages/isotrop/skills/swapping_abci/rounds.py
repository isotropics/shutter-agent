# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains the rounds of SwappingAbciApp."""

import json
from enum import Enum
from typing import Dict, FrozenSet, Mapping, Optional, Set, Tuple,Type, cast
from abc import ABC

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbstractRound,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    CollectionRound,
    DegenerateRound,
    DeserializedCollection,
    EventToTimeout,
    get_name,
)
from packages.isotrop.skills.swapping_abci.payloads import (
    APICheckPayload,
    DecisionMakingPayload,
    TxPreparationPayload,
    StrategyType,
    StrategyEvaluationPayload,
)


class Event(Enum):
    """SwappingAbciApp Events"""

    DONE = "done"
    ERROR = "error"
    TRANSACT = "transact"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"
    MULTI_TRANSACT = "multi_transact"
    DONE_ENTER = "done_enter"
    DONE_EXIT = "done_exit"
    DONE_SWAP_BACK = "done_swap_back"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    def _get_deserialized(self, key: str) -> DeserializedCollection:
        """Strictly get a collection and return it deserialized."""
        serialized = self.db.get_strict(key)
        return CollectionRound.deserialize_collection(serialized)

    @property
    def prices(self) -> Optional[list]:
        return self.db.get("prices", None)

    @property
    def amounts(self) -> Optional[list]:
        amounts_str = self.db.get("amounts", "")
        amounts = []
        if amounts_str:
            amounts = [a for _, a in sorted(json.loads(amounts_str).items(), key=lambda x: x[0])]

        return amounts

    @property
    def participant_to_price_round(self) -> DeserializedCollection:
        """Get the participants to the price round."""
        return self._get_deserialized("participant_to_price_round")

    @property
    def most_voted_tx_hash(self) -> Optional[float]:
        """Get the token most_voted_tx_hash."""
        return self.db.get("most_voted_tx_hash", None)

    @property
    def participant_to_tx_round(self) -> DeserializedCollection:
        """Get the participants to the tx round."""
        return self._get_deserialized("participant_to_tx_round")

    @property
    def tx_submitter(self) -> str:
        """Get the round that submitted a tx to transaction_settlement_abci."""
        return str(self.db.get_strict("tx_submitter"))
    
    @property
    def most_voted_strategy(self) -> str:
        """Get the most_voted_strategy."""
        return cast(str, self.db.get("most_voted_strategy"))
    
    @property
    def final_tx_hash(self) -> str:
        """Get the final_enter_pool_tx_hash."""
        return cast(str, self.db.get_strict("final_tx_hash"))
    
    @property
    def participant_to_strategy(self) -> Mapping[str, StrategyEvaluationPayload]:
        """Get the participant_to_strategy."""
        return cast(
            Mapping[str, StrategyEvaluationPayload],
            self.db.get_strict("participant_to_strategy"),
        )

class LiquidityRebalancingAbstractRound(AbstractRound[Event], ABC):
    """Abstract round for the liquidity rebalancing skill."""

    synchronized_data_class: Type[BaseSynchronizedData] = SynchronizedData

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, self._synchronized_data)

    def _return_no_majority_event(self) -> Tuple[SynchronizedData, Event]:
        """
        Trigger the NO_MAJORITY event.

        :return: a new synchronized data and a NO_MAJORITY event
        """
        return self.synchronized_data, Event.NO_MAJORITY
    

class StrategyEvaluationRound(
    CollectSameUntilThresholdRound,LiquidityRebalancingAbstractRound
):
    """A round in which agents evaluate the financial strategy"""

    #round_id = "strategy_evaluation"
    payload_class = StrategyEvaluationPayload

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            synchronized_data = self.synchronized_data.update(
                participant_to_strategy=tuple(self.collection),
                most_voted_strategy=self.most_voted_payload,
                synchronized_data_class=SynchronizedData,
            )
            strategy = json.loads(self.most_voted_payload)
            if strategy["action"] == StrategyType.WAIT.value:
                return synchronized_data, Event.DONE
            if strategy["action"] == StrategyType.ENTER.value:
                return synchronized_data, Event.DONE_ENTER
            if strategy["action"] == StrategyType.EXIT.value:
                return synchronized_data, Event.DONE
            if strategy["action"] == StrategyType.SWAP_BACK.value:
                return synchronized_data, Event.DONE_ENTER
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class APICheckRound(CollectSameUntilThresholdRound,LiquidityRebalancingAbstractRound):
    """APICheckRound"""

    payload_class = APICheckPayload
    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            synchronized_data = self.synchronized_data.update(
                most_voted_strategy=self.most_voted_payload,
                synchronized_data_class=SynchronizedData,
            )
            return synchronized_data, Event.DONE

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self._return_no_majority_event()
        return None


class DecisionMakingRound(CollectSameUntilThresholdRound,LiquidityRebalancingAbstractRound):
    """DecisionMakingRound"""

    payload_class = DecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""

        if self.threshold_reached:
            event = Event(self.most_voted_payload)
            return self.synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY

        return None

    # Event.DONE, Event.ERROR, Event.TRANSACT, Event.ROUND_TIMEOUT  # this needs to be referenced for static checkers


class TxPreparationRound(CollectSameUntilThresholdRound,LiquidityRebalancingAbstractRound):
    """TxPreparationRound"""

    payload_class = TxPreparationPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_tx_round)
    selection_key = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )

    # Event.ROUND_TIMEOUT  # this needs to be referenced for static checkers


class FinishedDecisionMakingRound(DegenerateRound):
    """FinishedDecisionMakingRound"""


class FinishedTxPreparationRound(DegenerateRound):
    """FinishedSwappingRound"""

class FinishedStrategyEvaluationRound(DegenerateRound):
    """FinishedSwappingRound"""


class SwappingAbciApp(AbciApp[Event]):
    """SwappingAbciApp"""

    initial_round_cls: AppState = StrategyEvaluationRound
    initial_states: Set[AppState] = {
        StrategyEvaluationRound,
    }
    transition_function: AbciAppTransitionFunction = {
        StrategyEvaluationRound: {
            Event.NO_MAJORITY: StrategyEvaluationRound,
            Event.ROUND_TIMEOUT: StrategyEvaluationRound,
            Event.DONE: FinishedStrategyEvaluationRound,
            Event.DONE_ENTER: APICheckRound,
        },
        APICheckRound: {
            Event.NO_MAJORITY: APICheckRound,
            Event.ROUND_TIMEOUT: APICheckRound,
            Event.DONE: DecisionMakingRound,
        },
        DecisionMakingRound: {
            Event.NO_MAJORITY: DecisionMakingRound,
            Event.ROUND_TIMEOUT: DecisionMakingRound,
            Event.DONE: FinishedDecisionMakingRound,
            Event.ERROR: FinishedDecisionMakingRound,
            Event.TRANSACT: TxPreparationRound,
        },
        TxPreparationRound: {
            Event.NO_MAJORITY: TxPreparationRound,
            Event.ROUND_TIMEOUT: TxPreparationRound,
            Event.DONE: FinishedTxPreparationRound,
        },
        FinishedDecisionMakingRound: {},
        FinishedTxPreparationRound: {},
        FinishedStrategyEvaluationRound: {},
    }
    final_states: Set[AppState] = {
        FinishedDecisionMakingRound,
        FinishedTxPreparationRound,
        FinishedStrategyEvaluationRound,
    }
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        StrategyEvaluationRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedDecisionMakingRound: set(),
        FinishedStrategyEvaluationRound: set(),
        FinishedTxPreparationRound: {get_name(SynchronizedData.most_voted_tx_hash)},
    }
