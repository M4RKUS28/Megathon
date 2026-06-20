import uuid

from pydantic import BaseModel


class StyleGuide(BaseModel):
    companyName: str = ""
    logoUrls: list[str] = []
    brandColors: list[str] = []
    fonts: list[str] = []
    imageUrls: list[str] = []
    websiteUrl: str = ""


class BrandingResponse(BaseModel):
    company_id: uuid.UUID
    company_name: str
    slug: str
    primary_color: str | None = None
    logo_url: str | None = None
    style_guide: StyleGuide


class BrandingUpdate(BaseModel):
    style_guide: StyleGuide
    primary_color: str | None = None
    logo_url: str | None = None
