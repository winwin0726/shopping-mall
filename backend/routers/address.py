from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import User, AddressBook
from backend.schemas import AddressBookCreate, AddressBookResponse, AddressBookUpdate
from backend.utils.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=List[AddressBookResponse])
def get_my_addresses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ 내 주소록 목록 조회 (기본 배송지 우선 정렬) """
    addresses = db.query(AddressBook)\
        .filter(AddressBook.user_id == current_user.id)\
        .order_by(AddressBook.is_default.desc(), AddressBook.id.desc())\
        .all()
    return addresses

@router.get("/me/default", response_model=AddressBookResponse)
def get_default_address(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ 내 기본 배송지 조회 """
    address = db.query(AddressBook)\
        .filter(AddressBook.user_id == current_user.id, AddressBook.is_default == True)\
        .first()
    if not address:
        raise HTTPException(status_code=404, detail="Default address not found")
    return address

@router.post("/", response_model=AddressBookResponse)
def create_address(
    payload: AddressBookCreate,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """ 새 주소 등록 """
    # 첫 주소이거나 is_default가 True일 경우, 다른 모든 주소의 is_default를 False로 변경
    is_first = db.query(AddressBook).filter(AddressBook.user_id == current_user.id).count() == 0
    should_be_default = is_first or payload.is_default

    if should_be_default:
        db.query(AddressBook).filter(AddressBook.user_id == current_user.id).update({"is_default": False})

    new_address = AddressBook(
        user_id=current_user.id,
        recipient_name=payload.recipient_name,
        phone=payload.phone,
        postal_code=payload.postal_code,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        is_default=should_be_default
    )
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address

@router.put("/{address_id}", response_model=AddressBookResponse)
def update_address(
    address_id: int,
    payload: AddressBookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ 기존 주소 수정 """
    address = db.query(AddressBook).filter(AddressBook.id == address_id, AddressBook.user_id == current_user.id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    if payload.is_default:
        db.query(AddressBook).filter(AddressBook.user_id == current_user.id).update({"is_default": False})
        address.is_default = True

    if payload.recipient_name is not None: address.recipient_name = payload.recipient_name
    if payload.phone is not None: address.phone = payload.phone
    if payload.postal_code is not None: address.postal_code = payload.postal_code
    if payload.address_line1 is not None: address.address_line1 = payload.address_line1
    if payload.address_line2 is not None: address.address_line2 = payload.address_line2

    db.commit()
    db.refresh(address)
    return address

@router.delete("/{address_id}")
def delete_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ 주소 삭제 """
    address = db.query(AddressBook).filter(AddressBook.id == address_id, AddressBook.user_id == current_user.id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    was_default = address.is_default
    db.delete(address)
    db.commit()

    # 만약 지운 주소가 기본 배송지였다면, 남은 것 중 가장 최근 주소를 기본으로 설정
    if was_default:
        latest_address = db.query(AddressBook).filter(AddressBook.user_id == current_user.id).order_by(AddressBook.id.desc()).first()
        if latest_address:
            latest_address.is_default = True
            db.commit()

    return {"status": "success"}
