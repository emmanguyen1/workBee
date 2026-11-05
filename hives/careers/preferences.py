from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator
from hives.careers.taxonomy import FIELDS
from hives.careers.sectors import SECTORS

class MultiPreferences(BaseModel):
    sectors: list[str] = Field(default_factory=list,max_length=30)
    career_fields: list[str] = Field(default_factory=list,max_length=40)
    companies: list[Annotated[str,Field(min_length=1,max_length=100)]] = Field(default_factory=list,max_length=60)
    countries: list[Annotated[str,Field(min_length=1,max_length=10)]] = Field(default_factory=list,max_length=60)
    regions: list[Annotated[str,Field(min_length=1,max_length=10)]] = Field(default_factory=list,max_length=70)
    workplaces: list[Literal["remote","hybrid","onsite","unspecified"]] = Field(default_factory=list,max_length=4)
    role_types: list[Literal["early_career","internship","new_grad","entry_level","apprenticeship","other"]] = Field(default_factory=list,max_length=6)
    opportunity_types: list[Literal["internship","job","research","lab","program"]] = Field(default_factory=list,max_length=5)

    @field_validator("career_fields")
    @classmethod
    def known_fields(cls,values):
        if any(v not in FIELDS for v in values): raise ValueError("Unknown career field")
        return list(dict.fromkeys(values))

    @field_validator("sectors")
    @classmethod
    def known_sectors(cls,values):
        if any(v not in SECTORS for v in values):raise ValueError("Unknown technical sector")
        return list(dict.fromkeys(values))
