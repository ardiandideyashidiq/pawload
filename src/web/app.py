from __future__ import annotations

import json
import logging
import queue
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename

from sourceforge.config import setup_logging
from web.bridge import WebBridge, get_lan_ip


def create_app(bridge: WebBridge | None = None, verbose: int = 0) -> Flask:
    """Flask application factory for MultiCloud transfer manager."""
    pkg_dir = Path(__file__).parent
    dist_dir = pkg_dir / "dist"
    assets_dir = dist_dir / "assets"

    app = Flask(
        __name__,
        static_folder=str(assets_dir) if assets_dir.is_dir() else None,
        static_url_path="/assets",
    )

    app.config["VERBOSE"] = verbose
    if verbose > 0:
        logging.getLogger("werkzeug").setLevel(logging.INFO)
    else:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    active_bridge = bridge or WebBridge()
    app.config["BRIDGE"] = active_bridge

    @app.before_request
    def log_request_start() -> None:
        request._start_time = time.time()
        if app.config.get("VERBOSE", 0) >= 2:
            logger.debug(
                f">> {request.method} {request.path} from {request.remote_addr or '127.0.0.1'}"
            )

    @app.after_request
    def log_request_end(response: Response) -> Response:
        verbosity = app.config.get("VERBOSE", 0)
        if verbosity > 0:
            start = getattr(request, "_start_time", time.time())
            duration_ms = (time.time() - start) * 1000
            client = request.remote_addr or "127.0.0.1"
            status = response.status_code
            msg = f'{client} - "{request.method} {request.path}" {status} ({duration_ms:.1f}ms)'
            if status >= 400:
                logger.warning(msg)
            elif verbosity >= 2:
                logger.debug(msg)
            else:
                logger.info(msg)
        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str) -> Any:
        if path.startswith("api/"):
            return jsonify({"error": "Endpoint not found"}), 404

        target = dist_dir / path
        if path and target.is_file():
            return send_from_directory(dist_dir, path)

        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return send_from_directory(dist_dir, "index.html")

        fallback_html = (
            "<!doctype html><html><head><title>MultiCloud Transfer Manager</title></head>"
            "<body style='font-family:system-ui,sans-serif;background:#090d16;color:#f1f5f9;padding:40px;'>"
            "<h2 style='color:#38bdf8;'>MultiCloud Frontend Not Built</h2>"
            "<p>The compiled React bundle was not found in <code>src/web/dist</code>.</p>"
            "<p>To build it: <pre style='background:#1e293b;padding:12px;border-radius:6px;'>cd frontend && bun install && bun run build</pre></p>"
            "</body></html>"
        )
        return (
            fallback_html,
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    @app.route("/api/config", methods=["GET", "POST"])
    def handle_config() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        if request.method == "GET":
            return jsonify(br.get_active_config())

        body = request.get_json(silent=True) or {}
        if "section" in body and "data" in body:
            section = body.get("section")
            data = body.get("data", {})
            if not section or not isinstance(data, dict):
                return jsonify({"error": "Missing 'section' or 'data'"}), 400
            ok = br.save_config_section(section, data)
            return jsonify({"success": ok})

        # Multi-section dict payload
        saved = True
        for sec, val in body.items():
            if isinstance(val, dict) and not br.save_config_section(sec, val):
                saved = False
        return jsonify({"success": saved})

    @app.route("/api/inspect", methods=["POST"])
    def handle_inspect() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        body = request.get_json(silent=True) or {}
        target = body.get("target", "")
        return jsonify(br.inspect_target(target))

    @app.route("/api/transfers", methods=["GET"])
    def handle_transfers() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        return jsonify(br.get_transfers())

    @app.route("/api/download", methods=["POST"])
    def handle_download() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        body = request.get_json(silent=True) or {}
        target = body.get("target", "")
        if not target:
            return jsonify({"error": "Target URL or path is required"}), 400

        output_dir = body.get("output_dir")
        concurrency = int(body.get("concurrency", 4))
        mirror = body.get("mirror")
        notify = bool(body.get("notify", False))

        tid = br.start_download(
            target=target,
            output_dir=output_dir,
            concurrency=concurrency,
            mirror=mirror,
            notify=notify,
        )
        return jsonify({"transfer_id": tid})

    @app.route("/api/upload", methods=["POST"])
    def handle_upload() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        local_path = ""
        provider = "gofile"
        remote_path = ""
        notify = False

        if "file" in request.files:
            file_obj = request.files["file"]
            if not file_obj or not file_obj.filename:
                return jsonify({"error": "No file selected"}), 400

            upload_dir = Path(tempfile.gettempdir()) / "multicloud_uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            safe_name = (
                secure_filename(file_obj.filename) or f"upload_{int(time.time())}.bin"
            )
            save_path = upload_dir / safe_name
            file_obj.save(str(save_path))
            local_path = str(save_path)

            provider = request.form.get("provider", "gofile")
            remote_path = request.form.get("folder_id") or request.form.get(
                "remote_path", ""
            )
            notify = request.form.get("notify", "").lower() in ("true", "1", "yes")
        else:
            body = request.get_json(silent=True) or request.form.to_dict() or {}
            local_path = body.get("local_path", "")
            if not local_path:
                return jsonify(
                    {"error": "local_path or uploaded file is required"}
                ), 400

            provider = body.get("provider", "gofile")
            remote_path = body.get("folder_id") or body.get("remote_path", "")
            notify = bool(body.get("notify", False))

        if app.config.get("VERBOSE", 0) > 0:
            logger.info(
                f"Upload initiated: local_path={local_path!r}, provider={provider}, "
                f"remote_path={remote_path or 'root'}, notify={notify}"
            )

        try:
            tid = br.start_upload(
                local_path=local_path,
                provider=provider,
                remote_path=remote_path,
                notify=notify,
            )
            return jsonify({"transfer_id": tid})
        except Exception as e:
            logger.error(f"Failed to start upload for {local_path}: {e}")
            return jsonify({"error": str(e)}), 400

    @app.route("/api/transfers/<tid>/pause", methods=["POST"])
    def handle_pause(tid: str) -> Any:
        br: WebBridge = app.config["BRIDGE"]
        ok = br.pause_transfer(tid)
        return jsonify({"success": ok})

    @app.route("/api/transfers/<tid>/resume", methods=["POST"])
    def handle_resume(tid: str) -> Any:
        br: WebBridge = app.config["BRIDGE"]
        ok = br.resume_transfer(tid)
        return jsonify({"success": ok})

    @app.route("/api/transfers/<tid>/cancel", methods=["POST"])
    def handle_cancel(tid: str) -> Any:
        br: WebBridge = app.config["BRIDGE"]
        ok = br.cancel_transfer(tid)
        return jsonify({"success": ok})

    @app.route("/api/open", methods=["POST"])
    def handle_open() -> Any:
        br: WebBridge = app.config["BRIDGE"]
        body = request.get_json(silent=True) or {}
        p = body.get("path", "")
        ok = br.open_path(p)
        return jsonify({"success": ok})

    @app.route("/api/events")
    def handle_events() -> Response:
        br: WebBridge = app.config["BRIDGE"]
        verbosity = app.config.get("VERBOSE", 0)
        if verbosity > 0:
            logger.info(
                f"SSE client connected from {request.remote_addr or '127.0.0.1'}"
            )

        @stream_with_context
        def event_stream() -> Any:
            event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)

            def listener(payload: dict[str, Any]) -> None:
                try:
                    event_queue.put_nowait(payload)
                except queue.Full:
                    pass

            br.subscribe(listener)
            try:
                yield ": connected\n\n"
                initial_transfers = br.get_transfers()
                yield f"event: init\ndata: {json.dumps(initial_transfers)}\n\n"

                while True:
                    try:
                        event = event_queue.get(timeout=20.0)
                        event_type = event.get("type", "message")
                        event_data = event.get("data", event)
                        yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
                    except queue.Empty:
                        yield ": ping\n\n"
            except GeneratorExit:
                pass
            finally:
                br.unsubscribe(listener)
                if verbosity > 0:
                    logger.info(
                        f"SSE client disconnected from {request.remote_addr or '127.0.0.1'}"
                    )

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    open_browser: bool = True,
    bridge: WebBridge | None = None,
    verbose: int = 0,
) -> None:
    """Launch multi-threaded Flask server with rich terminal banner."""
    setup_logging(verbose)
    active_bridge = bridge or WebBridge()
    app = create_app(active_bridge, verbose=verbose)

    lan_ip = get_lan_ip()
    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan_ip}:{port}"

    console = Console()
    console.print(
        Panel(
            f"[bold green]MultiCloud Transfer Manager Web Server Active[/bold green]\n\n"
            f"  ➜ [bold cyan]Local:[/bold cyan]    [link={local_url}]{local_url}[/link]\n"
            f"  ➜ [bold cyan]Network:[/bold cyan]  [link={lan_url}]{lan_url}[/link]\n\n"
            f"[dim]Flask server with Tailwind CSS & shadcn components.[/dim]\n"
            f"[dim]Press [bold]Ctrl+C[/bold] to stop server.[/dim]",
            title="⚡ MultiCloud Web App",
            border_style="cyan",
        )
    )

    if open_browser:
        try:
            webbrowser.open(local_url)
        except Exception as e:
            logger.debug(f"Could not auto-open browser: {e}")

    try:
        run_simple(host, port, app, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping MultiCloud web server...[/yellow]")
