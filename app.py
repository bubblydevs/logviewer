__version__ = "1.1.2"

import html
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic, response
from sanic.exceptions import NotFound
from jinja2 import Environment, FileSystemLoader

load_dotenv()

from core import auth, dashboard
from core.models import LogEntry

if "URL_PREFIX" in os.environ:
    print("Using the legacy config var `URL_PREFIX`, rename it to `LOG_URL_PREFIX`")
    prefix = os.environ["URL_PREFIX"]
else:
    prefix = os.getenv("LOG_URL_PREFIX", "/logs")

if prefix == "NONE":
    prefix = ""

# Parse multiple database mapping or fallback to single database
DATABASE_MAPPING_STR = os.getenv("DATABASE_MAPPING", "")
DATABASE_MAPPING = {}

if DATABASE_MAPPING_STR.strip():
    # Parse DATABASE_MAPPING format: path1=uri1,path2=uri2,path3=uri3
    for mapping in DATABASE_MAPPING_STR.split(","):
        if "=" in mapping:
            path, uri = mapping.split("=", 1)
            DATABASE_MAPPING[path.strip()] = uri.strip()

# If no mapping provided, use legacy single database setup
if not DATABASE_MAPPING:
    MONGO_URI = os.getenv("MONGO_URI") or os.getenv("CONNECTION_URI")
    if not MONGO_URI:
        print("No CONNECTION_URI or DATABASE_MAPPING config var found. "
              "Please enter your MongoDB connection URI in the configuration or .env file.")
        exit(1)
else:
    MONGO_URI = None  # Will use mapping instead

app = Sanic(__name__)
app.static("/static", "./static")

jinja_env = Environment(loader=FileSystemLoader("templates"))


def render_template(name, *args, **kwargs):
    template = jinja_env.get_template(name + ".html")
    kwargs.setdefault("auth_enabled", auth.AUTH_ENABLED)
    kwargs.setdefault("user", auth.current_user.get())
    return response.html(template.render(*args, **kwargs))


app.ctx.render_template = render_template

if auth.AUTH_ENABLED:
    app.blueprint(auth.bp)

    @app.on_request
    async def require_login(request):
        return await auth.auth_middleware(request, prefix)

    @app.on_response
    async def refresh_session(request, resp):
        await auth.refresh_session_middleware(request, resp)


def strtobool(val):
    """
    Copied from distutils.strtobool.

    Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


JAVA_BRANDING = strtobool(os.getenv("JAVA_BRANDING", "no"))
jinja_env.globals.update(
    java_branding=JAVA_BRANDING,
    java_logo_url=os.getenv(
        "JAVA_LOGO_URL",
        "https://payhip.com/cdn-cgi/image/format=auto,width=1500/https://pe56d.s3.amazonaws.com/o_1hkesjldmd5bk2917qcavsq0uu.png",
    ),
    java_policy_url=os.getenv(
        "JAVA_POLICY_URL",
        "https://docs.google.com/document/d/1BwLS66KzTESwoaGdqKYqJysGHHBW4-jqWvM3920O9yQ/edit?tab=t.0",
    ),
)


async def get_db(app, log_path=None):
    """Get the appropriate database for the given log path.
    
    If using DATABASE_MAPPING mode, route to the specific database.
    If using legacy mode, always return the default database.
    """
    if DATABASE_MAPPING and log_path in DATABASE_MAPPING:
        # Reuse one client per mapped database instead of connecting on every request
        if log_path not in app.ctx.mapped_dbs:
            app.ctx.mapped_dbs[log_path] = AsyncIOMotorClient(DATABASE_MAPPING[log_path]).modmail_bot
        return app.ctx.mapped_dbs[log_path]
    elif not DATABASE_MAPPING and MONGO_URI:
        # Legacy single database mode
        return app.ctx.db
    else:
        raise NotFound


@app.listener("before_server_start")
async def init(app, loop):
    # In legacy mode, create a single connection
    if not DATABASE_MAPPING and MONGO_URI:
        app.ctx.db = AsyncIOMotorClient(MONGO_URI).modmail_bot
    else:
        # In mapping mode, connections are created lazily by get_db
        app.ctx.db = None
    app.ctx.mapped_dbs = {}
    
    use_attachment_proxy = strtobool(os.getenv("USE_ATTACHMENT_PROXY", "no"))
    if use_attachment_proxy:
        app.ctx.attachment_proxy_url = os.getenv("ATTACHMENT_PROXY_URL", "https://cdn.discordapp.xyz")
        app.ctx.attachment_proxy_url = html.escape(app.ctx.attachment_proxy_url).rstrip("/")
    else:
        app.ctx.attachment_proxy_url = None

@app.exception(NotFound)
async def not_found(request, exc):
    return render_template("not_found")


@app.get("/")
async def index(request):
    user = getattr(request.ctx, "user", None)
    if not (auth.AUTH_ENABLED and user):
        return render_template("index")

    server_paths = list(DATABASE_MAPPING)
    filters = dashboard.parse_args(request.args, server_paths)

    if DATABASE_MAPPING:
        paths = [filters["server"]] if filters["server"] else server_paths
        sources = [(path, await get_db(app, log_path=path)) for path in paths]
    else:
        sources = [(None, await get_db(app))]

    tickets, has_next = await dashboard.list_tickets(
        sources, prefix, user["id"], filters["tab"], filters["status"], filters["q"], filters["page"]
    )

    return render_template(
        "dashboard",
        tickets=tickets,
        has_next=has_next,
        filters=filters,
        server_paths=server_paths,
        link=lambda **changes: dashboard.link(filters, **changes),
    )


@app.get(prefix + "/raw/<key>")
async def get_raw_logs_file(request, key):
    """Returns the plain text rendered log entry (legacy single database mode)"""
    db = await get_db(app)
    document = await db.logs.find_one({"key": key})

    if document is None:
        raise NotFound

    log_entry = LogEntry(app, document)
    return log_entry.render_plain_text()


@app.get(prefix + "/raw/<log_path>/<key>")
async def get_raw_logs_file_mapped(request, log_path, key):
    """Returns the plain text rendered log entry (multi-database mode)"""
    db = await get_db(app, log_path=log_path)
    document = await db.logs.find_one({"key": key})

    if document is None:
        raise NotFound

    log_entry = LogEntry(app, document)
    return log_entry.render_plain_text()


@app.get(prefix + "/<key>")
async def get_logs_file(request, key):
    """Returns the html rendered log entry (legacy single database mode)"""
    db = await get_db(app)
    document = await db.logs.find_one({"key": key})

    if document is None:
        raise NotFound

    log_entry = LogEntry(app, document)
    return log_entry.render_html()


@app.get(prefix + "/<log_path>/<key>")
async def get_logs_file_mapped(request, log_path, key):
    """Returns the html rendered log entry (multi-database mode)"""
    db = await get_db(app, log_path=log_path)
    document = await db.logs.find_one({"key": key})

    if document is None:
        raise NotFound

    log_entry = LogEntry(app, document)
    return log_entry.render_html()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=os.getenv("PORT", 8000),
        debug=bool(os.getenv("DEBUG", False)),
    )
