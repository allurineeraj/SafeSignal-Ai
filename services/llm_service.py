import os
import json

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import google-genai
try:
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    class BaseModel:
        pass
    from typing import Any
    def Field(*args, **kwargs) -> Any:
        return None


# Current Gemini model used by SafeSignalAI
GEMINI_MODEL = "gemini-3.6-flash"


class HybridAIExtraction(BaseModel):
    activity: str = Field(
        description=(
            "The primary work activity occurring. "
            "Examples: Working at height, Pump maintenance, "
            "Confined-space entry. "
            "Use 'Not identified from report' only when the report "
            "does not provide enough information."
        )
    )

    hazards: str = Field(
        description=(
            "Primary hazards present. "
            "Examples: Toxic atmosphere, Electrical energy, "
            "Moving machinery, Fall from height."
        )
    )

    energy_sources: str = Field(
        description=(
            "Primary energy sources involved. "
            "Examples: Electrical, Mechanical, Chemical/Gas, "
            "Pressure, Gravity. "
            "Use 'Not identified from report' only when absent."
        )
    )

    exposure: str = Field(
        description=(
            "Who was exposed and how. "
            "Examples: Worker directly exposed, "
            "Multiple personnel exposed."
        )
    )

    failed_barrier_candidates: list[str] = Field(
        description=(
            "Safety barriers that were missing, failed, bypassed, "
            "or ineffective. "
            "Examples: Energy isolation missing, LOTO bypassed, "
            "Fall protection missing. "
            "Return an empty list when no failed barrier is described."
        )
    )

    potential_consequences: str = Field(
        description=(
            "Credible potential consequence if the hazard had manifested. "
            "Examples: Electrocution, Fatal fall from height, "
            "Crushing injury, Fire or explosion."
        )
    )

    life_saving_rule_candidates: list[str] = Field(
        description=(
            "Life-Saving Rules potentially relevant to the report. "
            "Return an empty list if none can be identified."
        )
    )

    evidence: list[str] = Field(
        description=(
            "Specific words, phrases, or short excerpts from the report "
            "that support the identified hazard, exposure, energy source, "
            "failed barrier, or consequence."
        )
    )

    actual_injury: str = Field(
        description=(
            "Description of any actual injury that occurred. "
            "Use 'No injury reported' for a near miss or unsafe act "
            "where no injury occurred."
        )
    )

    llm_reasoning: str = Field(
        description=(
            "Brief factual explanation of how the report supports the "
            "identified hazard, failed barrier, and potential consequence. "
            "Do not invent facts."
        )
    )


def extract_safety_details(text: str) -> dict:
    """
    Use Gemini to extract structured safety intelligence from a worker
    safety report.

    Returns:
        dict: Structured LLM extraction with metadata.
        None: If Gemini is unavailable or the request fails.
    """

    if not HAS_GENAI:
        print("LLM unavailable: google-genai package is not installed.")
        return None

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or api_key == "your_api_key_here":
        print("LLM unavailable: GEMINI_API_KEY not found.")
        return None

    try:
        client = genai.Client(api_key=api_key)

        system_prompt = """
You are the AI safety-analysis component of SafeSignalAI,
an HSE safety-intelligence platform for an oil and gas environment.

Analyze the worker's raw safety report and extract structured safety
information.

The report may contain:
- Broken English
- Hindi words
- Informal descriptions
- Technical terminology
- Near-miss descriptions
- Unsafe-act descriptions

IMPORTANT RULES:

1. Extract information from the report.
2. Do not invent facts.
3. Infer obvious safety meaning only when directly supported by the
   report.
4. Identify the actual hazard described.
5. Identify the energy source involved when supported.
6. Identify who was exposed.
7. Identify failed, missing, bypassed, or ineffective safety barriers.
8. Identify a credible potential consequence.
9. Identify relevant Life-Saving Rules when supported.
10. Provide evidence phrases from the report.
11. If there is no actual injury, return "No injury reported".
12. Do NOT return:
    "Unknown — requires HSE review"
13. HSE review happens AFTER this AI assessment. The AI must provide
    its best-supported assessment before the HSE officer reviews it.
14. The AI assessment is NOT the final HSE decision.
15. Do not decide whether the HSE officer should accept or reject the
    result. That decision belongs to the HSE officer.
16. Return structured JSON matching the provided schema.
"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=HybridAIExtraction,
                temperature=0.1,
            ),
        )

        if not response or not response.text:
            print("LLM Extraction Error: Gemini returned an empty response.")
            return None

        # Parse Gemini's structured JSON response
        result_dict = json.loads(response.text)

        # Add LLM metadata
        result_dict["llm_provider"] = "Google Gemini"
        result_dict["llm_model"] = GEMINI_MODEL
        result_dict["llm_analysis_status"] = "Success"

        # Gemini structured extraction does not provide a reliable
        # token-level confidence score.
        result_dict["llm_confidence"] = 1.0

        return result_dict

    except Exception as e:
        print(f"LLM Extraction Error: {e}")
        return None