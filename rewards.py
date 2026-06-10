"""Reward milestone calculation.

Rules:
- 100 -> 3500
- 200 -> 5555
- 300 -> 6500
- 400-900: +200 per 100 (so 400=6700, 500=6900, 600=7100, 700=7300, 800=7500, 900=7700)
- 1000+: +500 per 100 starting from 900 baseline (1000=8200, 1100=8700, ...)
"""
from __future__ import annotations

REWARD_TABLE: dict[int, int] = {
    100: 3500,
    200: 5555,
    300: 6500,
}

# 400..900 step +200 from 300 value? Spec: "400-900 tin: tăng 200đ mỗi 100 tin"
# baseline is 6500 (mốc 300). 400=6700, 500=6900, 600=7100, 700=7300, 800=7500, 900=7700
_base = 6500
for _m in range(400, 1000, 100):
    _base += 200
    REWARD_TABLE[_m] = _base
# 1000+ : +500 each 100
# 1000 = 8200 (per spec). 900 was 7700, +500 = 8200. ok.
_base_k = 7700
def _ensure(milestone: int) -> int:
    if milestone in REWARD_TABLE:
        return REWARD_TABLE[milestone]
    if milestone < 100 or milestone % 100 != 0:
        return 0
    # Build up to milestone
    last = max(k for k in REWARD_TABLE if k <= milestone) if any(k <= milestone for k in REWARD_TABLE) else 0
    val = REWARD_TABLE[last]
    m = last
    while m < milestone:
        m += 100
        if m <= 900:
            val += 200
        else:
            val += 500
        REWARD_TABLE[m] = val
    return REWARD_TABLE[milestone]

# Pre-build up to 2000
for _m in range(1000, 2100, 100):
    _ensure(_m)


def get_reward_amount(milestone: int) -> int:
    return _ensure(milestone)


def milestone_for(total_today: int) -> int | None:
    """Return milestone reached if today's count just crossed a 100 mark, else None.
    Caller should compare with highest_reward to avoid double reward.
    """
    if total_today < 100:
        return None
    return (total_today // 100) * 100


def next_milestone(current: int) -> int:
    if current < 100:
        return 100
    return ((current // 100) + 1) * 100


def format_money(amount: int) -> str:
    if amount % 1000 == 0:
        return f"{amount // 1000}k"
    return f"{amount/1000:.3f}".rstrip("0").rstrip(".") + "k"


RANKS = [
    (0, 99, "🥉 Người Mới"),
    (100, 299, "🔈 Loa Mini"),
    (300, 499, "🔊 Loa Phường"),
    (500, 999, "🔊 Loa Phường Full Pin"),
    (1000, 10**12, "👑 Ông Hoàng Tương Tác"),
]


def get_rank(total: int) -> str:
    for lo, hi, name in RANKS:
        if lo <= total <= hi:
            return name
    return RANKS[0][2]
