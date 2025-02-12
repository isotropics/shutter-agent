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

"""This package contains round behaviours of SwappingAbciApp."""

import json
import time
import random
from abc import ABC
from typing import Any, Dict, Generator, List, Optional, Set, Type, cast
from packages.valory.protocols.ledger_api.message import LedgerApiMessage

from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.uniswapv2pair.contract import UniswapV2Pair
from packages.valory.contracts.uniswapv2router02.contract import UniswapV2Router02
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)

from hexbytes import HexBytes

from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.isotrop.skills.swapping_abci.models import Params, SharedState
from packages.isotrop.skills.swapping_abci.payloads import (
    APICheckPayload,
    DecisionMakingPayload,
    TxPreparationPayload,
    StrategyType,
    StrategyEvaluationPayload,
)
from packages.isotrop.skills.swapping_abci.rounds import (
    APICheckRound,
    DecisionMakingRound,
    Event,
    SwappingAbciApp,
    SynchronizedData,
    TxPreparationRound,
    StrategyEvaluationRound,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import hash_payload_to_hex

HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
TX_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
debug_str = "*"*100
tx_debug_str = "+"*50
token_config = {
    "usdc": {
        "decimals": 6
    },
    "wxrp": {
        "decimals": 18
    },
    "weth": {
        "decimals": 18
    }
}
SAFE_TX_GAS_ENTER = 0
SAFE_TX_GAS_EXIT = 0
SAFE_TX_GAS_SWAP_BACK = 0
WXDAI = "0xe91d153e0b41518a2ce8dd3d7944fa863463a97d"

class SwappingBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the swapping_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)

    def get_balance(self, token: str):
        """Get balance."""
        # Use the contract API to interact with the ERC20 contract
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=token,
            contract_id=str(ERC20.contract_id),
            contract_callable="check_balance",
            account=self.synchronized_data.safe_contract_address,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"Could not calculate the balance of the safe: {response_msg}")
            return 0,0

        self.context.logger.info(f"Token Balance in account {response_msg}")

        # Fetching token balance, token decimal is 8
        token_balance = response_msg.raw_transaction.body.get("token", None)
        wallet_balance = response_msg.raw_transaction.body.get("wallet", None)

        self.context.logger.info(f"Token balance is {token_balance}")
        return token_balance, wallet_balance

