from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import Patient, PatientAssignment

from ..auth.model import User
from ..auth.rbac import Role, has_permission


class PatientNotFoundError(LookupError):
    pass


class PatientAccessDeniedError(PermissionError):
    pass


class PatientAssignmentError(ValueError):
    pass


def get_patient(db: Session, patient_id: UUID) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise PatientNotFoundError(str(patient_id))
    return patient


def has_patient_access(db: Session, user: User, patient_id: UUID) -> bool:
    patient = get_patient(db, patient_id)

    if user.role == Role.ADMIN.value:
        return True

    if user.role == Role.PATIENT.value:
        return patient.user_id == user.id

    assignment = (
        db.query(PatientAssignment)
        .filter(PatientAssignment.patient_id == patient_id)
        .filter(PatientAssignment.physician_id == user.id)
        .filter(PatientAssignment.status == "active")
        .first()
    )
    return assignment is not None


def require_patient_access(db: Session, user: User, patient_id: UUID) -> Patient:
    patient = get_patient(db, patient_id)
    if not has_patient_access(db, user, patient_id):
        raise PatientAccessDeniedError(str(patient_id))
    return patient


def create_patient_for_user(
    db: Session,
    *,
    user: User,
    display_name: str,
) -> Patient:
    if not has_permission(user, "patients:write"):
        raise PatientAccessDeniedError(str(user.id))

    patient = Patient(display_name=" ".join(display_name.split()))
    try:
        db.add(patient)
        db.flush()
        db.add(
            PatientAssignment(
                physician_id=user.id,
                patient_id=patient.id,
                assigned_by_user_id=user.id,
                status="active",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return patient


def assign_patient_to_physician(
    db: Session,
    *,
    patient_id: UUID,
    physician_id: UUID,
    assigned_by_user: User,
) -> PatientAssignment:
    if assigned_by_user.role != Role.ADMIN.value:
        raise PatientAccessDeniedError(str(assigned_by_user.id))

    get_patient(db, patient_id)
    physician = db.query(User).filter(User.id == physician_id).first()
    if physician is None or physician.role != Role.PHYSICIAN.value:
        raise PatientAssignmentError("The assignee must be an active physician.")
    if not physician.is_active:
        raise PatientAssignmentError("The assignee must be active.")

    assignment = (
        db.query(PatientAssignment)
        .filter(PatientAssignment.patient_id == patient_id)
        .filter(PatientAssignment.physician_id == physician_id)
        .first()
    )
    if assignment is None:
        assignment = PatientAssignment(
            patient_id=patient_id,
            physician_id=physician_id,
            assigned_by_user_id=assigned_by_user.id,
            status="active",
        )
        db.add(assignment)
    else:
        assignment.status = "active"

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PatientAssignmentError("Patient assignment could not be saved.") from exc
    return assignment


def patient_response(patient: Patient) -> dict[str, object]:
    return {
        "patient_id": patient.id,
        "display_name": patient.display_name,
        "user_id": patient.user_id,
    }
