from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from ..forms import clean
from ..models import Person, Sop
from ..services import ownership as ownership_service
from ..web import Ctx, csrf, ctx, get_db, render, see_other
from ._shared import owned_person

router = APIRouter()
_EMAIL = TypeAdapter(EmailStr)


def _read(form, db: DbSession, user_id: int, person_id: int | None = None) -> tuple[dict, list[str]]:
    values = {
        "name": clean(form.get("name"), 80),
        "role": clean(form.get("role"), 80),
        "email": clean(form.get("email"), 254).lower(),
        "notes": clean(form.get("notes"), 300),
    }
    errors = []
    if len(values["name"]) < 2:
        errors.append("Give the person a name of at least 2 characters.")
    if values["email"]:
        try:
            _EMAIL.validate_python(values["email"])
        except ValidationError:
            errors.append("Enter a valid email address, or leave it blank.")
    clash = db.scalar(
        select(Person.id).where(
            Person.user_id == user_id,
            Person.name == values["name"],
            Person.id != (person_id or 0),
        )
    )
    if clash:
        errors.append("Someone with that name is already on your team list.")
    return values, errors


@router.get("/people")
def people_page(
    request: Request,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    people = db.scalars(select(Person).where(Person.user_id == c.user.id).order_by(Person.name)).all()
    sops = db.scalars(
        select(Sop).options(selectinload(Sop.owner), selectinload(Sop.steps)).where(Sop.user_id == c.user.id)
    ).all()
    cover = ownership_service.coverage(people, sops, c.today)
    return render(request, "people.html", c, people=people, cover=cover)


@router.get("/people/new")
def new_person_page(
    request: Request,
    c: Ctx = Depends(ctx),
):
    return render(
        request,
        "person_form.html",
        c,
        mode="new",
        person=None,
        values={"name": "", "role": "", "email": "", "notes": ""},
        errors=[],
    )


@router.post("/people/new")
async def create_person(
    request: Request,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    form = await request.form()
    values, errors = _read(form, db, c.user.id)
    if errors:
        return render(
            request,
            "person_form.html",
            c,
            http_status=409 if len(errors) == 1 and "already" in errors[0] else 422,
            mode="new",
            person=None,
            values=values,
            errors=errors,
        )
    person = Person(user_id=c.user.id, active=True, **values)
    db.add(person)
    db.commit()
    return see_other("/people")


@router.get("/people/{person_id}/edit")
def edit_person_page(
    request: Request,
    person_id: int,
    c: Ctx = Depends(ctx),
    db: DbSession = Depends(get_db),
):
    person = owned_person(db, c.user.id, person_id)
    return render(
        request,
        "person_form.html",
        c,
        mode="edit",
        person=person,
        values={
            "name": person.name,
            "role": person.role,
            "email": person.email,
            "notes": person.notes,
        },
        errors=[],
    )


@router.post("/people/{person_id}/edit")
async def update_person(
    request: Request,
    person_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    person = owned_person(db, c.user.id, person_id)
    form = await request.form()
    values, errors = _read(form, db, c.user.id, person_id=person.id)
    if errors:
        return render(
            request,
            "person_form.html",
            c,
            http_status=409 if len(errors) == 1 and "already" in errors[0] else 422,
            mode="edit",
            person=person,
            values=values,
            errors=errors,
        )
    for key, value in values.items():
        setattr(person, key, value)
    db.commit()
    return see_other("/people")


@router.post("/people/{person_id}/toggle")
def toggle_person(
    person_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    person = owned_person(db, c.user.id, person_id)
    person.active = not person.active
    db.commit()
    return see_other("/people")


@router.post("/people/{person_id}/delete")
async def delete_person(
    request: Request,
    person_id: int,
    c: Ctx = Depends(csrf),
    db: DbSession = Depends(get_db),
):
    person = owned_person(db, c.user.id, person_id)
    form = await request.form()
    if str(form.get("confirm", "")).strip() != person.name:
        raise HTTPException(422, f"Type {person.name} exactly to remove this person.")
    db.delete(person)
    db.commit()
    return see_other("/people")
