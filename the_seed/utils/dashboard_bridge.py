"""Dashboard Bridge - WebSocket server for real-time dashboard updates."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Deque, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

if TYPE_CHECKING:
    from ..core.fsm import FSM, FSMContext

from .log_manager import LogManager

logger = LogManager.get_logger()


@dataclass
class FsmStatePayload:
    """FSM state payload for dashboard."""
    fsm_state: str
    step_index: int
    plan_length: int
    current_goal: str
    blackboard: dict[str, Any]


@dataclass
class AgentMetricsPayload:
    """Agent performance metrics payload."""
    tokens_per_min: float
    llm_calls_per_min: float
    active_tasks: int
    total_actions: int
    execution_volume: int
    failure_rate: float
    recovery_rate: float
    timestamp: int


@dataclass
class GameMetricsPayload:
    """Game performance metrics payload."""
    fps: float
    frame_time_ms: float
    tick_rate: float
    entity_count: int


@dataclass
class TraceEventPayload:
    """Trace event payload for FSM transitions and actions."""
    timestamp: int
    event_type: str  # "fsm_transition" | "action_start" | "action_end" | "log"
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    action_name: Optional[str] = None
    details: dict[str, Any] | None = None


@dataclass
class MemoryQuery:
    """Memory query record."""
    query: str
    hits: int
    timestamp: int


@dataclass
class MemoryEntry:
    """Memory entry record."""
    key: str
    value: str
    timestamp: int
    is_new: bool


@dataclass
class MemoryPayload:
    """Memory monitoring payload."""
    total_entries: int
    recent_queries: list[MemoryQuery]
    recent_additions: list[MemoryEntry]


@dataclass
class LogPayload:
    """Log message payload."""
    level: str
    message: str


class DashboardBridge:
    """WebSocket server bridge for dashboard communication."""

    _instance: Optional['DashboardBridge'] = None

    def __new__(cls) -> 'DashboardBridge':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize dashboard bridge."""
        if self._initialized:
            return

        self._initialized = True
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        self.command_handler: Optional[callable] = None

        # Metrics tracking
        self.llm_calls: Deque[float] = deque(maxlen=100)
        self.tokens_used: Deque[tuple[float, int]] = deque(maxlen=100)
        self.total_tokens = 0
        self.total_llm_calls = 0
        self.action_count = 0
        self.action_failures = 0
        self.action_recoveries = 0

        # Memory tracking
        self.memory_entries: dict[str, str] = {}
        self.recent_queries: Deque[MemoryQuery] = deque(maxlen=50)
        self.recent_additions: Deque[MemoryEntry] = deque(maxlen=50)

    def start(self, host: str = "127.0.0.1", port: int = 8080, command_handler: callable = None) -> None:
        """Start WebSocket server in background thread.

        Args:
            host: Server host address
            port: Server port
            command_handler: Optional callback function(command: str) to handle dashboard commands
        """
        if self.running:
            logger.warning("Dashboard bridge already running")
            return

        self.command_handler = command_handler
        self.running = True
        self.server_thread = threading.Thread(
            target=self._run_server, args=(host, port), daemon=True
        )
        self.server_thread.start()
        logger.info(f"Dashboard bridge started on ws://{host}:{port}")

    def _run_server(self, host: str, port: int) -> None:
        """Run WebSocket server event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def handler(websocket: WebSocketServerProtocol) -> None:
            self.clients.add(websocket)
            logger.info(f"Dashboard client connected: {websocket.remote_address}")

            try:
                # Send initial state
                await self._send_init_message(websocket)

                # Keep connection alive
                async for message in websocket:
                    # Handle client messages (commands, etc.)
                    await self._handle_client_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self.clients.discard(websocket)
                logger.info(f"Dashboard client disconnected: {websocket.remote_address}")

        async def serve() -> None:
            async with websockets.serve(handler, host, port):
                await asyncio.Future()  # run forever

        try:
            self.loop.run_until_complete(serve())
        except Exception as e:
            logger.error(f"Dashboard server error: {e}")

    async def _send_init_message(self, websocket: WebSocketServerProtocol) -> None:
        """Send initial state to newly connected client."""
        init_payload = FsmStatePayload(
            fsm_state="IDLE",
            step_index=0,
            plan_length=0,
            current_goal="",
            blackboard={
                "game_basic_state": "Waiting for game connection...",
                "scratchpad": "",
                "current_step": {},
                "plan": [],
                "action_result": {}
            }
        )

        message = {
            "type": "init",
            "payload": asdict(init_payload)
        }

        await websocket.send(json.dumps(message))

    async def _handle_client_message(self, websocket: WebSocketServerProtocol, message: str) -> None:
        """Handle messages from dashboard clients."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "command":
                # Handle dashboard commands
                payload = data.get("payload", {})
                command = payload.get("command", "")
                logger.info(f"Dashboard command received: {command}")

                # Call registered command handler if available
                if self.command_handler:
                    # Run handler in separate thread to avoid blocking WebSocket
                    threading.Thread(
                        target=self.command_handler,
                        args=(command,),
                        daemon=True
                    ).start()
                else:
                    logger.warning("No command handler registered")

        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    def broadcast(self, message_type: str, payload: Any) -> None:
        """Broadcast message to all connected clients."""
        if not self.clients or not self.loop:
            return

        message = {
            "type": message_type,
            "payload": asdict(payload) if hasattr(payload, '__dict__') else payload
        }

        async def send_to_all() -> None:
            if self.clients:
                await asyncio.gather(
                    *[client.send(json.dumps(message)) for client in self.clients],
                    return_exceptions=True
                )

        asyncio.run_coroutine_threadsafe(send_to_all(), self.loop)

    def update_fsm_state(self, fsm: 'FSM') -> None:
        """Update FSM state and broadcast to clients."""
        ctx = fsm.ctx
        bb = ctx.blackboard

        # Extract blackboard data safely
        blackboard_data = {
            "game_basic_state": getattr(bb, "game_basic_state", ""),
            "scratchpad": getattr(bb, "scratchpad", ""),
            "current_step": getattr(bb, "current_step", {}),
            "plan": getattr(bb, "plan", []),
            "action_result": getattr(bb, "action_result", {})
        }

        payload = FsmStatePayload(
            fsm_state=fsm.state.name if hasattr(fsm.state, 'name') else str(fsm.state),
            step_index=getattr(bb, "step_index", 0),
            plan_length=len(getattr(bb, "plan", [])),
            current_goal=ctx.goal,
            blackboard=blackboard_data
        )

        self.broadcast("update", payload)

    def track_llm_call(self, tokens: int = 0) -> None:
        """Track LLM call for metrics."""
        current_time = time.time()
        self.llm_calls.append(current_time)
        self.total_llm_calls += 1
        if tokens > 0:
            self.tokens_used.append((current_time, tokens))
            self.total_tokens += tokens

        # Calculate and broadcast metrics
        self._broadcast_agent_metrics()

    def track_action(self, action_name: str, success: bool = True, recovered: bool = False) -> None:
        """Track action execution for metrics."""
        self.action_count += 1
        if not success:
            self.action_failures += 1
        if recovered:
            self.action_recoveries += 1

        # Broadcast trace event
        payload = TraceEventPayload(
            timestamp=int(time.time() * 1000),
            event_type="action_end" if success else "action_start",
            action_name=action_name,
            details={"success": success, "recovered": recovered}
        )
        self.broadcast("trace_event", payload)

        # Update metrics
        self._broadcast_agent_metrics()

    def track_fsm_transition(self, from_state: str, to_state: str, details: dict[str, Any] | None = None) -> None:
        """Track FSM state transition."""
        payload = TraceEventPayload(
            timestamp=int(time.time() * 1000),
            event_type="fsm_transition",
            from_state=from_state,
            to_state=to_state,
            details=details or {}
        )
        self.broadcast("trace_event", payload)

    def send_log(self, level: str, message: str) -> None:
        """Send log message to dashboard."""
        payload = LogPayload(level=level, message=message)
        self.broadcast("log", payload)

    def update_memory(self, key: str, value: str) -> None:
        """Update memory entry."""
        is_new = key not in self.memory_entries
        self.memory_entries[key] = value

        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=int(time.time() * 1000),
            is_new=is_new
        )
        self.recent_additions.append(entry)

        self._broadcast_memory_update()

    def query_memory(self, query: str, hits: int = 0) -> None:
        """Track memory query."""
        query_record = MemoryQuery(
            query=query,
            hits=hits,
            timestamp=int(time.time() * 1000)
        )
        self.recent_queries.append(query_record)

        self._broadcast_memory_update()

    def update_game_metrics(self, fps: float, frame_time_ms: float, tick_rate: float, entity_count: int) -> None:
        """Update game performance metrics."""
        payload = GameMetricsPayload(
            fps=fps,
            frame_time_ms=frame_time_ms,
            tick_rate=tick_rate,
            entity_count=entity_count
        )
        self.broadcast("game_metrics", payload)

    def _broadcast_agent_metrics(self) -> None:
        """Calculate and broadcast agent metrics."""
        current_time = time.time()

        # Calculate failure rate
        failure_rate = (
            self.action_failures / self.action_count
            if self.action_count > 0 else 0.0
        )

        # Calculate recovery rate
        recovery_rate = (
            self.action_recoveries / self.action_failures
            if self.action_failures > 0 else 0.0
        )

        payload = AgentMetricsPayload(
            tokens_per_min=float(self.total_tokens),  # Using per_min field for total
            llm_calls_per_min=float(self.total_llm_calls),  # Using per_min field for total
            active_tasks=0,  # TODO: Track active tasks
            total_actions=self.action_count,
            execution_volume=self.action_count,
            failure_rate=failure_rate,
            recovery_rate=recovery_rate,
            timestamp=int(current_time * 1000)
        )

        self.broadcast("agent_metrics", payload)

    def _broadcast_memory_update(self) -> None:
        """Broadcast memory update."""
        payload = MemoryPayload(
            total_entries=len(self.memory_entries),
            recent_queries=list(self.recent_queries),
            recent_additions=list(self.recent_additions)
        )
        self.broadcast("memory_update", payload)


def hook_fsm_transition(fsm_class: type['FSM']) -> None:
    """Hook FSM transition method to broadcast state changes to dashboard."""
    original_transition = fsm_class.transition
    bridge = DashboardBridge()

    def wrapped_transition(self: 'FSM', next_state: Any) -> None:
        """Wrapped transition method that broadcasts to dashboard."""
        old_state = self.state
        result = original_transition(self, next_state)

        # Broadcast FSM state change
        bridge.track_fsm_transition(
            from_state=old_state.name if hasattr(old_state, 'name') else str(old_state),
            to_state=next_state.name if hasattr(next_state, 'name') else str(next_state)
        )

        # Broadcast full FSM state update
        bridge.update_fsm_state(self)

        return result

    fsm_class.transition = wrapped_transition  # type: ignore
