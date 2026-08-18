from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, require_permission, require_role
from ..auth.rbac import Permission, Role
from ..database import get_db

from .schemas import (
    PatientAssignmentRequest,
    PatientAssignmentResponse,
    PatientCreateRequest,
    PatientResponse,
)
from .service import (
    PatientAccessDeniedError,
    PatientAssignmentError,
    PatientNotFoundError,
    assign_patient_to_physician,
    create_patient_for_user,
    patient_response,
    require_patient_access,
)


router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post(
    "",
    response_model=PatientResponse,
    dependencies=[Depends(require_permission(Permission.PATIENTS_WRITE))],
)
def create_patient(
    request: PatientCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientResponse:
    try:
        patient = create_patient_for_user(
            db,
            user=current_user,
            display_name=request.display_name,
        )
    except PatientAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access is not permitted.") from exc
    return patient_response(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient_details(
    patient_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientResponse:
    try:
        patient = require_patient_access(db, current_user, patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.") from exc
    except PatientAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access is not permitted.") from exc
    return patient_response(patient)


@router.post(
    "/{patient_id}/assignments",
    response_model=PatientAssignmentResponse,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def assign_patient(
    patient_id: UUID,
    request: PatientAssignmentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientAssignmentResponse:
    try:
        assignment = assign_patient_to_physician(
            db,
            patient_id=patient_id,
            physician_id=request.physician_id,
            assigned_by_user=current_user,
        )
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.") from exc
    except PatientAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient assignment is not permitted.") from exc
    except PatientAssignmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return PatientAssignmentResponse(
        patient_id=assignment.patient_id,
        physician_id=assignment.physician_id,
        status=assignment.status,
    )
