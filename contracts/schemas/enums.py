from enum import Enum, IntEnum


class InputModality(str, Enum):
    TYPED = "typed"
    HANDWRITTEN = "handwritten"
    MULTILINGUAL = "multilingual"


class ConfidenceTier(str, Enum):
    AUTO_PASS = "auto_pass"
    DUAL_RUN = "dual_run"
    HUMAN_VERIFICATION_REQUIRED = "human_verification_required"
    VERIFIED = "verified"


class ProcessingStatus(str, Enum):
    COMPLETE = "complete"
    PENDING_HUMAN_VERIFICATION = "pending_human_verification"
    FAILED = "failed"


class VerificationState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClinicalEventValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class MemorySource(str, Enum):
    SIMULATED_ABHA = "simulated_abha"
    PATIENT_UPLOAD = "patient_upload"
    PHYSICIAN_APPROVED_CONSULTATION = "physician_approved_consultation"


class TrustTier(IntEnum):
    VERIFIED = 1
    PHYSICIAN_REVIEWED = 2
    UNVERIFIED = 3
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class ThreadMatchConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ThreadMatchMethod(str, Enum):
    CODE_SYSTEM = "code_system"
    NORMALIZED_CONCEPT = "normalized_concept"
    TEXT_SIMILARITY = "text_similarity"
    NEW_THREAD = "new_thread"


class ConflictStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


class ConflictResolutionAction(str, Enum):
    CONFIRM_EVENT_A = "confirm_event_a"
    CONFIRM_EVENT_B = "confirm_event_b"
    KEEP_UNRESOLVED = "keep_unresolved"


class ReviewedStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED_APPROVED = "reviewed_approved"
    REVIEWED_REJECTED = "reviewed_rejected"
    RESOLUTION_CONFIRMED = "resolution_confirmed"


class DocumentType(str, Enum):
    SOAP_NOTE = "soap_note"
    DISCHARGE_SUMMARY = "discharge_summary"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class ReviewAction(str, Enum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT_REGENERATE = "reject_regenerate"
