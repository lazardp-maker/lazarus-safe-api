from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IncidentsSummary(BaseModel):
    homicide: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de omor sau omucidere",
    )
    sexual_violence: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de violență sexuală",
    )
    robbery: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de tâlhărie sau jaf",
    )
    theft: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de furt",
    )
    violence: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de violență fizică",
    )
    traffic: int = Field(
        default=0,
        ge=0,
        description="Număr incidente rutiere",
    )
    emergency: int = Field(
        default=0,
        ge=0,
        description="Număr situații de urgență",
    )
    public_order: int = Field(
        default=0,
        ge=0,
        description="Număr incidente de ordine publică",
    )
    general: int = Field(
        default=0,
        ge=0,
        description="Alte semnale generale",
    )


class AnalyzeRequest(BaseModel):
    lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitudinea utilizatorului",
        examples=[44.8565],
    )
    lng: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitudinea utilizatorului",
        examples=[24.8692],
    )


class AnalyzeResponse(BaseModel):
    level: str = Field(
        ...,
        description="Nivelul de risc afișat utilizatorului",
        examples=["Prudență ridicată"],
    )
    message: str = Field(
        ...,
        description="Mesaj clar, pe înțelesul utilizatorului",
        examples=[
            "Au fost identificate incidente violente grave în perioada recentă. Se recomandă vigilență maximă și evitarea zonelor sau intervalelor vulnerabile."
        ],
    )

    county: Optional[str] = Field(
        default=None,
        description="Județul detectat",
        examples=["arges"],
    )
    city: Optional[str] = Field(
        default=None,
        description="Orașul sau localitatea detectată",
        examples=["pitesti"],
    )

    incidents_summary: IncidentsSummary = Field(
        ...,
        description="Sumar al incidentelor relevante pentru zonă",
    )

    sources_used: List[str] = Field(
        default_factory=list,
        description="Lista surselor folosite în analiză",
        examples=[["IPJ Arges", "ISU Arges", "Agerpres"]],
    )

    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Scor general de încredere al analizei, între 0 și 1",
        examples=[0.78],
    )

    analyzed_at: Optional[str] = Field(
        default=None,
        description="Timestamp ISO al analizei",
        examples=["2026-04-05T15:10:00+00:00"],
    )

    debug: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Informații tehnice pentru debugging sau administrare",
        examples=[
            {
                "county": "arges",
                "city": "pitesti",
                "profile_found": True,
                "lookback_days": 60,
                "incidents_analyzed": 14,
                "verified_incidents": 8,
                "incident_score_total": 17.4,
            }
        ],
    )