from dataclasses import dataclass
from pathlib import Path

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
    doc_files: list[tuple[str, Path]]

SCENARIOS = {
    "bitcoin": DemoScenario(
        id="bitcoin",
        title="Bitcoin Consensus",
        description="Self-contained single-document demo using pre-loaded data",
        domain="Technology",
        query="How does Bitcoin achieve decentralized consensus and who introduced the system?",
        mode="adaptive",
        params={"epsilon": 0.01, "patience": 2, "k_max": 12},
        doc_files=[
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
        params={"epsilon": 0.01, "patience": 2, "k_max": 12},
        doc_files=[
            ("Insulin Overview", DATA_DIR / "medical" / "insulin.txt"),
        ],
    ),

}