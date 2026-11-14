"""Token request/response models. Shapes confirmed on the Seller API dashboard (api-spec.md 3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TokenRequest(BaseModel):
    client_id: str
    client_secret: SecretStr

    def to_body(self) -> dict[str, str]:
        return {
            "clientId": self.client_id,
            "clientSecret": self.client_secret.get_secret_value(),
        }


class TokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    access_token: SecretStr = Field(alias="accessToken", min_length=1)
    expires_in: int = Field(alias="expiresIn", gt=0)
    token_type: str = Field(default="Bearer", alias="tokenType")
