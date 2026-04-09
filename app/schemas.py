from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IncidentsSummary(BaseModel):
    homicide: int = Field(default=0, ge=0)
    sexual_violence: int = Field(default=0, ge=0)
    robbery: int = Field(default=0, ge=0)
    theft: int = Field(default=0, ge=0)
    violence: int = Field(default=0, ge=0)
    traffic: int = Field(default=0, ge=0)
    emergency: int = Field(default=0, ge=0)
    public_order: int = Field(default=0, ge=0)
    general: int = Field(default=0, ge=0)


class ClosestSevereIncident(BaseModel):
    incident_id: Optional[int] = None
    incident_type: Optional[str] = None
    incident_label: Optional[str] = None
    distance_m: Optional[float] = None
    distance_text: Optional[str] = None
    days_ago: Optional[int] = None
    city: Optional[str] = None
    county: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    published_date: Optional[str] = None

    official_confirmation: bool = False
    primary_source_name: Optional[str] = None
    primary_source_type: Optional[str] = None
    primary_source_url: Optional[str] = None
    primary_source_title: Optional[str] = None


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AnalyzeResponse(BaseModel):
    level: str = Field(..., description="Nivel textual de risc")
    score: float = Field(default=0.0, ge=0, le=10)
    message: str = Field(...)

    county: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)

    incidents_summary: IncidentsSummary = Field(...)
    incidents_count: int = Field(default=0, ge=0)

    sources_used: List[str] = Field(default_factory=list)

    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    confidence_percent: Optional[float] = Field(default=None, ge=0, le=100)

    closest_severe_incident: Optional[ClosestSevereIncident] = Field(default=None)

    analyzed_at: Optional[str] = Field(default=None)

    debug: Optional[Dict[str, Any]] = Field(default=None)