"""Declarative scene format. No user supplied Python is executed."""
import math
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


def finite(value: float) -> float:
    if not math.isfinite(value) or abs(value) > 100000:
        raise ValueError("Coordinates must be finite and within +/-100000")
    return value


Number = Annotated[float, AfterValidator(finite)]
Vec3 = tuple[Number, Number, Number]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Keyframe(Model):
    time: float = Field(ge=0, le=120)
    location: Vec3 | None = None
    rotation: Vec3 | None = None
    scale: Vec3 | None = None


class Object(Model):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["cube", "sphere", "cylinder", "cone", "torus", "plane", "text", "model", "image"]
    location: Vec3 = (0, 0, 1)
    rotation: Vec3 = (0, 0, 0)
    scale: Vec3 = (1, 1, 1)
    color: Color = "#4F8CFF"
    metallic: float = Field(default=0.15, ge=0, le=1)
    roughness: float = Field(default=0.35, ge=0, le=1)
    text: str = Field(default="", max_length=2000)
    asset: str | None = None
    keyframes: list[Keyframe] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def required_asset(self):
        if self.kind in ("model", "image") and not self.asset:
            raise ValueError("model/image objects require an asset path")
        return self


class Camera(Model):
    location: Vec3 = (7, -10, 6)
    target: Vec3 = (0, 0, 1)
    lens: float = Field(default=45, ge=10, le=200)
    end_location: Vec3 | None = None


class SceneSpec(Model):
    title: str = Field(default="Codex Blender Video", max_length=200)
    prompt: str = Field(default="", max_length=20000)
    content: str = Field(default="", max_length=50000)
    duration: float = Field(default=5, ge=0.1, le=120)
    fps: int = Field(default=24, ge=1, le=60)
    width: int = Field(default=1280, ge=64, le=3840, multiple_of=2)
    height: int = Field(default=720, ge=64, le=3840, multiple_of=2)
    background: Color = "#101828"
    floor: Color = "#202C40"
    camera: Camera = Field(default_factory=Camera)
    objects: list[Object] = Field(min_length=1, max_length=150)
    audio: str | None = None
    font: str | None = None
    voice_audio: str | None = None
    music: str | None = None
    voice_volume: float = Field(default=1, ge=0, le=2)
    music_volume: float = Field(default=0.2, ge=0, le=1)
    duck_music: bool = True
    samples: int = Field(default=16, ge=1, le=256)
    subtitles: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def timeline(self):
        names = [obj.name for obj in self.objects]
        if len(names) != len(set(names)):
            raise ValueError("Object names must be unique")
        for obj in self.objects:
            times = [k.time for k in obj.keyframes]
            if len(times) != len(set(times)):
                raise ValueError("Keyframe times must be unique per object")
            if any(t > self.duration for t in times):
                raise ValueError("Keyframes must be inside the video duration")
        return self
