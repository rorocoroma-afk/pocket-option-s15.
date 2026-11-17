
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import math

app = Flask(__name__)
CORS(app)

TIMEFRAME_SECONDS = 15
EXPIRY_SECONDS = 15


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "name": "Pocket Option S15 AI",
        "timeframe": "15 secondes"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "OK"})


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value * multiplier) + (
            result * (1 - multiplier)
        )

    return result


def rsi(values, period=14):
    if len(values) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def analyze_candles(candles):
    if len(candles) < 30:
        raise ValueError("Il faut au moins 30 bougies S15.")

    candles = sorted(candles, key=lambda c: c["time"])

    closes = [float(c["close"]) for c in candles]

    # Vérifier les intervalles de 15 secondes
    for i in range(1, len(candles)):
        difference = (
            int(candles[i]["time"]) -
            int(candles[i - 1]["time"])
        )

        if difference != TIMEFRAME_SECONDS:
            raise ValueError(
                "Les bougies doivent être espacées de 15 secondes."
            )

    fast = ema(closes, 9)
    slow = ema(closes, 21)
    strength = rsi(closes)

    if fast is None or slow is None or strength is None:
        raise ValueError("Données insuffisantes.")

    score = 0
    reasons = []

    if fast > slow:
        score += 1
        reasons.append("Tendance haussière EMA")

    elif fast < slow:
        score -= 1
        reasons.append("Tendance baissière EMA")

    if closes[-1] > closes[-2]:
        score += 1
        reasons.append("Dernière bougie haussière")

    elif closes[-1] < closes[-2]:
        score -= 1
        reasons.append("Dernière bougie baissière")

    if strength < 30:
        score += 1
        reasons.append("RSI en zone basse")

    elif strength > 70:
        score -= 1
        reasons.append("RSI en zone haute")

    if score >= 2:
        signal = "CALL"
    elif score <= -2:
        signal = "PUT"
    else:
        signal = "ATTENDRE"

    # Score technique, pas une probabilité de réussite
    confidence_score = min(95, abs(score) * 25 + 20)

    if signal == "ATTENDRE":
        confidence_score = 0

    return {
        "signal": signal,
        "timeframe": "S15",
        "expiry_seconds": EXPIRY_SECONDS,
        "confidence_score": confidence_score,
        "score_type": "Score technique, non calibré",
        "rsi": round(strength, 2),
        "ema_9": round(fast, 6),
        "ema_21": round(slow, 6),
        "reasons": reasons,
        "analyzed_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    market = data.get("market")
    candles = data.get("candles")

    if not market:
        return jsonify({"error": "Choisis un marché."}), 400

    if not candles or not isinstance(candles, list):
        return jsonify({
            "error": "Aucune bougie réelle reçue."
        }), 400

    try:
        result = analyze_candles(candles)
        result["market"] = market

        return jsonify(result)

    except (ValueError, KeyError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
