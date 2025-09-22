from enum import Enum, auto
from loguru import logger

class BotState(Enum):
    """
    Defines the possible operational states of the trading bot.
    Using an Enum makes the states explicit and prevents errors from typos.
    """
    IDLE = auto()          # Bot is waiting for favorable market conditions to enter a trade.
    PRECHECK = auto()      # Performing initial checks (API health, balances, market rules).
    ENTER = auto()         # Looking to enter a new weekly short position.
    MONITOR = auto()       # Actively monitoring open positions for threats or profit-taking.
    ADJUST = auto()        # Adjusting an existing position (e.g., rolling a threatened leg).
    EXPIRY_ROLL = auto()   # Rolling an entire weekly position as it nears expiry.
    HEDGE_ROLL = auto()    # Rolling the monthly hedge position.
    KILLED = auto()        # Bot has been stopped due to a hard risk limit or manual intervention.

class StateMachine:
    """
    Manages the bot's state and orchestrates transitions.
    This provides a central point of control for the bot's lifecycle.
    """
    def __init__(self, initial_state: BotState = BotState.PRECHECK):
        self._state = initial_state
        self.is_running = True
        logger.info(f"State machine initialized. Initial state: {self._state.name}")

    @property
    def state(self) -> BotState:
        """Returns the current state of the bot."""
        return self._state

    def transition(self, to_state: BotState):
        """
        Transitions the bot to a new state and logs the change.
        """
        if not isinstance(to_state, BotState):
            logger.error(f"Invalid object passed to transition: {to_state}. Must be a BotState enum member.")
            return

        from_state_name = self._state.name
        to_state_name = to_state.name

        if from_state_name == to_state_name:
            logger.debug(f"Staying in state: {from_state_name}")
        else:
            logger.info(f"STATE TRANSITION: {from_state_name} -> {to_state_name}")
            self._state = to_state

    def stop(self):
        """Stops the state machine and transitions to a terminal state."""
        if self.is_running:
            logger.warning("Stop signal received. Transitioning to KILLED state and shutting down.")
            self.transition(BotState.KILLED)
            self.is_running = False
