"""
Bhasha Shiksha Setu — Flask application factory.
Run:  python run.py   (from the project root)
"""
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.config import Config
from backend.database import init_db


def create_app(config_object=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)
    # Re-read env at startup so runtime overrides (tests, Docker) always win.
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        os.getenv("DATABASE_URL") or app.config["SQLALCHEMY_DATABASE_URI"])
    app.config["UPLOAD_DIR"] = os.getenv("UPLOAD_DIR") or app.config["UPLOAD_DIR"]

    # CORS — controlled by the CORS_ORIGINS env var
    origins = [o.strip() for o in app.config["CORS_ORIGINS"].split(",") if o.strip()]
    CORS(app, origins=origins if origins and origins != ["*"] else "*",
         allow_headers=["Content-Type", "Authorization", "X-Guest-Id"])

    # Security-minded simple headers
    @app.after_request
    def add_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    # Register blueprints
    from backend.routes import admin, auth, content, student, teacher, tutor, voice
    for bp in (auth.bp, content.bp, student.bp, teacher.bp, tutor.bp, voice.bp,
               admin.bp, admin.alias_bp):
        app.register_blueprint(bp)

    # Serve the static sites (frontend + admin)
    _serve_sites(app)

    # Global error handler — users always see friendly messages
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "Endpoint not found."}), 404
        return jsonify({"success": False, "message": "Page not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.path.startswith("/api/"):
            return jsonify({"success": False,
                            "message": "Method not allowed for this endpoint."}), 405
        return not_found(e)

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"success": False,
                        "message": "Upload too large (max {:.0f} MB).".format(
                            app.config["MAX_CONTENT_LENGTH"] / 1024 / 1024)}), 413

    @app.errorhandler(Exception)
    def server_error(e):
        app.logger.error("Unhandled error: %s", e)
        return jsonify({"success": False,
                        "message": "Something went wrong. Please try again."}), 500

    init_db(app)
    return app


def _serve_sites(app):
    """Serve frontend/ (root + /student /teacher /tutor) and admin/ (/admin)."""
    import os

    from flask import send_from_directory

    frontend_dir = str(app.config["FRONTEND_DIR"])
    admin_dir = str(app.config["ADMIN_DIR"])

    @app.route("/")
    def home():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>")
    def site_files(path):
        # Never let static serving shadow API or admin routes
        if path.startswith("api/") or path.startswith("admin/api/"):
            return jsonify({"success": False, "message": "Endpoint not found."}), 404
        if path == "admin" or path.startswith("admin/"):
            rel = path[len("admin/"):] if path.startswith("admin/") else ""
            if not rel:
                return send_from_directory(admin_dir, "login.html")
            full = os.path.join(admin_dir, rel)
            if os.path.isfile(full):
                return send_from_directory(admin_dir, rel)
            return send_from_directory(admin_dir, "login.html")
        if path.startswith("uploads/"):
            return send_from_directory(app.config["UPLOAD_DIR"], os.path.basename(path))
        full = os.path.join(frontend_dir, path)
        if os.path.isfile(full):
            return send_from_directory(frontend_dir, path)
        # SPA-friendly fallback for mode pages
        if path in ("student", "teacher", "tutor", "student.html", "teacher.html", "tutor.html"):
            return send_from_directory(frontend_dir, f"{path.split('.')[0]}.html")
        return jsonify({"success": False, "message": "Page not found."}), 404


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
