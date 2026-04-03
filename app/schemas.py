from typing import Optional

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


class AnalyzeRequest(BaseModel):
    lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitudinea utilizatorului",
    )
    lng: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitudinea utilizatorului",
    )


class AnalyzeResponse(BaseModel):
    level: str = Field(
        ...,
        description="Nivelul de risc afișat utilizatorului",
    )
    message: str = Field(
        ...,
        description="Mesaj clar, pe înțelesul utilizatorului",
    )
    county: Optional[str] = Field(
        default=None,
        description="Județul detectat",
    )
    city: Optional[str] = Field(
        default=None,
        description="Orașul sau localitatea detectată",
    )
    incidents_summary: IncidentsSummary = Field(
        ...,
        description="Sumar al incidentelor relevante pentru zonă",
    )
    sources_used: list[str] = Field(
        default_factory=list,
        description="Lista surselor folosite în analiză",
    )