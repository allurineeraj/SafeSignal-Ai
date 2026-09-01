import sys
import os

sys.path.append(r'C:\Users\24016\OneDrive\Desktop\SafeSignalAl')
os.environ['GEMINI_API_KEY'] = 'invalid'

from services.classifier import classify_report
from database.db import save_report, save_ai_prediction

text = "During inspection of a diesel generator, an operator noticed fuel leaking from a damaged hose near the hot engine surface. The generator was running and the leak was not isolated immediately. No injury occurred, but the fuel could have ignited and caused a fire or serious burns."
immediate_action = "The generator was stopped and the leaking hose was isolated. The area was cleared of personnel and the maintenance team was informed."

print('--- Starting Classification ---')
# The fallback logic uses the rule engine
result = classify_report(text, immediate_action)
print(f'Activity: {result.get("activity")}')
print(f'Hazard: {result.get("hazards")}')
print(f'Energy Source: {result.get("energy_sources")}')
print(f'Failed Barrier: {result.get("failed_barriers")}')
print(f'Potential Consequences: {result.get("potential_consequences")}')
print(f'Actual Injury: {result.get("actual_injury")}')
print(f'LLM Status: {result.get("llm_analysis_status")}')
