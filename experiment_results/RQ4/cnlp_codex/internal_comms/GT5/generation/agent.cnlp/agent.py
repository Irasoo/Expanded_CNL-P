from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, TypedDict

from communication_api import (
    classify_communication_type,
    draft_company_newsletter,
    draft_faq,
    draft_general_comms,
    draft_three_p,
    parse_general_comms_request,
)
from llm_runtime import LLMRuntime


CommunicationType = Literal["three_p", "newsletter", "faq", "general", "unknown"]


class GeneralCommsRequest(TypedDict):
    target_audience: str
    purpose: str
    tone: str
    format_requirement: str


@dataclass
class AgentState:
    communication_type: CommunicationType = "unknown"
    team_name: str = ""
    three_p_materials: str = ""
    newsletter_materials: str = ""
    faq_request: str = ""
    general_comms_request: GeneralCommsRequest = field(
        default_factory=lambda: {
            "target_audience": "",
            "purpose": "",
            "tone": "",
            "format_requirement": "",
        }
    )
    general_comms_materials: str = ""
    final_communication: str = ""


class InternalCommsAssistant:
    def __init__(self, llm: LLMRuntime) -> None:
        self.llm = llm
        self.state = AgentState()
        self.logger = logging.getLogger("internal_comms_assistant")

    @staticmethod
    def _input_once(message: str) -> str:
        print(message)
        return input("> ")

    @staticmethod
    def _display(value: str) -> None:
        print(value)

    def run(self) -> str | None:
        return self._internal_comms_dispatcher()

    def _internal_comms_dispatcher(self) -> str | None:
        selection = self._input_once(
            "Select the internal communication type to generate "
            "(three_p, newsletter, faq, or general)."
        )
        classified = classify_communication_type(self.llm, selection)
        self.state.communication_type = classified  # validated finite value domain

        if self.state.communication_type == "unknown":
            self.logger.warning(
                "The internal communication type selected by the user cannot be recognized"
            )
            self._display(
                "The selected communication type cannot be recognized. "
                "Supported types are three_p, newsletter, faq, and general."
            )
            return None

        if self.state.communication_type == "three_p":
            self.state.final_communication = self._three_p_writer()
        elif self.state.communication_type == "newsletter":
            self.state.final_communication = self._newsletter_writer()
        elif self.state.communication_type == "faq":
            self.state.final_communication = self._faq_writer()
        else:
            self.state.final_communication = self._general_comms_writer()

        return self.state.final_communication

    def _three_p_writer(self) -> str:
        self.state.three_p_materials = self._input_once(
            "Provide the team update materials to organize into a 3P update."
        )
        self.state.team_name = self._input_once(
            "Provide the name of the team covered by this 3P update."
        )
        result = draft_three_p(
            self.llm,
            team_name=self.state.team_name,
            source_materials=self.state.three_p_materials,
        )
        self._display(result)
        return result

    def _newsletter_writer(self) -> str:
        self.state.newsletter_materials = self._input_once(
            "Provide announcements, important developments, team updates, milestones, "
            "meeting summaries, public reports, or other relevant newsletter materials."
        )
        result = draft_company_newsletter(
            self.llm, source_materials=self.state.newsletter_materials
        )
        self._display(result)
        return result

    def _faq_writer(self) -> str:
        self.state.faq_request = self._input_once(
            "Provide the internal FAQ request, including the questions to answer and "
            "any relevant reference materials."
        )
        result = draft_faq(self.llm, request=self.state.faq_request)
        self._display(result)
        return result

    def _general_comms_writer(self) -> str:
        raw_request = self._input_once(
            "Provide the target audience, communication purpose, desired tone, and "
            "format requirement in one response."
        )
        parsed_request = parse_general_comms_request(self.llm, raw_request)
        self.state.general_comms_request = GeneralCommsRequest(**parsed_request)
        self.state.general_comms_materials = self._input_once(
            "Provide the announcements, background information, project updates, "
            "meeting content, reference text, or other materials for the communication."
        )
        result = draft_general_comms(
            self.llm,
            request=self.state.general_comms_request,
            source_materials=self.state.general_comms_materials,
        )
        self._display(result)
        return result

