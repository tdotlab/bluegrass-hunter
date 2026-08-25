import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agent import run_region_research, run_research
from geography import expand_region, select_settlements
from report import render_markdown


app = FastAPI(title="Kentucky Web Scout")


OutputFormat = Literal["json", "markdown"]


class ResearchRequest(BaseModel):
    category: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=120)
    count: int = Field(default=20, ge=1, le=50)
    output_format: OutputFormat = "json"


class RegionRequest(BaseModel):
    anchors: list[str] = Field(min_length=3, max_length=5)


class RegionResearchRequest(BaseModel):
    category: str = Field(min_length=2, max_length=120)
    anchors: list[str] | None = Field(default=None, min_length=3, max_length=5)
    count: int = Field(default=10, ge=1, le=50)
    town_limit: int = Field(default=5, ge=1, le=20)
    settlement_names: list[str] | None = Field(default=None, max_length=20)
    verify: bool = False
    output_format: OutputFormat = "json"


def _check_token(authorization: str | None) -> None:
    expected_token = os.getenv("RESEARCH_TOKEN")
    if expected_token and authorization != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Missing or invalid research token")


def _artifact_filename(target: str, extension: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", target.casefold()).strip("-")
    slug = (slug or "research-report")[:80].rstrip("-")
    date = datetime.now(timezone.utc).date().isoformat()
    return f"{date}-{slug}.{extension}"


def _format_report(report: Any, output_format: OutputFormat) -> Any:
    if output_format == "markdown":
        return PlainTextResponse(
            content=render_markdown(report),
            media_type="text/markdown",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{_artifact_filename(report.target, "md")}"'
                )
            },
        )
    return report.model_dump()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/research")
async def research(
    request: ResearchRequest,
    authorization: str | None = Header(default=None),
) -> Any:
    _check_token(authorization)
    report = await run_research(request.category, request.location, request.count)
    return _format_report(report, request.output_format)


@app.post("/research-region")
async def research_region(
    request: RegionResearchRequest,
    authorization: str | None = Header(default=None),
) -> Any:
    _check_token(authorization)

    if request.settlement_names:
        try:
            settlements = [
                settlement.model_dump()
                for settlement in select_settlements(request.settlement_names)
            ][: request.town_limit]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif request.anchors:
        try:
            expansion = await expand_region(request.anchors)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        available = [settlement.model_dump() for settlement in expansion.settlements]
        priority = {
            "incorporated_place": 0,
            "census_designated_place": 1,
            "unincorporated_populated_place": 2,
        }
        settlements = sorted(
            available,
            key=lambda item: (
                priority.get(item.get("place_status"), 3),
                item["name"].casefold(),
            ),
        )[: request.town_limit]
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either settlement_names or at least three anchors.",
        )

    if not settlements:
        raise HTTPException(
            status_code=400,
            detail="The region produced no searchable settlements.",
        )
    report = await run_region_research(
        request.category,
        settlements,
        request.count,
        verify=request.verify,
    )
    return _format_report(report, request.output_format)


@app.post("/expand-region")
async def expand_region_endpoint(
    request: RegionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    _check_token(authorization)
    try:
        expansion = await expand_region(request.anchors)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="The map data service failed while expanding the region.",
        ) from exc
    return expansion.model_dump()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Research local website opportunities")
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--output", default="reports/latest.md")
    parser.add_argument("--json-output", default="reports/latest.json")
    args = parser.parse_args()

    report = asyncio.run(run_research(args.category, args.location, args.count))

    markdown_output = Path(args.output)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")

    json_output = Path(args.json_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {markdown_output}")
    print(f"Wrote {json_output}")


if __name__ == "__main__":
    if os.getenv("PORT"):
        import uvicorn

        uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ["PORT"]))
    else:
        cli()
