## Swapping Service
## Overview
  This system automates decision-making and transaction preparation for a decentralized trading and arbitrage platform. It interacts with smart contracts, evaluates strategies, and executes token swaps and approvals based on predefined conditions.

## Main Components
 - Strategy Evaluation Behaviour: Evaluates token amounts and strategy, determining if a swap-back or      regular swap should occur.
 - Decision Making Behaviour: Decides the next action (e.g., TRANSACT event) based on the ratio of token amounts.
 - Transaction Preparation Behaviour: Prepares transactions for token swaps, approvals, and multisend.
 - Swapping Round Behaviour: Coordinates all behaviors to execute a full transaction preparation cycle.
## Key Features
- Transaction Building: Prepares exchange, approval, swap, and multisend transactions.
- Event-Driven Execution: Triggers events like DONE or TRANSACT based on token amounts.
- Benchmarking: Measures the time taken for operations to ensure performance.
- Smart Contract Interaction: Interacts with ERC20 tokens, Uniswap router, and multisend contracts.
- Safe Transaction Hashing: Generates a unique transaction hash for multisend operations.

## Workflow Overview
1. Strategy Evaluation (StrategyEvaluationRound):

    - This round involves evaluating a strategy, determining whether to perform a swap or swap-back based on the analysis of token amounts.
    - Once strategy evaluation is done, it either transitions to the APICheckRound (via Event.DONE_ENTER) or ends (Event.DONE), leading to the next round.
2. API Check (APICheckRound):

    - In this round, the system interacts with APIs (likely external smart contracts or data providers) to fetch prices, balances, or other relevant information.
    - Based on the results, the system will transition to the DecisionMakingRound (Event.DONE).
3. Decision Making (DecisionMakingRound):

    - After the API check, the system evaluates whether it should perform a transaction based on predefined conditions, such as the ratio of token amounts.
    - If conditions are met, it triggers the TRANSACT event and moves to the TxPreparationRound.
    - If the event is DONE or ERROR, it concludes the round.
4. Transaction Preparation (TxPreparationRound):

    - In this round, the system prepares the transactions based on the strategy and decisions made earlier (including swap transactions, approval transactions, etc.).
    - Once the transactions are prepared, the round concludes (Event.DONE).
5. Finished States:

    - If any of the rounds reach their conclusion (i.e., FinishedStrategyEvaluationRound, FinishedDecisionMakingRound, FinishedTxPreparationRound), the app is considered to have completed its operation, and no further transitions occur.
## System requirements

- Python `>=3.10`
- [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19`
- [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `==0.6.0`
- [Pip](https://pip.pypa.io/en/stable/installation/)
- [Poetry](https://python-poetry.org/)
- [Docker Engine](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Set Docker permissions so you can run containers as non-root user](https://docs.docker.com/engine/install/linux-postinstall/)

## Run you own agent

### Get the code

1. Clone this repo:

    ```
    https://github.com/isotropics/shutter-agent.git
    ```

2. Create the virtual environment:

    ```
    cd shutter-agent
    poetry shell
    poetry install
    ```

3. Sync packages:

    ```
    autonomy packages sync --update-packages
    ```

### Prepare the data

1. Prepare a `keys.json` file containing wallet address and the private key for each of the  agents.

    ```
    autonomy generate-key ethereum -n 1
    ```

2. Prepare a `ethereum_private_key.txt` file containing one of the private keys from `keys.json`. Ensure that there is no newline at the end.

3. Deploy a [Safe on Gnosis](https://app.safe.global/welcome) (it's free) and set your agent addresses as signers. Set the signature threshold to 3 out of 4.

4. Create a [Tenderly](https://tenderly.co/) account and from your dashboard create a fork of Gnosis chain (virtual testnet).

5. From Tenderly, fund your agents and Safe with a small amount of xDAI, i.e. $0.02 each.

6. Make a copy of the env file:

    ```
    cp sample.env .env
    ```

7. Fill in the required environment variables in .env. The necessary variables include:
    - ALL_PARTICIPANTS: The list of all agent wallet addresses.
    - GNOSIS_LEDGER_RPC: Set this to your Tenderly fork Admin RPC URL.
    - COINGECKO_API_KEY: Obtain an API key from CoinGecko.
    - SAFE_CONTRACT_ADDRESS: The address of your deployed Gnosis Safe.
    - RESET_PAUSE_DURATION: Set the duration for the reset pause (e.g., 10 seconds).
    - RESET_TENDERMINT_AFTER: Set the duration after which Tendermint should be reset (e.g., 10 seconds).
    - TRANSFER_TARGET_ADDRESS: The target address for transfers.
    - SUBGRAPH_URL: The Graph subgraph URL for fetching relevant data.
    - MULTI_SEND_CONTRACT_TOKEN_ADDRESS: The address of the multi-send contract token.
    - TRANSFER_CONTRACT_TOKEN_ADDRESS: The address of the transfer contract token.
    - TOKEN_ADDRESS: The address of the token to be used.(
        wxdai:0xe91d153e0b41518a2ce8dd3d7944fa863463a97d,
        weth:0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1,
        usdc:0xddafbb505ad214d7b80b1f830fccc89b60fb7a83,
        link:0xe2e73a1c69ecf83f464efce6a5be353a37ca09b2,
        uni:0x4537e328bf7e4efa29d05caea260d7fe26af9d74,
        crv:0x712b3d230F3C1c19db860d80619288b1F0BDd0Bd,
        wbtc:0x8e5bBbb09Ed1ebdE8674Cda39A0c169401db4252,
        grt:0xFAdc59D012Ba3c110B08A15B7755A5cb7Cbe77D7
        )
    - TARGET_TOKENS: A list of tokens you want to target for transaction

### Run a single agent

1. Verify that `ALL_PARTICIPANTS` in `.env` contains only 1 address.

2. Run the agent:

    ```
    bash run_agent.sh
    ```

### Run the service (4 agents)

1. Check that Docker is running:

    ```
    docker
    ```

2. Verify that `ALL_PARTICIPANTS` in `.env` contains 4 addresses.

3. Run the service:

    ```
    bash run_service.sh
    ```

4. Look at the service logs for one of the agents (on another terminal):

    ```
    docker logs -f swappingservice_abci_0
    ```


