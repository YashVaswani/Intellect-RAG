# ingestion/schemas.py
"""
Pydantic schemas for Gemini Vision multimodal document extraction.
Enforces lossless layout preservation: tables in Markdown, charts/graphs with visual summaries and metrics.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class DataPoint(BaseModel):
    label: str = Field(..., description="Metric, key, or field label.")
    value: str = Field(..., description="Metric, key, or field value.")
    model_config = {"extra": "forbid"}


class TableStructure(BaseModel):
    table_title: Optional[str] = Field(None, description="Heading, title, or context of the table if available.")
    markdown_data: str = Field(..., description="The complete table translated into clean Markdown format.")
    model_config = {"extra": "forbid"}


class VisualDataStructure(BaseModel):
    type: str = Field(..., description="Type of graphic: e.g., Line Graph, Bar Chart, Pie Chart, Flowchart, Diagram, Infographic.")
    title: Optional[str] = Field(None, description="Title, label, or header of the chart/graphic.")
    visual_summary: str = Field(..., description="Detailed textual description explaining what the chart/graphic visually illustrates and key insights.")
    extracted_data_points: List[DataPoint] = Field(default_factory=list, description="Key metrics, data points, or trend coordinates extracted from the graphic.")
    model_config = {"extra": "forbid"}


class PageExtractionSchema(BaseModel):
    page_number: int = Field(..., description="The page number being processed.")
    has_visual_data: bool = Field(..., description="True if the page contains a table, chart, diagram, or visual graphic.")
    tables: List[TableStructure] = Field(default_factory=list, description="List of all tables on this page.")
    charts_and_graphs: List[VisualDataStructure] = Field(default_factory=list, description="List of all visual charts, metrics, or graphs on this page.")
    standard_text: str = Field("", description="All general narrative paragraphs, headers (#, ##), and key-value details on the page.")
    model_config = {"extra": "forbid"}


class DocumentExtractionSchema(BaseModel):
    file_name: str = Field(..., description="Name of the document.")
    total_pages: int = Field(1, description="Total number of pages processed.")
    pages: List[PageExtractionSchema] = Field(default_factory=list, description="Structured extractions for each page.")
    model_config = {"extra": "forbid"}
