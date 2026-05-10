"""
서울 시청 근처 맛집 웹 앱
Flask 기반으로 식당 목록 조회 및 랜덤 추천 기능을 제공합니다.
"""

import os
import json
import random
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# restaurants.json 경로
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restaurants.json")


def load_restaurants():
    """restaurants.json에서 식당 데이터 로드"""
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@app.route("/")
def index():
    """메인 페이지"""
    restaurants = load_restaurants()
    return render_template("index.html", restaurants=restaurants)


@app.route("/api/recommend")
def recommend():
    """랜덤 3개 식당 추천 API"""
    restaurants = load_restaurants()
    count = min(3, len(restaurants))
    picks = random.sample(restaurants, count)
    return jsonify(picks)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
