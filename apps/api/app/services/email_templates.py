from sqlalchemy.orm import Session

from app.models.entities import EmailTemplates


def get_or_create_email_templates(session: Session) -> EmailTemplates:
    row = session.query(EmailTemplates).order_by(EmailTemplates.created_at.asc()).first()
    if row is not None:
        return row
    row = EmailTemplates(refactor_body=None, greenfield_body=None)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_email_templates(
    session: Session,
    *,
    refactor_body: str | None,
    greenfield_body: str | None,
) -> EmailTemplates:
    row = get_or_create_email_templates(session)
    row.refactor_body = refactor_body.strip() if refactor_body and refactor_body.strip() else None
    row.greenfield_body = greenfield_body.strip() if greenfield_body and greenfield_body.strip() else None
    session.commit()
    session.refresh(row)
    return row
