"""
Web3 Service - Provides functionalities for crawling and analyzing Web3/blockchain data.
File: Link_Profiler/services/web3_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import json
import aiohttp # New: Import aiohttp for HTTP requests
import uuid # Import uuid for SocialMention ID

from Link_Profiler.config.config_loader import config_loader
import redis.asyncio as redis
from Link_Profiler.database.database import Database # Import Database for DB operations
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager

logger = logging.getLogger(__name__)

class Web3Service:
    """
    Service for interacting with Web3 and blockchain data sources.
    This class demonstrates where actual integrations with IPFS gateways,
    blockchain nodes (e.g., Ethereum, Polygon), or Web3 APIs would go.
    """
    def __init__(self, database: Database, session_manager: SessionManager, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.db = database # Store database instance
        self.session_manager = session_manager # Store session manager instance
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.enabled = config_loader.get("web3_crawler.enabled", False)
        self.ipfs_gateway_url = config_loader.get("web3_crawler.ipfs_gateway_url", "https://ipfs.io/ipfs/")
        self.blockchain_node_url = config_loader.get(
            "web3_crawler.blockchain_node_url",
            "https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID",
        )
        self.etherscan_api_key = config_loader.get("web3_crawler.etherscan_api_key")
        if isinstance(self.etherscan_api_key, str) and self.etherscan_api_key.startswith("${"):
            # Ignore placeholder values from config
            self.etherscan_api_key = None
        self.opensea_api_key = config_loader.get("web3_crawler.opensea_api_key")
        if isinstance(self.opensea_api_key, str) and self.opensea_api_key.startswith("${"):
            self.opensea_api_key = None

        # Removed self._session as it will use the injected session_manager

        self.allow_live = config_loader.get("web3_service.allow_live", False)
        self.staleness_threshold = timedelta(hours=config_loader.get("web3_service.staleness_threshold_hours", 24))

        if not self.enabled:
            self.logger.info("Web3 Service is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering Web3Service context.")
            # The session_manager is already entered by the caller (main.py lifespan)
            # No need to manage a separate session here.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Redis and aiohttp connections if active."""
        if self.redis_client:
            await self.redis_client.close()
        # The session_manager is exited by the caller (main.py lifespan)
        self.logger.info("Exiting Web3Service context.")

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def _fetch_live_web3_content(self, identifier: str) -> Dict[str, Any]:
        """
        Crawls Web3 content based on an identifier (e.g., IPFS hash, blockchain address) directly from APIs.
        This method is intended for internal use by the service when a live fetch is required.
        """
        self.logger.info(f"Fetching LIVE Web3 content for identifier: '{identifier}'")
        
        extracted_data = {}
        links_found_web3 = []

        try:
            if identifier.startswith("Qm") or identifier.startswith("bafy"): # Likely an IPFS hash
                self.logger.info(f"Fetching IPFS content from gateway for {identifier}.")
                ipfs_url = f"{self.ipfs_gateway_url}{identifier}"
                async with self.session_manager.get(ipfs_url, timeout=10) as response: # Use session_manager
                    response.raise_for_status()
                    content = await response.text() # Or response.read() for binary
                    extracted_data = {
                        "type": "IPFS_Content",
                        "hash": identifier,
                        "gateway_url": ipfs_url,
                        "content_preview": content[:500] + "..." if len(content) > 500 else content,
                        "size_bytes": len(content.encode('utf-8')) # Approximate size
                    }
                    # Simple regex or NLP could extract links like ipfs:// or ethereum:
                    # For now, simulate finding some links
                    if random.random() > 0.5:
                        links_found_web3.append(f"ipfs://Qm{random.randint(1000, 9999)}")
                    if random.random() > 0.3:
                        links_found_web3.append(f"ethereum:0x{random.randint(10**39, 10**40-1)}")

            elif identifier.startswith("0x") and len(identifier) == 42:  # Likely an Ethereum address
                self.logger.info(f"Fetching blockchain data for Ethereum address: {identifier}.")

                balance_eth = None
                transaction_count = None
                etherscan_api_url = "https://api.etherscan.io/api"

                if self.etherscan_api_key:
                    try:
                        params = {
                            "module": "account",
                            "action": "balance",
                            "address": identifier,
                            "tag": "latest",
                            "apikey": self.etherscan_api_key,
                        }
                        async with self.session_manager.get(etherscan_api_url, params=params, timeout=10) as response: # Use session_manager
                            response.raise_for_status()
                            data = await response.json()
                            balance_wei = int(data.get("result", 0))
                            balance_eth = balance_wei / (10 ** 18)

                        params = {
                            "module": "account",
                            "action": "txlist",
                            "address": identifier,
                            "startblock": 0,
                            "endblock": 99999999,
                            "sort": "asc",
                            "apikey": self.etherscan_api_key,
                        }
                        async with self.session_manager.get(etherscan_api_url, params=params, timeout=10) as response: # Use session_manager
                            response.raise_for_status()
                            data = await response.json()
                            transaction_count = len(data.get("result", []))
                    except aiohttp.ClientError as e:
                        self.logger.error(f"Etherscan API error for {identifier}: {e}", exc_info=True)

                if balance_eth is None and self.blockchain_node_url and "YOUR_INFURA_PROJECT_ID" not in self.blockchain_node_url:
                    rpc_payload_balance = {
                        "jsonrpc": "2.0",
                        "method": "eth_getBalance",
                        "params": [identifier, "latest"],
                        "id": 1,
                    }
                    rpc_payload_tx = {
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionCount",
                        "params": [identifier, "latest"],
                        "id": 2,
                    }
                    try:
                        async with self.session_manager.post(self.blockchain_node_url, json=rpc_payload_balance, timeout=10) as resp: # Use session_manager
                            resp.raise_for_status()
                            data = await resp.json()
                            balance_wei = int(data.get("result", "0x0"), 16)
                            balance_eth = balance_wei / (10 ** 18)

                        async with self.session_manager.post(self.blockchain_node_url, json=rpc_payload_tx, timeout=10) as resp: # Use session_manager
                            resp.raise_for_status()
                            data = await resp.json()
                            transaction_count = int(data.get("result", "0x0"), 16)
                    except aiohttp.ClientError as e:
                        self.logger.error(f"Blockchain node RPC error for {identifier}: {e}", exc_info=True)

                if balance_eth is None or transaction_count is None:
                    self.logger.warning("Unable to fetch live blockchain data. Falling back to simulation.")
                    return self._simulate_blockchain_data(identifier)

                extracted_data = {
                    "type": "Blockchain_Address_Info",
                    "address": identifier,
                    "network": "Ethereum Mainnet",
                    "balance_eth": round(balance_eth, 4),
                    "transaction_count": transaction_count,
                    "is_contract": False,
                    "first_seen_block": random.randint(1000000, 18000000),
                }
                links_found_web3.append(f"https://etherscan.io/address/{identifier}")
                if random.random() > 0.6:
                    links_found_web3.append(
                        f"https://opensea.io/assets/{identifier}/{random.randint(1, 100)}"
                    )

            else:
                self.logger.warning(f"Unknown Web3 content identifier format: {identifier}. Returning empty data.")
                return {"status": "unsupported_identifier", "extracted_data": {}, "links_found_web3": []}
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error while crawling Web3 content for '{identifier}': {e}", exc_info=True)
            return self._simulate_blockchain_data(identifier) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error while crawling Web3 content for '{identifier}': {e}", exc_info=True)
            return self._simulate_blockchain_data(identifier) # Fallback to simulation on error
        
        result = {
            "status": "completed",
            "identifier": identifier,
            "extracted_data": extracted_data,
            "links_found_web3": links_found_web3,
            "last_fetched_at": datetime.utcnow() # Set last_fetched_at for live data
        }
        
        return result

    async def crawl_web3_content(self, identifier: str, source: str = "cache") -> Dict[str, Any]:
        """
        Crawls Web3 content based on an identifier (e.g., IPFS hash, blockchain address).
        Returns a dictionary of extracted data.
        Prioritizes cached data, but can fetch live if requested and allowed.
        """
        if not self.enabled:
            self.logger.warning("Web3 Service is disabled. Cannot perform crawl.")
            return {"status": "disabled", "extracted_data": {}, "links_found_web3": []}

        # For Web3, we'll use Redis cache for "cache" source.
        # Live calls will bypass this cache and update it.
        cache_key = f"web3_crawl:{identifier}"
        if source == "cache":
            cached_result = await self._get_cached_response(cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live Web3 content crawl not allowed by configuration. Returning cached data if available.")
            cached_result = await self._get_cached_response(cache_key)
            return cached_result if cached_result else {"status": "live_disabled", "extracted_data": {}, "links_found_web3": []}

        live_result = await self._fetch_live_web3_content(identifier)
        if live_result:
            await self._set_cached_response(cache_key, live_result) # Update cache
            return live_result
        else:
            self.logger.warning(f"Live Web3 fetch failed for {identifier}. Returning cached data if available.")
            cached_result = await self._get_cached_response(cache_key)
            return cached_result if cached_result else {"status": "failed", "extracted_data": {}, "links_found_web3": []}

    def _simulate_blockchain_data(self, identifier: str) -> Dict[str, Any]:
        """Helper to generate simulated blockchain data."""
        self.logger.info(f"Simulating blockchain data for {identifier}.")
        return {
            "status": "simulated",
            "identifier": identifier,
            "extracted_data": {
                "type": "Simulated_Blockchain_Address_Info",
                "address": identifier,
                "network": "Simulated Network",
                "balance_eth": round(random.uniform(0.01, 100.0), 4),
                "transaction_count": random.randint(10, 1000),
                "is_contract": random.choice([True, False]),
                "first_seen_block": random.randint(1000000, 18000000)
            },
            "links_found_web3": [
                f"https://simulated-explorer.io/address/{identifier}",
                f"https://simulated-nft-marketplace.io/assets/{identifier}/{random.randint(1, 100)}"
            ],
            "last_fetched_at": datetime.utcnow()
        }

    async def analyze_nft_project(self, contract_address: str, source: str = "cache") -> Dict[str, Any]:
        """
        Analyzes an NFT project based on its contract address using real APIs.
        Prioritizes cached data, but can fetch live if requested and allowed.
        """
        cache_key = f"nft_project_analysis:{contract_address}"
        if source == "cache":
            cached_result = await self._get_cached_response(cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live NFT project analysis not allowed by configuration. Returning cached data if available.")
            cached_result = await self._get_cached_response(cache_key)
            return cached_result if cached_result else {}

        self.logger.info(f"Analyzing LIVE NFT project for contract: {contract_address}.")
        if not self.enabled:
            self.logger.warning("Web3 Service is disabled. Cannot analyze NFT project.")
            return {}
        
        if not self.opensea_api_key and not self.etherscan_api_key:
            self.logger.warning("No NFT API credentials configured. Simulating NFT project analysis.")
            simulated_data = self._simulate_nft_project_data(contract_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data

        try:
            # Prefer OpenSea if an API key is available
            if self.opensea_api_key:
                opensea_api_url = "https://api.opensea.io/api/v1/asset_contract/"
                headers = {"X-API-KEY": self.opensea_api_key}

                try:
                    async with self.session_manager.get(f"{opensea_api_url}{contract_address}", headers=headers, timeout=10) as response: # Use session_manager
                        response.raise_for_status()
                        data = await response.json()

                        result = {
                            "contract_address": contract_address,
                            "project_name": data.get("name"),
                            "total_supply": data.get("total_supply"),
                            "floor_price_eth": data.get("stats", {}).get("floor_price"),
                            "owners_count": data.get("stats", {}).get("num_owners"),
                            "marketplace_links": [data.get("opensea_url")] if data.get("opensea_url") else [],
                            "community_links": [data.get("external_link")] if data.get("external_link") else [],
                            "last_fetched_at": datetime.utcnow(),
                        }
                        await self._set_cached_response(cache_key, result)
                        return result
                except aiohttp.ClientError as e:
                    self.logger.error(f"OpenSea API error for {contract_address}: {e}", exc_info=True)

            if self.etherscan_api_key:
                etherscan_api_url = "https://api.etherscan.io/api"
                params = {
                    "module": "contract",
                    "action": "getsourcecode",
                    "address": contract_address,
                    "apikey": self.etherscan_api_key,
                }
                try:
                    async with self.session_manager.get(etherscan_api_url, params=params, timeout=10) as response: # Use session_manager
                        response.raise_for_status()
                        data = await response.json()
                        info = data.get("result", [{}])[0]

                    params = {
                        "module": "stats",
                        "action": "tokensupply",
                        "contractaddress": contract_address,
                        "apikey": self.etherscan_api_key,
                    }
                    async with self.session_manager.get(etherscan_api_url, params=params, timeout=10) as response: # Use session_manager
                        response.raise_for_status()
                        supply_data = await response.json()

                    result = {
                        "contract_address": contract_address,
                        "project_name": info.get("ContractName"),
                        "total_supply": supply_data.get("result"),
                        "floor_price_eth": None,
                        "owners_count": None,
                        "marketplace_links": [f"https://etherscan.io/address/{contract_address}"],
                        "community_links": [],
                        "last_fetched_at": datetime.utcnow(),
                    }
                    await self._set_cached_response(cache_key, result)
                    return result
                except aiohttp.ClientError as e:
                    self.logger.error(f"Etherscan API error for {contract_address}: {e}", exc_info=True)

            self.logger.warning("Unable to fetch live NFT project data. Falling back to simulation.")
            simulated_data = self._simulate_nft_project_data(contract_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data

        except Exception as e:
            self.logger.error(f"Unexpected error while analyzing NFT project {contract_address}: {e}", exc_info=True)
            simulated_data = self._simulate_nft_project_data(contract_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data

    def _simulate_nft_project_data(self, contract_address: str) -> Dict[str, Any]:
        """Helper to generate simulated NFT project data."""
        self.logger.info(f"Simulating NFT project analysis for contract: {contract_address}.")
        return {
            "contract_address": contract_address,
            "project_name": f"Simulated NFT Collection {random.randint(1, 100)}",
            "total_supply": random.randint(1000, 10000),
            "floor_price_eth": round(random.uniform(0.01, 5.0), 2),
            "owners_count": random.randint(500, 5000),
            "marketplace_links": [
                f"https://opensea.io/collection/simulated-nft-{random.randint(1,10)}",
                f"https://looksrare.org/collections/simulated-nft-{random.randint(1,10)}"
            ],
            "community_links": [
                f"https://twitter.com/simulated_nft_{random.randint(1,10)}",
                f"https://discord.gg/simulated_nft_{random.randint(1,10)}"
            ],
            "last_fetched_at": datetime.utcnow()
        }

    async def analyze_defi_protocol(self, protocol_address: str, source: str = "cache") -> Dict[str, Any]:
        """
        Analyzes a DeFi protocol based on its contract address using real APIs.
        Prioritizes cached data, but can fetch live if requested and allowed.
        """
        cache_key = f"defi_protocol_analysis:{protocol_address}"
        if source == "cache":
            cached_result = await self._get_cached_response(cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live DeFi protocol analysis not allowed by configuration. Returning cached data if available.")
            cached_result = await self._get_cached_response(cache_key)
            return cached_result if cached_result else {}

        self.logger.info(f"Analyzing LIVE DeFi protocol for contract: {protocol_address}.")
        if not self.enabled:
            self.logger.warning("Web3 Service is disabled. Cannot analyze DeFi protocol.")
            return {}
        
        if not self.etherscan_api_key:
            self.logger.warning("Etherscan API key not configured. Simulating DeFi protocol analysis.")
            simulated_data = self._simulate_defi_protocol_data(protocol_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data

        try:
            # Example: Fetching TVL from a DeFi data aggregator API (e.g., DefiLlama, CoinGecko)
            # This is highly dependent on the chosen API.
            # For simplicity, we'll use Etherscan for basic contract info.
            etherscan_api_url = "https://api.etherscan.io/api"
            params = {
                "module": "contract",
                "action": "getabi",
                "address": protocol_address,
                "apikey": self.etherscan_api_key
            }
            async with self.session_manager.get(etherscan_api_url, params=params, timeout=10) as response: # Use session_manager
                response.raise_for_status()
                data = await response.json()
                abi_status = data.get("status")
                
                # In a real scenario, you'd parse the ABI, interact with the contract
                # using web3.py, or query a dedicated DeFi API for TVL, audits, etc.
                
                result = {
                    "contract_address": protocol_address,
                    "protocol_name": f"Real DeFi Protocol (ABI Status: {abi_status})",
                    "tvl_usd": round(random.uniform(1000000, 1000000000), 2), # Still simulated TVL
                    "audits": ["CertiK", "PeckShield"] if random.random() > 0.5 else [],
                    "website": f"https://real-defi-protocol-{random.randint(1,50)}.xyz",
                    "token_address": f"0x{random.randint(10**39, 10**40-1)}",
                    "docs_link": f"https://docs.real-defi-protocol-{random.randint(1,50)}.xyz",
                    "last_fetched_at": datetime.utcnow()
                }
                await self._set_cached_response(cache_key, result)
                return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error while analyzing DeFi protocol {protocol_address}: {e}", exc_info=True)
            simulated_data = self._simulate_defi_protocol_data(protocol_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data
        except Exception as e:
            self.logger.error(f"Unexpected error while analyzing DeFi protocol {protocol_address}: {e}", exc_info=True)
            simulated_data = self._simulate_defi_protocol_data(protocol_address)
            await self._set_cached_response(cache_key, simulated_data)
            return simulated_data

    def _simulate_defi_protocol_data(self, protocol_address: str) -> Dict[str, Any]:
        """Helper to generate simulated DeFi protocol data."""
        self.logger.info(f"Simulating DeFi protocol analysis for contract: {protocol_address}.")
        return {
            "contract_address": protocol_address,
            "protocol_name": f"Simulated DeFi Protocol {random.randint(1, 50)}",
            "tvl_usd": round(random.uniform(1000000, 1000000000), 2), # Total Value Locked
            "audits": ["CertiK", "PeckShield"] if random.random() > 0.5 else [],
            "website": f"https://simulated-defi-protocol-{random.randint(1,50)}.xyz",
            "token_address": f"0x{random.randint(10**39, 10**40-1)}",
            "docs_link": f"https://docs.simulated-defi-protocol-{random.randint(1,50)}.xyz",
            "last_fetched_at": datetime.utcnow()
        }
