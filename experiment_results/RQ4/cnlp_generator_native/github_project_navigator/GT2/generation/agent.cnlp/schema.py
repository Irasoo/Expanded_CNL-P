from __future__ import annotations

from typing import Any, Literal
from typing_extensions import NotRequired, TypedDict


WriteOperation = Literal["SET", "APPEND"]
HistoryRole = Literal["system", "user", "assistant"]


class CNLPVariableInfo(TypedDict):
    """Configuration required to initialize one CNL-P variable."""

    variable_name: str
    # config.py imports generated types from schema.py and stores the actual
    # Python type object here.
    value_type: Any
    default_value: Any


class HistorySection(TypedDict):
    role: HistoryRole
    content: str


class ModelConfig(TypedDict):
    api_key: str
    model_name: str
    base_url: NotRequired[str | None]


class AgentConfig(TypedDict):
    variable_config: list[CNLPVariableInfo]
    agent_attributes: str
    model_config: ModelConfig


class BooleanResponse(TypedDict):
    result: bool


# CNL-P declared types are appended below this static section by the
# Native schema generator.

from typing import Literal, TypeAlias
from typing_extensions import NotRequired, TypedDict

InputKind: TypeAlias = Literal['repository_url', 'repository_name', 'unclear']

ReleaseAnalysisMode: TypeAlias = Literal['overview', 'asset_match']

OperatingSystem: TypeAlias = Literal['windows', 'macos', 'linux', 'other']

ProcessorArchitecture: TypeAlias = Literal['x64', 'arm64', 'unknown']

PackagePreference: TypeAlias = Literal['installer', 'portable', 'archive', 'any']

ReleaseAdviceStatus: TypeAlias = Literal['overview', 'recommended', 'no_match']

class SelectedRepository(TypedDict):
    owner: str
    repository: str
    repository_url: str

class ProjectOverview(TypedDict):
    found: bool
    full_name: str
    repository_url: str
    description: str
    readme: str
    license: str
    primary_language: str
    topics: list[str]
    stars: int | float
    forks: int | float
    open_issues: int | float
    archived: bool
    updated_at: str

class IssueInformationResult(TypedDict):
    analyzed_issue_count: int | float
    issues: list[str]

class IssueAnalysisResult(TypedDict):
    analyzed_issue_count: int | float
    common_problems: list[str]
    confirmed_problems: list[str]
    unresolved_problems: list[str]
    representative_issues: list[str]
    limitations: list[str]

class ReleaseRequest(TypedDict):
    analysis_mode: 'ReleaseAnalysisMode'
    operating_system: NotRequired['OperatingSystem']
    architecture: NotRequired['ProcessorArchitecture']
    package_preference: NotRequired['PackagePreference']

class ReleaseAsset(TypedDict):
    name: str
    download_url: str
    size: int | float
    digest: str

class ReleaseInformation(TypedDict):
    version: str
    release_name: str
    release_notes: str
    published_at: str
    assets: list['ReleaseAsset']
    source_zip_url: str
    source_tar_url: str

class AssetSelection(TypedDict):
    found: bool
    asset: NotRequired['ReleaseAsset']
    reason: str

class ReleaseAdvice(TypedDict):
    status: 'ReleaseAdviceStatus'
    version: str
    asset: NotRequired['ReleaseAsset']
    summary: str
    acquisition_url: str
    integrity_guidance: str
    limitations: list[str]
