from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Preference(StrictModel):
    concept: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=300)
    confidence: float = Field(default=1, ge=0, le=1)
    hard: bool = False
    confirmed: bool = True
    negated: bool = False
    priority: int = Field(default=3, ge=1, le=5)
    source_turn: int = Field(default=0, ge=0)
    dimension: str | None = Field(default=None, max_length=120)
    replaces: list[str] = Field(default_factory=list, max_length=20)
    target_field: Literal['category','brand','city','country','labels','description','benefits'] | None = Field(default=None, description='Hotel tier MUST bind to category; named brand to brand; geography to city/country. Null only for free semantic attributes supported in labels/descriptions/benefits.')
    normalized_value: str | None = Field(default=None, max_length=300)
    evidence_scope: Literal['hotel','proximity'] = 'hotel'

class Filter(StrictModel):
    field: Literal['country','city','name','brand','category','labels','description','benefits','off_price','peak_price','id','estimated','peak_months','off_months','peak_sample','off_sample','remark']
    op: Literal['eq','contains','lt','lte','gt','gte','ne'] = 'contains'
    value: str | float | bool

class Query(StrictModel):
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    operation: Literal['list','count','min','max','mean','group','compare','detail','similar','seasonal'] = 'list'
    price_field: Literal['off_price','peak_price'] = 'off_price'
    group_by: Literal['brand','city','country','category'] | None = None
    metric: Literal['count','mean','min','max'] = 'count'
    sort_desc: bool = False
    limit: int = Field(default=3, ge=1, le=20)
    ids: list[str] = Field(default_factory=list, max_length=20)

class SlotPatch(StrictModel):
    # Absent keys preserve state; explicit null clears a slot.
    city: str | None = None
    country: str | None = None
    max_budget: float | None = Field(default=None, gt=0)
    budget_hard: bool | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    travel_dates: str | None = None
    purpose: str | None = None
    exploratory: bool | None = None
    category: Literal['high-end','Top Luxury','International chain'] | None = Field(default=None, description='Canonical CSV Brand level value, not a word occurring in labels or descriptions. An explicit luxury hotel tier normalizes to Top Luxury; null clears the tier.')
    brand: str | None = Field(default=None, max_length=160)
    budget_kind: Literal['subjective','numeric','flexible','skipped'] | None = None
    budget_description: str | None = Field(default=None, max_length=300)

class ClarificationNeed(StrictModel):
    topic: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=600)
    priority: int = Field(default=3, ge=1, le=5)
    material: bool = True
    target_slot: Literal['category','brand','city','country','max_budget','budget_kind','purpose'] | None = None
    preference_keys: list[str] = Field(default_factory=list, max_length=20)
    reason: Literal['missing','ambiguous','conflict'] = 'missing'

class Plan(StrictModel):
    intent: Literal['recommend','clarify','query','unsupported','close']
    search_action: Literal['refine','new_search'] = 'refine'
    requested_count: int | None = Field(default=None, ge=1, le=10)
    unresolved_concepts: list[str] = Field(default_factory=list, max_length=10)
    clarification_needs: list[ClarificationNeed] = Field(default_factory=list, max_length=5)
    additional_queries: list[Query] = Field(default_factory=list, max_length=4)
    add_preferences: list[Preference] = Field(default_factory=list, max_length=20)
    remove_preferences: list[str] = Field(default_factory=list, max_length=20)
    slots: SlotPatch = Field(default_factory=SlotPatch)
    question: str | None = Field(default=None, max_length=600)
    question_topic: str | None = Field(default=None, max_length=120)
    resolved_topics: list[str] = Field(default_factory=list, max_length=20)
    confirmed_preferences: list[str] = Field(default_factory=list, max_length=20)
    query: Query = Field(default_factory=Query)
    # 1-based indices into the latest recommendation/result list.
    references: list[int] = Field(default_factory=list, max_length=20)
    use_focus: bool = False
    semantic_query: str = Field(default='', max_length=600)
    requested_fields: list[str] = Field(default_factory=list, max_length=12)
    @model_validator(mode='after')
    def question_required(self):
        if self.intent == 'clarify' and not self.question and not self.clarification_needs:
            raise ValueError('Clarification needs a question')
        return self

class Evidence(StrictModel):
    preference: str
    relation: Literal['hotel_property','hotel_location_relation','other_entity','unclear']
    field: Literal['labels','description','benefits','category','name','city','country','brand']
    quote: str = Field(min_length=2)
    supports: bool = True

class CandidateEvidence(StrictModel):
    id: str
    evidence: list[Evidence] = Field(default_factory=list)

class EvidenceBatch(StrictModel):
    hotels: list[CandidateEvidence] = Field(default_factory=list)

class ClarificationRecord(StrictModel):
    question: str
    status: Literal['pending','answered','skipped'] = 'pending'
    source_turn: int
    resolved_turn: int | None = None
    answer: str | None = None
    target_slot: str | None = None
    preference_keys: list[str] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)

class Session(StrictModel):
    status: Literal['active','paused'] = 'active'
    history: list[dict[str, str]] = Field(default_factory=list)
    preferences: dict[str, Preference] = Field(default_factory=dict)
    slots: dict[str, Any] = Field(default_factory=dict)
    last_ids: list[str] = Field(default_factory=list)
    focus_ids: list[str] = Field(default_factory=list)
    pending_question: str | None = None
    pending_topic: str | None = None
    pending_ids: list[str] = Field(default_factory=list)
    clarification_memory: dict[str, ClarificationRecord] = Field(default_factory=dict)
    last_result: dict[str, Any] = Field(default_factory=dict)
    turn: int = 0
