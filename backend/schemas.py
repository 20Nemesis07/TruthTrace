from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Short = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)
]
Verdict = Literal["TRUE", "FALSE", "MISLEADING", "UNVERIFIABLE"]
Relation = Literal[
    "Supports",
    "Contradicts",
    "Partially supports",
    "Irrelevant",
    "Insufficient evidence",
]


class Claim(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    claim: str = Field(min_length=5, max_length=1500)
    offline: bool = False


class Analysis(BaseModel):
    kind: Literal["factual", "opinion", "prediction", "ambiguous"]
    topic: Literal["health", "finance", "space", "public affairs", "leadership", "general"]
    assertions: list[Short] = Field(min_length=1, max_length=6)
    entities: list[Short] = Field(max_length=20)
    qualifiers: list[Short] = Field(max_length=20)
    queries: list[Short] = Field(min_length=1, max_length=4)


class Finding(BaseModel):
    assertion: int = Field(ge=0, le=5)
    evidence_id: Short
    relation: Relation
    quote: str = Field(max_length=750)
    reason: Short


class Findings(BaseModel):
    findings: list[Finding] = Field(max_length=60)


class Synthesis(BaseModel):
    verdict: Verdict
    established: str
    interpretation: str
    uncertainty: str
    citations: list[str]


class Validate(BaseModel):
    report_id: str = Field(max_length=64)
    findings: list[Finding] = Field(max_length=60)
