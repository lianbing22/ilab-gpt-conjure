from __future__ import annotations

from fastapi import FastAPI

from codex_image.webui.context import WebUIContext

from .brand import register_brand_routes
from .gallery import register_gallery_routes
from .generation import register_generation_routes
from .queue import register_queue_routes
from .reference_files import register_reference_file_routes
from .settings import register_settings_routes
from .tasks import register_task_routes


def register_webui_routes(app: FastAPI, ctx: WebUIContext) -> None:
    register_settings_routes(app, ctx)
    register_task_routes(app, ctx)
    register_queue_routes(app, ctx)
    register_gallery_routes(app, ctx)
    register_reference_file_routes(app, ctx)
    register_generation_routes(app, ctx)
    # Brand overlay is optional: only register if the context wired it up.
    if ctx.brand_asset_storage is not None and ctx.brand_template_store is not None:
        register_brand_routes(app, ctx)
