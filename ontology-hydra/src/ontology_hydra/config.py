import tomllib
from enum import StrEnum
from pathlib import Path
from shutil import copyfile

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class ComponentName(StrEnum):
    draft_ops = "draft_ops"
    kg_extractor = "kg_extractor"
    planner = "planner"
    review_ops = "review_ops"
    generate_title = "generate_title"


class ProviderConfig(_Model):
    api_key: str


class ComponentConfig(_Model):
    provider: str
    model: str

    kwargs: dict[str, object] | None = None


class HydraConfig(_Model):
    providers: dict[str, ProviderConfig]
    default: ComponentConfig
    components: dict[ComponentName, ComponentConfig] | None = None

    @model_validator(mode="after")
    def default_has_valid_provider(self):
        if self.default.provider not in self.providers:
            msg = f"Default has undefined provider: '{self.default.provider}'"
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def components_have_valid_providers(self):
        if self.components is None:
            return self

        for name, cfg in self.components.items():
            if cfg.provider not in self.providers:
                msg = f"Component '{name}' has undefined provider: '{cfg.provider}'"
                raise ValueError(msg)

        return self

    @field_validator("providers", mode="after")
    @classmethod
    def has_one_provider(cls, value: dict[str, ProviderConfig]):
        if len(value) == 0:
            msg = "No providers defined! Need to define at least one provider."
            raise ValueError(msg)

        return value

    def resolve_component(self, name: ComponentName):
        if self.components is None:
            return self.default

        return self.components.get(name, self.default)


def load_config(path: Path):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return HydraConfig.model_validate(data)


def example_config_path():
    return Path(__file__).resolve().parents[2] / "config.example.toml"


def init_config(path: Path):
    if path.exists():
        msg = f"Config already exists at {path}"
        raise FileExistsError(msg)
    example_path = example_config_path()
    if not example_path.exists():
        msg = f"Example config not found at {example_path}"
        raise FileNotFoundError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(example_path, path)