class StrategyEvaluationBehaviour(SwappingBaseBehaviour):  # pylint: disable=too-many-ancestors
    """StrategyEvaluationBehaviour"""

    matching_round: Type[AbstractRound] = StrategyEvaluationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
   
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Get the previous strategy or use the dummy one
            strategy: dict = {}
            try:
                strategy = json.loads(self.synchronized_data.most_voted_strategy)
                self.context.logger.info("Strategy Data found in try")
                if strategy["action"] == StrategyType.ENTER.value:
                    strategy["action"] = StrategyType.SWAP_BACK.value

                elif strategy["action"] == StrategyType.SWAP_BACK.value:
                    strategy["action"] = StrategyType.ENTER.value

            except ValueError:
                strategy = self.get_dummy_strategy()
                self.context.logger.info("Strategy Data found in catch block")

            if strategy["action"] == StrategyType.WAIT.value:  # pragma: nocover
                self.context.logger.info("Current strategy is still optimal. Waiting.")

            if strategy["action"] == StrategyType.ENTER.value:
                tokens = ['token_a', 'token_b', 'token_c', 'token_d', 'token_e', 'token_f', 'token_g']
                selected_token_key = random.choice(tokens)
                self.context.state.selected_token_key = selected_token_key
                # Dynamically set the ticker and address based on selected token
                strategy['token_a']['ticker'] = self.params.rebalancing_params[f"{selected_token_key}_ticker"]
                strategy['token_a']['address'] = self.params.rebalancing_params[f"{selected_token_key}_address"]

                self.context.logger.info(
                    f"Performing strategy update: moving into {strategy['token_base']['ticker']}-{strategy['token_a']['ticker']} (pool swapper v2)"
                )

            if strategy["action"] == StrategyType.EXIT.value:
                self.context.logger.info(
                    "Performing strategy update: moving out of "
                    + f"{strategy['token_base']['ticker']}-{strategy['token_a']['ticker']} (pool swapper v2)"
                )

            if strategy["action"] == StrategyType.SWAP_BACK.value:
                self.context.logger.info(
                    f"Performing strategy update: swapping back {strategy['token_a']['ticker']}, {strategy['token_base']['ticker']}"
                )
            
            payload = StrategyEvaluationPayload(
                sender, json.dumps(strategy, sort_keys=True)
            )
            
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    
    def get_dummy_strategy(self) -> dict:
        """Get a dummy strategy."""
        last_timestamp = cast(
            SharedState, self.context.state
        ).round_sequence.abci_app.last_timestamp.timestamp()

        strategy = {
            "action": StrategyType.ENTER.value,
            "safe_nonce": 0,
            "safe_tx_gas": {
                "enter": SAFE_TX_GAS_ENTER,
                "exit": SAFE_TX_GAS_EXIT,
                "swap_back": SAFE_TX_GAS_SWAP_BACK,
            },
            "deadline": int(last_timestamp)
            + self.params.rebalancing_params["deadline"],
            "chain": self.params.rebalancing_params["chain"],
            "token_base": {
                "ticker": self.params.rebalancing_params["token_base_ticker"],
                "address": self.params.rebalancing_params["token_base_address"],
                "amount_in_max_a": self.params.rebalancing_params["default_max_allowance"],
                "amount_min_after_swap_back_a": int(1e2),
                "is_native": False,
                "set_allowance": self.params.rebalancing_params["max_allowance"],
                "remove_allowance": 0,
            },
            "token_LP": {
                "address": self.params.rebalancing_params["lp_token_address"],
                "set_allowance": self.params.rebalancing_params["max_allowance"],
                "remove_allowance": 0,
            },
            "token_a": {
                "ticker": self.params.rebalancing_params["token_a_ticker"],
                "address": self.params.rebalancing_params["token_a_address"],
                "amount_after_swap": int(1e3),
                "amount_min_after_add_liq": int(0.5e3),
                "is_native": False,  # if one of the two tokens is native, A must be the one
                "set_allowance": self.params.rebalancing_params["max_allowance"],
                "remove_allowance": 0,
                "amount_received_after_exit": 0,
            },
        }
        return strategy

class APICheckBehaviour(SwappingBaseBehaviour):  # pylint: disable=too-many-ancestors
    """APICheckBehaviour"""

    matching_round: Type[AbstractRound] = APICheckRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            self.context.logger.info(f"APICheckBehaviour.async_act    {debug_str}")
            strategy = json.loads(self.synchronized_data.most_voted_strategy)
            self.context.logger.info(f"APICheckBehaviour.strategy    {strategy}")
            yield from self.get_eq_prices(strategy=strategy)
            self.context.logger.info(f"APICheckBehaviour.strategy    {strategy}")
            payload = APICheckPayload(
                sender, json.dumps(strategy, sort_keys=True)
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_eq_prices(self, strategy: dict) -> Generator[None, None, tuple[list[float], list[int]]]:
        is_swap_back = False
        if strategy["action"] == StrategyType.SWAP_BACK.value:
            is_swap_back = True
            self.context.logger.info(f"final_tx_hash: {self.synchronized_data.final_tx_hash}")
            token_a = strategy["token_a"]["address"]
            token_balance, wallet_balance = yield from self.get_balance(token=token_a)
            self.context.logger.info(f"token_a amount_received: {token_balance}")
            self.context.logger.info(f"wallet balance: {wallet_balance}")
            if token_balance > 0:
                strategy["token_a"]["amount_received"] = strategy["token_a"]["amount_after_swap"]
            else:
                is_swap_back = False

        source_token = strategy["token_a"]["address"] if is_swap_back else strategy["token_base"]["address"]
        destination_token = strategy["token_base"]["address"] if is_swap_back else strategy["token_a"]["address"]
        amount_in = strategy["token_a"]["amount_received"] if is_swap_back else self.params.rebalancing_params["default_max_allowance"]

        price_results = yield from self._get_amounts_and_prices_v1(source_token, destination_token, amount_in)
        self.context.logger.info(f"get_prices results {type(price_results)}, {price_results}    {debug_str}")
        prices, amounts_out = price_results
        if not amounts_out or not prices:
            return prices, amounts_out
        
        source_token_amount, destination_token_amount = amounts_out
        if is_swap_back:
            strategy["token_base"]["amount_min_after_swap_back_a"] = destination_token_amount
        else:
            strategy["token_a"]["amount_after_swap"] = destination_token_amount

    def _get_amounts_and_prices_v1(self, source_token: str, destination_token: str, amount_in: int):
        self.context.logger.info(f"get_amounts_and_prices    {debug_str}")
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_id=str(UniswapV2Router02.contract_id),
            contract_callable="get_amounts_out",
            contract_address=self.params.uni_router_address,
            amount_in=amount_in,
            path=[source_token, destination_token],
            chain_id=GNOSIS_CHAIN_ID
        )
        
        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"{debug_str} Getting the swap price failed: {response}"
            )
            return [], []

        amounts = response.state.body.get("amounts", None)
        if not amounts:
            self.context.logger.error(
                f"{debug_str} Getting amounts out failed: {response}"
            )
            return [], []
        
        self.context.logger.info(f"amounts out data:    {amounts}")
        for i, amount in enumerate(amounts):
            if amount <= 0:
                self.context.logger.error(
                    f"{debug_str} found zero amount for token {i+1}: {response}"
                )
                return [], []

        self.context.logger.info(f"{debug_str} Amounts out: {amounts}")
        price1 = float(amounts[0] / amount_in)
        price2 = float(amounts[1] / amounts[0])
        return [price1, price2], amounts

