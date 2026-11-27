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
MAX_DURATION = 3600


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Keyframe(Model):
    time: float = Field(ge=0, le=MAX_DURATION)
    location: Vec3 | None = None
    rotation: Vec3 | None = None
    scale: Vec3 | None = None
    visible: bool | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)


class Repetition(Model):
    count: int = Field(default=1, ge=1, le=500)
    offset: Vec3 = (0, 0, 0)
    rotation: Vec3 = (0, 0, 0)


class Object(Model):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["cube", "sphere", "cylinder", "cone", "torus", "plane", "text", "model", "image", "empty"]
    location: Vec3 = (0, 0, 1)
    rotation: Vec3 = (0, 0, 0)
    scale: Vec3 = (1, 1, 1)
    color: Color = "#4F8CFF"
    metallic: float = Field(default=0.15, ge=0, le=1)
    roughness: float = Field(default=0.35, ge=0, le=1)
    text: str = Field(default="", max_length=2000)
    asset: str | None = None
    asset_nodes: list[str] = Field(default_factory=list,max_length=200)
    asset_pivot: Vec3 = (0,0,0)
    recolor: Color | None = None
    transmission: float = Field(default=0,ge=0,le=1)
    bevel: float = Field(default=0,ge=0,le=1)
    parent: str | None = None
    visible: bool = True
    opacity: float = Field(default=1, ge=0, le=1)
    repeat: Repetition | None = None
    keyframes: list[Keyframe] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def required_asset(self):
        if self.kind in ("model", "image") and not self.asset:
            raise ValueError("model/image objects require an asset path")
        if self.asset and self.kind not in ('model','image'):
            raise ValueError("asset must be null for primitives/text/empty; text uses the video's font")
        return self


class Camera(Model):
    location: Vec3 = (7, -10, 6)
    target: Vec3 = (0, 0, 1)
    lens: float = Field(default=45, ge=10, le=200)
    projection: Literal['perspective', 'orthographic'] = 'perspective'
    ortho_scale: float = Field(default=10, gt=0, le=10000)
    end_location: Vec3 | None = None
    keyframes: list["CameraKeyframe"] = Field(default_factory=list, max_length=100)


class CameraKeyframe(Model):
    time: float = Field(ge=0, le=MAX_DURATION)
    location: Vec3
    target: Vec3
    lens: float = Field(default=45, ge=10, le=200)
    ortho_scale: float | None = Field(default=None, gt=0, le=10000)


class SpeechCue(Model):
    start: float = Field(ge=0, le=MAX_DURATION)
    end: float = Field(gt=0, le=MAX_DURATION)
    text: str = Field(min_length=1, max_length=15000)
    voice_id: str = "vi-VN-NamMinhNeural"
    rate: int = Field(default=0, ge=-50, le=100)
    audio: str | None = None

    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start:
            raise ValueError("Speech end must follow its start")
        return self


class SoundCue(Model):
    start: float = Field(ge=0, le=MAX_DURATION)
    end: float = Field(gt=0, le=MAX_DURATION)
    kind: Literal['chime','footstep','click','mechanical','whoosh','success','breath','pop','scan',
                  'bird','fly','water_drop']
    volume: float = Field(default=.35, ge=0, le=1)
    audio: str | None = None


class MusicCue(Model):
    start: float = Field(ge=0, le=MAX_DURATION)
    end: float = Field(gt=0, le=MAX_DURATION)
    style: Literal['playful','ambient','triumphant']
    volume: float = Field(default=1, ge=0, le=1)
    audio: str | None = None


class BoneKeyframe(Model):
    time: float = Field(ge=0, le=MAX_DURATION)
    rotation: Vec3


class Bone(Model):
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
    parent: str | None = None
    head: Vec3
    tail: Vec3
    objects: list[str] = Field(default_factory=list, max_length=100)
    rotation: Vec3 = (0, 0, 0)
    keyframes: list[BoneKeyframe] = Field(default_factory=list, max_length=100)


class Rig(Model):
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
    root: str
    bones: list[Bone] = Field(min_length=1, max_length=100)


class ElementPart(Model):
    name: str = Field(min_length=1, max_length=100)
    count: int = Field(default=1, ge=1, le=1000)


class GeometryElement(Model):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=3000)
    role: Literal['setting','character','prop','graphic']
    construction: Literal['geometry','asset','image','overlay'] = 'geometry'
    requirement_id: str | None = None
    asset_paths: list[str] = Field(default_factory=list,max_length=150)
    rigged: bool = False
    count: int = Field(default=1, ge=1, le=1000)
    appearance: str = Field(min_length=1, max_length=3000)
    parts: list[ElementPart] = Field(default_factory=list, max_length=40)


