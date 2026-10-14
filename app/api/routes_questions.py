"""Perguntas em linguagem natural."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_login
from app.services.questions import answer_question

router = APIRouter(prefix="/api", dependencies=[Depends(require_login)])


class QuestionIn(BaseModel):
    question: str = Field(..., max_length=1000)


@router.post("/ask")
def ask(body: QuestionIn, user=Depends(require_login)):
    return answer_question(body.question, user["username"])
