import json
import os
from services.classifier import classify_report

text = "During pump maintenance, a technician entered the work area while the pump was still energized. The electrical isolation and lockout/tagout were not completed. No injury occurred, but the technician was directly exposed to electrical energy and could have suffered electrocution."

res = classify_report(text)
print(json.dumps(res, indent=2))