class DecisionMakingBehaviour(SwappingBaseBehaviour):  # pylint: disable=too-many-ancestors
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            event = self.get_event()
            payload = DecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_event(self) -> str:
        """Get the next event based on the amounts data."""
        amounts = self.synchronized_data.amounts
        event = Event.DONE.value
        self.context.logger.info(f"DecisionMakingBehaviour get_event  amounts={amounts}   {debug_str}")

        # Check for specific condition to transition to TRANSACT event
        if len(amounts) == 4 and amounts[0] and amounts[-1] > amounts[0]:
            initial_amount = amounts[0] * 1e-18
            final_amount = amounts[0] * 1e-18
            ratio = final_amount / initial_amount
            self.context.logger.info(f"DecisionMakingBehaviour get_event  initial_amount={initial_amount}, final_amount={final_amount}, ratio={ratio}    {debug_str}")

            # If the ratio exceeds 1.05, trigger a TRANSACT event
            if ratio > 1.05:
                event = Event.TRANSACT.value

        self.context.logger.info(f"Event is {event}")
        event = Event.TRANSACT.value
        return str(event)

class TxPreparationBehaviour(SwappingBaseBehaviour):  # pylint: disable=too-many-ancestors
    """TxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = TxPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            strategy = json.loads(self.synchronized_data.most_voted_strategy)
            self.context.logger.info(f"TxPreparationBehaviour.strategy: {strategy}")
            
            is_swap_back = strategy["action"] == StrategyType.SWAP_BACK.value
            source_token = strategy["token_a"]["address"] if is_swap_back else strategy["token_base"]["address"]
            dest_token = strategy["token_base"]["address"] if is_swap_back else strategy["token_a"]["address"]
            amount_in = strategy["token_a"]["amount_received"] if is_swap_back else strategy["token_base"]["amount_in_max_a"]
            amount_out_min = strategy["token_base"]["amount_min_after_swap_back_a"] if is_swap_back else strategy["token_a"]["amount_after_swap"]
            self.context.logger.info(f"Transaction amount_in: {amount_in}, amount_out_min: {amount_out_min}")
            
            transactions = []

            base_token = strategy["token_base"]["address"]
            token_balance, wallet_balance = yield from self.get_balance(base_token)
            xDAI_balance = wallet_balance / 10**18  # Convert to xDAI
            self.context.logger.info(f"xDAI Balance: {xDAI_balance}")

            if xDAI_balance >= self.params.default_xdai_val:
                amount_to_convert = wallet_balance * 0.80
                self.context.logger.info(f"Amount to convert: {amount_to_convert}")
                exchange_tx = yield from self._build_exchange_tx(amount_to_convert)
                transactions.append(exchange_tx)

            approval_tx = yield from self._build_approval_tx(source_token, amount_in)
            transactions.append(approval_tx)

            swap_tx = yield from self._build_arbitrage_swap_tx_v1(source_token, dest_token, amount_in, amount_out_min)
            transactions.append(swap_tx)

            self.context.logger.info(f"Prepared {len(transactions)} transactions for Multisend: {tx_debug_str}")

            multisend_data = yield from self._build_multisend_tx(transactions)
            self.context.logger.info(f"Multisend data: {multisend_data} {tx_debug_str}")

            safe_tx_hash = yield from self._get_safe_tx_hash(multisend_data)
            self.context.logger.info(f"Safe transaction hash: {safe_tx_hash} {tx_debug_str}")

            tx_hash = hash_payload_to_hex(
                safe_tx_hash=safe_tx_hash,
                ether_value=0,
                safe_tx_gas=SAFE_GAS,
                to_address=self.params.multisend_contract_address,
                data=bytes.fromhex(multisend_data),
                operation=SafeOperation.DELEGATE_CALL.value,  # type: ignore
            )

            self.context.logger.info(f"Transaction hash: {tx_hash} {tx_debug_str}")
            payload = TxPreparationPayload(
                sender=sender, tx_submitter=self.auto_behaviour_id(), tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def _build_exchange_tx(self, amount_to_convert: int) -> Generator[None, None, dict]:
        """Exchange xDAI to wxDAI."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=WXDAI,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_deposit_tx",
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.info(f"Could not build deposit tx: {response_msg}")
            return False

        approval_data = response_msg.state.body.get("data")
        if approval_data is None:
            self.context.logger.info(f"Could not build deposit tx: {response_msg}")
            return False
        
        return {
            "operation": MultiSendOperation.CALL,
            "to": WXDAI,
            "value": int(amount_to_convert),
            "data": HexBytes(approval_data),
        }

    def _build_approval_tx(self, token: str, amount: int) -> Generator[None, None, dict]:
        """Build approval transaction for a given token."""
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=token,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_approval_tx",
            spender=self.params.uni_router_address,
            amount=amount,
            chain_id=GNOSIS_CHAIN_ID
        )
        approve_data = cast(bytes, contract_api_msg.raw_transaction.body["data"])
        return {
            "operation": MultiSendOperation.CALL,
            "to": token,
            "value": 0,
            "data": HexBytes(approve_data.hex()),
        }

    def _build_arbitrage_swap_tx_v1(self, source_token, dest_token, amount_in, amount_out_min) -> Generator[None, None, dict]:
        """Build a swap transaction for arbitrage."""
        deadline = int(time.time() + 60 * 2)  # 2 minutes
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.uni_router_address,
            contract_id=str(UniswapV2Router02.contract_id),
            contract_callable="build_swap_transaction",
            amount_in=amount_in,
            amount_out_min=amount_out_min,
            path=[source_token, dest_token],
            to=self.synchronized_data.safe_contract_address,
            deadline=deadline,
            chain_id=GNOSIS_CHAIN_ID
        )
        swap_data = cast(bytes, contract_api_msg.raw_transaction.body["data"])

        return {
            "operation": MultiSendOperation.CALL,
            "to": self.params.uni_router_address,
            "value": 0,
            "data": HexBytes(swap_data.hex()),
        }

    def _build_multisend_tx(self, txs: List[dict]) -> Generator[None, None, str]:
        """Build the multisend transaction."""
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.multisend_contract_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=txs,
            chain_id=GNOSIS_CHAIN_ID
        )
        self.context.logger.info(f"Contract API message: {contract_api_msg}")
        return cast(str, contract_api_msg.raw_transaction.body["data"])[2:]

    def _get_safe_tx_hash(self, data: str) -> Generator[None, None, Optional[str]]:
        """Prepare and return the safe transaction hash."""
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.multisend_contract_address,
            value=0,
            data=data,
            operation=SafeOperation.DELEGATE_CALL.value,
            safe_tx_gas=SAFE_GAS,
            chain_id=GNOSIS_CHAIN_ID
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(f"Failed to get safe transaction hash: {response.performative.value}, {response}")
            return None

        tx_hash = cast(str, response.state.body["tx_hash"])[2:]
        return tx_hash
    
class SwappingRoundBehaviour(AbstractRoundBehaviour):
    """SwappingRoundBehaviour"""

    initial_behaviour_cls = StrategyEvaluationBehaviour
    abci_app_cls = SwappingAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        APICheckBehaviour,
        DecisionMakingBehaviour,
        TxPreparationBehaviour,
        StrategyEvaluationBehaviour,
    ]