from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import User, SupportTicket
from backend.schemas import TicketCreate, TicketResponse
from backend.utils.deps import get_current_user

router = APIRouter()


@router.post("/", response_model=TicketResponse)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """1:1 문의 접수"""
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=payload.subject,
        content=payload.content,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/me", response_model=List[TicketResponse])
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내 문의 내역 조회"""
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.id.desc())
        .all()
    )
    return tickets


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket_detail(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """문의 단건 상세 조회 (답변 확인용)"""
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id, SupportTicket.user_id == current_user.id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
