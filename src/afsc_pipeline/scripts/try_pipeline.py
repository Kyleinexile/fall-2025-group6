import os
from afsc_pipeline.pipeline import Pipeline

RAW = """
1N0X1 – Intelligence Analyst

- Analyze intelligence reports and produce briefings for senior leaders.
- Maintain databases and disseminate updates to joint partners.
- Coordinate ISR collection requirements and tasking.
"""

if __name__ == "__main__":
    # Set your Neo4j password in env before running:
    #   PowerShell:  $env:NEO4J_PASSWORD="your_pw"
    #   Cmd:         set NEO4J_PASSWORD=your_pw
    if not os.getenv("NEO4J_PASSWORD"):
        raise SystemExit("Set NEO4J_PASSWORD env var before running.")

    pipe = Pipeline()
    try:
        report = pipe.run(RAW, enhance=False, dedupe=False)  # MVP: skills-only
        print("AFSC:", report.afsc_code, "-", report.afsc_title)
        print("Counts:", report.counts_by_type)
        print("Created items:", report.created_items, "Created edges:", report.created_edges)
        if report.warnings:
            print("Warnings:", report.warnings)
        print("Done. See 'runs/<today>/<AFSC>/' for artifacts.")
    finally:
        pipe.close()
