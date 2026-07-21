from .auth import LoginRequest, RegisterRequest, Token, TokenPayload, MessageResponse
from .user import UserCreate, UserOut, UserUpdate
from .card import CardCreate, CardOut, CardUpdate, CardMove
from .phase import PhaseCreate, PhaseOut, PhaseUpdate, PhaseWithCards, PhaseReorder
from .board import BoardCreate, BoardOut, BoardUpdate, BoardWithPhases

# Resolve forward references for nested schemas
PhaseWithCards.model_rebuild()
BoardWithPhases.model_rebuild()

__all__ = [
    "LoginRequest", "RegisterRequest",
    "Token", "TokenPayload", "MessageResponse",
    "UserCreate", "UserOut", "UserUpdate",
    "BoardCreate", "BoardOut", "BoardUpdate", "BoardWithPhases",
    "PhaseCreate", "PhaseOut", "PhaseUpdate", "PhaseWithCards", "PhaseReorder",
    "CardCreate", "CardOut", "CardUpdate", "CardMove",
]
