import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from models.llm import generate
print(generate("give me 2 bullet points on recent cyber incidents (generic ok)."))

