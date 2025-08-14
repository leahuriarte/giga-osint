import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from index.raptor.builder import RaptorBuilder

if __name__ == "__main__":
    rb = RaptorBuilder()
    rb.build_nodes(topic_hint="security/osint")
    print("raptor nodes built.")
