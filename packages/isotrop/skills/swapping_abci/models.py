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

"""This module contains the shared state for the abci skill of SwappingAbciApp."""

from typing import Any

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.isotrop.skills.swapping_abci.rounds import SwappingAbciApp

class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = SwappingAbciApp


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""
        self.uni_router_address = kwargs.get("uni_router_address", None)
        self.multisend_contract_address = kwargs.get("multisend_contract_address", "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761")
        self.rebalancing_params = self._ensure("rebalancing", kwargs,dict)
        self.default_xdai_val: int = self._ensure("default_xdai_val", kwargs, int)

        super().__init__(*args, **kwargs)
