"""Cost calculation service for estimating USD cost based on token usage and model pricing."""

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple


class ModelPricing(NamedTuple):
    """Token pricing rates in USD per token."""

    prompt_rate_per_token: Decimal
    completion_rate_per_token: Decimal


# Standard token pricing matrix (USD per single token)
PRICING_REGISTRY: dict[str, ModelPricing] = {
    # gpt-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
    "gpt-4o-mini": ModelPricing(
        prompt_rate_per_token=Decimal("0.00000015"),
        completion_rate_per_token=Decimal("0.00000060"),
    ),
    # gpt-4o: $2.50 / 1M prompt, $10.00 / 1M completion
    "gpt-4o": ModelPricing(
        prompt_rate_per_token=Decimal("0.00000250"),
        completion_rate_per_token=Decimal("0.00001000"),
    ),
    # gpt-3.5-turbo: $0.50 / 1M prompt, $1.50 / 1M completion
    "gpt-3.5-turbo": ModelPricing(
        prompt_rate_per_token=Decimal("0.00000050"),
        completion_rate_per_token=Decimal("0.00000150"),
    ),
}

# Fallback pricing rate for unknown/custom models
DEFAULT_PRICING = ModelPricing(
    prompt_rate_per_token=Decimal("0.00000100"),
    completion_rate_per_token=Decimal("0.00000200"),
)


class CostCalculatorService:
    """Calculates estimated financial costs of LLM API requests."""

    def __init__(self, pricing_table: dict[str, ModelPricing] | None = None) -> None:
        self.pricing_table = pricing_table or PRICING_REGISTRY

    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Decimal:
        """Calculate the total estimated cost in USD for the given token split.

        Returns Decimal rounded to 6 decimal places.
        """
        pricing = self.pricing_table.get(model, DEFAULT_PRICING)
        prompt_cost = Decimal(prompt_tokens) * pricing.prompt_rate_per_token
        completion_cost = Decimal(completion_tokens) * pricing.completion_rate_per_token
        total_cost = prompt_cost + completion_cost
        return total_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
