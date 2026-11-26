from typing import Literal
from mcp.server.fastmcp import FastMCP, Image

from .config import ASSETS, OUTPUTS, blender_command, assets_dir
from .models import SceneSpec
from .jobs import submit, status, job_path
from .library import catalog

INSTRUCTIONS = """You direct Blender videos from the user's prompt and supplied content.
First call blender_info and list_assets. Convert the user's intent to a SceneSpec using
scene_schema. Preserve supplied wording and use assets only from list_assets. Report
limitations honestly: this renderer supports primitives, extruded text, image planes,
GLB models, transform animation, a moving camera, studio lighting and optional audio;
it does not synthesize footage, voice, rigged characters or arbitrary Blender code.
Z is up; camera looks toward target. Rotations are degrees. Text lies in local XY:
use rotation [90,0,0] to face a camera on negative Y. All keyframes are in seconds.
Use multiple objects and keyframes to make a coherent composition, with readable text.
Generate preview first, poll video_job_status, then inspect video_preview. If the
user requested a video, continue to submit mode=video and poll to completion without
asking again. Use small resolution and short duration while iterating. Return the
absolute output paths. Do not claim completion on submission alone.
"""

mcp = FastMCP("codex-blender", instructions=INSTRUCTIONS)


@mcp.tool()
def blender_info() -> dict:
    """Check Blender availability and renderer capabilities before creating a video."""
    try:
        command, error = blender_command(), None
    except (RuntimeError, ValueError) as exc:
        command, error = None, str(exc)
    return {"ready": command is not None, "command": command, "error": error,
            "assets_directory": str(assets_dir()), "output_directory": str(OUTPUTS),
            "limits": {"duration_seconds": 120, "max_objects": 150, "max_side_pixels": 3840},
            "instructions": INSTRUCTIONS}


@mcp.tool()
def list_assets() -> list[dict]:
    """List user supplied image, GLB model, audio and font files in assets/."""
    return catalog()


@mcp.tool()
def scene_schema() -> dict:
    """Get the complete validated SceneSpec schema and animation fields."""
    return SceneSpec.model_json_schema()


@mcp.tool()
def create_video(scene: SceneSpec, mode: Literal["preview", "video"] = "preview") -> dict:
    """Build a Blender scene and start a background preview/video job. Poll status using returned id.

    Codex must turn the user's prompt/content into the structured scene argument.
    Include the original user prompt/content in their metadata fields; the renderer
    executes objects/keyframes, not free-form text. Preview mode returns PNG + .blend;
    video mode also encodes H.264 MP4 with optional audio. No API key is required here.
    """
    return submit(scene, mode)


@mcp.tool()
def video_job_status(job_id: str) -> dict:
    """Read render progress, failure details and absolute artifact paths."""
    return status(job_id)


@mcp.tool()
def video_preview(job_id: str) -> Image:
    """Read the rendered preview image for visual inspection."""
    path = job_path(job_id) / "preview.png"
    if not path.is_file():
        raise ValueError("Preview is not ready; check video_job_status")
    return Image(path=str(path))


@mcp.tool()
def video_job_log(job_id: str) -> str:
    """Read the last 12000 characters of a render log to diagnose errors."""
    path = job_path(job_id) / "render.log"
    if not path.exists():
        return "Log not available yet"
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 12000))
        return stream.read().decode("utf-8", errors="replace")


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
