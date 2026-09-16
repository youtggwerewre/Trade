import math
import config


def calculate_lot_size(balance: float, risk_percent: float, stop_loss_distance: float,
                        contract_size: float = None) -> float:
    """
    balance: account balance in USD
    risk_percent: e.g. 1.0 for 1%
    stop_loss_distance: |entry - stop_loss| in price (e.g. 8.50)
    contract_size: oz per standard lot for YOUR broker/account (defaults to
    config.CONTRACT_SIZE_PER_LOT = 100). Some brokers offer smaller XAUUSD
    contracts on micro/cent accounts specifically for small balances — set
    this to match yours via the bot's /contractsize command.
    """
    contract_size = contract_size or config.CONTRACT_SIZE_PER_LOT
    if stop_loss_distance <= 0 or balance <= 0:
        return 0.0
    risk_amount = balance * (risk_percent / 100)
    raw_lots = risk_amount / (stop_loss_distance * contract_size)
    steps = math.floor(raw_lots / config.LOT_STEP)
    return round(steps * config.LOT_STEP, 2)


def lot_size_breakdown(balance: float, risk_percent: float, stop_loss_distance: float,
                        contract_size: float = None) -> dict:
    """
    Same calculation, but instead of silently returning 0.0 lots when the
    target risk can't be hit at all, reports exactly what the SMALLEST
    tradeable lot would actually cost — so a small account gets an honest
    answer instead of a blank number.
    """
    contract_size = contract_size or config.CONTRACT_SIZE_PER_LOT
    lots = calculate_lot_size(balance, risk_percent, stop_loss_distance, contract_size)

    if lots >= config.LOT_STEP:
        actual_risk = lots * contract_size * stop_loss_distance
        return {
            "lots": lots,
            "affordable": True,
            "risk_amount": round(actual_risk, 2),
            "risk_percent_actual": round(100 * actual_risk / balance, 1) if balance else 0.0,
        }

    if balance <= 0 or stop_loss_distance <= 0:
        return {"lots": 0.0, "affordable": False, "risk_amount": 0.0, "risk_percent_actual": 0.0}

    min_lot_risk = config.LOT_STEP * contract_size * stop_loss_distance
    return {
        "lots": 0.0,
        "affordable": False,
        "risk_amount": round(min_lot_risk, 2),
        "risk_percent_actual": round(100 * min_lot_risk / balance, 1),
    }