class ShotBrief(Model):
    title: str = Field(min_length=1, max_length=200)
    start: float = Field(ge=0, le=MAX_DURATION)
    end: float = Field(gt=0, le=MAX_DURATION)
    setting: str = Field(min_length=1, max_length=5000)
    actions: list[str] = Field(min_length=1, max_length=40)
    # Global video timestamps, so narration keeps its exact position across cuts.
    narration: list[SpeechCue] = Field(default_factory=list, max_length=100)
    animate: bool = True
    elements: list[GeometryElement] = Field(default_factory=list, max_length=60)


class ActionBinding(Model):
    action_index: int = Field(ge=0, le=39)
    objects: list[str] = Field(min_length=1, max_length=50)
    start: float = Field(ge=0, le=MAX_DURATION)
    end: float = Field(gt=0, le=MAX_DURATION)
    elements: list[str] = Field(default_factory=list, max_length=60)


class PartBinding(Model):
    part: str = Field(min_length=1, max_length=100)
    objects: list[str] = Field(min_length=1, max_length=100)


class ElementBinding(Model):
    element_id: str
    objects: list[str] = Field(min_length=1, max_length=100)
    parts: list[PartBinding] = Field(default_factory=list, max_length=40)


class AreaLight(Model):
    location: Vec3 = (2, -4, 8)
    energy: float = Field(default=1800, ge=0, le=100000)
    size: float = Field(default=6, gt=0, le=100)
    color: Color = "#FFFFFF"


class ShotDesign(Model):
    background: Color = "#101828"
    floor: Color = "#202C40"
    ground: bool = True
    ambient: float = Field(default=.5, ge=0, le=10)
    lights: list[AreaLight] = Field(default_factory=lambda: [AreaLight(location=(2,-4,8)), AreaLight(location=(-5,-1,5),energy=1200), AreaLight(location=(2,5,6),energy=2200)], max_length=10)
    camera: Camera = Field(default_factory=Camera)
    objects: list[Object] = Field(min_length=1, max_length=150)
    rigs: list[Rig] = Field(default_factory=list, max_length=30)
    bindings: list[ActionBinding] = Field(default_factory=list, max_length=100)
    element_bindings: list[ElementBinding] = Field(default_factory=list, max_length=60)


class Shot(ShotBrief, ShotDesign):
    pass


class VideoPlan(Model):
    title: str = Field(max_length=200)
    duration: float = Field(gt=0, le=MAX_DURATION)
    fps: int = Field(default=24, ge=1, le=60)
    width: int = Field(default=540, ge=64, le=3840, multiple_of=2)
    height: int = Field(default=960, ge=64, le=3840, multiple_of=2)
    style: str = Field(max_length=5000)
    characters: list[str] = Field(default_factory=list, max_length=30)
    music: str | None = None
    music_style: Literal['none','playful','ambient','triumphant'] = 'none'
    music_cues: list[MusicCue] = Field(default_factory=list, max_length=100)
    export_assets: bool = False
    effects: list[SoundCue] = Field(default_factory=list, max_length=200)
    font: str | None = None
    captions: bool = False
    voice_volume: float = Field(default=1, ge=0, le=2)
    music_volume: float = Field(default=.2, ge=0, le=1)
    duck_music: bool = True
    unsupported: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    shots: list[ShotBrief] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def schedule(self):
        validate_shots(self.shots, self.duration)
        if any(not 0 <= effect.start < effect.end <= self.duration for effect in self.effects):
            raise ValueError("Sound effects must fit the video timeline")
        validate_music(self.music_cues, self.duration)
        return self


def validate_music(cues, duration):
    previous = 0
    for cue in sorted(cues, key=lambda item: item.start):
        if not 0 <= cue.start < cue.end <= duration or cue.start < previous:
            raise ValueError('Music cues must have non-overlapping intervals within the video')
        previous = cue.end


