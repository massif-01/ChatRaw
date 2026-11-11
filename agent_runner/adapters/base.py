"""Candidate adapter contract for CONTRACT v1; Python 3.11+, stdlib only.

These TypedDicts describe trusted Runner/adapter calls, not HTTP validation.
Runner validates browser input, ownership, capabilities, and emitted payloads.
No adapter imports backend.main, writes the public ledger, or emits ``done``.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import ClassVar, Literal, NotRequired, TypeAlias, TypedDict


ADAPTER_CONTRACT_VERSION = 1
AgentId = Literal["hermes", "codex", "claude", "pi", "deepseek"]
JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JSONObject: TypeAlias = dict[str, JSONValue]
AdapterConfig: TypeAlias = JSONObject
RunStatus = Literal[
    "queued", "running", "waiting_input", "waiting_approval", "stopping",
    "completed", "failed", "cancelled", "interrupted", "unknown",
]
TerminalStatus = Literal["completed", "failed", "cancelled", "interrupted"]
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "interrupted"})


class Capabilities(TypedDict):
    streaming_text: bool
    tools: bool
    questions: bool
    approvals: bool
    cancel: bool
    resume: bool
    compact: bool
    images: bool
    files: bool
    steer: bool
    queue: bool
    cancel_mode: Literal["none", "native", "process_stop"]
    limits: NotRequired[JSONObject]
    reason: NotRequired[str]


class ProbeResult(TypedDict):
    availability: Literal["ready", "unconfigured", "unavailable", "unknown"]
    reason: str
    version: str | None
    capabilities: Capabilities
    # Explicit per-check evidence, not an implied chain of successful checks.
    checks: dict[
        Literal["program", "protocol", "authentication", "model_request"],
        Literal["passed", "failed", "unknown", "not_checked"],
    ]
    models: NotRequired[list[JSONObject]]


class SessionBinding(TypedDict):
    """JSON-only private snapshot. Native data must contain no credentials.

    workspace is the Runner-resolved absolute directory. Native identifiers,
    transcript paths and native run references belong in native; handles,
    callbacks, locks and config secrets belong only in adapter memory.
    """

    session_id: str
    agent_id: AgentId
    workspace: str
    native: JSONObject


class Attachment(TypedDict):
    """Runner-admitted local file; never a path supplied by the browser."""

    attachment_id: str
    path: Path
    name: str
    mime_type: str
    size: int


class RunRequest(TypedDict):
    run_id: str
    message: str
    attachments: list[Attachment]


class CompactRequest(TypedDict):
    run_id: str


class RecoveryRequest(TypedDict):
    # No prompt: recovery must never replay a possibly executed submission.
    run_id: str


class AdapterErrorData(TypedDict):
    code: str
    message: str
    retryable: bool


class RunResult(TypedDict):
    # unknown is deliberately not terminal: no done, no automatic next run.
    status: TerminalStatus | Literal["unknown"]
    final_text: str
    error: NotRequired[AdapterErrorData]


class QuestionOption(TypedDict):
    id: str
    label: str
    description: NotRequired[str]
    recommended: NotRequired[bool]


class Question(TypedDict):
    id: str
    text: str
    type: Literal["single", "multi", "text"]
    options: list[QuestionOption]
    allow_custom: bool
    required: bool


class QuestionInteraction(TypedDict):
    kind: Literal["question"]
    title: str
    questions: list[Question]
    allow_cancel: bool
    detail: NotRequired[str]
    expires_at: NotRequired[str | None]
    presentation: NotRequired[Literal["plan"]]


class ApprovalDecision(TypedDict):
    id: str
    label: str
    scope: NotRequired[str]


class ApprovalOperation(TypedDict, total=False):
    tool: str
    command: str
    cwd_label: str
    paths: list[str]
    host_label: str


class ApprovalInteraction(TypedDict):
    kind: Literal["approval"]
    title: str
    decisions: list[ApprovalDecision]
    allow_cancel: bool
    detail: NotRequired[str]
    operation: NotRequired[ApprovalOperation]
    expires_at: NotRequired[str | None]
    presentation: NotRequired[Literal["plan"]]


class QuestionAnswer(TypedDict):
    question_id: str
    option_ids: list[str]
    text: NotRequired[str]


class AnswersReply(TypedDict):
    answers: list[QuestionAnswer]


class DecisionReply(TypedDict):
    decision_id: str


class CancelledReply(TypedDict):
    cancelled: Literal[True]


InteractionReply: TypeAlias = AnswersReply | DecisionReply | CancelledReply


class PublicEvent(TypedDict):
    type: Literal[
        "status", "text_delta", "reasoning_delta", "tool_started",
        "tool_updated", "tool_completed", "usage", "error",
    ]
    data: JSONObject


class InteractionRequestedEvent(TypedDict):
    type: Literal["interaction_requested"]
    # Adapter-generated key unique within this run; not the public interaction ID.
    native_key: str
    data: QuestionInteraction | ApprovalInteraction


class InteractionResolvedData(TypedDict):
    outcome: Literal["answered", "cancelled", "expired", "invalidated"]
    answer_summary: NotRequired[str]


class InteractionResolvedEvent(TypedDict):
    type: Literal["interaction_resolved"]
    native_key: str
    data: InteractionResolvedData


class BindingUpdatedEvent(TypedDict):
    """Private checkpoint; Runner persists before await emit returns.

    Emit a full replacement snapshot when a lazy native session ID or native
    run reference becomes known. Never serialize this event to browser output.
    There is no atomic transaction with upstream: a crash before checkpoint
    still requires unknown-state recovery and must not resend the operation.
    """

    type: Literal["binding_updated"]
    data: SessionBinding


class ArtifactSource(TypedDict):
    path: Path
    name: str
    mime_type: str


class ArtifactEvent(TypedDict):
    """Private candidate. Runner admits/copies it before allocating artifact_id."""

    type: Literal["artifact"]
    data: ArtifactSource


AdapterEvent: TypeAlias = (
    PublicEvent | InteractionRequestedEvent | InteractionResolvedEvent
    | BindingUpdatedEvent | ArtifactEvent
)
# Awaiting emit means durable acceptance, never waiting for the user's reply.
Emit: TypeAlias = Callable[[AdapterEvent], Awaitable[None]]


class AdapterError(Exception):
    """Safe public error. Raw native exceptions/stderr must not be used here.

    Raising this does not establish that native execution ended. After dispatch,
    Runner needs native terminal evidence; otherwise it records unknown.
    """

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def as_data(self) -> AdapterErrorData:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


class UnsupportedCapability(AdapterError):
    def __init__(self, capability: str):
        super().__init__("unsupported_capability", f"Unsupported capability: {capability}")


class AgentAdapter(ABC):
    """One no-argument instance per Runner session; constructor has no I/O.

    Runner serializes run/compact per session, but respond/cancel must remain
    callable while execution waits. Snapshot config is validated before I/O;
    changes take effect on explicit create/resume boundaries, not mid-run.
    All methods run on Runner's event loop. Threaded native callbacks bridge
    onto that loop without blocking the native transport reader.
    """

    agent_id: ClassVar[AgentId]
    # JSON Schema for browser-editable settings only, additionalProperties=false.
    # Executables, argv, credentials and allowed roots are host config, not fields.
    settings_schema: ClassVar[JSONObject]

    @abstractmethod
    def validate_config(self, config: AdapterConfig) -> AdapterConfig:
        """Return normalized private config or raise AdapterError; no I/O."""

    @abstractmethod
    async def probe(self, config: AdapterConfig) -> ProbeResult:
        """Read-only checks; never implicitly issue a billable model request."""

    @abstractmethod
    async def create_session(
        self, session_id: str, workspace: Path, config: AdapterConfig,
    ) -> SessionBinding:
        """Create once; no user prompt. Native ID may be deferred to run."""

    async def resume_session(
        self, binding: SessionBinding, config: AdapterConfig,
    ) -> SessionBinding:
        """Restore the same idle session; never silently create a replacement.

        This is not active-run recovery. Runner must fence unknown runs first;
        old callbacks are invalid unless the native waiting request is verified.
        """
        raise UnsupportedCapability("resume")

    async def recover_run(
        self, binding: SessionBinding, request: RecoveryRequest,
        config: AdapterConfig, emit: Emit,
    ) -> RunResult:
        """Reconcile/reattach an existing run without submitting it again.

        Runner keeps the session fenced until terminal evidence. Implementations
        may await existing native execution, emitting verified progress using
        the original run's sink. Old interactions are invalidated first; only
        verified still-pending native requests may be emitted with fresh keys.
        Unsupported recovery leaves unknown, never infers death from missing I/O.
        """
        return {
            "status": "unknown",
            "final_text": "",
            "error": {
                "code": "recovery_unavailable",
                "message": "Native run state could not be verified",
                "retryable": False,
            },
        }

    @abstractmethod
    async def run(
        self, binding: SessionBinding, request: RunRequest, emit: Emit,
    ) -> RunResult:
        """Return only on native settlement or unknown; EOF is not settlement.

        Forward only this message and attachments. Preserve slash commands.
        final_text is authoritative (not another delta). Do not emit done or
        terminal status; Runner commits final state and emits done exactly once.
        """

    async def respond(
        self, binding: SessionBinding, interaction_key: str, reply: InteractionReply,
    ) -> None:
        """Resolve a live native callback; recheck expiry/run association.

        Runner supplies the private key after validating public ID and payload.
        Return means native response dispatch, not completed tool execution.
        """
        raise UnsupportedCapability("interactions")

    async def cancel(self, binding: SessionBinding, run_id: str) -> None:
        """Request stop; run/compact still owes the actual settlement result.

        Only stop owned execution. Never kill an external Hermes service or
        a shared runtime to cancel one session. Late replies cannot authorize.
        """
        raise UnsupportedCapability("cancel")

    async def compact(
        self, binding: SessionBinding, request: CompactRequest, emit: Emit,
    ) -> RunResult:
        """Native compaction only; uses the same admission/stop rules as run."""
        raise UnsupportedCapability("compact")

    @abstractmethod
    async def close(self, binding: SessionBinding) -> None:
        """Release owned resources after settlement; keep native user state.

        Idempotent cleanup, not implicit approval, session deletion, or proof
        an external run has stopped. Never stop a pre-existing external service.
        """


# Runner owns an explicit allowlist of factories; no browser module imports.
AdapterFactory: TypeAlias = Callable[[], AgentAdapter]
