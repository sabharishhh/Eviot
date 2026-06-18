from dataclasses import dataclass
from pathlib import Path

# This points to backend/demo/data/
DATA_DIR = Path(__file__).parent / "data"

@dataclass
class DemoScenario:
    id: str
    title: str
    description: str
    domain: str
    query: str
    mode: str
    params: dict
    doc_files: list[tuple[str, Path]]  # (display_name, path)

# The registry of all our pre-built demos
SCENARIOS = {
    "bitcoin": DemoScenario(
        id="bitcoin",
        title="Bitcoin Consensus",
        description="Self-contained single-document demo using pre-loaded data",
        domain="Technology",
        query="How does Bitcoin achieve decentralized consensus and who introduced the system?",
        mode="adaptive",
        params={"epsilon": 0.05, "patience": 2, "k_max": 12},
        doc_files=[
            # Notice we are using 'consensus.txt' to match the file you created!
            ("Bitcoin Overview", DATA_DIR / "bitcoin" / "consensus.txt"),
        ],
    ),

    "insulin": DemoScenario(
        id="insulin",
        title="Insulin Discovery & Impact",
        description="Medical domain multi-hop reasoning connecting the reduction of mortality with the first successful clinical application of insulin.",
        domain="Medical",
        query="Did the discovery of insulin ultimately reduce mortality from diabetes, and who was responsible for its first successful clinical use?",
        mode="adaptive",
        params={"epsilon": 0.05, "patience": 2, "k_max": 12},
        doc_files=[
            ("Insulin Overview", DATA_DIR / "medical" / "insulin.txt"),
        ],
    ),

    # Note for later: You can easily add the Legal, Medical, and Tech Spec 
    # scenarios from the product specification document here using the exact same format!
}