def validate_rigs(rigs, objects, duration):
    from .geometry import descendants
    lookup = {obj.name: obj for obj in objects}
    names, bound = set(lookup), set()
    templates = [obj.model_dump(mode='json') for obj in objects]
    for rig in rigs:
        if rig.name in names or rig.root not in lookup or lookup[rig.root].kind != 'empty':
            raise ValueError('Rig needs a unique name and an existing empty root')
        names.add(rig.name)
        bones = {bone.name: bone for bone in rig.bones}
        if len(bones) != len(rig.bones):
            raise ValueError('Bone names must be unique within a rig')
        owned = descendants(templates, [rig.root])
        for bone in rig.bones:
            if sum((a-b)**2 for a,b in zip(bone.head,bone.tail)) < .000001:
                raise ValueError('Bone head and tail must differ')
            chain, parent = {bone.name}, bone.parent
            while parent is not None:
                if parent not in bones or parent in chain:
                    raise ValueError('Bone parents must exist and must not form cycles')
                chain.add(parent)
                parent = bones[parent].parent
            for name in bone.objects:
                if name not in owned or lookup[name].kind not in {'cube','sphere','cylinder','cone','torus','plane','model'}:
                    raise ValueError('Bones must bind mesh geometry inside their rig root')
                if name in bound:
                    raise ValueError('A geometry object may bind to only one bone')
                if lookup[name].repeat:
                    raise ValueError('Rigged geometry cannot use repeat recipes')
                bound.add(name)
            times = [key.time for key in bone.keyframes]
            if len(times) != len(set(times)) or any(time > duration for time in times):
                raise ValueError('Bone keys must have unique times within the shot')
        if any(lookup[name].repeat for name in owned):
            raise ValueError('Rig roots and their descendants cannot use repeat recipes')


def validate_shots(shots, duration):
    cursor = 0
    for shot in shots:
        if abs(shot.start - cursor) > .001 or shot.end <= shot.start:
            raise ValueError("Shots must form a continuous timeline starting at zero")
        for cue in shot.narration:
            if cue.start < shot.start or cue.end > shot.end:
                raise ValueError("Narration must fit its shot's video timestamps")
        cursor = shot.end
    if abs(cursor - duration) > .001:
        raise ValueError("Last shot must end at the full video duration")


def validate_objects(objects, camera, duration):
    from .geometry import expand_objects
    expand_objects([obj.model_dump(mode='json') for obj in objects])
    names = {obj.name for obj in objects}
    if len(names) != len(objects):
        raise ValueError("Object names must be unique within a shot")
    parents = {obj.name: obj.parent for obj in objects}
    for obj in objects:
        chain = {obj.name}
        parent = obj.parent
        while parent is not None:
            if parent not in names or parent in chain:
                raise ValueError("Object parents must exist and must not form cycles")
            chain.add(parent)
            parent = parents[parent]
        times = [key.time for key in obj.keyframes]
        if len(times) != len(set(times)) or any(t > duration for t in times):
            raise ValueError("Object keyframes must have unique times within the shot duration")
    times = [key.time for key in camera.keyframes]
    if len(times) != len(set(times)) or any(t > duration for t in times):
        raise ValueError("Camera keyframes must have unique times within the shot duration")


class SceneSpec(Model):
    title: str = Field(default="Codex Blender Video", max_length=200)
    prompt: str = Field(default="", max_length=70002)
    content: str = Field(default="", max_length=50000)
    duration: float = Field(default=5, ge=0.1, le=MAX_DURATION)
    fps: int = Field(default=24, ge=1, le=60)
    width: int = Field(default=1280, ge=64, le=3840, multiple_of=2)
    height: int = Field(default=720, ge=64, le=3840, multiple_of=2)
    background: Color = "#101828"
    floor: Color = "#202C40"
    ground: bool = True
    camera: Camera = Field(default_factory=Camera)
    objects: list[Object] = Field(default_factory=list, max_length=150)
    rigs: list[Rig] = Field(default_factory=list, max_length=30)
    shots: list[Shot] = Field(default_factory=list, max_length=60)
    captions: bool = False
    audio: str | None = None
    audio_mode: Literal['full','music_only'] = 'full'
    font: str | None = None
    voice_audio: str | None = None
    music: str | None = None
    music_style: Literal['none','playful','ambient','triumphant'] = 'none'
    music_cues: list[MusicCue] = Field(default_factory=list, max_length=100)
    export_assets: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=30)
    effects: list[SoundCue] = Field(default_factory=list, max_length=200)
    voice_volume: float = Field(default=1, ge=0, le=2)
    music_volume: float = Field(default=0.2, ge=0, le=1)
    duck_music: bool = True
    samples: int = Field(default=16, ge=1, le=256)
    subtitles: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def timeline(self):
        validate_music(self.music_cues, self.duration)
        if any(not 0 <= effect.start < effect.end <= self.duration for effect in self.effects):
            raise ValueError("Sound effects must fit the video timeline")
        if self.shots:
            if self.objects or self.rigs:
                raise ValueError("Use shots or legacy objects/rigs, not both")
            validate_shots(self.shots, self.duration)
            for shot in self.shots:
                validate_objects(shot.objects, shot.camera, shot.end - shot.start)
                validate_rigs(shot.rigs, shot.objects, shot.end - shot.start)
        else:
            if not self.objects:
                raise ValueError("A video must contain shots or objects")
            validate_objects(self.objects, self.camera, self.duration)
            validate_rigs(self.rigs, self.objects, self.duration)
        return self
