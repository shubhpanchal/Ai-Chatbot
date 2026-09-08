"""Unit tests for token cost calculation and pricing matrices."""

from decimal import Decimal

from app.services.cost import CostCalculatorService, ModelPricing


def test_cost_calculator_gpt_4o_mini() -> None:
    """Verify cost calculation for gpt-4o-mini ($0.15/1M input, $0.60/1M output)."""
    service = CostCalculatorService()

    # 100 prompt tokens, 50 completion tokens
    # prompt = 100 * 0.00000015 = 0.000015
    # completion = 50 * 0.00000060 = 0.000030
    # total = 0.000045
    cost = service.calculate_cost("gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
    assert cost == Decimal("0.000045")


def test_cost_calculator_gpt_4o() -> None:
    """Verify cost calculation for gpt-4o ($2.50/1M input, $10.00/1M output)."""
    service = CostCalculatorService()

    # 1000 prompt tokens, 500 completion tokens
    # prompt = 1000 * 0.00000250 = 0.002500
    # completion = 500 * 0.00001000 = 0.005000
    # total = 0.007500
    cost = service.calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert cost == Decimal("0.007500")


def test_cost_calculator_zero_tokens() -> None:
    """Verify zero token usage results in zero cost."""
    service = CostCalculatorService()
    cost = service.calculate_cost("gpt-4o-mini", prompt_tokens=0, completion_tokens=0)
    assert cost == Decimal("0.000000")


def test_cost_calculator_custom_pricing_table() -> None:
    """Verify CostCalculatorService with custom model pricing rates."""
    custom_table = {
        "custom-llm": ModelPricing(
            prompt_rate_per_token=Decimal("0.00000500"),
            completion_rate_per_token=Decimal("0.00001500"),
        )
    }
    service = CostCalculatorService(pricing_table=custom_table)

    cost = service.calculate_cost("custom-llm", prompt_tokens=200, completion_tokens=100)
    # prompt = 200 * 0.00000500 = 0.001000
    # completion = 100 * 0.00001500 = 0.001500
    # total = 0.002500
    assert cost == Decimal("0.002500")
