import asyncio
import logging
from ton_core import NetworkGlobalID, to_nano, to_amount
from tonutils.clients import ToncenterClient
from tonutils.contracts.wallet import WalletV4R2

import db

logger = logging.getLogger(__name__)

class TonManager:
    def __init__(self, is_testnet=True):
        self.network = NetworkGlobalID.TESTNET if is_testnet else NetworkGlobalID.MAINNET
        self.client = ToncenterClient(network=self.network)

    async def create_user_wallet(self, user_id):
        # Create a new Wallet V4R2
        wallet, public_key, private_key, mnemonic = WalletV4R2.create(self.client)
        address = wallet.address.to_str(is_bounceable=False)
        mnemonic_str = " ".join(mnemonic)

        db.update_player_wallet(user_id, address, mnemonic_str)
        return address, mnemonic_str

    async def get_balance(self, address):
        try:
            wallet = await WalletV4R2.from_address(self.client, address)
            await wallet.refresh()
            return float(to_amount(wallet.balance))
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            return 0.0

    async def transfer(self, mnemonic_str, destination, amount_ton, comment=""):
        try:
            mnemonic = mnemonic_str.split(" ")
            wallet, _, _, _ = WalletV4R2.from_mnemonic(self.client, mnemonic)

            # The wallet will automatically deploy on first transfer if it has funds
            tx_hash = await wallet.transfer(
                destination=destination,
                amount=amount_ton,
                comment=comment
            )
            return tx_hash
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            return None

    async def check_deposits(self, bot):
        """Check all players for new deposits. To be called manually or from a Cron Trigger."""
        try:
            # We need a list of players with wallets. 
            # Since we can't easily join, we'll just query all players who might have wallets.
            # In a real app, you might want a more efficient way.
            players_results = db._DB.prepare("SELECT user_id, wallet_address, ton_balance FROM players WHERE wallet_address IS NOT NULL").all()
            
            for player in players_results.results:
                user_id = player.user_id
                address = player.wallet_address
                local_balance = player.ton_balance
                
                onchain_balance = await self.get_balance(address)
                
                if onchain_balance > local_balance:
                    diff = onchain_balance - local_balance
                    db.update_ton_balance(user_id, diff, tx_hash=f"dep_{user_id}_{int(asyncio.get_event_loop().time())}", tx_type="deposit")
                    
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"💰 <b>Deposit Detected!</b>\n\n"
                                 f"Amount: {round(diff, 4)} TON\n"
                                 f"New Balance: {round(onchain_balance, 4)} TON",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user {user_id}: {e}")
                        
                elif onchain_balance < local_balance:
                    db.update_ton_balance(user_id, onchain_balance - local_balance)

        except Exception as e:
            logger.error(f"Deposit check error: {e}")

ton_manager = TonManager()
