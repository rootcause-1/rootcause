"""Copy the generated scorecard tables from docs/SCORECARD.md into README.md (between the scorecard markers), so the
README's numbers are never typed by hand. Run after `make chaos`."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- scorecard:start -->", "<!-- scorecard:end -->"


def main() -> None:
    card = (ROOT / "docs" / "SCORECARD.md").read_text(encoding="utf-8").splitlines()
    body = "\n".join(line for line in card[1:] if not line.startswith("# ")).strip()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    head, _, rest = readme.partition(START)
    _, _, tail = rest.partition(END)
    (ROOT / "README.md").write_text(f"{head}{START}\n{body}\n{END}{tail}", encoding="utf-8")
    print("README scorecard synced from docs/SCORECARD.md")


if __name__ == "__main__":
    main()
