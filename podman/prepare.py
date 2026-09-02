"""Copy the current integration into Home Assistant and point it at the mock."""

from pathlib import Path
import shutil
import sys


REAL_URLS = (
    "https://account-fk.niu.com",
    "https://app-api-fk.niu.com",
)


def prepare(source: Path, target: Path, mock_url: str) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    constants = target / "const.py"
    text = constants.read_text(encoding="utf-8")
    for real_url in REAL_URLS:
        if real_url not in text:
            raise RuntimeError(f"Expected NIU URL not found: {real_url}")
        text = text.replace(real_url, mock_url)
    constants.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    prepare(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/source"),
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("/config/custom_components/niu"),
        sys.argv[3] if len(sys.argv) > 3 else "http://mock-niu:8080",
    )
