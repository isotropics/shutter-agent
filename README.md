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
    
    ```

2. Create the virtual environment:

    ```
    cd shutter-swapping
    poetry shell
    poetry install
    ```

3. Sync packages:

    ```
    autonomy packages sync --update-packages
    ```

### Prepare the data

1. Prepare a `keys.json` file containing wallet address and the private key for each of the four agents.

    ```
    autonomy generate-key ethereum -n 4
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
    - TOKEN_ADDRESS: The address of the token to be used.
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


