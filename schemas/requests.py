# schemas/requests.py
from pydantic import BaseModel, Field
from typing import Optional

class NaturalLanguageRequest(BaseModel):
    description: str = Field(..., description="Natural language description of optimization problem")
    explain_solution: bool = Field(default=True, description="Generate explanation of solution")

class FileInputRequest(BaseModel):
    file_path: str = Field(..., description="Path to text file containing problem description")
    explain_solution: bool = Field(default=True, description="Generate explanation of solution")