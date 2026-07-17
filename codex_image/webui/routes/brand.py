"""Brand overlay routes: asset upload, template publish, branded download/recompose.

Mirrors the gallery route pattern (closure-style ``register_brand_routes``
decorating the shared ``app``, reaching storage via ``ctx``). Brand assets are
served through a controlled FileResponse (no static mount) so access stays
auditable and deletable, per the review.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from codex_image.webui.context import WebUIContext


def _brand_asset_response(asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "filename": asset.filename,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "size_bytes": asset.size_bytes,
        "sha256": asset.sha256,
        "created_at": asset.created_at,
        "last_used_at": asset.last_used_at,
        "used_count": asset.used_count,
    }


def _brand_template_response(version) -> dict[str, Any]:
    return {
        "template_id": version.template_id,
        "version": version.version,
        "name": version.name,
        "status": version.status,
        "content_hash": version.content_hash,
        "created_at": version.created_at,
        "archived_at": version.archived_at,
        "recipe": version.recipe,
    }


def register_brand_routes(app: FastAPI, ctx: WebUIContext) -> None:
    # --------------------------------------------------------------- assets

    @app.get("/api/brand/assets")
    def list_brand_assets(limit: int = 100) -> dict[str, Any]:
        items = ctx.brand_asset_storage.list_recent(limit=limit)
        return {"items": [_brand_asset_response(item) for item in items]}

    @app.post("/api/brand/assets")
    async def upload_brand_asset(
        filename: str = Form(...),
        image: UploadFile = File(...),
    ) -> dict[str, Any]:
        data = await image.read()
        try:
            asset = ctx.brand_asset_storage.create_or_touch(
                filename, data, image.content_type
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"asset": _brand_asset_response(asset)}

    @app.get("/api/brand/assets/{asset_id}/image")
    def get_brand_asset_image(asset_id: str) -> FileResponse:
        try:
            path = ctx.brand_asset_storage.image_path(asset_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Brand asset not found") from exc
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.delete("/api/brand/assets/{asset_id}")
    def delete_brand_asset(asset_id: str) -> dict[str, Any]:
        try:
            ctx.brand_asset_storage.delete(asset_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "id": asset_id}

    # -------------------------------------------------------------- templates

    @app.get("/api/brand/templates")
    def list_brand_templates(active_only: bool = True) -> dict[str, Any]:
        versions = ctx.brand_template_store.list_active() if active_only else []
        # When active_only is False, surface the active versions per template
        # (full history is reachable via the per-template endpoint).
        return {"templates": [_brand_template_response(v) for v in versions]}

    @app.get("/api/brand/templates/{template_id}")
    def get_brand_template(template_id: str) -> dict[str, Any]:
        try:
            versions = ctx.brand_template_store.list_versions(template_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail="Template not found") from exc
        return {"template_id": template_id, "versions": [_brand_template_response(v) for v in versions]}

    @app.post("/api/brand/templates")
    def publish_brand_template(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        from codex_image.branding.models import BrandTemplate, PlacementConfig

        try:
            template = _template_from_payload(payload, PlacementConfig)
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        version = ctx.brand_template_store.publish(template)
        return {"template": _brand_template_response(version)}

    @app.post("/api/brand/templates/{template_id}/archive")
    def archive_brand_template(template_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        version = _positive_int(payload.get("version"))
        if version is None:
            raise HTTPException(status_code=400, detail="version required")
        try:
            archived = ctx.brand_template_store.archive(template_id, version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Template version not found") from exc
        return {"template": _brand_template_response(archived)}

    # ----------------------------------------------- branded output actions

    @app.get("/api/tasks/{task_id}/outputs/{output_index}/branding/download")
    def download_branded_output(task_id: str, output_index: int) -> FileResponse:
        from codex_image.webui.task_outputs import _safe_branded_output_path

        try:
            metadata = ctx.storage.read_metadata(task_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        branding = _branding_for_output(metadata, output_index)
        if not branding or branding.get("status") != "completed":
            raise HTTPException(status_code=404, detail="Branded output not available")
        path = _safe_branded_output_path(ctx.storage, task_id, str(branding.get("file") or ""))
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Branded file missing")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/api/tasks/{task_id}/branding/recompose")
    def recompose_task_branding(task_id: str) -> dict[str, Any]:
        if ctx.branding_service is None:
            raise HTTPException(status_code=503, detail="Branding not enabled")
        # Force recompose: clear cached branding so the idempotency guard re-runs.
        from codex_image.webui.task_outputs import _delete_branding_derivative_files

        def _clear(m: dict[str, Any]) -> None:
            for output in m.get("outputs", []) or []:
                if isinstance(output, dict) and isinstance(output.get("branding"), dict):
                    _delete_branding_derivative_files(ctx.storage, task_id, output["branding"])
                    output.pop("branding", None)

        try:
            ctx.storage.update_metadata(task_id, _clear)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        outcome = ctx.branding_service.apply_task_branding(task_id)
        return {
            "task_id": task_id,
            "status": outcome.status,
            "branded_count": outcome.branded_count,
            "failed_count": outcome.failed_count,
            "total": outcome.total,
        }


def _branding_for_output(metadata: dict[str, Any], output_index: int) -> dict[str, Any] | None:
    outputs = metadata.get("outputs") if isinstance(metadata.get("outputs"), list) else []
    for output in outputs:
        if isinstance(output, dict) and _positive_int(output.get("index")) == output_index:
            branding = output.get("branding")
            return branding if isinstance(branding, dict) else None
    return None


def _positive_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _template_from_payload(payload: dict[str, Any], PlacementConfig) -> "BrandTemplate":  # type: ignore[name-defined]
    """Build a BrandTemplate from the API payload, validating placements."""
    from codex_image.branding.models import BrandTemplate

    template_id = str(payload["id"])
    name = str(payload.get("name") or template_id)
    theme_mode = str(payload.get("theme_mode") or "auto")
    variant_policy = str(payload.get("variant_policy") or "per-element")
    if theme_mode not in ("auto", "light-assets", "dark-assets"):
        raise ValueError("invalid theme_mode")
    if variant_policy not in ("per-element", "unified"):
        raise ValueError("invalid variant_policy")

    raw_placements = payload.get("placements") or {}
    placements: dict[str, dict[str, Any]] = {}
    for layout, elements in raw_placements.items():
        if layout not in ("square", "portrait", "landscape"):
            raise ValueError(f"invalid layout: {layout}")
        placements[layout] = {}
        for element in ("logo", "slogan"):
            cfg = elements.get(element) or {}
            placements[layout][element] = PlacementConfig(
                anchor=str(cfg.get("anchor") or "top-left"),
                width_ratio=float(cfg.get("width_ratio") or 0.16),
                margin_x_ratio=float(cfg.get("margin_x_ratio") or 0.035),
                margin_y_ratio=float(cfg.get("margin_y_ratio") or 0.035),
            )

    raw_variants = payload.get("asset_variants") or {}
    asset_variants: dict[str, dict[str, str]] = {}
    for tone in ("light-assets", "dark-assets"):
        ids = raw_variants.get(tone) or {}
        asset_variants[tone] = {
            "logo": str(ids.get("logo") or ""),
            "slogan": str(ids.get("slogan") or ""),
        }

    return BrandTemplate(
        id=template_id,
        version=int(payload.get("version") or 1),
        name=name,
        theme_mode=theme_mode,  # type: ignore[arg-type]
        variant_policy=variant_policy,  # type: ignore[arg-type]
        placements=placements,  # type: ignore[arg-type]
        asset_variants=asset_variants,
    )
