from typing import Any, List, Optional, Literal, Union, Dict
from pydantic import BaseModel

# Retell -> Your Server Events


class Utterance(BaseModel):
    role: Literal["agent", "user", "system"]
    content: str


class PingPongRequest(BaseModel):
    interaction_type: Literal["ping_pong"]
    timestamp: int


class CallDetailsRequest(BaseModel):
    interaction_type: Literal["call_details"]
    call: dict


class UpdateOnlyRequest(BaseModel):
    interaction_type: Literal["update_only"]
    transcript: List[Utterance]


class ResponseRequiredRequest(BaseModel):
    interaction_type: Literal["reminder_required", "response_required"]
    response_id: int
    transcript: List[Utterance]


CustomLlmRequest = ResponseRequiredRequest | UpdateOnlyRequest | CallDetailsRequest | PingPongRequest

# Your Server -> Retell Events


class ConfigResponse(BaseModel):
    response_type: Literal["config"] = "config"
    config: Dict[str, bool] = {
        "auto_reconnect": True,
        "call_details": True,
    }


class PingPongResponse(BaseModel):
    response_type: Literal["ping_pong"] = "ping_pong"
    timestamp: int


class ResponseResponse(BaseModel):
    response_type: Literal["response"] = "response"
    response_id: int
    content: str
    content_complete: bool
    end_call: Optional[bool] = False
    transfer_number: Optional[str] = None


CustomLlmResponse = ConfigResponse | PingPongResponse | ResponseResponse
