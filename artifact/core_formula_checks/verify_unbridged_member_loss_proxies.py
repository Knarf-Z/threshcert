from fractions import Fraction


resistances = [1, 3, 6, 8, 11, 16, 25]
threshold = 4
expected = {
    "CERTIFIED_ATTACKER_PAYMENT": Fraction(0),
    "UNBRIDGED_MEMBER_FLOOR_PROXY": Fraction(4),
    "UNBRIDGED_LOWER_TAIL_PROXY": Fraction(18),
    "INVALID_MEAN_HEURISTIC": Fraction(40),
}
actual = {
    "CERTIFIED_ATTACKER_PAYMENT": Fraction(0),
    "UNBRIDGED_MEMBER_FLOOR_PROXY": threshold * min(resistances),
    "UNBRIDGED_LOWER_TAIL_PROXY": sum(sorted(resistances)[:threshold]),
    "INVALID_MEAN_HEURISTIC": threshold * Fraction(sum(resistances), len(resistances)),
}

for name, value in actual.items():
    if value != expected[name]:
        raise AssertionError(f"{name}: expected {expected[name]}, actual {value}")
    print(f"{name}={value}")

print("LOSS_PAYMENT_SEMANTIC_BOUNDARY=PASS")
